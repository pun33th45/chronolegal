#!/usr/bin/env bash
# Optional off-host replication for genuine disaster-recovery coverage.
#
# scripts/backup/backup_db.sh already produces tested, verified LOCAL
# backups — but a backup that only ever lives on the same host as the
# database it protects doesn't survive losing that host (see
# docs/deployment.md's LOCAL vs. DISASTER-RECOVERY distinction). This
# script closes that gap WITHOUT assuming any specific cloud provider:
# plain rsync over SSH works with any remote host you already control (a
# second server, a NAS, a cheap storage-only VPS, etc.) — no new cloud
# subscription or SDK dependency required.
#
# Safe by default: does nothing (exit 0) unless OFFHOST_BACKUP_HOST is
# explicitly set. Never deletes local backups — this only ever adds a
# copy remotely, so scripts/backup/backup_db.sh's existing, tested
# retention/backup behavior is completely unaffected whether or not this
# is configured.
#
# Required if enabled:
#   OFFHOST_BACKUP_HOST   e.g. backup-user@backup-host.example.com
#   OFFHOST_BACKUP_PATH   remote directory to sync backups into
# Optional:
#   OFFHOST_SSH_KEY       private key path for the rsync/ssh connection
#                         (default: whatever `ssh` already resolves —
#                         agent, default identity file, etc.)
#   BACKUP_DIR            local backups directory (default: ./backups)
#
# Usage: scripts/backup/sync_offhost.sh
set -euo pipefail

if [ -z "${OFFHOST_BACKUP_HOST:-}" ]; then
  echo "sync_offhost: OFFHOST_BACKUP_HOST is not set — off-host replication is disabled. Nothing to do."
  exit 0
fi

: "${OFFHOST_BACKUP_PATH:?OFFHOST_BACKUP_PATH must be set when OFFHOST_BACKUP_HOST is configured}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"

if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
  echo "sync_offhost: no local backups found in $BACKUP_DIR — run backup_db.sh first" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is not installed — cannot perform off-host sync" >&2
  exit 1
fi

SSH_CMD="ssh -o StrictHostKeyChecking=accept-new"
if [ -n "${OFFHOST_SSH_KEY:-}" ]; then
  SSH_CMD="$SSH_CMD -i ${OFFHOST_SSH_KEY}"
fi

echo "Syncing $BACKUP_DIR -> $OFFHOST_BACKUP_HOST:$OFFHOST_BACKUP_PATH ..."
# --checksum: verifies transferred file integrity by content hash, not just
# size/mtime, so a corrupted transfer is re-copied rather than silently
# accepted as "in sync".
if ! rsync -az --checksum -e "$SSH_CMD" "$BACKUP_DIR"/ "$OFFHOST_BACKUP_HOST:$OFFHOST_BACKUP_PATH"/; then
  echo "ERROR: off-host sync failed — local backups are still intact, but disaster-recovery coverage is now stale until this succeeds" >&2
  exit 1
fi

echo "Off-host sync complete: $BACKUP_DIR -> $OFFHOST_BACKUP_HOST:$OFFHOST_BACKUP_PATH"
