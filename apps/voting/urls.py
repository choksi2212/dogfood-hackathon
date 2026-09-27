"""URL routes for the voting app.

Mounted under ``/api/`` in ``config/urls.py``. All routes are deadline-gated
inside the view, not via decorator at the URL layer.
"""
from django.urls import path

from . import views

urlpatterns = [
    path(
        "events/<slug:slug>/submissions/<uuid:id>/vote",
        views.VoteView.as_view(),
        name="vote",
    ),
    path(
        "events/<slug:slug>/votes/results",
        views.VoteResultsView.as_view(),
        name="vote_results",
    ),
]
