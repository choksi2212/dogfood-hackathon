from django.urls import path

from . import views

urlpatterns = [
    path(
        "events/<slug:slug>/normalize",
        views.NormalizeView.as_view(),
        name="event_normalize",
    ),
]
