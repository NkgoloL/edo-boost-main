#!/usr/bin/env bash
# docker/migrate.sh
#
# Run inside the db-migrate service defined in docker-compose.yml.
# Waits for Postgres to be ready, runs all pending Alembic migrations,
# then optionally seeds reference data on first boot.
#
# Environment variables expected:
#   DATABASE_URL   — async SQLAlchemy URL (postgresql+asyncpg://...)
#   POSTGRES_HOST  — hostname for pg_isready check (default: postgres)
#   POSTGRES_USER  — (default: eduboost_user)
#   POSTGRES_DB    — (default: eduboost)
#   SEED_ON_BOOT   — set to "true" to run seed script on first boot
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-eduboost_user}"
POSTGRES_DB="${POSTGRES_DB:-eduboost}"
SEED_ON_BOOT="${SEED_ON_BOOT:-false}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "==> Waiting for PostgreSQL at ${POSTGRES_HOST}..."
for i in $(seq 1 $MAX_RETRIES); do
    if pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q; then
        echo "==> PostgreSQL is ready."
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: PostgreSQL did not become ready in time."
        exit 1
    fi
    echo "    Attempt $i/$MAX_RETRIES — retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

echo "==> Running Alembic migrations..."
cd /workspace
alembic upgrade head
echo "==> Migrations complete."

# Seed reference data only if SEED_ON_BOOT=true AND the seed sentinel
# row does not already exist (idempotent).
if [ "$SEED_ON_BOOT" = "true" ]; then
    echo "==> Checking seed sentinel..."
    SEEDED=$(psql "$DATABASE_URL" -tAc \
        "SELECT COUNT(*) FROM audit_log WHERE action='create' AND target_table='seed'" 2>/dev/null || echo "0")
    if [ "$SEEDED" -eq "0" ]; then
        echo "==> Running seed script..."
        psql "$DATABASE_URL" -f /workspace/scripts/db_seed.sql
        psql "$DATABASE_URL" -c \
            "INSERT INTO audit_log(action, target_table, metadata) VALUES ('create','seed','{\"source\":\"db_seed.sql\"}')"
        echo "==> Seed complete."
    else
        echo "==> Seed already applied — skipping."
    fi
fi

echo "==> db-migrate service finished successfully."
