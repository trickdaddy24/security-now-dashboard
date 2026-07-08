from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AppConfig:
    download_dir: Path = field(default_factory=lambda: ROOT / "downloads")
    parallel: int = 2
    skip_existing: bool = True
    filename_format: str = "raw"
    default_media: list[str] = field(default_factory=lambda: ["audio_hq"])
    verify_ssl: bool = True
    min_free_mb: int = 500
    history_file: Path | None = None

    def resolve_history_path(self) -> Path:
        if self.history_file:
            return self.history_file
        return self.download_dir / ".sn-history.jsonl"


def _load_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config() -> AppConfig:
    cfg = AppConfig()
    for path in (ROOT / "config.toml", Path.home() / ".config" / "security-now-dashboard" / "config.toml"):
        data = _load_toml(path)
        if not data:
            continue
        dl = data.get("downloads", {})
        if dl.get("dir"):
            cfg.download_dir = Path(dl["dir"]).expanduser()
        if "parallel" in dl:
            cfg.parallel = int(dl["parallel"])
        if "skip_existing" in dl:
            cfg.skip_existing = bool(dl["skip_existing"])
        if dl.get("filename_format"):
            cfg.filename_format = str(dl["filename_format"])
        if "min_free_mb" in dl:
            cfg.min_free_mb = int(dl["min_free_mb"])
        if "verify_ssl" in dl:
            cfg.verify_ssl = bool(dl["verify_ssl"])
        media = data.get("media", {})
        if media.get("default"):
            cfg.default_media = list(media["default"])
        if data.get("history", {}).get("file"):
            cfg.history_file = Path(data["history"]["file"]).expanduser()
        break

    if env := os.getenv("SN_DOWNLOAD_DIR"):
        cfg.download_dir = Path(env)
    if env := os.getenv("SN_PARALLEL"):
        cfg.parallel = int(env)
    if env := os.getenv("SN_FILENAME_FORMAT"):
        cfg.filename_format = env
    if env := os.getenv("SN_VERIFY_SSL"):
        cfg.verify_ssl = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_MIN_FREE_MB"):
        cfg.min_free_mb = int(env)
    if env := os.getenv("SN_HISTORY_FILE"):
        cfg.history_file = Path(env)
    if env := os.getenv("SN_SKIP_EXISTING"):
        cfg.skip_existing = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_MEDIA"):
        cfg.default_media = [m.strip() for m in env.split(",") if m.strip()]

    cfg.download_dir.mkdir(parents=True, exist_ok=True)
    return cfg