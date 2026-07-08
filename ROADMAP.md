# Security Now Dashboard — Roadmap

Modern Python fork of [Seth Leedy's GRC-Downloader](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT) with a **live WebSocket dashboard** for watching downloads in real time.

Phases are ordered by dependency: each phase builds on the last. Check boxes as they ship; link PRs/issues inline when you start work.

---

## Overview

| Phase | Theme | Status |
|-------|--------|--------|
| **1** | Foundation — downloader + live dashboard | **Shipped** (v1.1.0) |
| **2** | CLI & automation — bash-script parity, scripting | Planned |
| **3** | Library & discovery — RSS, search, media library | Planned |
| **4** | Dashboard & UX — polish, browsing, insights | Planned |
| **5** | Homelab production — Saltbox, auth, watchers, integrations | Planned |

---

## Phase 1 — Foundation

**Goal:** Reliable GRC downloads with a real-time control plane. Personal archival that “just works” on Windows, Linux, and Docker.

**Status:** Shipped in **v1.1.0** (July 2026). Phase 1 polish complete; ready for Phase 2 CLI work.

### Shipped

- [x] GRC archive parser (`securitynow.htm` → episode #, title, date)
- [x] Media URLs: Audio HQ/LQ (GRC), TWiT CDN, transcript `.txt`/`.pdf`/`.html`, show notes PDF
- [x] Episode specs: `latest`, `next`, single, ranges (`1080:1086`), `all`
- [x] Async downloader: streaming progress, resume (`.part`), parallel jobs, skip-existing
- [x] FastAPI REST + WebSocket live updates
- [x] Terminal-style dashboard (progress, throughput, job queue)
- [x] Docker + `docker-compose.yml` + `/health`
- [x] Smoke tests + GitHub Actions CI
- [x] Docs suite (README, CHANGELOG, CONTRIBUTING, LICENSE)

### Phase 1 polish (v1.1.0)

- [x] Video formats: HD / HQ / LQ from `cdn.twit.tv/video/sn` (upstream `-vhd`, `-vhq`, `-vlq`)
- [x] Filename presets: `-ff ordered`, `-ff kodi`, custom `<showname> <episodenumber> …` templates
- [x] Disk space pre-check before batch (`chk_disk_space` parity from upstream)
- [x] Download history log (JSONL or SQLite) — survives restart, feeds Phase 4 charts
- [x] Config file (`config.toml` or `.env`) for defaults: download dir, parallel, preferred media
- [x] Graceful partial-batch resume after crash (re-queue failed jobs only)
- [x] Episode metadata sidecar (`.json` per episode: title, date, URLs, checksum, downloaded_at)
- [x] Unit tests for parser edge cases (HTML variants, missing titles, `... min` duration)
- [x] Integration test: download one small file (show notes) in CI with network allowlist

**Success criteria:** Download latest HQ audio + show notes from dashboard or API; Docker health green; zero manual steps after clone.

---

## Phase 2 — CLI & automation

**Goal:** Full parity with Seth Leedy's bash script for cron, SSH, and headless homelab use — no browser required.

**Why:** Vacation mode, nightly cron on Saltbox, and scripting (`sn-download -latest -ahq`) should work without the dashboard.

### CLI (`sn-download` or `python -m grc_downloader`)

- [ ] Flag mapping from `GRC-Downloader.sh`:
  - [ ] `-ep N` / `-ep N:M` / `-ep N:latest`
  - [ ] `-latest`, `-all`, implicit `next` when no episode flags
  - [ ] `-ahq`, `-alq`, `-vhd`, `-vhq`, `-vlq`
  - [ ] `-eptxt`, `-eppdf`, `-ephtml`, `-epnotes`
  - [ ] `-d PATH`, `-pd N`, `-p` (pretend/dry-run), `-q` (quiet)
  - [ ] `-skip-digital-cert-check` → httpx `verify=False`
- [ ] `-u` self-update check against GitHub release (optional, not auto-replace)
- [ ] Exit codes: `0` success, `1` partial failure, `2` usage error, `3` disk space
- [ ] Progress to stderr (human) or `--json` (machine) for piping to Notifier/scripts

### Scheduling & automation

- [ ] Systemd timer unit example (`sn-download-latest.service` + `.timer`)
- [ ] Cron one-liner docs for weekly “catch up from `next`”
- [ ] `docker compose run` recipe for one-shot downloads without keeping dashboard up
- [ ] Environment-only mode: all options via `SN_*` env vars (12-factor)

### API hardening (headless clients)

- [ ] `GET /api/jobs/history` — last N batches from Phase 1 log
- [ ] Idempotent `POST /api/download` with `client_token` to avoid duplicate batches
- [ ] Webhook callback URL on batch complete (`?callback=https://…`)

**Success criteria:** `sn-download -latest -ahq -q` in cron downloads the newest episode with no UI; JSON mode usable from bash.

---

## Phase 3 — Library & discovery

**Goal:** Turn a folder of downloads into a **searchable personal archive** — RSS for players, full-text search, library browser.

**Why:** The upstream script's killer features after downloading are RSS feeds and transcript search. This phase makes the archive useful years later.

### RSS feeds (upstream `-create-rss-*`)

- [ ] `security_now_audio.rss` from local MP3s + GRC metadata
- [ ] `security_now_video.rss` (when Phase 1 video lands)
- [ ] `security_now_text.rss` — show notes + transcript excerpts
- [ ] Combined `security_now.rss` (`-create-rss-feeds` parity)
- [ ] `-rss-filename` / config path override
- [ ] `-rss-limit N` — truncate description text per item
- [ ] Enclosure URLs: `file://` for local players, or HTTP base URL when served behind Traefik
- [ ] Dashboard: **Rebuild RSS** button + last-built timestamp
- [ ] Serve RSS at `GET /feed/audio.rss` (optional static + dynamic)

### Transcript search (upstream `-stxt` / `-dandstxt`)

- [ ] Index all local `.txt` transcripts (SQLite FTS5 or tantivy)
- [ ] Case-insensitive search API: `GET /api/search?q=spinrite`
- [ ] Dashboard search tab with highlighted snippets + episode jump links
- [ ] `-dandstxt`: download missing transcripts then search (one-shot CLI flag)
- [ ] Compressed cache dir (gzip/7z) for `.tmp_search_txt` parity — optional on low-disk systems
- [ ] Search across show notes PDF text (pdftotext or embedded extract)

### Library intelligence

- [ ] `GET /api/library` — scan download dir: episode #, formats on disk, total size, gaps in sequence
- [ ] “Missing episodes” report: compare local set vs GRC latest (e.g. you have 1–900 but gap at 412)
- [ ] “Missing formats” per episode (have MP3 but no transcript)
- [ ] One-click batch: “fill gaps” / “download all missing transcripts”
- [ ] SHA-256 checksum verify after download; re-download on mismatch
- [ ] Import legacy folders from old `GRC-Downloader.sh` naming (`sn-01086.mp3` etc.)

**Success criteria:** Plex/Apple Podcasts can subscribe to your local RSS; search finds “SQRL” across 500+ transcripts in &lt;1s.

---

## Phase 4 — Dashboard & UX

**Goal:** A dashboard worth leaving open on a second monitor — browse the archive, understand download health, enjoy using it.

**Why:** Phase 1 proved live progress works; Phase 4 makes the product feel finished.

### Live operations UI

- [ ] Episode picker — visual grid of recent 30 from catalog, click to queue
- [ ] Drag-and-drop priority reorder for queued jobs
- [ ] Per-job cancel (not only whole-batch cancel)
- [ ] Sparkline: download speed over last 60s per active job
- [ ] ETA column from bytes remaining ÷ speed
- [ ] Sound/toast optional notification when batch completes (browser Notification API)
- [ ] Dark/light theme toggle (keep terminal green as default)
- [ ] Mobile-responsive layout for phone status checks on vacation

### Library browser

- [ ] “Library” tab: table of episodes on disk (sort by #, date, size)
- [ ] Inline play audio in browser (HTML5 `<audio>` for MP3)
- [ ] Open transcript / show notes in modal or new tab
- [ ] Filter: audio only, transcripts only, complete sets
- [ ] Storage dashboard: total GB, breakdown by media type, disk free %

### History & insights

- [ ] Batch history timeline (from Phase 1 log): date, episodes, success/fail counts
- [ ] Chart: downloads per week (last 90 days)
- [ ] “Last sync” indicator vs GRC latest episode
- [ ] Export CSV of library inventory

### Quality

- [ ] E2E smoke test (Playwright): load dashboard, mock WebSocket, assert UI renders
- [ ] Accessibility pass: keyboard nav, ARIA on progress bars
- [ ] PWA manifest — “Add to Home Screen” on iPad for homelab status

**Success criteria:** User can browse 1000+ local episodes, play audio, and queue new downloads without reading README.

---

## Phase 5 — Homelab production

**Goal:** Runs 24/7 on Saltbox next to Plex/Notifier — secure, observable, self-healing.

**Why:** You deploy Notifier and MovieNexus on `138.201.28.235`; this should fit the same playbook.

### Saltbox / Traefik deployment

- [ ] `docker-compose.saltbox.yml` with external `saltbox` network (no published ports)
- [ ] Traefik labels template (`sn.yourdomain.com`, TLS, Authelia middleware)
- [ ] Persistent volume docs for `/data/downloads` on host bind vs named volume
- [ ] Resource limits (CPU/memory) for download bursts
- [ ] Read-only root filesystem where practical; tmp for `.part` files

### Security & access

- [ ] Optional HTTP basic auth (`SN_AUTH_USER` / `SN_AUTH_PASSWORD`)
- [ ] Document Authelia forward-auth pattern (match Notifier)
- [ ] Rate limit `POST /api/download` (per IP / per API key)
- [ ] API key header for automation (`X-SN-API-Key`)
- [ ] CORS lockdown when not in dev mode

### Watchers & integrations

- [ ] **New episode watcher** — poll GRC every N hours; auto-queue `latest` when # bumps
- [ ] **Notifier integration** — webhook/Telegram when new episode downloaded or watcher fires
- [ ] **Discord webhook** on batch complete (success/fail summary)
- [ ] Plex: optional post-download hook — hint path for podcast library scan
- [ ] Kodi: `sn.strm` or playlist export for local MP3 paths
- [ ] Immich irrelevant; **Podcast apps**: OPML export pointing at Phase 3 RSS

### Observability & ops

- [ ] Prometheus metrics: `sn_jobs_active`, `sn_bytes_total`, `sn_last_episode_number`, `sn_errors_total`
- [ ] Grafana dashboard JSON (optional import)
- [ ] Structured JSON logging to stdout for Loki/Vector (you run Vector on Saltbox)
- [ ] Uptime Kuma / healthcheck.io monitor on `/health`
- [ ] Backup cron example: nightly `tar.gz` of download dir + RSS + search index

### Reliability

- [ ] Circuit breaker on GRC fetch (like MovieNexus Box Office Mojo pattern)
- [ ] Retry with exponential backoff on transient HTTP errors
- [ ] Stale `.part` cleanup job (older than 7 days)
- [ ] Multi-instance warning: only one writer per download dir (file lock)

**Success criteria:** Dashboard at `https://sn.e4z.xyz` (or similar) behind Authelia; new SN episode auto-downloads and pings Telegram via Notifier within an hour of GRC posting.

---

## Cross-phase ideas (backlog)

Park here until a phase owns them:

- [ ] SpinRite / SQRL easter egg: filter episodes mentioning keywords from Steve's running topics
- [ ] “Steve said” quote extractor from transcripts (LLM-assisted, optional)
- [ ] Compare TWiT CDN vs GRC HQ file hashes — prefer single canonical copy
- [ ] Bandwidth throttle (`--max-mbps`) for shared homelab uplink
- [ ] IPv6 / proxy egress options for restrictive networks
- [ ] Windows Service wrapper for dashboard (NSSM docs)
- [ ] ARM64 Docker image (Raspberry Pi archival node)

---

## Non-goals

- Public multi-tenant hosting or re-distributing GRC/TWiT media
- Replacing the official [GRC/TWiT RSS](http://leoville.tv/podcasts/sn.xml)
- Scraping behind paywalls or circumventing rate limits aggressively
- Training ML models on transcript content (out of scope unless explicitly added later)

---

## How to use this doc

1. Pick a phase and open a GitHub issue: `phase-2: sn-download CLI skeleton`
2. Check boxes in PR descriptions; move items to CHANGELOG on release
3. Bump **VERSION** + tag when a phase milestone ships (e.g. `1.1.0` = Phase 2 CLI MVP)

**Last updated:** July 2026