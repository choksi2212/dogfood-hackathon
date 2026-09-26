#!/bin/sh
set -e

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-dogfood}"

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

echo "[entrypoint] starting: $@"
exec "$@"
