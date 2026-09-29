from django.urls import path

from . import views

urlpatterns = [
    path("gallery", views.GalleryView.as_view(), name="gallery"),
    # Issue #17: the per-event gallery documented in ARCHITECTURE.md
    # §15.3 / JUDGING.md (200 for every role). Same view as /api/gallery
    # — the <slug:slug> kwarg scopes the queryset to one event.
    path(
        "events/<slug:slug>/gallery",
        views.GalleryView.as_view(),
        name="event_gallery",
    ),
    path("submissions/<uuid:id>", views.SubmissionDetailView.as_view(), name="submission_detail"),
    path(
        "events/<slug:slug>/submit",
        views.SubmitView.as_view(),
        name="submit",
    ),
    path(
        "events/<slug:slug>/submissions/<uuid:id>/comments",
        views.CommentListCreateView.as_view(),
        name="comments",
    ),
    path(
        "events/<slug:slug>/submissions/<uuid:id>/comments/<uuid:comment_id>",
        views.CommentModerateView.as_view(),
        name="moderate_comment",
    ),
    # T1 spec: image gallery per submission. POST adds one image; DELETE
    # removes by id; GET lists (used internally — public read happens
    # through SubmissionDetailView which now nests `images`).
    path(
        "events/<slug:slug>/submissions/<uuid:id>/images",
        views.SubmissionImageView.as_view(),
        name="submission_images",
    ),
    path(
        "events/<slug:slug>/submissions/<uuid:id>/images/<uuid:image_id>",
        views.SubmissionImageView.as_view(),
        name="submission_image",
    ),
]
