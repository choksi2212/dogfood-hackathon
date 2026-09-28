from django.urls import path

from . import views

urlpatterns = [
    path("schema/", views.OpenAPISchemaView.as_view(), name="openapi_schema"),
    path("webhooks", views.WebhookListCreateView.as_view(), name="webhooks"),
    # T4 spec: bulk import endpoint. Organizer-only, accepts a JSON
    # body keyed by kind (judges / teams / submissions).
    path(
        "events/<slug:slug>/bulk/import",
        views.BulkImportView.as_view(),
        name="bulk_import",
    ),
]
