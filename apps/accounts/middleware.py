"""Session middleware. Resolves the `session` cookie to a user via the
hash-stored Session row. Sliding expiry: each authenticated request
extends the session lifetime by 14 days.
"""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from .models import Session


class SessionMiddleware:
    """Resolves the session cookie to a user and stamps request.user /
    request.session_obj. Should run BEFORE AuthenticationMiddleware so
    DRF sees the populated user."""

    SLIDING_TTL_DAYS = 14

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = AnonymousUser()
        request.session_obj = None

        token = request.COOKIES.get("session")
        if token:
            session = Session.lookup(token)
            if session is not None and session.expires_at > timezone.now():
                request.user = session.user
                request.session_obj = session
                session.last_seen_at = timezone.now()
                session.expires_at = timezone.now() + timedelta(days=self.SLIDING_TTL_DAYS)
                session.save(update_fields=["last_seen_at", "expires_at"])
            elif session is not None:
                # expired — purge it
                session.delete()

        return self.get_response(request)


class AuditMiddleware:
    """Append 401/403 responses on /api/ to the audit log."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in (401, 403) and request.path.startswith("/api/"):
            from django.contrib.auth.models import AnonymousUser

            user = getattr(request, "user", None) or AnonymousUser()
            from apps.audit.models import AuditEvent

            # ``action`` is a CharField(max_length=100). Truncate the
            # full method+path so very long routes (e.g. ``PATCH
            # /api/events/.../submissions/<id>/comments/<comment_id>``)
            # still fit. The full path is recoverable from the
            # request logs upstream; here we only need a label.
            action_label = f"{request.method} {request.path}"[:95]

            AuditEvent.objects.create(
                actor_id=user.id if user.is_authenticated else None,
                action=action_label,
                target_type="endpoint",
                target_id=None,
                payload={},
                ip=self._get_ip(request),
                user_agent=request.headers.get("User-Agent", "")[:255],
                result="denied",
            )
        return response

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class RateLimitMiddleware:
    """Simple per-IP sliding-window rate limiter. Buckets are in-memory —
    process-local, so multi-worker deploys need a shared store; for the
    hackathon one worker is enough.
    """

    LIMITS = {
        "auth": (5, 15 * 60),
        "read": (60, 60),
        "write": (10, 60),
    }

    def __init__(self, get_response):
        from collections import defaultdict

        self.get_response = get_response
        self.buckets = defaultdict(dict)

    def __call__(self, request):
        from django.http import JsonResponse

        ip = self._get_ip(request)
        endpoint_class = self._classify(request)
        limit, window = self.LIMITS[endpoint_class]

        now = timezone.now().timestamp() if hasattr(timezone, "now") else __import__("time").time()
        bucket_key = f"{ip}:{endpoint_class}"
        bucket = self.buckets.setdefault(bucket_key, {"count": 0, "reset_at": now + window})

        if now >= bucket["reset_at"]:
            bucket["count"] = 0
            bucket["reset_at"] = now + window

        bucket["count"] += 1

        if bucket["count"] > limit:
            retry_after = int(bucket["reset_at"] - now)
            return JsonResponse(
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Slow down.",
                        "detail": {"retry_after": retry_after},
                    }
                },
                status=429,
                headers={"Retry-After": str(retry_after)},
            )

        return self.get_response(request)

    def _classify(self, request):
        if "/api/auth/" in request.path:
            return "auth"
        if request.method in ("POST", "PATCH", "DELETE", "PUT"):
            return "write"
        return "read"

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")
