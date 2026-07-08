from __future__ import annotations

from typing import Any


def render_prometheus(snapshot: dict[str, Any], *, latest_episode: int = 0, errors_total: int = 0) -> str:
    counts = snapshot.get("counts") or {}
    active = counts.get("active", 0)
    failed = counts.get("failed", 0)
    completed = counts.get("completed", 0)
    bytes_done = snapshot.get("bytes_completed", 0)
    lines = [
        "# HELP sn_jobs_active Currently running download jobs",
        "# TYPE sn_jobs_active gauge",
        f"sn_jobs_active {active}",
        "# HELP sn_jobs_failed Failed jobs in current batch",
        "# TYPE sn_jobs_failed gauge",
        f"sn_jobs_failed {failed}",
        "# HELP sn_jobs_completed Completed jobs in current batch",
        "# TYPE sn_jobs_completed gauge",
        f"sn_jobs_completed {completed}",
        "# HELP sn_bytes_total Bytes completed in current batch snapshot",
        "# TYPE sn_bytes_total counter",
        f"sn_bytes_total {bytes_done}",
        "# HELP sn_last_episode_number Latest episode number from GRC catalog",
        "# TYPE sn_last_episode_number gauge",
        f"sn_last_episode_number {latest_episode}",
        "# HELP sn_errors_total Cumulative download errors (session)",
        "# TYPE sn_errors_total counter",
        f"sn_errors_total {errors_total}",
        "# HELP sn_batch_running Whether a batch is running (1=yes)",
        "# TYPE sn_batch_running gauge",
        f"sn_batch_running {1 if snapshot.get('running') else 0}",
    ]
    return "\n".join(lines) + "\n"