from __future__ import annotations

import re
from datetime import datetime

from .models import MediaType

SHOW_NAME = "Security Now"
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_component(text: str, max_len: int = 120) -> str:
    cleaned = INVALID_CHARS.sub("", text).strip()
    return cleaned[:max_len].rstrip(". ") or "episode"


def _episode_year(date_label: str, episode: int) -> int:
    for fmt in ("%d %b %Y", "%d %b%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_label.strip(), fmt).year
        except ValueError:
            continue
    return 2000 + max(0, min(99, episode // 52))


def _media_tag(media: MediaType) -> str:
    return {
        MediaType.AUDIO_HQ: "audio-hq",
        MediaType.AUDIO_LQ: "audio-lq",
        MediaType.AUDIO_TWIT: "audio-twit",
        MediaType.VIDEO_HD: "video-hd",
        MediaType.VIDEO_HQ: "video-hq",
        MediaType.VIDEO_LQ: "video-lq",
        MediaType.TRANSCRIPT_TXT: "transcript",
        MediaType.TRANSCRIPT_PDF: "transcript-pdf",
        MediaType.TRANSCRIPT_HTML: "transcript-html",
        MediaType.SHOW_NOTES: "notes",
    }[media]


def _extension(media: MediaType) -> str:
    return {
        MediaType.AUDIO_HQ: "mp3",
        MediaType.AUDIO_LQ: "mp3",
        MediaType.AUDIO_TWIT: "mp3",
        MediaType.VIDEO_HD: "mp4",
        MediaType.VIDEO_HQ: "mp4",
        MediaType.VIDEO_LQ: "mp4",
        MediaType.TRANSCRIPT_TXT: "txt",
        MediaType.TRANSCRIPT_PDF: "pdf",
        MediaType.TRANSCRIPT_HTML: "htm",
        MediaType.SHOW_NOTES: "pdf",
    }[media]


def build_filename(
    episode: int,
    media: MediaType,
    *,
    title: str = "",
    date_label: str = "",
    fmt: str = "raw",
) -> str:
    ext = _extension(media)
    ep4 = f"{episode:04d}"
    tag = _media_tag(media)

    preset = (fmt or "raw").strip().lower()
    if preset == "raw":
        if media == MediaType.AUDIO_TWIT:
            return f"sn-{ep4}-twit.mp3"
        if media == MediaType.AUDIO_LQ:
            return f"sn-{ep4}-lq.mp3"
        if media == MediaType.SHOW_NOTES:
            return f"sn-{ep4}-notes.pdf"
        if media in (MediaType.VIDEO_HD, MediaType.VIDEO_HQ, MediaType.VIDEO_LQ):
            return f"sn-{ep4}-{tag.split('-')[-1]}.mp4"
        return f"sn-{ep4}.{ext}"

    if preset == "ordered":
        name = sanitize_component(title or f"Episode {episode}")
        date = sanitize_component(date_label or "unknown-date", 32)
        return f"{episode:04d} {name} - {date} [{tag}].{ext}"

    if preset == "kodi":
        year = _episode_year(date_label, episode)
        stem = f"{SHOW_NAME} S{year}E{episode:04d}"
        # Video: clean name for Plex/Kodi (art saved as -thumb.jpg / -fanart.jpg)
        if media in (MediaType.VIDEO_HD, MediaType.VIDEO_HQ, MediaType.VIDEO_LQ):
            return f"{stem}.{ext}"
        return f"{stem} [{tag}].{ext}"

    return f"sn-{ep4}-{tag}.{ext}"