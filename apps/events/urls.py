from django.urls import path

from . import views

urlpatterns = [
    path("", views.EventCreateView.as_view()),
    path("<slug:slug>/", views.EventDetailView.as_view()),
    path("<slug:slug>/tracks", views.TrackCreateView.as_view()),
    path("<slug:slug>/rubric", views.RubricCreateView.as_view()),
    path("<slug:slug>/memberships", views.MembershipListView.as_view()),
]
