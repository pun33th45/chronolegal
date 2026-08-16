#!/usr/bin/env bash
# Creates a pg_dump custom-format (-Fc) backup of the running `postgres`
# service, via `docker compose exec` — using the pg_dump binary already
# built into the postgres:16-alpine image, no extra tooling required on
# the host or in the backend image.
#
# Custom format (-Fc) is compressed, supports parallel/selective restore via
# pg_restore, and is Postgres's own recommended format for single-database
# logical backups — see docs/deployment.md's Backup & Restore section.
#
# Required environment (read from the shell environment or `.env` via
# `docker compose --env-file`/`set -a; source .env`; never hardcoded here):
#   POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD
#
# Optional:
#   BACKUP_DIR             (default: ./backups)
#   BACKUP_RETENTION_DAYS  (default: 14; 0 disables pruning)
#   COMPOSE_FILES          (default: "-f docker-compose.yml")
#
# Usage: scripts/backup/backup_db.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${POSTGRES_USER:?POSTGRES_USER must be set (see .env)}"
: "${POSTGRES_DB:?POSTGRES_DB must be set (see .env)}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set (see .env)}"

BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
read -ra COMPOSE_FILE_ARGS <<< "${COMPOSE_FILES:--f docker-compose.yml}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/chronolegal_${TIMESTAMP}.dump"
TMP_DEST="${DEST}.partial"

echo "Backing up database '$POSTGRES_DB' to $DEST ..."

cd "$REPO_ROOT"
if ! docker compose "${COMPOSE_FILE_ARGS[@]}" exec -T \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$TMP_DEST"; then
  echo "ERROR: pg_dump failed — no backup was produced" >&2
  rm -f "$TMP_DEST"
  exit 1
fi

if [ ! -s "$TMP_DEST" ]; then
  echo "ERROR: pg_dump produced an empty file — discarding" >&2
  rm -f "$TMP_DEST"
  exit 1
fi

mv "$TMP_DEST" "$DEST"
chmod 600 "$DEST"
echo "Backup written: $DEST ($(du -h "$DEST" | cut -f1))"

"$SCRIPT_DIR/prune_backups.sh" "$BACKUP_DIR" "$RETENTION_DAYS" 'chronolegal_*.dump'

echo ""
echo "This is a LOCAL backup on the host running docker compose. It protects"
echo "against database/container corruption, but NOT against loss of the host"
echo "itself (disk failure, accidental deletion, host compromise). Copy backups"
echo "off-host (S3, another machine, etc.) for real disaster-recovery coverage —"
echo "see docs/deployment.md's Backup & Restore section."
