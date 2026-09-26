from django.urls import path

from . import views


urlpatterns = [
    path(
        "events/<slug:slug>/pairwise/ballots",
        views.PairwiseBallotView.as_view(),
        name="pairwise_ballots",
    ),
    path(
        "events/<slug:slug>/pairwise/ranking",
        views.PairwiseRankView.as_view(),
        name="pairwise_ranking",
    ),
]
