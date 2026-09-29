"""T4: bulk import/export — POST /api/events/<slug>/import and GET
/api/events/<slug>/export.

Covered here:

* role gates — both endpoints are organizer-only, with the documented
  bootstrap exception on import: a FRESH slug may be imported by any
  organizer (nobody can hold a membership in an event that doesn't
  exist yet), while an existing slug requires being THAT event's
  organizer;
* input validation — bodies over 5 MiB are 413'd before parsing;
  truncated, malformed or non-object bodies are 422'd (never a 500);
  a failed import is atomic, so not even a bootstrapped event survives;
* importer semantics for the OFFICIAL fixtures.json (repo root): 41
  project rows collapse to 40 submissions (prj_41 is a deliberate
  resubmit by tm_07 — Submission is OneToOne with Team) and 126 score
  rows collapse to 123 distinct (judge, submission) assignments;
* the acceptance property: import fixtures.json -> export A -> import A
  into a FRESH slug -> export B -> A == B, byte for byte. The exporter
  (apps/api/exporter.py) exists for exactly this property: deterministic
  orderings, fixture-style ids derived from import-stable sorts, and
  the synthetic demo participant's artifacts excluded (the importer
  re-seeds them itself, into the first team in *file* order, which is
  not stable across slugs).
"""

import json
from pathlib import Path

import pytest
from django.test import Client

from apps.api.views import MAX_IMPORT_BYTES
from apps.events.models import Event, Membership
from apps.judging.models import JudgeAssignment, Review, Score
from apps.submissions.models import Submission
from apps.teams.models import Team

pytestmark = [pytest.mark.bulk]

REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_FIXTURES = json.loads((REPO_ROOT / "fixtures.json").read_text(encoding="utf-8"))

# What the official fixtures.json holds verbatim...
FIXTURE_PROJECT_ROWS = 41
FIXTURE_JUDGE_ROWS = 30
FIXTURE_TEAM_ROWS = 40
FIXTURE_SCORE_ROWS = 126

# ...and what the schema stores it as after the documented collapses
# (prj_41 overwrites prj_07's row for tm_07; the 126 score rows share
# 123 distinct (judge, submission) pairs).
EXPECTED_SUBMISSIONS = 40
EXPECTED_ASSIGNMENTS = 123
EXPECTED_SCORES = EXPECTED_ASSIGNMENTS * 3  # functionality/quality/innovation per assignment

# The exporter derives the event id from the event NAME (the one event
# field the importer restores verbatim) so that A == B holds across
# different slugs.
FIXTURE_EVENT_NAME = "Sample Hack 2026"
FIXTURE_EVENT_ID = "evt_sample-hack-2026"


def _import_path(slug):
    return f"/api/events/{slug}/import"


def _export_path(slug):
    return f"/api/events/{slug}/export"


def _import_fixtures(client, slug, body=None):
    """POST the official fixtures.json (or ``body``) into ``slug``."""
    return client.post(
        _import_path(slug),
        body if body is not None else OFFICIAL_FIXTURES,
        content_type="application/json",
    )


def _export_bytes(client, slug) -> bytes:
    """GET the export and return the raw streamed bytes."""
    resp = client.get(_export_path(slug))
    assert resp.status_code == 200, f"export of {slug!r} returned {resp.status_code}"
    return b"".join(resp.streaming_content)


def _minimal_body():
    """The smallest body that passes the view's shape validation AND the
    importer's own dereferencing — a valid single-team event with one
    project (scores are optional and omitted)."""
    return {
        "event": {"name": "Tiny", "submissions_close": "2026-03-01T18:00:00Z"},
        "tracks": [{"id": "trk_01", "name": "Main"}],
        "judges": [{"id": "jdg_01", "name": "J", "email": "j@ex.org", "tracks": []}],
        "teams": [{"id": "tm_01", "name": "Solo", "members": ["solo@example.org"]}],
        "projects": [
            {
                "id": "prj_01",
                "team": "tm_01",
                "track": "trk_01",
                "title": "Tiny Project",
                "summary": "One line.",
                "submitted_at": "2026-02-27T04:08:00Z",
            }
        ],
    }


def _db_counts(event):
    """Row counts that must be stable across an idempotent re-import."""
    return (
        Submission.objects.filter(event=event).count(),
        Team.objects.filter(event=event).count(),
        event.tracks.count(),
        JudgeAssignment.objects.filter(batch__event=event).count(),
        Score.objects.filter(assignment__batch__event=event).count(),
        Review.objects.filter(assignment__batch__event=event).count(),
    )


class TestExportAccess:
    def test_anonymous_gets_401(self, sample_event):
        assert Client().get(_export_path(sample_event.slug)).status_code == 401

    def test_participant_gets_403(self, sample_event, auth_client):
        resp = auth_client["participant"].get(_export_path(sample_event.slug))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"

    def test_judge_gets_403(self, sample_event, auth_client):
        assert auth_client["judge_a"].get(_export_path(sample_event.slug)).status_code == 403

    def test_missing_event_is_403_for_organizer(self, sample_event, auth_client):
        # House behavior of the shared [IsAuthenticated, IsOrganizer]
        # permission pair: a slug that resolves to no event fails the
        # permission check, so a non-admin organizer sees 403 — never a
        # 404 (the 404 below is admin-only).
        assert auth_client["organizer"].get(_export_path("no-such-event")).status_code == 403


class TestExportShape:
    """GET export of an importer-seeded event: the exact fixtures shape,
    the documented counts, deterministic ids, and no demo-participant
    artifacts."""

    def test_shape_counts_and_ids(self, sample_event, auth_client):
        slug = "bulk-shape"
        assert _import_fixtures(auth_client["organizer"], slug).status_code == 200

        body = json.loads(_export_bytes(auth_client["organizer"], slug))

        assert set(body) == {"event", "tracks", "judges", "teams", "projects", "scores"}
        assert body["event"] == {
            "id": FIXTURE_EVENT_ID,
            "name": FIXTURE_EVENT_NAME,
            "submissions_close": "2026-03-01T18:00:00+00:00",
        }
        assert len(body["tracks"]) == 8
        assert len(body["judges"]) == FIXTURE_JUDGE_ROWS
        assert len(body["teams"]) == FIXTURE_TEAM_ROWS
        # 41 fixture project rows -> 40 stored submissions (prj_41 is the
        # deliberate resubmit for tm_07) -> 40 exported projects.
        assert len(body["projects"]) == EXPECTED_SUBMISSIONS
        # 126 fixture score rows -> 123 stored (judge, submission) pairs.
        assert len(body["scores"]) == EXPECTED_ASSIGNMENTS

        # Fixture-style ids, densely renumbered by the exporter's stable
        # sorts — prj_41 (the collapsed resubmit) cannot appear.
        assert [t["id"] for t in body["tracks"]] == [f"trk_{i:02d}" for i in range(1, 9)]
        assert [j["id"] for j in body["judges"]] == [f"jdg_{i:02d}" for i in range(1, 31)]
        assert [t["id"] for t in body["teams"]] == [f"tm_{i:02d}" for i in range(1, 41)]
        assert [p["id"] for p in body["projects"]] == [f"prj_{i:02d}" for i in range(1, 41)]

        # Every score row points at ids the sections define, carries the
        # importer's three standard criteria keys, and has a comment.
        judge_ids = {j["id"] for j in body["judges"]}
        project_ids = {p["id"] for p in body["projects"]}
        for row in body["scores"]:
            assert row["judge"] in judge_ids
            assert row["project"] in project_ids
            assert set(row["criteria"]) == {"functionality", "quality", "innovation"}
            assert isinstance(row["comment"], str)

        # Projects reference their team/track and carry the importer's
        # verbatim fields.
        team_ids = {t["id"] for t in body["teams"]}
        for project in body["projects"]:
            assert project["team"] in team_ids
            assert {"id", "team", "track", "title", "summary", "repo_url", "submitted_at"} == set(project)

    def test_demo_participant_artifacts_are_excluded(self, sample_event, auth_client):
        # import_fixtures seeds participant@test.local into the first
        # team in FILE order — which is not stable across slugs, so the
        # exporter must not emit it, or A == B would break.
        slug = "bulk-no-demo"
        assert _import_fixtures(auth_client["organizer"], slug).status_code == 200

        body = json.loads(_export_bytes(auth_client["organizer"], slug))

        members = [m for t in body["teams"] for m in t["members"]]
        assert "participant@test.local" not in members
        # The first-team membership is dropped, not the whole team: every
        # official fixture team has >= 1 real member of its own.
        assert all(t["members"] for t in body["teams"])

    def test_export_is_deterministic(self, sample_event, auth_client):
        slug = "bulk-determinism"
        assert _import_fixtures(auth_client["organizer"], slug).status_code == 200
        assert _export_bytes(auth_client["organizer"], slug) == _export_bytes(auth_client["organizer"], slug)

    def test_export_streams_attachment(self, sample_event, auth_client):
        slug = "bulk-attachment"
        assert _import_fixtures(auth_client["organizer"], slug).status_code == 200
        resp = auth_client["organizer"].get(_export_path(slug))
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("application/json")
        assert resp["Content-Disposition"] == f'attachment; filename="fixtures-{slug}.json"'


class TestImportAccess:
    def test_anonymous_cannot_import(self, sample_event):
        resp = Client().post(_import_path(sample_event.slug), OFFICIAL_FIXTURES, content_type="application/json")
        assert resp.status_code == 401
        # ...and cannot bootstrap a fresh event either.
        resp = Client().post(_import_path("bulk-anon-fresh"), OFFICIAL_FIXTURES, content_type="application/json")
        assert resp.status_code == 401
        assert not Event.objects.filter(slug="bulk-anon-fresh").exists()

    def test_participant_cannot_import_existing_event(self, sample_event, auth_client):
        resp = auth_client["participant"].post(
            _import_path(sample_event.slug), OFFICIAL_FIXTURES, content_type="application/json"
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"

    def test_judge_cannot_import(self, sample_event, auth_client):
        resp = auth_client["judge_a"].post(
            _import_path(sample_event.slug), OFFICIAL_FIXTURES, content_type="application/json"
        )
        assert resp.status_code == 403

    def test_participant_cannot_bootstrap_a_fresh_event(self, sample_event, auth_client):
        # The bootstrap exception is for ORGANIZERS only: a fresh slug
        # still requires organizing at least one event somewhere.
        slug = "bulk-fresh-denied"
        resp = auth_client["participant"].post(_import_path(slug), OFFICIAL_FIXTURES, content_type="application/json")
        assert resp.status_code == 403
        assert not Event.objects.filter(slug=slug).exists()

    def test_organizer_can_bootstrap_a_fresh_event(self, sample_event, auth_client):
        # No membership in "bulk-fresh" can exist — the import itself is
        # what creates the event. The organizer of sample_event may
        # bootstrap it.
        slug = "bulk-fresh"
        resp = _import_fixtures(auth_client["organizer"], slug)
        assert resp.status_code == 200
        event = Event.objects.get(slug=slug)
        assert Membership.objects.filter(user__email="organizer@test.local", event=event, role="organizer").exists()


class TestImportValidation:
    """Every rejection is a 4xx with the error envelope — a truncated or
    malformed body must NEVER reach a 500 inside the importer."""

    def _organizer_post(self, auth_client, body, content_type="application/json"):
        return auth_client["organizer"].post(
            _import_path("sample-hack-2026"), body, content_type=content_type
        )

    @pytest.mark.parametrize("missing", ["event", "tracks", "judges", "teams", "projects"])
    def test_missing_section_is_422(self, sample_event, auth_client, missing):
        body = {k: v for k, v in _minimal_body().items() if k != missing}
        resp = self._organizer_post(auth_client, body)
        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == "validation_failed"
        assert missing in error["message"]

    @pytest.mark.parametrize(
        "raw",
        ['[]', '"just a string"', "42", "null", "true", "[1, 2]"],
    )
    def test_non_object_json_body_is_422(self, sample_event, auth_client, raw):
        resp = self._organizer_post(auth_client, raw)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"

    @pytest.mark.parametrize(
        "raw",
        ["", '{"event": "truncated', "{", "not json at all", "]]"],
    )
    def test_broken_json_body_is_422_never_500(self, sample_event, auth_client, raw):
        resp = self._organizer_post(auth_client, raw)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"

    @pytest.mark.parametrize(
        "section,value",
        [("tracks", {}), ("judges", "x"), ("teams", 42), ("projects", {}), ("event", ["not", "a", "dict"])],
    )
    def test_wrong_section_type_is_422(self, sample_event, auth_client, section, value):
        body = _minimal_body()
        body[section] = value
        resp = self._organizer_post(auth_client, body)
        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == "validation_failed"
        assert section in error["message"]

    @pytest.mark.parametrize(
        "event_section",
        [
            {"name": "NoClose"},  # no submissions_close
            {"submissions_close": "2026-03-01T18:00:00Z"},  # no name
            {"name": 7, "submissions_close": 7},  # non-strings would 500 the importer
            {},
        ],
    )
    def test_event_section_requires_string_fields(self, sample_event, auth_client, event_section):
        body = _minimal_body()
        body["event"] = event_section
        resp = self._organizer_post(auth_client, body)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"

    def test_scores_must_be_a_list_when_present(self, sample_event, auth_client):
        body = _minimal_body()
        body["scores"] = {"judge": "jdg_01"}
        resp = self._organizer_post(auth_client, body)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"

    def test_oversized_body_is_413(self, sample_event, auth_client):
        # 1 byte over the limit, and JSON-valid — the guard fires before
        # parsing, so the body never reaches the importer.
        payload = '{"padding": "' + "x" * (MAX_IMPORT_BYTES - 14) + '"}'
        assert len(payload.encode()) == MAX_IMPORT_BYTES + 1
        resp = self._organizer_post(auth_client, payload)
        assert resp.status_code == 413
        error = resp.json()["error"]
        assert error["code"] == "payload_too_large"
        assert "5 MiB" in error["message"]

    def test_oversized_guard_fires_before_parsing(self, sample_event, auth_client):
        # Not even JSON — still 413, not a parse error.
        resp = self._organizer_post(auth_client, "x" * (MAX_IMPORT_BYTES + 1))
        assert resp.status_code == 413

    def test_non_json_content_type_is_415(self, sample_event, auth_client):
        resp = self._organizer_post(auth_client, "hello", content_type="text/plain")
        assert resp.status_code == 415

    def test_failed_import_is_atomic(self, sample_event, auth_client):
        # A project row referencing an unknown team id blows up inside
        # the importer — the view reports it as 422, and the importer's
        # transaction rolls back so not even the bootstrapped event
        # survives.
        slug = "bulk-atomic"
        body = _minimal_body()
        body["projects"][0]["team"] = "tm_99"
        resp = auth_client["organizer"].post(_import_path(slug), body, content_type="application/json")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert not Event.objects.filter(slug=slug).exists()


class TestImportSemantics:
    def test_bootstrap_imports_official_fixtures(self, sample_event, auth_client):
        slug = "bulk-official"
        resp = _import_fixtures(auth_client["organizer"], slug)
        assert resp.status_code == 200

        # The response counts describe the FILE, verbatim...
        assert resp.json() == {
            "event": slug,
            "imported": {
                "projects": FIXTURE_PROJECT_ROWS,
                "judges": FIXTURE_JUDGE_ROWS,
                "teams": FIXTURE_TEAM_ROWS,
                "scores": FIXTURE_SCORE_ROWS,
            },
        }

        # ...while the schema stores the documented collapses.
        event = Event.objects.get(slug=slug)
        assert event.name == FIXTURE_EVENT_NAME
        assert Submission.objects.filter(event=event).count() == EXPECTED_SUBMISSIONS
        assert Team.objects.filter(event=event).count() == EXPECTED_SUBMISSIONS  # 40 fixture teams
        assert event.tracks.count() == 8
        assert Membership.objects.filter(event=event, role="judge").count() == FIXTURE_JUDGE_ROWS
        assert JudgeAssignment.objects.filter(batch__event=event).count() == EXPECTED_ASSIGNMENTS
        assert Score.objects.filter(assignment__batch__event=event).count() == EXPECTED_SCORES
        assert Review.objects.filter(assignment__batch__event=event).count() == EXPECTED_ASSIGNMENTS

    def test_reimport_is_idempotent(self, sample_event, auth_client):
        organizer = auth_client["organizer"]
        slug = "bulk-idempotent"
        assert _import_fixtures(organizer, slug).status_code == 200
        event = Event.objects.get(slug=slug)
        before = _db_counts(event)

        # The event now exists, so the second POST is the existing-event
        # path (requires being THIS event's organizer, which the importer
        # granted) rather than the bootstrap path.
        second = _import_fixtures(organizer, slug)
        assert second.status_code == 200
        assert second.json()["imported"]["projects"] == FIXTURE_PROJECT_ROWS
        assert _db_counts(event) == before


class TestRoundTrip:
    """The acceptance property: export -> import into a fresh slug ->
    export is BYTE-identical."""

    def test_export_import_export_is_byte_identical(self, sample_event, auth_client):
        organizer = auth_client["organizer"]
        source = "rt-source"
        assert _import_fixtures(organizer, source).status_code == 200

        bytes_a = _export_bytes(organizer, source)
        assert json.loads(bytes_a)["event"]["id"] == FIXTURE_EVENT_ID

        dest = "rt-dest"
        resp = organizer.post(_import_path(dest), json.loads(bytes_a), content_type="application/json")
        assert resp.status_code == 200

        bytes_b = _export_bytes(organizer, dest)

        # The property itself: raw response bytes, no normalization.
        assert bytes_a == bytes_b
        # Canonical JSON as a second witness (catches accidental
        # whitespace-only drift the raw comparison would already have
        # flagged).
        canonical_a = json.dumps(json.loads(bytes_a), sort_keys=True)
        canonical_b = json.dumps(json.loads(bytes_b), sort_keys=True)
        assert canonical_a == canonical_b

    def test_reimporting_the_export_is_stable(self, sample_event, auth_client):
        # Import the export back INTO THE SAME event (the idempotence
        # path — the importer wipes and rebuilds): the export must not
        # change by a single byte, even though the demo participant is
        # re-seeded into a different first-team this time around.
        organizer = auth_client["organizer"]
        slug = "rt-stable"
        assert _import_fixtures(organizer, slug).status_code == 200
        bytes_a = _export_bytes(organizer, slug)

        resp = organizer.post(_import_path(slug), json.loads(bytes_a), content_type="application/json")
        assert resp.status_code == 200
        assert _export_bytes(organizer, slug) == bytes_a

    def test_round_trip_preserves_counts(self, sample_event, auth_client):
        organizer = auth_client["organizer"]
        source = "rt-counts-a"
        assert _import_fixtures(organizer, source).status_code == 200
        bytes_a = _export_bytes(organizer, source)

        dest = "rt-counts-b"
        assert organizer.post(_import_path(dest), json.loads(bytes_a), content_type="application/json").status_code == 200

        assert _db_counts(Event.objects.get(slug=source)) == _db_counts(Event.objects.get(slug=dest))
        # In particular the collapsed fixtures shape survives intact...
        assert len(json.loads(bytes_a)["scores"]) == EXPECTED_ASSIGNMENTS
        assert len(json.loads(_export_bytes(organizer, dest))["projects"]) == EXPECTED_SUBMISSIONS
