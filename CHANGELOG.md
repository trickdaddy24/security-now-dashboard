# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Headless CLI matching original `GRC-Downloader.sh` flags
- RSS feed generation (`-create-rss-audio` parity)
- Transcript full-text search
- Optional dashboard authentication for public deploys

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

[Unreleased]: https://github.com/trickdaddy24/security-now-dashboard/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.1.0
[1.0.0]: https://github.com/trickdaddy24/security-now-dashboard/releases/tag/v1.0.0