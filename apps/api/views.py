"""Webhook + OpenAPI views (T4 surface)."""
import secrets
from functools import lru_cache
from pathlib import Path

import yaml
from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event, Membership

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
            or Membership.objects.filter(
                user=request.user, role="organizer"
            ).exists()
        ):
            return Response(
                {"error": {"code": "forbidden", "message": "Not an organizer."}},
                status=403,
            )
        events = Event.objects.filter(
            memberships__user=request.user,
            memberships__role="organizer",
        )
        hooks = Webhook.objects.filter(event__in=events, is_active=True)
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
