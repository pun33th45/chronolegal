#!/usr/bin/env bash
# Deletes backup files older than a retention window, from a given directory,
# matching a given glob pattern. Split out from backup_db.sh so retention
# logic can be tested in isolation (no Docker/Postgres required — it only
# ever touches plain files).
#
# Usage: prune_backups.sh <backup_dir> <retention_days> <glob_pattern>
#
# Guarantee: the single most recent matching file is NEVER deleted,
# regardless of its age — even if every backup predates the retention
# window, at least one survives.
set -euo pipefail

BACKUP_DIR="${1:?Usage: prune_backups.sh <backup_dir> <retention_days> <glob_pattern>}"
RETENTION_DAYS="${2:?Usage: prune_backups.sh <backup_dir> <retention_days> <glob_pattern>}"
GLOB_PATTERN="${3:?Usage: prune_backups.sh <backup_dir> <retention_days> <glob_pattern>}"

if [ ! -d "$BACKUP_DIR" ]; then
  echo "prune_backups: backup directory does not exist: $BACKUP_DIR" >&2
  exit 1
fi

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "prune_backups: retention_days must be a non-negative integer, got: $RETENTION_DAYS" >&2
  exit 1
fi

# Newest-first list of matching files. Zero matches -> empty list, nothing to do.
mapfile -t all_backups < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$GLOB_PATTERN" -printf '%T@ %p\n' 2>/dev/null \
  | sort -rn | cut -d' ' -f2-)

if [ "${#all_backups[@]}" -eq 0 ]; then
  echo "prune_backups: no backups found matching '$GLOB_PATTERN' in $BACKUP_DIR"
  exit 0
fi

newest="${all_backups[0]}"

if [ "$RETENTION_DAYS" -eq 0 ]; then
  # 0 = retention disabled; keep everything.
  echo "prune_backups: retention_days=0 (retention disabled), keeping all ${#all_backups[@]} backup(s)"
  exit 0
fi

removed=0
for f in "${all_backups[@]}"; do
  if [ "$f" = "$newest" ]; then
    continue # never delete the newest, even if it's older than the window
  fi
  if [ -n "$(find "$f" -maxdepth 0 -mtime "+$RETENTION_DAYS" 2>/dev/null)" ]; then
    rm -f "$f"
    echo "prune_backups: removed expired backup: $f"
    removed=$((removed + 1))
  fi
done

echo "prune_backups: removed $removed expired backup(s); newest kept: $newest"
