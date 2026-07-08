#!/usr/bin/env bash
set -euo pipefail
API=$(grep 'api:' /srv/git/saltbox/accounts.yml | awk '{print $2}')
EMAIL=$(grep 'email:' /srv/git/saltbox/accounts.yml | head -1 | awk '{print $2}')
ZONE=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=stunna.xyz" \
  -H "X-Auth-Email: $EMAIL" -H "X-Auth-Key: $API" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['id'])")
EXISTING=$(curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=sn.aaa.stunna.xyz" \
  -H "X-Auth-Email: $EMAIL" -H "X-Auth-Key: $API" \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)['result']))")
if [[ "$EXISTING" -gt 0 ]]; then
  echo "dns_exists"
  exit 0
fi
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" \
  -H "X-Auth-Email: $EMAIL" -H "X-Auth-Key: $API" \
  -H "Content-Type: application/json" \
  -d '{"type":"A","name":"sn.aaa.stunna.xyz","content":"138.201.28.235","proxied":false,"ttl":1}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok' if d.get('success') else d)"