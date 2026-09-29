"""Webhook + OpenAPI + bulk import/export views (T4 surface)."""

import io
import json
import secrets
import tempfile
from functools import lru_cache
from pathlib import Path

import yaml
from django.core.exceptions import RequestDataTooBig
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.exceptions import ParseError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.helpers import log as audit_log
from apps.events.models import Event, Membership
from apps.events.permissions import IsOrganizer

from .exporter import build_export, chunked_export_json
from .models import Webhook

# Single source of truth for the OpenAPI document. The view loads
# openapi.yaml from the repo root on first request and caches it
# in-process; editing the YAML is the way to change the spec.
OPENAPI_YAML_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


@lru_cache(maxsize=1)
def _openapi_spec() -> dict:
    with OPENAPI_YAML_PATH.open() as fh:
        return yaml.safe_load(fh)


class OpenAPISchemaView(APIView):
    permission_classes = []

    def get(self, request):
        return JsonResponse(_openapi_spec())


class WebhookListCreateView(APIView):
    """GET /api/webhooks — list webhooks for events the user organizes.
    POST — create a new webhook. Secret is generated server-side."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # The URL doesn't carry an event slug, so the URL-pattern
        # ``IsOrganizer`` permission can't resolve an event — we do the
        # check inline: a non-organizer sees 403, an empty list is the
        # wrong signal (200 with []).
        if not (
            getattr(request.user, "is_admin_role", False)
            or Membership.objects.filter(user=request.user, role="organizer").exists()
        ):
            return Response(
                {"error": {"code": "forbidden", "message": "Not an organizer."}},
                status=403,
            )
        events = Event.objects.filter(
            memberships__user=request.user,
            memberships__role="organizer",
        )
        # ``select_related("event")`` collapses the per-row ``h.event.slug``
        # access into a single LEFT JOIN. Without it, N hooks trigger N
        # extra queries.
        hooks = Webhook.objects.filter(event__in=events, is_active=True).select_related("event")
        return Response(
            [
                {
                    "id": str(h.id),
                    "event": h.event.slug,
                    "url": h.url,
                    "events": h.events,
                    "is_active": h.is_active,
                    "created_at": h.created_at.isoformat(),
                }
                for h in hooks
            ]
        )

    def post(self, request):
        event_slug = request.data.get("event_slug")
        url = request.data.get("url")
        events = request.data.get("events", [])
        if not event_slug or not url:
            return Response(
                {"error": {"code": "validation_failed", "message": "event_slug and url required."}},
                status=422,
            )

        if not Membership.objects.filter(
            user=request.user, event__slug=event_slug, role="organizer"
        ).exists() and not getattr(request.user, "is_admin_role", False):
            return Response(
                {"error": {"code": "forbidden", "message": "Not an organizer of this event."}},
                status=403,
            )

        event = Event.objects.get(slug=event_slug)
        hook = Webhook.objects.create(
            event=event,
            url=url,
            secret=secrets.token_urlsafe(32),
            events=events,
            is_active=True,
        )
        return Response(
            {
                "id": str(hook.id),
                "event": event.slug,
                "url": hook.url,
                "secret": hook.secret,
                "events": hook.events,
            },
            status=201,
        )


# --- T4: bulk import/export -------------------------------------------------

# 5 MiB. The official fixtures.json is ~46 KB, so this is ~100x headroom
# while still bounding how much JSON a single request can make the
# importer parse and how big of a tempfile one request can write.
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _payload_too_large_response(actual_bytes):
    """The documented 413 for oversized import bodies (see openapi.yaml):
    never a parse error, never Django's generic 400."""
    return Response(
        {
            "error": {
                "code": "payload_too_large",
                "message": (
                    f"Body is {actual_bytes} bytes; the import limit is {MAX_IMPORT_BYTES} (5 MiB)."
                ),
            }
        },
        status=413,
    )

# Top-level sections import_fixtures dereferences unconditionally. The
# view validates exactly these and no more (deep per-row validation
# stays the importer's job) so a *truncated* body fails fast with a 422
# instead of a KeyError-500 from inside the management command.
_REQUIRED_FIXTURE_SECTIONS = ("event", "tracks", "judges", "teams", "projects")
_LIST_SECTIONS = ("tracks", "judges", "teams", "projects")
# The importer dereferences event["name"] and event["submissions_close"]
# verbatim, so a dict-shaped `event` without these strings would 500.
_REQUIRED_EVENT_FIELDS = ("name", "submissions_close")


class EventImportView(APIView):
    """POST /api/events/<slug>/import — bulk-import a fixtures.json-shaped
    body into the event, reusing the battle-tested importer
    (``import_fixtures``) instead of duplicating its logic. The importer
    is idempotent + atomic: re-importing the same body is safe, and a
    failed import leaves the event exactly as it was.

    Role check is INLINE, not ``IsOrganizer``: the importer must also be
    able to CREATE an event (bootstrap import — a fresh event slug), and
    nobody can hold a membership in an event that doesn't exist yet. So:

      * event exists  -> requester must be an organizer of THAT event
                         (or an admin);
      * event absent -> requester must organize at least one event
                         (or be an admin) — the bootstrap case.

    The body is written to a tempfile so the importer reads exactly what
    the organizer sent (its file-parsing path, byte for byte), then the
    temp directory is removed either way.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        if not self._authorized(request, slug):
            return Response(
                {"error": {"code": "forbidden", "message": "Only organizers can import."}},
                status=403,
            )

        # Size guard BEFORE parsing: an oversized body is rejected without
        # even JSON-decoding it. Content-Length is inspected first so a huge
        # body is refused without reading it at all; RequestDataTooBig
        # (Django's own DATA_UPLOAD_MAX_MEMORY_SIZE guard, configured above
        # the import limit in settings) is translated into the documented
        # 413 instead of Django's generic 400.
        try:
            content_length = int(
                request.META.get("CONTENT_LENGTH")
                or request.META.get("HTTP_CONTENT_LENGTH")
                or 0
            )
        except (TypeError, ValueError):
            content_length = 0
        if content_length > MAX_IMPORT_BYTES:
            return _payload_too_large_response(content_length)
        try:
            raw = request.body
        except RequestDataTooBig:
            # A client that understates (or omits) Content-Length still gets
            # 413 — never a parser crash, never a generic 400.
            return _payload_too_large_response(MAX_IMPORT_BYTES + 1)
        if len(raw) > MAX_IMPORT_BYTES:
            return _payload_too_large_response(len(raw))

        try:
            data = request.data
        except ParseError:
            # Syntactically broken JSON — e.g. a body truncated mid-string.
            # The endpoint's documented contract is "malformed body => 422,
            # never a 500" (see openapi.yaml), so the parser error is
            # reported as a validation failure instead of DRF's default 400
            # (a status this endpoint does not declare).
            return self._validation_failed(
                "Body must be valid JSON shaped like fixtures.json "
                "(sections: event, tracks, judges, teams, projects, scores)."
            )
        if not isinstance(data, dict):
            return self._validation_failed(
                "Body must be a JSON object shaped like fixtures.json "
                "(sections: event, tracks, judges, teams, projects, scores)."
            )

        missing = [s for s in _REQUIRED_FIXTURE_SECTIONS if s not in data]
        if missing:
            return self._validation_failed(
                f"Truncated fixtures body — missing section(s): {', '.join(missing)}."
            )
        bad_types = [s for s in _LIST_SECTIONS if not isinstance(data[s], list)]
        if not isinstance(data["event"], dict):
            bad_types.append("event")
        if bad_types:
            return self._validation_failed(
                f"Section(s) with wrong type: {', '.join(sorted(set(bad_types)))} "
                "(event must be an object; tracks/judges/teams/projects must be lists)."
            )
        missing_event_fields = [
            f for f in _REQUIRED_EVENT_FIELDS if not isinstance(data["event"].get(f), str)
        ]
        if missing_event_fields:
            return self._validation_failed(
                f"event section is missing required string field(s): "
                f"{', '.join(missing_event_fields)}."
            )
        scores = data.get("scores", [])
        if not isinstance(scores, list):
            return self._validation_failed("scores, when present, must be a list.")

        with tempfile.TemporaryDirectory(prefix="hack-hamster-import-") as tmp_dir:
            # delete=False + TemporaryDirectory: call_command reopens the
            # file by path, so it must outlive the NamedTemporaryFile
            # context; the surrounding TemporaryDirectory removes
            # everything (file included) on the way out, on both the
            # success and the failure path.
            with tempfile.NamedTemporaryFile(
                "w",
                suffix=".json",
                encoding="utf-8",
                dir=tmp_dir,
                delete=False,
            ) as tmp:
                json.dump(data, tmp)
                tmp_path = tmp.name
            try:
                call_command(
                    "import_fixtures",
                    file=tmp_path,
                    event_slug=slug,
                    stdout=io.StringIO(),
                )
            except (CommandError, KeyError, TypeError, ValueError) as exc:
                # CommandError -> the importer's own validation. KeyError/
                # TypeError/ValueError -> a truncated row inside one of the
                # lists (e.g. a project without "team"). The importer is
                # atomic, so nothing partial was committed — 422, not 500.
                return self._validation_failed(f"Import failed: {exc}")

        audit_log(
            request.user,
            "bulk.import",
            Event.objects.filter(slug=slug).first(),
            payload=self._counts(data, scores),
            request=request,
        )
        return Response({"imported": self._counts(data, scores), "event": slug})

    @staticmethod
    def _authorized(request, slug) -> bool:
        is_admin = getattr(request.user, "is_admin_role", False)
        if is_admin:
            return True
        event = Event.objects.filter(slug=slug).first()
        if event is not None:
            return Membership.objects.filter(
                user=request.user, event=event, role="organizer"
            ).exists()
        # Bootstrap: the event doesn't exist yet — the import is what
        # creates it. Any organizer (of any event) may bootstrap.
        return Membership.objects.filter(user=request.user, role="organizer").exists()

    @staticmethod
    def _counts(data, scores) -> dict:
        return {
            "projects": len(data["projects"]),
            "judges": len(data["judges"]),
            "teams": len(data["teams"]),
            "scores": len(scores),
        }

    @staticmethod
    def _validation_failed(message: str):
        return Response(
            {"error": {"code": "validation_failed", "message": message}},
            status=422,
        )


class EventExportView(APIView):
    """GET /api/events/<slug>/export — organizer-only bulk export: streams
    the event as fixtures-shaped JSON, byte-for-byte re-importable by
    ``POST /api/events/<slug>/import`` (and ``import_fixtures``). See
    apps/api/exporter.py for the determinism rules and the documented
    round-trip caveats.

    ``[IsAuthenticated, IsOrganizer]`` — the shared permission pair; for a
    non-existent event non-admins get 403 at the permission layer (house
    behavior of organizer-gated endpoints), admins get the 404 below.
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request, slug):
        event = Event.objects.filter(slug=slug).first()
        if event is None:
            return Response(
                {"error": {"code": "not_found", "message": f"Event {slug!r} not found."}},
                status=404,
            )

        export = build_export(event)
        audit_log(
            request.user,
            "bulk.export",
            event,
            payload={
                "projects": len(export["projects"]),
                "judges": len(export["judges"]),
                "teams": len(export["teams"]),
                "scores": len(export["scores"]),
            },
            request=request,
        )
        response = StreamingHttpResponse(
            chunked_export_json(export), content_type="application/json"
        )
        response["Content-Disposition"] = f'attachment; filename="fixtures-{event.slug}.json"'
        return response
