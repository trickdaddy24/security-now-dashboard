"""Lightweight smoke tests — no network required."""

from __future__ import annotations

import tempfile
from pathlib import Path

from grc_downloader.disk import check_disk_space, estimate_batch_bytes
from grc_downloader.filenames import build_filename, sanitize_component
from grc_downloader.models import MediaType
from grc_downloader.parser import media_url, parse_episode_range, _parse_catalog_html


SAMPLE_HTML = """
Episode&nbsp;#1086 | 07 Jul 2026 | ... min.</font></td></tr></table>
<table><tr><td><font size=2><b>The Apex Agentic Adversary</b></font>
Episode&nbsp;#1085 | 30 Jun 2026 | 149 min.</font></td></tr></table>
<table><tr><td><font size=2><b>A SOTA State-Sponsored Campaign</b></font>
"""

MISSING_TITLE_HTML = """
Episode&nbsp;#900 | 01 Jan 2020 | 120 min.</font>
<table><tr><td><font size=2><b>Legacy Episode</b></font>
"""


def test_parse_catalog_html() -> None:
    episodes, latest = _parse_catalog_html(SAMPLE_HTML)
    assert latest == 1086
    assert len(episodes) == 2
    assert episodes[0].title == "The Apex Agentic Adversary"
    assert episodes[1].duration == "149"


def test_parse_ellipsis_duration() -> None:
    episodes, _ = _parse_catalog_html(SAMPLE_HTML)
    assert episodes[0].duration is None


def test_episode_range() -> None:
    assert parse_episode_range("latest", 1086) == [1086]
    assert parse_episode_range("1084:1086", 1086) == [1084, 1085, 1086]
    assert parse_episode_range("1080:latest", 1086)[0] == 1080
    assert parse_episode_range("next", 1086, local_next=1080) == [1080]


def test_media_urls() -> None:
    assert media_url(1086, MediaType.AUDIO_HQ).endswith("sn-1086.mp3")
    assert "sn1086_h264m_1920x1080.mp4" in media_url(1086, MediaType.VIDEO_HD)
    assert "pscrb.fm" in media_url(42, MediaType.VIDEO_LQ)


def test_filename_presets() -> None:
    raw = build_filename(1086, MediaType.AUDIO_HQ, fmt="raw")
    assert raw == "sn-1086.mp3"
    ordered = build_filename(
        1086, MediaType.SHOW_NOTES,
        title="The Apex Agentic Adversary",
        date_label="07 Jul 2026",
        fmt="ordered",
    )
    assert "1086" in ordered and "notes" in ordered
    kodi = build_filename(1086, MediaType.AUDIO_HQ, date_label="07 Jul 2026", fmt="kodi")
    assert kodi.startswith("Security Now S")
    assert "E1086" in kodi


def test_sanitize_component() -> None:
    assert sanitize_component('bad<>:"|?*name') == "badname"


def test_disk_estimate() -> None:
    est = estimate_batch_bytes([1086], [MediaType.SHOW_NOTES])
    assert 0 < est < 10 * 1024 * 1024
    with tempfile.TemporaryDirectory() as tmp:
        ok, _ = check_disk_space(Path(tmp), [1086], [MediaType.SHOW_NOTES], min_free_mb=1)
        assert ok is True


def test_app_import() -> None:
    import app  # noqa: F401


if __name__ == "__main__":
    test_parse_catalog_html()
    test_parse_ellipsis_duration()
    test_episode_range()
    test_media_urls()
    test_filename_presets()
    test_sanitize_component()
    test_disk_estimate()
    test_app_import()
    print("smoke ok")