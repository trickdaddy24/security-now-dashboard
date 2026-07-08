from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .disk import free_bytes
from .integrations import notify_telegram
from .version import get_version

log = logging.getLogger(__name__)


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "unknown"


def build_heartbeat_message(
    *,
    download_dir: Path,
    running: bool,
    counts: dict[str, Any] | None,
    watcher_enabled: bool,
    watcher_interval_hours: float,
    latest_episode: int,
) -> str:
    host = socket.gethostname()
    version = get_version()
    free = free_bytes(download_dir)
    free_gb = free / (1024**3) if free else 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    c = counts or {}
    batch_line = (
        f"batch running ({c.get('active', 0)} active, {c.get('completed', 0)} done)"
        if running
        else "batch idle"
    )
    watcher_line = (
        f"watcher on ({watcher_interval_hours:g}h)"
        if watcher_enabled
        else "watcher off"
    )
    ep_line = f"GRC latest #{latest_episode}" if latest_episode else "GRC catalog pending"
    return (
        f"💓 Security Now heartbeat — {now}\n"
        f"🖥️ {host} | 🌐 {_local_ip()} | v{version}\n"
        f"📁 {download_dir} · {free_gb:.1f} GB free\n"
        f"⬇️ {batch_line} · {watcher_line}\n"
        f"📻 {ep_line}"
    )


async def run_heartbeat_loop(
    *,
    bot_token: str | None,
    chat_id: str | None,
    interval_hours: float,
    verify_ssl: bool,
    status_cb: Callable[[], dict[str, Any]],
) -> None:
    if not bot_token or not chat_id or interval_hours <= 0:
        log.info("Telegram heartbeat disabled (missing credentials or interval=0)")
        return
    interval = max(0.5, interval_hours) * 3600.0
    log.info("Telegram heartbeat started (every %.1fh)", interval_hours)
    while True:
        try:
            snap = status_cb()
            msg = build_heartbeat_message(
                download_dir=Path(snap.get("download_dir", ".")),
                running=bool(snap.get("running")),
                counts=snap.get("counts"),
                watcher_enabled=bool(snap.get("watcher_enabled")),
                watcher_interval_hours=float(snap.get("watcher_interval_hours") or 6),
                latest_episode=int(snap.get("latest_episode") or 0),
            )
            ok = await notify_telegram(
                bot_token,
                chat_id,
                msg,
                verify_ssl=verify_ssl,
            )
            if ok:
                log.info("Telegram heartbeat sent")
            else:
                log.warning("Telegram heartbeat failed")
        except Exception:
            log.exception("Heartbeat loop error")
        await asyncio.sleep(interval)