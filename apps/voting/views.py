"""T3 (Community Voting) views.

Endpoints (under /api/):

  POST   /api/events/<slug>/submissions/<id>/vote   cast or update a ballot
  DELETE /api/events/<slug>/submissions/<id>/vote   retract a ballot

Both are deadline-gated: voting opens at ``submissions_close_at`` (i.e.
once the registration window has closed). The vote window is not
explicitly bounded here — the spec ties voting to the same window as
peer scoring. Anti-abuse is layered at the proxy / abuse-flag app.

Mode semantics (see ``Event.voting_mode``):

* ``simple``    — every cast is exactly 1 vote. ``votes`` is forced to 1
                  for storage consistency; the budget table is unused.
* ``quadratic`` — the voter may spend any ``n`` up to the per-ballot cap;
                  the cost is ``n**2`` credits out of a 100-credit event
                  budget for that voter.
"""
import hashlib

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.helpers import log as audit_log
from apps.events.decorators import deadline_gated
from apps.events.models import Event
from apps.submissions.models import Submission

from .models import Vote, VoteAudit, VoteBudget


QUADRATIC_BUDGET = 100
SIMPLE_VOTE_VALUE = 1
MAX_QUADRATIC_BALLOT = 10  # n <= 10 -> cost <= 100; matches the budget


def _voter_key(request, event) -> str:
    """Stable, opaque voter identifier.

    Authenticated users get ``user:<uuid>``. Anonymous voters get
    ``fp:<sha256(ip + user_agent)[:32]>`` — collision-prone in theory
    (shared NAT, library Wi-Fi) but cheap and well-bounded for the
    hackathon threat model.

    `request.user` may be ``None`` for unauthenticated DRF requests when
    the project default ``UNAUTHENTICATED_USER=None`` is in effect
    (the `VoteView` skips authentication entirely). Treat that the same
    as anonymous.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user:{user.id}"
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.headers.get("User-Agent", "")
    digest = hashlib.sha256(f"{ip}{ua}".encode()).hexdigest()[:32]
    return f"fp:{digest}"


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_agent(request) -> str:
    return request.headers.get("User-Agent", "")[:255]


class VoteView(APIView):
    """Cast, update, or retract a ballot for one project.

    POST semantics:

    * Body may include ``{"votes": <int>}``. In simple mode it is
      ignored (always stored as 1).
    * Retracted votes can be re-cast: the row's ``retracted_at`` is
      cleared and the credit cost is recharged.
    * Anonymous voters get a fingerprint key; authenticated voters get
      a user-keyed row (which lets a later login "claim" earlier
      ballots if we want to — out of scope for G5).

    DELETE semantics:

    * Sets ``retracted_at`` and refunds the quadratic credit cost.
    * Does NOT delete the row. The audit trail references ``vote.id``
      and that FK must remain valid.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []  # explicitly public — no session lookup

    @deadline_gated("submissions_close_at")
    def post(self, request, slug, id):
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

        try:
            project = Submission.objects.get(id=id, event=event)
        except Submission.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Submission {id!r} not found in {slug!r}.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Self-vote guard. Anonymous requests bypass this — the IP/UA
        # fingerprint has no link to a team.
        user = getattr(request, "user", None)
        user_is_authed = user is not None and getattr(user, "is_authenticated", False)
        if user_is_authed:
            from apps.teams.models import TeamMember

            if TeamMember.objects.filter(
                team=project.team, user=user
            ).exists():
                return Response(
                    {
                        "error": {
                            "code": "forbidden_role",
                            "message": "You cannot vote on your own team's project.",
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        voter_key = _voter_key(request, event)

        # Determine the ballot value.
        if event.voting_mode == "simple":
            n_votes = SIMPLE_VOTE_VALUE
        else:
            try:
                n_votes = int(request.data.get("votes", 1))
            except (TypeError, ValueError):
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": "`votes` must be a positive integer.",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if n_votes < 1:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": (
                                "`votes` must be between 1 and "
                                f"{MAX_QUADRATIC_BALLOT} (inclusive)."
                            ),
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        # Quadratic budget check happens BEFORE any side effects so a
        # rejected ballot does NOT leave a VoteBudget row behind. We
        # need to know what the ballot would cost (delta against any
        # prior live vote) to decide if it fits in the 100-credit budget.
        cost = 0
        delta = 0
        if event.voting_mode == "quadratic":
            cost = n_votes * n_votes
            previous = Vote.objects.filter(
                event=event, project=project, voter_key=voter_key
            ).first()
            previous_cost = (
                previous.votes * previous.votes
                if previous and previous.retracted_at is None
                else 0
            )
            delta = cost - previous_cost
            spent = (
                VoteBudget.objects.filter(
                    event=event, voter_key=voter_key
                )
                .values_list("spent_credits", flat=True)
                .first()
                or 0
            )
            if spent + delta > QUADRATIC_BUDGET:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": (
                                f"Exceeds {QUADRATIC_BUDGET}-credit "
                                "quadratic budget."
                            ),
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        with transaction.atomic():
            if event.voting_mode == "quadratic":
                budget, _ = VoteBudget.objects.select_for_update().get_or_create(
                    event=event, voter_key=voter_key
                )
                budget.spent_credits += delta
                budget.save(update_fields=["spent_credits", "updated_at"])

            vote, _created = Vote.objects.update_or_create(
                event=event,
                project=project,
                voter_key=voter_key,
                defaults={
                    "voter_user": user if user_is_authed else None,
                    "voter_email_hash": "",
                    "votes": n_votes,
                    "retracted_at": None,
                },
            )

            VoteAudit.objects.create(
                vote=vote,
                action="cast",
                ip=_client_ip(request),
                user_agent=_user_agent(request),
            )

        audit_log(
            user if user_is_authed else None,
            "vote.cast",
            vote,
            request=request,
        )

        return Response(
            {
                "vote_id": str(vote.id),
                "votes": n_votes,
                "mode": event.voting_mode,
                "spent_credits": (
                    VoteBudget.objects.get(
                        event=event, voter_key=voter_key
                    ).spent_credits
                    if event.voting_mode == "quadratic"
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @deadline_gated("submissions_close_at")
    def delete(self, request, slug, id):
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

        try:
            project = Submission.objects.get(id=id, event=event)
        except Submission.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Submission {id!r} not found in {slug!r}.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        voter_key = _voter_key(request, event)

        with transaction.atomic():
            try:
                vote = Vote.objects.select_for_update().get(
                    event=event, project=project, voter_key=voter_key
                )
            except Vote.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": "No ballot to retract.",
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if vote.retracted_at is not None:
                # Idempotent: already retracted, no-op.
                return Response({"retracted": True, "already": True})

            if event.voting_mode == "quadratic":
                refund = vote.votes * vote.votes
                budget = VoteBudget.objects.select_for_update().get(
                    event=event, voter_key=voter_key
                )
                budget.spent_credits = max(0, budget.spent_credits - refund)
                budget.save(update_fields=["spent_credits", "updated_at"])

            vote.retracted_at = timezone.now()
            vote.save(update_fields=["retracted_at"])

            VoteAudit.objects.create(
                vote=vote,
                action="retract",
                ip=_client_ip(request),
                user_agent=_user_agent(request),
            )

        audit_log(
            request.user if request.user and request.user.is_authenticated else None,
            "vote.retract",
            vote,
            request=request,
        )

        return Response({"retracted": True, "vote_id": str(vote.id)})
