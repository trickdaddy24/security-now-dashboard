from __future__ import annotations

import os
import socket
import time

import httpx

IPIFY_URL = "https://api.ipify.org"
IP_CACHE_TTL_SECONDS = 3600

_ip_cache: dict[str, object] = {"ip": None, "at": 0.0}


def container_ip() -> str:
    """Best-effort local/container address (often a Docker bridge IP)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "unknown"


async def resolve_external_ip(*, verify_ssl: bool = True, force_refresh: bool = False) -> str:
    """Public routable IP — env override, cached HTTP lookup, then container IP."""
    if env := os.getenv("SN_EXTERNAL_IP", "").strip():
        return env

    now = time.time()
    cached = _ip_cache.get("ip")
    cached_at = float(_ip_cache.get("at") or 0)
    if not force_refresh and isinstance(cached, str) and cached and (now - cached_at) < IP_CACHE_TTL_SECONDS:
        return cached

    try:
        async with httpx.AsyncClient(timeout=5.0, verify=verify_ssl) as client:
            resp = await client.get(IPIFY_URL)
            resp.raise_for_status()
            ip = resp.text.strip()
            if ip:
                _ip_cache["ip"] = ip
                _ip_cache["at"] = now
                return ip
    except Exception:
        pass

    return container_ip()


def format_host_line(*, external_ip: str, hostname: str | None = None) -> str:
    host = hostname or socket.gethostname()
    return f"🖥️ {host} | 🌐 {external_ip}"


def build_telegram_message(
    headline: str,
    *,
    version: str,
    external_ip: str,
    public_url: str | None = None,
    extra_lines: list[str] | None = None,
) -> str:
    """Standard Telegram body with version + public host/IP footer."""
    parts = [f"{headline} · v{version}"]
    if extra_lines:
        parts.extend(extra_lines)
    parts.append(format_host_line(external_ip=external_ip))
    if public_url:
        parts.append(f"🔗 {public_url}")
    return "\n".join(parts)