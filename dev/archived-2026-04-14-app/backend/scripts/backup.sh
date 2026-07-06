#!/usr/bin/env bash
# =============================================================
# backup.sh — Nightly database + uploads backup
# Agora Consulting AI — Anti-Financial Crime Platform
# =============================================================
# Dumps the PostgreSQL database (pg_dump, custom format) and tars
# the uploads directory into $BACKUP_DIR, timestamped, and prunes
# backups older than $RETENTION_DAYS (default 30).
#
# Required environment:
#   DATABASE_URL   — postgres connection URL (asyncpg scheme accepted)
#   BACKUP_DIR     — target directory for backup files
# Optional:
#   UPLOADS_DIR    — uploads directory (default /app/uploads)
#   RETENTION_DAYS — days of backups to keep (default 30)
#
# Cron usage (nightly at 02:30, inside the backend container host):
#   30 2 * * * BACKUP_DIR=/var/backups/sof DATABASE_URL=postgres://... \
#       /path/to/backend/scripts/backup.sh >> /var/log/sof-backup.log 2>&1
# =============================================================
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${BACKUP_DIR:?BACKUP_DIR must be set}"
UPLOADS_DIR="${UPLOADS_DIR:-/app/uploads}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# pg_dump does not understand the SQLAlchemy driver scheme.
PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
PG_URL="${PG_URL/postgres:\/\//postgresql://}"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "[*] $(date -u +%Y-%m-%dT%H:%M:%SZ) — backing up to $BACKUP_DIR"

# --- 1. Database dump (custom format — restore with pg_restore) ---
DB_FILE="$BACKUP_DIR/sof-db-$STAMP.dump"
pg_dump --format=custom --no-owner --dbname="$PG_URL" --file="$DB_FILE"
echo "[+] Database dump: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"

# --- 2. Uploads archive ---
if [ -d "$UPLOADS_DIR" ]; then
    UPLOADS_FILE="$BACKUP_DIR/sof-uploads-$STAMP.tar.gz"
    tar -czf "$UPLOADS_FILE" -C "$(dirname "$UPLOADS_DIR")" "$(basename "$UPLOADS_DIR")"
    echo "[+] Uploads archive: $UPLOADS_FILE ($(du -h "$UPLOADS_FILE" | cut -f1))"
else
    echo "[!] Uploads directory not found ($UPLOADS_DIR) — skipping uploads archive."
fi

# --- 3. Prune old backups ---
find "$BACKUP_DIR" -maxdepth 1 -name 'sof-db-*.dump' -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'sof-uploads-*.tar.gz' -mtime "+$RETENTION_DAYS" -delete

echo "[+] Backup complete (retention: ${RETENTION_DAYS} days)."
