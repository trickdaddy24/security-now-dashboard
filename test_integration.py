"""Optional network integration test — downloads a small show-notes PDF."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from grc_downloader.config import AppConfig
from grc_downloader.downloader import DownloadManager
from grc_downloader.models import MediaType


async def _run() -> None:
    if os.getenv("SN_SKIP_INTEGRATION", "").lower() in ("1", "true", "yes"):
        print("integration skipped")
        return

    with tempfile.TemporaryDirectory() as tmp:
        cfg = AppConfig(download_dir=Path(tmp), parallel=1, min_free_mb=1)
        mgr = DownloadManager(cfg)
        ok, err = await mgr.enqueue(
            episodes=[1086],
            media_types=[MediaType.SHOW_NOTES],
            titles={1086: "Integration Test"},
            dates={1086: "07 Jul 2026"},
        )
        assert ok, err
        while mgr._running:
            await asyncio.sleep(0.5)
        snap = mgr.snapshot()
        assert snap["counts"]["completed"] == 1
        assert (Path(tmp) / "sn-1086-notes.pdf").is_file()
        meta = Path(tmp) / "sn-1086.meta.json"
        assert meta.is_file()
    print("integration ok")


if __name__ == "__main__":
    asyncio.run(_run())