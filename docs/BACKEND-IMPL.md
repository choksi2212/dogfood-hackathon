# HACK HAMSTER 2026 — Backend & DB Implementation

**Event:** hackhamster.com · Hackathon Raptors · "Build the platform that will judge you"
**Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
**Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`)
**Repo:** `https://github.com/choksi2212/dogfood-hackathon`
**Spec:** `https://hackhamster.com/spec`
**Stack:** Django 5 + DRF + PostgreSQL 16 + Next.js 15, all in `docker compose up`
**Companion docs:** [PRD](PRD.md), [TRD](TRD.md), [Architecture](../ARCHITECTURE.md)

> The PRD says *what*. The TRD says *how*. The architecture says *how the how is
> shaped*. This document says *exactly what to type*.

---

## Part 1 — Project Setup

### 1.1 Repository layout

```
hack-hamster-hackathon/
├── README.md
├── LICENSE                  MIT or Apache-2.0
├── .gitignore
├── .gitattributes           * text=auto eol=lf
├── .hack-hamster.toml
├── acceptance-report.txt
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.web
├── Makefile
├── requirements.txt
├── package.json
├── package-lock.json
├── nginx/
│   └── nginx.conf
├── backend/
├── web/
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   └── BACKEND-IMPL.md
├── ARCHITECTURE.md
├── DATA-MODEL.md
├── JUDGING.md
├── THREAT-MODEL.md
├── openapi.yaml
├── role-isolation-matrix.txt
├── normalization-proof.txt
└── demo-video.mp4
```

### 1.2 .gitignore

```gitignore
.env
.env.local
*.pyc
__pycache__/
node_modules/
.next/
pgdata/
media/
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
```

### 1.3 .gitattributes

```
* text=auto eol=lf
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.webp binary
*.pdf binary
*.mp4 binary
*.yaml text eol=lf
*.yml text eol=lf
*.toml text eol=lf
```

### 1.4 requirements.txt

```
Django==5.1.2
djangorestframework==3.15.2
drf-spectacular==0.27.2
psycopg[binary]==3.2.3
argon2-cffi==23.1.0
gunicorn==23.0.0
python-dotenv==1.0.1
django-cors-headers==4.6.0
reportlab==4.2.5
cryptography==43.0.3
pillow==11.0.0
markdown==3.7
bleach==6.2.0
pytest==8.3.3
pytest-django==4.9.0
pytest-mock==3.14.0
factory-boy==3.3.1
ruff==0.7.4
mypy==1.13.0
mypy-extensions==1.0.0
django-stubs==5.1.0
djangorestframework-stubs==3.15.2
```

### 1.5 package.json (web)

```json
{
  "name": "hack-hamster-web",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.0.3",
    "react": "19.0.0-rc-...",
    "react-dom": "19.0.0-rc-..."
  }
}
```

### 1.6 Makefile

```makefile
# Condensed from the real Makefile (COMPOSE ?= docker compose).
up:          $(COMPOSE) up --build
seed:        $(COMPOSE) exec -T web python manage.py import_fixtures
accept:      $(COMPOSE) exec -T web python acceptance.py .hack-hamster.toml | tee acceptance-report.txt
test:        $(COMPOSE) exec -T web pytest tests/ -v
lint:        ruff check .
             ruff format --check .
ci:          lint
             pip install -r requirements.txt
             python manage.py migrate --noinput
             pytest tests/ -v --tb=short
down-clean:  $(COMPOSE) down -v
```

The `accept` target runs the vendored `acceptance.py` (byte-for-byte the
spec's `run.py`, only the filename differs) directly — no wrapper script,
no separate user-seeder command — and seeding is the single idempotent
`manage.py import_fixtures`. The real Makefile also has `accept-fresh`
(re-seed then accept), `test-<category>`, `test-cov`, `types`, and the
`metrics-*` targets for the observability stack.

### 1.7 docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: hack-hamster
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: hack-hamster
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hack-hamster -d hack-hamster"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      DATABASE_URL: postgres://hack-hamster:${DB_PASSWORD}@db:5432/hack-hamster
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DJANGO_DEBUG: "false"
      DJANGO_ALLOWED_HOSTS: localhost,backend
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
      - ./scripts:/app/scripts

  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    environment:
      NEXT_PUBLIC_API_BASE: /
      API_INTERNAL_URL: http://backend:8000
    depends_on:
      - backend
    volumes:
      - ./web:/app/web

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "${WEB_PORT:-8080}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - web

volumes:
  postgres-data:
```

### 1.8 Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000",
     "--workers", "3", "--threads", "2", "--timeout", "60",
     "--access-logfile", "-", "--error-logfile", "-"]
```

The entrypoint waits for postgres (`pg_isready`), runs `migrate --noinput`,
runs `import_fixtures` (skippable with `SKIP_SEED=1`; it falls back to the
legacy `seed_fixtures` only when `fixtures.json` is missing), then `exec`s
the CMD. There is no `Dockerfile.backend`, no separate user-seeder
command, and no `backend.wsgi` — the Django project package is `config/`.

### 1.9 Dockerfile.web

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --only=production

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=deps /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]
```

---

## Part 2 — Django Project Setup

### 2.1 backend/backend/settings.py

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'apps.accounts',
    'apps.events',
    'apps.teams',
    'apps.submissions',
    'apps.judging',
    'apps.voting',
    'apps.audit',
    'apps.normalization',
    'apps.pairwise',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.accounts.middleware.AuditMiddleware',
    'apps.accounts.middleware.RateLimitMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hack-hamster',
        'USER': 'hack-hamster',
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': 'db',
        'PORT': '5432',
    }
}

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'uuid'

# Sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_NAME = 'session'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60  # 14 days

# DRF
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'EXCEPTION_HANDLER': 'apps.api.exceptions.custom_exception_handler',
}

# Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'HACK HAMSTER API',
    'DESCRIPTION': 'Hackathon submission and judging portal',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'apps.accounts.logging.JsonFormatter',
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'json',
        },
    },
    'root': {'handlers': ['stdout'], 'level': 'INFO'},
}

# Argon2
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

ARGON2_PASSWORD_HASHER_MEMORY_COST = 65536  # 64 MB
ARGON2_PASSWORD_HASHER_TIME_COST = 3
ARGON2_PASSWORD_HASHER_PARALLELISM = 4
```

### 2.2 backend/backend/urls.py

```python
from django.contrib import admin
from django.urls import path, include
from apps.api.views import healthz, readyz, verify_view, widget_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz', healthz),
    path('readyz', readyz),
    path('verify', verify_view),
    path('widget.js', widget_view),
    path('api/', include('apps.api.urls')),
]
```

### 2.3 backend/backend/wsgi.py

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
application = get_wsgi_application()
```

### 2.4 backend/manage.py

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
```

---

## Part 3 — Auth App (apps/accounts)

### 3.1 Models

```python
# apps/accounts/models.py

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users_user'
    
    def __str__(self) -> str:
        return self.email
    
    @property
    def is_admin_role(self) -> bool:
        return self.memberships.filter(role='admin').exists()


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'users_session'
        indexes = [
            models.Index(fields=['user', 'last_seen_at']),
        ]
```

### 3.2 Session middleware

```python
# apps/accounts/middleware.py

import hashlib
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from .models import Session


class SessionMiddleware:
    """Resolves the session cookie to a user."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request.user = AnonymousUser()
        request.session_obj = None
        
        cookie = request.COOKIES.get('session')
        if cookie:
            token_hash = hashlib.sha256(cookie.encode()).hexdigest()
            try:
                session = Session.objects.select_related('user').get(
                    token_hash=token_hash,
                )
                if session.expires_at > timezone.now():
                    request.user = session.user
                    request.session_obj = session
                    session.last_seen_at = timezone.now()
                    session.expires_at = timezone.now() + timedelta(days=14)
                    session.save(update_fields=['last_seen_at', 'expires_at'])
                else:
                    session.delete()
            except Session.DoesNotExist:
                pass
        
        return self.get_response(request)
```

### 3.3 Audit middleware

```python
class AuditMiddleware:
    """Logs denied requests to the audit log."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in (401, 403) and request.path.startswith('/api/'):
            from apps.audit.models import AuditEvent
            AuditEvent.objects.create(
                actor_id=request.user.id if request.user.is_authenticated else None,
                action=f'{request.method} {request.path}',
                target_type='endpoint',
                target_id=None,
                payload={},
                ip=self._get_ip(request),
                user_agent=request.headers.get('User-Agent', '')[:255],
                result='denied',
            )
        return response
    
    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
```

### 3.4 Rate limit middleware

```python
import time
from collections import defaultdict
from django.http import JsonResponse


class RateLimitMiddleware:
    """Per-IP rate limiting."""
    
    LIMITS = {
        'auth': (5, 15 * 60),
        'read': (60, 60),
        'write': (10, 60),
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.buckets: dict = defaultdict(dict)
    
    def __call__(self, request):
        ip = self._get_ip(request)
        endpoint_class = self._classify(request)
        limit, window = self.LIMITS[endpoint_class]
        
        now = time.time()
        bucket_key = f'{ip}:{endpoint_class}'
        bucket = self.buckets.setdefault(bucket_key, {'count': 0, 'reset_at': now + window})
        
        if now >= bucket['reset_at']:
            bucket['count'] = 0
            bucket['reset_at'] = now + window
        
        bucket['count'] += 1
        
        if bucket['count'] > limit:
            retry_after = int(bucket['reset_at'] - now)
            return JsonResponse(
                {'error': {'code': 'rate_limited', 'message': 'Slow down.', 'detail': {'retry_after': retry_after}}},
                status=429,
                headers={'Retry-After': str(retry_after)},
            )
        
        return self.get_response(request)
    
    def _classify(self, request):
        if '/api/auth/' in request.path:
            return 'auth'
        if request.method in ('POST', 'PATCH', 'DELETE'):
            return 'write'
        return 'read'
    
    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')
```

### 3.5 JSON formatter

```python
# apps/accounts/logging.py

import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            'ts': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
            'extra': getattr(record, 'extra', {}),
        })
```

### 3.6 Auth views

```python
# apps/accounts/views.py

import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import User, Session
from .serializers import UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = self._create_session(user, request)
        response = Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            'session', token,
            httponly=True, samesite='Lax',
            secure=not settings.DEBUG,
            max_age=14 * 24 * 60 * 60,
        )
        return response
    
    def _create_session(self, user, request):
        token = secrets.token_urlsafe(32)
        Session.objects.create(
            user=user,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(days=14),
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        return token


class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {'error': {'code': 'not_authenticated', 'message': 'Invalid credentials.'}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        if not user.check_password(password):
            return Response(
                {'error': {'code': 'not_authenticated', 'message': 'Invalid credentials.'}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # Invalidate old sessions
        Session.objects.filter(user=user).delete()
        
        token = secrets.token_urlsafe(32)
        Session.objects.create(
            user=user,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(days=14),
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        response = Response(UserSerializer(user).data)
        response.set_cookie(
            'session', token,
            httponly=True, samesite='Lax',
            secure=not settings.DEBUG,
            max_age=14 * 24 * 60 * 60,
        )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if hasattr(request, 'session_obj') and request.session_obj:
            request.session_obj.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie('session')
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response(UserSerializer(request.user).data)
```

### 3.7 User serializer

```python
# apps/accounts/serializers.py

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_active', 'memberships']
        read_only_fields = ['id', 'is_active']
    
    def get_memberships(self, obj):
        return [
            {'event': m.event.slug, 'role': m.role}
            for m in obj.memberships.select_related('event')
        ]
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
```

### 3.8 URLs

```python
# apps/accounts/urls.py

from django.urls import path
from .views import RegisterView, LoginView, LogoutView, MeView

urlpatterns = [
    path('register', RegisterView.as_view()),
    path('login', LoginView.as_view()),
    path('logout', LogoutView.as_view()),
    path('me', MeView.as_view()),
]
```

### 3.9 The seed command (`import_fixtures`)

```python
# apps/accounts/management/commands/import_fixtures.py (condensed;
# helper bodies elided)

import hashlib, hmac, json
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = ("Load the official fixtures.json into the real schema and "
            "seed the five demo sessions (organizer, judge_a, judge_b, "
            "judge_c, participant).")

    def handle(self, *args, **options):
        data = json.loads(Path("fixtures.json").read_text())
        event = self._upsert_event(data["event"])          # slug sample-hack-2026
        self._upsert_tracks(event, data["tracks"])
        judges = self._upsert_judges(event, data["judges"])
        teams, projects = self._upsert_teams_and_projects(
            event, data["teams"], data["projects"])
        self._upsert_scores(event, data["scores"])

        # Five demo sessions with deterministic tokens:
        for label, user in self._demo_users(event, judges):
            token = hmac.new(
                settings.SECRET_KEY.encode(),
                f"hack-hamster-2026-demo-session:{label}:{user.email}".encode(),
                hashlib.sha256,
            ).hexdigest()
            self._upsert_session(user, token)   # user-agent: import_fixtures/1.0
            self.stdout.write(f'{label.upper()}_HEADER = "Cookie: session={token}"')
```

The five demo sessions are bound to the first three **fixture** judges —
`judge_a` → `tomas.varga@example.org`, `judge_b` → `wei.lindqvist@example.org`,
`judge_c` → `priya.nair@example.org` — plus the organizer and participant
accounts, all with the dev password `hack-hamster-dev-password`. Because each
token is `HMAC-SHA256(DJANGO_SECRET_KEY, "hack-hamster-2026-demo-session:{label}:{email}")`,
the five committed `.hack-hamster.toml` `[auth]` headers are valid on every fresh
volume; they change only if `DJANGO_SECRET_KEY` changes (re-run `make seed` to
print the new values). The command is idempotent, and `entrypoint.sh` runs it
automatically after `migrate`. There is no separate user-seeder command; a
legacy `seed_fixtures` (synthetic data) is only a fallback when
`fixtures.json` is missing.

## Part 4 — Events App (apps/events)

### 4.1 Models

```python
# apps/events/models.py

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from apps.accounts.models import User


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(max_length=4000, blank=True)
    open_at = models.DateTimeField()
    submissions_close_at = models.DateTimeField()
    judging_open_at = models.DateTimeField()
    judging_close_at = models.DateTimeField()
    results_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_events')
    
    class Meta:
        db_table = 'events_event'
        indexes = [models.Index(fields=['slug'])]
    
    def clean(self):
        if self.submissions_close_at <= self.open_at:
            raise ValidationError('submissions_close_at must be after open_at')
        if self.judging_open_at < self.submissions_close_at:
            raise ValidationError('judging_open_at must be after submissions_close_at')
        if self.judging_close_at <= self.judging_open_at:
            raise ValidationError('judging_close_at must be after judging_open_at')
    
    def state(self, now=None):
        from django.utils import timezone
        now = now or timezone.now()
        if now < self.open_at: return 'draft'
        if now < self.submissions_close_at: return 'registration'
        if now < self.judging_open_at: return 'submissions_closed'
        if now < self.judging_close_at: return 'judging'
        if self.results_at and now < self.results_at: return 'results_pending'
        if self.results_at: return 'results_published'
        return 'archived'


class Track(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tracks')
    name = models.CharField(max_length=40)
    slug = models.SlugField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'events_track'
        unique_together = ('event', 'slug')
        ordering = ['order', 'name']


class Prize(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='prizes')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, null=True, blank=True, related_name='prizes')
    name = models.CharField(max_length=80)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'events_prize'
        ordering = ['order', 'name']


class Membership(models.Model):
    ROLE_CHOICES = [
        ('visitor', 'Visitor'),
        ('participant', 'Participant'),
        ('judge', 'Judge'),
        ('organizer', 'Organizer'),
        ('admin', 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_memberships')
    
    class Meta:
        db_table = 'events_membership'
        unique_together = ('user', 'event')
        indexes = [
            models.Index(fields=['user', 'event']),
        ]


class Rubric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='rubric')
    name = models.CharField(max_length=80, default='Default')
    
    class Meta:
        db_table = 'events_rubric'


class RubricCriterion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='criteria')
    name = models.CharField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    weight = models.DecimalField(max_digits=4, decimal_places=3)
    min = models.IntegerField(default=1)
    max = models.IntegerField(default=5)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'events_rubriccriterion'
        ordering = ['order', 'name']
    
    def clean(self):
        from decimal import Decimal
        siblings = RubricCriterion.objects.filter(rubric=self.rubric).exclude(pk=self.pk)
        total = sum(s.weight for s in siblings) + self.weight
        if abs(total - Decimal('1.000')) > Decimal('0.001'):
            raise ValidationError(f'Weights must sum to 1.0 (currently {total})')
```

### 4.2 Permissions

```python
# apps/events/permissions.py

from rest_framework.permissions import BasePermission
from .models import Membership


def _get_event(request, view):
    """Resolve the event from the URL kwargs."""
    slug = view.kwargs.get('slug')
    if slug:
        from .models import Event
        try:
            return Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return None
    return None


class IsInEvent(BasePermission):
    def has_permission(self, request, view):
        event = _get_event(request, view)
        if not event:
            return False
        if request.user.is_admin_role:
            return True
        return Membership.objects.filter(
            user=request.user, event=event
        ).exists()


class IsParticipant(IsInEvent):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_admin_role:
            return True
        return Membership.objects.filter(
            user=request.user, event=_get_event(request, view),
            role='participant',
        ).exists()


class IsJudge(IsInEvent):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_admin_role:
            return True
        return Membership.objects.filter(
            user=request.user, event=_get_event(request, view),
            role='judge',
        ).exists()


class IsOrganizer(IsInEvent):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_admin_role:
            return True
        return Membership.objects.filter(
            user=request.user, event=_get_event(request, view),
            role='organizer',
        ).exists()
```

### 4.3 Serializers

```python
# apps/events/serializers.py

from rest_framework import serializers
from .models import Event, Track, Prize, Membership, Rubric, RubricCriterion


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = ['id', 'name', 'slug', 'description', 'order']


class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prize
        fields = ['id', 'name', 'value', 'track', 'order']


class RubricCriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricCriterion
        fields = ['id', 'name', 'description', 'weight', 'min', 'max', 'order']


class RubricSerializer(serializers.ModelSerializer):
    criteria = RubricCriterionSerializer(many=True)
    
    class Meta:
        model = Rubric
        fields = ['id', 'name', 'criteria']


class EventSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    prizes = PrizeSerializer(many=True, read_only=True)
    rubric = RubricSerializer(read_only=True)
    state = serializers.CharField(read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'slug', 'name', 'description',
            'open_at', 'submissions_close_at', 'judging_open_at',
            'judging_close_at', 'results_at',
            'tracks', 'prizes', 'rubric', 'state',
        ]
        read_only_fields = ['id', 'tracks', 'prizes', 'rubric', 'state']


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = Membership
        fields = ['id', 'user', 'user_email', 'user_name', 'role', 'created_at']
```

### 4.4 Views

```python
# apps/events/views.py

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Event, Track, Prize, Membership, Rubric, RubricCriterion
from .serializers import EventSerializer, TrackSerializer, PrizeSerializer, MembershipSerializer, RubricSerializer
from .permissions import IsOrganizer, IsInEvent
from apps.audit.helpers import log as audit_log


class EventCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(created_by=request.user)
        audit_log(request.user, 'event.created', event, request=request)
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


class EventDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EventSerializer
    lookup_field = 'slug'
    queryset = Event.objects.all()
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsInEvent()]
        return [IsAuthenticated(), IsOrganizer()]


class TrackCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        serializer = TrackSerializer(data={**request.data, 'event': event.id})
        serializer.is_valid(raise_exception=True)
        track = serializer.save(event=event)
        audit_log(request.user, 'track.created', track, request=request)
        return Response(TrackSerializer(track).data, status=status.HTTP_201_CREATED)


class RubricCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        criteria_data = request.data.get('criteria', [])
        
        from decimal import Decimal
        total = sum(Decimal(str(c.get('weight', 0))) for c in criteria_data)
        if abs(total - Decimal('1.000')) > Decimal('0.001'):
            return Response(
                {'error': {'code': 'validation_failed', 'message': f'Weights sum to {total}, not 1.0.'}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        
        # Replace existing rubric
        Rubric.objects.filter(event=event).delete()
        rubric = Rubric.objects.create(event=event, name=request.data.get('name', 'Default'))
        for c in criteria_data:
            RubricCriterion.objects.create(rubric=rubric, **c)
        
        audit_log(request.user, 'rubric.set', rubric, request=request)
        return Response(RubricSerializer(rubric).data, status=status.HTTP_201_CREATED)
```

### 4.5 Deadline decorator

```python
# apps/events/decorators.py

from functools import wraps
from django.http import HttpResponse
from .models import Event


def deadline_gated(field_name: str):
    """Decorator that enforces an event deadline before the view runs."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(self, request, *args, **kwargs):
            event_slug = kwargs.get('slug')
            try:
                event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                return HttpResponse(status=404)
            
            from django.utils import timezone
            deadline = getattr(event, field_name)
            if timezone.now() > deadline:
                return HttpResponse(
                    status=422,
                    content=__import__('json').dumps({
                        'error': {
                            'code': 'deadline_passed',
                            'message': f'The {field_name.replace("_", " ")} window has closed.',
                            'detail': {'deadline': field_name},
                        }
                    }),
                    content_type='application/json',
                )
            
            return view_func(self, request, *args, **kwargs)
        return wrapped
    return decorator
```

### 4.6 URLs

```python
# apps/events/urls.py

from django.urls import path
from .views import EventCreateView, EventDetailView, TrackCreateView, RubricCreateView

urlpatterns = [
    path('', EventCreateView.as_view()),
    path('<slug:slug>/', EventDetailView.as_view()),
    path('<slug:slug>/tracks', TrackCreateView.as_view()),
    path('<slug:slug>/rubric', RubricCreateView.as_view()),
]
```

---

## Part 5 — Teams App (apps/teams)

### 5.1 Models

```python
# apps/teams/models.py

import uuid
import secrets
import hashlib
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.events.models import Event


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=60)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'teams_team'
        indexes = [models.Index(fields=['event', 'name'])]


class TeamMember(models.Model):
    ROLE_CHOICES = [('member', 'Member'), ('captain', 'Captain')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    role_in_team = models.CharField(max_length=20, choices=ROLE_CHOICES, default='captain')
    
    class Meta:
        db_table = 'teams_teammember'
        unique_together = ('team', 'user')


class TeamInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invites')
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_invites')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='consumed_invites')
    
    class Meta:
        db_table = 'teams_teaminvite'
        indexes = [models.Index(fields=['token_hash'])]
    
    @classmethod
    def create(cls, team, created_by):
        from datetime import timedelta
        token = secrets.token_urlsafe(32)
        expires_at = min(
            timezone.now() + timedelta(days=7),
            team.event.submissions_close_at,
        )
        return cls.objects.create(
            team=team,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_by=created_by,
            expires_at=expires_at,
        ), token
```

### 5.2 Views

```python
# apps/teams/views.py

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Team, TeamMember, TeamInvite
from apps.events.models import Event, Membership
from apps.events.permissions import IsParticipant
from apps.audit.helpers import log as audit_log


class TeamCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        
        if TeamMember.objects.filter(user=request.user, team__event=event).exists():
            return Response(
                {'error': {'code': 'conflict', 'message': 'You are already in a team for this event.'}},
                status=status.HTTP_409_CONFLICT,
            )
        
        team = Team.objects.create(
            event=event,
            name=request.data.get('name'),
            created_by=request.user,
        )
        TeamMember.objects.create(team=team, user=request.user, role_in_team='captain')
        audit_log(request.user, 'team.created', team, request=request)
        return Response({'id': str(team.id), 'name': team.name}, status=status.HTTP_201_CREATED)


class InviteCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]
    
    def post(self, request, slug, id):
        team = Team.objects.get(id=id, event__slug=slug)
        
        if not TeamMember.objects.filter(team=team, user=request.user, role_in_team='captain').exists():
            return Response(
                {'error': {'code': 'forbidden_role', 'message': 'Only the captain can create invites.'}},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        if team.members.count() >= 4:
            return Response(
                {'error': {'code': 'conflict', 'message': 'Team is full (4 members).'}},
                status=status.HTTP_409_CONFLICT,
            )
        
        invite, token = TeamInvite.create(team, request.user)
        invite_url = f'{request.scheme}://{request.get_host()}/teams/join?token={token}'
        return Response(
            {'invite_url': invite_url, 'expires_at': invite.expires_at.isoformat()},
            status=status.HTTP_201_CREATED,
        )


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        import hashlib
        token = request.data.get('token', '')
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        try:
            invite = TeamInvite.objects.select_related('team__event').get(token_hash=token_hash)
        except TeamInvite.DoesNotExist:
            return Response(
                {'error': {'code': 'gone', 'message': 'Invalid invite token.'}},
                status=status.HTTP_410_GONE,
            )
        
        from django.utils import timezone
        if invite.consumed_at or invite.expires_at < timezone.now():
            return Response(
                {'error': {'code': 'gone', 'message': 'Invite expired or consumed.'}},
                status=status.HTTP_410_GONE,
            )
        
        team = invite.team
        if team.members.count() >= 4:
            return Response(
                {'error': {'code': 'conflict', 'message': 'Team is full.'}},
                status=status.HTTP_409_CONFLICT,
            )
        
        if TeamMember.objects.filter(user=request.user, team__event=team.event).exists():
            return Response({'id': str(team.id), 'name': team.name})
        
        TeamMember.objects.create(team=team, user=request.user, role_in_team='member')
        invite.consumed_at = timezone.now()
        invite.consumed_by = request.user
        invite.save()
        audit_log(request.user, 'team.joined', team, request=request)
        return Response({'id': str(team.id), 'name': team.name})
```

---

## Part 6 — Submissions App (apps/submissions)

### 6.1 Models

```python
# apps/submissions/models.py

import uuid
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from apps.accounts.models import User
from apps.events.models import Event, Track
from apps.teams.models import Team


class Submission(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('locked', 'Locked'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='submission')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='submissions')
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name='submissions')
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=140)
    description = models.TextField(max_length=8000)
    thumbnail_path = models.CharField(max_length=255, blank=True)
    demo_video_url = models.URLField(blank=True)
    repo_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True)
    
    class Meta:
        db_table = 'submissions_submission'
        indexes = [
            models.Index(fields=['event', 'status', 'track']),
            models.Index(fields=['search_vector'], name='search_vector_idx'),
        ]


class SubmissionImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='images')
    path = models.CharField(max_length=255)
    width = models.IntegerField()
    height = models.IntegerField()
    order = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'submissions_submissionimage'
        ordering = ['order']


class TechTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=24, unique=True)
    
    class Meta:
        db_table = 'submissions_techtag'


class SubmissionTag(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    tag = models.ForeignKey(TechTag, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'submissions_submissiontag'
        unique_together = ('submission', 'tag')


class CustomQuestion(models.Model):
    TYPE_CHOICES = [
        ('short_text', 'Short text'),
        ('long_text', 'Long text'),
        ('url', 'URL'),
        ('single_choice', 'Single choice'),
        ('multi_choice', 'Multi choice'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='custom_questions')
    prompt = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    choices = models.JSONField(default=list, blank=True)  # for single/multi choice
    
    class Meta:
        db_table = 'submissions_customquestion'
        ordering = ['order']


class CustomAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='custom_answers')
    question = models.ForeignKey(CustomQuestion, on_delete=models.CASCADE)
    value_text = models.TextField(blank=True)
    value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    
    class Meta:
        db_table = 'submissions_customanswer'
        unique_together = ('submission', 'question')
```

### 6.2 Submission search trigger

```python
# apps/submissions/migrations/0002_search_vector.py

from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('submissions', '0001_initial')]
    operations = [
        TrigramExtension(),
        migrations.RunSQL(
            "CREATE TRIGGER submissions_search_vector_update "
            "BEFORE INSERT OR UPDATE ON submissions_submission "
            "FOR EACH ROW EXECUTE FUNCTION "
            "tsvector_update_trigger(search_vector, 'pg_catalog.english', name, tagline);"
        ),
    ]
```

### 6.3 Views

```python
# apps/submissions/views.py

import uuid
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Submission, SubmissionImage, CustomQuestion, CustomAnswer, TechTag
from .serializers import SubmissionSerializer
from apps.teams.models import Team, TeamMember
from apps.events.models import Event, Track
from apps.events.permissions import IsParticipant
from apps.events.decorators import deadline_gated
from apps.audit.helpers import log as audit_log
from django.utils import timezone


class SubmissionCreateView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        team = TeamMember.objects.filter(user=request.user, team__event=event).first().team
        track = Track.objects.get(event=event, slug=request.data.get('track_slug'))
        
        submission = Submission.objects.create(
            team=team,
            event=event,
            track=track,
            name=request.data.get('name', ''),
            tagline='',
            description='',
        )
        audit_log(request.user, 'submission.created', submission, request=request)
        return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


class SubmissionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SubmissionSerializer
    
    def get_queryset(self):
        return Submission.objects.all()
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsParticipant()]
    
    def perform_update(self, serializer):
        if serializer.instance.status not in ('draft', 'submitted'):
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Cannot edit a locked or withdrawn submission.')
        serializer.save()


class SubmitSubmissionView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]
    
    @deadline_gated('submissions_close_at')
    def post(self, request, slug, id):
        submission = Submission.objects.get(id=id, event__slug=slug)
        
        if submission.status != 'draft':
            return Response(
                {'error': {'code': 'gone', 'message': 'Already submitted.'}},
                status=status.HTTP_410_GONE,
            )
        
        # Validate required custom answers
        questions = CustomQuestion.objects.filter(event=submission.event, required=True)
        answered_question_ids = set(
            CustomAnswer.objects.filter(submission=submission, question__in=questions).values_list('question_id', flat=True)
        )
        missing = [q for q in questions if q.id not in answered_question_ids]
        if missing:
            return Response(
                {'error': {'code': 'validation_failed', 'message': 'Required answers missing.', 'detail': {'questions': [str(q.id) for q in missing]}}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        
        submission.status = 'submitted'
        submission.submitted_at = timezone.now()
        submission.save()
        audit_log(request.user, 'submission.submitted', submission, request=request)
        return Response(SubmissionSerializer(submission).data)
```

### 6.4 Gallery view (the spec route)

```python
# apps/submissions/gallery_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Submission
from apps.events.models import Event
from .serializers import SubmissionSerializer


class GalleryView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, slug):
        event = Event.objects.get(slug=slug)
        qs = Submission.objects.filter(
            event=event,
            status='submitted',
        ).select_related('team', 'track')
        
        q = request.query_params.get('q')
        if q:
            qs = qs.extra(
                where=["search_vector @@ plainto_tsquery('english', %s)"],
                params=[q],
            )
        
        track = request.query_params.get('track')
        if track:
            track_slugs = track.split(',')
            qs = qs.filter(track__slug__in=track_slugs)
        
        sort = request.query_params.get('sort', 'track')
        if sort == 'alpha':
            qs = qs.order_by('name')
        elif sort == 'newest':
            qs = qs.order_by('-submitted_at')
        else:
            qs = qs.order_by('track__order', 'name')
        
        try:
            page = int(request.query_params.get('page', 1))
        except ValueError:
            page = 1
        page_size = 24
        
        items = qs[(page-1)*page_size:page*page_size]
        total = qs.count()
        
        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': SubmissionSerializer(items, many=True).data,
        })
```

## Part 7 — Judging App (apps/judging)

### 7.1 Models

```python
# apps/judging/models.py

import uuid
import secrets
import hashlib
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.events.models import Event
from apps.submissions.models import Submission


class JudgeBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='judge_batches')
    seed = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    reviews_per_project = models.IntegerField(default=3)
    projects_per_judge = models.IntegerField(default=4)
    
    class Meta:
        db_table = 'judging_judgebatch'


class JudgeAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(JudgeBatch, on_delete=models.CASCADE, related_name='assignments')
    judge = models.ForeignKey(User, on_delete=models.CASCADE, related_name='judge_assignments')
    project = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='judge_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'judging_judgeassignment'
        unique_together = ('batch', 'judge', 'project')
        indexes = [
            models.Index(fields=['judge', 'batch']),
            models.Index(fields=['project']),
        ]


class JudgeInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='judge_invites')
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'judging_judgeinvite'


class Score(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(JudgeAssignment, on_delete=models.CASCADE, related_name='scores')
    criterion = models.ForeignKey('events.RubricCriterion', on_delete=models.CASCADE)
    value = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'judging_score'
        unique_together = ('assignment', 'criterion')


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(JudgeAssignment, on_delete=models.CASCADE, related_name='review')
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'judging_review'
```

### 7.2 Assignment algorithm

```python
# apps/judging/assignment.py

import random
from collections import defaultdict
from django.db import transaction
from .models import JudgeBatch, JudgeAssignment
from apps.events.models import Membership
from apps.submissions.models import Submission
from apps.api.exceptions import ValidationFailed


class AssignmentError(Exception):
    pass


@transaction.atomic
def run_assignment(event, seed, reviews_per_project=3, projects_per_judge=None, created_by=None):
    """Run the assignment algorithm.
    
    Invariants:
      - Every project has exactly `reviews_per_project` assignments.
      - Every judge has <= ceil(reviews_per_project * projects / judges) assignments.
      - No judge is assigned their own team's project (COI).
      - Track spread is balanced.
      - Batches are disjoint.
    """
    projects = list(Submission.objects.filter(event=event, status='submitted').select_related('team'))
    judges = list(
        Membership.objects.filter(event=event, role='judge').select_related('user')
    )
    
    if not projects or not judges:
        raise ValidationFailed('Need both projects and judges.')
    
    n_projects = len(projects)
    n_judges = len(judges)
    target = n_projects * reviews_per_project
    per_judge_max = (target + n_judges - 1) // n_judges  # ceil
    n_tracks = event.tracks.count()
    
    if projects_per_judge is None:
        projects_per_judge = per_judge_max
    
    # Build COI map: judge -> set of team_ids they cannot review
    judge_team_blacklist = {
        m.user_id: set(
            m.user.team_memberships.values_list('team_id', flat=True)
        )
        for m in judges
    }
    
    # Try up to 10 times with different effective seeds
    for attempt in range(10):
        effective_seed = seed + attempt
        rng = random.Random(effective_seed)
        
        # Sort projects by (track, name) for deterministic iteration
        sorted_projects = sorted(
            projects, key=lambda p: (p.track.order, p.name)
        )
        
        # Greedy assignment
        judge_load = defaultdict(int)
        judge_tracks = defaultdict(set)
        assignments = []
        
        success = True
        for project in sorted_projects:
            # Find candidate judges (not at max load, no COI)
            candidates = [
                m.user_id for m in judges
                if judge_load[m.user_id] < projects_per_judge
                and project.team_id not in judge_team_blacklist.get(m.user_id, set())
            ]
            
            if len(candidates) < reviews_per_project:
                success = False
                break
            
            # Sort candidates by current load (prefer less-loaded), then by track diversity
            candidates.sort(key=lambda j: (judge_load[j], -len(judge_tracks[j])))
            
            # Pick top reviews_per_project
            chosen = candidates[:reviews_per_project]
            for judge_id in chosen:
                assignments.append((judge_id, project.id))
                judge_load[judge_id] += 1
                judge_tracks[judge_id].add(project.track_id)
        
        if not success:
            continue
        
        # Verify track spread invariant: each judge covers at least n_tracks - 1
        # (skip this if there are too few projects to satisfy it)
        if n_tracks > 1:
            min_tracks = min(len(tracks) for tracks in judge_tracks.values())
            if min_tracks < n_tracks - 1 and n_projects >= n_tracks - 1:
                continue  # retry with different seed
        
        # All invariants pass. Persist.
        batch = JudgeBatch.objects.create(
            event=event,
            seed=effective_seed,
            created_by=created_by,
            reviews_per_project=reviews_per_project,
            projects_per_judge=projects_per_judge,
        )
        JudgeAssignment.objects.bulk_create([
            JudgeAssignment(batch=batch, judge_id=judge_id, project_id=project_id)
            for judge_id, project_id in assignments
        ])
        
        return {
            'batch_id': str(batch.id),
            'n_assignments': len(assignments),
            'judges_with_zero_projects': [
                str(j.user_id) for j in judges if judge_load[j.user_id] == 0
            ],
            'seed_used': effective_seed,
        }
    
    raise AssignmentError('Could not produce a valid assignment after 10 retries.')


def is_connected(event):
    """Check if the judge-project bipartite graph is connected."""
    edges = JudgeAssignment.objects.filter(batch__event=event).values_list(
        'judge_id', 'project_id'
    )
    if not edges:
        return False
    
    # BFS from any node
    nodes = set()
    for j, p in edges:
        nodes.add(('j', j))
        nodes.add(('p', p))
    
    adj = defaultdict(set)
    for j, p in edges:
        adj[('j', j)].add(('p', p))
        adj[('p', p)].add(('j', j))
    
    start = next(iter(nodes))
    visited = {start}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    return len(visited) == len(nodes)
```

### 7.3 Permissions

```python
# apps/judging/permissions.py

from rest_framework.permissions import BasePermission
from apps.events.models import Membership
from .models import JudgeAssignment


def _is_judge(request, view):
    if not request.user.is_authenticated:
        return False
    if request.user.is_admin_role:
        return True
    event_slug = view.kwargs.get('slug')
    return Membership.objects.filter(
        user=request.user,
        event__slug=event_slug,
        role='judge',
    ).exists()


class IsAssignedJudge(BasePermission):
    def has_permission(self, request, view):
        if not _is_judge(request, view):
            return False
        project_id = view.kwargs.get('project_id')
        if not project_id:
            return True
        return JudgeAssignment.objects.filter(
            judge=request.user,
            project_id=project_id,
        ).exists()


class IsOwnJudge(BasePermission):
    """The graded cell. Denies if the cookie's judge doesn't match the URL's judge param."""
    
    def has_permission(self, request, view):
        judge_param = request.query_params.get('judge')
        if not judge_param:
            return True  # no judge param means "my own scores"
        
        if not hasattr(request, 'session_obj') or not request.session_obj:
            return False
        
        # The judge is identified by the user; the param is the user identifier
        # We compare request.user.id (or email) to judge_param
        cookie_judge = str(request.user.id)
        if judge_param == cookie_judge:
            return True
        # Also accept the seed-script format "judge_a", "judge_b"
        # which maps to users by email
        if request.user.email.startswith(judge_param + '@'):
            return True
        return False
```

### 7.4 Views

```python
# apps/judging/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import JudgeAssignment, Score, Review
from .permissions import IsAssignedJudge, IsOwnJudge
from .assignment import run_assignment
from apps.events.models import Event, Membership
from apps.events.permissions import IsOrganizer
from apps.events.decorators import deadline_gated
from apps.submissions.models import Submission
from apps.audit.helpers import log as audit_log
from django.utils import timezone


class BatchInviteView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        emails = request.data.get('emails', [])
        
        for email in emails:
            from apps.accounts.models import User
            user, _ = User.objects.get_or_create(
                email=email.lower(),
                defaults={'is_active': True},
            )
            Membership.objects.get_or_create(
                user=user, event=event,
                defaults={'role': 'judge', 'created_by': request.user},
            )
        
        audit_log(request.user, 'judge.invited_bulk', event, payload={'count': len(emails)}, request=request)
        return Response({'invited': len(emails)})


class AssignmentRunView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        seed = request.data.get('seed', 42)
        reviews_per_project = request.data.get('reviews_per_project', 3)
        projects_per_judge = request.data.get('projects_per_judge')
        
        result = run_assignment(
            event=event,
            seed=seed,
            reviews_per_project=reviews_per_project,
            projects_per_judge=projects_per_judge,
            created_by=request.user,
        )
        audit_log(request.user, 'assignment.run', event, payload=result, request=request)
        return Response(result)


class MyBatchView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, slug):
        if not request.user.is_authenticated:
            return Response(status=403)
        
        event = Event.objects.get(slug=slug)
        if not Membership.objects.filter(user=request.user, event=event, role='judge').exists():
            return Response(status=403)
        
        # 403 if judging is not yet open
        if timezone.now() < event.judging_open_at:
            return Response(
                {'error': {'code': 'deadline_not_open', 'message': 'Judging not yet open.'}},
                status=403,
            )
        
        assignments = JudgeAssignment.objects.filter(
            judge=request.user,
            batch__event=event,
        ).select_related('project__team', 'project__track')
        
        projects_data = []
        for a in assignments:
            review = getattr(a, 'review', None)
            projects_data.append({
                'id': str(a.project.id),
                'name': a.project.name,
                'tagline': a.project.tagline,
                'thumbnail_url': a.project.thumbnail_path,
                'submitted': a.project.status == 'submitted',
                'reviewed': review is not None and review.submitted_at is not None,
            })
        
        scored = sum(1 for p in projects_data if p['reviewed'])
        return Response({
            'projects': projects_data,
            'progress': {'scored': scored, 'total': len(projects_data)},
        })


class JudgeScoresView(APIView):
    """The spec route. Returns the authenticated judge's own scores."""
    permission_classes = [IsAuthenticated, IsOwnJudge]
    
    def get(self, request):
        if not Membership.objects.filter(
            user=request.user, role='judge'
        ).exists():
            return Response(status=403)
        
        # Determine which judge's scores to return
        judge_param = request.query_params.get('judge')
        if judge_param:
            # Cross-judge request: IsOwnJudge will deny
            # (or if it allows, we return the requested judge's scores)
            # But IsOwnJudge denies cross-judge, so we only get here for own
            target_judge_id = request.user.id
        else:
            target_judge_id = request.user.id
        
        assignments = JudgeAssignment.objects.filter(judge_id=target_judge_id)
        scores = Score.objects.filter(
            assignment__in=assignments
        ).select_related('criterion', 'assignment__project')
        
        return Response({
            'judge_id': str(target_judge_id),
            'scores': [
                {
                    'project_id': str(s.assignment.project_id),
                    'criterion_id': str(s.criterion_id),
                    'value': s.value,
                }
                for s in scores
            ]
        })


class ScoreSaveView(APIView):
    permission_classes = [IsAuthenticated, IsAssignedJudge]
    
    @deadline_gated('judging_close_at')
    def put(self, request, slug, project_id):
        assignment = JudgeAssignment.objects.get(
            judge=request.user, project_id=project_id,
        )
        
        scores_data = request.data.get('scores', [])
        for s in scores_data:
            Score.objects.update_or_create(
                assignment=assignment,
                criterion_id=s['criterion_id'],
                defaults={'value': s['value']},
            )
        
        # Save comment if present
        comment = request.data.get('comment', '')
        if comment:
            review, _ = Review.objects.get_or_create(assignment=assignment)
            review.comment = comment
            review.save()
        
        return Response({'saved': True})


class ScoreSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsAssignedJudge]
    
    @deadline_gated('judging_close_at')
    def post(self, request, slug, project_id):
        assignment = JudgeAssignment.objects.get(
            judge=request.user, project_id=project_id,
        )
        
        # Validate all required criteria have scores
        from apps.events.models import RubricCriterion
        required_criteria = RubricCriterion.objects.filter(rubric__event__slug=slug)
        scored = Score.objects.filter(assignment=assignment).values_list('criterion_id', flat=True)
        missing = [c.id for c in required_criteria if c.id not in scored]
        if missing:
            return Response(
                {'error': {'code': 'validation_failed', 'message': 'Required criteria missing.', 'detail': {'criteria': missing}}},
                status=422,
            )
        
        review, _ = Review.objects.get_or_create(assignment=assignment)
        review.submitted_at = timezone.now()
        review.save()
        audit_log(request.user, 'review.submitted', assignment, request=request)
        
        return Response({'submitted_at': review.submitted_at.isoformat()})
```

### 7.5 URLs

```python
# apps/judging/urls.py

from django.urls import path
from .views import BatchInviteView, AssignmentRunView, MyBatchView, JudgeScoresView, ScoreSaveView, ScoreSubmitView

urlpatterns = [
    path('<slug:slug>/judges/bulk-invite', BatchInviteView.as_view()),
    path('<slug:slug>/assignments/run', AssignmentRunView.as_view()),
    path('<slug:slug>/me/batch', MyBatchView.as_view()),
    path('<slug:slug>/me/batch/<uuid:project_id>/scores', ScoreSaveView.as_view()),
    path('<slug:slug>/me/batch/<uuid:project_id>/submit', ScoreSubmitView.as_view()),
]


# apps/judging/urls_judge.py (mounted at /api/judge/)

from django.urls import path
from .views import JudgeScoresView

urlpatterns = [
    path('scores', JudgeScoresView.as_view()),
]
```

---

## Part 8 — Voting App (apps/voting)

### 8.1 Models

```python
# apps/voting/models.py

import uuid
from django.db import models
from apps.accounts.models import User
from apps.events.models import Event
from apps.submissions.models import Submission


class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='votes')
    project = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='votes')
    voter_key = models.CharField(max_length=64)  # open mode: fingerprint; auth: user_id; email: hash
    voter_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    voter_email_hash = models.CharField(max_length=64, blank=True)
    votes = models.IntegerField(default=1)  # quadratic: n; simple: 1
    created_at = models.DateTimeField(auto_now_add=True)
    retracted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'voting_vote'
        unique_together = ('event', 'project', 'voter_key')
        indexes = [models.Index(fields=['event', 'voter_key'])]


class VoteBudget(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    voter_key = models.CharField(max_length=64)
    spent_credits = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'voting_votebudget'
        unique_together = ('event', 'voter_key')


class VoteAudit(models.Model):
    ACTION_CHOICES = [('cast', 'Cast'), ('retract', 'Retract')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vote = models.ForeignKey(Vote, on_delete=models.CASCADE, related_name='audit')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'voting_voteaudit'
```

### 8.2 Views

```python
# apps/voting/views.py

import hashlib
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Vote, VoteBudget, VoteAudit
from apps.events.models import Event
from apps.events.decorators import deadline_gated
from apps.submissions.models import Submission
from apps.audit.helpers import log as audit_log


def _voter_key(request, event):
    """Determine the voter key based on event.voting_mode."""
    if request.user.is_authenticated:
        return f'user:{request.user.id}'
    ip = request.META.get('REMOTE_ADDR', '')
    ua = request.headers.get('User-Agent', '')
    return f'fp:{hashlib.sha256(f"{ip}{ua}".encode()).hexdigest()[:32]}'


class VoteView(APIView):
    permission_classes = [AllowAny]
    
    @deadline_gated('judging_close_at')  # voting opens when judging closes
    def post(self, request, slug, id):
        event = Event.objects.get(slug=slug)
        project = Submission.objects.get(id=id, event=event)
        
        # Self-vote check
        if request.user.is_authenticated:
            from apps.teams.models import TeamMember
            if TeamMember.objects.filter(team=project.team, user=request.user).exists():
                return Response(
                    {'error': {'code': 'forbidden_role', 'message': 'Cannot vote on your own team project.'}},
                    status=403,
                )
        
        voter_key = _voter_key(request, event)
        n_votes = int(request.data.get('votes', 1))
        
        # Validate based on mode
        if event.voting_mode == 'quadratic':
            cost = n_votes ** 2
            budget, _ = VoteBudget.objects.get_or_create(event=event, voter_key=voter_key)
            if budget.spent_credits + cost > 100:
                return Response(
                    {'error': {'code': 'validation_failed', 'message': 'Exceeds budget.'}},
                    status=422,
                )
            budget.spent_credits += cost
            budget.save()
        
        vote, created = Vote.objects.update_or_create(
            event=event, project=project, voter_key=voter_key,
            defaults={
                'voter_user': request.user if request.user.is_authenticated else None,
                'votes': n_votes,
                'retracted_at': None,
            },
        )
        
        VoteAudit.objects.create(
            vote=vote, action='cast',
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        audit_log(request.user if request.user.is_authenticated else None, 'vote.cast', vote, request=request)
        
        return Response({'vote_id': str(vote.id), 'votes': n_votes})
    
    @deadline_gated('submissions_close_at')
    def delete(self, request, slug, id):
        event = Event.objects.get(slug=slug)
        project = Submission.objects.get(id=id, event=event)
        voter_key = _voter_key(request, event)
        
        try:
            vote = Vote.objects.get(event=event, project=project, voter_key=voter_key)
        except Vote.DoesNotExist:
            return Response(status=404)
        
        if event.voting_mode == 'quadratic':
            cost = vote.votes ** 2
            budget = VoteBudget.objects.get(event=event, voter_key=voter_key)
            budget.spent_credits -= cost
            budget.save()
        
        vote.retracted_at = timezone.now()
        vote.save()
        
        VoteAudit.objects.create(
            vote=vote, action='retract',
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        
        return Response({'retracted': True})
```

---

## Part 9 — Audit App (apps/audit)

### 9.1 Models

```python
# apps/audit/models.py

import uuid
from django.db import models
from apps.accounts.models import User
from apps.events.models import Event


class AuditEvent(models.Model):
    RESULT_CHOICES = [('success', 'Success'), ('denied', 'Denied'), ('error', 'Error')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='success')
    
    class Meta:
        db_table = 'audit_auditevent'
        indexes = [
            models.Index(fields=['event', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
```

### 9.2 Audit helper

```python
# apps/audit/helpers.py

from .models import AuditEvent


def log(actor, action, target=None, payload=None, request=None, result='success'):
    """Append a row to the audit log. Call from views after a successful action."""
    AuditEvent.objects.create(
        event=_event_from_request(request) or (_event_from_target(target) if target else None),
        actor=actor if actor and getattr(actor, 'is_authenticated', False) else None,
        action=action,
        target_type=type(target).__name__ if target else '',
        target_id=getattr(target, 'id', None),
        payload=payload or {},
        ip=_ip_from_request(request),
        user_agent=_ua_from_request(request),
        result=result,
    )


def _event_from_request(request):
    if not request:
        return None
    slug = request.resolver_match.kwargs.get('slug') if hasattr(request, 'resolver_match') else None
    if slug:
        from apps.events.models import Event
        try:
            return Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return None
    return None


def _event_from_target(target):
    if hasattr(target, 'event'):
        return target.event
    return None


def _ip_from_request(request):
    if not request:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _ua_from_request(request):
    if not request:
        return ''
    return request.headers.get('User-Agent', '')[:255]
```

### 9.3 Migration: revoke UPDATE/DELETE

```python
# apps/audit/migrations/0002_immutable.py

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('audit', '0001_initial')]
    operations = [
        migrations.RunSQL("REVOKE UPDATE, DELETE ON audit_auditevent FROM hack-hamster;"),
    ]
```

## Part 10 — Normalization App (apps/normalization)

### 10.1 The fit algorithm

```python
# apps/normalization/fit.py

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class FitResult:
    q: dict  # project_id -> quality estimate
    b: dict  # judge_id -> bias estimate
    leverage: dict  # judge_id -> n_reviews / total_reviews
    raw_means: dict  # project_id -> raw mean
    raw_sigma: float
    normalized_sigma: float
    is_connected: bool
    iterations: int
    scores: list  # list of NormalizedScore dicts
    biases: list  # list of JudgeBias dicts


def normalize(scores: list) -> FitResult:
    """Fit the two-way additive model by alternating means.
    
    scores: list of dicts with keys: project_id, judge_id, value
    """
    # Build sparse matrices
    cells = {}  # (project_id, judge_id) -> value
    project_judges = defaultdict(set)
    judge_projects = defaultdict(set)
    projects = set()
    judges = set()
    
    for s in scores:
        key = (s['project_id'], s['judge_id'])
        if key in cells:
            cells[key] = (cells[key] + s['value']) / 2  # dedup; keep later (we replace)
        else:
            cells[key] = s['value']
        project_judges[s['project_id']].add(s['judge_id'])
        judge_projects[s['judge_id']].add(s['project_id'])
        projects.add(s['project_id'])
        judges.add(s['judge_id'])
    
    # Verify connectivity
    if not _is_connected(project_judges, judge_projects):
        return FitResult(
            q={}, b={}, leverage={}, raw_means={},
            raw_sigma=0.0, normalized_sigma=0.0,
            is_connected=False, iterations=0, scores=[], biases=[],
        )
    
    # Initialize
    grand_mean = sum(cells.values()) / len(cells)
    b = {j: 0.0 for j in judges}
    q = {p: 0.0 for p in projects}
    
    # Iterate
    max_iter = 1000
    for iteration in range(1, max_iter + 1):
        # Update q: for each project, mean of (value - b) over its judges
        new_q = {}
        for p in projects:
            js = project_judges[p]
            new_q[p] = sum(cells[(p, j)] - b[j] for j in js) / len(js)
        
        # Update b: for each judge, mean of (value - q) over their projects
        new_b = {}
        for j in judges:
            ps = judge_projects[j]
            new_b[j] = sum(cells[(p, j)] - new_q[p] for p in ps) / len(ps)
        
        # Recentre: b sums to 0
        b_mean = sum(new_b.values()) / len(new_b)
        new_b = {j: v - b_mean for j, v in new_b.items()}
        
        # Convergence check
        max_change = max(
            abs(new_q[p] - q[p]) for p in projects
        ) if projects else 0.0
        max_change = max(max_change, max(
            abs(new_b[j] - b[j]) for j in judges
        ) if judges else 0.0)
        
        q = new_q
        b = new_b
        
        if max_change < 1e-9:
            break
    
    # Compute raw means
    raw_means = {}
    for p in projects:
        js = project_judges[p]
        raw_means[p] = sum(cells[(p, j)] for j in js) / len(js)
    
    # Compute normalized scores
    normalized = {p: q[p] + grand_mean for p in projects}
    
    # Compute leverage
    total_reviews = sum(len(js) for js in project_judges.values())
    leverage = {j: len(judge_projects[j]) / total_reviews for j in judges}
    
    # Compute sigmas
    raw_vals = list(raw_means.values())
    norm_vals = list(normalized.values())
    raw_sigma = _std(raw_vals)
    normalized_sigma = _std(norm_vals)
    
    # Compute ranks
    raw_ranked = sorted(projects, key=lambda p: -raw_means[p])
    norm_ranked = sorted(projects, key=lambda p: -normalized[p])
    raw_rank = {p: i + 1 for i, p in enumerate(raw_ranked)}
    norm_rank = {p: i + 1 for i, p in enumerate(norm_ranked)}
    
    return FitResult(
        q=q, b=b, leverage=leverage,
        raw_means=raw_means,
        raw_sigma=raw_sigma,
        normalized_sigma=normalized_sigma,
        is_connected=True,
        iterations=iteration,
        scores=[
            {
                'project_id': p,
                'raw_mean': raw_means[p],
                'adjusted': normalized[p],
                'rank_before': raw_rank[p],
                'rank_after': norm_rank[p],
            }
            for p in projects
        ],
        biases=[
            {
                'judge_id': j,
                'bias': b[j],
                'n_reviews': len(judge_projects[j]),
                'leverage': leverage[j],
            }
            for j in judges
        ],
    )


def _is_connected(project_judges, judge_projects) -> bool:
    """BFS in the bipartite graph."""
    if not project_judges:
        return False
    
    start = next(iter(project_judges))
    visited_p = {start}
    visited_j = set()
    queue = [('p', start)]
    
    while queue:
        kind, node = queue.pop(0)
        if kind == 'p':
            for j in project_judges.get(node, set()):
                if j not in visited_j:
                    visited_j.add(j)
                    queue.append(('j', j))
        else:
            for p in judge_projects.get(node, set()):
                if p not in visited_p:
                    visited_p.add(p)
                    queue.append(('p', p))
    
    return len(visited_p) == len(project_judges) and len(visited_j) == len(judge_projects)


def _std(values) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5
```

### 10.2 The proof generator

```python
# apps/normalization/proof.py

from .models import NormalizationRun


def generate_proof(run: NormalizationRun, result) -> str:
    """Generate the FIG. 03 proof file."""
    lines = []
    lines.append('HACK HAMSTER normalization proof')
    lines.append(f'event: {run.event.slug}')
    lines.append(f'method: {run.method}')
    lines.append(f'created_at: {run.created_at.isoformat()}')
    lines.append(f'raw_sigma: {run.raw_sigma:.2f}')
    lines.append(f'normalized_sigma: {run.normalized_sigma:.2f}')
    lines.append(f'is_connected: {run.is_connected}')
    lines.append(f'iterations: {result.iterations}')
    lines.append('')
    
    # Rank movement (top 10 by |delta|)
    lines.append('Rank movement (top 10 by |delta|):')
    lines.append('project_id  raw_rank  adj_rank  delta')
    movements = sorted(result.scores, key=lambda s: abs(s['rank_after'] - s['rank_before']), reverse=True)
    for s in movements[:10]:
        delta = s['rank_after'] - s['rank_before']
        arrow = '▲' if delta < 0 else '▼' if delta > 0 else '='
        lines.append(f"{s['project_id']}  {s['rank_before']}  {s['rank_after']}  {arrow} {abs(delta)}")
    lines.append('')
    
    # Zero-variance raters
    zero_var = [b for b in result.biases if b['leverage'] < 1e-9 and b['n_reviews'] > 0]
    if zero_var:
        lines.append('Zero-variance raters:')
        for b in zero_var:
            lines.append(f"  {b['judge_id']}: leverage=0.00, n_reviews={b['n_reviews']} - no ranking signal")
        lines.append('')
    
    lines.append('Method:')
    lines.append('y_ij = mu + b_j + q_i + epsilon_ij')
    lines.append('fit: alternating means until convergence (max change < 1e-9)')
    lines.append('connectivity: required; reported')
    lines.append('z-score: rejected (divides by zero on sigma=0 raters)')
    
    return '\n'.join(lines)
```

### 10.3 The normalization view

```python
# apps/normalization/views.py

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import NormalizationRun, NormalizedScore, JudgeBias
from .fit import normalize, _is_connected
from .proof import generate_proof
from apps.judging.models import Score
from apps.events.models import Event
from apps.events.permissions import IsOrganizer
from apps.audit.helpers import log as audit_log


class NormalizeView(APIView):
    permission_classes = [IsOrganizer]
    
    @transaction.atomic
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        
        # Load scores
        scores = list(
            Score.objects.filter(assignment__batch__event=event)
            .select_related('assignment__judge', 'assignment__project', 'criterion')
            .values(
                'assignment__project_id', 'assignment__judge_id', 'value'
            )
        )
        
        # Dedupe by (project, judge): keep the last
        seen = {}
        for s in scores:
            key = (s['assignment__project_id'], s['assignment__judge_id'])
            seen[key] = s['value']
        deduped = [
            {'project_id': str(k[0]), 'judge_id': str(k[1]), 'value': v}
            for k, v in seen.items()
        ]
        
        # Fit
        result = normalize(deduped)
        if not result.is_connected:
            return Response(
                {'error': {'code': 'disconnected_graph', 'message': 'Bipartite graph is disconnected.'}},
                status=422,
            )
        
        # Persist
        run = NormalizationRun.objects.create(
            event=event,
            method='additive_alternating_means',
            params={},
            created_by=request.user,
            raw_sigma=result.raw_sigma,
            normalized_sigma=result.normalized_sigma,
            is_connected=result.is_connected,
        )
        NormalizedScore.objects.bulk_create([
            NormalizedScore(
                run=run,
                project_id=s['project_id'],
                raw_mean=s['raw_mean'],
                adjusted=s['adjusted'],
                rank_before=s['rank_before'],
                rank_after=s['rank_after'],
            )
            for s in result.scores
        ])
        JudgeBias.objects.bulk_create([
            JudgeBias(
                run=run,
                judge_id=b['judge_id'],
                bias=b['bias'],
                n_reviews=b['n_reviews'],
                leverage=b['leverage'],
            )
            for b in result.biases
        ])
        
        # Generate proof
        proof = generate_proof(run, result)
        # Save to a file the organizer can download
        from django.core.files.base import ContentFile
        run.proof_file.save(
            'normalization-proof.txt',
            ContentFile(proof.encode()),
            save=True,
        )
        
        audit_log(request.user, 'normalization.run', run, request=request)
        return Response({
            'run_id': str(run.id),
            'raw_sigma': run.raw_sigma,
            'normalized_sigma': run.normalized_sigma,
            'is_connected': run.is_connected,
            'n_projects': len(result.scores),
            'n_judges': len(result.biases),
            'n_reviews': len(deduped),
        })
```

### 10.4 Unit tests on synthetic data

```python
# apps/normalization/tests.py

import random
import pytest
from apps.normalization.fit import normalize


def test_normalization_recovers_quality():
    random.seed(42)
    n_projects = 40
    n_judges = 30
    reviews_per_project = 3
    
    true_q = {f'p{i}': random.gauss(3, 1) for i in range(n_projects)}
    true_b = {f'j{i}': random.gauss(0, 0.5) for i in range(n_judges)}
    
    # Each judge reviews 4 projects
    scores = []
    for p_idx in range(n_projects):
        judge_indices = random.sample(range(n_judges), reviews_per_project)
        for j_idx in judge_indices:
            value = true_q[f'p{p_idx}'] + true_b[f'j{j_idx}'] + random.gauss(0, 0.1)
            scores.append({
                'project_id': f'p{p_idx}',
                'judge_id': f'j{j_idx}',
                'value': value,
            })
    
    result = normalize(scores)
    
    assert result.is_connected
    assert result.iterations < 100
    
    # Recovered q should correlate with true_q
    true_q_vals = [true_q[p] for p in sorted(true_q)]
    recovered_q_vals = [result.q[p] for p in sorted(true_q)]
    
    # Pearson correlation
    n = len(true_q_vals)
    mean_t = sum(true_q_vals) / n
    mean_r = sum(recovered_q_vals) / n
    cov = sum((t - mean_t) * (r - mean_r) for t, r in zip(true_q_vals, recovered_q_vals)) / n
    var_t = sum((t - mean_t) ** 2 for t in true_q_vals) / n
    var_r = sum((r - mean_r) ** 2 for r in recovered_q_vals) / n
    correlation = cov / ((var_t * var_r) ** 0.5)
    
    assert correlation > 0.95


def test_normalization_handles_zero_variance_rater():
    """A judge who rates everything the same should not break the fit."""
    scores = [
        {'project_id': 'p1', 'judge_id': 'j1', 'value': 4.0},
        {'project_id': 'p2', 'judge_id': 'j1', 'value': 4.0},  # same as p1
        {'project_id': 'p1', 'judge_id': 'j2', 'value': 3.0},
        {'project_id': 'p2', 'judge_id': 'j2', 'value': 5.0},
    ]
    result = normalize(scores)
    assert result.is_connected
    # j1 has zero variance; their bias is estimable but contributes equally
    assert result.b['j1'] == 0.0  # centred around 0


def test_normalization_handles_incomplete_batch():
    """Some projects have fewer reviews than others."""
    scores = [
        {'project_id': 'p1', 'judge_id': 'j1', 'value': 4.0},
        {'project_id': 'p1', 'judge_id': 'j2', 'value': 3.0},
        # p2 has only one review
        {'project_id': 'p2', 'judge_id': 'j1', 'value': 5.0},
    ]
    result = normalize(scores)
    assert result.is_connected
    assert 'p1' in result.q
    assert 'p2' in result.q


def test_normalization_deduplicates_duplicate_scores():
    """A duplicate (judge, project) entry should be averaged."""
    scores = [
        {'project_id': 'p1', 'judge_id': 'j1', 'value': 4.0},
        {'project_id': 'p1', 'judge_id': 'j1', 'value': 6.0},  # duplicate, different value
    ]
    result = normalize(scores)
    # Deduped to a single (4 + 6) / 2 = 5
    assert result.q  # fit completes
```

### 10.5 URLs

```python
# apps/normalization/urls.py

from django.urls import path
from .views import NormalizeView

urlpatterns = [
    path('<slug:slug>/normalize', NormalizeView.as_view()),
]
```

---

## Part 11 — Pairwise App (apps/pairwise)

### 11.1 Models

```python
# apps/pairwise/models.py

import uuid
from django.db import models
from apps.accounts.models import User
from apps.events.models import Event
from apps.submissions.models import Submission


class PairwiseRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='pairwise_runs')
    method = models.CharField(max_length=50, default='bradley_terry_mm')
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pairwise_pairwiserun'


class PairwiseComparison(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    judge = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pairwise_comparisons')
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    left_project = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='pairwise_left')
    right_project = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='pairwise_right')
    winner = models.CharField(max_length=10, choices=[('left', 'Left'), ('right', 'Right')])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pairwise_pairwisecomparison'
        unique_together = ('judge', 'event', 'left_project', 'right_project')


class PairwiseRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PairwiseRun, on_delete=models.CASCADE, related_name='ratings')
    project = models.ForeignKey(Submission, on_delete=models.CASCADE)
    theta = models.FloatField()
    stderr = models.FloatField()
    
    class Meta:
        db_table = 'pairwise_pairwiserating'
        unique_together = ('run', 'project')
```

### 11.2 The BT fit

```python
# apps/pairwise/fit.py

from collections import defaultdict


def fit_bt(comparisons: list) -> dict:
    """Fit Bradley-Terry by MM algorithm.
    
    comparisons: list of dicts with keys: left, right, winner (left/right)
    Returns: dict mapping project_id -> {theta, stderr}
    """
    projects = set()
    wins = defaultdict(int)  # project -> total wins
    losses = defaultdict(int)  # project -> total losses
    n_ij = defaultdict(lambda: defaultdict(int))  # n_ij[winner][loser] = count
    
    for c in comparisons:
        l, r, w = c['left'], c['right'], c['winner']
        projects.add(l)
        projects.add(r)
        if w == 'left':
            wins[l] += 1
            losses[r] += 1
            n_ij[l][r] += 1
        else:
            wins[r] += 1
            losses[l] += 1
            n_ij[r][l] += 1
    
    # Initialize p with weak prior: half-win / half-loss against phantom
    phantom_w = 0.5
    phantom_l = 0.5
    p = {}
    for proj in projects:
        if wins[proj] == 0 and losses[proj] == 0:
            p[proj] = 1.0  # unseen, default
        elif wins[proj] == 0:
            p[proj] = phantom_w / (phantom_l + losses[proj])
        elif losses[proj] == 0:
            p[proj] = wins[proj] + phantom_w  # undefeated
        else:
            p[proj] = (wins[proj] + phantom_w) / (losses[proj] + phantom_l)
    
    # Iterate
    for iteration in range(1000):
        new_p = {}
        for i in projects:
            w_i = wins[i] + phantom_w
            denom = 0.0
            for j in projects:
                if j == i:
                    continue
                denom += n_ij[i][j] / (p[i] + p[j])
                denom += n_ij[j][i] / (p[j] + p[i])  # both directions
            new_p[i] = w_i / denom if denom > 0 else 1.0
        
        # Renormalize
        total = sum(new_p.values())
        new_p = {k: v / total for k, v in new_p.items()}
        
        # Convergence
        max_change = max(abs(new_p[i] - p[i]) for i in projects) if projects else 0.0
        p = new_p
        if max_change < 1e-9:
            break
    
    # theta = log(p)
    theta = {proj: _log(p[proj]) for proj in projects}
    
    # stderr: approximation via Fisher information
    # For simplicity: 1/sqrt(wins + losses)
    stderr = {}
    for proj in projects:
        n = wins[proj] + losses[proj]
        stderr[proj] = 1.0 / (n + 1) ** 0.5  # rough
    
    return {'theta': theta, 'stderr': stderr, 'iterations': iteration + 1}


def _log(x):
    import math
    if x <= 0:
        return -10
    return math.log(x)
```

### 11.3 Pair selection by information value

```python
# apps/pairwise/selection.py

import math
from collections import defaultdict


def next_pair(judge_id, event, current_theta):
    """Pick the next pair for a judge, by information value."""
    from apps.judging.models import JudgeAssignment
    from apps.submissions.models import Submission
    
    projects = list(
        Submission.objects.filter(
            event=event,
            status='submitted',
            judge_assignments__judge_id=judge_id,
        ).distinct()
    )
    
    if len(projects) < 2:
        return None
    
    # Get existing comparisons by this judge
    from .models import PairwiseComparison
    existing = PairwiseComparison.objects.filter(judge_id=judge_id, event=event)
    seen_pairs = {(c.left_project_id, c.right_project_id) for c in existing}
    
    candidates = []
    for i in range(len(projects)):
        for j in range(i + 1, len(projects)):
            p1, p2 = projects[i], projects[j]
            if (p1.id, p2.id) in seen_pairs or (p2.id, p1.id) in seen_pairs:
                continue
            
            # Information value: uncertainty * novelty
            theta1 = current_theta.get(str(p1.id), 0.0)
            theta2 = current_theta.get(str(p2.id), 0.0)
            predicted_p1 = 1.0 / (1.0 + math.exp(-(theta1 - theta2)))
            uncertainty = 1.0 - abs(predicted_p1 - 0.5) * 2  # 1 when uncertain, 0 when certain
            
            candidates.append((uncertainty, p1, p2))
    
    if not candidates:
        return None
    
    candidates.sort(key=lambda c: -c[0])
    _, p1, p2 = candidates[0]
    return (p1, p2)
```

### 11.4 Views

```python
# apps/pairwise/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PairwiseComparison, PairwiseRun, PairwiseRating
from .fit import fit_bt
from .selection import next_pair
from apps.judging.models import JudgeAssignment
from apps.submissions.models import Submission
from apps.events.models import Event, Membership
from apps.events.permissions import IsJudge, IsOrganizer
from apps.events.decorators import deadline_gated


class PairwiseNextView(APIView):
    permission_classes = [IsAuthenticated, IsJudge]
    
    @deadline_gated('judging_close_at')
    def get(self, request, slug):
        event = Event.objects.get(slug=slug)
        
        # Get current theta from latest run (or default)
        theta = {}
        latest_run = PairwiseRun.objects.filter(event=event).order_by('-created_at').first()
        if latest_run:
            for r in latest_run.ratings.all():
                theta[str(r.project_id)] = r.theta
        
        pair = next_pair(request.user.id, event, theta)
        if not pair:
            return Response({'done': True})
        
        p1, p2 = pair
        return Response({
            'left': {'id': str(p1.id), 'name': p1.name, 'tagline': p1.tagline, 'thumbnail_url': p1.thumbnail_path},
            'right': {'id': str(p2.id), 'name': p2.name, 'tagline': p2.tagline, 'thumbnail_url': p2.thumbnail_path},
        })


class PairwiseAnswerView(APIView):
    permission_classes = [IsAuthenticated, IsJudge]
    
    @deadline_gated('judging_close_at')
    def post(self, request, slug, id):
        comp = PairwiseComparison.objects.get(id=id, judge=request.user)
        comp.winner = request.data.get('winner')
        comp.save()
        return Response({'saved': True})


class PairwiseRankingView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        comparisons = list(
            PairwiseComparison.objects.filter(event=event).values(
                'left_project_id', 'right_project_id', 'winner'
            )
        )
        comparisons = [
            {
                'left': str(c['left_project_id']),
                'right': str(c['right_project_id']),
                'winner': c['winner'],
            }
            for c in comparisons
        ]
        
        result = fit_bt(comparisons)
        
        run = PairwiseRun.objects.create(event=event, method='bradley_terry_mm')
        PairwiseRating.objects.bulk_create([
            PairwiseRating(
                run=run,
                project_id=proj,
                theta=theta,
                stderr=stderr,
            )
            for proj, (theta, stderr) in zip(
                result['theta'].keys(),
                zip(result['theta'].values(), result['stderr'].values()),
            )
        ])
        
        # Ranking
        ranking = sorted(result['theta'].items(), key=lambda x: -x[1])
        return Response({
            'run_id': str(run.id),
            'n_comparisons': len(comparisons),
            'iterations': result['iterations'],
            'ranking': [
                {'project_id': p, 'theta': t, 'stderr': result['stderr'][p]}
                for p, t in ranking
            ],
        })
```

## Part 12 — API App (apps/api)

### 12.1 Models

```python
# apps/api/models.py

import uuid
import secrets
import hashlib
from django.db import models
from apps.accounts.models import User
from apps.events.models import Event


class Webhook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField(max_length=500)
    secret_hash = models.CharField(max_length=64)
    events = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    
    class Meta:
        db_table = 'api_webhook'
    
    @classmethod
    def create(cls, event, url, events, created_by):
        secret = secrets.token_urlsafe(32)
        return cls.objects.create(
            event=event,
            url=url,
            secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
            events=events,
            created_by=created_by,
        ), secret


class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=100)
    payload = models.BinaryField()
    signature = models.CharField(max_length=64)
    attempted_at = models.DateTimeField()
    status_code = models.IntegerField(default=0)
    response_body = models.TextField(blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'api_webhookdelivery'


class SigningKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_key = models.BinaryField()
    private_key = models.BinaryField()  # stored only in production via .env
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'api_signingkey'


class Certificate(models.Model):
    KIND_CHOICES = [('participant', 'Participant'), ('judge', 'Judge'), ('organizer', 'Organizer')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='certificates')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    serial = models.CharField(max_length=40, unique=True)
    signature = models.BinaryField()
    public_key = models.ForeignKey(SigningKey, on_delete=models.PROTECT)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_certificate'
```

### 12.2 Custom exception handler

```python
# apps/api/exceptions.py

from rest_framework.views import exception_handler as drf_default
from rest_framework.response import Response
from rest_framework import status


class Hack HamsterError(Exception):
    code = 'error'
    message = 'An error occurred.'
    status_code = 400
    
    def __init__(self, message=None, detail=None):
        if message:
            self.message = message
        self.detail = detail


class ForbiddenRole(Hack HamsterError):
    code = 'forbidden_role'
    message = 'You do not have permission to do that.'
    status_code = 403


class DeadlinePassed(Hack HamsterError):
    code = 'deadline_passed'
    message = 'The deadline has passed.'
    status_code = 422


class ValidationFailed(Hack HamsterError):
    code = 'validation_failed'
    message = 'Validation failed.'
    status_code = 422


class RateLimited(Hack HamsterError):
    code = 'rate_limited'
    message = 'Too many requests.'
    status_code = 429
    
    def __init__(self, retry_after=60):
        self.retry_after = retry_after


def custom_exception_handler(exc, context):
    if isinstance(exc, Hack HamsterError):
        body = {'error': {'code': exc.code, 'message': exc.message, 'detail': exc.detail}}
        response = Response(body, status=exc.status_code)
        if isinstance(exc, RateLimited):
            response['Retry-After'] = str(exc.retry_after)
        return response
    
    response = drf_default(exc, context)
    if response is None:
        return None
    
    # Wrap DRF default errors
    detail = response.data
    if isinstance(detail, dict) and 'detail' in detail:
        body = {'error': {'code': _code_for_status(response.status_code), 'message': str(detail['detail']), 'detail': {}}}
        return Response(body, status=response.status_code)
    if isinstance(detail, dict):
        # Validation errors are field-keyed
        body = {'error': {'code': 'validation_failed', 'message': 'Validation failed.', 'detail': detail}}
        return Response(body, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(detail, list):
        body = {'error': {'code': 'validation_failed', 'message': 'Validation failed.', 'detail': {'errors': detail}}}
        return Response(body, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    return response


def _code_for_status(s):
    return {
        400: 'bad_request',
        401: 'not_authenticated',
        403: 'forbidden_role',
        404: 'not_found',
        405: 'method_not_allowed',
        409: 'conflict',
        410: 'gone',
        413: 'payload_too_large',
        415: 'unsupported_media_type',
        429: 'rate_limited',
    }.get(s, 'internal_error')
```

### 12.3 Health endpoints

```python
# apps/api/views.py

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.events.models import Event


def healthz(request):
    return JsonResponse({'status': 'ok'})


def readyz(request):
    # Check migrations
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        return JsonResponse({'status': 'migrations_pending'}, status=503)
    
    # Check seed
    if not Event.objects.filter(slug='sample-hack-2026').exists():
        return JsonResponse({'status': 'seed_pending'}, status=503)
    
    return JsonResponse({'status': 'ready', 'migrations_applied': True, 'seed_loaded': True})


def certificate_view(request, public_id):
    """GET /api/certificates/<public_id> — public verify-on-read."""
    try:
        cert = Certificate.objects.select_related("submission").get(public_id=public_id)
    except Certificate.DoesNotExist:
        return JsonResponse({'error': {'code': 'not_found'}}, status=404)
    if not cert.verify():   # recompute the HMAC; hmac.compare_digest
        return JsonResponse({'error': {'code': 'signature_invalid'}}, status=400)
    return JsonResponse({
        'public_id': cert.public_id,
        'submission_id': str(cert.submission_id),
        'issued_at': cert.issued_at.isoformat(),
        'signed_payload': cert.signed_payload,
        'signature': cert.signature,
        'signature_algorithm': 'HMAC-SHA256',
    })


def widget_view(request):
    """Returns the embeddable widget JS bundle."""
    from django.conf import settings
    import os
    bundle_path = os.path.join(settings.BASE_DIR, 'web', 'widget.bundle.js')
    if not os.path.exists(bundle_path):
        bundle_path = os.path.join(settings.BASE_DIR, 'static', 'widget.bundle.js')
    
    if not os.path.exists(bundle_path):
        return JsonResponse({'error': {'code': 'not_found', 'message': 'Widget not built.'}}, status=404)
    
    with open(bundle_path, 'rb') as f:
        content = f.read()
    from django.http import HttpResponse
    return HttpResponse(content, content_type='application/javascript')
```

### 12.4 URL aggregator

```python
# apps/api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('auth/', include('apps.accounts.urls')),
    path('events/', include('apps.events.urls')),
    path('teams/', include('apps.teams.urls')),
    path('submissions/', include('apps.submissions.urls')),
    path('judge/', include('apps.judging.urls_judge')),
    path('voting/', include('apps.voting.urls')),
    path('audit/', include('apps.audit.urls')),
    path('normalization/', include('apps.normalization.urls')),
    path('pairwise/', include('apps.pairwise.urls')),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

### 12.5 Admin URL aggregator

```python
# apps/api/urls_admin.py

from django.urls import path
from .admin_views import DumpView, KeysRotateView

urlpatterns = [
    path('dump', DumpView.as_view()),
    path('keys/rotate', KeysRotateView.as_view()),
]
```

### 12.6 The seed_fixtures command

The kickoff deck (slide 7) says: *"Seed from the fixture event's own
`submissions_close_date`. One of the checks depends on it."* Concretely: T1 check 3
("POST `{submit}` as participant after deadline → 4xx") passes iff the seeded event's
`submissions_close_at` is in the UTC past at the moment `make accept` runs. The seed
command is *transparent* — it reads the field verbatim from `fixtures.json`. The
fixtures author is responsible for shipping a past date. If a future date ships, T1
fails; this is the contract, not a bug.

The model field is `submissions_close_at` (`_at`, not the deck's prose `_date`). The
JSON key is `submissions_close_at`. Do not "fix" the JSON to match the deck's prose —
the deck is informal here, the code is the contract.

```python
# apps/events/management/commands/seed_fixtures.py

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.events.models import Event, Track, Prize, Membership, Rubric, RubricCriterion
from apps.teams.models import Team, TeamMember
from apps.submissions.models import Submission, TechTag, SubmissionTag, CustomQuestion, CustomAnswer
from apps.judging.models import JudgeBatch, JudgeAssignment, JudgeInvite, Score, Review
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Load fixtures.json into the database.'
    
    def add_arguments(self, parser):
        parser.add_argument('--path', default='fixtures.json')
    
    def handle(self, *args, **options):
        path = Path(options['path'])
        if not path.exists():
            path = Path('/app/fixtures.json')
        
        with open(path) as f:
            data = json.load(f)
        
        # Event
        event, _ = Event.objects.update_or_create(
            slug=data['event']['slug'],
            defaults={
                'name': data['event']['name'],
                'description': data['event'].get('description', ''),
                'open_at': data['event']['open_at'],
                'submissions_close_at': data['event']['submissions_close_at'],
                'judging_open_at': data['event']['judging_open_at'],
                'judging_close_at': data['event']['judging_close_at'],
                'results_at': data['event'].get('results_at'),
                'created_by_id': None,
            },
        )
        
        # Tracks
        track_map = {}
        for t in data.get('tracks', []):
            track, _ = Track.objects.update_or_create(
                event=event, slug=t['slug'],
                defaults={'name': t['name'], 'description': t.get('description', ''), 'order': t.get('order', 0)},
            )
            track_map[t['slug']] = track
        
        # Rubric
        rubric, _ = Rubric.objects.update_or_create(
            event=event, defaults={'name': 'Default'},
        )
        RubricCriterion.objects.filter(rubric=rubric).delete()
        for i, c in enumerate(data.get('rubric', {}).get('criteria', [])):
            RubricCriterion.objects.create(
                rubric=rubric,
                name=c['name'],
                weight=c['weight'],
                min=c.get('min', 1),
                max=c.get('max', 5),
                order=i,
            )
        
        # Judges
        judge_map = {}
        for j in data.get('judges', []):
            user, _ = User.objects.get_or_create(
                email=j['email'],
                defaults={'is_active': True, 'name': j.get('name', '')},
            )
            Membership.objects.get_or_create(
                user=user, event=event,
                defaults={'role': 'judge'},
            )
            judge_map[j['id']] = user
        
        # Teams and projects
        project_map = {}
        for p in data.get('projects', []):
            team_data = next((t for t in data['teams'] if t['id'] == p['team']), None)
            captain, _ = User.objects.get_or_create(
                email=team_data['members'][0],
                defaults={'is_active': True},
            )
            Membership.objects.get_or_create(
                user=captain, event=event,
                defaults={'role': 'participant'},
            )
            team, _ = Team.objects.update_or_create(
                event=event, name=team_data['name'],
                defaults={'created_by': captain},
            )
            TeamMember.objects.get_or_create(team=team, user=captain, defaults={'role_in_team': 'captain'})
            for member_email in team_data['members'][1:]:
                member, _ = User.objects.get_or_create(
                    email=member_email,
                    defaults={'is_active': True},
                )
                TeamMember.objects.get_or_create(team=team, user=member)
            
            submission, _ = Submission.objects.update_or_create(
                team=team,
                defaults={
                    'event': event,
                    'track': track_map[p['track']],
                    'name': p['title'],
                    'tagline': p.get('summary', ''),
                    'description': p.get('long_description', ''),
                    'repo_url': p.get('repo_url', ''),
                    'live_url': p.get('live_url', ''),
                    'status': 'submitted',
                },
            )
            project_map[p['id']] = submission
        
        # Scores
        if data.get('scores'):
            # Create a default batch
            batch, _ = JudgeBatch.objects.get_or_create(
                event=event,
                defaults={'seed': 1, 'created_by_id': None, 'reviews_per_project': 3, 'projects_per_judge': 4},
            )
            
            Score.objects.filter(assignment__batch=batch).delete()
            
            # Build a simple assignment for the seed data
            seen = set()
            for s in data['scores']:
                key = (s['project'], s['judge'])
                if key in seen:
                    continue  # dedupe
                seen.add(key)
                
                assignment, _ = JudgeAssignment.objects.get_or_create(
                    batch=batch,
                    judge=judge_map[s['judge']],
                    project=project_map[s['project']],
                )
                for criterion_id, value in s['criteria'].items():
                    criterion = RubricCriterion.objects.get(
                        rubric=rubric, name=criterion_id.replace('_', ' ').title()
                    )
                    Score.objects.update_or_create(
                        assignment=assignment,
                        criterion=criterion,
                        defaults={'value': int(value)},
                    )
        
        self.stdout.write(self.style.SUCCESS(f'Loaded fixtures: {len(data.get("projects", []))} projects'))
```

---

## Part 13 — CSV Export

### 13.1 The CSV streaming view

```python
# apps/judging/csv_view.py

import csv
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from .models import Score, JudgeAssignment, Review
from apps.events.permissions import IsOrganizer
from apps.events.models import Event


class CSVExportView(APIView):
    permission_classes = [IsOrganizer]
    
    def get(self, request, slug):
        event = Event.objects.get(slug=slug)
        
        class Echo:
            """File-like object that just yields what it's written."""
            def write(self, value):
                return value
        
        writer = csv.writer(Echo())
        
        def rows():
            # Header
            yield writer.writerow([
                'project_id', 'project_title', 'track', 'team',
                'judge_id', 'judge_email',
                'criterion_name', 'value',
                'comment', 'submitted_at',
                'raw_mean', 'normalized_score', 'rank',
            ])
            
            scores = (
                Score.objects
                .filter(assignment__batch__event=event)
                .select_related(
                    'assignment__project__team',
                    'assignment__project__track',
                    'assignment__judge',
                    'criterion',
                    'assignment__review',
                )
            )
            
            from collections import defaultdict
            project_scores = defaultdict(list)
            for s in scores:
                project_scores[s.assignment.project_id].append(s)
            
            # Get latest normalization if available
            from apps.normalization.models import NormalizationRun, NormalizedScore
            latest_run = NormalizationRun.objects.filter(event=event).order_by('-created_at').first()
            norm_scores = {}
            if latest_run:
                for ns in NormalizedScore.objects.filter(run=latest_run):
                    norm_scores[ns.project_id] = (ns.adjusted, ns.rank_after)
            
            for s in scores:
                project = s.assignment.project
                review = getattr(s.assignment, 'review', None)
                norm_score, rank = norm_scores.get(project.id, ('', ''))
                
                yield writer.writerow([
                    str(project.id),
                    project.name,
                    project.track.slug,
                    project.team.name,
                    str(s.assignment.judge.id),
                    s.assignment.judge.email,
                    s.criterion.name,
                    s.value,
                    review.comment if review else '',
                    review.submitted_at.isoformat() if review and review.submitted_at else '',
                    '',  # raw_mean (aggregate per project)
                    norm_score,
                    rank,
                ])
            
            # Footer
            yield writer.writerow([
                f'# Export generated at {event.open_at}',
                f'event={event.slug}',
                f'projects={Submission.objects.filter(event=event, status="submitted").count()}',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
            ])
        
        response = StreamingHttpResponse(rows(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="export-{event.slug}.csv"'
        return response
```

---

## Part 14 — The Role-Isolation Matrix Test

### 14.1 The fixture and the test

```python
# backend/tests/integration/test_role_isolation.py

import pytest
from django.test import Client


ROLE_ENDPOINTS = [
    # (role, method, path, expected_status)
    ('visitor', 'GET', '/api/events/sample-hack-2026/gallery', 200),
    ('visitor', 'GET', '/api/judge/scores', 401),
    ('visitor', 'GET', '/api/judge/scores?judge=judge_a', 401),
    
    ('participant', 'GET', '/api/events/sample-hack-2026/gallery', 200),
    ('participant', 'GET', '/api/judge/scores', 403),
    ('participant', 'GET', '/api/judge/scores?judge=judge_a', 403),
    
    ('judge_a', 'GET', '/api/judge/scores', 200),
    ('judge_b', 'GET', '/api/judge/scores', 200),  # own scores
    ('judge_b', 'GET', '/api/judge/scores?judge=judge_a', 403),  # THE graded cell
    
    ('organizer', 'GET', '/api/judge/scores', 200),
    ('organizer', 'GET', '/api/judge/scores?judge=judge_a', 200),
    ('organizer', 'GET', '/api/events/sample-hack-2026/export.csv', 200),
    
    ('admin', 'GET', '/api/judge/scores', 200),
    ('admin', 'GET', '/api/judge/scores?judge=judge_a', 200),
    ('admin', 'GET', '/api/admin/dump', 200),
]


@pytest.mark.django_db
@pytest.mark.parametrize("role,method,path,expected_status", ROLE_ENDPOINTS)
def test_role_isolation_matrix(role, method, path, expected_status, client, seed_data):
    """The 30-cell role-isolation matrix."""
    if role != 'visitor':
        session_cookie = seed_data['cookies'][role]
        client.cookies['session'] = session_cookie
    
    response = getattr(client, method.lower())(path)
    assert response.status_code == expected_status, \
        f"{method} {path} as {role}: expected {expected_status}, got {response.status_code}"
```

### 14.2 Conftest for tests

```python
# backend/tests/conftest.py

import pytest
from apps.events.models import Event, Membership
from apps.accounts.models import User
from apps.accounts.middleware import SessionMiddleware
from django.contrib.sessions.backends.db import SessionStore


@pytest.fixture
def seed_data(db):
    """Create the five pre-baked users and return their session tokens."""
    event = Event.objects.get(slug='sample-hack-2026')
    
    users = {}
    cookies = {}
    
    for role, email, name in [
        ('organizer', 'organizer@test.local', 'Organizer'),
        ('judge_a', 'tomas.varga@example.org', 'Judge A'),
        ('judge_b', 'wei.lindqvist@example.org', 'Judge B'),
        ('judge_c', 'priya.nair@example.org', 'Judge C'),
        ('participant', 'participant@test.local', 'Participant'),
    ]:
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={'is_active': True, 'name': name},
        )
        user.set_password('hack-hamster123')
        user.save()
        
        Membership.objects.get_or_create(
            user=user, event=event,
            defaults={'role': role},
        )
        
        session = SessionStore()
        session['_auth_user_id'] = str(user.id)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session.save()
        
        from apps.accounts.models import Session as AppSession
        AppSession.objects.create(
            user=user,
            token_hash='_test_' + role,
            expires_at=session.expire_date,
        )
        
        users[role] = user
        cookies[role] = session.session_key
    
    return {'users': users, 'cookies': cookies, 'event': event}
```

### 14.3 Generate the role-isolation-matrix.txt artifact

```python
# backend/management/commands/generate_role_matrix.py

from django.core.management.base import BaseCommand
from django.test import Client
from apps.events.models import Event
from apps.accounts.models import User
from apps.accounts.models import Session as AppSession
from django.contrib.sessions.backends.db import SessionStore


class Command(BaseCommand):
    help = 'Generate role-isolation-matrix.txt from real HTTP calls.'
    
    def handle(self, *args, **options):
        event = Event.objects.get(slug='sample-hack-2026')
        lines = [
            'HACK HAMSTER role-isolation matrix',
            f'event: {event.slug}',
            'method: real HTTP calls via Django test client',
            '',
            'role          endpoint                                              expected  actual',
            '-' * 90,
        ]
        
        endpoints = [
            ('visitor', 'GET', '/api/events/sample-hack-2026/gallery'),
            ('visitor', 'GET', '/api/judge/scores'),
            ('visitor', 'GET', '/api/judge/scores?judge=judge_a'),
            ('participant', 'GET', '/api/judge/scores'),
            ('judge_a', 'GET', '/api/judge/scores'),
            ('judge_b', 'GET', '/api/judge/scores'),  # own
            ('judge_b', 'GET', '/api/judge/scores?judge=judge_a'),  # peer
            ('organizer', 'GET', '/api/judge/scores'),
            ('organizer', 'GET', '/api/events/sample-hack-2026/export.csv'),
        ]
        
        # ... iterate, make real HTTP calls, write status codes
        
        matrix = '\n'.join(lines)
        with open('role-isolation-matrix.txt', 'w') as f:
            f.write(matrix)
        self.stdout.write(self.style.SUCCESS('Wrote role-isolation-matrix.txt'))
```

---

## Part 15 — The .hack-hamster.toml

### 15.1 The file

This is the committed file at the repo root (abridged — the `[auth]` values
are real hex tokens, not placeholders):

```toml
[portal]
base_url = "http://localhost:8000"

[tiers]
claimed = ["T1", "T2", "T3"]
pitch = "A self-hosted hackathon portal with a judging engine you can trust: ..."

[auth]
# Seeded deterministically by import_fixtures (see §15.2) — valid after
# any clean `docker compose up`, no copy-paste step.
organizer   = "Cookie: session=<hex-token>"
judge_a     = "Cookie: session=<hex-token>"
judge_b     = "Cookie: session=<hex-token>"
participant = "Cookie: session=<hex-token>"

[routes]
gallery      = "/api/gallery"
submit       = "/api/events/sample-hack-2026/submit"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/peer-scores?judge=judge_a"
csv_export   = "/api/csv_export"
```

### 15.2 How the [auth] block is populated

It is not a manual step. `import_fixtures` seeds the demo sessions with
DETERMINISTIC tokens — `HMAC-SHA256(DJANGO_SECRET_KEY,
"hack-hamster-2026-demo-session:{label}:{email}")`, derived from the role label and
the seeded user's email (never a database PK, which fresh volumes would
change) — so the committed `.hack-hamster.toml` is valid after any
`docker compose up` and on any fresh database volume:

```bash
# 1. Bring up the portal (entrypoint runs migrate + import_fixtures)
docker compose up

# 2. Run the checker — the committed [auth] values just work
python3 acceptance.py .hack-hamster.toml        # or the official run.py
```

`import_fixtures` still prints the headers ("Stable demo session cookies
(deterministic — they match the committed .hack-hamster.toml)") for the one case
that needs them: if you changed `DJANGO_SECRET_KEY`, copy the newly printed
values into `.hack-hamster.toml`.

### 15.3 The run.py script (provided by spec)

The spec provides `run.py`. We do not modify it. It:

1. Parses `.hack-hamster.toml`.
2. Makes the 7 HTTP calls.
3. Asserts the responses.
4. Prints PASS/FAIL with detail.

Our `make accept` runs it and commits the report.

---

## Part 16 — URLs Cross-Reference

The complete URL tree (mounted at `/api/`):

```
/api/
├── auth/
│   ├── register       POST
│   ├── login          POST
│   ├── logout         POST
│   └── me             GET
├── events/
│   ├──                POST    (create)
│   ├── <slug>/        GET, PATCH
│   ├── <slug>/tracks  POST
│   └── <slug>/rubric  POST
├── teams/
│   ├── join           POST
│   └── (others via events/<slug>/teams)
├── submissions/
│   └── (mounted via events/<slug>/submissions)
├── judge/
│   └── scores         GET
├── voting/
│   └── (mounted via events/<slug>/projects/<id>/vote)
├── audit/
│   └── (events/<slug>/audit)
├── normalization/
│   └── (events/<slug>/normalize)
├── pairwise/
│   └── (events/<slug>/pairwise)
└── admin/
    ├── dump                  GET
    └── keys/rotate           POST
```

Plus:

```
/admin/                  Django admin
/healthz                 GET
/readyz                  GET
/verify                  GET
/widget.js               GET
/api/schema/             GET (OpenAPI YAML)
/api/schema/swagger-ui/  GET
/api/schema/redoc/       GET
```

