"""Webhook + OpenAPI views (T4 surface)."""

import secrets
from functools import lru_cache
from pathlib import Path

import yaml
from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event, Membership
from apps.events.permissions import IsOrganizer

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


class BulkImportView(APIView):
    """T4 spec: bulk import endpoint for organizers.

    POST /api/events/<slug>/bulk/import
        body: ``{"kind": "judges"|"teams"|"submissions",
                 "rows": [...]}``

    Each row is a dict matching the shape of the corresponding model.
    For ``judges``, each row is ``{email, name, role}`` and creates
    the User + Membership in one transaction. For ``teams``, each row
    is ``{name, captain_email, member_emails}`` and creates the
    Team, TeamMember rows, and (if missing) Users for any emails.
    For ``submissions``, each row is
    ``{team_name, track_slug, name, tagline, description, tech_tags,
       repo_url, live_url, demo_video_url, thumbnail_path}``.

    Organizer-only. Best-effort idempotent: re-imports are skipped
    when the row already exists (judge by email, team by name +
    event, submission by team + event).
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        from apps.audit.helpers import log as audit_log
        from apps.events.models import Event, Membership

        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": f"Event {slug!r} not found."}},
                status=404,
            )

        kind = request.data.get("kind")
        rows = request.data.get("rows", [])
        if kind not in ("judges", "teams", "submissions"):
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "kind must be one of: judges, teams, submissions.",
                    }
                },
                status=422,
            )
        if not isinstance(rows, list):
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "rows must be a list.",
                    }
                },
                status=422,
            )

        if kind == "judges":
            created = self._import_judges(event, rows, request.user)
        elif kind == "teams":
            created = self._import_teams(event, rows)
        else:
            created = self._import_submissions(event, rows)

        audit_log(
            request.user,
            "bulk.import",
            target=event,
            payload={"kind": kind, "created": created, "submitted": len(rows)},
            request=request,
        )
        return Response(
            {"kind": kind, "submitted": len(rows), "created": created},
            status=201,
        )

    def _import_judges(self, event, rows, organizer):
        from apps.accounts.models import User
        from apps.events.models import Membership

        created = 0
        for row in rows:
            email = (row.get("email") or "").strip().lower()
            if not email:
                continue
            name = (row.get("name") or "").strip()
            role = (row.get("role") or "judge").strip()
            if role not in ("judge", "organizer", "participant", "admin"):
                role = "judge"
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={"username": email, "name": name, "is_active": True},
            )
            if user_created:
                user.set_password("dogfood-dev-password")
                user.save()
            _, m_created = Membership.objects.get_or_create(
                user=user,
                event=event,
                defaults={"role": role, "created_by": organizer},
            )
            if user_created or m_created:
                created += 1
        return created

    def _import_teams(self, event, rows):
        from apps.accounts.models import User
        from apps.teams.models import Team, TeamMember

        created = 0
        for row in rows:
            name = (row.get("name") or "").strip()
            captain_email = (row.get("captain_email") or "").strip().lower()
            member_emails = row.get("member_emails") or []
            if not name or not captain_email:
                continue
            captain, _ = User.objects.get_or_create(
                email=captain_email,
                defaults={"username": captain_email, "is_active": True},
            )
            team, t_created = Team.objects.get_or_create(
                event=event,
                name=name,
                defaults={"created_by": captain},
            )
            if not t_created:
                continue  # idempotent skip
            TeamMember.objects.get_or_create(
                team=team,
                user=captain,
                defaults={"role_in_team": "captain"},
            )
            for member_email in member_emails:
                member_email = member_email.strip().lower()
                if not member_email or member_email == captain_email:
                    continue
                member, _ = User.objects.get_or_create(
                    email=member_email,
                    defaults={"username": member_email, "is_active": True},
                )
                TeamMember.objects.get_or_create(
                    team=team,
                    user=member,
                    defaults={"role_in_team": "member"},
                )
            created += 1
        return created

    def _import_submissions(self, event, rows):
        from apps.submissions.models import Submission

        created = 0
        for row in rows:
            team_name = (row.get("team_name") or "").strip()
            if not team_name:
                continue
            from apps.teams.models import Team

            try:
                team = Team.objects.get(event=event, name=team_name)
            except Team.DoesNotExist:
                continue
            track_slug = row.get("track_slug")
            try:
                track = event.tracks.get(slug=track_slug) if track_slug else event.tracks.first()
            except Exception:
                continue
            if track is None:
                continue
            defaults = {
                "event": event,
                "track": track,
                "name": (row.get("name") or f"{team_name} submission").strip()[:80],
                "tagline": (row.get("tagline") or "").strip()[:140],
                "description": row.get("description") or "",
                "thumbnail_path": row.get("thumbnail_path") or "",
                "demo_video_url": row.get("demo_video_url") or "",
                "repo_url": row.get("repo_url") or "",
                "live_url": row.get("live_url") or "",
                "tech_tags": row.get("tech_tags") or [],
                "status": row.get("status") or "draft",
            }
            _, created_flag = Submission.objects.get_or_create(
                team=team,
                defaults=defaults,
            )
            if created_flag:
                created += 1
        return created
