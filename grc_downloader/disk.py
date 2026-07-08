from __future__ import annotations

import shutil
from pathlib import Path

from .models import ESTIMATED_BYTES, MediaType


def free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def estimate_batch_bytes(episodes: list[int], media_types: list[MediaType]) -> int:
    per_ep = sum(ESTIMATED_BYTES.get(m, 50 * 1024 * 1024) for m in media_types)
    return per_ep * len(episodes)


def check_disk_space(
    path: Path,
    episodes: list[int],
    media_types: list[MediaType],
    min_free_mb: int = 500,
) -> tuple[bool, str]:
    needed = estimate_batch_bytes(episodes, media_types)
    reserve = min_free_mb * 1024 * 1024
    free = free_bytes(path)
    required = needed + reserve
    if free >= required:
        return True, ""
    return (
        False,
        f"Need ~{_human(needed)} + {_human(reserve)} reserve; only {_human(free)} free on disk",
    )


def _human(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} TB"