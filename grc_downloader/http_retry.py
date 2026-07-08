from __future__ import annotations

import asyncio

import httpx


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt >= max_attempts - 1:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
    assert last_exc is not None
    raise last_exc