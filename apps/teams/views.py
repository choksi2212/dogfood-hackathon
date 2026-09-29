from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.models import Membership as EventMembership
from apps.events.permissions import IsParticipant

from .models import Team, TeamInvite, TeamMember


def _grant_participant_membership(user, event, created_by):
    """Issue #54: joining a team is the REST path that makes a user a
    participant of the team's event. Without this, register → join
    team → submit dead-ends at the submit permission (403)."""
    EventMembership.objects.get_or_create(
        user=user,
        event=event,
        defaults={"role": "participant", "created_by": created_by},
    )


def _clean_name(request):
    raw = request.data.get("name") if isinstance(request.data, dict) else None
    if not isinstance(raw, str):
        return None
    return raw.strip()[:60]


class TeamCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]

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

        if TeamMember.objects.filter(user=request.user, team__event=event).exists():
            return Response(
                {
                    "error": {
                        "code": "conflict",
                        "message": "You are already in a team for this event.",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        name = _clean_name(request)
        if not name:
            # Issue #53: was an IntegrityError 500 on the null name.
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "name is required.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        team = Team.objects.create(
            event=event,
            name=name,
            created_by=request.user,
        )
        TeamMember.objects.create(team=team, user=request.user, role_in_team="captain")
        return Response(
            {"id": str(team.id), "name": team.name},
            status=status.HTTP_201_CREATED,
        )


class InviteCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]

    def post(self, request, slug, id):
        try:
            team = Team.objects.get(id=id, event__slug=slug)
        except Team.DoesNotExist:
            # Issue #53: was a DoesNotExist 500 on unknown team ids.
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Team {id!r} not found in this event.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not TeamMember.objects.filter(team=team, user=request.user, role_in_team="captain").exists():
            return Response(
                {
                    "error": {
                        "code": "forbidden_role",
                        "message": "Only the captain can create invites.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if team.members.count() >= 4:
            return Response(
                {
                    "error": {
                        "code": "conflict",
                        "message": "Team is full (4 members).",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        invite, token = TeamInvite.create(team, request.user)
        # Issue #52: the URL pointed at GET /teams/join — a page that
        # doesn't exist (404). The real join surface is the
        # POST /api/teams/join API route, so the captain gets a
        # link that actually works end-to-end.
        invite_url = f"{request.scheme}://{request.get_host()}/api/teams/join?token={token}"
        return Response(
            {"invite_url": invite_url, "token": token, "expires_at": invite.expires_at.isoformat()},
            status=status.HTTP_201_CREATED,
        )


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import TeamMember as TM
        from .models import _hash_token

        # Issue #58: a non-dict body must be a clean 4xx, not a 500.
        if not isinstance(request.data, dict):
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "Body must be a JSON object with a 'token' field.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        raw_token = request.data.get("token", "")
        token = raw_token if isinstance(raw_token, str) else ""

        token_hash = _hash_token(token)

        try:
            invite = TeamInvite.objects.select_related("team__event").get(token_hash=token_hash)
        except TeamInvite.DoesNotExist:
            return Response(
                {"error": {"code": "gone", "message": "Invalid invite token."}},
                status=status.HTTP_410_GONE,
            )

        from django.utils import timezone

        if invite.consumed_at or invite.expires_at < timezone.now():
            return Response(
                {
                    "error": {
                        "code": "gone",
                        "message": "Invite expired or consumed.",
                    }
                },
                status=status.HTTP_410_GONE,
            )

        team = invite.team
        if team.members.count() >= 4:
            return Response(
                {"error": {"code": "conflict", "message": "Team is full."}},
                status=status.HTTP_409_CONFLICT,
            )

        if TM.objects.filter(user=request.user, team__event=team.event).exists():
            return Response({"id": str(team.id), "name": team.name})

        TM.objects.create(team=team, user=request.user, role_in_team="member")
        # Issue #54: the joiner becomes a participant of the event so
        # the register → join → submit lifecycle is complete.
        _grant_participant_membership(request.user, team.event, request.user)
        invite.consumed_at = timezone.now()
        invite.consumed_by = request.user
        invite.save()
        return Response({"id": str(team.id), "name": team.name})
