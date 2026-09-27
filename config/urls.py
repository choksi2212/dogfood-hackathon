"""Root URL configuration.

T1 (G2):
  /healthz                          liveness (G1)
  /api/gallery                      public, returns submitted projects
  /api/events/<slug>/submit         participant, deadline-gated

T2 (G3):
  /api/judge/scores                 judge_a (own), 401/403 for judge_b
  /api/judge/peer-scores            judge_b's scores — DENIED (graded cell)
  /api/csv_export                   organizer, streams CSV

G4 (normalization):
  /api/events/<slug>/normalize      organizer, run additive fit

G5 (voting):
  /api/events/<slug>/submissions/<id>/vote  cast/retract
  /api/events/<slug>/votes/results          organizer, per-project tally
  /api/events/<slug>/audit-log              organizer, human-readable trail

G6 (pairwise):
  /api/events/<slug>/pairwise/ballots       POST ballot
  /api/events/<slug>/pairwise/ranking      GET ranking

G7 (T4 surface):
  /widget.js                                  embeddable JS
  /api/widget/gallery                         JSON feed for widget
  /api/certificates/<public_id>              signed certificate
  /api/webhooks                               organizer subscriptions
  /api/schema/                                OpenAPI 3 as JSON
"""

from django.http import JsonResponse
from django.urls import include, path


def root(request):
    return JsonResponse(
        {
            "service": "dogfood-portal",
            "stage": "G8",
            "tiers_claimed": ["t1", "t2"],
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
    path("api/", include("apps.normalization.urls")),
    path("api/", include("apps.voting.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.abuse.urls")),
    path("api/", include("apps.pairwise.urls")),
    path("api/", include("apps.api.urls")),
    path("api/certificates/", include("apps.certificates.urls")),
    path("api/", include("apps.widget.urls")),
    path("widget.js", include("apps.widget.urls_root")),
    path("api/billing/", include("apps.billing.urls")),
    path("", include("apps.observability.urls")),
]
