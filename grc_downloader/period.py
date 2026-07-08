from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import EpisodeInfo

_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y")


def parse_episode_date(date_label: str) -> datetime | None:
    text = (date_label or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def period_cutoff(period: str, count: int, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    count = max(1, count)
    unit = (period or "day").strip().lower()
    if unit.startswith("week"):
        return now - timedelta(weeks=count)
    if unit.startswith("month"):
        return now - timedelta(days=30 * count)
    return now - timedelta(days=count)


def episodes_in_period(
    episodes: list[EpisodeInfo],
    period: str,
    count: int,
    *,
    now: datetime | None = None,
) -> list[int]:
    """Episodes whose GRC air date falls within the last N days/weeks/months."""
    cutoff = period_cutoff(period, count, now=now)
    matched: list[int] = []
    for ep in episodes:
        dt = parse_episode_date(ep.date_label)
        if dt is None:
            continue
        if dt >= cutoff:
            matched.append(ep.number)
    return sorted(set(matched))