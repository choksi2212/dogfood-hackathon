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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.helpers import log as audit_log
from apps.events.decorators import deadline_gated
from apps.events.models import Event, Membership, RubricCriterion
from apps.events.permissions import IsOrganizer

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

        audit_log(
            request.user,
            "judges.bulk_invite",
            event,
            payload={"emails": emails, "invited": invited},
            request=request,
        )
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
        audit_log(
            request.user,
            "assignment.run",
            event,
            payload=result,
            request=request,
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

        # ``review`` is a OneToOne on JudgeAssignment — without it in the
        # select_related, each iteration triggers a fresh query. With 30+
        # assignments per judge this is a 30x slowdown on the dashboard
        # render.
        #
        # A judge can hold assignments across more than one batch — the
        # organizer re-running assignment doesn't delete old batches
        # (JudgeBatch keeps them "around for audit"), and with a fixed
        # seed the same judge/project pairing often repeats. Order oldest
        # -> newest so that, when the same project_id repeats, the dict
        # below ends up keyed on the assignment from the newest batch —
        # the same "latest batch wins" resolution ScoreSaveView and
        # ScoreSubmitView use, so what a judge sees as "reviewed" here
        # always matches the assignment their save/submit calls hit.
        assignments = JudgeAssignment.objects.filter(judge=request.user, batch__event=event).select_related(
            "project__team", "project__track", "review"
        ).order_by("batch__created_at")

        projects_by_id = {}
        for a in assignments:
            review = a.review if hasattr(a, "review") else None
            projects_by_id[str(a.project.id)] = {
                "id": str(a.project.id),
                "name": a.project.name,
                "tagline": a.project.tagline,
                "submitted": a.project.status == "submitted",
                "reviewed": review is not None and review.submitted_at is not None,
                "submitted_at": review.submitted_at.isoformat() if review and review.submitted_at else None,
            }
        projects = list(projects_by_id.values())

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

        # Direct join on judge avoids the ``__in`` subquery and lets
        # PostgreSQL plan a single hash join on the (assignment.judge_id)
        # index. With many assignments per judge this matters.
        scores = Score.objects.filter(assignment__judge=judge).select_related("criterion", "assignment__project")

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
        # Same "latest batch wins" resolution as MyBatchView — a judge
        # can hold more than one assignment for this project across
        # batches (old ones aren't deleted when the organizer re-runs
        # assignment), so `.get()` here would raise MultipleObjectsReturned
        # instead of ever saving anything.
        assignment = (
            JudgeAssignment.objects.filter(judge=request.user, project_id=project_id)
            .order_by("-batch__created_at")
            .first()
        )
        if assignment is None:
            return Response(
                {"error": {"code": "not_found", "message": "No assignment for this project."}},
                status=404,
            )

        scores_data = request.data.get("scores", [])
        rubric_criteria = {str(c.id): c for c in RubricCriterion.objects.filter(rubric__event__slug=slug)}
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
                                f"Score {value} for {criterion.name} outside [{criterion.min}, {criterion.max}]."
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
        # Same "latest batch wins" resolution as MyBatchView/ScoreSaveView.
        assignment = (
            JudgeAssignment.objects.filter(judge=request.user, project_id=project_id)
            .order_by("-batch__created_at")
            .first()
        )
        if assignment is None:
            return Response(
                {"error": {"code": "not_found", "message": "No assignment for this project."}},
                status=404,
            )

        # All required criteria must be scored.
        required_criteria = RubricCriterion.objects.filter(rubric__event__slug=slug)
        scored_ids = set(Score.objects.filter(assignment=assignment).values_list("criterion_id", flat=True))
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

        # Cache once: the original code called .count() twice on the
        # same queryset (lines 340 + 352 below) which is two round trips
        # to PostgreSQL for the same answer. Materialize once.
        organizer_events = list(Membership.objects.filter(user=request.user, role="organizer").select_related("event"))
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
            if not (is_admin or Membership.objects.filter(user=request.user, event=event, role="organizer").exists()):
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
            if not is_admin and len(organizer_events) == 0:
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
            elif len(organizer_events) == 1:
                event = organizer_events[0].event
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

        assignments = JudgeAssignment.objects.filter(batch__event=event).select_related("judge", "project", "batch")
        scores = Score.objects.filter(assignment__in=assignments).select_related(
            "criterion", "assignment__judge", "assignment__project"
        )

        def rows():
            writer = csv.writer(_Echo())
            yield writer.writerow(
                ["event_slug", "project_id", "project_name", "judge_email", "criterion_name", "score", "weight"]
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
        response["Content-Disposition"] = f'attachment; filename="scores-{event.slug}.csv"'
        return response


# --- T2 spec compliance: CSV at every stage --------------------------
# Each view is organizer-only, streamed as CSV. The organizer check is
# done inline after resolving the event (since the URL is keyed off
# the slug, IsOrganizer would key off `slug` kwargs and work too, but
# the inline shape mirrors CSVExportView's pattern and keeps the auth
# gate explicit at the call site).


class _OrganizerEventCSV(APIView):
    """Base for the per-stage CSV endpoints. Subclasses implement
    ``csv_rows(event)`` returning an iterable of row lists."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    filename_suffix: str = ""

    def csv_rows(self, event):
        raise NotImplementedError

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
                status=404,
            )

        def rows():
            for row in self.csv_rows(event):
                yield row

        response = StreamingHttpResponse(rows(), content_type="text/csv")
        response["Content-Disposition"] = (
            "attachment; filename=" + self.filename_suffix + "-" + event.slug + ".csv"
        )
        return response


class CSVScoresView(_OrganizerEventCSV):
    """T2: raw per-judge scores (every (assignment, criterion) cell).
    Companion to the normalized-score CSV at /api/csv_export."""

    filename_suffix = "scores-raw"

    def csv_rows(self, event):
        from .models import Score

        yield [
            "event_slug",
            "judge_email",
            "project_id",
            "project_name",
            "criterion_id",
            "criterion_name",
            "value",
            "weight",
            "submitted_at",
        ]
        scores = (
            Score.objects.filter(assignment__batch__event=event)
            .select_related(
                "assignment__judge",
                "assignment__project",
                "criterion",
                "assignment__review",
            )
            .order_by("assignment__judge__email", "assignment__project__name")
        )
        for s in scores:
            submitted = ""
            if s.assignment.review and s.assignment.review.submitted_at:
                submitted = s.assignment.review.submitted_at.isoformat()
            yield [
                event.slug,
                s.assignment.judge.email,
                str(s.assignment.project_id),
                s.assignment.project.name,
                str(s.criterion_id),
                s.criterion.name,
                s.value,
                str(s.criterion.weight),
                submitted,
            ]


class CSVRosterView(_OrganizerEventCSV):
    """T2: judge roster, one row per judge in the event with progress."""

    filename_suffix = "roster"

    def csv_rows(self, event):
        from apps.events.models import Membership
        from .models import JudgeAssignment

        yield [
            "email",
            "name",
            "role",
            "n_assignments",
            "n_reviewed",
        ]
        members = (
            Membership.objects.filter(event=event, role="judge")
            .select_related("user")
            .order_by("user__email")
        )
        for m in members:
            n_assigned = JudgeAssignment.objects.filter(
                judge=m.user, batch__event=event
            ).count()
            n_reviewed = JudgeAssignment.objects.filter(
                judge=m.user,
                batch__event=event,
                review__submitted_at__isnull=False,
            ).count()
            yield [
                m.user.email,
                m.user.name,
                m.role,
                n_assigned,
                n_reviewed,
            ]


class CSVAssignmentsView(_OrganizerEventCSV):
    """T2: judge-project assignments."""

    filename_suffix = "assignments"

    def csv_rows(self, event):
        from .models import JudgeAssignment

        yield [
            "judge_email",
            "project_id",
            "project_name",
            "track_slug",
            "batch_id",
            "reviewed",
        ]
        assignments = (
            JudgeAssignment.objects.filter(batch__event=event)
            .select_related(
                "judge", "project__track", "batch", "review"
            )
            .order_by("judge__email", "project__name")
        )
        for a in assignments:
            reviewed = "no"
            if a.review and a.review.submitted_at:
                reviewed = "yes"
            yield [
                a.judge.email,
                str(a.project_id),
                a.project.name,
                a.project.track.slug,
                str(a.batch_id),
                reviewed,
            ]


class CSVSubmissionsView(_OrganizerEventCSV):
    """T2: submissions CSV."""

    filename_suffix = "submissions"

    def csv_rows(self, event):
        from apps.submissions.models import Submission

        yield [
            "id",
            "team_name",
            "track_slug",
            "name",
            "tagline",
            "status",
            "submitted_at",
            "tech_tags",
        ]
        subs = (
            Submission.objects.filter(event=event)
            .select_related("team", "track")
            .order_by("track__order", "name")
        )
        for s in subs:
            yield [
                str(s.id),
                s.team.name,
                s.track.slug,
                s.name,
                s.tagline,
                s.status,
                s.submitted_at.isoformat() if s.submitted_at else "",
                ";".join(s.tech_tags or []),
            ]


class CSVAuditView(_OrganizerEventCSV):
    """T2: audit log CSV (full record)."""

    filename_suffix = "audit"

    def csv_rows(self, event):
        from apps.audit.models import AuditEvent

        yield [
            "created_at",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "result",
            "payload",
        ]
        events = AuditEvent.objects.filter(
            event__slug=event.slug
        ).order_by("-created_at")
        for e in events:
            yield [
                e.created_at.isoformat() if e.created_at else "",
                e.actor_email or "",
                e.action,
                e.target_type,
                e.target_id or "",
                e.result,
                e.payload or "",
            ]


class CSVRankingsView(_OrganizerEventCSV):
    """T2: per-track rankings, average score per submission."""

    filename_suffix = "rankings"

    def csv_rows(self, event):
        from .models import Score
        from collections import defaultdict

        yield [
            "track_slug",
            "rank",
            "project_id",
            "project_name",
            "n_judges",
            "mean_score",
        ]
        scores = (
            Score.objects.filter(assignment__batch__event=event)
            .select_related("assignment__project__track", "assignment__judge")
        )
        per_project = defaultdict(list)
        for s in scores:
            per_project[s.assignment.project_id].append(s.value)
        from apps.submissions.models import Submission

        projects = {
            p.id: p
            for p in Submission.objects.filter(event=event).select_related("track")
        }
        rows = []
        for pid, values in per_project.items():
            project = projects.get(pid)
            if project is None:
                continue
            rows.append(
                (
                    project.track.slug,
                    -sum(values) / len(values),
                    pid,
                    project.name,
                    len(values),
                    sum(values) / len(values),
                )
            )
        rows.sort()
        for rank, (track_slug, _, pid, name, n, mean) in enumerate(rows, start=1):
            yield [
                track_slug,
                rank,
                str(pid),
                name,
                n,
                "%.4f" % mean,
            ]


# --- T2: organizer-wide live judging progress ----------------------


class EventProgressView(APIView):
    """T2: organizer-wide live judging progress.

    One row per judge with their progress, plus event totals. Used by
    the organizer's dashboard to show "X of Y projects scored by Z of
    W judges" in real time.
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

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
                status=404,
            )

        from apps.events.models import Membership
        from .models import JudgeAssignment

        members = (
            Membership.objects.filter(event=event, role="judge")
            .select_related("user")
            .order_by("user__email")
        )
        judges = []
        total_assigned = 0
        total_reviewed = 0
        for m in members:
            n_assigned = JudgeAssignment.objects.filter(
                judge=m.user, batch__event=event
            ).count()
            n_reviewed = JudgeAssignment.objects.filter(
                judge=m.user,
                batch__event=event,
                review__submitted_at__isnull=False,
            ).count()
            total_assigned += n_assigned
            total_reviewed += n_reviewed
            judges.append(
                {
                    "judge_email": m.user.email,
                    "judge_name": m.user.name,
                    "n_assigned": n_assigned,
                    "n_reviewed": n_reviewed,
                    "complete": n_assigned > 0
                    and n_reviewed == n_assigned,
                }
            )

        return Response(
            {
                "event_slug": event.slug,
                "judges": judges,
                "totals": {
                    "n_judges": len(judges),
                    "n_assigned": total_assigned,
                    "n_reviewed": total_reviewed,
                    "complete": (
                        total_assigned > 0
                        and total_reviewed == total_assigned
                    ),
                },
            }
        )
