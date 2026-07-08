from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from .host_info import build_telegram_message, resolve_external_ip
from .integrations import notify_discord, notify_telegram, post_webhook
from .version import get_version
from .models import MediaType
from .parser import fetch_catalog

log = logging.getLogger(__name__)
STATE_FILE = ".sn-watcher-state.json"


def load_state(download_dir: Path) -> dict[str, Any]:
    path = download_dir / STATE_FILE
    if not path.is_file():
        return {"last_seen": 0, "last_check": None, "last_triggered": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_seen": 0, "last_check": None, "last_triggered": None}


def save_state(download_dir: Path, state: dict[str, Any]) -> None:
    path = download_dir / STATE_FILE
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


async def check_new_episode(
    download_dir: Path,
    *,
    verify_ssl: bool = True,
) -> tuple[int, int, bool]:
    """Returns (latest, last_seen, is_new)."""
    state = load_state(download_dir)
    last_seen = int(state.get("last_seen", 0))
    _, latest = await fetch_catalog(verify_ssl=verify_ssl)
    state["last_check"] = time.time()
    save_state(download_dir, state)
    return latest, last_seen, latest > last_seen


async def run_watcher_loop(
    download_dir: Path,
    enqueue_cb,
    *,
    interval_hours: float = 6.0,
    verify_ssl: bool = True,
    notifier_url: str | None = None,
    discord_url: str | None = None,
    telegram_token: str | None = None,
    telegram_chat_id: str | None = None,
    public_url: str | None = None,
    default_media: list[str] | None = None,
) -> None:
    interval = max(0.5, interval_hours) * 3600.0
    media = default_media or ["audio_twit"]
    log.info("Episode watcher started (every %.1fh)", interval_hours)
    while True:
        try:
            latest, last_seen, is_new = await check_new_episode(download_dir, verify_ssl=verify_ssl)
            if is_new and latest > 0:
                log.info("New episode detected: #%s (was #%s)", latest, last_seen)
                ok = await enqueue_cb(latest, media)
                state = load_state(download_dir)
                state["last_seen"] = latest
                state["last_triggered"] = time.time()
                save_state(download_dir, state)
                msg = f"Security Now episode #{latest} queued (was #{last_seen})"
                await post_webhook(notifier_url, {"event": "new_episode", "episode": latest, "message": msg}, verify_ssl=verify_ssl)
                await notify_discord(discord_url, title="Security Now — new episode", description=msg, verify_ssl=verify_ssl)
                ext_ip = await resolve_external_ip(verify_ssl=verify_ssl)
                await notify_telegram(
                    telegram_token,
                    telegram_chat_id,
                    build_telegram_message(
                        "Security Now — new episode",
                        version=get_version(),
                        external_ip=ext_ip,
                        public_url=public_url,
                        extra_lines=[msg],
                    ),
                    verify_ssl=verify_ssl,
                )
                if not ok:
                    log.warning("Failed to enqueue episode #%s", latest)
            elif latest > last_seen:
                state = load_state(download_dir)
                state["last_seen"] = latest
                save_state(download_dir, state)
        except Exception:
            log.exception("Watcher check failed")
        await asyncio.sleep(interval)