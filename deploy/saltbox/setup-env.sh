#!/usr/bin/env bash
set -euo pipefail
cd /opt/security-now-dashboard
DISCORD="$(grep '^DISCORD_WEBHOOK_URL=' ~/notifier/.env | cut -d= -f2- | tr -d "'")"
if [[ -f .env.production ]] && grep -q '^SN_API_KEY=' .env.production; then
  API_KEY="$(grep '^SN_API_KEY=' .env.production | cut -d= -f2-)"
else
  API_KEY="$(openssl rand -hex 24)"
fi
# Authelia on Traefik handles login — no app-level basic auth
cat > .env.production <<EOF
SN_DOWNLOAD_DIR=/data/downloads
SN_DEV_MODE=1
SN_API_KEY=${API_KEY}
SN_RATE_LIMIT=30
SN_WATCHER_ENABLED=1
SN_WATCHER_INTERVAL_HOURS=6
SN_PUBLIC_URL=https://sn.aaa.stunna.xyz
SN_LOG_JSON=1
SN_LOG_LEVEL=INFO
SN_DISCORD_WEBHOOK=${DISCORD}
EOF
chmod 600 .env.production
mkdir -p data/downloads
echo "env_ok"
echo "public_url=https://sn.aaa.stunna.xyz"
echo "auth=authelia"
echo "api_key=${API_KEY}"