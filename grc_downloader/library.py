from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .metadata import file_sha256, sidecar_path

EPISODE_RE = re.compile(r"(?:^sn-|^sn)(\d{3,4})", re.I)
KODI_RE = re.compile(r"E(\d{3,4})", re.I)
ORDERED_RE = re.compile(r"^(\d{3,4})\s")
LEGACY_RE = re.compile(r"sn-(\d{4})")

AUDIO_EXTS = {".mp3"}
VIDEO_EXTS = {".mp4", ".m4v"}
TEXT_EXTS = {".txt", ".pdf", ".htm", ".html"}

FORMAT_KEYS: dict[str, str] = {
    "audio_hq": "audio_hq",
    "audio_lq": "audio_lq",
    "audio_twit": "audio_twit",
    "video_hd": "video_hd",
    "video_hq": "video_hq",
    "video_lq": "video_lq",
    "transcript_txt": "transcript_txt",
    "transcript_pdf": "transcript_pdf",
    "transcript_html": "transcript_html",
    "show_notes": "show_notes",
}


@dataclass
class FileEntry:
    filename: str
    media: str
    bytes: int
    sha256: str | None = None
    checksum_ok: bool | None = None


@dataclass
class EpisodeEntry:
    number: int
    title: str | None = None
    date: str | None = None
    files: dict[str, FileEntry] = field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        return sum(f.bytes for f in self.files.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "date": self.date,
            "formats": list(self.files.keys()),
            "files": {
                k: {
                    "filename": v.filename,
                    "bytes": v.bytes,
                    "sha256": v.sha256,
                    "checksum_ok": v.checksum_ok,
                }
                for k, v in self.files.items()
            },
            "total_bytes": self.total_bytes,
        }


def _episode_from_name(name: str) -> int | None:
    for pattern in (LEGACY_RE, EPISODE_RE, KODI_RE, ORDERED_RE):
        m = pattern.search(name)
        if m:
            return int(m.group(1))
    return None


def _classify_file(path: Path) -> tuple[int | None, str | None]:
    name = path.name.lower()
    ep = _episode_from_name(path.name)
    if ep is None:
        return None, None

    ext = path.suffix.lower()
    if ext in AUDIO_EXTS:
        if "-lq" in name:
            return ep, "audio_lq"
        if "-twit" in name:
            return ep, "audio_twit"
        return ep, "audio_hq"
    if ext in VIDEO_EXTS:
        if "_hd" in name or "-hd" in name:
            return ep, "video_hd"
        if "_hq" in name or "-hq" in name:
            return ep, "video_hq"
        if "_lq" in name or "-lq" in name:
            return ep, "video_lq"
        return ep, "video_hq"
    if ext == ".txt":
        return ep, "transcript_txt"
    if ext == ".pdf":
        if "-notes" in name or "notes" in name:
            return ep, "show_notes"
        return ep, "transcript_pdf"
    if ext in (".htm", ".html"):
        return ep, "transcript_html"
    return ep, None


def _load_sidecars(download_dir: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for path in download_dir.glob("**/sn-*.meta.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ep = int(data.get("episode", 0))
            if ep:
                out[ep] = data
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return out


def scan_library(download_dir: Path, *, verify_checksums: bool = False) -> list[EpisodeEntry]:
    download_dir = Path(download_dir)
    sidecars = _load_sidecars(download_dir)
    episodes: dict[int, EpisodeEntry] = {}

    for path in download_dir.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name.endswith(".meta.json") or path.suffix == ".part":
            continue

        ep_num, media = _classify_file(path)
        if ep_num is None or media is None:
            continue

        entry = episodes.get(ep_num)
        if not entry:
            meta = sidecars.get(ep_num, {})
            entry = EpisodeEntry(
                number=ep_num,
                title=meta.get("title"),
                date=meta.get("date"),
            )
            episodes[ep_num] = entry

        sidecar_file = (sidecars.get(ep_num, {}).get("files") or {}).get(media, {})
        expected_hash = sidecar_file.get("sha256")
        checksum_ok: bool | None = None
        if expected_hash and verify_checksums:
            try:
                checksum_ok = file_sha256(path) == expected_hash
            except OSError:
                checksum_ok = False

        try:
            rel_name = str(path.relative_to(download_dir))
        except ValueError:
            rel_name = path.name
        entry.files[media] = FileEntry(
            filename=rel_name.replace("\\", "/"),
            media=media,
            bytes=path.stat().st_size,
            sha256=expected_hash,
            checksum_ok=checksum_ok,
        )

    for ep_num, meta in sidecars.items():
        if ep_num not in episodes:
            episodes[ep_num] = EpisodeEntry(
                number=ep_num,
                title=meta.get("title"),
                date=meta.get("date"),
            )

    return sorted(episodes.values(), key=lambda e: e.number, reverse=True)


def missing_episodes(local: list[int], latest: int) -> list[int]:
    if not latest or not local:
        return list(range(1, latest + 1)) if latest else []
    have = set(local)
    return [n for n in range(1, latest + 1) if n not in have]


def missing_formats(
    entry: EpisodeEntry,
    expected: list[str] | None = None,
) -> list[str]:
    expected = expected or ["audio_hq", "transcript_txt", "show_notes"]
    return [fmt for fmt in expected if fmt not in entry.files]


def storage_by_media(entries: list[EpisodeEntry]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for entry in entries:
        for media, finfo in entry.files.items():
            totals[media] = totals.get(media, 0) + finfo.bytes
    return totals


def library_summary(
    download_dir: Path,
    latest_remote: int,
    expected_formats: list[str] | None = None,
    disk_free_bytes: int | None = None,
    *,
    verify_checksums: bool = False,
) -> dict[str, Any]:
    entries = scan_library(download_dir, verify_checksums=verify_checksums)
    numbers = [e.number for e in entries]
    gaps = missing_episodes(numbers, latest_remote) if latest_remote else []

    missing_fmt_report: list[dict[str, Any]] = []
    checksum_failures: list[dict[str, Any]] = []
    total_bytes = 0

    for entry in entries:
        total_bytes += entry.total_bytes
        missing = missing_formats(entry, expected_formats)
        if missing:
            missing_fmt_report.append({"episode": entry.number, "missing": missing})
        for media, finfo in entry.files.items():
            if finfo.checksum_ok is False:
                checksum_failures.append({
                    "episode": entry.number,
                    "media": media,
                    "filename": finfo.filename,
                })

    media_bytes = storage_by_media(entries)
    sync_ok = None
    if latest_remote and numbers:
        sync_ok = max(numbers) >= latest_remote

    disk_free_pct = None
    if disk_free_bytes is not None and disk_free_bytes >= 0:
        denom = total_bytes + disk_free_bytes
        if denom > 0:
            disk_free_pct = round((disk_free_bytes / denom) * 100, 1)

    return {
        "episode_count": len(entries),
        "total_bytes": total_bytes,
        "storage_by_media": media_bytes,
        "disk_free_bytes": disk_free_bytes,
        "disk_free_pct": disk_free_pct,
        "latest_local": max(numbers) if numbers else None,
        "latest_remote": latest_remote,
        "sync_ok": sync_ok,
        "missing_episodes": gaps[:200],
        "missing_episode_count": len(gaps),
        "missing_formats": missing_fmt_report[:100],
        "checksum_failures": checksum_failures,
        "episodes": [e.to_dict() for e in entries[:500]],
    }