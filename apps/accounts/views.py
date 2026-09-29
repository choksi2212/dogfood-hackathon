from django.conf import settings
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Session, User
from .serializers import UserSerializer


def _set_session_cookie(response, token):
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
        max_age=14 * 24 * 60 * 60,
    )


def _client_meta(request):
    return (
        request.META.get("REMOTE_ADDR"),
        request.headers.get("User-Agent", "")[:255],
    )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate required fields up-front so a missing/invalid payload
        # is rejected with 422 *before* a User row gets created.
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""

        field_errors: dict[str, str] = {}
        if not email:
            field_errors["email"] = "Email is required."
        if not password:
            field_errors["password"] = "Password is required."
        elif len(password) < 8:
            field_errors["password"] = "Password must be at least 8 characters."

        if field_errors:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "Invalid registration payload.",
                        "fields": field_errors,
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.set_password(password)
        user.save()
        ip, ua = _client_meta(request)
        _, token = Session.create(user, label="", ip=ip, user_agent=ua)
        response = Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        _set_session_cookie(response, token)
        return response


class LoginView(APIView):
    """Mint a new session for the user.

    Note: we do NOT delete prior sessions here. Multiple logins (e.g.
    laptop + phone) coexist — the same user can have N active
    sessions at once. Old sessions stay valid until they expire or
    the user explicitly logs one out via ``LogoutView``. Deleting
    prior sessions on every login would race when two concurrent
    logins hit at the same time, and would also break the legitimate
    multi-device case.
    """

    permission_classes = [AllowAny]
    # The API-wide parser default is JSON-only (see REST_FRAMEWORK in
    # config/settings.py) so junk content types fail fast with 415.
    # Login is the one endpoint that standard form posts genuinely hit —
    # curl -d, fetch with URLSearchParams, an HTML form fallback — so it
    # opts in to FormParser alongside JSON (issue #19). JSON stays the
    # documented primary format; the opt-in is deliberately local to
    # this view, not global.
    parser_classes = [JSONParser, FormParser]

    def post(self, request):
        email = (request.data.get("email") or "").lower()
        password = request.data.get("password") or ""

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"error": {"code": "not_authenticated", "message": "Invalid credentials."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"error": {"code": "not_authenticated", "message": "Invalid credentials."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip, ua = _client_meta(request)
        _, token = Session.create(user, label="login", ip=ip, user_agent=ua)

        response = Response(UserSerializer(user).data)
        _set_session_cookie(response, token)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session = getattr(request, "session_obj", None)
        if session is not None:
            session.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie("session")
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
