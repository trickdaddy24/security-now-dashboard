from __future__ import annotations

import re
from typing import Iterable

import httpx

from .circuit import CircuitBreaker
from .http_retry import get_with_retry
from .models import EpisodeInfo, MediaType

GRC_CIRCUIT = CircuitBreaker()

GRC_ARCHIVE_URL = "https://www.grc.com/securitynow.htm"
USER_AGENT = "SecurityNowDashboard/1.0 (+fork of GRC-Downloader concept)"


def media_url(episode: int, media: MediaType) -> str:
    ep = f"{episode:04d}"
    base = "https://www.grc.com/sn"
    # TWiT retired cachefly _hq/_hd/_lq URLs; video is Megaphone → 1080p H.264 only.
    video_sn = f"sn{episode}"
    video_file = f"{video_sn}_h264m_1920x1080.mp4"
    video_url = (
        f"https://pscrb.fm/rss/p/mgln.ai/e/294/cdn.twit.tv/video/sn/"
        f"{video_sn}/{video_file}"
    )
    mapping = {
        MediaType.AUDIO_HQ: f"https://media.grc.com/sn/sn-{ep}.mp3",
        MediaType.AUDIO_LQ: f"https://media.grc.com/sn/sn-{ep}-lq.mp3",
        MediaType.AUDIO_TWIT: f"https://cdn.twit.tv/audio/sn/sn{episode}/sn{episode}.mp3",
        MediaType.VIDEO_HD: video_url,
        MediaType.VIDEO_HQ: video_url,
        MediaType.VIDEO_LQ: video_url,
        MediaType.TRANSCRIPT_TXT: f"{base}/sn-{ep}.txt",
        MediaType.TRANSCRIPT_PDF: f"{base}/sn-{ep}.pdf",
        MediaType.TRANSCRIPT_HTML: f"{base}/sn-{ep}.htm",
        MediaType.SHOW_NOTES: f"{base}/sn-{ep}-notes.pdf",
    }
    return mapping[media]


async def fetch_catalog(
    client: httpx.AsyncClient | None = None,
    *,
    verify_ssl: bool = True,
) -> tuple[list[EpisodeInfo], int]:
    """Return episodes from the GRC archive page (newest first) and latest episode number."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=verify_ssl,
            headers={"User-Agent": USER_AGENT},
        )
    if GRC_CIRCUIT.is_open():
        raise RuntimeError("GRC catalog circuit breaker is open — try again later")
    try:
        resp = await get_with_retry(client, GRC_ARCHIVE_URL)
        GRC_CIRCUIT.record_success()
        return _parse_catalog_html(resp.text)
    except Exception:
        GRC_CIRCUIT.record_failure()
        raise
    finally:
        if owns:
            await client.aclose()


def _parse_catalog_html(html: str) -> tuple[list[EpisodeInfo], int]:
    episodes: list[EpisodeInfo] = []
    pattern = re.compile(
        r"Episode&nbsp;#(\d+)\s*\|\s*([^|<]+)"
        r"(?:\s*\|\s*([^<]+?)\s*min\.)?"
        r".*?<font size=2><b>([^<]+)</b>",
        re.DOTALL,
    )

    for m in pattern.finditer(html):
        number = int(m.group(1))
        date_label = m.group(2).strip()
        duration_raw = (m.group(3) or "").strip()
        duration = duration_raw if duration_raw and duration_raw != "..." else None
        title = m.group(4).strip()

        if any(e.number == number for e in episodes):
            continue
        episodes.append(
            EpisodeInfo(
                number=number,
                title=title,
                date_label=date_label,
                duration=duration,
            )
        )

    episodes.sort(key=lambda e: e.number, reverse=True)
    latest = episodes[0].number if episodes else 0
    return episodes, latest


def parse_episode_range(
    spec: str,
    latest: int,
    local_next: int | None = None,
) -> list[int]:
    """Parse episode spec like '1086', '1080:1086', '1080:latest', 'all', 'next'."""
    spec = (spec or "").strip().lower()
    if not spec or spec == "next":
        start = local_next or 1
        return [start] if start <= latest else []
    if spec in {"latest", "-latest"}:
        return [latest] if latest else []
    if spec == "all":
        return list(range(1, latest + 1)) if latest else []

    if ":" in spec:
        left, right = spec.split(":", 1)
        start = int(left)
        end = latest if right.strip() in {"latest", "max"} else int(right)
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    return [int(spec)]