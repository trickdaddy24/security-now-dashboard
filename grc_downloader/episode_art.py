from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

TWIT_EPISODE_URL = "https://twit.tv/shows/security-now/episodes/{episode}"
YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})"
)
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"

# Browser-like headers — elroy.twit.tv returns 403 for bot-style User-Agents.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def is_valid_image(data: bytes) -> bool:
    if len(data) < 512:
        return False
    return data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC)


def youtube_thumb_candidates(video_id: str) -> list[str]:
    return [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
    ]


def parse_youtube_id(html: str) -> str | None:
    m = YOUTUBE_ID_RE.search(html)
    return m.group(1) if m else None


async def resolve_youtube_video_id(
    episode: int,
    *,
    verify_ssl: bool = True,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=30.0, verify=verify_ssl, headers=DEFAULT_HEADERS)
    try:
        resp = await client.get(TWIT_EPISODE_URL.format(episode=episode))
        resp.raise_for_status()
        return parse_youtube_id(resp.text)
    except Exception:
        log.debug("Could not resolve YouTube id for episode %s", episode, exc_info=True)
        return None
    finally:
        if owns:
            await client.aclose()


async def download_image_url(
    url: str,
    *,
    verify_ssl: bool = True,
    referer: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> bytes | None:
    owns = client is None
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    if owns:
        client = httpx.AsyncClient(timeout=30.0, verify=verify_ssl, headers=headers)
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.content
        if not is_valid_image(data):
            log.warning("URL did not return a valid image (%s, %d bytes)", url, len(data))
            return None
        return data
    except Exception:
        log.debug("Image download failed for %s", url, exc_info=True)
        return None
    finally:
        if owns:
            await client.aclose()


async def fetch_episode_art_bytes(
    download_dir: Path,
    episode: int,
    *,
    verify_ssl: bool = True,
) -> tuple[bytes | None, str]:
    """Return image bytes and source label (youtube|twit|none)."""
    from .twit_thumbs import get_thumb_url

    async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl, headers=DEFAULT_HEADERS) as client:
        video_id = await resolve_youtube_video_id(episode, verify_ssl=verify_ssl, client=client)
        if video_id:
            for url in youtube_thumb_candidates(video_id):
                data = await download_image_url(url, verify_ssl=verify_ssl, client=client)
                if data:
                    log.info("Episode %s art from YouTube (%s)", episode, video_id)
                    return data, "youtube"

        twit_url = await get_thumb_url(download_dir, episode, verify_ssl=verify_ssl)
        if twit_url:
            data = await download_image_url(
                twit_url,
                verify_ssl=verify_ssl,
                referer="https://twit.tv/",
                client=client,
            )
            if data:
                log.info("Episode %s art from TWiT RSS", episode)
                return data, "twit"

    return None, "none"


def art_cache_path(download_dir: Path) -> Path:
    return Path(download_dir) / ".sn-episode-art-cache.json"


def record_art_fetch(download_dir: Path, episode: int, source: str, bytes_len: int) -> None:
    path = art_cache_path(download_dir)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    episodes = data.setdefault("episodes", {})
    episodes[str(episode)] = {
        "source": source,
        "bytes": bytes_len,
        "fetched_at": time.time(),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")