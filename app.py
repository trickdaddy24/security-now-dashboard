"""Security Now live download dashboard — FastAPI + WebSocket."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from grc_downloader.config import AppConfig, load_config
from grc_downloader.disk import check_disk_space, free_bytes
from grc_downloader.downloader import DownloadManager
from grc_downloader.client_tokens import claim_token, lookup_token
from grc_downloader.history import read_batches, read_recent
from grc_downloader.models import MediaType
from grc_downloader.parser import fetch_catalog, parse_episode_range

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

CONFIG: AppConfig = load_config()

app = FastAPI(title="Security Now Dashboard", version="1.2.0")
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
        _manager = DownloadManager(CONFIG, broadcast=_broadcast)
    return _manager


class StartRequest(BaseModel):
    episodes: str = Field(default="latest", description="e.g. latest, 1086, 1080:1086, all, next")
    media: list[str] | None = None
    parallel: int | None = Field(default=None, ge=1, le=8)
    skip_existing: bool | None = None
    filename_format: str | None = None
    retry_failed: bool = False
    client_token: str | None = None
    callback_url: str | None = None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    return {
        "download_dir": str(CONFIG.download_dir.resolve()),
        "parallel": CONFIG.parallel,
        "skip_existing": CONFIG.skip_existing,
        "filename_format": CONFIG.filename_format,
        "default_media": CONFIG.default_media,
        "min_free_mb": CONFIG.min_free_mb,
        "disk_free_bytes": free_bytes(CONFIG.download_dir),
    }


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    episodes, latest = await fetch_catalog(verify_ssl=CONFIG.verify_ssl)
    mgr = get_manager()
    local_next = mgr._local_next_episode()  # noqa: SLF001
    return {
        "latest": latest,
        "local_next": local_next,
        "download_dir": str(CONFIG.download_dir.resolve()),
        "disk_free_bytes": free_bytes(CONFIG.download_dir),
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


@app.get("/api/history")
async def history(limit: int = 50) -> dict[str, Any]:
    mgr = get_manager()
    return {"events": read_recent(mgr.history_path, limit=limit)}


@app.get("/api/jobs/history")
async def jobs_history(limit: int = 20) -> dict[str, Any]:
    mgr = get_manager()
    return {"batches": read_batches(mgr.history_path, limit=limit)}


@app.post("/api/download/estimate")
async def estimate_download(req: StartRequest) -> dict[str, Any]:
    mgr = get_manager()
    episodes_meta, latest = await fetch_catalog(verify_ssl=CONFIG.verify_ssl)
    local_next = mgr._local_next_episode()
    ep_list = parse_episode_range(req.episodes, latest, local_next)
    media_types = _parse_media(req.media)
    if not ep_list:
        return {"ok": False, "error": "No episodes matched"}
    ok, msg = check_disk_space(CONFIG.download_dir, ep_list, media_types, CONFIG.min_free_mb)
    return {
        "ok": ok,
        "message": msg,
        "episodes": ep_list,
        "job_count": len(ep_list) * len(media_types),
        "disk_free_bytes": free_bytes(CONFIG.download_dir),
    }


def _parse_media(media: list[str] | None) -> list[MediaType]:
    raw = media or CONFIG.default_media
    out: list[MediaType] = []
    for m in raw:
        out.append(MediaType(m))
    return out


@app.post("/api/download")
async def start_download(req: StartRequest) -> dict[str, Any]:
    mgr = get_manager()
    if mgr._running and not req.retry_failed:
        return {"ok": False, "error": "A batch is already running"}

    if req.retry_failed:
        ok, err = await mgr.enqueue(
            episodes=[],
            media_types=[],
            retry_failed=True,
            parallel=req.parallel,
            callback_url=req.callback_url,
        )
        return {"ok": ok, "error": err or None, "retry_failed": True}

    if req.client_token:
        existing = lookup_token(CONFIG.download_dir, req.client_token)
        if existing:
            return {"ok": True, "duplicate": True, "batch_id": existing}

    episodes_meta, latest = await fetch_catalog(verify_ssl=CONFIG.verify_ssl)
    titles = {e.number: e.title for e in episodes_meta}
    dates = {e.number: e.date_label for e in episodes_meta}
    local_next = mgr._local_next_episode()

    ep_list = parse_episode_range(req.episodes, latest, local_next)
    if not ep_list:
        return {"ok": False, "error": "No episodes matched that spec"}

    try:
        media_types = _parse_media(req.media)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    ok, err = await mgr.enqueue(
        episodes=ep_list,
        media_types=media_types,
        titles=titles,
        dates=dates,
        parallel=req.parallel,
        skip_existing=req.skip_existing,
        filename_format=req.filename_format,
        callback_url=req.callback_url,
    )
    if not ok:
        return {"ok": False, "error": err}
    if req.client_token and mgr._batch_id:  # noqa: SLF001
        claim_token(CONFIG.download_dir, req.client_token, mgr._batch_id)
    return {
        "ok": True,
        "episodes": ep_list,
        "jobs": len(mgr._order),
        "batch_id": mgr._batch_id,
    }


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

    host = os.getenv("SN_HOST", "127.0.0.1")
    port = int(os.getenv("SN_PORT", "8787"))
    uvicorn.run("app:app", host=host, port=port, reload=True)