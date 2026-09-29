"""T3 (Community Voting) views.

Endpoints (under /api/):

  POST   /api/events/<slug>/submissions/<id>/vote   cast or update a ballot
  DELETE /api/events/<slug>/submissions/<id>/vote   retract a ballot
  GET    /api/events/<slug>/votes/results           live tally — organizers
                                                      always, any session once
                                                      results_at has passed

Both are deadline-gated by ``judging_close_at``: community voting runs
alongside judge review — ballots land on final, submitted work — and
closes when judging closes (``@deadline_gated`` rejects once
``now > judging_close_at`` — see tests/voting/test_voting.py, which
builds its own event with that deadline in the future specifically to
exercise the "voting allowed" paths). Gating on the *submission*
window would make community voting impossible on any real event, since
voting is what happens after submissions close. Results stay hidden
from non-organizers until ``results_at`` regardless. Anti-abuse is
layered at the proxy / abuse-flag app.

Mode semantics (see ``Event.voting_mode``):

* ``simple``    — every cast is exactly 1 vote. ``votes`` is forced to 1
                  for storage consistency; the budget table is unused.
* ``quadratic`` — the voter may spend any ``n`` up to the per-ballot cap;
                  the cost is ``n**2`` credits out of a 100-credit event
                  budget for that voter.
"""

import hashlib
import os

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import CookieSessionAuthentication
from apps.audit.helpers import log as audit_log
from apps.events.decorators import deadline_gated
from apps.events.models import Event, Membership
from apps.submissions.models import Submission
from apps.webhooks.delivery import notify

from .models import Vote, VoteAudit, VoteBudget


def _client_ip(request) -> str | None:
    """Client IP. X-Forwarded-For is untrusted by default (issue #45):
    a client can set the header to any value, so honouring it lets a
    spoofed first element mint a fresh rate-limit bucket / fingerprint
    per request. Deployments behind a trusted proxy that appends the
    real client IP can opt in via TRUST_PROXY=true.
    """
    if os.environ.get("TRUST_PROXY", "").lower() in ("1", "true", "yes"):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

QUADRATIC_BUDGET = 100
SIMPLE_VOTE_VALUE = 1
MAX_QUADRATIC_BALLOT = 10  # n <= 10 -> cost <= 100; matches the budget


def _voter_key(request, event) -> str:
    """Stable, opaque voter identifier.

    Authenticated users get ``user:<uuid>``. Anonymous voters get
    ``fp:<sha256(ip + user_agent)[:32]>`` — collision-prone in theory
    (shared NAT, library Wi-Fi) but cheap and well-bounded for the
    hackathon threat model.

    With ``CookieSessionAuthentication`` on the view, an anonymous
    request resolves ``request.user`` to ``None`` (the project sets
    ``UNAUTHENTICATED_USER = None``), which is handled here the same
    as any unauthenticated request.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user:{user.id}"
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.headers.get("User-Agent", "")
    digest = hashlib.sha256(f"{ip}{ua}".encode()).hexdigest()[:32]
    return f"fp:{digest}"


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
    * Retraction is ownership-checked (issue #78): the request must
      resolve to the SAME voter identity that cast the ballot — the
      authenticated user for ``user:`` keys, or the same IP+UA
      fingerprint for ``fp:`` keys. An anonymous visitor sharing the
      fingerprint can no longer retract an authenticated participant's
      ballot, because a ``user:`` row is never matched by a
      fingerprint key.
    """

    permission_classes = [AllowAny]
    # Session auth so an authenticated voter is identified as
    # ``user:<id>`` (self-vote guard, audit attribution, retraction
    # ownership). CookieSessionAuthentication returns None for
    # anonymous requests, so open voting stays open for visitors.
    authentication_classes = [CookieSessionAuthentication]

    @deadline_gated("judging_close_at")
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

            if TeamMember.objects.filter(team=project.team, user=user).exists():
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
                            "message": (f"`votes` must be between 1 and {MAX_QUADRATIC_BALLOT} (inclusive)."),
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
            previous = Vote.objects.filter(event=event, project=project, voter_key=voter_key).first()
            previous_cost = previous.votes * previous.votes if previous and previous.retracted_at is None else 0
            delta = cost - previous_cost
            spent = (
                VoteBudget.objects.filter(event=event, voter_key=voter_key)
                .values_list("spent_credits", flat=True)
                .first()
                or 0
            )
            if spent + delta > QUADRATIC_BUDGET:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": (f"Exceeds {QUADRATIC_BUDGET}-credit quadratic budget."),
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        with transaction.atomic():
            if event.voting_mode == "quadratic":
                budget, _ = VoteBudget.objects.select_for_update().get_or_create(event=event, voter_key=voter_key)
                budget.spent_credits += delta
                budget.save(update_fields=["spent_credits", "updated_at"])
                spent_after = budget.spent_credits
            else:
                spent_after = None

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

        # T4 webhooks: tally subscribers get the new count. Deliberately
        # no voter identity in the payload — votes are pseudonymous and
        # the audit trail (organizer-only) already records the actor.
        notify(
            event,
            "vote.created",
            {
                "event": event.slug,
                "project_id": str(project.id),
                "project": project.name,
                "votes": n_votes,
                "mode": event.voting_mode,
            },
        )

        return Response(
            {
                "vote_id": str(vote.id),
                "votes": n_votes,
                "mode": event.voting_mode,
                "spent_credits": spent_after,
            },
            status=status.HTTP_201_CREATED,
        )

    @deadline_gated("judging_close_at")
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

        # Ownership check (issue #78): the lookup is scoped to the
        # caller's own voter_key, so a request can only ever retract
        # a ballot cast by the SAME identity — the authenticated user
        # for ``user:`` keys, or the same IP+UA fingerprint for ``fp:``
        # keys. (Pre-fix, authenticated voters were mis-keyed as
        # fingerprints, so an anonymous visitor sharing the fingerprint
        # could retract a participant's ballot.)
        vote = Vote.objects.filter(event=event, project=project, voter_key=voter_key).first()
        if vote is None:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": "No ballot to retract.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Mode-mismatch guard (issue #77): a ballot cast under simple
        # mode has no VoteBudget row. If the organizer has since
        # flipped the event to quadratic, refunding would raise
        # VoteBudget.DoesNotExist -> 500. Answer 409 instead.
        if event.voting_mode == "quadratic" and vote.votes > 0 and not VoteBudget.objects.filter(
            event=event, voter_key=vote.voter_key
        ).exists():
            return Response(
                {
                    "error": {
                        "code": "mode_mismatch",
                        "message": (
                            "This ballot was cast before the event switched to "
                            "quadratic voting and has no credit budget to refund; "
                            "it cannot be retracted under the new mode."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            vote = Vote.objects.select_for_update().get(pk=vote.pk)
            if vote.retracted_at is not None:
                # Idempotent: already retracted, no-op.
                return Response({"retracted": True, "already": True})

            if event.voting_mode == "quadratic":
                refund = vote.votes * vote.votes
                budget = VoteBudget.objects.select_for_update().get(event=event, voter_key=vote.voter_key)
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


class VoteResultsView(APIView):
    """GET /api/events/<slug>/votes/results — live vote tally per
    project.

    Organizers (and admins) always get the tally. Any other signed-in
    session gets it once the results window has opened — ``now >=
    results_at`` (FR-230/FR-231 in docs/PRD.md §3.3: before
    ``results_at`` non-organizers receive 403, after it any session
    receives 200). Retracted ballots contribute zero (see
    Vote.effective_votes); a project with only retracted votes still
    appears with vote_count 0 rather than being omitted, so the full
    submission set stays visible. ``results_visible`` mirrors the
    same state so the frontend can decide whether tallies are final."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
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

        results_visible = event.results_at is None or timezone.now() >= event.results_at
        if not results_visible:
            is_organizer = getattr(request.user, "is_admin_role", False) or (
                Membership.objects.filter(user=request.user, event=event, role="organizer").exists()
            )
            if not is_organizer:
                return Response(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Results are not published yet — tallies open at the event's results time.",
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        projects = Submission.objects.filter(event=event, status="submitted")
        tally = {
            str(p.id): {
                "project_id": str(p.id),
                "project_name": p.name,
                "vote_count": 0,
                "total_votes": 0,
            }
            for p in projects
        }

        live_votes = Vote.objects.filter(
            event=event, project__in=projects, retracted_at__isnull=True
        )
        for v in live_votes:
            row = tally.get(str(v.project_id))
            if row is None:
                continue
            row["vote_count"] += 1
            row["total_votes"] += v.votes

        results = sorted(
            tally.values(), key=lambda r: r["total_votes"], reverse=True
        )

        return Response(
            {
                "event_slug": event.slug,
                "voting_mode": event.voting_mode,
                "results_visible": results_visible,
                "results": results,
            }
        )
