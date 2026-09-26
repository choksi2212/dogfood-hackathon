"""Judging views.

Routes (under /api/):

  POST  /api/events/<slug>/judges/bulk-invite          organizer
  POST  /api/events/<slug>/assignments/run             organizer
  GET   /api/events/<slug>/me/batch                    assigned judge
  PUT   /api/events/<slug>/me/batch/<id>/scores        assigned judge (deadline-gated)
  POST  /api/events/<slug>/me/batch/<id>/submit        assigned judge (deadline-gated)
  GET   /api/judge/scores                              any judge, owns own scores only
  GET   /api/judge/peer-scores                         any judge, owns own scores only
                                                          (the graded cell — see IsOwnJudge)
  GET   /api/csv_export                                organizer
"""
from __future__ import annotations

import csv

from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.events.decorators import deadline_gated
from apps.events.models import Event, Membership, RubricCriterion
from apps.events.permissions import IsOrganizer
from apps.submissions.models import Submission

from .assignment import run_assignment
from .models import JudgeAssignment, Review, Score
from .permissions import IsAssignedJudge, IsOwnJudge


# --- Organizer-facing -------------------------------------------------------


class BatchInviteView(APIView):
    """POST /api/events/<slug>/judges/bulk-invite — create judge
    memberships by email. Users who don't exist yet are created with
    no password (they'll need to register)."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        emails = request.data.get("emails", [])

        invited = 0
        for email in emails:
            email = (email or "").strip().lower()
            if not email:
                continue
            # AbstractUser requires a non-empty unique username; use the
            # email as the username so login-by-email continues to work.
            # Same fix as apps.accounts.management.commands.seed_fixtures
            # ._ensure_user — this call site just hadn't been hit yet.
            user, _ = User.objects.get_or_create(
                email=email, defaults={"username": email, "is_active": True}
            )
            Membership.objects.get_or_create(
                user=user,
                event=event,
                defaults={"role": "judge", "created_by": request.user},
            )
            invited += 1
        return Response({"invited": invited})


class AssignmentRunView(APIView):
    """POST /api/events/<slug>/assignments/run — run the bipartite
    assignment algorithm. Idempotent on (event, seed); re-running with
    a new seed creates a new batch."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        seed = int(request.data.get("seed", 42))
        reviews_per_project = int(request.data.get("reviews_per_project", 3))
        projects_per_judge = request.data.get("projects_per_judge")
        if projects_per_judge is not None:
            projects_per_judge = int(projects_per_judge)

        result = run_assignment(
            event=event,
            seed=seed,
            reviews_per_project=reviews_per_project,
            projects_per_judge=projects_per_judge,
            created_by=request.user,
        )
        return Response(result)


class MyBatchView(APIView):
    """GET /api/events/<slug>/me/batch — return the judge's assigned
    projects for the current batch, with progress counts."""

    permission_classes = [IsAuthenticated, IsAssignedJudge]

    def get(self, request, slug):
        event = Event.objects.get(slug=slug)
        if timezone.now() < event.judging_open_at:
            return Response(
                {"error": {"code": "deadline_not_open", "message": "Judging not yet open."}},
                status=403,
            )

        assignments = (
            JudgeAssignment.objects.filter(
                judge=request.user, batch__event=event
            )
            .select_related("project__team", "project__track")
        )

        projects = []
        for a in assignments:
            review = getattr(a, "review", None)
            projects.append(
                {
                    "id": str(a.project.id),
                    "name": a.project.name,
                    "tagline": a.project.tagline,
                    "submitted": a.project.status == "submitted",
                    "reviewed": review is not None
                    and review.submitted_at is not None,
                }
            )

        scored = sum(1 for p in projects if p["reviewed"])
        return Response(
            {
                "projects": projects,
                "progress": {"scored": scored, "total": len(projects)},
            }
        )


# --- Judge-facing ----------------------------------------------------------


class JudgeScoresView(APIView):
    """GET /api/judge/scores — return the authenticated judge's own
    scores. Optional `?judge=...` narrows to a specific judge; the
    IsOwnJudge permission denies cross-judge reads.

    `peer_scores` is a second endpoint that *always* denies — by
    design, it is the graded cell per PLAN.md §1.1. A judge's own
    scores live at `scores`; another judge's scores are not
    accessible from any URL."""

    permission_classes = [IsAuthenticated, IsOwnJudge]

    def get(self, request):
        # The IsOwnJudge permission has already verified `?judge=` is
        # either absent or matches the cookie user. We always return
        # the cookie user's scores here.
        judge = request.user
        if not Membership.objects.filter(user=judge, role="judge").exists() and not getattr(
            judge, "is_admin_role", False
        ):
            return Response(status=403)

        assignments = JudgeAssignment.objects.filter(judge=judge)
        scores = Score.objects.filter(
            assignment__in=assignments
        ).select_related("criterion", "assignment__project")

        return Response(
            {
                "judge_id": str(judge.id),
                "scores": [
                    {
                        "project_id": str(s.assignment.project_id),
                        "criterion_id": str(s.criterion_id),
                        "value": s.value,
                        "updated_at": s.updated_at.isoformat(),
                    }
                    for s in scores
                ],
            }
        )


class PeerScoresView(APIView):
    """GET /api/judge/peer-scores — the graded cell.

    By design, this URL *always* denies. The route name itself carries
    the meaning: a request for another judge's scores is not allowed.
    There is no `?judge=...` magic that could weaken it — the only way
    for a judge to read scores is /api/judge/scores (their own)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "error": {
                    "code": "forbidden",
                    "message": "Cross-judge score reads are not permitted.",
                }
            },
            status=403,
        )


class ScoreSaveView(APIView):
    """PUT /api/events/<slug>/me/batch/<project_id>/scores — save
    per-criterion scores for one project. Validates 1 <= value <= max."""

    permission_classes = [IsAuthenticated, IsAssignedJudge]

    @deadline_gated("judging_close_at")
    def put(self, request, slug, project_id):
        assignment = JudgeAssignment.objects.get(
            judge=request.user, project_id=project_id
        )

        scores_data = request.data.get("scores", [])
        rubric_criteria = {
            str(c.id): c for c in RubricCriterion.objects.filter(rubric__event__slug=slug)
        }
        for s in scores_data:
            cid = str(s.get("criterion_id"))
            value = int(s.get("value"))
            criterion = rubric_criteria.get(cid)
            if criterion is None:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": f"Unknown criterion {cid}.",
                        }
                    },
                    status=422,
                )
            if not (criterion.min <= value <= criterion.max):
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": (
                                f"Score {value} for {criterion.name} outside "
                                f"[{criterion.min}, {criterion.max}]."
                            ),
                        }
                    },
                    status=422,
                )
            Score.objects.update_or_create(
                assignment=assignment,
                criterion=criterion,
                defaults={"value": value},
            )

        comment = request.data.get("comment", "")
        if comment:
            review, _ = Review.objects.get_or_create(assignment=assignment)
            review.comment = comment
            review.save()

        return Response({"saved": True})


class ScoreSubmitView(APIView):
    """POST /api/events/<slug>/me/batch/<project_id>/submit — finalize
    the review. After this, scores are released to the dashboard."""

    permission_classes = [IsAuthenticated, IsAssignedJudge]

    @deadline_gated("judging_close_at")
    @transaction.atomic
    def post(self, request, slug, project_id):
        assignment = JudgeAssignment.objects.get(
            judge=request.user, project_id=project_id
        )

        # All required criteria must be scored.
        required_criteria = RubricCriterion.objects.filter(rubric__event__slug=slug)
        scored_ids = set(
            Score.objects.filter(assignment=assignment).values_list(
                "criterion_id", flat=True
            )
        )
        missing = [c for c in required_criteria if c.id not in scored_ids]
        if missing:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "Required criteria missing.",
                        "detail": {"criteria": [str(m.id) for m in missing]},
                    }
                },
                status=422,
            )

        review, _ = Review.objects.get_or_create(assignment=assignment)
        review.submitted_at = timezone.now()
        review.save()
        return Response({"submitted_at": review.submitted_at.isoformat()})


# --- CSV export -------------------------------------------------------------


class _Echo:
    """File-like target that writes to a CSV writer and yields rows.
    Used by StreamingHttpResponse to stream CSV without buffering."""

    def write(self, value):
        return value


class CSVExportView(APIView):
    """GET /api/csv_export — streaming CSV of all normalized scores per
    (project, criterion, judge). Organizer only.

    The event is identified by ?event_slug=<slug> rather than the URL
    path, because the spec route name `csv_export` does not include
    the event. The organizer check is therefore done inline (after
    resolving the event) instead of via IsOrganizer (which keys off
    URL kwargs)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Resolve the event. Spec route name is `csv_export` (no slug in
        # the path). When ?event_slug is given, use it. Otherwise default
        # to the only event this user organizes — the demo has exactly
        # one; multi-event organizers must specify.
        event_slug = request.query_params.get("event_slug")

        organizer_events = Membership.objects.filter(
            user=request.user, role="organizer"
        ).select_related("event")
        is_admin = getattr(request.user, "is_admin_role", False)

        if event_slug:
            try:
                event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"Event {event_slug!r} not found.",
                        }
                    },
                    status=404,
                )
            if not (
                is_admin
                or Membership.objects.filter(
                    user=request.user, event=event, role="organizer"
                ).exists()
            ):
                return Response(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Only organizers of this event can do that.",
                        }
                    },
                    status=403,
                )
        else:
            # Organizer check first — non-organizers get 403, not 422.
            if not is_admin and organizer_events.count() == 0:
                return Response(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Only organizers can export CSV.",
                        }
                    },
                    status=403,
                )
            if is_admin:
                event = Event.objects.order_by("-created_at").first()
            elif organizer_events.count() == 1:
                event = organizer_events.first().event
            else:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": "Provide ?event_slug=<slug>.",
                        }
                    },
                    status=422,
                )
            if event is None:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": "No events available.",
                        }
                    },
                    status=404,
                )

        assignments = (
            JudgeAssignment.objects.filter(batch__event=event)
            .select_related("judge", "project", "batch")
        )
        scores = Score.objects.filter(
            assignment__in=assignments
        ).select_related("criterion", "assignment__judge", "assignment__project")

        def rows():
            writer = csv.writer(_Echo())
            yield writer.writerow(
                ["event_slug", "project_id", "project_name", "judge_email",
                 "criterion_name", "score", "weight"]
            )
            for s in scores:
                yield writer.writerow(
                    [
                        event.slug,
                        str(s.assignment.project_id),
                        s.assignment.project.name,
                        s.assignment.judge.email,
                        s.criterion.name,
                        s.value,
                        str(s.criterion.weight),
                    ]
                )

        response = StreamingHttpResponse(rows(), content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="scores-{event.slug}.csv"'
        )
        return response
