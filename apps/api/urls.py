from django.urls import path

from . import views

urlpatterns = [
    path("schema/", views.OpenAPISchemaView.as_view(), name="openapi_schema"),
    path("webhooks", views.WebhookListCreateView.as_view(), name="webhooks"),
    # T4 bulk import/export — mounted at api/ in config/urls.py, these
    # resolve to /api/events/<slug>/import and /api/events/<slug>/export.
    # They don't collide with apps.events.urls (tried first at
    # api/events/): nothing there matches "<slug>/import" or
    # "<slug>/export", so resolution falls through to this include.
    path("events/<slug:slug>/import", views.EventImportView.as_view(), name="event_import"),
    path("events/<slug:slug>/export", views.EventExportView.as_view(), name="event_export"),
]
