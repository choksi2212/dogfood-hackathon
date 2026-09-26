from django.urls import path

from . import views

urlpatterns = [
    path("<slug:slug>/teams", views.TeamCreateView.as_view()),
    path("<slug:slug>/teams/<uuid:id>/invite", views.InviteCreateView.as_view()),
    path("teams/join", views.JoinTeamView.as_view()),
]
