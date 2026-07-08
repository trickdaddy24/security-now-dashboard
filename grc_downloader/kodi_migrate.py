from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .filenames import build_filename
from .library import scan_library
from .metadata import sidecar_path, update_sidecar
from .models import MediaType
from .paths import media_rel_path
from .twit_thumbs import thumb_paths_for_video

log = logging.getLogger(__name__)

_MEDIA_FROM_KEY = {m.value: m for m in MediaType}


def _resolve_media(media_key: str) -> MediaType | None:
    return _MEDIA_FROM_KEY.get(media_key)


def migrate_filenames_to_kodi(
    download_dir: Path,
    *,
    episode_folders: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rename on-disk files to Kodi layout using sidecar title/date metadata."""
    download_dir = Path(download_dir)
    renamed: list[dict[str, Any]] = []
    skipped: list[str] = []
    errors: list[str] = []

    for entry in scan_library(download_dir, verify_checksums=False):
        meta_path = sidecar_path(download_dir, entry.number, episode_folders=episode_folders)
        meta: dict[str, Any] = {}
        if meta_path.is_file():
            try:
                import json

                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        title = entry.title or meta.get("title") or f"Episode {entry.number}"
        date_label = entry.date or meta.get("date") or ""

        for media_key, finfo in entry.files.items():
            media = _resolve_media(media_key)
            if media is None:
                skipped.append(finfo.filename)
                continue
            new_base = build_filename(
                entry.number,
                media,
                title=title,
                date_label=date_label,
                fmt="kodi",
            )
            new_rel = media_rel_path(entry.number, new_base, episode_folders=episode_folders)
            if finfo.filename.replace("\\", "/") == new_rel:
                continue
            old_path = download_dir / finfo.filename
            new_path = download_dir / new_rel
            if not old_path.is_file():
                errors.append(f"missing: {finfo.filename}")
                continue
            if new_path.exists() and new_path.resolve() != old_path.resolve():
                errors.append(f"target exists: {new_rel}")
                continue
            record = {"episode": entry.number, "media": media_key, "from": finfo.filename, "to": new_rel}
            if dry_run:
                renamed.append(record)
                continue
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            if media in (MediaType.VIDEO_HD, MediaType.VIDEO_HQ, MediaType.VIDEO_LQ):
                old_thumb, old_fan = thumb_paths_for_video(old_path)
                new_thumb, new_fan = thumb_paths_for_video(new_path)
                for old_art, new_art in ((old_thumb, new_thumb), (old_fan, new_fan)):
                    if old_art.is_file() and not new_art.exists():
                        new_art.parent.mkdir(parents=True, exist_ok=True)
                        old_art.rename(new_art)
            update_sidecar(
                download_dir,
                entry.number,
                title=title,
                date_label=date_label,
                media=media_key,
                filename=new_rel,
                url=meta.get("files", {}).get(media_key, {}).get("url", ""),
                file_path=new_path,
                episode_folders=episode_folders,
            )
            renamed.append(record)
            log.info("Renamed %s → %s", finfo.filename, new_rel)

    return {
        "ok": not errors,
        "renamed": renamed,
        "renamed_count": len(renamed),
        "skipped": skipped,
        "errors": errors,
    }