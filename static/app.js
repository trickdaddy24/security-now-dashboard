const state = {
  snapshot: null,
  catalog: null,
  library: null,
  speedHistory: {},
  dragJobId: null,
  batchWasRunning: false,
};

const $ = (id) => document.getElementById(id);
const versionBadge = $("versionBadge");
const footerVersion = $("footerVersion");

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

/** Episode files live in subfolders — encode each path segment for /media/… */
function mediaUrl(filename) {
  if (!filename) return "";
  return "/media/" + filename.split("/").map((p) => encodeURIComponent(p)).join("/");
}

function setVersion(v) {
  const label = `v${v}`;
  if (versionBadge) versionBadge.textContent = label;
  if (footerVersion) footerVersion.textContent = label;
  document.title = `Security Now ${label} — Live Download Console`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

// Theme — dark, daylight, + 5 FIFA ’26 country palettes
const THEMES = ["dark", "light", "usa", "mexico", "canada", "brazil", "argentina"];

function applyTheme(theme) {
  const t = THEMES.includes(theme) ? theme : "dark";
  document.documentElement.dataset.theme = t;
  localStorage.setItem("sn-theme", t);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--green").trim();
    if (accent) meta.setAttribute("content", accent);
  }
  const sel = $("themeSelect");
  if (sel && sel.value !== t) sel.value = t;
}

const savedTheme = localStorage.getItem("sn-theme");
applyTheme(savedTheme || "dark");
const themeSelect = $("themeSelect");
if (themeSelect) {
  themeSelect.value = document.documentElement.dataset.theme;
  themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
}

// Notifications
const notifyToggle = $("notifyToggle");
if (notifyToggle) {
  notifyToggle.checked = localStorage.getItem("sn-notify") === "1";
  notifyToggle.addEventListener("change", () => {
    localStorage.setItem("sn-notify", notifyToggle.checked ? "1" : "0");
    if (notifyToggle.checked && Notification.permission === "default") {
      Notification.requestPermission();
    }
  });
}

function maybeNotifyBatchDone(snapshot) {
  if (!notifyToggle?.checked || Notification.permission !== "granted") return;
  const c = snapshot.counts || {};
  new Notification("Security Now batch finished", {
    body: `${c.completed ?? 0} completed, ${c.failed ?? 0} failed`,
    icon: "/static/icon.svg",
  });
}

async function loadConfig() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    if (cfg.version) setVersion(cfg.version);
    const parallel = document.querySelector('input[name="parallel"]');
    if (parallel && cfg.parallel) parallel.value = cfg.parallel;
    const fmt = document.querySelector('select[name="filename_format"]');
    if (fmt && cfg.filename_format) fmt.value = cfg.filename_format;
    const disk = $("diskLine");
    if (disk) disk.textContent = `Disk free: ${fmtBytes(cfg.disk_free_bytes)}`;
  } catch { /* ignore */ }
}

function renderEpisodeGrid(data) {
  state.catalog = data;
  const meta = $("catalogMeta");
  const grid = $("episodeGrid");
  const sync = $("syncLine");
  if (!data.episodes?.length) {
    meta.textContent = "Could not load catalog.";
    grid.innerHTML = "";
    return;
  }
  meta.textContent = `Latest #${data.latest}${data.local_next ? ` · local next #${data.local_next}` : ""} — click to queue`;
  if (sync) {
    const ok = data.local_next && data.latest && data.local_next > data.latest;
    sync.textContent = ok
      ? `GRC sync: up to date (#${data.latest})`
      : `GRC sync: remote #${data.latest}${data.local_next ? ` · you have through #${data.local_next - 1}` : ""}`;
  }
  grid.innerHTML = data.episodes.slice(0, 30).map((e) => `
    <button type="button" class="ep-card" data-ep="${e.number}" role="listitem" title="${esc(e.title)}">
      <span class="ep-num">#${e.number}</span>
      <span class="ep-title">${esc(e.title || "Untitled")}</span>
      <span class="ep-date muted">${esc(e.date || "")}</span>
    </button>
  `).join("");
  grid.querySelectorAll(".ep-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ep = btn.dataset.ep;
      const input = $("episodesInput");
      if (input) input.value = ep;
      input?.focus();
    });
  });
}

async function loadCatalog() {
  try {
    renderEpisodeGrid(await (await fetch("/api/catalog")).json());
  } catch {
    renderEpisodeGrid({ episodes: [] });
  }
}

function recordSpeed(job) {
  if (job.status !== "running") return;
  const hist = state.speedHistory[job.id] || (state.speedHistory[job.id] = []);
  hist.push(job.speed_bps || 0);
  if (hist.length > 60) hist.shift();
}

function drawSparkline(canvas, samples) {
  if (!canvas || !samples.length) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const max = Math.max(...samples, 1);
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--green").trim() || "#3dff9a";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  samples.forEach((v, i) => {
    const x = (i / Math.max(samples.length - 1, 1)) * (w - 4) + 2;
    const y = h - 4 - (v / max) * (h - 8);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function renderStats(snapshot) {
  const c = snapshot.counts || {};
  document.querySelectorAll("[data-k]").forEach((node) => {
    node.textContent = c[node.dataset.k] ?? 0;
  });
  $("dlDir").textContent = snapshot.download_dir || "—";
  const disk = $("diskLine");
  if (disk && snapshot.disk_free_bytes != null) {
    disk.textContent = `Disk free: ${fmtBytes(snapshot.disk_free_bytes)}`;
  }
  const active = (snapshot.jobs || []).filter((j) => j.status === "running");
  const totalSpeed = active.reduce((s, j) => s + (j.speed_bps || 0), 0);
  const tp = $("throughput");
  if (active.length === 1) tp.textContent = active[0].speed_human;
  else if (active.length > 1) tp.textContent = `${fmtBytes(totalSpeed)}/s (${active.length} streams)`;
  else tp.textContent = "0 B/s";
  $("startBtn").disabled = !!snapshot.running;
}

function renderJobs(snapshot) {
  const jobs = snapshot.jobs || [];
  const list = $("jobList");
  if (!jobs.length) {
    list.innerHTML = '<p class="empty">No jobs yet. Start a batch or click an episode above.</p>';
    return;
  }
  const order = { running: 0, queued: 1, failed: 2, completed: 3, skipped: 4, cancelled: 5 };
  const sorted = [...jobs].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9) || b.episode - a.episode);

  list.innerHTML = sorted.map((j) => {
    recordSpeed(j);
    const pct = j.percent ?? (["completed", "skipped"].includes(j.status) ? 100 : 0);
    const draggable = j.status === "queued" ? 'draggable="true"' : "";
    const cancelBtn = ["queued", "running"].includes(j.status)
      ? `<button type="button" class="btn tiny cancel-job" data-id="${j.id}" aria-label="Cancel job">✕</button>`
      : "";
    const metaRight = j.status === "running"
      ? `${fmtBytes(j.bytes_downloaded)} / ${j.total_bytes ? fmtBytes(j.total_bytes) : "?"} · ${j.speed_human} · ETA ${j.eta_human || "—"}`
      : j.status === "failed" ? (esc(j.error) || "Error")
      : j.status === "skipped" ? "On disk"
      : j.status === "completed" ? fmtBytes(j.total_bytes || j.bytes_downloaded)
      : "Waiting…";
    return `
      <article class="job ${j.status}" data-id="${j.id}" role="listitem" ${draggable}>
        <div class="job-head">
          <div>
            <span class="job-ep">EP ${j.episode}</span>
            <span class="muted"> · ${esc(j.media_label)}</span>
          </div>
          <div class="job-head-right">
            <span class="job-status ${j.status}">${j.status}</span>
            ${cancelBtn}
          </div>
        </div>
        <div class="progress" role="progressbar" aria-valuenow="${Math.round(pct)}" aria-valuemin="0" aria-valuemax="100" aria-label="Download progress">
          <span style="width:${pct}%"></span>
        </div>
        <canvas class="sparkline" data-spark="${j.id}" width="280" height="28" aria-hidden="true"></canvas>
        <div class="job-meta">
          <span>${esc(j.title || j.filename)}</span>
          <span>${metaRight}</span>
        </div>
      </article>`;
  }).join("");

  sorted.forEach((j) => {
    const c = list.querySelector(`canvas[data-spark="${j.id}"]`);
    if (c) drawSparkline(c, state.speedHistory[j.id] || []);
  });

  list.querySelectorAll(".cancel-job").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await fetch(`/api/jobs/${btn.dataset.id}/cancel`, { method: "POST" });
    });
  });

  list.querySelectorAll(".job[draggable]").forEach((el) => {
    el.addEventListener("dragstart", () => { state.dragJobId = el.dataset.id; el.classList.add("dragging"); });
    el.addEventListener("dragend", () => { state.dragJobId = null; el.classList.remove("dragging"); });
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("drag-over"); });
    el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
    el.addEventListener("drop", async (e) => {
      e.preventDefault();
      el.classList.remove("drag-over");
      const targetId = el.dataset.id;
      if (!state.dragJobId || state.dragJobId === targetId) return;
      const queued = sorted.filter((j) => j.status === "queued").map((j) => j.id);
      const from = queued.indexOf(state.dragJobId);
      const to = queued.indexOf(targetId);
      if (from < 0 || to < 0) return;
      queued.splice(to, 0, queued.splice(from, 1)[0]);
      await fetch("/api/jobs/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: queued }),
      });
      const st = await (await fetch("/api/status")).json();
      applySnapshot(st);
    });
  });
}

function applySnapshot(snapshot) {
  if (state.batchWasRunning && !snapshot.running) maybeNotifyBatchDone(snapshot);
  state.batchWasRunning = !!snapshot.running;
  state.snapshot = snapshot;
  renderStats(snapshot);
  renderJobs(snapshot);
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  const pill = $("connStatus");
  ws.onopen = () => {
    pill.classList.add("live");
    pill.querySelector("span:last-child").textContent = "Live";
  };
  ws.onclose = () => {
    pill.classList.remove("live");
    pill.querySelector("span:last-child").textContent = "Reconnecting…";
    setTimeout(connectWs, 1500);
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.event === "job_updated" && state.snapshot && msg.data?.job) {
      const job = msg.data.job;
      const idx = state.snapshot.jobs.findIndex((j) => j.id === job.id);
      if (idx >= 0) state.snapshot.jobs[idx] = job;
      else state.snapshot.jobs.push(job);
      applySnapshot(state.snapshot);
      return;
    }
    if (msg.event === "batch_finished" && state.snapshot) {
      applySnapshot(msg.data?.jobs ? msg.data : state.snapshot);
      maybeNotifyBatchDone(state.snapshot);
      loadCatalog();
      return;
    }
    if (msg.data?.jobs) applySnapshot(msg.data);
  };
}

// Tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === tab);
      t.setAttribute("aria-selected", t.dataset.tab === tab ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel").forEach((p) => {
      p.classList.toggle("active", p.id === `panel-${tab}`);
    });
    if (tab === "library") loadLibrary();
    if (tab === "search") loadSearchStatus();
    if (tab === "insights") loadInsights();
  });
});

$("downloadForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const media = [...e.target.querySelectorAll('input[name="media"]:checked')].map((el) => el.value);
  if (!media.length) { alert("Pick at least one media type."); return; }
  $("startBtn").disabled = true;
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      episodes: fd.get("episodes"),
      media,
      parallel: Number(fd.get("parallel") || 2),
      skip_existing: fd.get("skip_existing") === "on",
      filename_format: fd.get("filename_format") || "raw",
    }),
  });
  const data = await res.json();
  if (!data.ok) alert(data.error || "Failed to start");
});

$("cancelBtn")?.addEventListener("click", () => fetch("/api/cancel", { method: "POST" }));
$("retryBtn")?.addEventListener("click", async () => {
  const data = await (await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ retry_failed: true, episodes: "latest", media: [] }),
  })).json();
  if (!data.ok) alert(data.error || "Nothing to retry");
});

// Library
function filterEpisodes(eps, filter) {
  if (filter === "audio") return eps.filter((e) => (e.formats || []).some((f) => f.startsWith("audio")));
  if (filter === "transcript") return eps.filter((e) => (e.formats || []).includes("transcript_txt"));
  if (filter === "complete") {
    return eps.filter((e) => {
      const f = e.formats || [];
      return f.some((x) => x.startsWith("audio")) && f.includes("transcript_txt") && f.includes("show_notes");
    });
  }
  return eps;
}

function sortEpisodes(eps, sort) {
  const copy = [...eps];
  if (sort === "number-asc") copy.sort((a, b) => a.number - b.number);
  else if (sort === "number-desc") copy.sort((a, b) => b.number - a.number);
  else if (sort === "size-desc") copy.sort((a, b) => (b.total_bytes || 0) - (a.total_bytes || 0));
  else if (sort === "title-asc") copy.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
  return copy;
}

function audioFile(ep) {
  const files = ep.files || {};
  for (const key of ["audio_hq", "audio_twit", "audio_lq"]) {
    if (files[key]?.filename) return files[key].filename;
  }
  return null;
}

function openModal(title, bodyHtml) {
  $("modalTitle").textContent = title;
  $("modalBody").innerHTML = bodyHtml;
  $("modal").classList.remove("hidden");
}

function closeModal() {
  $("modal").classList.add("hidden");
  $("modalBody").innerHTML = "";
}

document.querySelectorAll("[data-close-modal]").forEach((el) => {
  el.addEventListener("click", closeModal);
});

function renderLibraryTable() {
  if (!state.library) return;
  const filter = $("libFilter")?.value || "all";
  const sort = $("libSort")?.value || "number-desc";
  let eps = sortEpisodes(filterEpisodes(state.library.episodes || [], filter), sort);
  const table = $("libTable");
  if (!eps.length) {
    table.innerHTML = "<p class='empty'>No episodes match filter.</p>";
    return;
  }
  table.innerHTML = eps.map((e) => {
    const files = e.files || {};
    const audio = audioFile(e);
    const txt = files.transcript_txt?.filename;
    const notes = files.show_notes?.filename;
    return `
      <div class="lib-row">
        <span class="ep">#${e.number}</span>
        <span>
          ${esc(e.title || "Untitled")}<br>
          <span class="muted">${(e.formats || []).join(" · ")}</span>
          ${audio ? `<br><audio controls preload="metadata" src="${mediaUrl(audio)}" class="mini-audio"></audio>` : ""}
          <div class="lib-actions">
            ${txt ? `<button type="button" class="btn tiny open-txt" data-file="${esc(txt)}" data-ep="${e.number}">Transcript</button>` : ""}
            ${notes ? `<button type="button" class="btn tiny open-notes" data-file="${esc(notes)}" data-ep="${e.number}">Notes</button>` : ""}
          </div>
        </span>
        <span class="formats">${fmtBytes(e.total_bytes)}</span>
      </div>`;
  }).join("");

  table.querySelectorAll(".open-txt").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const res = await fetch(mediaUrl(btn.dataset.file));
      const text = await res.text();
      openModal(`#${btn.dataset.ep} Transcript`, `<pre class="modal-pre">${esc(text.slice(0, 12000))}${text.length > 12000 ? "…" : ""}</pre>`);
    });
  });
  table.querySelectorAll(".open-notes").forEach((btn) => {
    btn.addEventListener("click", () => {
      openModal(`#${btn.dataset.ep} Show notes`, `<p><a href="${mediaUrl(btn.dataset.file)}" target="_blank" rel="noopener">Open PDF in new tab</a></p><iframe src="${mediaUrl(btn.dataset.file)}" class="modal-pdf"></iframe>`);
    });
  });
}

function renderLibrary(data) {
  state.library = data;
  $("libSummary").innerHTML = `
    <div class="stat-row">
      <div class="chip"><strong>${data.episode_count ?? 0}</strong> episodes</div>
      <div class="chip"><strong>${fmtBytes(data.total_bytes)}</strong> on disk</div>
      <div class="chip">Local <strong>#${data.latest_local ?? "—"}</strong></div>
      <div class="chip">GRC <strong>#${data.latest_remote ?? "—"}</strong></div>
      <div class="chip">Free <strong>${data.disk_free_pct != null ? data.disk_free_pct + "%" : fmtBytes(data.disk_free_bytes)}</strong></div>
      <div class="chip">Gaps <strong>${data.missing_episode_count ?? 0}</strong></div>
    </div>`;
  const br = $("storageBreakdown");
  const sb = data.storage_by_media || {};
  const keys = Object.keys(sb);
  br.innerHTML = keys.length
    ? `<p class="muted">Storage: ${keys.map((k) => `${k} ${fmtBytes(sb[k])}`).join(" · ")}</p>`
    : "";
  renderLibraryTable();
}

async function loadLibrary() {
  try {
    renderLibrary(await (await fetch("/api/library")).json());
    loadRssStatus();
  } catch {
    $("libSummary").innerHTML = "<p class='muted'>Library scan failed.</p>";
  }
}

$("libFilter")?.addEventListener("change", renderLibraryTable);
$("libSort")?.addEventListener("change", renderLibraryTable);
$("refreshLibBtn")?.addEventListener("click", loadLibrary);

async function loadRssStatus() {
  try {
    const data = await (await fetch("/api/rss/status")).json();
    const el = $("rssStatus");
    const links = $("feedLinks");
    if (!data.built_at) {
      el.textContent = "Not built yet";
      links.innerHTML = "";
      return;
    }
    el.textContent = `Built ${new Date(data.built_at * 1000).toLocaleString()}`;
    links.innerHTML = ["audio", "video", "text", "all"].map((k) =>
      `<a href="/feed/${k}.rss" target="_blank" rel="noopener">/feed/${k}.rss</a>`
    ).join("");
  } catch { /* ignore */ }
}

$("rebuildRssBtn")?.addEventListener("click", async () => {
  const btn = $("rebuildRssBtn");
  btn.disabled = true;
  await fetch("/api/rss/rebuild", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  btn.disabled = false;
  loadRssStatus();
});

$("fillTranscriptsBtn")?.addEventListener("click", async () => {
  const data = await (await fetch("/api/library/fill-transcripts", { method: "POST" })).json();
  if (!data.ok) alert(data.error || "Failed");
  else if (!data.episodes?.length) alert(data.message || "None missing");
  else alert(`Queued ${data.episodes.length} transcript(s)`);
});

// Search
async function loadSearchStatus() {
  try {
    const data = await (await fetch("/api/search/status")).json();
    $("searchStatus").textContent = data.indexed_at
      ? `Index: ${data.documents} docs · ${new Date(data.indexed_at * 1000).toLocaleString()}`
      : "Index: not built";
  } catch { /* ignore */ }
}

$("searchForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = new FormData(e.target).get("q");
  if (!q) return;
  const data = await (await fetch(`/api/search?q=${encodeURIComponent(q)}`)).json();
  const box = $("searchResults");
  if (!data.results?.length) {
    box.innerHTML = "<p class='empty'>No matches.</p>";
    return;
  }
  box.innerHTML = data.results.map((r) => `
    <article class="hit">
      <div class="hit-ep">#${r.episode} · ${esc(r.title || "Episode")}</div>
      <div class="snippet">${r.snippet || ""}</div>
    </article>`).join("");
});

$("reindexBtn")?.addEventListener("click", async () => {
  $("reindexBtn").disabled = true;
  await fetch("/api/search/reindex", { method: "POST" });
  $("reindexBtn").disabled = false;
  loadSearchStatus();
});

// Insights
function drawWeeklyChart(weekly) {
  const canvas = $("weeklyChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const w = rect.width;
  const h = rect.height;
  ctx.clearRect(0, 0, w, h);
  if (!weekly.length) {
    ctx.fillStyle = "#6f8f7f";
    ctx.font = "12px monospace";
    ctx.fillText("No download history yet", 12, h / 2);
    return;
  }
  const max = Math.max(...weekly.map((x) => x.completed), 1);
  const barW = Math.max(8, (w - 40) / weekly.length - 4);
  const green = getComputedStyle(document.documentElement).getPropertyValue("--green").trim() || "#3dff9a";
  weekly.forEach((row, i) => {
    const bh = (row.completed / max) * (h - 30);
    const x = 20 + i * (barW + 4);
    const y = h - 20 - bh;
    ctx.fillStyle = green;
    ctx.fillRect(x, y, barW, bh);
    ctx.fillStyle = "#6f8f7f";
    ctx.font = "9px monospace";
    ctx.fillText(String(row.completed), x, y - 4);
  });
}

async function loadInsights() {
  try {
    const data = await (await fetch("/api/insights")).json();
    $("insightsSync").textContent = data.sync_ok
      ? `Last sync: up to date (GRC #${data.latest_remote})`
      : `Last sync: GRC #${data.latest_remote} · local next #${data.local_next ?? "?"}`;
    const w = data.watcher || {};
    const wl = $("watcherLine");
    if (wl) {
      if (!w.enabled) {
        wl.textContent = "Watcher: disabled (set SN_WATCHER_ENABLED=1)";
      } else {
        const seen = w.last_seen ? `#${w.last_seen}` : "—";
        const chk = w.last_check ? new Date(w.last_check * 1000).toLocaleString() : "never";
        wl.textContent = `Watcher: every ${w.interval_hours ?? "?"}h · last seen ${seen} · checked ${chk}`;
      }
    }
    const tl = $("batchTimeline");
    const batches = data.timeline || [];
    tl.innerHTML = batches.length
      ? batches.map((b) => `
          <div class="timeline-row">
            <span class="muted">${b.started_at ? new Date(b.started_at * 1000).toLocaleString() : "—"}</span>
            <span>${b.retry_failed ? "Retry" : `Eps ${(b.episodes || []).length || "?"}`} · <strong class="ok">${b.completed ?? 0}</strong> ok · <strong class="warn">${b.failed ?? 0}</strong> fail</span>
          </div>`).join("")
      : "<p class='muted'>No batch history yet.</p>";
    drawWeeklyChart(data.weekly || []);
  } catch {
    $("batchTimeline").innerHTML = "<p class='muted'>Failed to load insights.</p>";
  }
}

window.addEventListener("resize", () => {
  if ($("panel-insights")?.classList.contains("active")) loadInsights();
});

loadConfig();
loadCatalog();
connectWs();
fetch("/api/status").then((r) => r.json()).then((snap) => {
  state.batchWasRunning = !!snap.running;
  applySnapshot(snap);
});