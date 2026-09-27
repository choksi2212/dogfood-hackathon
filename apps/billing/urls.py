from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("plans", views.PlanListView.as_view(), name="plans"),
    path(
        "account/<slug:slug>",
        views.BillingAccountView.as_view(),
        name="account",
    ),
    path(
        "account/<slug:slug>/upgrade",
        views.UpgradePlanView.as_view(),
        name="upgrade",
    ),
]
