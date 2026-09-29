"""Django settings for the HACK HAMSTER 2026 portal.

All config is env-driven so the same image runs in dev, CI, and the
judge's machine. Defaults are dev-safe; production must override via env.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core --------------------------------------------------------------------

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-secret-key-change-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web").split(",") if h.strip()
]

# --- Apps --------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Local apps
    "apps.accounts.apps.AccountsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.events.apps.EventsConfig",
    "apps.judging.apps.JudgingConfig",
    "apps.teams.apps.TeamsConfig",
    "apps.submissions.apps.SubmissionsConfig",
    "apps.normalization.apps.NormalizationConfig",
    "apps.pairwise.apps.PairwiseConfig",
    "apps.voting.apps.VotingConfig",
    "apps.abuse.apps.AbuseConfig",
    "apps.certificates.apps.CertificatesConfig",
    "apps.widget.apps.WidgetConfig",
    "apps.webhooks.apps.WebhooksConfig",
    "apps.api.apps.ApiConfig",
    "apps.health.apps.HealthConfig",
    "apps.observability.apps.ObservabilityConfig",
    "apps.billing.apps.BillingConfig",
]

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Middleware order matters:
#   1. SecurityMiddleware — sets headers
#   2. Django's SessionMiddleware — needed by django.contrib.messages
#   3. CommonMiddleware — normalizes URLs
#   4. CsrfViewMiddleware — CSRF tokens
#   5. Our SessionMiddleware — resolves cookie → request.user via the
#      hash-stored Session row. Must run AFTER the standard one because it
#      doesn't create request.session.
#   6. MessageMiddleware — flash messages
#   7. AuditMiddleware — appends 401/403 responses to the audit log
#   8. RateLimitMiddleware — last because it short-circuits before view
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.accounts.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.AuditMiddleware",
    "apps.accounts.middleware.RateLimitMiddleware",
    "apps.observability.middleware.RequestCorrelationMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Cache -------------------------------------------------------------------
# Hot public reads (gallery, widget JSON) go through Django's cache
# framework. LocMemCache is in-process — sub-millisecond lookups, no
# network hop. For multi-worker deployments the cache is per-worker;
# for the single-worker dev server this is the fastest possible path.
# Switch to Redis in production by setting ``CACHE_BACKEND`` to
# ``django.core.cache.backends.redis.RedisCache`` and providing a
# ``CACHE_LOCATION`` URL.
CACHES = {
    "default": {
        "BACKEND": os.environ.get("CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"),
        "LOCATION": os.environ.get("CACHE_LOCATION", "hack-hamster-default"),
        "TIMEOUT": int(os.environ.get("CACHE_TIMEOUT", "300")),
        "OPTIONS": {
            "MAX_ENTRIES": int(os.environ.get("CACHE_MAX_ENTRIES", "10000")),
        },
    }
}

# --- Database ----------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "hack-hamster"),
        "USER": os.environ.get("POSTGRES_USER", "hack-hamster"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "hack-hamster"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # ``None`` keeps each connection alive for the lifetime of the
        # worker (psycopg3 + persistent connections are the fastest path
        # for high-throughput back ends). Set to a number of seconds
        # (``CONN_MAX_AGE=60``) to recycle.
        "CONN_MAX_AGE": None
        if os.environ.get("DB_CONN_MAX_AGE", "persistent") == "persistent"
        else int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {
            # Server-side statement timeout — fail fast on runaway
            # queries instead of holding a worker.
            "options": "-c statement_timeout=30s -c idle_in_transaction_session_timeout=60s",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Locale ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static ------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Upload limits -----------------------------------------------------------
# Above the 5 MiB import limit in apps/api/views.py (MAX_IMPORT_BYTES), so
# the import endpoint's own 413 guard fires first and this Django guard
# never turns an oversized import into a generic 400.
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- DRF ---------------------------------------------------------------------

REST_FRAMEWORK = {
    # CookieSessionAuthentication reads request.user that the
    # SessionMiddleware already populated; without it, DRF's request
    # wrapper would store _user=None and crash on .is_authenticated.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CookieSessionAuthentication",
    ],
    # No default permission — every view declares its own. The role
    # isolation matrix is provable precisely because we never inherit
    # "IsAuthenticated" implicitly.
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "apps.api.exceptions.custom_exception_handler",
}

# --- Logging -----------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json").lower()  # "json" or "simple"

_JSON_LOG_RECORD_KEYS = (
    "ts",
    "level",
    "logger",
    "msg",
    "request_id",
    "user_id",
    "method",
    "path",
    "status",
    "duration_ms",
)


def _json_formatter():
    """Late-bound so settings.py doesn't import the app at module load."""
    from apps.observability.logging import JsonFormatter

    return JsonFormatter(_JSON_LOG_RECORD_KEYS)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
        "json": {
            "()": _json_formatter,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.db.backends": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "observability.request": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
