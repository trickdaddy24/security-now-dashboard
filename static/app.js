const state = { snapshot: null };

const connStatus = document.getElementById("connStatus");
const jobList = document.getElementById("jobList");
const throughputEl = document.getElementById("throughput");
const dlDir = document.getElementById("dlDir");
const startBtn = document.getElementById("startBtn");
const form = document.getElementById("downloadForm");
const versionBadge = document.getElementById("versionBadge");
const footerVersion = document.getElementById("footerVersion");

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

function setVersion(v) {
  const label = `v${v}`;
  if (versionBadge) versionBadge.textContent = label;
  if (footerVersion) footerVersion.textContent = label;
  document.title = `Security Now ${label} — Live Download Console`;
}

async function loadConfig() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    if (cfg.version) setVersion(cfg.version);
    const parallel = form.querySelector('input[name="parallel"]');
    if (parallel && cfg.parallel) parallel.value = cfg.parallel;
    const fmt = form.querySelector('select[name="filename_format"]');
    if (fmt && cfg.filename_format) fmt.value = cfg.filename_format;
    const disk = document.getElementById("diskLine");
    if (disk) disk.textContent = `Disk free: ${fmtBytes(cfg.disk_free_bytes)}`;
  } catch { /* ignore */ }
}

function renderCatalog(data) {
  const el = document.getElementById("catalog");
  if (!data.episodes?.length) {
    el.innerHTML = "<h3>Archive feed</h3><p class='muted'>Could not load catalog.</p>";
    return;
  }
  const rows = data.episodes.slice(0, 8).map((e) => `
    <div class="catalog-item">
      <strong>#${e.number}</strong> · ${e.title || "Untitled"}
      <span class="muted"> — ${e.date}${e.duration ? ` · ${e.duration}` : ""}</span>
    </div>
  `).join("");
  el.innerHTML = `
    <h3>Archive feed</h3>
    <p class="muted">Latest: <strong>#${data.latest}</strong>${data.local_next ? ` · local next: #${data.local_next}` : ""}</p>
    ${rows}
  `;
}

function renderStats(snapshot) {
  const c = snapshot.counts || {};
  document.querySelectorAll("[data-k]").forEach((node) => {
    const k = node.dataset.k;
    node.textContent = c[k] ?? 0;
  });
  dlDir.textContent = snapshot.download_dir || "—";
  const disk = document.getElementById("diskLine");
  if (disk && snapshot.disk_free_bytes != null) {
    disk.textContent = `Disk free: ${fmtBytes(snapshot.disk_free_bytes)}`;
  }

  const activeJobs = (snapshot.jobs || []).filter((j) => j.status === "running");
  const totalSpeed = activeJobs.reduce((sum, j) => sum + (j.speed_bps || 0), 0);

  if (activeJobs.length === 1) {
    throughputEl.textContent = activeJobs[0].speed_human;
  } else if (activeJobs.length > 1) {
    throughputEl.textContent = `${fmtBytes(totalSpeed)}/s (${activeJobs.length} streams)`;
  } else {
    throughputEl.textContent = "0 B/s";
  }

  startBtn.disabled = !!snapshot.running;
}

function renderJobs(snapshot) {
  const jobs = snapshot.jobs || [];
  if (!jobs.length) {
    jobList.innerHTML = "<p class='empty'>No jobs yet. Start a batch to watch downloads live.</p>";
    return;
  }

  const sorted = [...jobs].sort((a, b) => {
    const order = { running: 0, queued: 1, failed: 2, completed: 3, skipped: 4, cancelled: 5 };
    return (order[a.status] ?? 9) - (order[b.status] ?? 9) || b.episode - a.episode;
  });

  jobList.innerHTML = sorted.map((j) => {
    const pct = j.percent ?? (j.status === "completed" || j.status === "skipped" ? 100 : 0);
    const metaLeft = j.title ? `${j.title}` : j.filename;
    const metaRight = j.status === "running"
      ? `${fmtBytes(j.bytes_downloaded)} / ${j.total_bytes ? fmtBytes(j.total_bytes) : "?"} · ${j.speed_human}`
      : j.status === "failed"
        ? (j.error || "Error")
        : j.status === "skipped"
          ? "Already on disk"
          : j.status === "completed"
            ? fmtBytes(j.total_bytes || j.bytes_downloaded)
            : "Waiting…";
    return `
      <article class="job ${j.status}" data-id="${j.id}">
        <div class="job-head">
          <div>
            <span class="job-ep">EP ${j.episode}</span>
            <span class="muted"> · ${j.media_label}</span>
          </div>
          <span class="job-status ${j.status}">${j.status}</span>
        </div>
        <div class="progress"><span style="width:${pct}%"></span></div>
        <div class="job-meta">
          <span>${metaLeft}</span>
          <span>${metaRight}</span>
        </div>
      </article>
    `;
  }).join("");
}

function applySnapshot(snapshot) {
  state.snapshot = snapshot;
  renderStats(snapshot);
  renderJobs(snapshot);
}

async function loadCatalog() {
  try {
    const res = await fetch("/api/catalog");
    renderCatalog(await res.json());
  } catch {
    renderCatalog({ episodes: [] });
  }
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    connStatus.classList.add("live");
    connStatus.querySelector("span:last-child").textContent = "Live";
  };

  ws.onclose = () => {
    connStatus.classList.remove("live");
    connStatus.querySelector("span:last-child").textContent = "Reconnecting…";
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
  });
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const media = [...form.querySelectorAll('input[name="media"]:checked')].map((el) => el.value);
  if (!media.length) {
    alert("Pick at least one media type.");
    return;
  }
  const body = {
    episodes: fd.get("episodes"),
    media,
    parallel: Number(fd.get("parallel") || 2),
    skip_existing: fd.get("skip_existing") === "on",
    filename_format: fd.get("filename_format") || "raw",
  };
  startBtn.disabled = true;
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) alert(data.error || "Failed to start");
});

document.getElementById("cancelBtn").addEventListener("click", async () => {
  await fetch("/api/cancel", { method: "POST" });
});

document.getElementById("retryBtn").addEventListener("click", async () => {
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ retry_failed: true, episodes: "latest", media: [] }),
  });
  const data = await res.json();
  if (!data.ok) alert(data.error || "Nothing to retry");
});

// Library
function renderLibrary(data) {
  const summary = document.getElementById("libSummary");
  summary.innerHTML = `
    <div class="stat-row">
      <div class="chip"><strong>${data.episode_count ?? 0}</strong> episodes</div>
      <div class="chip"><strong>${fmtBytes(data.total_bytes)}</strong> on disk</div>
      <div class="chip">Local latest: <strong>#${data.latest_local ?? "—"}</strong></div>
      <div class="chip">GRC latest: <strong>#${data.latest_remote ?? "—"}</strong></div>
      <div class="chip">Missing eps: <strong>${data.missing_episode_count ?? 0}</strong></div>
      <div class="chip">Checksum fails: <strong>${(data.checksum_failures || []).length}</strong></div>
    </div>
    ${data.missing_episodes?.length ? `<p class="muted">Gap sample: ${data.missing_episodes.slice(0, 12).join(", ")}${data.missing_episode_count > 12 ? "…" : ""}</p>` : ""}
  `;

  const table = document.getElementById("libTable");
  const eps = data.episodes || [];
  if (!eps.length) {
    table.innerHTML = "<p class='empty'>No local episodes found.</p>";
    return;
  }
  table.innerHTML = eps.map((e) => `
    <div class="lib-row">
      <span class="ep">#${e.number}</span>
      <span>${e.title || "Untitled"}<br><span class="muted">${(e.formats || []).join(" · ")}</span></span>
      <span class="formats">${fmtBytes(e.total_bytes)}</span>
    </div>
  `).join("");
}

async function loadLibrary() {
  try {
    const data = await (await fetch("/api/library")).json();
    renderLibrary(data);
    loadRssStatus();
  } catch {
    document.getElementById("libSummary").innerHTML = "<p class='muted'>Library scan failed.</p>";
  }
}

async function loadRssStatus() {
  try {
    const data = await (await fetch("/api/rss/status")).json();
    const el = document.getElementById("rssStatus");
    const links = document.getElementById("feedLinks");
    if (!data.built_at) {
      el.textContent = "Not built yet — click Rebuild RSS";
      links.innerHTML = "";
      return;
    }
    const when = new Date(data.built_at * 1000).toLocaleString();
    const counts = Object.entries(data.counts || {}).map(([k, v]) => `${k}: ${v}`).join(" · ");
    el.textContent = `Last built: ${when}${counts ? ` · ${counts}` : ""}`;
    const feedMap = { audio: "audio", video: "video", text: "text", all: "all" };
    links.innerHTML = Object.entries(feedMap).map(([key, path]) =>
      `<a href="/feed/${path}.rss" target="_blank" rel="noopener">/feed/${path}.rss</a>`
    ).join("");
  } catch { /* ignore */ }
}

document.getElementById("refreshLibBtn")?.addEventListener("click", loadLibrary);

document.getElementById("rebuildRssBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("rebuildRssBtn");
  btn.disabled = true;
  const res = await fetch("/api/rss/rebuild", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const data = await res.json();
  btn.disabled = false;
  if (!data.ok) alert("RSS rebuild failed");
  loadRssStatus();
});

document.getElementById("fillTranscriptsBtn")?.addEventListener("click", async () => {
  const res = await fetch("/api/library/fill-transcripts", { method: "POST" });
  const data = await res.json();
  if (!data.ok) alert(data.error || "Failed");
  else if (!data.episodes?.length) alert(data.message || "No missing transcripts");
  else alert(`Queued transcripts for ${data.episodes.length} episode(s)`);
});

// Search
async function loadSearchStatus() {
  try {
    const data = await (await fetch("/api/search/status")).json();
    const el = document.getElementById("searchStatus");
    if (!data.indexed_at) {
      el.textContent = "Index: not built — click Rebuild index";
      return;
    }
    el.textContent = `Index: ${data.documents} transcript(s) · ${new Date(data.indexed_at * 1000).toLocaleString()}`;
  } catch { /* ignore */ }
}

document.getElementById("searchForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = new FormData(e.target).get("q");
  if (!q) return;
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  const box = document.getElementById("searchResults");
  if (!data.results?.length) {
    box.innerHTML = "<p class='empty'>No matches.</p>";
    return;
  }
  box.innerHTML = data.results.map((r) => `
    <article class="hit">
      <div class="hit-ep">#${r.episode} · ${r.title || "Episode"}</div>
      <div class="snippet">${r.snippet || ""}</div>
    </article>
  `).join("");
});

document.getElementById("reindexBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("reindexBtn");
  btn.disabled = true;
  await fetch("/api/search/reindex", { method: "POST" });
  btn.disabled = false;
  loadSearchStatus();
});

loadConfig();
loadCatalog();
connectWs();
fetch("/api/status").then((r) => r.json()).then(applySnapshot);