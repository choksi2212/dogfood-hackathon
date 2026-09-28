from django.urls import path

from . import views

urlpatterns = [
    path("<str:public_id>", views.certificate_view, name="certificate_view"),
    # T4 spec: signed, verifiable judge participation records. Same
    # public-id shape as submission certificates (token_urlsafe(24))
    # so the URL is opaque and unguessable.
    path("judges/<str:public_id>", views.judge_certificate_view, name="judge_certificate_view"),
]
