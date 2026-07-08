from __future__ import annotations

import csv
import io
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .history import read_batches


def batch_timeline(history_path: Path, limit: int = 30) -> list[dict[str, Any]]:
    batches = read_batches(history_path, limit=limit)
    out: list[dict[str, Any]] = []
    for b in batches:
        counts = b.get("counts") or {}
        out.append({
            "batch_id": b.get("batch_id"),
            "started_at": b.get("started_at"),
            "finished_at": b.get("finished_at"),
            "episodes": b.get("episodes", []),
            "media": b.get("media", []),
            "retry_failed": b.get("retry_failed", False),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "total": sum(counts.values()) if counts else 0,
        })
    return out


def weekly_downloads(history_path: Path, days: int = 90) -> list[dict[str, Any]]:
    if not history_path.is_file():
        return []
    cutoff = time.time() - days * 86400
    week_counts: dict[str, int] = defaultdict(int)

    for line in history_path.read_text(encoding="utf-8").strip().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "job_finished":
            continue
        ts = ev.get("ts", 0)
        if ts < cutoff:
            continue
        job = ev.get("job") or {}
        if job.get("status") != "completed":
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        week_key = dt.strftime("%Y-W%W")
        week_counts[week_key] += 1

    return [
        {"week": week, "completed": count}
        for week, count in sorted(week_counts.items())
    ][-26:]


def library_csv(episodes: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["episode", "title", "date", "formats", "total_bytes"])
    for ep in episodes:
        writer.writerow([
            ep.get("number"),
            ep.get("title") or "",
            ep.get("date") or "",
            ";".join(ep.get("formats") or []),
            ep.get("total_bytes", 0),
        ])
    return buf.getvalue()