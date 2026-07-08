"""Lightweight smoke tests — no network required for structure checks."""

from __future__ import annotations

import asyncio
import re

from grc_downloader.models import MediaType
from grc_downloader.parser import media_url, parse_episode_range, _parse_catalog_html


SAMPLE_HTML = """
Episode&nbsp;#1086 | 07 Jul 2026 | ... min.</font></td></tr></table>
<table><tr><td><font size=2><b>The Apex Agentic Adversary</b></font>
Episode&nbsp;#1085 | 30 Jun 2026 | 149 min.</font></td></tr></table>
<table><tr><td><font size=2><b>A SOTA State-Sponsored Campaign</b></font>
"""


def test_parse_catalog_html() -> None:
    episodes, latest = _parse_catalog_html(SAMPLE_HTML)
    assert latest == 1086
    assert len(episodes) == 2
    assert episodes[0].number == 1086
    assert episodes[0].title == "The Apex Agentic Adversary"
    assert episodes[0].date_label == "07 Jul 2026"


def test_episode_range() -> None:
    assert parse_episode_range("latest", 1086) == [1086]
    assert parse_episode_range("1084:1086", 1086) == [1084, 1085, 1086]
    assert parse_episode_range("next", 1086, local_next=1080) == [1080]


def test_media_urls() -> None:
    assert media_url(1086, MediaType.AUDIO_HQ) == "https://media.grc.com/sn/sn-1086.mp3"
    assert "1086" in media_url(1086, MediaType.AUDIO_TWIT)


def test_app_import() -> None:
    import app  # noqa: F401


if __name__ == "__main__":
    test_parse_catalog_html()
    test_episode_range()
    test_media_urls()
    test_app_import()
    print("smoke ok")