const state = { snapshot: null };

const connStatus = document.getElementById("connStatus");
const jobList = document.getElementById("jobList");
const throughputEl = document.getElementById("throughput");
const dlDir = document.getElementById("dlDir");
const startBtn = document.getElementById("startBtn");
const form = document.getElementById("downloadForm");

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
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

  const activeJobs = (snapshot.jobs || []).filter((j) => j.status === "running");
  const totalSpeed = activeJobs.reduce((sum, j) => sum + (j.speed_bps || 0), 0);
  throughputEl.textContent = totalSpeed > 0 ? activeJobs[0].speed_human.replace(/[\d.]+/, (m) => {
    // show aggregate if multiple
    return (totalSpeed / (totalSpeed >= 1024 * 1024 ? 1024 * 1024 : totalSpeed >= 1024 ? 1024 : 1)).toFixed(1);
  }) : "0 B/s";

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

loadCatalog();
connectWs();
fetch("/api/status").then((r) => r.json()).then(applySnapshot);