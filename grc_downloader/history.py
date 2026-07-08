from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def append_history(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_recent(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def new_batch_id() -> str:
    return str(uuid.uuid4())


def batch_started_record(batch_id: str, episodes: list[int], media: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "type": "batch_started",
        "batch_id": batch_id,
        "ts": time.time(),
        "episodes": episodes,
        "media": media,
        **extra,
    }


def job_finished_record(batch_id: str, job: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "job_finished",
        "batch_id": batch_id,
        "ts": time.time(),
        "job": job,
    }


def batch_finished_record(batch_id: str, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "type": "batch_finished",
        "batch_id": batch_id,
        "ts": time.time(),
        "counts": counts,
    }


def read_batches(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Aggregate batch_started / batch_finished pairs from JSONL history."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    batches: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        batch_id = ev.get("batch_id")
        if not batch_id:
            continue
        if ev.get("type") == "batch_started":
            if batch_id not in batches:
                order.append(batch_id)
            batches[batch_id] = {
                "batch_id": batch_id,
                "started_at": ev.get("ts"),
                "episodes": ev.get("episodes", []),
                "media": ev.get("media", []),
                "parallel": ev.get("parallel"),
                "filename_format": ev.get("filename_format"),
                "retry_failed": ev.get("retry_failed", False),
            }
        elif ev.get("type") == "batch_finished" and batch_id in batches:
            batches[batch_id]["finished_at"] = ev.get("ts")
            batches[batch_id]["counts"] = ev.get("counts", {})

    out = [batches[bid] for bid in order if bid in batches]
    return out[-limit:][::-1]