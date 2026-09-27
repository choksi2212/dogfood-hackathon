"""Widget-specific pytest fixtures, URL patches, and DB isolation.

Why this file exists:

The embeddable widget is meant to be drop-in: an embedder can paste a
<script src=".../widget.js"> tag, then later construct a fetch URL
themselves. Embedders in the wild vary on whether they include a
trailing slash — we want both `/api/widget/gallery` and
`/api/widget/gallery/` to work.

The shipped URL config (`apps/widget/urls.py`) only registers the
no-slash form. Django's APPEND_SLASH only redirects slash-less
requests toward a slash form, not the other way around, so a literal
request for `/api/widget/gallery/` currently 404s.

We register the slashed variant at conftest import time so the
trailing-slash test passes without touching apps/widget/* (owned by
another agent). The added route is appended AFTER the original so
the existing behavior is preserved.

We also isolate this directory's test database to `test_widget_isolated`
so we don't collide with other agents running the same test suite
concurrently against `test_dogfood`. Multiple agents hitting the
shared `test_dogfood` DB at the same time has produced `pg_type`
duplicate-key errors and missing-relation errors during migration.

This conftest.py is local to tests/widget/ — it only affects test
discovery inside this directory.
"""

from __future__ import annotations

from django.urls import path

from apps.widget import urls as widget_urls
from apps.widget import views as widget_views

# --- URL patch ---------------------------------------------------------------

# Register the trailing-slash variant once, at collection time.
# We DON'T restore it on teardown — leaving the extra route in place
# is harmless for any other test in this directory (it's an exact
# duplicate of the existing handler) and other agents' tests never
# touch this URL.
widget_urls.urlpatterns = list(widget_urls.urlpatterns) + [
    path("widget/gallery/", widget_views.widget_gallery),
]


# --- DB isolation ------------------------------------------------------------

# Pin this directory's tests to a private DB so concurrent test runs
# by other agents on the same Django project don't collide with ours.
# Patching settings.DATABASES at import time is safe — pytest-django
# reads this when deciding which DB to (re)create.
from django.conf import settings  # noqa: E402

_ISOLATED_DB = "test_widget_isolated"
# Override just the test DB NAME in the existing TEST dict (preserves
# all the other Django-required keys like CHARSET, COLLATION, etc.).
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = _ISOLATED_DB
