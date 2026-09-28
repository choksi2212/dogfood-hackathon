"""Audit helper. Views call log() after a successful (or denied) action.

The actual `request` object is the natural place to derive the actor, event,
and IP from; we read off it lazily so that views which don't have a request
(management commands, signals) can still pass a target.
"""

from .models import AuditEvent


def log(actor, action, target=None, payload=None, request=None, result="success"):
    event = _event_from_request(request) or (_event_from_target(target) if target else None)
    AuditEvent.objects.create(
        event=event,
        actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=type(target).__name__ if target else "",
        target_id=getattr(target, "id", None),
        payload=payload or {},
        ip=_ip_from_request(request),
        user_agent=_ua_from_request(request),
        result=result,
    )
    # T4: forward interesting actions to any subscribed webhooks.
    # Forwarding is best-effort and fire-and-forget — see
    # apps/api/delivery.py. We only forward successful actions
    # (denials aren't usually what an organizer wants to react to)
    # and only when we can resolve an event slug (so the webhook
    # lookup has something to key off).
    if event is not None and result == "success":
        from apps.api.delivery import dispatch_event

        dispatch_event(
            event.slug,
            action,
            {
                "actor": (
                    getattr(actor, "email", None)
                    if actor and getattr(actor, "is_authenticated", False)
                    else None
                ),
                "target_type": type(target).__name__ if target else "",
                "target_id": str(getattr(target, "id", "")) if target else "",
                "payload": payload or {},
            },
        )


def _event_from_request(request):
    if not request:
        return None
    slug = None
    if hasattr(request, "resolver_match") and request.resolver_match:
        slug = request.resolver_match.kwargs.get("slug")
    if slug:
        from apps.events.models import Event

        try:
            return Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return None
    return None


def _event_from_target(target):
    if hasattr(target, "event"):
        return target.event
    return None


def _ip_from_request(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _ua_from_request(request):
    if not request:
        return ""
    return request.headers.get("User-Agent", "")[:255]
