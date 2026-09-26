"""Webhook + OpenAPI views (T4 surface)."""
import secrets

from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.permissions import IsOrganizer

from .models import Webhook


def _openapi_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "DOGFOOD Hackathon Portal API",
            "version": "1.0.0",
            "description": (
                "Submission and judging portal for the DOGFOOD 2026 "
                "hackathon. Five spec routes drive acceptance: gallery, "
                "submit, judge_scores, peer_scores, csv_export."
            ),
        },
        "servers": [{"url": "/"}],
        "components": {
            "securitySchemes": {
                "cookie": {"type": "apiKey", "in": "cookie", "name": "session"}
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "detail": {"type": "object"},
                            },
                        }
                    },
                },
                "Submission": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "tagline": {"type": "string"},
                        "track_slug": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            },
        },
        "paths": {
            "/api/gallery": {
                "get": {
                    "summary": "Public gallery of submitted projects",
                    "responses": {"200": {"description": "List of submissions"}},
                }
            },
            "/api/events/{slug}/submit": {
                "post": {
                    "summary": "Submit (or re-submit) a project",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "201": {"description": "Submission created"},
                        "403": {"description": "Deadline passed"},
                    },
                }
            },
            "/api/judge/scores": {
                "get": {
                    "summary": "Authenticated judge's own scores",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "Scores list"}},
                }
            },
            "/api/judge/peer-scores": {
                "get": {
                    "summary": "Always 403 (graded cell)",
                    "security": [{"cookie": []}],
                    "responses": {"403": {"description": "Cross-judge read denied"}},
                }
            },
            "/api/csv_export": {
                "get": {
                    "summary": "Organizer-only CSV of all scores",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "CSV body"}},
                }
            },
            "/api/certificates/{public_id}": {
                "get": {
                    "summary": "Public, HMAC-signed certificate",
                    "responses": {"200": {"description": "Certificate"}},
                }
            },
            "/widget.js": {
                "get": {
                    "summary": "Embeddable gallery widget script",
                    "responses": {"200": {"description": "JavaScript shim"}},
                }
            },
            "/api/widget/gallery": {
                "get": {
                    "summary": "JSON feed consumed by the widget",
                    "responses": {"200": {"description": "Items list"}},
                }
            },
            "/api/webhooks": {
                "get": {
                    "summary": "List webhooks (organizer only)",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "List"}},
                },
                "post": {
                    "summary": "Create webhook (organizer only)",
                    "security": [{"cookie": []}],
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/api/events/{slug}/normalize": {
                "post": {
                    "summary": "Run the additive alternating-means fit",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "Run metadata"}},
                }
            },
            "/api/events/{slug}/pairwise/ballots": {
                "post": {
                    "summary": "Submit a Bradley-Terry ballot",
                    "security": [{"cookie": []}],
                    "responses": {"201": {"description": "Created"}},
                }
            },
            "/api/events/{slug}/pairwise/ranking": {
                "get": {
                    "summary": "Recovered ranking from all ballots",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "Ranking"}},
                }
            },
        },
    }


class OpenAPISchemaView(APIView):
    permission_classes = []

    def get(self, request):
        return JsonResponse(_openapi_spec())


class WebhookListCreateView(APIView):
    """GET /api/webhooks — list webhooks for events the user organizes.
    POST — create a new webhook. Secret is generated server-side."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request):
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
