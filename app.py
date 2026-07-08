"""Security Now live download dashboard — FastAPI + WebSocket."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from grc_downloader.downloader import DownloadManager
from grc_downloader.models import MediaType
from grc_downloader.parser import fetch_catalog, parse_episode_range

ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = Path(os.getenv("SN_DOWNLOAD_DIR", ROOT / "downloads"))
STATIC_DIR = ROOT / "static"

app = FastAPI(title="Security Now Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_ws_clients: set[WebSocket] = set()
_manager: DownloadManager | None = None


async def _broadcast(message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    payload = json.dumps(message)
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


def get_manager() -> DownloadManager:
    global _manager
    if _manager is None:
        _manager = DownloadManager(DOWNLOAD_DIR, broadcast=_broadcast)
    return _manager


class StartRequest(BaseModel):
    episodes: str = Field(default="latest", description="e.g. latest, 1086, 1080:1086, all, next")
    media: list[str] = Field(default_factory=lambda: ["audio_hq"])
    parallel: int = Field(default=2, ge=1, le=8)
    skip_existing: bool = True


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    episodes, latest = await fetch_catalog()
    mgr = get_manager()
    local_next = mgr._local_next_episode()  # noqa: SLF001 — intentional for API
    return {
        "latest": latest,
        "local_next": local_next,
        "download_dir": str(DOWNLOAD_DIR.resolve()),
        "episodes": [
            {
                "number": e.number,
                "title": e.title,
                "date": e.date_label,
                "duration": e.duration,
            }
            for e in episodes[:30]
        ],
    }


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return get_manager().snapshot()


@app.post("/api/download")
async def start_download(req: StartRequest) -> dict[str, Any]:
    mgr = get_manager()
    if mgr._running:
        return {"ok": False, "error": "A batch is already running"}

    episodes_meta, latest = await fetch_catalog()
    titles = {e.number: e.title for e in episodes_meta}
    local_next = mgr._local_next_episode()

    ep_list = parse_episode_range(req.episodes, latest, local_next)
    if not ep_list:
        return {"ok": False, "error": "No episodes matched that spec"}

    media_types: list[MediaType] = []
    for m in req.media:
        try:
            media_types.append(MediaType(m))
        except ValueError:
            return {"ok": False, "error": f"Unknown media type: {m}"}

    await mgr.enqueue(
        episodes=ep_list,
        media_types=media_types,
        titles=titles,
        parallel=req.parallel,
        skip_existing=req.skip_existing,
    )
    return {"ok": True, "episodes": ep_list, "jobs": len(mgr._order)}


@app.post("/api/cancel")
async def cancel_download() -> dict[str, bool]:
    await get_manager().cancel()
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"event": "snapshot", "data": get_manager().snapshot()}))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8787, reload=True)