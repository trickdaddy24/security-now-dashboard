const state = {
  snapshot: null,
  catalog: null,
  library: null,
  speedHistory: {},
  dragJobId: null,
  batchWasRunning: false,
  selectedEpisodes: new Set(),
  periodBatch: null,
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

// Theme — Terminal + FIFA ’26 country palettes (USA, Argentina + 7 others)
const THEMES = ["dark", "usa", "argentina", "mexico", "canada", "brazil", "france", "germany", "england", "spain"];

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

  } catch { /* ignore */ }
}

function refreshCatalogMeta() {
  const data = state.catalog;
  const meta = $("catalogMeta");
  if (!meta || !data?.episodes?.length) return;
  const n = state.selectedEpisodes.size;
  const syncOk = data.local_next && data.latest && data.local_next > data.latest;
  const syncBit = syncOk
    ? `up to date through #${data.latest}`
    : `remote #${data.latest}${data.local_next ? ` · local through #${data.local_next - 1}` : ""}`;
  const selBit = n ? ` · ${n} selected` : " · click to select";
  meta.textContent = `Latest #${data.latest}${data.local_next ? ` · next #${data.local_next}` : ""} · ${syncBit}${selBit}`;
}

function updateEpisodeSelectionUi() {
  const n = state.selectedEpisodes.size;
  if (n && !state.periodBatch) {
    const nums = [...state.selectedEpisodes].map(Number).sort((a, b) => a - b);
    const input = $("episodesInput");
    if (input) {
      input.value = nums.length === 1 ? String(nums[0]) : `${nums[0]}:${nums[nums.length - 1]}`;
    }
  }
  document.querySelectorAll(".ep-card").forEach((btn) => {
    btn.classList.toggle("selected", state.selectedEpisodes.has(Number(btn.dataset.ep)));
    btn.setAttribute("aria-pressed", state.selectedEpisodes.has(Number(btn.dataset.ep)) ? "true" : "false");
  });
  refreshCatalogMeta();
}

function renderEpisodeGrid(data) {
  state.catalog = data;
  const meta = $("catalogMeta");
  const grid = $("episodeGrid");
  if (!data.episodes?.length) {
    meta.textContent = "Could not load catalog.";
    grid.innerHTML = "";
    return;
  }
  refreshCatalogMeta();
  grid.innerHTML = data.episodes.slice(0, 30).map((e) => {
    const on = state.selectedEpisodes.has(e.number);
    return `
    <button type="button" class="ep-card${on ? " selected" : ""}" data-ep="${e.number}" role="listitem"
      aria-pressed="${on ? "true" : "false"}" title="${esc(e.title)}">
      <span class="ep-check" aria-hidden="true">${on ? "✓" : ""}</span>
      <span class="ep-num">#${e.number}</span>
      <span class="ep-title">${esc(e.title || "Untitled")}</span>
      <span class="ep-date muted">${esc(e.date || "")}</span>
    </button>`;
  }).join("");
  grid.querySelectorAll(".ep-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.periodBatch = null;
      const ep = Number(btn.dataset.ep);
      if (state.selectedEpisodes.has(ep)) state.selectedEpisodes.delete(ep);
      else state.selectedEpisodes.add(ep);
      updateEpisodeSelectionUi();
    });
  });
  updateEpisodeSelectionUi();
}

function getSelectedMedia() {
  return [...document.querySelectorAll('#downloadForm input[name="media"]:checked')].map((el) => el.value);
}

function setAllMedia(checked) {
  document.querySelectorAll('#downloadForm input[name="media"]').forEach((el) => {
    el.checked = checked;
  });
  syncMediaChips();
}

function syncMediaChips() {
  document.querySelectorAll(".chip-btn[data-media]").forEach((btn) => {
    const input = document.querySelector(`#downloadForm input[name="media"][value="${btn.dataset.media}"]`);
    btn.classList.toggle("active", !!(input && input.checked));
  });
}

function buildDownloadPayload(extra = {}) {
  const form = $("downloadForm");
  const fd = new FormData(form);
  const media = getSelectedMedia();
  const payload = {
    media,
    parallel: Number(fd.get("parallel") || 2),
    skip_existing: fd.get("skip_existing") === "on",
    filename_format: fd.get("filename_format") || "raw",
    ...extra,
  };
  if (state.periodBatch) {
    payload.period = state.periodBatch.period;
    payload.period_count = state.periodBatch.count;
    payload.episodes = "latest";
  } else {
    payload.episodes = fd.get("episodes") || "latest";
  }
  return payload;
}

function renderEstimate(data) {
  const line = $("estimateLine");
  if (!line) return;
  if (!data.ok) {
    line.textContent = data.error || "Estimate failed";
    line.classList.add("warn");
    return;
  }
  line.classList.remove("warn");
  const jobs = data.job_count ?? 0;
  const eps = data.episode_count ?? data.episodes?.length ?? 0;
  const range = data.episode_range || "—";
  const size = fmtBytes(data.estimated_bytes);
  const disk = data.disk_free_bytes != null ? fmtBytes(data.disk_free_bytes) : "—";
  const space = data.message ? ` · ${data.message}` : data.ok ? " · disk OK" : "";
  const period = data.period && data.period_count
    ? `last ${data.period_count} ${data.period}(s) · `
    : "";
  line.textContent = `${period}${eps} ep (${range}) · ${jobs} jobs · ~${size} · ${disk} free${space}`;
}

async function runEstimate() {
  const media = getSelectedMedia();
  if (!media.length) {
    alert("Pick at least one media type.");
    return;
  }
  const line = $("estimateLine");
  if (line) line.textContent = "Calculating…";
  const payload = buildDownloadPayload();
  try {
    renderEstimate(await (await fetch("/api/download/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })).json());
  } catch {
    if (line) line.textContent = "Estimate failed";
  }
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
      if (job.status === "completed" || job.status === "failed") loadEventLog();
      return;
    }
    if (msg.event === "batch_finished" && state.snapshot) {
      applySnapshot(msg.data?.jobs ? msg.data : state.snapshot);
      maybeNotifyBatchDone(state.snapshot);
      loadCatalog();
      loadEventLog();
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
    if (tab === "insights") {
      loadInsights();
      loadIntegrations();
    }
  });
});

$("downloadForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!getSelectedMedia().length) { alert("Pick at least one media type."); return; }
  $("startBtn").disabled = true;
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildDownloadPayload()),
  });
  const data = await res.json();
  if (!data.ok) alert(data.error || "Failed to start");
});

document.querySelectorAll(".chip-btn[data-media]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = document.querySelector(`#downloadForm input[name="media"][value="${btn.dataset.media}"]`);
    if (!input) return;
    input.checked = !input.checked;
    syncMediaChips();
    if (state.periodBatch || $("estimateLine")?.textContent !== "Estimated download: —") runEstimate();
  });
});

$("selectAllMediaBtn")?.addEventListener("click", () => setAllMedia(true));
$("clearMediaBtn")?.addEventListener("click", () => setAllMedia(false));

document.querySelectorAll('#downloadForm input[name="media"]').forEach((el) => {
  el.addEventListener("change", syncMediaChips);
});
syncMediaChips();

$("applyPeriodBtn")?.addEventListener("click", async () => {
  const count = Number($("periodCount")?.value || 1);
  const period = $("periodUnit")?.value || "day";
  state.periodBatch = { period, count };
  state.selectedEpisodes.clear();
  updateEpisodeSelectionUi();
  const input = $("episodesInput");
  if (input) input.value = `last ${count} ${period}${count === 1 ? "" : "s"}`;
  await runEstimate();
});

$("estimateBtn")?.addEventListener("click", runEstimate);

$("selectAllEpsBtn")?.addEventListener("click", () => {
  state.periodBatch = null;
  (state.catalog?.episodes || []).slice(0, 30).forEach((e) => state.selectedEpisodes.add(e.number));
  updateEpisodeSelectionUi();
});

$("clearEpsBtn")?.addEventListener("click", () => {
  state.selectedEpisodes.clear();
  state.periodBatch = null;
  const input = $("episodesInput");
  if (input) input.value = "latest";
  updateEpisodeSelectionUi();
  const line = $("estimateLine");
  if (line) line.textContent = "Estimated download: —";
});

$("episodesInput")?.addEventListener("input", () => {
  state.periodBatch = null;
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

let _libLoadTimer = null;
let _libLoadPct = 0;

const LIB_LOAD_STEPS = [
  { at: 12, label: "Contacting GRC catalog…", hint: "Checking latest episode number." },
  { at: 35, label: "Scanning download folder…", hint: "Walking episode folders on disk." },
  { at: 62, label: "Indexing media files…", hint: "Matching audio, video, and transcripts." },
  { at: 82, label: "Building library view…", hint: "Almost ready." },
];

function showLibraryLoading(active) {
  const box = $("libLoading");
  const table = $("libTable");
  if (!box) return;
  if (active) {
    box.classList.remove("hidden");
    if (table) table.classList.add("hidden");
    _libLoadPct = 0;
    setLibraryProgress(4, LIB_LOAD_STEPS[0].label, LIB_LOAD_STEPS[0].hint);
    if (_libLoadTimer) clearInterval(_libLoadTimer);
    let step = 0;
    _libLoadTimer = setInterval(() => {
      if (_libLoadPct >= 88) return;
      _libLoadPct = Math.min(88, _libLoadPct + 2 + Math.random() * 4);
      while (step < LIB_LOAD_STEPS.length - 1 && _libLoadPct >= LIB_LOAD_STEPS[step + 1].at) step += 1;
      const s = LIB_LOAD_STEPS[step];
      setLibraryProgress(_libLoadPct, s.label, s.hint);
    }, 280);
    $("libSummary").innerHTML = '<p class="muted">Scanning archive…</p>';
    $("storageBreakdown").innerHTML = "";
  } else {
    if (_libLoadTimer) {
      clearInterval(_libLoadTimer);
      _libLoadTimer = null;
    }
    setLibraryProgress(100, "Done", "");
    setTimeout(() => {
      box.classList.add("hidden");
      if (table) table.classList.remove("hidden");
    }, 220);
  }
}

function setLibraryProgress(pct, label, hint) {
  const bar = $("libProgressBar");
  const prog = $("libProgress");
  const lbl = $("libLoadingLabel");
  const h = $("libLoadingHint");
  const n = Math.round(pct);
  if (bar) bar.style.width = `${n}%`;
  if (prog) prog.setAttribute("aria-valuenow", String(n));
  if (lbl && label) lbl.textContent = label;
  if (h) h.textContent = hint || "";
}

async function loadLibrary() {
  showLibraryLoading(true);
  try {
    renderLibrary(await (await fetch("/api/library")).json());
    loadRssStatus();
  } catch {
    $("libSummary").innerHTML = "<p class='muted'>Library scan failed.</p>";
    $("libTable").innerHTML = "<p class='empty'>Could not scan library.</p>";
  } finally {
    showLibraryLoading(false);
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
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim() || "#6f8f7f";
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
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim() || "#6f8f7f";
    ctx.font = "9px monospace";
    ctx.fillText(String(row.completed), x, y - 4);
  });
}

async function loadIntegrations() {
  const status = $("telegramStatus");
  const meta = $("telegramMeta");
  const btn = $("testTelegramBtn");
  try {
    const data = await (await fetch("/api/integrations/status")).json();
    const tg = data.telegram || {};
    if (status) {
      status.textContent = tg.enabled
        ? `Connected · chat ${tg.chat_id_masked || "—"}`
        : "Not configured — set SN_TELEGRAM_BOT_TOKEN and SN_TELEGRAM_CHAT_ID";
    }
    if (meta) {
      meta.innerHTML = tg.enabled
        ? [
            `<li>Per-download alerts: <strong>${tg.on_job_complete ? "on" : "off"}</strong></li>`,
            `<li>Heartbeat: <strong>every ${tg.heartbeat_interval_hours ?? 6}h</strong></li>`,
          ].join("")
        : "";
    }
    if (btn) btn.disabled = !tg.enabled;
  } catch {
    if (status) status.textContent = "Could not load integration status.";
    if (btn) btn.disabled = true;
  }
}

$("testTelegramBtn")?.addEventListener("click", async () => {
  const btn = $("testTelegramBtn");
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = "Sending…";
  try {
    const data = await (await fetch("/api/integrations/telegram/test", { method: "POST" })).json();
    if (data.ok) {
      $("telegramStatus").textContent = "Test sent — check your Telegram.";
    } else {
      alert(data.error || "Telegram test failed");
    }
  } catch {
    alert("Telegram test failed");
  } finally {
    btn.textContent = "Send test";
    loadIntegrations();
  }
});

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

function formatLogTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleTimeString();
}

function renderEventLog(events) {
  const box = $("eventLog");
  if (!box) return;
  if (!events?.length) {
    box.innerHTML = '<p class="empty">No log events yet.</p>';
    return;
  }
  box.innerHTML = events.map((ev) => {
    const level = (ev.level || "INFO").toLowerCase();
    const detail = [
      ev.episode != null ? `ep ${ev.episode}` : "",
      ev.media || "",
      ev.job_filename || "",
      ev.status_code != null ? `HTTP ${ev.status_code}` : "",
    ].filter(Boolean).join(" · ");
    const extra = ev.exception ? `<div class="log-exc">${esc(ev.exception)}</div>` : "";
    return `
      <div class="log-row ${level}">
        <span class="log-ts">${esc(formatLogTime(ev.ts))}</span>
        <span class="log-level">${esc(ev.level || "INFO")}</span>
        <span class="log-msg">${esc(ev.message || "")}${detail ? ` <span class="muted">· ${esc(detail)}</span>` : ""}</span>
        ${extra}
      </div>`;
  }).join("");
}

async function loadEventLog() {
  const meta = $("eventLogMeta");
  try {
    const data = await (await fetch("/api/logs?limit=60")).json();
    if (meta) {
      const parts = [`${data.count ?? 0} events`];
      if (data.log_file) parts.push(data.log_file);
      meta.textContent = parts.join(" · ");
    }
    renderEventLog(data.events || []);
  } catch {
    if (meta) meta.textContent = "Log unavailable";
    renderEventLog([]);
  }
}

$("refreshLogsBtn")?.addEventListener("click", () => loadEventLog());
setInterval(loadEventLog, 15000);

loadConfig();
loadCatalog();
connectWs();
fetch("/api/status").then((r) => r.json()).then((snap) => {
  state.batchWasRunning = !!snap.running;
  applySnapshot(snap);
});
loadEventLog();