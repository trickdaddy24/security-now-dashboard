"""Episode folder layout tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

from grc_downloader.downloader import DownloadManager
from grc_downloader.config import AppConfig
from grc_downloader.library import scan_library
from grc_downloader.models import MediaType
from grc_downloader.paths import media_rel_path


def test_media_rel_path() -> None:
    assert media_rel_path(1086, "sn-1086.mp3", episode_folders=True) == "sn-1086/sn-1086.mp3"
    assert media_rel_path(1086, "sn-1086.mp3", episode_folders=False) == "sn-1086.mp3"


def test_build_tasks_use_episode_folders() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = AppConfig(download_dir=Path(tmp), episode_folders=True)
        mgr = DownloadManager(cfg)
        tasks = mgr.build_tasks([1086], [MediaType.AUDIO_HQ])
        assert tasks[0].filename == "sn-1086/sn-1086.mp3"


def test_scan_library_nested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ep_dir = root / "sn-1086"
        ep_dir.mkdir()
        (ep_dir / "sn-1086.mp3").write_bytes(b"x" * 10)
        (ep_dir / "sn-1086.txt").write_text("hello", encoding="utf-8")
        entries = scan_library(root)
        ep = next(e for e in entries if e.number == 1086)
        assert ep.files["audio_hq"].filename == "sn-1086/sn-1086.mp3"


if __name__ == "__main__":
    test_media_rel_path()
    test_build_tasks_use_episode_folders()
    test_scan_library_nested()
    print("paths ok")