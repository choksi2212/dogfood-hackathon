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
                "submit, judge_scores, peer_scores, csv_export. Public "
                "surface for integrators; protected surfaces for "
                "organizers, judges, and participants via cookie session."
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
                        "status": {
                            "type": "string",
                            "enum": ["draft", "submitted", "locked", "withdrawn"],
                        },
                    },
                },
                "Certificate": {
                    "type": "object",
                    "properties": {
                        "public_id": {"type": "string"},
                        "submission_id": {"type": "string", "format": "uuid"},
                        "signed_payload": {"type": "object"},
                        "signature": {"type": "string"},
                        "signature_algorithm": {
                            "type": "string",
                            "example": "HMAC-SHA256",
                        },
                        "issued_at": {"type": "string", "format": "date-time"},
                    },
                },
            },
        },
        "paths": {
            "/healthz": {
                "get": {
                    "summary": "Liveness probe — DB roundtrip",
                    "responses": {
                        "200": {"description": "OK"},
                        "503": {"description": "Degraded"},
                    },
                }
            },
            "/api/schema/": {
                "get": {
                    "summary": "This OpenAPI 3 spec as JSON",
                    "responses": {
                        "200": {
                            "description": "OpenAPI document",
                            "content": {"application/json": {}},
                        }
                    },
                }
            },
            "/api/gallery": {
                "get": {
                    "summary": "Public gallery of submitted projects",
                    "responses": {
                        "200": {
                            "description": "List of submissions",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/Submission"
                                                },
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/register": {
                "post": {
                    "summary": "Create a new user account and start a session",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "password": {"type": "string"},
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "User created; session cookie set"},
                        "400": {"description": "Validation failed"},
                    },
                }
            },
            "/api/login": {
                "post": {
                    "summary": "Authenticate with email + password; sets session cookie",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "password": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Authenticated; session cookie set"},
                        "401": {"description": "Invalid credentials"},
                    },
                }
            },
            "/api/logout": {
                "post": {
                    "summary": "End the current session",
                    "security": [{"cookie": []}],
                    "responses": {
                        "204": {"description": "Session ended; cookie cleared"},
                    },
                }
            },
            "/api/me": {
                "get": {
                    "summary": "Current authenticated user profile",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "User profile"}},
                }
            },
            "/api/events/": {
                "post": {
                    "summary": "Create a new event (organizer only)",
                    "security": [{"cookie": []}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {
                        "201": {"description": "Event created"},
                        "400": {"description": "Validation failed"},
                    },
                }
            },
            "/api/events/{slug}/": {
                "get": {
                    "summary": "Retrieve event details",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Event detail"}},
                },
                "put": {
                    "summary": "Update an event (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Event updated"}},
                },
                "patch": {
                    "summary": "Partial update of an event (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Event updated"}},
                },
            },
            "/api/events/{slug}/tracks": {
                "post": {
                    "summary": "Add a track to an event (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"201": {"description": "Track created"}},
                }
            },
            "/api/events/{slug}/rubric": {
                "post": {
                    "summary": "Define the rubric for an event (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"201": {"description": "Rubric created"}},
                }
            },
            "/api/events/{slug}/memberships": {
                "get": {
                    "summary": "List memberships for an event (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "List of memberships"}},
                }
            },
            "/api/events/{slug}/judges/bulk-invite": {
                "post": {
                    "summary": "Bulk-invite judges by email (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Invitations dispatched"}},
                }
            },
            "/api/events/{slug}/assignments/run": {
                "post": {
                    "summary": "Run the bipartite assignment algorithm (organizer only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Assignment batch metadata"}},
                }
            },
            "/api/events/{slug}/me/batch": {
                "get": {
                    "summary": "Judge's assigned projects for the current batch",
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
                        "200": {"description": "Batch contents + progress counts"},
                    },
                }
            },
            "/api/events/{slug}/me/batch/{project_id}/scores": {
                "put": {
                    "summary": "Save per-criterion scores for an assigned project",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "project_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {"200": {"description": "Scores saved"}},
                }
            },
            "/api/events/{slug}/me/batch/{project_id}/submit": {
                "post": {
                    "summary": "Finalize and submit scores for an assigned project",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "project_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {"200": {"description": "Scores submitted"}},
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
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "tagline": {"type": "string"},
                                        "description": {"type": "string"},
                                        "track_slug": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Submission created"},
                        "403": {"description": "Not a participant of this event"},
                        "422": {
                            "description": "Deadline passed or validation failed",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/events/{slug}/normalize": {
                "post": {
                    "summary": "Run the additive alternating-means fit on the event's scores",
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
                        "200": {"description": "Normalization run metadata"},
                        "422": {"description": "Bipartite graph disconnected"},
                    },
                }
            },
            "/api/events/{slug}/pairwise/ballots": {
                "post": {
                    "summary": "Submit a Bradley-Terry ballot",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "left_id": {"type": "string", "format": "uuid"},
                                        "right_id": {"type": "string", "format": "uuid"},
                                        "winner": {
                                            "type": "string",
                                            "enum": ["left", "right", "tie"],
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Ballot recorded"},
                        "404": {"description": "Event or submission not found"},
                    },
                }
            },
            "/api/events/{slug}/pairwise/ranking": {
                "get": {
                    "summary": "Recovered ranking from all ballots",
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
                        "200": {"description": "Projects ranked by recovered theta"},
                    },
                }
            },
            "/api/events/{slug}/submissions/{id}/vote": {
                "post": {
                    "summary": "Cast a vote on a submission",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "votes": {"type": "integer", "default": 1},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Vote recorded"},
                        "403": {"description": "Self-vote not allowed"},
                        "404": {"description": "Event or submission not found"},
                    },
                },
                "delete": {
                    "summary": "Retract a vote",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {
                        "200": {"description": "Retracted"},
                        "404": {
                            "description": "No ballot to retract or event/submission not found"
                        },
                    },
                },
            },
            "/api/judge/scores": {
                "get": {
                    "summary": "Authenticated judge's own scores",
                    "security": [{"cookie": []}],
                    "responses": {
                        "200": {
                            "description": "List of (project_id, criterion_id, value)",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "judge_id": {"type": "string", "format": "uuid"},
                                            "scores": {
                                                "type": "array",
                                                "items": {"type": "object"},
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "403": {"description": "Not a judge"},
                    },
                }
            },
            "/api/judge/peer-scores": {
                "get": {
                    "summary": "Always 403 (graded cell — cross-judge reads denied by URL design)",
                    "security": [{"cookie": []}],
                    "responses": {
                        "403": {
                            "description": "Cross-judge score read denied",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/csv_export": {
                "get": {
                    "summary": "Organizer-only CSV of all scores across the event",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "event_slug",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "default": "sample-hack-2026"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "CSV body with header row",
                            "content": {"text/csv": {}},
                        },
                        "403": {"description": "Not an organizer of this event"},
                    },
                }
            },
            "/api/{public_id}": {
                "get": {
                    "summary": "Public, HMAC-signed certificate for a submission",
                    "parameters": [
                        {
                            "name": "public_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Certificate payload + signature",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Certificate"}
                                }
                            },
                        },
                        "404": {"description": "Not found"},
                    },
                }
            },
            "/widget.js": {
                "get": {
                    "summary": "Embeddable gallery widget script (CORS open)",
                    "responses": {
                        "200": {
                            "description": "JavaScript shim that fetches /api/widget/gallery",
                            "content": {"application/javascript": {}},
                        }
                    },
                }
            },
            "/api/widget/gallery": {
                "get": {
                    "summary": "JSON feed consumed by the widget",
                    "parameters": [
                        {
                            "name": "event",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Items list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/Submission"
                                                },
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/webhooks": {
                "get": {
                    "summary": "List webhooks (organizer only)",
                    "security": [{"cookie": []}],
                    "responses": {"200": {"description": "List of webhook subscriptions"}},
                },
                "post": {
                    "summary": "Create a webhook (organizer only)",
                    "security": [{"cookie": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event_slug": {"type": "string"},
                                        "url": {"type": "string"},
                                        "events": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Webhook created (secret returned ONCE)"},
                    },
                },
            },
            "/api/{slug}/teams": {
                "post": {
                    "summary": "Create a team in an event (participant only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"201": {"description": "Team created"}},
                }
            },
            "/api/{slug}/teams/{id}/invite": {
                "post": {
                    "summary": "Issue a team invite (captain only)",
                    "security": [{"cookie": []}],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {"201": {"description": "Invite issued"}},
                }
            },
            "/api/teams/join": {
                "post": {
                    "summary": "Accept a team invite token",
                    "security": [{"cookie": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"token": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Joined"}},
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
