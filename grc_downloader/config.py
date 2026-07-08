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
    default_media: list[str] = field(default_factory=lambda: ["audio_twit"])
    verify_ssl: bool = True
    min_free_mb: int = 500
    history_file: Path | None = None
    rss_dir: Path | None = None
    rss_base_url: str | None = None
    rss_limit: int = 500
    search_db: Path | None = None
    auth_user: str | None = None
    auth_password: str | None = None
    api_key: str | None = None
    dev_mode: bool = True
    cors_origins: list[str] = field(default_factory=list)
    rate_limit_per_minute: int = 30
    watcher_enabled: bool = False
    watcher_interval_hours: float = 6.0
    notifier_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_on_job_complete: bool = True
    heartbeat_interval_hours: float = 6.0
    log_json: bool = False
    log_level: str = "INFO"
    log_file: Path | None = None
    part_cleanup_days: int = 7
    require_download_lock: bool = True
    episode_folders: bool = True

    def resolve_history_path(self) -> Path:
        if self.history_file:
            return self.history_file
        return self.download_dir / ".sn-history.jsonl"

    def resolve_rss_dir(self) -> Path:
        return self.rss_dir if self.rss_dir else self.download_dir

    def resolve_search_db(self) -> Path:
        return self.search_db if self.search_db else self.download_dir / ".sn-search.db"


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
        rss = data.get("rss", {})
        if rss.get("dir"):
            cfg.rss_dir = Path(rss["dir"]).expanduser()
        if rss.get("base_url"):
            cfg.rss_base_url = str(rss["base_url"])
        if "limit" in rss:
            cfg.rss_limit = int(rss["limit"])
        search = data.get("search", {})
        if search.get("db"):
            cfg.search_db = Path(search["db"]).expanduser()
        sec = data.get("security", {})
        if sec.get("auth_user"):
            cfg.auth_user = str(sec["auth_user"])
        if sec.get("auth_password"):
            cfg.auth_password = str(sec["auth_password"])
        if sec.get("api_key"):
            cfg.api_key = str(sec["api_key"])
        if "dev_mode" in sec:
            cfg.dev_mode = bool(sec["dev_mode"])
        if "rate_limit_per_minute" in sec:
            cfg.rate_limit_per_minute = int(sec["rate_limit_per_minute"])
        if sec.get("cors_origins"):
            cfg.cors_origins = list(sec["cors_origins"])
        watch = data.get("watcher", {})
        if "enabled" in watch:
            cfg.watcher_enabled = bool(watch["enabled"])
        if "interval_hours" in watch:
            cfg.watcher_interval_hours = float(watch["interval_hours"])
        if watch.get("notifier_webhook"):
            cfg.notifier_webhook_url = str(watch["notifier_webhook"])
        if watch.get("discord_webhook"):
            cfg.discord_webhook_url = str(watch["discord_webhook"])
        if watch.get("telegram_bot_token"):
            cfg.telegram_bot_token = str(watch["telegram_bot_token"])
        if watch.get("telegram_chat_id"):
            cfg.telegram_chat_id = str(watch["telegram_chat_id"])
        if "telegram_on_job_complete" in watch:
            cfg.telegram_on_job_complete = bool(watch["telegram_on_job_complete"])
        if "heartbeat_interval_hours" in watch:
            cfg.heartbeat_interval_hours = float(watch["heartbeat_interval_hours"])
        ops = data.get("ops", {})
        if ops.get("telegram_bot_token"):
            cfg.telegram_bot_token = str(ops["telegram_bot_token"])
        if ops.get("telegram_chat_id"):
            cfg.telegram_chat_id = str(ops["telegram_chat_id"])
        if "telegram_on_job_complete" in ops:
            cfg.telegram_on_job_complete = bool(ops["telegram_on_job_complete"])
        if "heartbeat_interval_hours" in ops:
            cfg.heartbeat_interval_hours = float(ops["heartbeat_interval_hours"])
        if "log_json" in ops:
            cfg.log_json = bool(ops["log_json"])
        if ops.get("log_level"):
            cfg.log_level = str(ops["log_level"])
        if "part_cleanup_days" in ops:
            cfg.part_cleanup_days = int(ops["part_cleanup_days"])
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
    if env := os.getenv("SN_RSS_DIR"):
        cfg.rss_dir = Path(env)
    if env := os.getenv("SN_RSS_BASE_URL"):
        cfg.rss_base_url = env
    if env := os.getenv("SN_RSS_LIMIT"):
        cfg.rss_limit = int(env)
    if env := os.getenv("SN_SEARCH_DB"):
        cfg.search_db = Path(env)
    if env := os.getenv("SN_AUTH_USER"):
        cfg.auth_user = env
    if env := os.getenv("SN_AUTH_PASSWORD"):
        cfg.auth_password = env
    if env := os.getenv("SN_API_KEY"):
        cfg.api_key = env
    if env := os.getenv("SN_DEV_MODE"):
        cfg.dev_mode = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_CORS_ORIGINS"):
        cfg.cors_origins = [o.strip() for o in env.split(",") if o.strip()]
    if env := os.getenv("SN_RATE_LIMIT"):
        cfg.rate_limit_per_minute = int(env)
    if env := os.getenv("SN_WATCHER_ENABLED"):
        cfg.watcher_enabled = env.lower() in ("1", "true", "yes")
    if env := os.getenv("SN_WATCHER_INTERVAL_HOURS"):
        cfg.watcher_interval_hours = float(env)
    if env := os.getenv("SN_NOTIFIER_WEBHOOK"):
        cfg.notifier_webhook_url = env
    if env := os.getenv("SN_DISCORD_WEBHOOK"):
        cfg.discord_webhook_url = env
    if env := os.getenv("SN_TELEGRAM_BOT_TOKEN"):
        cfg.telegram_bot_token = env
    if env := os.getenv("SN_TELEGRAM_CHAT_ID"):
        cfg.telegram_chat_id = env
    if env := os.getenv("SN_TELEGRAM_ON_JOB_COMPLETE"):
        cfg.telegram_on_job_complete = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_HEARTBEAT_INTERVAL_HOURS"):
        cfg.heartbeat_interval_hours = float(env)
    if env := os.getenv("SN_LOG_JSON"):
        cfg.log_json = env.lower() in ("1", "true", "yes")
    if env := os.getenv("SN_LOG_LEVEL"):
        cfg.log_level = env
    if env := os.getenv("SN_LOG_FILE"):
        cfg.log_file = Path(env).expanduser()
    if env := os.getenv("SN_PART_CLEANUP_DAYS"):
        cfg.part_cleanup_days = int(env)
    if env := os.getenv("SN_REQUIRE_DOWNLOAD_LOCK"):
        cfg.require_download_lock = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_EPISODE_FOLDERS"):
        cfg.episode_folders = env.lower() not in ("0", "false", "no")
    if env := os.getenv("SN_PUBLIC_URL"):
        if not cfg.rss_base_url:
            cfg.rss_base_url = env

    cfg.download_dir.mkdir(parents=True, exist_ok=True)
    return cfg