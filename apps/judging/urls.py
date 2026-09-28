from django.urls import path

from . import views

urlpatterns = [
    # Organizer
    path(
        "events/<slug:slug>/judges/bulk-invite",
        views.BatchInviteView.as_view(),
        name="judges_bulk_invite",
    ),
    path(
        "events/<slug:slug>/assignments/run",
        views.AssignmentRunView.as_view(),
        name="assignments_run",
    ),
    # Assigned judge
    path(
        "events/<slug:slug>/me/batch",
        views.MyBatchView.as_view(),
        name="me_batch",
    ),
    path(
        "events/<slug:slug>/me/batch/<uuid:project_id>/scores",
        views.ScoreSaveView.as_view(),
        name="score_save",
    ),
    path(
        "events/<slug:slug>/me/batch/<uuid:project_id>/submit",
        views.ScoreSubmitView.as_view(),
        name="score_submit",
    ),
    # Spec routes (judge_scores / peer_scores / csv_export)
    path(
        "judge/scores",
        views.JudgeScoresView.as_view(),
        name="judge_scores",
    ),
    path(
        "judge/peer-scores",
        views.PeerScoresView.as_view(),
        name="peer_scores",
    ),
    path(
        "csv_export",
        views.CSVExportView.as_view(),
        name="csv_export",
    ),
    # T2: organizer-only "every stage" CSV export endpoints. Each
    # route produces a CSV of one stage's data — spec mandates "CSV
    # export at every stage", so per-stage routes are clearer than
    # one consolidated `/csv?kind=...` URL.
    path(
        "events/<slug:slug>/csv/scores",
        views.CSVScoresView.as_view(),
        name="csv_scores",
    ),
    path(
        "events/<slug:slug>/csv/roster",
        views.CSVRosterView.as_view(),
        name="csv_roster",
    ),
    path(
        "events/<slug:slug>/csv/assignments",
        views.CSVAssignmentsView.as_view(),
        name="csv_assignments",
    ),
    path(
        "events/<slug:slug>/csv/submissions",
        views.CSVSubmissionsView.as_view(),
        name="csv_submissions",
    ),
    path(
        "events/<slug:slug>/csv/audit",
        views.CSVAuditView.as_view(),
        name="csv_audit",
    ),
    path(
        "events/<slug:slug>/csv/rankings",
        views.CSVRankingsView.as_view(),
        name="csv_rankings",
    ),
    # T2: organizer-wide live judging progress — one row per judge
    # with scored/total counts and per-event totals.
    path(
        "events/<slug:slug>/progress",
        views.EventProgressView.as_view(),
        name="event_progress",
    ),
]
