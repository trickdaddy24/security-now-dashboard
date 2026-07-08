<div align="center">

# Security Now Dashboard

[![Tests](https://github.com/trickdaddy24/security-now-dashboard/actions/workflows/tests.yml/badge.svg)](https://github.com/trickdaddy24/security-now-dashboard/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/version-1.0.0-3DFF9A.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python fork of [Seth Leedy's GRC Security Now downloader](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT) with a **real-time WebSocket dashboard** — watch episode downloads, speed, and queue status live in the browser.

*Inspired by GRC · Built for homelab archival · Not affiliated with GRC or TWiT*

</div>

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Dashboard Usage](#dashboard-usage)
- [Episode & Media Options](#episode--media-options)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Backup & Recovery](#backup--recovery)
- [Roadmap](#roadmap)
- [Version History](#version-history)
- [Credits](#credits)
- [License](#license)

## Features

- **GRC archive sync** — parses [grc.com/securitynow.htm](https://www.grc.com/securitynow.htm) for latest episode number, titles, and dates
- **Multi-format downloads** — audio HQ/LQ, TWiT CDN audio, transcript `.txt`/`.pdf`/`.html`, show notes PDF
- **Episode selection** — `latest`, `next` (auto-increment from local files), single episode, ranges (`1080:1086`), `all`
- **Parallel downloads** — configurable concurrency (1–8) with resume and skip-existing
- **Live dashboard** — WebSocket progress bars, throughput, active/queued/completed counts
- **REST API** — start batches, cancel, poll status, fetch catalog
- **Docker-ready** — single-container deploy with volume-mounted download directory
- **Upstream parity (planned)** — RSS feeds, transcript search, full CLI flags — see [ROADMAP.md](ROADMAP.md)

## Architecture

```
  browser ──HTTP/WS──▶  FastAPI (app.py)
                           │
                           ├── static/     dashboard UI
                           ├── /api/*      REST control plane
                           ├── /ws         live job events
                           │
                           └── grc_downloader/
                                 ├── parser.py     scrape GRC catalog + build URLs
                                 └── downloader.py async queue + streaming I/O
                                          │
                                          ▼
                               downloads/  (local episode files)
                                          │
                                          ▼
                               GRC media.grc.com · grc.com/sn · cdn.twit.tv
```

| Component | Role | Path |
|---|---|---|
| **Dashboard** | Launch batches, watch live progress | `static/` |
| **API** | Catalog, status, start/cancel jobs | `app.py` |
| **Parser** | Episode list + media URL builder | `grc_downloader/parser.py` |
| **Downloader** | Job queue, progress broadcast, disk I/O | `grc_downloader/downloader.py` |
| **Storage** | Downloaded MP3/PDF/TXT files | `downloads/` (or `SN_DOWNLOAD_DIR`) |

## Quick Start

### Local (recommended for first run)

```bash
git clone https://github.com/trickdaddy24/security-now-dashboard.git
cd security-now-dashboard
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8787
```

Open **http://127.0.0.1:8787**, pick episodes and media types, click **Start downloads**.

### Docker

```bash
docker compose up --build -d
```

Dashboard: **http://localhost:8787** · Downloads persist in `./data/downloads/`.

### Smoke test

```bash
python test_smoke.py
```

## Configuration

| File | Purpose |
|---|---|
| `.env` | Optional local overrides (copy from `.env.example`) |
| `docker-compose.yml` | Container ports, volume mount, health check |
| `SN_DOWNLOAD_DIR` | Where episode files are written |

No database — state is in-memory for active jobs; completed files live on disk.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SN_DOWNLOAD_DIR` | No | `./downloads` | Directory for downloaded episode files |
| `SN_HOST` | No | `127.0.0.1` | Bind host when using `python app.py` directly |
| `SN_PORT` | No | `8787` | Bind port when using `python app.py` directly |

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | Health check (`{"status":"ok"}`) |
| `GET` | `/api/catalog` | Latest episode + recent archive entries |
| `GET` | `/api/status` | Full job snapshot (counts + all jobs) |
| `POST` | `/api/download` | Start a download batch |
| `POST` | `/api/cancel` | Cancel the running batch |
| `WS` | `/ws` | Live events: `snapshot`, `batch_started`, `job_updated`, `batch_finished` |

### Start download (example)

```bash
curl -X POST http://127.0.0.1:8787/api/download \
  -H "Content-Type: application/json" \
  -d '{"episodes":"latest","media":["audio_hq"],"parallel":2,"skip_existing":true}'
```

### Media type values

| Value | File |
|---|---|
| `audio_hq` | `sn-XXXX.mp3` (GRC HQ) |
| `audio_lq` | `sn-XXXX-lq.mp3` |
| `audio_twit` | `sn-XXXX-twit.mp3` (TWiT CDN) |
| `transcript_txt` | `sn-XXXX.txt` |
| `transcript_pdf` | `sn-XXXX.pdf` |
| `transcript_html` | `sn-XXXX.htm` |
| `show_notes` | `sn-XXXX-notes.pdf` |

## Dashboard Usage

<!-- screenshot: dashboard with active download progress bars -->

1. **Episodes** — `latest`, `next`, `1086`, `1080:1086`, or `all`
2. **Media types** — check one or more formats per batch
3. **Parallel** — how many simultaneous downloads (default 2)
4. **Skip existing** — leave checked to avoid re-downloading files already on disk

The status pill turns **Live** when the WebSocket connects. Progress updates stream automatically — no refresh needed.

## Episode & Media Options

Mapped from the original bash script:

| Original flag | Dashboard / API equivalent |
|---|---|
| `-latest` | `episodes: "latest"` |
| `-ep 1080:1086` | `episodes: "1080:1086"` |
| `-all` | `episodes: "all"` |
| (no flags — next ep) | `episodes: "next"` |
| `-ahq` / `-alq` | `audio_hq` / `audio_lq` |
| `-eptxt` / `-eppdf` / `-ephtml` / `-epnotes` | transcript + show_notes media types |
| `-pd 4` | `parallel: 4` |
| `-d /path` | `SN_DOWNLOAD_DIR` env var |

## Project Structure

```
security-now-dashboard/
├── app.py                 # FastAPI app + WebSocket hub
├── grc_downloader/
│   ├── parser.py          # GRC catalog + URL builder
│   ├── downloader.py      # Async download manager
│   └── models.py          # Job/media enums
├── static/
│   ├── index.html         # Dashboard shell
│   ├── styles.css         # Terminal-style UI
│   └── app.js             # WebSocket client
├── test_smoke.py          # Offline smoke tests
├── Dockerfile
├── docker-compose.yml
├── README.md
├── ROADMAP.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── VERSION
```

## Deployment

### Standalone / LAN

Default `docker-compose.yml` publishes port **8787**. Bind to your LAN IP or put behind a reverse proxy.

### Saltbox (Traefik)

Pattern matches other homelab apps (Notifier, MovieNexus):

1. Remove the `ports:` block from `docker-compose.yml`
2. Attach the external `saltbox` network
3. Add Traefik labels for your subdomain, e.g. `sn.yourdomain.com`
4. Mount a persistent volume for `/data/downloads`

Example labels (adjust domain and cert resolver):

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.sn-dashboard.rule=Host(`sn.example.com`)
  - traefik.http.routers.sn-dashboard.entrypoints=websecure
  - traefik.http.routers.sn-dashboard.tls.certresolver=letsencrypt
  - traefik.http.services.sn-dashboard.loadbalancer.server.port=8787
```

> **Note:** v1.0.0 has no built-in authentication. Do not expose publicly without Authelia, basic auth, or VPN.

## Backup & Recovery

**Persistent state** = files in `SN_DOWNLOAD_DIR` (default `./downloads` or Docker `./data/downloads`).

### Backup (online-safe)

```bash
# Local
tar -czf security-now-backup-$(date +%F).tar.gz downloads/

# Docker volume
tar -czf security-now-backup-$(date +%F).tar.gz data/downloads/
```

### Restore

```bash
tar -xzf security-now-backup-YYYY-MM-DD.tar.gz
# Ensure SN_DOWNLOAD_DIR points at the restored folder
```

### Disaster recovery

1. Re-clone the repo or pull the latest Docker image
2. Restore the `downloads/` tarball to the same path
3. `docker compose up -d` or restart `uvicorn`
4. Use `skip_existing: true` — already-downloaded files are marked **skipped**

## Roadmap

Five phases — full detail in [ROADMAP.md](ROADMAP.md):

| Phase | Theme | Status |
|-------|--------|--------|
| **1** | Foundation — downloader + live dashboard | Shipped (v1.0.0) |
| **2** | CLI & automation — bash parity, cron, JSON output | Planned |
| **3** | Library & discovery — RSS, transcript search, gap reports | Planned |
| **4** | Dashboard & UX — library browser, charts, mobile | Planned |
| **5** | Homelab production — Saltbox, watcher, Notifier hooks | Planned |

## Version History

| Version | Date | Notes |
|---|---|---|
| **1.0.0** | 2026-07-08 | Initial release — downloader + live dashboard + Docker + CI |

Full details: [CHANGELOG.md](CHANGELOG.md)

## Credits

- **Original inspiration:** [Seth Leedy — GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT) (bash, v2.2)
- **Show:** [Security Now!](https://www.grc.com/securitynow.htm) by Steve Gibson & Leo Laporte
- **Media hosts:** GRC (`media.grc.com`, `grc.com/sn`) and TWiT (`cdn.twit.tv`)

This project is an independent fork for personal archival and homelab use. Respect GRC/TWiT terms and bandwidth.

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026 Minus One Labs.