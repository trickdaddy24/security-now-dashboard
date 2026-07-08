from __future__ import annotations

import time
from pathlib import Path


def cleanup_stale_parts(download_dir: Path, max_age_days: int = 7) -> list[str]:
    download_dir = Path(download_dir)
    cutoff = time.time() - max_age_days * 86400
    removed: list[str] = []
    for path in download_dir.glob("*.part"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path.name)
        except OSError:
            continue
    return removed