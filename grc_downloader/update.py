from __future__ import annotations

import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
RELEASES_URL = "https://api.github.com/repos/trickdaddy24/security-now-dashboard/releases/latest"


def current_version() -> str:
    if VERSION_FILE.is_file():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _parse_version(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) if parts else (0,)


async def check_for_update() -> dict[str, str | bool]:
    current = current_version()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            latest = resp.json().get("tag_name", "").lstrip("v")
    except Exception as exc:  # noqa: BLE001
        return {
            "current": current,
            "latest": current,
            "update_available": False,
            "error": str(exc),
        }

    update_available = _parse_version(latest) > _parse_version(current)
    return {
        "current": current,
        "latest": latest,
        "update_available": update_available,
        "url": "https://github.com/trickdaddy24/security-now-dashboard/releases/latest",
    }