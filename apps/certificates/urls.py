from django.urls import path

from . import views

urlpatterns = [
    path("<str:public_id>", views.certificate_view, name="certificate_view"),
    # T4 spec: signed, verifiable judge participation records. Main's
    # implementation is JudgeRecord (not JudgeCertificate) — exposed via
    # judge_record_view. Same public-id shape as submission certificates
    # so the URL is opaque and unguessable.
    path("judges/<str:public_id>", views.judge_record_view, name="judge_certificate_view"),
]
