#!/usr/bin/env bash
# One-shot: rename library files to Kodi/Plex layout and fetch TWiT episode thumbnails.
set -euo pipefail
ROOT="${1:-/opt/security-now-dashboard}"
cd "$ROOT"
COMPOSE="docker compose -f docker-compose.yml -f deploy/saltbox/docker-compose.production.yml"
$COMPOSE exec -T security-now-dashboard python - <<'PY'
import asyncio
from grc_downloader.config import load_config
from grc_downloader.kodi_migrate import migrate_filenames_to_kodi
from grc_downloader.twit_thumbs import fetch_thumbs_for_library

cfg = load_config()
migrate = migrate_filenames_to_kodi(
    cfg.download_dir,
    episode_folders=cfg.episode_folders,
)
print("migrate_ok", migrate.get("renamed_count", 0), "renamed")
if migrate.get("errors"):
    for err in migrate["errors"]:
        print("migrate_error", err)

async def run():
    thumbs = await fetch_thumbs_for_library(
        cfg.download_dir,
        verify_ssl=cfg.verify_ssl,
        skip_existing=False,
    )
    print(
        "thumbs_ok",
        thumbs.get("fetched_count", 0),
        "fetched",
        thumbs.get("skipped_count", 0),
        "skipped",
    )
    if thumbs.get("errors"):
        for err in thumbs["errors"]:
            print("thumb_error", err)

asyncio.run(run())
PY