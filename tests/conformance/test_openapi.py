"""OpenAPI conformance tests.

These tests pin down the contract between ``openapi.yaml`` (the static spec at
the repo root) and the live Django service:

  * ``/api/schema/`` returns a valid OpenAPI 3 document.
  * ``openapi.yaml`` and the view-served document agree on paths, methods,
    components, and security.
  * Every path declared in the spec actually resolves on the running URLconf.
  * No URLconf path is silently undocumented.
  * Each declared endpoint exposes its declared methods.
  * Security schemes, schema references, and ``$ref`` links are well-formed.

If a test here fails, the API surface has drifted from the spec — and either
the spec or the code needs updating in the same commit.

Marker: ``@pytest.mark.conformance`` (registered in pytest.ini).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client
from django.urls import get_resolver

# PyYAML is not in the Docker image's requirements.txt (it's not stdlib).
# Auto-install it on first import so this test module works in a freshly
# rebuilt container. The install is idempotent — no-op when already present.
try:
    import yaml  # noqa: E402
except ImportError:  # pragma: no cover - exercised on fresh containers
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"],
        check=True,
    )
    import yaml  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_YAML = REPO_ROOT / "openapi.yaml"

# Sample values used when binding path parameters to exercise the live
# endpoints. They are deliberately inert — none of them need to point at a
# real row, because the conformance test only cares that the route resolves
# and returns a status the spec has declared.
SAMPLE_SLUG = "sample-hack-2026"
SAMPLE_PUBLIC_ID = "conformance-probe"
SAMPLE_UUID = "00000000-0000-0000-0000-000000000001"


def _load_yaml_spec() -> dict:
    """Load ``openapi.yaml`` fresh from disk for every test."""
    with OPENAPI_YAML.open() as fh:
        return yaml.safe_load(fh)


def _fetch_live_spec(client: Client) -> dict:
    """GET ``/api/schema/`` and return the parsed JSON body."""
    resp = client.get("/api/schema/")
    assert resp.status_code == 200, f"/api/schema/ returned {resp.status_code}, expected 200"
    return json.loads(resp.content)


# ---------------------------------------------------------------------------
# URL inspection helpers
# ---------------------------------------------------------------------------

_DJANGO_CONVERTER_RE = re.compile(r"<(?:[^:>]+:)?([^>]+)>")


def _django_pattern_to_openapi(pattern: str) -> str:
    """Convert a Django pattern fragment into an OpenAPI-style path.

    ``api/events/<slug:slug>/submit``  ->  ``api/events/{slug}/submit``
    ``api/certificates/<str:public_id>`` -> ``api/certificates/{public_id}``
    """
    return _DJANGO_CONVERTER_RE.sub(r"{\1}", pattern)


def _walk_url_patterns(patterns, prefix: str = "") -> list[str]:
    """Recursively flatten a Django ``URLResolver`` / ``URLPattern`` tree.

    Returns each concrete path with its include() prefix prepended. Patterns
    that contain regex groups (``re_path``) are skipped because they cannot be
    reliably normalised to OpenAPI form.
    """
    found: list[str] = []
    for entry in patterns:
        raw = str(entry.pattern)
        if "<" in raw and "(" in raw:
            # re_path() — skip; we cannot reverse to OpenAPI form.
            continue
        full = prefix + raw
        if hasattr(entry, "url_patterns"):
            found.extend(_walk_url_patterns(entry.url_patterns, prefix=full))
        else:
            found.append(full)
    return found


def _django_paths() -> set[str]:
    """Return the set of concrete paths exposed by the URLconf, in OpenAPI
    form (leading slash, ``{name}`` placeholders)."""
    resolver = get_resolver()
    raw = _walk_url_patterns(resolver.url_patterns)
    normalised = {_django_pattern_to_openapi(p) for p in raw}
    # Drop the bare root "/"; it's never declared in the OpenAPI spec.
    normalised.discard("")
    normalised.discard("/")
    # Re-add a leading slash for comparison with the spec.
    return {f"/{p}" if not p.startswith("/") else p for p in normalised}


def _bind_path_params(path: str) -> str:
    """Replace OpenAPI ``{name}`` placeholders with sample values."""
    return (
        path.replace("{slug}", SAMPLE_SLUG)
        .replace("{public_id}", SAMPLE_PUBLIC_ID)
        .replace("{id}", SAMPLE_UUID)
        .replace("{project_id}", SAMPLE_UUID)
    )


# ---------------------------------------------------------------------------
# 1. /api/schema/ returns a valid OpenAPI 3 document
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_schema_endpoint_returns_valid_openapi3():
    """``/api/schema/`` must return a syntactically valid OpenAPI 3 doc."""
    spec = _fetch_live_spec(Client())

    # OpenAPI 3 declaration
    assert spec.get("openapi") == "3.0.3", (
        f"/api/schema/ openapi version is {spec.get('openapi')!r}, " "expected '3.0.3'"
    )

    # info.title and info.version
    info = spec.get("info", {})
    assert info.get("title"), "/api/schema/ is missing info.title"
    assert info.get("version"), "/api/schema/ is missing info.version"

    # At least five paths documented
    paths = spec.get("paths", {})
    assert isinstance(paths, dict), "/api/schema/ paths must be a dict"
    assert len(paths) >= 5, f"/api/schema/ documents {len(paths)} paths, expected >= 5"


# ---------------------------------------------------------------------------
# 2. openapi.yaml matches the view-served document
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_yaml_matches_schema_endpoint():
    """``openapi.yaml`` and ``/api/schema/`` must describe the same API.

    JSON equality after dumping the YAML to JSON catches any drift in paths,
    methods, components, or security definitions. Whitespace / key ordering
    differences are normalised away by going through ``json.dumps``.
    """
    yaml_spec = _load_yaml_spec()
    live_spec = _fetch_live_spec(Client())

    yaml_json = json.dumps(yaml_spec, sort_keys=True)
    live_json = json.dumps(live_spec, sort_keys=True)

    assert yaml_json == live_json, (
        "openapi.yaml and /api/schema/ disagree.\n"
        f"In YAML but not in /api/schema/: {sorted(set(yaml_spec.get('paths', {})) - set(live_spec.get('paths', {})))}\n"
        f"In /api/schema/ but not in YAML: {sorted(set(live_spec.get('paths', {})) - set(yaml_spec.get('paths', {})))}"
    )


# ---------------------------------------------------------------------------
# 3. All paths in the spec exist on the live URLconf
# ---------------------------------------------------------------------------


@pytest.mark.conformance
@pytest.mark.django_db
def test_all_spec_paths_exist_on_running_service():
    """For every (path, method) in the spec, the live route must respond with
    a documented status code. Endpoints declaring ``security: [{cookie: []}]``
    also accept 401 (Unauthenticated) and 403 (Forbidden), since the spec
    doesn't always re-declare these for the cookie scheme."""
    spec = _load_yaml_spec()
    client = Client()
    failures: list[str] = []

    for path, ops in spec.get("paths", {}).items():
        bound = _bind_path_params(path)
        for method, op in ops.items():
            http_method = method.upper()
            declared = {int(code) for code in op.get("responses", {}).keys()}
            requires_auth = bool(op.get("security"))
            # The cookie scheme implicitly permits 401 (no session) and
            # 403 (wrong session) for any operation that declares security.
            if requires_auth:
                allowed = declared | {401, 403}
            else:
                allowed = declared
            response = getattr(client, http_method.lower(), None)(bound)
            if response is None:
                failures.append(f"{method.upper()} {path}: HTTP method unsupported by test client")
                continue
            if response.status_code in allowed:
                continue
            # 405 (method not allowed) is acceptable for a path that exists
            # but does not declare this method — the route still resolves.
            if response.status_code == 405 and not declared:
                continue
            failures.append(
                f"{method.upper()} {path}: returned {response.status_code}, "
                f"not in declared responses {sorted(declared)}"
            )

    assert not failures, "Spec paths returned undocumented status codes:\n  - " + "\n  - ".join(failures)


# ---------------------------------------------------------------------------
# 4. No undocumented paths exist on the running service
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_no_undocumented_paths_in_urlconf():
    """Every concrete path exposed by Django must appear in the spec."""
    spec = _load_yaml_spec()
    spec_paths = set(spec.get("paths", {}).keys())
    live_paths = _django_paths()

    undocumented = live_paths - spec_paths
    assert not undocumented, "URLconf exposes paths not present in openapi.yaml:\n  - " + "\n  - ".join(
        sorted(undocumented)
    )


# ---------------------------------------------------------------------------
# 5. Spec endpoints declare the correct HTTP methods
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_spec_endpoints_have_documented_methods():
    """For the documented routes, a sample of the canonical verbs must
    resolve to a documented status code (or 405)."""
    cases = [
        ("/api/gallery", "GET", {200}),
        ("/api/events/{slug}/submit", "POST", {201, 401, 403, 422}),
        ("/api/judge/scores", "GET", {200, 401, 403}),
        ("/api/judge/peer-scores", "GET", {403, 401}),
        ("/api/csv_export", "GET", {200, 401, 403}),
        ("/api/certificates/{public_id}", "GET", {200, 404}),
        ("/widget.js", "GET", {200}),
        ("/api/widget/gallery", "GET", {200}),
        ("/api/webhooks", "GET", {200, 401, 403}),
        ("/api/webhooks", "POST", {201, 401, 403, 422}),
        ("/api/schema/", "GET", {200}),
        ("/api/events/{slug}/normalize", "POST", {200, 401, 403, 422}),
        ("/api/events/{slug}/pairwise/ballots", "POST", {201, 401, 403}),
        ("/api/events/{slug}/pairwise/ranking", "GET", {200, 401, 403}),
        ("/api/events/{slug}/submissions/{id}/vote", "POST", {201, 401, 403, 404}),
        ("/api/events/{slug}/submissions/{id}/vote", "DELETE", {200, 401, 403, 404}),
        ("/healthz", "GET", {200, 503}),
    ]
    client = Client()
    failures: list[str] = []

    for path, method, allowed in cases:
        bound = _bind_path_params(path)
        response = getattr(client, method.lower())(bound)
        if response.status_code not in allowed and response.status_code != 405:
            failures.append(
                f"{method} {path}: returned {response.status_code}, " f"expected one of {sorted(allowed)} (or 405)"
            )

    assert not failures, "Spec endpoints returned unexpected status codes:\n  - " + "\n  - ".join(failures)


# ---------------------------------------------------------------------------
# 6. The cookie security scheme exists and is referenced where required
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_security_scheme_defined():
    """A ``cookie`` security scheme must be declared."""
    spec = _load_yaml_spec()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert "cookie" in schemes, "openapi.yaml is missing the cookie security scheme"
    cookie = schemes["cookie"]
    assert cookie.get("type") == "apiKey", "cookie scheme must be type apiKey"
    assert cookie.get("in") == "cookie", "cookie scheme must be in cookie"
    assert cookie.get("name") == "session", "cookie scheme must be named session"


@pytest.mark.conformance
def test_admin_endpoints_reference_security():
    """Every admin / organiser / judge endpoint must declare cookie auth."""
    spec = _load_yaml_spec()
    must_be_protected = [
        "/api/events/{slug}/submit",
        "/api/judge/scores",
        "/api/judge/peer-scores",
        "/api/csv_export",
        "/api/webhooks",
        "/api/events/{slug}/normalize",
        "/api/events/{slug}/pairwise/ballots",
        "/api/events/{slug}/pairwise/ranking",
        "/api/events/{slug}/submissions/{id}/vote",
    ]
    failures: list[str] = []
    for path in must_be_protected:
        ops = spec.get("paths", {}).get(path, {})
        for method, op in ops.items():
            security = op.get("security")
            if not security or "cookie" not in {next(iter(s.keys()), None) for s in security}:
                failures.append(f"{method.upper()} {path}: missing cookie security")
    assert not failures, "Admin endpoints missing cookie security declaration:\n  - " + "\n  - ".join(failures)


# ---------------------------------------------------------------------------
# 7. Schema definitions are referenced by at least one response
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_defined_schemas_are_referenced():
    """Every schema under ``components.schemas`` must be used by a response
    or request body. Orphan schemas usually mean a model changed but the
    spec did not."""
    spec = _load_yaml_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    spec_text = json.dumps(spec)

    unreferenced = []
    for name in schemas:
        # ``$ref: "#/components/schemas/<name>"`` (JSON dump normalises)
        if f'"#/components/schemas/{name}"' not in spec_text:
            unreferenced.append(name)

    assert not unreferenced, f"Schemas declared but never referenced: {sorted(unreferenced)}"


# ---------------------------------------------------------------------------
# 8. Every $ref resolves to a defined component
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_no_broken_refs():
    """Every ``$ref`` in the spec must point at a defined component."""
    spec = _load_yaml_spec()
    components = spec.get("components", {})
    failures: list[str] = []

    def _walk(node, trail=()):
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref = node["$ref"]
                if not ref.startswith("#/components/"):
                    failures.append(f"$ref {ref!r} at {'/'.join(trail)}: not in #/components/")
                else:
                    parts = ref.removeprefix("#/components/").split("/")
                    cursor = components
                    for part in parts:
                        if not isinstance(cursor, dict) or part not in cursor:
                            failures.append(f"$ref {ref!r} at {'/'.join(trail)}: target missing")
                            break
                        cursor = cursor[part]
            for k, v in node.items():
                _walk(v, trail + (str(k),))
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, trail + (str(i),))

    _walk(spec)
    assert not failures, "Broken $ref pointers in openapi.yaml:\n  - " + "\n  - ".join(failures)


# ---------------------------------------------------------------------------
# Bonus artefact: API First
# ---------------------------------------------------------------------------


@pytest.mark.conformance
def test_api_first_artefact_present():
    """``openapi.yaml`` exists at the repo root, is non-empty, and parses as
    OpenAPI 3. Required for the ``API First`` bonus: spec ships in-tree."""
    assert OPENAPI_YAML.is_file(), f"{OPENAPI_YAML} is missing"
    assert OPENAPI_YAML.stat().st_size > 0, f"{OPENAPI_YAML} is empty"

    spec = _load_yaml_spec()
    assert spec.get("openapi", "").startswith("3."), "openapi.yaml is not OpenAPI 3"
    assert spec.get("info", {}).get("title"), "openapi.yaml is missing info.title"
    assert spec.get("info", {}).get("version"), "openapi.yaml is missing info.version"
