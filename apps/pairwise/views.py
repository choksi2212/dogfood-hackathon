"""Pairwise views.

Routes (under /api/):

  POST  /api/events/<slug>/pairwise/ballots   authenticated judge for
                                              this event; persist one
                                              (left, right, winner)
                                              ballot
  GET   /api/events/<slug>/pairwise/ranking   authenticated judge for
                                              this event; runs the BT
                                              fit on every ballot for
                                              the event and returns
                                              the ranked projects.
                                              Idempotent -- each call
                                              creates a new
                                              PairwiseRun row but the
                                              result depends only on
                                              the ballots currently in
                                              the table.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.permissions import IsJudge
from apps.submissions.models import Submission

from .fit import bradley_terry
from .models import PairwiseBallot, PairwiseRanking, PairwiseRun

VALID_WINNERS = ("left", "right", "tie")


class PairwiseBallotView(APIView):
    """POST /api/events/<slug>/pairwise/ballots.

    Body: {left_id, right_id, winner}. Saves one ballot for the
    authenticated judge. Re-posting the same triple from the same
    voter_key overwrites the prior winner -- judges can revise their
    vote until judging_close_at."""

    permission_classes = [IsAuthenticated, IsJudge]

    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": f"Event {slug!r} not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if timezone.now() > event.judging_close_at:
            return Response(
                {"error": {"code": "deadline_passed", "message": "The judging window has closed."}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        left_id = request.data.get("left_id")
        right_id = request.data.get("right_id")
        winner = request.data.get("winner")

        if not left_id or not right_id or left_id == right_id:
            return Response(
                {"error": {"code": "validation_failed", "message": "left_id and right_id must be set and distinct."}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if winner not in VALID_WINNERS:
            return Response(
                {"error": {"code": "validation_failed", "message": f"winner must be one of {VALID_WINNERS}."}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Resolve the projects so we know they exist AND they belong to
        # this event. A ballot about some other event's project is
        # nonsensical.
        try:
            left = Submission.objects.get(id=left_id, event=event)
            right = Submission.objects.get(id=right_id, event=event)
        except Submission.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "left_id or right_id is not a submission for this event.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        voter_key = str(getattr(request.user, "id", "") or "")

        ballot, created = PairwiseBallot.objects.update_or_create(
            event=event,
            voter_key=voter_key,
            left_project=left,
            right_project=right,
            defaults={"winner": winner},
        )

        return Response(
            {
                "ballot_id": str(ballot.id),
                "created": created,
                "winner": winner,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PairwiseRankView(APIView):
    """GET /api/events/<slug>/pairwise/ranking.

    Runs the Bradley-Terry fit on every ballot for the event and
    returns the ranked projects. Each call creates a fresh
    PairwiseRun; the response shape is the same regardless. Re-running
    after new ballots arrive is expected and supported."""

    permission_classes = [IsAuthenticated, IsJudge]

    def get(self, request, slug):
        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": f"Event {slug!r} not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Pull every ballot for the event. The fit is fast for any
        # realistic ballot count; we don't try to be clever about
        # incremental updates.
        ballots_qs = PairwiseBallot.objects.filter(event=event).values("left_project_id", "right_project_id", "winner")
        ballots = [
            {
                "left_id": str(row["left_project_id"]),
                "right_id": str(row["right_project_id"]),
                "winner": row["winner"],
            }
            for row in ballots_qs
        ]

        # The set of project ids is the union of all submissions for
        # the event and every id that appears in any ballot. Submissions
        # with zero ballots still get a theta (regularised by the
        # phantom prior).
        submission_ids = set(str(s.id) for s in Submission.objects.filter(event=event).only("id"))
        ballot_ids = {b["left_id"] for b in ballots} | {b["right_id"] for b in ballots}
        project_ids = sorted(submission_ids | ballot_ids)

        fit = bradley_terry(ballots, project_ids)

        with transaction.atomic():
            run = PairwiseRun.objects.create(
                event=event,
                method="bradley_terry_mm",
                n_ballots=len(ballots),
                iterations=fit["iterations"],
                converged=fit["converged"],
                created_by=request.user,
            )
            if fit["ranking"]:
                PairwiseRanking.objects.bulk_create(
                    [
                        PairwiseRanking(
                            run=run,
                            project_id=r["project_id"],
                            theta=r["theta"],
                            wins=fit["wins"].get(r["project_id"], 0),
                            losses=fit["losses"].get(r["project_id"], 0),
                            ties=fit["ties"].get(r["project_id"], 0),
                            rank=r["rank"],
                        )
                        for r in fit["ranking"]
                    ]
                )

        return Response(
            {
                "run_id": str(run.id),
                "event_slug": event.slug,
                "n_ballots": len(ballots),
                "iterations": fit["iterations"],
                "converged": fit["converged"],
                "ranking": [
                    {
                        "project_id": r["project_id"],
                        "theta": r["theta"],
                        "rank": r["rank"],
                        "wins": fit["wins"].get(r["project_id"], 0),
                        "losses": fit["losses"].get(r["project_id"], 0),
                        "ties": fit["ties"].get(r["project_id"], 0),
                    }
                    for r in fit["ranking"]
                ],
            }
        )
