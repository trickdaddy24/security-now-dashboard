"""Insights and Phase 4 model tests — no network."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from grc_downloader.insights import batch_timeline, library_csv, weekly_downloads
from grc_downloader.models import DownloadJob, JobStatus, MediaType


def test_weekly_downloads() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "h.jsonl"
        path.write_text(
            json.dumps({
                "type": "job_finished",
                "batch_id": "b1",
                "ts": time.time() - 3600,
                "job": {"status": "completed", "episode": 1},
            }) + "\n",
            encoding="utf-8",
        )
        rows = weekly_downloads(path, days=365)
        assert len(rows) >= 1
        assert rows[0]["completed"] >= 1


def test_library_csv_export() -> None:
    csv_text = library_csv([{"number": 42, "title": "Test", "date": "Jan", "formats": ["audio_hq"], "total_bytes": 1000}])
    assert "42" in csv_text
    assert "Test" in csv_text


def test_eta_in_job_dict() -> None:
    job = DownloadJob(
        id="x",
        episode=1,
        media=MediaType.AUDIO_HQ,
        title="T",
        url="http://x",
        filename="a.mp3",
        status=JobStatus.RUNNING,
        bytes_downloaded=50,
        total_bytes=100,
        speed_bps=10.0,
    )
    d = job.to_dict()
    assert d["eta_seconds"] == 5.0
    assert d["eta_human"] == "5s"


if __name__ == "__main__":
    test_weekly_downloads()
    test_library_csv_export()
    test_eta_in_job_dict()
    print("insights ok")