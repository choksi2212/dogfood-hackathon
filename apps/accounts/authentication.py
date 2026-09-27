"""Custom DRF authentication that piggybacks on the cookie-based session
middleware. DRF's Request wrapper stores `_user = None` until an
authentication class populates it; with no DEFAULT_AUTHENTICATION_CLASSES,
`request.user.is_authenticated` would explode on None. We read the user
that apps.accounts.middleware.SessionMiddleware already resolved.
"""

from rest_framework.authentication import BaseAuthentication


class CookieSessionAuthentication(BaseAuthentication):
    """Returns (user, None) if the session middleware already populated
    request.user. Otherwise returns None — the view's permission_classes
    then decide whether to allow.

    Tried making this return (AnonymousUser(), None) instead of None for
    the anonymous case, to fix a bare `request.user.is_authenticated`
    crash in one view (apps/voting/views.py). Reverted: several
    permission classes (e.g. apps.events.permissions.IsInEvent) pass
    `request.user` straight into `Membership.objects.filter(user=...)`
    assuming it's None for anonymous (valid as IS NULL) — AnonymousUser
    isn't a real model instance and breaks that FK lookup instead. Fix
    the specific unguarded call site, not the shared authenticator."""

    def authenticate(self, request):
        user = (
            getattr(request._request, "user", None) if hasattr(request, "_request") else getattr(request, "user", None)
        )
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Session"
