"""Root URL configuration.

T1 (G2):
  /healthz                         — liveness (already shipped in G1)
  /api/gallery                     — public, returns submitted projects
  /api/events/<slug>/submit        — participant, deadline-gated

T2 (G3) adds:
  /api/judge/scores                — judge_a (own), 401/403 for judge_b
  /api/judge/peer-scores           — judge_b's scores — DENIED (graded cell)
  /api/csv_export                  — organizer, streams CSV
"""
from django.http import JsonResponse
from django.urls import include, path


def root(request):
    return JsonResponse(
        {
            "service": "dogfood-portal",
            "stage": "G2",
            "tiers_claimed": ["t1"],
        }
    )


urlpatterns = [
    path("", root, name="root"),
    path("healthz", include("apps.health.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/events/", include("apps.events.urls")),
    path("api/", include("apps.teams.urls")),
    path("api/", include("apps.submissions.urls")),
    path("api/", include("apps.judging.urls")),
    path("api/", include("apps.voting.urls")),
]
