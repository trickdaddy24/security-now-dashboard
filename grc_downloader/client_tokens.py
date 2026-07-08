from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TOKENS_FILE = ".sn-client-tokens.json"
TOKEN_TTL_SECONDS = 24 * 3600


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _prune(data: dict[str, Any], now: float) -> dict[str, Any]:
    return {
        token: entry
        for token, entry in data.items()
        if now - float(entry.get("ts", 0)) < TOKEN_TTL_SECONDS
    }


def lookup_token(download_dir: Path, token: str) -> str | None:
    path = download_dir / TOKENS_FILE
    data = _prune(_load(path), time.time())
    existing = data.get(token)
    if existing:
        return str(existing.get("batch_id"))
    return None


def claim_token(download_dir: Path, token: str, batch_id: str) -> tuple[bool, str | None]:
    """Register a client token. Returns (is_new, existing_batch_id)."""
    path = download_dir / TOKENS_FILE
    now = time.time()
    data = _prune(_load(path), now)

    existing = data.get(token)
    if existing:
        return False, str(existing.get("batch_id"))

    data[token] = {"batch_id": batch_id, "ts": now}
    _save(path, data)
    return True, None