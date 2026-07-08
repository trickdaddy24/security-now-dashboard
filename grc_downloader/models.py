from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class MediaType(str, Enum):
    AUDIO_HQ = "audio_hq"
    AUDIO_LQ = "audio_lq"
    AUDIO_TWIT = "audio_twit"
    TRANSCRIPT_TXT = "transcript_txt"
    TRANSCRIPT_PDF = "transcript_pdf"
    TRANSCRIPT_HTML = "transcript_html"
    SHOW_NOTES = "show_notes"


MEDIA_LABELS: dict[MediaType, str] = {
    MediaType.AUDIO_HQ: "Audio HQ (GRC)",
    MediaType.AUDIO_LQ: "Audio LQ",
    MediaType.AUDIO_TWIT: "Audio HQ (TWiT CDN)",
    MediaType.TRANSCRIPT_TXT: "Transcript (.txt)",
    MediaType.TRANSCRIPT_PDF: "Transcript (.pdf)",
    MediaType.TRANSCRIPT_HTML: "Transcript (.html)",
    MediaType.SHOW_NOTES: "Show Notes (.pdf)",
}


@dataclass
class EpisodeInfo:
    number: int
    title: str
    date_label: str
    duration: str | None = None


@dataclass
class DownloadTask:
    episode: int
    media: MediaType
    url: str
    filename: str
    title: str = ""


@dataclass
class DownloadJob:
    id: str
    episode: int
    media: MediaType
    title: str
    url: str
    filename: str
    status: JobStatus = JobStatus.QUEUED
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    speed_bps: float = 0.0
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        pct = None
        if self.total_bytes and self.total_bytes > 0:
            pct = min(100.0, (self.bytes_downloaded / self.total_bytes) * 100.0)
        return {
            "id": self.id,
            "episode": self.episode,
            "media": self.media.value,
            "media_label": MEDIA_LABELS.get(self.media, self.media.value),
            "title": self.title,
            "url": self.url,
            "filename": self.filename,
            "status": self.status.value,
            "bytes_downloaded": self.bytes_downloaded,
            "total_bytes": self.total_bytes,
            "percent": pct,
            "speed_bps": self.speed_bps,
            "speed_human": _human_speed(self.speed_bps),
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def _human_speed(bps: float) -> str:
    if bps <= 0:
        return "—"
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    v = float(bps)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} GB/s"