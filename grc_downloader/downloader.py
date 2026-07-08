from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from .models import DownloadJob, DownloadTask, JobStatus, MediaType
from .parser import media_url

BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


class DownloadManager:
    def __init__(self, download_dir: Path, broadcast: BroadcastFn | None = None):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.broadcast = broadcast
        self.jobs: dict[str, DownloadJob] = {}
        self._order: list[str] = []
        self._running = False
        self._cancel = False
        self._lock = asyncio.Lock()

    def snapshot(self) -> dict[str, Any]:
        jobs = [self.jobs[jid].to_dict() for jid in self._order if jid in self.jobs]
        active = [j for j in jobs if j["status"] == JobStatus.RUNNING.value]
        queued = [j for j in jobs if j["status"] == JobStatus.QUEUED.value]
        done = [j for j in jobs if j["status"] in {
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.SKIPPED.value,
            JobStatus.CANCELLED.value,
        }]
        bytes_done = sum(j["bytes_downloaded"] for j in done if j["status"] == JobStatus.COMPLETED.value)
        return {
            "running": self._running,
            "cancel_requested": self._cancel,
            "download_dir": str(self.download_dir.resolve()),
            "counts": {
                "total": len(jobs),
                "active": len(active),
                "queued": len(queued),
                "completed": sum(1 for j in jobs if j["status"] == JobStatus.COMPLETED.value),
                "failed": sum(1 for j in jobs if j["status"] == JobStatus.FAILED.value),
            },
            "bytes_completed": bytes_done,
            "jobs": jobs,
        }

    async def _emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        if not self.broadcast:
            return
        msg = {"event": event, "data": payload or self.snapshot()}
        await self.broadcast(msg)

    def _local_next_episode(self) -> int | None:
        highest = 0
        for path in self.download_dir.glob("sn-*"):
            name = path.name
            parts = name.split("-")
            if len(parts) < 2:
                continue
            num_part = parts[1].split(".")[0]
            if num_part.isdigit():
                highest = max(highest, int(num_part))
        return highest + 1 if highest else None

    def build_tasks(
        self,
        episodes: list[int],
        media_types: list[MediaType],
        titles: dict[int, str] | None = None,
    ) -> list[DownloadTask]:
        titles = titles or {}
        tasks: list[DownloadTask] = []
        for ep in episodes:
            for media in media_types:
                ext = {
                    MediaType.AUDIO_HQ: "mp3",
                    MediaType.AUDIO_LQ: "mp3",
                    MediaType.AUDIO_TWIT: "mp3",
                    MediaType.TRANSCRIPT_TXT: "txt",
                    MediaType.TRANSCRIPT_PDF: "pdf",
                    MediaType.TRANSCRIPT_HTML: "htm",
                    MediaType.SHOW_NOTES: "pdf",
                }[media]
                suffix = "-lq" if media == MediaType.AUDIO_LQ else ""
                suffix = "-notes" if media == MediaType.SHOW_NOTES else suffix
                filename = f"sn-{ep:04d}{suffix}.{ext}"
                if media == MediaType.AUDIO_TWIT:
                    filename = f"sn-{ep:04d}-twit.mp3"
                tasks.append(
                    DownloadTask(
                        episode=ep,
                        media=media,
                        url=media_url(ep, media),
                        filename=filename,
                        title=titles.get(ep, ""),
                    )
                )
        return tasks

    async def enqueue(
        self,
        episodes: list[int],
        media_types: list[MediaType],
        titles: dict[int, str] | None = None,
        parallel: int = 2,
        skip_existing: bool = True,
    ) -> None:
        async with self._lock:
            if self._running:
                raise RuntimeError("A download batch is already running")

            self._cancel = False
            self.jobs.clear()
            self._order.clear()

            tasks = self.build_tasks(episodes, media_types, titles)
            for task in tasks:
                dest = self.download_dir / task.filename
                job_id = str(uuid.uuid4())
                status = JobStatus.QUEUED
                if skip_existing and dest.exists() and dest.stat().st_size > 0:
                    status = JobStatus.SKIPPED
                job = DownloadJob(
                    id=job_id,
                    episode=task.episode,
                    media=task.media,
                    title=task.title,
                    url=task.url,
                    filename=task.filename,
                    status=status,
                    total_bytes=dest.stat().st_size if status == JobStatus.SKIPPED else None,
                    bytes_downloaded=dest.stat().st_size if status == JobStatus.SKIPPED else 0,
                )
                self.jobs[job_id] = job
                self._order.append(job_id)

            self._running = True
            await self._emit("batch_started")

        asyncio.create_task(self._run_queue(parallel))

    async def cancel(self) -> None:
        self._cancel = True
        await self._emit("cancel_requested")

    async def _run_queue(self, parallel: int) -> None:
        sem = asyncio.Semaphore(max(1, parallel))
        pending = [
            jid
            for jid in self._order
            if self.jobs[jid].status == JobStatus.QUEUED
        ]

        async def worker(job_id: str) -> None:
            async with sem:
                if self._cancel:
                    job = self.jobs[job_id]
                    job.status = JobStatus.CANCELLED
                    await self._emit("job_updated", {"job": job.to_dict()})
                    return
                await self._download_one(job_id)

        try:
            await asyncio.gather(*(worker(jid) for jid in pending))
        finally:
            self._running = False
            await self._emit("batch_finished")

    async def _download_one(self, job_id: str) -> None:
        job = self.jobs[job_id]
        dest = self.download_dir / job.filename
        part = dest.with_suffix(dest.suffix + ".part")

        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        job.bytes_downloaded = 0
        job.speed_bps = 0.0
        await self._emit("job_updated", {"job": job.to_dict()})

        headers = {"User-Agent": "SecurityNowDashboard/1.0"}
        resume_from = part.stat().st_size if part.exists() else 0
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        try:
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                async with client.stream("GET", job.url, headers=headers) as resp:
                    if resp.status_code == 416:
                        part.rename(dest)
                        job.status = JobStatus.COMPLETED
                        job.finished_at = time.time()
                        await self._emit("job_updated", {"job": job.to_dict()})
                        return
                    if resp.status_code not in (200, 206):
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )

                    total_header = resp.headers.get("content-length")
                    content_range = resp.headers.get("content-range", "")
                    if content_range and "/" in content_range:
                        job.total_bytes = int(content_range.rsplit("/", 1)[-1])
                    elif total_header:
                        extra = resume_from if resp.status_code == 206 else 0
                        job.total_bytes = int(total_header) + extra
                    else:
                        job.total_bytes = None

                    mode = "ab" if resume_from and resp.status_code == 206 else "wb"
                    if mode == "wb":
                        resume_from = 0
                        job.bytes_downloaded = 0

                    last_tick = time.time()
                    last_bytes = job.bytes_downloaded
                    with part.open(mode) as fh:
                        async for chunk in resp.aiter_bytes(64 * 1024):
                            if self._cancel:
                                job.status = JobStatus.CANCELLED
                                job.finished_at = time.time()
                                await self._emit("job_updated", {"job": job.to_dict()})
                                return
                            fh.write(chunk)
                            job.bytes_downloaded += len(chunk)
                            now = time.time()
                            if now - last_tick >= 0.25:
                                dt = now - last_tick
                                job.speed_bps = (job.bytes_downloaded - last_bytes) / dt if dt else 0
                                last_tick = now
                                last_bytes = job.bytes_downloaded
                                await self._emit("job_updated", {"job": job.to_dict()})

            part.rename(dest)
            job.status = JobStatus.COMPLETED
            job.speed_bps = 0.0
            job.finished_at = time.time()
            await self._emit("job_updated", {"job": job.to_dict()})

        except Exception as exc:  # noqa: BLE001 — surface to dashboard
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = time.time()
            await self._emit("job_updated", {"job": job.to_dict()})