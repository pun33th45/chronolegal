#!/usr/bin/env bash
# Restores a pg_dump custom-format (-Fc) backup, created by backup_db.sh,
# into a target database via the running `postgres` service.
#
# Safety: refuses to restore into a database that already exists unless
# --force is passed. This is deliberate — the normal, safe way to verify a
# backup is to restore it into a fresh, disposable database name (see
# docs/deployment.md's restore-verification steps), never by overwriting a
# live one. --force exists for the genuine disaster-recovery case (the real
# production database is gone/corrupted and must be rebuilt), and the
# operator must explicitly opt into it.
#
# Required environment: POSTGRES_USER, POSTGRES_PASSWORD (never hardcoded).
# Optional: COMPOSE_FILES (default: "-f docker-compose.yml")
#
# Usage:
#   scripts/backup/restore_db.sh <backup_file> <target_db> [--force]
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore_db.sh <backup_file> <target_db> [--force]}"
TARGET_DB="${2:?Usage: restore_db.sh <backup_file> <target_db> [--force]}"
FORCE="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${POSTGRES_USER:?POSTGRES_USER must be set (see .env)}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set (see .env)}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

read -ra COMPOSE_FILE_ARGS <<< "${COMPOSE_FILES:--f docker-compose.yml}"
cd "$REPO_ROOT"

PSQL=(docker compose "${COMPOSE_FILE_ARGS[@]}" exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres psql -U "$POSTGRES_USER")

exists="$("${PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'" -d postgres | tr -d '[:space:]')"

if [ "$exists" = "1" ] && [ "$FORCE" != "--force" ]; then
  echo "ERROR: database '$TARGET_DB' already exists. Refusing to restore over it." >&2
  echo "Pass --force only if you genuinely intend to overwrite it (real disaster recovery)." >&2
  exit 1
fi

if [ "$exists" = "1" ]; then
  echo "Dropping existing database '$TARGET_DB' (--force was passed)..."
  "${PSQL[@]}" -c "DROP DATABASE \"$TARGET_DB\" WITH (FORCE)" -d postgres
fi

echo "Creating database '$TARGET_DB'..."
"${PSQL[@]}" -c "CREATE DATABASE \"$TARGET_DB\"" -d postgres

echo "Restoring $BACKUP_FILE into '$TARGET_DB'..."
if ! docker compose "${COMPOSE_FILE_ARGS[@]}" exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
    pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" --no-owner --no-privileges < "$BACKUP_FILE"; then
  echo "ERROR: pg_restore reported a failure — inspect the target database before trusting it" >&2
  exit 1
fi

echo "Restore complete: $BACKUP_FILE -> database '$TARGET_DB'"
echo "Verify before trusting this restore, e.g.:"
echo "  docker compose ${COMPOSE_FILES:--f docker-compose.yml} exec -T backend alembic current"
echo "  (run against $TARGET_DB — see docs/deployment.md for a full verification checklist)"
