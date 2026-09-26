"""Root URL configuration.

G1 only exposes `/healthz` and a tiny service-identifying root. Tier routes
are added at G2/G3/G7.
"""
from django.http import JsonResponse
from django.urls import include, path


def root(request):
    return JsonResponse(
        {
            "service": "dogfood-portal",
            "stage": "G1",
            "tiers_claimed": [],
        }
    )


urlpatterns = [
    path("", root, name="root"),
    path("healthz", include("apps.health.urls")),
]
