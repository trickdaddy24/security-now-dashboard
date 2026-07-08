from __future__ import annotations

from dataclasses import dataclass
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
    VIDEO_HD = "video_hd"
    VIDEO_HQ = "video_hq"
    VIDEO_LQ = "video_lq"
    TRANSCRIPT_TXT = "transcript_txt"
    TRANSCRIPT_PDF = "transcript_pdf"
    TRANSCRIPT_HTML = "transcript_html"
    SHOW_NOTES = "show_notes"


MEDIA_LABELS: dict[MediaType, str] = {
    MediaType.AUDIO_HQ: "Audio HQ (GRC)",
    MediaType.AUDIO_LQ: "Audio LQ",
    MediaType.AUDIO_TWIT: "Audio HQ (TWiT CDN)",
    MediaType.VIDEO_HD: "Video HD (TWiT)",
    MediaType.VIDEO_HQ: "Video HQ (TWiT)",
    MediaType.VIDEO_LQ: "Video LQ (TWiT)",
    MediaType.TRANSCRIPT_TXT: "Transcript (.txt)",
    MediaType.TRANSCRIPT_PDF: "Transcript (.pdf)",
    MediaType.TRANSCRIPT_HTML: "Transcript (.html)",
    MediaType.SHOW_NOTES: "Show Notes (.pdf)",
}

# Conservative per-file estimates for disk pre-check (bytes)
ESTIMATED_BYTES: dict[MediaType, int] = {
    MediaType.AUDIO_HQ: 75 * 1024 * 1024,
    MediaType.AUDIO_LQ: 20 * 1024 * 1024,
    MediaType.AUDIO_TWIT: 75 * 1024 * 1024,
    MediaType.VIDEO_HD: 2 * 1024 * 1024 * 1024,
    MediaType.VIDEO_HQ: 650 * 1024 * 1024,
    MediaType.VIDEO_LQ: 200 * 1024 * 1024,
    MediaType.TRANSCRIPT_TXT: 200 * 1024,
    MediaType.TRANSCRIPT_PDF: 400 * 1024,
    MediaType.TRANSCRIPT_HTML: 250 * 1024,
    MediaType.SHOW_NOTES: 600 * 1024,
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
    date_label: str = ""


@dataclass
class DownloadJob:
    id: str
    episode: int
    media: MediaType
    title: str
    url: str
    filename: str
    date_label: str = ""
    status: JobStatus = JobStatus.QUEUED
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    speed_bps: float = 0.0
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        pct = None
        eta_seconds: float | None = None
        if self.total_bytes and self.total_bytes > 0:
            pct = min(100.0, (self.bytes_downloaded / self.total_bytes) * 100.0)
        if (
            self.status == JobStatus.RUNNING
            and self.speed_bps > 0
            and self.total_bytes
            and self.bytes_downloaded < self.total_bytes
        ):
            eta_seconds = (self.total_bytes - self.bytes_downloaded) / self.speed_bps
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
            "eta_seconds": eta_seconds,
            "eta_human": _human_eta(eta_seconds),
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def _human_eta(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


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