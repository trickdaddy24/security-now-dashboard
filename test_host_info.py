"""Host / external IP helpers — no network required."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

from grc_downloader.host_info import build_telegram_message, container_ip, resolve_external_ip


def test_container_ip_returns_string() -> None:
    ip = container_ip()
    assert isinstance(ip, str)
    assert ip


def test_build_telegram_message_minimal() -> None:
    msg = build_telegram_message(
        "Test headline",
        version="9.9.9",
        external_ip="1.2.3.4",
    )
    assert "Test headline · v9.9.9" in msg
    assert "1.2.3.4" in msg


async def _test_resolve_external_ip_env() -> None:
    with patch.dict(os.environ, {"SN_EXTERNAL_IP": "138.201.28.235"}):
        ip = await resolve_external_ip()
        assert ip == "138.201.28.235"


def test_resolve_external_ip_env() -> None:
    import asyncio

    asyncio.run(_test_resolve_external_ip_env())


async def _test_resolve_external_ip_http() -> None:
    import grc_downloader.host_info as host_info

    host_info._ip_cache["ip"] = None
    host_info._ip_cache["at"] = 0.0
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SN_EXTERNAL_IP", None)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = "203.0.113.50"
        mock_resp.raise_for_status = lambda: None
        with patch("grc_downloader.host_info.httpx.AsyncClient") as mock_client:
            instance = mock_client.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=mock_resp)
            ip = await resolve_external_ip(force_refresh=True)
            assert ip == "203.0.113.50"


def test_resolve_external_ip_http() -> None:
    import asyncio

    asyncio.run(_test_resolve_external_ip_http())


if __name__ == "__main__":
    test_container_ip_returns_string()
    test_build_telegram_message_minimal()
    test_resolve_external_ip_env()
    test_resolve_external_ip_http()
    print("host info ok")