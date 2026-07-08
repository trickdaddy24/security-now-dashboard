"""Telegram, heartbeat, and log tail tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from grc_downloader.heartbeat import build_heartbeat_message
from grc_downloader.integrations import notify_telegram
from grc_downloader.log_tail import tail_log_events


def test_tail_log_events_json_and_plain() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "app.log"
        log_file.write_text(
            "\n".join(
                [
                    '{"ts":"2026-07-08T12:00:00Z","level":"INFO","message":"job_started","episode":1086}',
                    "plain line",
                    '{"ts":"2026-07-08T12:01:00Z","level":"ERROR","message":"job_failed","episode":1085}',
                ]
            ),
            encoding="utf-8",
        )
        events = tail_log_events(log_file, limit=10)
        assert len(events) == 3
        assert events[0]["message"] == "job_failed"
        assert events[0]["episode"] == 1085
        assert events[2]["message"] == "job_started"


def test_build_heartbeat_message() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        msg = build_heartbeat_message(
            download_dir=Path(tmp),
            running=True,
            counts={"active": 1, "completed": 3},
            watcher_enabled=True,
            watcher_interval_hours=6,
            latest_episode=1086,
        )
    assert "Security Now heartbeat" in msg
    assert "batch running" in msg
    assert "watcher on" in msg
    assert "#1086" in msg


async def _test_notify_telegram_no_credentials() -> None:
    assert await notify_telegram(None, None, "hi") is False


def test_notify_telegram_no_credentials() -> None:
    import asyncio

    asyncio.run(_test_notify_telegram_no_credentials())


async def _test_notify_telegram_posts() -> None:
    with patch("grc_downloader.integrations.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=type("R", (), {"status_code": 200})())
        ok = await notify_telegram("token", "chat", "hello")
        assert ok is True
        instance.post.assert_called_once()


def test_notify_telegram_posts() -> None:
    import asyncio

    asyncio.run(_test_notify_telegram_posts())


if __name__ == "__main__":
    test_tail_log_events_json_and_plain()
    test_build_heartbeat_message()
    test_notify_telegram_no_credentials()
    test_notify_telegram_posts()
    print("telegram ok")