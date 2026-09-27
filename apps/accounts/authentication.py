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
    then decide whether to allow."""

    def authenticate(self, request):
        user = (
            getattr(request._request, "user", None) if hasattr(request, "_request") else getattr(request, "user", None)
        )
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Session"
