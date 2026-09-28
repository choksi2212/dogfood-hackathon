from django.urls import path

from . import views

urlpatterns = [
    path(
        "webhooks/<uuid:webhook_id>/deliveries",
        views.WebhookDeliveryListView.as_view(),
        name="webhook_deliveries",
    ),
]
