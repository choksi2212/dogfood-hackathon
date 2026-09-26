from django.urls import path

from . import views

urlpatterns = [
    path("<str:public_id>", views.certificate_view, name="certificate_view"),
]
