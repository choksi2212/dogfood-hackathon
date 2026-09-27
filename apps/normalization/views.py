"""Normalization views.

Routes (mounted under /api/):

  POST /api/events/<slug>/normalize     organizer-only

Idempotent on (event): each call creates a new `NormalizationRun` row;
old runs are kept for audit. The proof text is stored on the run's
`proof_text` field and also returned in the response so the caller can
write it to disk at submission time.
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.helpers import log as audit_log
from apps.events.models import Event
from apps.events.permissions import IsOrganizer
from apps.judging.models import Score

from .fit import normalize
from .models import JudgeBias, NormalizationRun, NormalizedScore
from .proof import generate_proof


class NormalizeView(APIView):
    """POST /api/events/<slug>/normalize — run the two-way additive fit
    on every score in the event, persist the result, return the proof."""

    permission_classes = [IsOrganizer]

    @transaction.atomic
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)

        # Pull every score cell in the event. One row in `judging_score`
        # is one (assignment, criterion) — for the additive fit we want
        # one number per (project, judge), so we sum across criteria
        # AFTER weighting by the criterion weight. The additive model is
        # on the weighted rubric total so `q_i` is in rubric units.
        scores_qs = (
            Score.objects.filter(assignment__batch__event=event)
            .select_related("assignment__project", "assignment__judge", "criterion")
            .values(
                "assignment__project_id",
                "assignment__judge_id",
                "value",
                "criterion__weight",
            )
        )

        # Aggregate weighted score per (project, judge), keeping the
        # last value when duplicates exist (defensive — Score has
        # unique_together on (assignment, criterion) but a defensive
        # dedup at the (project, judge) level costs nothing).
        weighted: dict[tuple[str, str], float] = {}
        for row in scores_qs:
            project_id = str(row["assignment__project_id"])
            judge_id = str(row["assignment__judge_id"])
            value = float(row["value"]) * float(row["criterion__weight"])
            weighted[(project_id, judge_id)] = value

        deduped = [
            {
                "project_id": project_id,
                "judge_id": judge_id,
                "value": value,
            }
            for (project_id, judge_id), value in weighted.items()
        ]

        result = normalize(deduped)

        if not result.is_connected:
            audit_log(
                request.user,
                "normalization.run",
                None,
                payload={"event": slug, "result": "disconnected"},
                request=request,
                result="error",
            )
            return Response(
                {
                    "error": {
                        "code": "disconnected_graph",
                        "message": (
                            "Bipartite graph (projects x judges) is "
                            "disconnected; cannot fit a single global "
                            "normalization."
                        ),
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        run = NormalizationRun.objects.create(
            event=event,
            method="additive_alternating_means",
            params={},
            created_by=request.user,
            raw_sigma=result.raw_sigma,
            normalized_sigma=result.normalized_sigma,
            is_connected=result.is_connected,
            iterations=result.iterations,
            n_reviews=result.n_reviews,
            n_projects=len(result.scores),
            n_judges=len(result.biases),
        )
        NormalizedScore.objects.bulk_create(
            [
                NormalizedScore(
                    run=run,
                    project_id=s["project_id"],
                    raw_mean=s["raw_mean"],
                    adjusted=s["adjusted"],
                    rank_before=s["rank_before"],
                    rank_after=s["rank_after"],
                )
                for s in result.scores
            ]
        )
        JudgeBias.objects.bulk_create(
            [
                JudgeBias(
                    run=run,
                    judge_id=b["judge_id"],
                    bias=b["bias"],
                    n_reviews=b["n_reviews"],
                    leverage=b["leverage"],
                )
                for b in result.biases
            ]
        )

        proof = generate_proof(run, result)
        run.proof_text = proof
        run.save(update_fields=["proof_text"])

        audit_log(
            request.user,
            "normalization.run",
            run,
            payload={
                "event": slug,
                "raw_sigma": run.raw_sigma,
                "normalized_sigma": run.normalized_sigma,
                "iterations": run.iterations,
            },
            request=request,
        )

        return Response(
            {
                "run_id": str(run.id),
                "raw_sigma": run.raw_sigma,
                "normalized_sigma": run.normalized_sigma,
                "is_connected": run.is_connected,
                "iterations": run.iterations,
                "n_projects": run.n_projects,
                "n_judges": run.n_judges,
                "n_reviews": run.n_reviews,
                "proof": proof,
            },
            status=status.HTTP_201_CREATED,
        )
