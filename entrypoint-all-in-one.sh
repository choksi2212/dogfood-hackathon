#!/bin/sh
# entrypoint-all-in-one.sh — boots the single-container image.
#
# 1. Initialize the local Postgres data directory (first run only).
# 2. Start postgres ourselves so the rest of the script can wait
#    on it and run migrations / seed fixtures.
# 3. Hand control over to supervisord, which keeps postgres alive
#    and adds django / next / nginx on top.

set -e

# In the all-in-one container, Postgres lives locally on the loopback
# interface — never "db" (that's the multi-service compose default).
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"

PGDATA="/var/lib/postgresql/data"
PGUSER="${POSTGRES_USER:-hack_hamster}"
PGDB="${POSTGRES_DB:-hack_hamster}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[all-in-one] initializing postgres data directory at $PGDATA"
    mkdir -p "$PGDATA"
    chown -R postgres:postgres "$PGDATA"
    su postgres -c "/usr/lib/postgresql/*/bin/initdb -D $PGDATA --encoding=UTF8 --lc-collate=C --lc-ctype=C"
fi

# Always bring up postgres under the postgres user so pg_isready /
# migrations can connect. supervisord will keep it alive afterwards.
echo "[all-in-one] starting postgres..."
su postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $PGDATA -l /tmp/pg.log start"
# Create the role + database if missing.
su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$PGUSER'\"" | grep -q 1 \
    || su postgres -c "psql -c \"CREATE ROLE $PGUSER LOGIN PASSWORD '$PGUSER' SUPERUSER\""
su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='$PGDB'\"" | grep -q 1 \
    || su postgres -c "psql -c \"CREATE DATABASE $PGDB OWNER $PGUSER\""

# Wait for postgres to accept connections.
echo "[all-in-one] waiting for postgres..."
i=0
until pg_isready -h 127.0.0.1 -p 5432 -U "$PGUSER" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "[all-in-one] postgres not ready after 60s, aborting"
        exit 1
    fi
    sleep 1
done

# Migrate + seed. The all-in-one image bakes fixtures.json in, so
# the same auto-seed behaviour as the multi-service compose applies.
echo "[all-in-one] running migrations..."
python manage.py migrate --noinput

if [ "${SKIP_SEED:-0}" != "1" ]; then
    if [ -f "fixtures.json" ]; then
        echo "[all-in-one] seeding from fixtures.json..."
        python manage.py import_fixtures
    else
        echo "[all-in-one] fixtures.json not found, falling back to seed_fixtures..."
        python manage.py seed_fixtures
    fi
fi

# Hand off to supervisord, which keeps postgres running and starts
# django / next / nginx.
echo "[all-in-one] handing off to supervisord: $@"
exec "$@"
