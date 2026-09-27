from django.urls import path

from . import views

app_name = "observability"

urlpatterns = [
    path("metrics", views.metrics, name="metrics"),
    path("observability/ping", views.ping, name="ping"),
]
