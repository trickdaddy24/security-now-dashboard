#!/usr/bin/env bash
set -euo pipefail
cd /opt/security-now-dashboard
DISCORD="$(grep '^DISCORD_WEBHOOK_URL=' ~/notifier/.env | cut -d= -f2- | tr -d "'")"
# Preserve existing password if .env.production already has one
if [[ -f .env.production ]] && grep -q '^SN_AUTH_PASSWORD=' .env.production; then
  AUTH_PASS="$(grep '^SN_AUTH_PASSWORD=' .env.production | cut -d= -f2-)"
else
  AUTH_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
fi
if [[ -f .env.production ]] && grep -q '^SN_API_KEY=' .env.production; then
  API_KEY="$(grep '^SN_API_KEY=' .env.production | cut -d= -f2-)"
else
  API_KEY="$(openssl rand -hex 24)"
fi
cat > .env.production <<EOF
SN_DOWNLOAD_DIR=/data/downloads
SN_DEV_MODE=0
SN_AUTH_USER=admin
SN_AUTH_PASSWORD=${AUTH_PASS}
SN_API_KEY=${API_KEY}
SN_RATE_LIMIT=30
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
echo "auth_user=admin"
echo "auth_password=${AUTH_PASS}"
echo "api_key=${API_KEY}"