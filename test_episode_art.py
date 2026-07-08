"""Episode art helpers — offline + optional live integration."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from grc_downloader.episode_art import (
    is_valid_image,
    parse_youtube_id,
    youtube_thumb_candidates,
)
from grc_downloader.twit_thumbs import download_episode_art, thumb_paths_for_video

SAMPLE_TWIT_HTML = """
<div id="youtube-player">
  <iframe src="https://www.youtube.com/embed/vK9fen8u2IE"></iframe>
</div>
<a href="https://youtu.be/vK9fen8u2IE">YouTube</a>
"""


def test_parse_youtube_id_from_twit_page() -> None:
    assert parse_youtube_id(SAMPLE_TWIT_HTML) == "vK9fen8u2IE"


def test_youtube_thumb_candidates() -> None:
    urls = youtube_thumb_candidates("vK9fen8u2IE")
    assert urls[0].endswith("/maxresdefault.jpg")
    assert "vK9fen8u2IE" in urls[0]


def test_is_valid_image() -> None:
    assert is_valid_image(b"\xff\xd8\xff" + b"x" * 600)
    assert is_valid_image(b"\x89PNG\r\n\x1a\n" + b"x" * 600)
    assert not is_valid_image(b"<html>403</html>")
    assert not is_valid_image(b"\xff\xd8" + b"x" * 10)


async def _test_live_episode_1082_art() -> None:
    if os.getenv("SN_SKIP_INTEGRATION", "").lower() in ("1", "true", "yes"):
        return
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        video = d / "sn-1082" / "Security Now S2026E1082.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"\x00")
        ok = await download_episode_art(d, 1082, video, verify_ssl=True, force=True)
        assert ok, "download_episode_art failed for ep 1082"
        thumb, fanart = thumb_paths_for_video(video)
        poster = video.parent / "poster.jpg"
        assert thumb.is_file() and thumb.stat().st_size > 10_000
        assert fanart.is_file()
        assert poster.is_file()
        data = thumb.read_bytes()
        assert is_valid_image(data)
        # YouTube maxres is typically much larger than TWiT 720x405 (~35KB)
        assert len(data) > 50_000, f"expected YouTube-sized thumb, got {len(data)} bytes"


def test_live_episode_1082_art() -> None:
    asyncio.run(_test_live_episode_1082_art())


if __name__ == "__main__":
    test_parse_youtube_id_from_twit_page()
    test_youtube_thumb_candidates()
    test_is_valid_image()
    test_live_episode_1082_art()
    print("episode art ok")