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
    # T4 webhook dispatch happens per-view (see apps/webhooks/delivery.py),
    # not from audit_log — each view knows which payload_type it wants to
    # fire and the event is already in scope. Audit events are the
    # immutable paper trail; webhook deliveries are the side effect.


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
