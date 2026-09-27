"""URLs at the project root: /widget.js (mounted via include() at root)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.widget_js, name="widget_js"),
]
