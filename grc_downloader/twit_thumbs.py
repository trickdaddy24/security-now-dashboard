from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

TWIT_SN_FEED = "https://feeds.twit.tv/sn.xml"
CACHE_FILE = ".sn-twit-thumb-cache.json"
CACHE_TTL_SECONDS = 24 * 3600
USER_AGENT = "SecurityNowDashboard/1.0"

_NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


def _cache_path(download_dir: Path) -> Path:
    return Path(download_dir) / CACHE_FILE


def _parse_episode_items(xml_text: str) -> dict[int, str]:
    root = ET.fromstring(xml_text)
    out: dict[int, str] = {}
    for item in root.findall("./channel/item"):
        ep_num: int | None = None
        for tag in ("itunes:episode", "podcast:episode"):
            el = item.find(tag, _NS) if ":" in tag else item.find(tag)
            if el is not None and el.text and str(el.text).strip().isdigit():
                ep_num = int(el.text.strip())
                break
        if ep_num is None:
            title = (item.findtext("title") or "").strip()
            m = re.search(r"\bSN\s+(\d+)\b", title, re.I)
            if m:
                ep_num = int(m.group(1))
        if ep_num is None:
            continue

        thumb = None
        img = item.find("itunes:image", _NS)
        if img is not None and img.get("href"):
            thumb = img.get("href")
        if not thumb:
            mt = item.find("media:content/media:thumbnail", _NS)
            if mt is not None and mt.get("url"):
                thumb = mt.get("url")
        if thumb:
            out[ep_num] = thumb.strip()
    return out


async def refresh_thumb_cache(
    download_dir: Path,
    *,
    verify_ssl: bool = True,
    client: httpx.AsyncClient | None = None,
) -> dict[int, str]:
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=60.0, verify=verify_ssl, headers={"User-Agent": USER_AGENT})
    try:
        resp = await client.get(TWIT_SN_FEED)
        resp.raise_for_status()
        mapping = _parse_episode_items(resp.text)
        payload: dict[str, Any] = {
            "fetched_at": time.time(),
            "episodes": {str(k): v for k, v in mapping.items()},
        }
        _cache_path(download_dir).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log.info("TWiT thumb cache refreshed (%d episodes)", len(mapping))
        return mapping
    finally:
        if owns:
            await client.aclose()


def load_thumb_cache(download_dir: Path) -> dict[int, str]:
    path = _cache_path(download_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        episodes = data.get("episodes") or {}
        return {int(k): str(v) for k, v in episodes.items()}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


def cache_is_stale(download_dir: Path) -> bool:
    path = _cache_path(download_dir)
    if not path.is_file():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched = float(data.get("fetched_at", 0))
        return (time.time() - fetched) > CACHE_TTL_SECONDS
    except (json.JSONDecodeError, ValueError, TypeError):
        return True


async def get_thumb_url(
    download_dir: Path,
    episode: int,
    *,
    verify_ssl: bool = True,
) -> str | None:
    cache = load_thumb_cache(download_dir)
    if cache_is_stale(download_dir) or episode not in cache:
        cache = await refresh_thumb_cache(download_dir, verify_ssl=verify_ssl)
    return cache.get(episode)


def thumb_paths_for_video(video_path: Path) -> tuple[Path, Path]:
    """Plex/Kodi local art: -thumb.jpg and -fanart.jpg beside the video."""
    base = video_path.with_suffix("")
    return base.with_name(base.name + "-thumb.jpg"), base.with_name(base.name + "-fanart.jpg")


async def download_episode_art(
    download_dir: Path,
    episode: int,
    video_path: Path,
    *,
    verify_ssl: bool = True,
) -> bool:
    url = await get_thumb_url(download_dir, episode, verify_ssl=verify_ssl)
    if not url:
        log.warning("No TWiT thumb for episode %s", episode)
        return False
    thumb_path, fanart_path = thumb_paths_for_video(video_path)
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.write_bytes(data)
        fanart_path.write_bytes(data)
        log.info("Saved episode art for #%s → %s", episode, thumb_path.name)
        return True
    except Exception:
        log.exception("Failed to download thumb for episode %s", episode)
        return False


async def fetch_thumbs_for_library(
    download_dir: Path,
    *,
    verify_ssl: bool = True,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Download Plex/Kodi art for every video file in the local library."""
    from .library import scan_library

    fetched: list[int] = []
    skipped: list[int] = []
    missing: list[int] = []
    errors: list[str] = []

    for entry in scan_library(download_dir, verify_checksums=False):
        video_path: Path | None = None
        for media_key in ("video_hd", "video_hq", "video_lq"):
            finfo = entry.files.get(media_key)
            if finfo:
                video_path = download_dir / finfo.filename
                break
        if video_path is None or not video_path.is_file():
            continue
        thumb_path, _ = thumb_paths_for_video(video_path)
        if skip_existing and thumb_path.is_file() and thumb_path.stat().st_size > 0:
            skipped.append(entry.number)
            continue
        try:
            ok = await download_episode_art(
                download_dir,
                entry.number,
                video_path,
                verify_ssl=verify_ssl,
            )
            if ok:
                fetched.append(entry.number)
            else:
                missing.append(entry.number)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ep {entry.number}: {exc}")
            log.exception("Thumb fetch failed for episode %s", entry.number)

    return {
        "ok": not errors,
        "fetched": fetched,
        "fetched_count": len(fetched),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "missing": missing,
        "missing_count": len(missing),
        "errors": errors,
    }