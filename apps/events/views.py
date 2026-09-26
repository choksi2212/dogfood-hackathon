from decimal import Decimal

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, Membership, Rubric, RubricCriterion, Track
from .permissions import IsInEvent, IsOrganizer
from .serializers import (
    EventSerializer,
    MembershipSerializer,
    PrizeSerializer,
    RubricSerializer,
    TrackSerializer,
)


class EventCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(created_by=request.user)
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


class EventDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EventSerializer
    lookup_field = "slug"
    queryset = Event.objects.all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsInEvent()]
        return [IsAuthenticated(), IsOrganizer()]


class TrackCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        serializer = TrackSerializer(data={**request.data, "event": event.id})
        serializer.is_valid(raise_exception=True)
        track = serializer.save(event=event)
        return Response(TrackSerializer(track).data, status=status.HTTP_201_CREATED)


class RubricCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

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

        Rubric.objects.filter(event=event).delete()
        rubric = Rubric.objects.create(event=event, name=request.data.get("name", "Default"))
        for c in criteria_data:
            RubricCriterion.objects.create(rubric=rubric, **c)

        return Response(RubricSerializer(rubric).data, status=status.HTTP_201_CREATED)


class MembershipListView(generics.ListAPIView):
    """Organizer view of who is in this event."""

    serializer_class = MembershipSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsOrganizer()]

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        return Membership.objects.filter(event__slug=slug).select_related("user", "event")
