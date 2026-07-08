"""Period-based episode filter tests."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_downloader.models import EpisodeInfo
from grc_downloader.period import episodes_in_period, parse_episode_date, period_cutoff


def test_parse_episode_date() -> None:
    dt = parse_episode_date("07 Jul 2026")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 7 and dt.day == 7


def test_episodes_in_period_days() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    eps = [
        EpisodeInfo(number=1086, title="New", date_label="07 Jul 2026", duration=None),
        EpisodeInfo(number=1085, title="Old", date_label="01 Jun 2026", duration=None),
    ]
    got = episodes_in_period(eps, "day", 14, now=now)
    assert got == [1086]


def test_period_cutoff_weeks() -> None:
    now = datetime(2026, 7, 8, tzinfo=timezone.utc)
    cutoff = period_cutoff("week", 2, now=now)
    assert (now - cutoff).days == 14


if __name__ == "__main__":
    test_parse_episode_date()
    test_episodes_in_period_days()
    test_period_cutoff_weeks()
    print("period ok")