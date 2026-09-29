"""URLs for signed public records and certificate issuance.

Mounted once at ``api/`` from config/urls.py so the whole feature lives in
one include next to the certificate routes:

  GET   /api/records/judge/<public_id>           public verify — no auth
  POST  /api/events/<slug>/records/judge         organizer: issue judge records
  GET   /api/events/<slug>/records/judge         organizer: list judge records
  POST  /api/events/<slug>/certificates/issue    organizer: issue certificates

The certificate routes stay where they were (apps.certificates.urls at
/api/certificates/...); none of these patterns collide with any other
include in config/urls.py.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("records/judge/<str:public_id>", views.judge_record_view, name="judge_record_view"),
    path("events/<slug:slug>/records/judge", views.JudgeRecordsView.as_view(), name="judge_records"),
    path(
        "events/<slug:slug>/certificates/issue",
        views.CertificatesIssueView.as_view(),
        name="certificates_issue",
    ),
]
