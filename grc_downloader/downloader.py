from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from .config import AppConfig
from .disk import check_disk_space, free_bytes
from .filenames import build_filename
from .history import (
    append_history,
    batch_finished_record,
    batch_started_record,
    job_finished_record,
    new_batch_id,
)
from .metadata import update_sidecar
from .models import DownloadJob, DownloadTask, JobStatus, MediaType
from .parser import media_url

BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]

EPISODE_RE = re.compile(r"sn-(\d{4})")
BATCH_STATE_FILE = ".sn-last-batch.json"


class DownloadManager:
    def __init__(self, config: AppConfig, broadcast: BroadcastFn | None = None):
        self.config = config
        self.download_dir = Path(config.download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = config.resolve_history_path()
        self.broadcast = broadcast
        self.jobs: dict[str, DownloadJob] = {}
        self._order: list[str] = []
        self._running = False
        self._cancel = False
        self._lock = asyncio.Lock()
        self._batch_id: str | None = None
        self._callback_url: str | None = None
        self._cancelled_jobs: set[str] = set()

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
            "batch_id": self._batch_id,
            "download_dir": str(self.download_dir.resolve()),
            "disk_free_bytes": free_bytes(self.download_dir),
            "filename_format": self.config.filename_format,
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
        for path in self.download_dir.iterdir():
            if path.suffix == ".json" and path.name.endswith(".meta.json"):
                m = EPISODE_RE.search(path.name)
                if m:
                    highest = max(highest, int(m.group(1)))
                continue
            m = EPISODE_RE.search(path.name)
            if m:
                highest = max(highest, int(m.group(1)))
        return highest + 1 if highest else None

    def build_tasks(
        self,
        episodes: list[int],
        media_types: list[MediaType],
        titles: dict[int, str] | None = None,
        dates: dict[int, str] | None = None,
        filename_format: str | None = None,
    ) -> list[DownloadTask]:
        titles = titles or {}
        dates = dates or {}
        fmt = filename_format or self.config.filename_format
        tasks: list[DownloadTask] = []
        for ep in episodes:
            for media in media_types:
                filename = build_filename(
                    ep,
                    media,
                    title=titles.get(ep, ""),
                    date_label=dates.get(ep, ""),
                    fmt=fmt,
                )
                tasks.append(
                    DownloadTask(
                        episode=ep,
                        media=media,
                        url=media_url(ep, media),
                        filename=filename,
                        title=titles.get(ep, ""),
                        date_label=dates.get(ep, ""),
                    )
                )
        return tasks

    def _save_batch_state(self) -> None:
        path = self.download_dir / BATCH_STATE_FILE
        path.write_text(
            json.dumps({
                "batch_id": self._batch_id,
                "jobs": [self.jobs[jid].to_dict() for jid in self._order],
            }, indent=2),
            encoding="utf-8",
        )

    def load_last_batch_failed(self) -> list[dict[str, Any]]:
        path = self.download_dir / BATCH_STATE_FILE
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return [j for j in data.get("jobs", []) if j.get("status") == JobStatus.FAILED.value]

    async def enqueue(
        self,
        episodes: list[int],
        media_types: list[MediaType],
        titles: dict[int, str] | None = None,
        dates: dict[int, str] | None = None,
        parallel: int | None = None,
        skip_existing: bool | None = None,
        filename_format: str | None = None,
        retry_failed: bool = False,
        callback_url: str | None = None,
    ) -> tuple[bool, str]:
        async with self._lock:
            if self._running:
                return False, "A download batch is already running"

            if retry_failed:
                failed = self.load_last_batch_failed()
                if not failed:
                    return False, "No failed jobs from the last batch"
                return await self._enqueue_failed_jobs(failed, parallel or self.config.parallel)

            ok, msg = check_disk_space(
                self.download_dir,
                episodes,
                media_types,
                self.config.min_free_mb,
            )
            if not ok:
                return False, msg

            self._cancel = False
            self._cancelled_jobs.clear()
            self.jobs.clear()
            self._order.clear()
            self._batch_id = new_batch_id()
            self._callback_url = callback_url
            skip = self.config.skip_existing if skip_existing is None else skip_existing
            par = parallel or self.config.parallel

            tasks = self.build_tasks(
                episodes,
                media_types,
                titles=titles,
                dates=dates,
                filename_format=filename_format,
            )
            for task in tasks:
                dest = self.download_dir / task.filename
                job_id = str(uuid.uuid4())
                status = JobStatus.QUEUED
                if skip and dest.exists() and dest.stat().st_size > 0:
                    status = JobStatus.SKIPPED
                job = DownloadJob(
                    id=job_id,
                    episode=task.episode,
                    media=task.media,
                    title=task.title,
                    date_label=task.date_label,
                    url=task.url,
                    filename=task.filename,
                    status=status,
                    total_bytes=dest.stat().st_size if status == JobStatus.SKIPPED else None,
                    bytes_downloaded=dest.stat().st_size if status == JobStatus.SKIPPED else 0,
                )
                self.jobs[job_id] = job
                self._order.append(job_id)

            append_history(
                self.history_path,
                batch_started_record(
                    self._batch_id,
                    episodes,
                    [m.value for m in media_types],
                    parallel=par,
                    filename_format=filename_format or self.config.filename_format,
                ),
            )

            self._running = True
            await self._emit("batch_started")

        asyncio.create_task(self._run_queue(par))
        return True, ""

    async def _enqueue_failed_jobs(self, failed: list[dict[str, Any]], parallel: int) -> tuple[bool, str]:
        self._cancel = False
        self._cancelled_jobs.clear()
        self.jobs.clear()
        self._order.clear()
        self._batch_id = new_batch_id()
        self._callback_url = None

        for item in failed:
            job_id = str(uuid.uuid4())
            media = MediaType(item["media"])
            job = DownloadJob(
                id=job_id,
                episode=int(item["episode"]),
                media=media,
                title=item.get("title", ""),
                url=item["url"],
                filename=item["filename"],
                status=JobStatus.QUEUED,
            )
            self.jobs[job_id] = job
            self._order.append(job_id)

        append_history(
            self.history_path,
            batch_started_record(self._batch_id, [], [], retry_failed=True),
        )
        self._running = True
        await self._emit("batch_started")
        asyncio.create_task(self._run_queue(parallel))
        return True, ""

    async def cancel(self) -> None:
        self._cancel = True
        await self._emit("cancel_requested")

    async def cancel_job(self, job_id: str) -> tuple[bool, str]:
        job = self.jobs.get(job_id)
        if not job:
            return False, "Job not found"
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            await self._emit("job_updated", {"job": job.to_dict()})
            return True, ""
        if job.status == JobStatus.RUNNING:
            self._cancelled_jobs.add(job_id)
            return True, ""
        return False, f"Cannot cancel job in state {job.status.value}"

    async def reorder_queue(self, job_ids: list[str]) -> tuple[bool, str]:
        async with self._lock:
            queued_ids = [jid for jid in self._order if self.jobs[jid].status == JobStatus.QUEUED]
            if set(job_ids) != set(queued_ids) or len(job_ids) != len(queued_ids):
                return False, "Job list must match current queued jobs"
            new_order: list[str] = []
            qi = 0
            for jid in self._order:
                if self.jobs[jid].status == JobStatus.QUEUED:
                    new_order.append(job_ids[qi])
                    qi += 1
                else:
                    new_order.append(jid)
            self._order = new_order
        await self._emit("queue_reordered")
        return True, ""

    async def _run_queue(self, parallel: int) -> None:
        sem = asyncio.Semaphore(max(1, parallel))
        pending = [jid for jid in self._order if self.jobs[jid].status == JobStatus.QUEUED]

        async def worker(job_id: str) -> None:
            async with sem:
                if self._cancel or job_id in self._cancelled_jobs:
                    job = self.jobs[job_id]
                    job.status = JobStatus.CANCELLED
                    self._cancelled_jobs.discard(job_id)
                    await self._emit("job_updated", {"job": job.to_dict()})
                    return
                await self._download_one(job_id)

        try:
            await asyncio.gather(*(worker(jid) for jid in pending))
        finally:
            self._running = False
            self._save_batch_state()
            snap = self.snapshot()
            if self._batch_id:
                append_history(
                    self.history_path,
                    batch_finished_record(self._batch_id, snap["counts"]),
                )
            await self._emit("batch_finished")
            if self._callback_url:
                asyncio.create_task(self._fire_callback(snap))

    async def _fire_callback(self, snap: dict[str, Any]) -> None:
        if not self._callback_url:
            return
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=self.config.verify_ssl) as client:
                await client.post(self._callback_url, json=snap)
        except Exception:
            pass

    async def _download_one(self, job_id: str) -> None:
        job = self.jobs[job_id]
        dest = self.download_dir / job.filename
        part = dest.with_suffix(dest.suffix + ".part")

        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        job.bytes_downloaded = part.stat().st_size if part.exists() else 0
        job.speed_bps = 0.0
        await self._emit("job_updated", {"job": job.to_dict()})

        headers = {"User-Agent": "SecurityNowDashboard/1.1"}
        resume_from = job.bytes_downloaded
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        try:
            async with httpx.AsyncClient(
                timeout=None,
                follow_redirects=True,
                verify=self.config.verify_ssl,
            ) as client:
                async with client.stream("GET", job.url, headers=headers) as resp:
                    if resp.status_code == 416:
                        if part.exists():
                            part.rename(dest)
                        job.status = JobStatus.COMPLETED
                        job.finished_at = time.time()
                        await self._finish_job(job, dest)
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
                            if self._cancel or job_id in self._cancelled_jobs:
                                job.status = JobStatus.CANCELLED
                                job.finished_at = time.time()
                                self._cancelled_jobs.discard(job_id)
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
            await self._finish_job(job, dest)

        except Exception as exc:  # noqa: BLE001
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = time.time()
            await self._emit("job_updated", {"job": job.to_dict()})
            if self._batch_id:
                append_history(self.history_path, job_finished_record(self._batch_id, job.to_dict()))

    async def _finish_job(self, job: DownloadJob, dest: Path) -> None:
        update_sidecar(
            self.download_dir,
            job.episode,
            title=job.title,
            date_label=job.date_label,
            media=job.media.value,
            filename=job.filename,
            url=job.url,
            file_path=dest,
        )
        await self._emit("job_updated", {"job": job.to_dict()})
        if self._batch_id:
            append_history(self.history_path, job_finished_record(self._batch_id, job.to_dict()))