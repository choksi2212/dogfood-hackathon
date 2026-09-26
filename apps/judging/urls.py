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
]
