"""Submission views.

T1 (G2):
  GET  /api/gallery                       → public list of submitted projects
  POST /api/events/<slug>/submit          → participant, deadline-gated

T3 surfaces (later):
  POST /api/events/<slug>/submissions/<id>/review-comment (T3 comments)
  POST /api/events/<slug>/submissions/<id>/vote (T3 voting)
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.decorators import deadline_gated
from apps.events.models import Event, Track
from apps.events.permissions import IsParticipant
from apps.teams.models import TeamMember

from .models import Submission
from .serializers import SubmissionSerializer, SubmissionSummarySerializer


class GalleryView(APIView):
    """Public gallery. Used by acceptance checks 1 and 2.

    Returns submitted-only submissions in track order. The check expects
    at least one known fixture title — we seed fixtures with a known
    title so this is always true after `manage.py seed_fixtures`.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # public — no session lookup needed

    def get(self, request):
        qs = (
            Submission.objects.filter(status="submitted")
            .select_related("team", "track")
            .order_by("track__order", "name")
        )

        track = request.query_params.get("track")
        if track:
            qs = qs.filter(track__slug__in=track.split(","))

        sort = request.query_params.get("sort", "track")
        if sort == "alpha":
            qs = qs.order_by("name")
        elif sort == "newest":
            qs = qs.order_by("-submitted_at")

        try:
            page = int(request.query_params.get("page", "1"))
        except ValueError:
            page = 1
        page_size = 24
        items = list(qs[(page - 1) * page_size : page * page_size])
        total = qs.count()

        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": SubmissionSummarySerializer(items, many=True).data,
            }
        )


class SubmitView(APIView):
    """The spec route. POST as participant, after deadline → 4xx.

    Body (JSON, optional):
      { "name": "...", "tagline": "...", "description": "...",
        "track_slug": "main", "team_id": "<uuid>" }
    Without a team_id, the server picks the participant's first team in
    this event.
    """

    permission_classes = [IsParticipant]

    @deadline_gated("submissions_close_at")
    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug)
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

        team = self._resolve_team(request, event)
        if isinstance(team, Response):
            return team

        track_slug = request.data.get("track_slug")
        if not track_slug:
            track = event.tracks.order_by("order").first()
            if track is None:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": "Event has no tracks; cannot submit.",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        else:
            try:
                track = Track.objects.get(event=event, slug=track_slug)
            except Track.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": f"Track {track_slug!r} not found.",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        name = (request.data.get("name") or "").strip()
        tagline = (request.data.get("tagline") or "").strip()[:140]
        if not name:
            name = f"{team.name} submission"

        submission, created = Submission.objects.get_or_create(
            team=team,
            defaults={
                "event": event,
                "track": track,
                "name": name,
                "tagline": tagline,
                "description": request.data.get("description", ""),
            },
        )
        if not created:
            submission.name = name
            submission.tagline = tagline
            submission.description = request.data.get("description", "")
            submission.track = track
            submission.save()

        if submission.status not in ("draft", "submitted"):
            return Response(
                {
                    "error": {
                        "code": "gone",
                        "message": f"Submission is {submission.status}; cannot re-submit.",
                    }
                },
                status=status.HTTP_410_GONE,
            )

        submission.status = "submitted"
        submission.submitted_at = timezone.now()
        submission.save()

        return Response(
            SubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )

    def _resolve_team(self, request, event):
        team_id = request.data.get("team_id")
        if team_id:
            from apps.teams.models import Team

            try:
                team = Team.objects.get(id=team_id, event=event)
            except Team.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"Team {team_id!r} not found in this event.",
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not TeamMember.objects.filter(team=team, user=request.user).exists():
                return Response(
                    {
                        "error": {
                            "code": "forbidden_role",
                            "message": "You are not a member of that team.",
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return team

        member = TeamMember.objects.filter(user=request.user, team__event=event).select_related("team").first()
        if member is None:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "You are not in a team for this event.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return member.team
