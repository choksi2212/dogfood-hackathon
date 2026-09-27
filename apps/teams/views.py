from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.permissions import IsParticipant

from .models import Team, TeamInvite, TeamMember


class TeamCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)

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

        team = Team.objects.create(
            event=event,
            name=request.data.get("name"),
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
        team = Team.objects.get(id=id, event__slug=slug)

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
        invite_url = f"{request.scheme}://{request.get_host()}/teams/join?token={token}"
        return Response(
            {"invite_url": invite_url, "expires_at": invite.expires_at.isoformat()},
            status=status.HTTP_201_CREATED,
        )


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import TeamMember as TM

        token = request.data.get("token", "")
        from .models import _hash_token

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
        invite.consumed_at = timezone.now()
        invite.consumed_by = request.user
        invite.save()
        return Response({"id": str(team.id), "name": team.name})
