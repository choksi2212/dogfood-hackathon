"""URLs under /api/widget/* (gallery endpoint)."""

from django.urls import path

from . import views

urlpatterns = [
    # Both forms accepted — embedders using either path hit the same
    # handler. Trailing-slash alias is declared in openapi.yaml.
    path("widget/gallery", views.widget_gallery, name="widget_gallery"),
    path("widget/gallery/", views.widget_gallery, name="widget_gallery_slash"),
]
