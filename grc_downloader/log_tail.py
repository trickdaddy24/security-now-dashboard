from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def tail_log_events(log_file: Path | None, *, limit: int = 80) -> list[dict[str, Any]]:
    """Return the most recent structured log lines (newest first)."""
    if not log_file or not log_file.is_file():
        return []
    limit = max(1, min(limit, 500))
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                events.append(_normalize_event(row))
            else:
                events.append({"ts": None, "level": "INFO", "message": str(row)})
        except json.JSONDecodeError:
            events.append({"ts": None, "level": "INFO", "message": line})
        if len(events) >= limit:
            break
    return events


def _normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ts": row.get("ts"),
        "level": row.get("level", "INFO"),
        "message": row.get("message", ""),
        "logger": row.get("logger"),
    }
    for key in ("episode", "media", "batch_id", "job_id", "job_filename", "status_code", "url"):
        if key in row and row[key] is not None:
            out[key] = row[key]
    if row.get("exception"):
        out["exception"] = row["exception"]
    return out