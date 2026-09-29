#!/bin/sh
set -e

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-hack-hamster}"

echo "[entrypoint] waiting for postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
i=0
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "[entrypoint] postgres not reachable after 60s, giving up"
        exit 1
    fi
    sleep 1
done

echo "[entrypoint] postgres ready, running migrations..."
python manage.py migrate --noinput

# Requirement #1 is "docker compose up brings up a working, SEEDED
# portal" — not "...and then you run one more command." Import the
# official fixtures.json automatically so a bare `docker compose up`
# is enough. Every boot re-imports (idempotent — see import_fixtures).
# The five demo session cookies are DETERMINISTIC (HMAC of
# DJANGO_SECRET_KEY + label + email), so the committed .hack-hamster.toml
# is valid on every boot and on every fresh database volume — the
# acceptance checker passes with no manual step. Set SKIP_SEED=1 to
# skip (e.g. CI runs that seed explicitly at a chosen point instead).
if [ "${SKIP_SEED:-0}" != "1" ]; then
    if [ -f "fixtures.json" ]; then
        echo "[entrypoint] seeding from fixtures.json..."
        python manage.py import_fixtures
    else
        echo "[entrypoint] fixtures.json not found, falling back to seed_fixtures..."
        python manage.py seed_fixtures
    fi
fi

echo "[entrypoint] starting: $@"
exec "$@"
