from django.urls import path

from . import views

urlpatterns = [
    path("schema/", views.OpenAPISchemaView.as_view(), name="openapi_schema"),
    path("webhooks", views.WebhookListCreateView.as_view(), name="webhooks"),
]
