#!/usr/bin/env bash
set -euo pipefail
cd /opt/security-now-dashboard
DISCORD="$(grep '^DISCORD_WEBHOOK_URL=' ~/notifier/.env | cut -d= -f2- | tr -d "'")"
cat > .env.production <<EOF
SN_DOWNLOAD_DIR=/data/downloads
SN_DEV_MODE=1
SN_WATCHER_ENABLED=1
SN_WATCHER_INTERVAL_HOURS=6
SN_PUBLIC_URL=https://sn.e4z.xyz
SN_LOG_JSON=1
SN_LOG_LEVEL=INFO
SN_DISCORD_WEBHOOK=${DISCORD}
EOF
chmod 600 .env.production
mkdir -p data/downloads
echo "env_ok"