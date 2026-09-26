from django.urls import path

from . import views

urlpatterns = [
    path("gallery", views.GalleryView.as_view(), name="gallery"),
    path(
        "events/<slug:slug>/submit",
        views.SubmitView.as_view(),
        name="submit",
    ),
]
