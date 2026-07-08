from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def sidecar_path(download_dir: Path, episode: int) -> Path:
    return download_dir / f"sn-{episode:04d}.meta.json"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def update_sidecar(
    download_dir: Path,
    episode: int,
    *,
    title: str,
    date_label: str,
    media: str,
    filename: str,
    url: str,
    file_path: Path,
) -> dict[str, Any]:
    path = sidecar_path(download_dir, episode)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    files = data.get("files", {})
    files[media] = {
        "filename": filename,
        "url": url,
        "bytes": file_path.stat().st_size,
        "sha256": file_sha256(file_path),
        "downloaded_at": time.time(),
    }

    data.update({
        "episode": episode,
        "title": title,
        "date": date_label,
        "updated_at": time.time(),
        "files": files,
    })
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data