# Security Now Dashboard — Roadmap

Modern Python fork of [Seth Leedy's GRC-Downloader](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT) with a **live WebSocket dashboard** for watching downloads in real time.

Phases are ordered by dependency: each phase builds on the last. Check boxes as they ship; link PRs/issues inline when you start work.

---

## Overview

| Phase | Theme | Status |
|-------|--------|--------|
| **1** | Foundation — downloader + live dashboard | **Shipped** (v1.1.0) |
| **2** | CLI & automation — bash-script parity, scripting | **Shipped** (v1.2.0) |
| **3** | Library & discovery — RSS, search, media library | **Shipped** (v1.3.0) |
| **4** | Dashboard & UX — polish, browsing, insights | **Shipped** (v1.4.0) |
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

**Status:** Shipped in **v1.2.0** (July 2026).

### CLI (`sn-download` or `python -m grc_downloader`)

- [x] Flag mapping from `GRC-Downloader.sh`:
  - [x] `-ep N` / `-ep N:M` / `-ep N:latest`
  - [x] `-latest`, `-all`, implicit `next` when no episode flags
  - [x] `-ahq`, `-alq`, `-vhd`, `-vhq`, `-vlq`
  - [x] `-eptxt`, `-eppdf`, `-ephtml`, `-epnotes`
  - [x] `-d PATH`, `-pd N`, `-p` (pretend/dry-run), `-q` (quiet)
  - [x] `-skip-digital-cert-check` → httpx `verify=False`
- [x] `-u` self-update check against GitHub release (optional, not auto-replace)
- [x] Exit codes: `0` success, `1` partial failure, `2` usage error, `3` disk space
- [x] Progress to stderr (human) or `--json` (machine) for piping to Notifier/scripts

### Scheduling & automation

- [x] Systemd timer unit example (`sn-download-latest.service` + `.timer`)
- [x] Cron one-liner docs for weekly “catch up from `next`”
- [x] `docker compose run` recipe for one-shot downloads without keeping dashboard up
- [x] Environment-only mode: all options via `SN_*` env vars (12-factor)

### API hardening (headless clients)

- [x] `GET /api/jobs/history` — last N batches from Phase 1 log
- [x] Idempotent `POST /api/download` with `client_token` to avoid duplicate batches
- [x] Webhook callback URL on batch complete (`callback_url` in POST body)

**Success criteria:** `sn-download -latest -ahq -q` in cron downloads the newest episode with no UI; JSON mode usable from bash.

---

## Phase 3 — Library & discovery

**Goal:** Turn a folder of downloads into a **searchable personal archive** — RSS for players, full-text search, library browser.

**Status:** Shipped in **v1.3.0** (July 2026).

### RSS feeds (upstream `-create-rss-*`)

- [x] `security_now_audio.rss` from local MP3s + GRC metadata
- [x] `security_now_video.rss`
- [x] `security_now_text.rss` — show notes + transcript excerpts
- [x] Combined `security_now.rss` (`-create-rss-feeds` parity)
- [x] `-rss-filename` / config path override (`SN_RSS_DIR`, `[rss]` in config)
- [x] `-rss-limit N` — truncate description text per item
- [x] Enclosure URLs: `file://` for local players, or HTTP via `SN_RSS_BASE_URL` / `/media/{file}`
- [x] Dashboard: **Rebuild RSS** button + last-built timestamp
- [x] Serve RSS at `GET /feed/audio.rss` (+ video, text, all)

### Transcript search (upstream `-stxt` / `-dandstxt`)

- [x] Index all local `.txt` transcripts (SQLite FTS5)
- [x] Case-insensitive search API: `GET /api/search?q=spinrite`
- [x] Dashboard search tab with highlighted snippets + episode jump links
- [x] `-dandstxt`: download missing transcripts then search (CLI + API)
- [ ] Compressed cache dir (gzip/7z) for `.tmp_search_txt` parity — optional on low-disk systems
- [ ] Search across show notes PDF text (pdftotext or embedded extract)

### Library intelligence

- [x] `GET /api/library` — scan download dir: episode #, formats on disk, total size, gaps in sequence
- [x] “Missing episodes” report: compare local set vs GRC latest
- [x] “Missing formats” per episode (have MP3 but no transcript)
- [x] One-click batch: “download all missing transcripts” (dashboard + API)
- [x] SHA-256 checksum verify on library scan (via `.meta.json` sidecars)
- [x] Legacy filename detection (`sn-01086.mp3`, kodi/ordered names)

**Success criteria:** Plex/Apple Podcasts can subscribe to your local RSS; search finds “SQRL” across 500+ transcripts in &lt;1s.

---

## Phase 4 — Dashboard & UX

**Goal:** A dashboard worth leaving open on a second monitor — browse the archive, understand download health, enjoy using it.

**Status:** Shipped in **v1.4.0** (July 2026).

### Live operations UI

- [x] Episode picker — visual grid of recent 30 from catalog, click to queue
- [x] Drag-and-drop priority reorder for queued jobs
- [x] Per-job cancel (not only whole-batch cancel)
- [x] Sparkline: download speed over last 60s per active job
- [x] ETA column from bytes remaining ÷ speed
- [x] Sound/toast optional notification when batch completes (browser Notification API)
- [x] Dark/light theme toggle (keep terminal green as default)
- [x] Mobile-responsive layout for phone status checks on vacation

### Library browser

- [x] “Library” tab: table of episodes on disk (sort by #, date, size)
- [x] Inline play audio in browser (HTML5 `<audio>` for MP3)
- [x] Open transcript / show notes in modal or new tab
- [x] Filter: audio only, transcripts only, complete sets
- [x] Storage dashboard: total GB, breakdown by media type, disk free %

### History & insights

- [x] Batch history timeline (from Phase 1 log): date, episodes, success/fail counts
- [x] Chart: downloads per week (last 90 days)
- [x] “Last sync” indicator vs GRC latest episode
- [x] Export CSV of library inventory

### Quality

- [ ] E2E smoke test (Playwright): load dashboard, mock WebSocket, assert UI renders
- [x] Accessibility pass: keyboard nav, ARIA on progress bars
- [x] PWA manifest — “Add to Home Screen” on iPad for homelab status

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