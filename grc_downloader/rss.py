from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.dom import minidom

from .library import EpisodeEntry, scan_library

RSS_STATE_FILE = ".sn-rss-built.json"

FEED_NAMES = {
    "audio": "security_now_audio.rss",
    "video": "security_now_video.rss",
    "text": "security_now_text.rss",
    "all": "security_now.rss",
}

AUDIO_MEDIA = {"audio_hq", "audio_lq", "audio_twit"}
VIDEO_MEDIA = {"video_hd", "video_hq", "video_lq"}
TEXT_MEDIA = {"transcript_txt", "transcript_pdf", "transcript_html", "show_notes"}


def _enclosure_url(download_dir: Path, filename: str, base_url: str | None) -> str:
    if base_url:
        base = base_url.rstrip("/")
        return f"{base}/media/{filename}"
    return Path(download_dir / filename).resolve().as_uri()


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _read_transcript_excerpt(download_dir: Path, entry: EpisodeEntry, limit: int) -> str:
    for key in ("transcript_txt", "show_notes"):
        finfo = entry.files.get(key)
        if not finfo:
            continue
        path = download_dir / finfo.filename
        if key == "transcript_txt" and path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                return _truncate(text, limit)
            except OSError:
                continue
    title = entry.title or f"Episode {entry.number}"
    return _truncate(title, limit)


def _item_element(
    entry: EpisodeEntry,
    media_key: str,
    finfo: Any,
    download_dir: Path,
    base_url: str | None,
    desc_limit: int,
) -> ET.Element | None:
    item = ET.Element("item")
    title = entry.title or f"Security Now #{entry.number}"
    ET.SubElement(item, "title").text = f"#{entry.number}: {title}"
    ET.SubElement(item, "description").text = _read_transcript_excerpt(download_dir, entry, desc_limit)
    pub = entry.date or ""
    if pub:
        ET.SubElement(item, "pubDate").text = pub
    guid = ET.SubElement(item, "guid")
    guid.text = f"sn-{entry.number:04d}-{media_key}"
    guid.set("isPermaLink", "false")

    mime = "audio/mpeg"
    if media_key.startswith("video"):
        mime = "video/mp4"
    elif media_key.endswith("pdf"):
        mime = "application/pdf"
    elif media_key.endswith("txt"):
        mime = "text/plain"
    elif media_key.endswith("html") or finfo.filename.endswith(".htm"):
        mime = "text/html"

    enc = ET.SubElement(item, "enclosure")
    enc.set("url", _enclosure_url(download_dir, finfo.filename, base_url))
    enc.set("length", str(finfo.bytes))
    enc.set("type", mime)
    return item


def _build_channel(
    title: str,
    description: str,
    link: str,
    items: list[ET.Element],
) -> bytes:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "generator").text = "security-now-dashboard"
    for item in items:
        channel.append(item)
    rough = ET.tostring(rss, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="UTF-8")


def build_feeds(
    download_dir: Path,
    *,
    rss_dir: Path | None = None,
    base_url: str | None = None,
    desc_limit: int = 500,
    which: set[str] | None = None,
) -> dict[str, Any]:
    download_dir = Path(download_dir)
    out_dir = Path(rss_dir) if rss_dir else download_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    which = which or set(FEED_NAMES.keys())

    entries = scan_library(download_dir)
    built: dict[str, str] = {}
    counts: dict[str, int] = {}

    def collect(media_set: set[str]) -> list[ET.Element]:
        items: list[ET.Element] = []
        for entry in sorted(entries, key=lambda e: e.number, reverse=True):
            for media_key, finfo in entry.files.items():
                if media_key in media_set:
                    el = _item_element(entry, media_key, finfo, download_dir, base_url, desc_limit)
                    if el is not None:
                        items.append(el)
        return items

    specs = [
        ("audio", "Security Now — Audio", AUDIO_MEDIA),
        ("video", "Security Now — Video", VIDEO_MEDIA),
        ("text", "Security Now — Text", TEXT_MEDIA),
        ("all", "Security Now — All Media", AUDIO_MEDIA | VIDEO_MEDIA | TEXT_MEDIA),
    ]

    for key, feed_title, media_set in specs:
        if key not in which:
            continue
        items = collect(media_set)
        xml = _build_channel(
            feed_title,
            "Personal Security Now archive",
            base_url or "https://www.grc.com/securitynow.htm",
            items,
        )
        path = out_dir / FEED_NAMES[key]
        path.write_bytes(xml)
        built[key] = str(path)
        counts[key] = len(items)

    state = {
        "built_at": time.time(),
        "feeds": built,
        "counts": counts,
        "base_url": base_url,
    }
    (download_dir / RSS_STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def rss_status(download_dir: Path) -> dict[str, Any]:
    path = download_dir / RSS_STATE_FILE
    if not path.is_file():
        return {"built_at": None, "feeds": {}, "counts": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"built_at": None, "feeds": {}, "counts": {}}