"""Organizer-facing delivery log — "did my webhook fire?"."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.models import Webhook
from apps.events.models import Membership


class WebhookDeliveryListView(APIView):
    """GET /api/webhooks/<webhook_id>/deliveries — organizer only.

    Role isolation: the webhook is resolved together with its event and
    the caller must organize that event (or be an admin). Non-organizers
    get 403 even for ids that do not exist — no existence leak.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, webhook_id):
        try:
            hook = Webhook.objects.select_related("event").get(id=webhook_id)
        except Webhook.DoesNotExist:
            return Response(
                {"error": {"code": "forbidden", "message": "Only organizers can read delivery logs."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_admin = getattr(request.user, "is_admin_role", False)
        if (
            not is_admin
            and not Membership.objects.filter(user=request.user, event=hook.event, role="organizer").exists()
        ):
            return Response(
                {"error": {"code": "forbidden", "message": "Only organizers can read delivery logs."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        deliveries = hook.deliveries.all()[:200]
        return Response(
            {
                "webhook": {"id": str(hook.id), "url": hook.url, "events": hook.events, "is_active": hook.is_active},
                "deliveries": [
                    {
                        "id": str(d.id),
                        "payload_type": d.payload_type,
                        "status": d.status,
                        "response_status": d.response_status,
                        "attempts": d.attempts,
                        "last_error": d.last_error,
                        "created_at": d.created_at.isoformat(),
                        "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
                    }
                    for d in deliveries
                ],
            }
        )
