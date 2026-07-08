from __future__ import annotations

import atexit
import os
from pathlib import Path


class DownloadDirLock:
    """Exclusive lock — one writer per download directory."""

    def __init__(self, download_dir: Path):
        self.download_dir = Path(download_dir)
        self.lock_path = self.download_dir / ".sn-download.lock"
        self._held = False

    def acquire(self) -> bool:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            os.write(fd, f"{os.getpid()}\n".encode())
            os.close(fd)
            self._held = True
            atexit.register(self.release)
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        if not self._held:
            return
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass
        self._held = False

    def holder_pid(self) -> int | None:
        if not self.lock_path.is_file():
            return None
        try:
            return int(self.lock_path.read_text(encoding="utf-8").strip().split()[0])
        except (ValueError, OSError):
            return None