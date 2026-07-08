"""TWiT RSS thumbnail parsing — no network required."""

from __future__ import annotations

from pathlib import Path

from grc_downloader.twit_thumbs import (
    _parse_episode_items,
    thumb_paths_for_video,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:podcast="https://podcastindex.org/namespace/1.0"
     version="2.0">
  <channel>
    <title>Security Now</title>
    <item>
      <title>SN 1086: The Apex Agentic Adversary</title>
      <itunes:episode>1086</itunes:episode>
      <itunes:image href="https://elroy.twit.tv/sites/default/files/images/episodes/SN1086_thumbnail.jpg"/>
    </item>
    <item>
      <title>SN 1085: A SOTA State-Sponsored Campaign</title>
      <podcast:episode>1085</podcast:episode>
      <media:content url="https://example.com/audio.mp3">
        <media:thumbnail url="https://elroy.twit.tv/SN1085_thumb.jpg"/>
      </media:content>
    </item>
    <item>
      <title>SN 900: Legacy title only</title>
    </item>
  </channel>
</rss>
"""


def test_parse_episode_items() -> None:
    mapping = _parse_episode_items(SAMPLE_RSS)
    assert mapping[1086] == "https://elroy.twit.tv/sites/default/files/images/episodes/SN1086_thumbnail.jpg"
    assert mapping[1085] == "https://elroy.twit.tv/SN1085_thumb.jpg"
    assert 900 not in mapping


def test_thumb_paths_for_video() -> None:
    video = Path("sn-1086/Security Now S2026E1086.mp4")
    thumb, fanart = thumb_paths_for_video(video)
    assert thumb.name == "Security Now S2026E1086-thumb.jpg"
    assert fanart.name == "Security Now S2026E1086-fanart.jpg"
    assert thumb.parent == video.parent


if __name__ == "__main__":
    test_parse_episode_items()
    test_thumb_paths_for_video()
    print("twit thumbs ok")