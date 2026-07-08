# Security Now Dashboard — Roadmap

Modern Python fork of [Seth Leedy's GRC-Downloader](https://github.com/sethleedy/GRC-SECURITY-NOW-PODCAST-DOWNLOAD-SCRIPT) with a **live WebSocket dashboard** for watching downloads in real time.

---

## Shipped (v1.0.0)

- [x] GRC archive parser (`securitynow.htm` → episode list + titles)
- [x] Download engine with streaming progress, resume, parallel jobs
- [x] Media types: Audio HQ/LQ, TWiT CDN, transcripts, show notes
- [x] Episode specs: `latest`, `next`, ranges, `all`
- [x] FastAPI REST + WebSocket dashboard
- [x] Docker + `docker-compose.yml`
- [x] Smoke tests + GitHub Actions CI

---

## Phase 2 — CLI parity (High priority)

**Goal:** Match the original bash script for headless/server use without opening the browser.

- [ ] `sn-download` CLI with flags mapped from `GRC-Downloader.sh`:
  - `-ep`, `-latest`, `-all`, `-ahq`, `-alq`, `-eptxt`, `-eppdf`, `-d`, `-pd`, `-p` (pretend)
- [ ] JSON progress output mode for scripting
- [ ] `--skip-digital-cert-check` equivalent (httpx verify toggle)
- [ ] Auto-detect next local episode (`next` default when no flags)

---

## Phase 3 — RSS feeds

**Goal:** Port `-create-rss-audio`, `-create-rss-video`, `-create-rss-text` from the upstream script.

- [ ] Generate `security_now.rss` from downloaded files + GRC metadata
- [ ] Configurable `-rss-limit` text truncation
- [ ] Optional local file:// or HTTP base URL for enclosure links
- [ ] Dashboard button: "Rebuild RSS"

---

## Phase 4 — Transcript search

**Goal:** Port `-stxt` and `-dandstxt` search modes.

- [ ] Index local `.txt` transcripts
- [ ] Case-insensitive search API + dashboard search box
- [ ] Optional compressed cache directory (7z/gzip) like upstream `.tmp_search_txt`
- [ ] Highlighted snippets in results

---

## Phase 5 — Deployment hardening

**Goal:** Safe to run on homelab (Saltbox) or a VPS.

- [ ] Traefik label example for Saltbox (like Notifier)
- [ ] Optional basic auth or Authelia forward-auth notes
- [ ] Rate limiting on `/api/download`
- [ ] Disk space pre-check before batch start (upstream `chk_disk_space` parity)

---

## Phase 6 — Integrations (Nice to have)

- [ ] Webhook on batch complete (Telegram / Discord / Notifier)
- [ ] "New episode" watcher — poll GRC on a schedule, auto-queue `latest`
- [ ] Kodi-friendly filename preset (`-ff kodi` parity)
- [ ] Plex podcast library path hints

---

## Non-goals (for now)

- Re-hosting or mirroring GRC/TWiT media (downloads are for personal archival only)
- Replacing the official [GRC RSS feed](http://leoville.tv/podcasts/sn.xml)
- Multi-user accounts (unless Phase 5 auth proves necessary)

---

**Last updated:** July 2026