from decimal import Decimal

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, Membership, Rubric, RubricCriterion
from .permissions import IsInEvent, IsOrganizer, IsOrganizerAnywhere
from .serializers import (
    EventSerializer,
    MembershipSerializer,
    RubricSerializer,
    TrackSerializer,
)
from apps.judging.models import Score


class EventCreateView(APIView):
    """POST /api/events/ (issue #46).

    ``IsOrganizerAnywhere`` (not per-event ``IsOrganizer``) — the URL
    has no slug to resolve. Authenticated admins and users who already
    organize any event may create a new one; the creator is granted an
    organizer Membership on the new event so they can immediately
    manage it (tracks, rubric, memberships) like any other organizer.
    """

    permission_classes = [IsAuthenticated, IsOrganizerAnywhere]

    def post(self, request):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(created_by=request.user)
        Membership.objects.get_or_create(
            user=request.user,
            event=event,
            defaults={"role": "organizer", "created_by": request.user},
        )
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


class EventDetailView(generics.RetrieveUpdateAPIView):
    """GET / PUT on a single event.

    GET is organizer-only — the full payload includes the rubric
    (criteria names + weights + min/max), prize structure, judging
    window, voting mode, and pairwise toggle. None of that has any
    audience outside the organizer:

      * Rubric weights and prize values should not influence judging
        behaviour and never need to be public.
      * Judges only need criterion *names* to label their sliders — they
        fetch that from ``GET /api/events/<slug>/rubric`` (judges see
        the rubric they score against; nobody sees other organizers'
        prize structures).
      * Participants see the public event detail in the gallery UI
        (name, description, tracks, deadlines, state) — that lives in
        a different serializer on the public surface, not here.

    PUT stays organizer-only.
    """

    serializer_class = EventSerializer
    lookup_field = "slug"
    queryset = Event.objects.all()

    def get_permissions(self):
        return [IsAuthenticated(), IsOrganizer()]


class RubricView(APIView):
    """GET / POST /api/events/<slug>/rubric.

    GET — any member of the event reads the rubric they will be judged
    against. Visible to judges (to label sliders), organizers (to
    manage criteria), and participants (to know what to optimize for
    on the public submission surface).

    POST — organizer-only — replaces the rubric wholesale. Weights must
    sum to 1.0 (with a small epsilon for floating point); existing rows
    are deleted before the new set is inserted (no soft-delete history).
    Each criterion must carry a positive weight (JUDGING.md §8.4).

    If any score has been recorded against the current rubric, the
    replace is REFUSED with 409 — deleting a RubricCriterion cascades
    every Score row that references it (issue #98), which silently
    wipes judging data while the progress dashboard keeps claiming the
    reviews are in. Re-linking by criterion name is unsafe (weights
    changed meaning); the honest contract is "rubric locked while
    scores exist".
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsInEvent()]
        return [IsAuthenticated(), IsOrganizer()]

    def get(self, request, slug):
        try:
            event = Event.objects.select_related("rubric").get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Event {slug!r} not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        rubric = getattr(event, "rubric", None)
        if rubric is None:
            return Response({"id": None, "name": None, "criteria": []})
        return Response(RubricSerializer(rubric).data)

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        criteria_data = request.data.get("criteria", [])

        total = sum((Decimal(str(c.get("weight", 0))) for c in criteria_data), Decimal("0"))
        if abs(total - Decimal("1.000")) > Decimal("0.001"):
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": f"Weights sum to {total}, not 1.0.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Negative / zero weights must not pass (JUDGING.md §8.4: the
        # portal enforces positive weights summing to 1). Validated
        # BEFORE any delete so a bad payload can never destroy the
        # existing rubric. RubricCriterion.clean() can't be used here —
        # it sums only *saved* siblings, so the first criterion of a
        # fresh rubric would always fail the sum check.
        for c in criteria_data:
            weight = Decimal(str(c.get("weight", 0)))
            if weight <= 0:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": f"Criterion weight must be positive (got {weight}).",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        # Refuse to destroy scores: the FK cascade would delete every
        # Score row wired to the old criteria (issue #98).
        if Score.objects.filter(assignment__batch__event=event).exists():
            return Response(
                {
                    "error": {
                        "code": "rubric_locked",
                        "message": (
                            "Scores exist against this event's rubric; replacing "
                            "it would cascade-delete every score. Clear scores "
                            "first or create a new event."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        Rubric.objects.filter(event=event).delete()
        rubric = Rubric.objects.create(event=event, name=request.data.get("name", "Default"))
        for c in criteria_data:
            RubricCriterion.objects.create(rubric=rubric, **c)

        return Response(RubricSerializer(rubric).data, status=status.HTTP_201_CREATED)


class TrackCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        serializer = TrackSerializer(data={**request.data, "event": event.id})
        serializer.is_valid(raise_exception=True)
        track = serializer.save(event=event)
        return Response(TrackSerializer(track).data, status=status.HTTP_201_CREATED)


class MembershipListView(generics.ListAPIView):
    """Organizer view of who is in this event."""

    serializer_class = MembershipSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsOrganizer()]

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        return Membership.objects.filter(event__slug=slug).select_related("user", "event")
