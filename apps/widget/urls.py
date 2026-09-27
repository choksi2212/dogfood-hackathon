"""URLs under /api/widget/* (gallery endpoint)."""

from django.urls import path

from . import views

urlpatterns = [
    path("widget/gallery", views.widget_gallery, name="widget_gallery"),
]
