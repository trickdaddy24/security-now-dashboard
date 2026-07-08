"""Library, RSS, and search smoke tests — no network."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from grc_downloader.library import (
    library_summary,
    missing_episodes,
    missing_formats,
    scan_library,
    EpisodeEntry,
)
from grc_downloader.rss import build_feeds, rss_status
from grc_downloader.search import index_transcripts, search_transcripts
from grc_downloader.version import get_version


def test_version() -> None:
    assert get_version() >= "1.0.0"


def test_scan_and_classify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sn-1086.mp3").write_bytes(b"x" * 1000)
        (root / "sn-1086.txt").write_text("SpinRite mention in transcript", encoding="utf-8")
        (root / "sn-1086-notes.pdf").write_bytes(b"%PDF")
        entries = scan_library(root)
        assert len(entries) >= 1
        ep = next(e for e in entries if e.number == 1086)
        assert "audio_hq" in ep.files or "transcript_txt" in ep.files


def test_missing_episodes() -> None:
    assert 5 in missing_episodes([1, 2, 3, 4, 6], 6)


def test_missing_formats() -> None:
    entry = EpisodeEntry(number=1, files={})
    assert "audio_hq" in missing_formats(entry)


def test_rss_build() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sn-0001.mp3").write_bytes(b"x" * 500)
        (root / "sn-0001.meta.json").write_text(
            json.dumps({"episode": 1, "title": "Pilot", "date": "01 Jan 2005", "files": {}}),
            encoding="utf-8",
        )
        state = build_feeds(root, base_url="http://localhost:8787", desc_limit=100)
        assert state["counts"]["audio"] >= 1
        assert rss_status(root).get("built_at")


def test_search_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sn-0042.txt").write_text("SQRL is a clever authentication scheme", encoding="utf-8")
        index_transcripts(root)
        hits = search_transcripts(root, "SQRL")
        assert len(hits) == 1
        assert hits[0]["episode"] == 42


def test_library_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sn-0002.mp3").write_bytes(b"x" * 100)
        summary = library_summary(root, latest_remote=5)
        assert summary["episode_count"] == 1
        assert summary["missing_episode_count"] >= 3


if __name__ == "__main__":
    test_version()
    test_scan_and_classify()
    test_missing_episodes()
    test_missing_formats()
    test_rss_build()
    test_search_index()
    test_library_summary()
    print("library ok")