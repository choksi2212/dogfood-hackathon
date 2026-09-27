"""Audit log view.

Routes (under /api/):

  GET /api/events/<slug>/audit-log   organizer-only, most recent events

AuditEvent rows are written by apps.audit.helpers.log() from across
the codebase (login, vote cast/retract, score save/submit, assignment
run, etc.) but had no read surface until now — the PRD calls for the
audit trail to be "human-readable" and organizer-visible, which needs
an endpoint before it needs a screen.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.permissions import IsOrganizer

from .models import AuditEvent


class AuditLogView(APIView):
    """GET /api/events/<slug>/audit-log?limit=<n> — most recent audit
    events for this event, newest first. `limit` defaults to 100,
    capped at 500 to keep the response bounded."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request, slug):
        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Event {slug!r} not found.",
                    }
                },
                status=404,
            )

        try:
            limit = min(int(request.query_params.get("limit", 100)), 500)
        except ValueError:
            limit = 100

        entries = (
            AuditEvent.objects.filter(event=event)
            .select_related("actor")
            .order_by("-created_at")[:limit]
        )

        return Response(
            {
                "event_slug": event.slug,
                "entries": [
                    {
                        "id": str(e.id),
                        "actor_email": e.actor.email if e.actor else None,
                        "action": e.action,
                        "target_type": e.target_type,
                        "target_id": str(e.target_id) if e.target_id else None,
                        "result": e.result,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in entries
                ],
            }
        )
