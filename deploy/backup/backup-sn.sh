#!/usr/bin/env bash
# Nightly backup for Security Now download dir + RSS + search index.
# Cron example (02:30 daily):
#   30 2 * * * /opt/security-now-dashboard/deploy/backup/backup-sn.sh /data/downloads /backups/sn

set -euo pipefail

SRC="${1:-./data/downloads}"
DEST="${2:-./backups/sn}"
STAMP="$(date +%F)"
ARCHIVE="${DEST}/security-now-${STAMP}.tar.gz"

mkdir -p "$DEST"
tar -czf "$ARCHIVE" \
  -C "$(dirname "$SRC")" "$(basename "$SRC")" \
  --exclude='*.part'

find "$DEST" -name 'security-now-*.tar.gz' -mtime +14 -delete

echo "Backup written: $ARCHIVE"