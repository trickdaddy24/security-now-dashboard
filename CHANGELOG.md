# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Playwright E2E dashboard tests
- Show notes PDF full-text search (pdftotext)
- Compressed transcript cache for low-disk systems

## [1.8.1] - 2026-07-08

### Added
- **Telegram startup notification** on container start/deploy with version, public URL, and external IP
- **`SN_EXTERNAL_IP`** env override (set on Saltbox to `138.201.28.235`); falls back to ipify lookup

### Changed
- **All Telegram alerts** (heartbeat, downloads, batches, watcher, test) include `v{version}` and public host IP instead of Docker bridge IP

## [1.8.0] - 2026-07-08

### Added
- **TWiT episode art** — fetches per-episode thumbnails from TWiT RSS (`itunes:image`) and saves Plex/Kodi local art as `-thumb.jpg` and `-fanart.jpg` beside each video
- **Library tools** — `POST /api/library/migrate-kodi` and `POST /api/library/fetch-thumbs`; dashboard buttons on Library tab
- **`deploy/saltbox/migrate-kodi.sh`** — one-shot server rename + thumb fetch for existing Plex library

### Changed
- **Kodi-only filenames** — all downloads use `Security Now S{year}E{ep}.mp4` (video) and tagged variants for other media; filename format dropdown removed from UI
- **Default config** — `SN_FILENAME_FORMAT=kodi`, `SN_FETCH_THUMBS=1`

## [1.7.0] - 2026-07-08

### Added
- **Telegram** — per-download alerts, 6h heartbeat, Insights tab status + Send test
- **Dashboard event log** — tails `SN_LOG_FILE`, live on Downloads tab
- **Batch by time** — last N days/weeks/months with size estimate
- **Media chips** — quick toggles with per-type size hints
- **Period-synced episode picker** — wide column layout, filters by air date

### Changed
- **Default audio** — TWiT CDN (`audio_twit`); GRC audio hidden from dashboard (API/CLI still support `audio_hq`)
- **FIFA themes** — Terminal, USA, Argentina + 7 countries (Mexico, Canada, Brazil, France, Germany, England, Spain)
- **Library scan** — faster default (skip checksums), loading progress bar
- **Downloads UI** — decluttered media/episode controls, consolidated estimate line

## [1.6.0] - 2026-07-08

### Added
- **FIFA '26 themes** — USA, Mexico, Canada, Brazil, Argentina plus Terminal and Daylight in a top-bar theme dropdown (`sn-theme` in `localStorage`)
- **Per-episode folders** — `SN_EPISODE_FOLDERS=1`, `grc_downloader/paths.py`, recursive library/search/cleanup scan; `deploy/saltbox/migrate-episode-folders.sh`
- **Download logging** — structured logs to `SN_LOG_FILE` (e.g. `/var/log/security-now/logs/app.log`)
- **Saltbox production** — primary URL `https://sn.aaa.stunna.xyz` (Authelia), Plex mount at `/mnt/local/Media/grc`, `deploy/saltbox/CLOUDFLARE-ACCESS.md`, `add-dns-sn-aaa.sh`

### Changed
- **TWiT video URLs** — Megaphone CDN (`pscrb.fm/...`) replaces retired `cdn.twit.tv` `_hq.mp4` links (~2–3 GB downloads work again)
- **Media serving** — `/media/{file_path:path}` and encoded `mediaUrl()` for nested paths like `sn-1086/sn-1086.mp3`; RSS enclosure URLs updated
- **Daylight theme** — improved contrast and CSS variables
- **Saltbox hardening** — port 8787 closed (`ports: !reset null`), `SN_DEV_MODE=1` behind Authelia; `sn.e4z.xyz` redirects to `sn.aaa.stunna.xyz` (health endpoints stay public on e4z)

### Fixed
- Library MP3 playback (silent player, missing timestamp) for files stored in per-episode subfolders

## [1.5.0] - 2026-07-08

### Added
- **Saltbox deploy** — `docker-compose.saltbox.yml` (Traefik, `saltbox` network, resource limits, read-only root)
- **Security** — optional HTTP basic auth, `X-SN-API-Key`, rate limit on `POST /api/download`, CORS lockdown (`SN_DEV_MODE=0`)
- **Episode watcher** — poll GRC every N hours, auto-queue new episodes (`SN_WATCHER_ENABLED`)
- **Integrations** — Notifier/Discord webhooks, Plex scan hint, Kodi `.strm` export, OPML for RSS feeds
- **Observability** — `GET /metrics` (Prometheus), JSON stdout logging, Grafana dashboard JSON
- **Reliability** — GRC circuit breaker, HTTP retry with backoff, stale `.part` cleanup, download-dir file lock
- `GET /api/watcher/status`, `GET /api/integrations/opml`, `POST /api/integrations/kodi`, `POST /api/integrations/plex-hint`
- Insights tab: watcher status line
- `deploy/backup/backup-sn.sh` nightly backup example
- Config: `[security]`, `[watcher]`, `[ops]` sections + `SN_*` env vars
- `test_phase5.py` offline tests

### Changed
- App lifespan: startup cleanup, optional watcher background task, config reload
- Downloader: Discord/Notifier on batch complete, stream download retries

## [1.4.0] - 2026-07-08

### Added
- **Version badge** on top-right (readable high-contrast style)
- **Episode picker** grid — click recent 30 to queue
- **Per-job cancel**, drag-and-drop queue reorder, speed sparklines, ETA display
- **Notify** toggle — browser notification when batch completes
- **Light/dark theme** toggle (◐ button, persisted)
- **Insights tab** — batch timeline, weekly downloads chart, GRC sync status
- Library: sort/filter, inline audio player, transcript modal, show notes viewer
- Storage breakdown by media type, disk free %, CSV export
- `GET /api/insights`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/reorder`
- `GET /api/library/export.csv`
- PWA `manifest.json` + icon
- `test_insights.py`, `test_dashboard_static.py`

### Changed
- GRC sync line on Downloads tab
- Improved mobile layout for topbar and job list

## [1.3.0] - 2026-07-08

### Added
- **Version badge** on dashboard header and footer (from `VERSION` via `/api/config`)
- **Library tab** — scan local archive, gaps, missing formats, checksum status
- **Search tab** — SQLite FTS5 transcript search with highlighted snippets
- **RSS feeds** — audio, video, text, combined; CLI `-create-rss-*`, dashboard Rebuild button
- `GET /api/library`, `GET /api/search`, `POST /api/search/reindex`
- `GET /api/rss/status`, `POST /api/rss/rebuild`, `GET /feed/{audio|video|text|all}.rss`
- `GET /media/{filename}` for HTTP RSS enclosures behind Traefik
- `POST /api/library/fill-transcripts` — queue missing `.txt` downloads
- CLI: `-stxt`, `-dandstxt`, `--reindex-search`, `-rss-limit`
- Config: `[rss]`, `[search]`, `SN_RSS_BASE_URL`, `SN_RSS_DIR`, `SN_SEARCH_DB`
- `test_library.py` offline tests

### Changed
- Dashboard tab navigation: Downloads · Library · Search
- App version reads dynamically from `VERSION` file (now **1.3.0**)

## [1.2.0] - 2026-07-08

### Added
- Headless CLI: `python -m grc_downloader` and `sn-download` launcher
- GRC-Downloader.sh flag parity: `-ep`, `-latest`, `-all`, `-ahq`/`-alq`/`-vhd`/`-vhq`/`-vlq`, `-eptxt`/`-eppdf`/`-ephtml`/`-epnotes`, `-d`, `-pd`, `-p`, `-q`, `-ff`, `-skip-digital-cert-check`, `-u`, `--json`, `--retry-failed`
- Exit codes: 0 success, 1 partial failure, 2 usage, 3 disk space
- CLI progress on stderr; `--json` machine output for scripting
- `SN_EPISODES`, `SN_MEDIA`, `SN_QUIET`, `SN_JSON`, `SN_PRETEND`, `SN_SKIP_EXISTING` env vars
- `GET /api/jobs/history` — aggregated batch history from JSONL log
- Idempotent `POST /api/download` via `client_token` (24h dedupe)
- Webhook `callback_url` on batch complete
- Systemd timer example (`deploy/systemd/`)
- `docker-compose.cli.yml` for one-shot downloads without dashboard
- `test_cli.py` offline CLI tests

## [1.1.0] - 2026-07-08

### Added
- TWiT video downloads: HD / HQ / LQ (`video_hd`, `video_hq`, `video_lq`)
- Filename presets: `raw`, `ordered`, `kodi` (dashboard select + `SN_FILENAME_FORMAT`)
- Disk space pre-check before batches (`min_free_mb` in config, `/api/download/estimate`)
- JSONL download history (`.sn-history.jsonl`) with `GET /api/history`
- `config.toml` + `SN_*` environment variables (`config.toml.example`)
- Retry failed jobs only (`retry_failed` on `POST /api/download`, dashboard button)
- Per-episode metadata sidecars (`sn-XXXX.meta.json` with SHA-256)
- Batch state file (`.sn-last-batch.json`) for crash recovery
- Expanded smoke tests (parser edge cases, filenames, disk estimates)
- Integration test: download show notes PDF in CI (skippable via `SN_SKIP_INTEGRATION`)

### Changed
- Dashboard: video media checkboxes, filename format select, disk free display, retry button
- `GET /api/config` exposes runtime settings and disk free bytes
- Catalog response includes `disk_free_bytes`

## [1.0.0] - 2026-07-08

### Added
- Python downloader fork inspired by [Seth Leedy's GRC-Downloader](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT)
- GRC archive parser (episode number, title, date from `grc.com/securitynow.htm`)
- Media types: Audio HQ/LQ, TWiT CDN audio, transcript `.txt`/`.pdf`/`.html`, show notes PDF
- Episode specs: `latest`, `next`, single episode, ranges (`1080:1086`), `all`
- Parallel downloads with resume, skip-existing, and per-job progress tracking
- FastAPI backend with REST API and WebSocket live updates
- Terminal-style web dashboard (progress bars, throughput, job queue)
- Docker image and `docker-compose.yml` with health check
- Project documentation suite (README, ROADMAP, CONTRIBUTING, LICENSE)

[Unreleased]: https://github.com/trickdaddy24/security-now-dashboard/compare/v1.7.0...HEAD
[1.7.0]: https://github.com/trickdaddy24/security-now-dashboard/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/trickdaddy24/security-now-dashboard/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/trickdaddy24/security-now-dashboard/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.4.0
[1.3.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.3.0
[1.2.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.2.0
[1.1.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.1.0
[1.0.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.0.0