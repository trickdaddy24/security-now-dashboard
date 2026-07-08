from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("episode", "media", "url", "status_code", "batch_id", "job_id", "filename"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def log_download_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    episode: int | None = None,
    media: str | None = None,
    url: str | None = None,
    status_code: int | None = None,
    batch_id: str | None = None,
    job_id: str | None = None,
    filename: str | None = None,
) -> None:
    extra = {
        k: v
        for k, v in {
            "episode": episode,
            "media": media,
            "url": url,
            "status_code": status_code,
            "batch_id": batch_id,
            "job_id": job_id,
            "filename": filename,
        }.items()
        if v is not None
    }
    logger.log(level, message, extra=extra)


def setup_json_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    formatter = JsonLogFormatter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))