from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import httpx

from .library import scan_library
from .rss import FEED_NAMES


async def post_webhook(url: str | None, payload: dict[str, Any], *, verify_ssl: bool = True) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=verify_ssl) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code < 400
    except Exception:
        return False


async def notify_discord(
    webhook_url: str | None,
    *,
    title: str,
    description: str,
    verify_ssl: bool = True,
) -> bool:
    if not webhook_url:
        return False
    return await post_webhook(
        webhook_url,
        {"content": f"**{title}**\n{description}"},
        verify_ssl=verify_ssl,
    )


def write_plex_hint(download_dir: Path, message: str) -> Path:
    path = download_dir / ".plex-scan-hint.txt"
    path.write_text(message + "\n", encoding="utf-8")
    return path


def export_kodi_strm(download_dir: Path, out_dir: Path | None = None) -> list[str]:
    download_dir = Path(download_dir)
    target = out_dir or download_dir / "kodi"
    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for entry in scan_library(download_dir):
        for media, finfo in entry.files.items():
            if not media.startswith("audio"):
                continue
            strm = target / f"sn-{entry.number:04d}.strm"
            strm.write_text(str((download_dir / finfo.filename).resolve()) + "\n", encoding="utf-8")
            written.append(strm.name)
    return written


def export_opml(base_url: str, title: str = "Security Now Local Feeds") -> str:
    base = base_url.rstrip("/")
    feeds = [
        ("Security Now Audio", f"{base}/feed/audio.rss"),
        ("Security Now Video", f"{base}/feed/video.rss"),
        ("Security Now Text", f"{base}/feed/text.rss"),
        ("Security Now All", f"{base}/feed/all.rss"),
    ]
    items = "\n".join(
        f'    <outline type="rss" text="{escape(name)}" title="{escape(name)}" xmlUrl="{escape(url)}"/>'
        for name, url in feeds
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        f"  <head><title>{escape(title)}</title></head>\n"
        f"  <body>\n{items}\n  </body>\n"
        "</opml>\n"
    )