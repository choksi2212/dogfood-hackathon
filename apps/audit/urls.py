from django.urls import path

from . import views

urlpatterns = [
    path(
        "events/<slug:slug>/audit-log",
        views.AuditLogView.as_view(),
        name="audit_log",
    ),
]
