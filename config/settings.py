"""Django settings for the DOGFOOD 2026 portal.

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
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web"
    ).split(",")
    if h.strip()
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
    "apps.api.apps.ApiConfig",
    "apps.health.apps.HealthConfig",
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

# --- Database ----------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "dogfood"),
        "USER": os.environ.get("POSTGRES_USER", "dogfood"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "dogfood"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
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
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
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
    },
}
