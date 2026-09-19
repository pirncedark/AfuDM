/* AfuDM arayuz mantigi. Python tarafina pywebview koprusuyle konusur. */

const $ = (id) => document.getElementById(id);
const POLL_MS = 700;
const TRACE_POINTS = 180;

const state = {
  filter: "all",
  motorTimer: null,
  seedTimer: null,
  torTimer: null,
  search: "",
  selected: null,
  activeDTab: "overview",
  items: [],
  settings: {},
  trace: new Array(TRACE_POINTS).fill(0),
  sessionBytes: 0,
  lastDone: new Map(),
  ready: false,
};

/* ---------- bicimleyiciler ---------- */
function size(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1024) return n + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) { value /= 1024; i++; }
  return value.toFixed(value < 10 ? 1 : 0) + " " + units[i];
}
function speed(bytes) {
  return bytes > 0 ? size(bytes) + "/s" : "—";
}
function clock(seconds) {
  const s = Number(seconds) || 0;
  if (s <= 0) return "—";
  if (s < 60) return s + " sn";
  if (s < 3600) return Math.floor(s / 60) + " dk " + (s % 60) + " sn";
  const h = Math.floor(s / 3600);
  return h + " sa " + Math.floor((s % 3600) / 60) + " dk";
}
/* Durum etiketi sozlukten gelir (ui/i18n.js); bilinmeyen durum oldugu gibi yazilir. */
function stateLabel(status) {
  const label = t("state." + status);
  return label === "state." + status ? status : label;
}

function toast(message, bad = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = "toast show" + (bad ? " bad" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.className = "toast"; }, 3400);
}

/* ---------- kopru ---------- */
async function call(method, ...args) {
  if (!window.pywebview || !window.pywebview.api) throw new Error(t("err.bridge"));
  const out = await window.pywebview.api[method](...args);
  if (out && out.ok === false) throw new Error(out.error || t("err.failed"));
  return out;
}

/* ---------- bant izi cizimi ---------- */
const canvas = $("trace");
const ctx = canvas.getContext("2d");
function drawTrace() {
  const ratio = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w * ratio || canvas.height !== h * ratio) {
    canvas.width = w * ratio; canvas.height = h * ratio;
  }
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);

  // Tepeye %25 boşluk: sabit hızda çizgi tavana yapışıp blok gibi görünmesin
  const peak = Math.max(...state.trace, 1024 * 512) * 1.25;
  const step = w / (TRACE_POINTS - 1);
  const y = (v) => h - 6 - (v / peak) * (h - 16);

  // zemin izgarasi: iki sessiz cizgi
  ctx.strokeStyle = "#1f2733";
  ctx.lineWidth = 1;
  [0.34, 0.67].forEach((f) => {
    ctx.beginPath();
    ctx.moveTo(0, Math.round(h * f) + 0.5);
    ctx.lineTo(w, Math.round(h * f) + 0.5);
    ctx.stroke();
  });

  ctx.beginPath();
  ctx.moveTo(0, h);
  state.trace.forEach((v, i) => ctx.lineTo(i * step, y(v)));
  ctx.lineTo(w, h);
  ctx.closePath();
  const fill = ctx.createLinearGradient(0, 0, 0, h);
  fill.addColorStop(0, "#5b9dff3d");
  fill.addColorStop(1, "#5b9dff00");
  ctx.fillStyle = fill;
  ctx.fill();

  ctx.beginPath();
  state.trace.forEach((v, i) => (i ? ctx.lineTo(i * step, y(v)) : ctx.moveTo(0, y(v))));
  ctx.strokeStyle = "#5b9dff";
  ctx.lineWidth = 1.5;
  ctx.stroke();
}
window.addEventListener("resize", drawTrace);

/* ---------- liste ---------- */
function rowClass(item) {
  if (item.status === "active" && item.kind === "torrent" && item.seeder) return "seeding";
  return item.status;
}
function segbar(item) {
  const cells = 24;
  const filled = Math.floor((item.progress / 100) * cells);
  const partial = item.progress > 0 && filled < cells;
  let html = '<div class="segbar">';
  for (let i = 0; i < cells; i++) {
    const cls = i < filled ? "f" : (partial && i === filled ? "h" : "");
    html += "<i" + (cls ? ' class="' + cls + '"' : "") + "></i>";
  }
  return html + "</div>";
}
function visible() {
  const q = state.search.toLowerCase();
  return state.items.filter((item) => {
    if (item.status === "removed") return false;
    const f = state.filter;
    if (f === "active" && !(item.status === "active" || item.status === "waiting")) return false;
    if (f === "paused" && item.status !== "paused" && item.status !== "scheduled") return false;
    if (f === "video" && item.kind !== "video") return false;
    if (f === "torrent" && item.kind !== "torrent") return false;
    if (f === "complete" && item.status !== "complete") return false;
    if (f === "error" && item.status !== "error") return false;
    if (q && !(item.title || "").toLowerCase().includes(q)) return false;
    return true;
  });
}
function renderList() {
  const rows = visible();
  const list = $("list");
  if (!rows.length) {
    list.innerHTML =
      '<div class="empty"><p>' + escapeHtml(t("empty.title")) + "</p>" +
      escapeHtml(t("empty.hint")) + "</div>";
    return;
  }
  list.innerHTML = rows.map((item) => {
    const seeding = item.kind === "torrent" && item.status === "active";
    let stateText = item.seeder ? t("state.seeding") : stateLabel(item.status);
    if (item.status === "scheduled" && item.start_after) {
      const when = new Date(item.start_after * 1000);
      stateText += " " + String(when.getHours()).padStart(2, "0") + ":" +
        String(when.getMinutes()).padStart(2, "0");
    }
    const kill = '<button data-act="remove" data-gid="' + item.gid + '">' + t("row.remove") + "</button>";
    let right;
    if (item.status === "complete") {
      right = '<button data-act="open" data-gid="' + item.gid + '">' + t("row.folder") + "</button>"
        + '<button data-act="remove" data-gid="' + item.gid + '">' + t("row.delete") + "</button>";
    } else if (item.status === "error") {
      // Hataya dusen indirme 'unpause' edilemez; kaydi bastan baslatmak gerekir
      right = '<button data-act="retry" data-id="' + (item.id || "") + '">' + t("row.retry") + "</button>" + kill;
    } else if (item.status === "paused") {
      right = '<button data-act="resume" data-gid="' + item.gid + '">' + t("row.resume") + "</button>" + kill;
    } else if (item.status === "scheduled") {
      right = kill;  // daha baslamadi: duraklatilacak bir sey yok
    } else {
      right = '<button data-act="pause" data-gid="' + item.gid + '">' + t("row.pause") + "</button>" + kill;
    }
    // Torrentte dosya secimi / agaci dugmesi
    if (item.kind === "torrent") {
      right = '<button data-act="files" data-gid="' + item.gid + '">' + t("tor.files") + "</button>" + right;
    }
    // Torrentte seed az olabilir: tracker listesini tazeleyen pencere (seedVeil)
    if (item.kind === "torrent" && item.status !== "complete" && item.status !== "error") {
      right = '<button data-act="seed" data-gid="' + item.gid + '">' + t("row.seed") + "</button>" + right;
    }
    return (
      '<div class="row ' + rowClass(item) + (state.selected === item.gid ? " sel" : "") +
        '" data-gid="' + item.gid + '">' +
        '<div class="row-name">' +
          '<div class="row-title"><span class="kind ' + item.kind + '">' + item.kind + "</span>" +
            escapeHtml(item.title || item.gid) + "</div>" +
          segbar(item) +
        "</div>" +
        '<div class="num"><span class="big">' + item.progress.toFixed(1) + "%</span>" +
          '<div class="size-line">' + size(item.completedLength) + " / " +
            (item.totalLength ? size(item.totalLength) : "?") + "</div></div>" +
        '<div class="num big">' + speed(item.downloadSpeed) +
          (seeding ? '<div class="size-line">' + item.numSeeders + " " + t("row.seed") + "</div>" :
            '<div class="size-line">' + (item.connections ? item.connections + " " + t("row.conn") : "&nbsp;") + "</div>") +
        "</div>" +
        '<div class="num">' + clock(item.eta) + "</div>" +
        '<div class="state ' + rowClass(item) + '">' + stateText +
          '<div class="acts">' + right + "</div></div>" +
      "</div>"
    );
  }).join("");
}
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderCounts() {
  const counts = {
    all: 0, active: 0, paused: 0, video: 0, torrent: 0, complete: 0, error: 0,
  };
  state.items.forEach((item) => {
    if (item.status === "removed") return;
    counts.all++;
    if (item.status === "active" || item.status === "waiting") counts.active++;
    if (item.status === "paused" || item.status === "scheduled") counts.paused++;
    if (item.kind === "video") counts.video++;
    if (item.kind === "torrent") counts.torrent++;
    if (item.status === "complete") counts.complete++;
    if (item.status === "error") counts.error++;
  });
  Object.entries(counts).forEach(([key, value]) => {
    const el = document.querySelector('[data-c="' + key + '"]');
    if (el) el.textContent = value;
  });
}

/* ---------- detay cekmecesi ---------- */
async function switchDetailTab(tabName) {
  state.activeDTab = tabName;
  document.querySelectorAll("#detailTabs .dtab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.dtab === tabName);
  });
  const panels = {
    overview: $("dPanelOverview"),
    files: $("dPanelFiles"),
    trackers: $("dPanelTrackers"),
    rules: $("dPanelRules"),
    automation: $("dPanelAutomation"),
    logs: $("dPanelLogs"),
  };
  Object.entries(panels).forEach(([k, panel]) => {
    if (panel) panel.classList.toggle("active", k === tabName);
  });
  if (state.selected) {
    await renderDetailTabContent(state.selected, tabName);
  }
}

async function renderDetailTabContent(gid, tabName) {
  const item = state.items.find((i) => i.gid === gid);
  if (!item) return;

  if (tabName === "files") {
    const fContent = $("dFilesContent");
    if (!fContent) return;
    if (item.kind === "torrent") {
      fContent.innerHTML = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">' +
        '<span class="hint">' + escapeHtml(item.title || item.gid) + '</span>' +
        '<button class="btn primary" id="dOpenTorVeil" style="margin-left:auto;">' + t("tor.btnFiles") + '</button>' +
        '</div><div id="dFilesSummary"></div>';
      const btn = $("dOpenTorVeil");
      if (btn) btn.onclick = () => torrentVeilAc(gid);
      try {
        const res = await call("torrent_dosyalari", gid);
        const sum = $("dFilesSummary");
        if (sum) {
          if (res.hazir_degil) {
            sum.innerHTML = '<div class="hint">' + escapeHtml(res.neden || t("tor.notReady")) + '</div>';
          } else {
            const dList = res.dosyalar || [];
            const seciliSayisi = dList.filter((d) => d.secili).length;
            sum.innerHTML = '<div class="kv">' +
              '<div>' + t("tor.count", {
                secili: seciliSayisi,
                toplam: dList.length,
                seciliBoyut: size(dList.reduce((acc, d) => acc + (d.secili ? d.boyut : 0), 0)),
                toplamBoyut: size(dList.reduce((acc, d) => acc + d.boyut, 0))
              }) + '</div></div>' +
              '<div style="max-height:140px;overflow:auto;font-size:11.5px;font-family:var(--mono);color:var(--muted);">' +
              dList.slice(0, 30).map((d) => '<div style="padding:2px 0;display:flex;justify-content:space-between;"><span>' +
                (d.secili ? '✓ ' : '✗ ') + escapeHtml(d.ad) + '</span><span>' + size(d.boyut) + '</span></div>').join('') +
              (dList.length > 30 ? '<div class="hint">+' + (dList.length - 30) + '...</div>' : '') +
              '</div>';
          }
        }
      } catch (_) {}
    } else {
      fContent.innerHTML = '<div class="kv"><div>' + t("kv.file") + '<b>' + escapeHtml(item.filename || "—") + '</b></div>' +
        '<div>' + t("kv.folder") + '<b>' + escapeHtml(item.dir || "—") + '</b></div></div>';
    }
  } else if (tabName === "trackers") {
    const tContent = $("dTrackersContent");
    const wrap = $("dPeersWrap");
    if (item.kind !== "torrent") {
      if (tContent) tContent.innerHTML = '<div class="hint">' + t("tor.empty") + '</div>';
      if (wrap) wrap.innerHTML = "";
      return;
    }
    if (tContent) {
      try {
        const met = await call("torrent_metrikleri", gid);
        if (met.ok && !met.hazir_degil) {
          const m = met.metrikler || {};
          tContent.innerHTML = '<div class="tor-metrik-bar" style="margin-bottom:10px;">' +
            '<div class="tor-metrik-kutu"><span class="tor-metrik-lbl">' + t("tor.seed") + '</span><b>' + (m.num_seeders || 0) + '</b></div>' +
            '<div class="tor-metrik-kutu"><span class="tor-metrik-lbl">' + t("tor.peers") + '</span><b>' + (m.connections || 0) + '</b></div>' +
            '<div class="tor-metrik-kutu"><span class="tor-metrik-lbl">' + t("tor.ratio") + '</span><b>' + (m.ratio || 0) + '</b></div>' +
            '<div class="tor-metrik-kutu"><span class="tor-metrik-lbl">' + t("tor.trackers") + '</span><b>' + (m.tracker_sayisi || 0) + ' (' + (m.canli_tracker || 0) + ' ' + t("eng.installed") + ')</b></div>' +
            '</div>';
        } else {
          tContent.innerHTML = '<div class="hint">' + (met.neden || t("tor.metaNotReady")) + '</div>';
        }
      } catch (_) {
        tContent.innerHTML = "";
      }
    }
    if (wrap) {
      let peers = [];
      try { peers = (await call("peers", item.gid)).peers || []; } catch (_) { peers = []; }
      if (!peers.length) {
        wrap.innerHTML = '<div class="hint">' + t("tor.noPeers") + '</div>';
      } else {
        peers.sort((a, b) => b.downloadSpeed - a.downloadSpeed);
        wrap.innerHTML =
          '<table class="peers"><thead><tr><th>' + t("peers.addr") + "</th><th>" + t("peers.type") +
          "</th><th>" + t("peers.down") + "</th><th>" + t("peers.up") + "</th><th>" +
          t("peers.client") + "</th></tr></thead><tbody>" +
          peers.slice(0, 40).map((p) =>
            "<tr><td>" + escapeHtml(p.ip) + ":" + p.port + "</td>" +
            '<td class="' + (p.seeder ? "s" : "") + '">' + (p.seeder ? "seed" : "peer") + "</td>" +
            "<td>" + speed(p.downloadSpeed) + "</td><td>" + speed(p.uploadSpeed) + "</td>" +
            "<td>" + escapeHtml(p.client || "") + "</td></tr>"
          ).join("") + "</tbody></table>";
      }
    }
  } else if (tabName === "rules") {
    const rContent = $("dRulesContent");
    if (rContent) {
      try {
        const out = await call("download_rules", gid), trace = out.trace || {};
        const rows = Object.entries(trace).map(([key, info]) => '<div class="kv"><div>' + escapeHtml(key) + '<b>' + escapeHtml(t("rules.source", {name: info.source_name || "?"})) + '</b></div></div>');
        rContent.innerHTML = rows.length ? rows.join("") : '<div class="hint">' + escapeHtml(t("dtab.rulesEmpty")) + '</div>';
      } catch (_) { rContent.textContent = t("dtab.rulesEmpty"); }
    }
  } else if (tabName === "automation") {
    const aContent = $("dAutomationContent");
    if (aContent) aContent.textContent = t("dtab.automationEmpty");
  } else if (tabName === "logs") {
    const lContent = $("dLogsContent");
    if (lContent) {
      try {
        const res = await call("loglar", gid);
        const evts = (res && res.events) || [];
        if (!evts.length && !item.errorMessage) {
          lContent.innerHTML = '<div class="hint">' + t("dtab.noLogs") + '</div>';
        } else {
          let lines = [];
          if (item.errorMessage) {
            lines.push('<div class="log-row"><span class="log-level err">[ERROR]</span>' + escapeHtml(item.errorMessage) + '</div>');
          }
          evts.slice(0, 25).forEach((ev) => {
            const d = ev.at ? new Date(ev.at * 1000).toLocaleTimeString() : "";
            const lvl = (ev.level || "info").toLowerCase();
            lines.push('<div class="log-row"><span class="log-time">' + d + '</span><span class="log-level ' + lvl + '">[' + lvl.toUpperCase() + ']</span>' + escapeHtml(ev.message || "") + '</div>');
          });
          lContent.innerHTML = lines.join("");
        }
      } catch (_) {
        lContent.innerHTML = '<div class="hint">' + t("dtab.noLogs") + '</div>';
      }
    }
  }
}

async function renderDrawer() {
  const drawer = $("drawer");
  const dTorFiles = $("dTorFiles");
  if (!state.selected) {
    drawer.className = "drawer";
    if (dTorFiles) dTorFiles.style.display = "none";
    return;
  }
  const item = state.items.find((i) => i.gid === state.selected);
  if (!item) {
    drawer.className = "drawer";
    if (dTorFiles) dTorFiles.style.display = "none";
    return;
  }
  drawer.className = "drawer open";
  $("dTitle").textContent = item.title || item.gid;
  $("dGid").textContent = item.gid;
  if (dTorFiles) {
    dTorFiles.style.display = item.kind === "torrent" ? "inline-block" : "none";
    dTorFiles.onclick = () => torrentVeilAc(item.gid);
  }

  // Tab butonlarini secili taba gore isaretle
  const activeTab = state.activeDTab || "overview";
  document.querySelectorAll("#detailTabs .dtab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.dtab === activeTab);
    btn.onclick = () => switchDetailTab(btn.dataset.dtab);
  });
  const panels = {
    overview: $("dPanelOverview"),
    files: $("dPanelFiles"),
    trackers: $("dPanelTrackers"),
    rules: $("dPanelRules"),
    automation: $("dPanelAutomation"),
    logs: $("dPanelLogs"),
  };
  Object.entries(panels).forEach(([k, panel]) => {
    if (panel) panel.classList.toggle("active", k === activeTab);
  });

  // Overview tabinin icerigini (dKv) doldur
  const cells = [
    [t("kv.status"), item.seeder ? t("state.seeding") : stateLabel(item.status)],
    [t("kv.size"), (item.totalLength ? size(item.totalLength) : t("kv.unknown"))],
    [t("kv.downloaded"), size(item.completedLength)],
    [t("kv.speed"), speed(item.downloadSpeed)],
    [t("kv.eta"), clock(item.eta)],
    [t("kv.conn"), String(item.connections || 0)],
  ];
  if (item.kind === "torrent") {
    cells.push([t("kv.seed"), String(item.numSeeders || 0)]);
    cells.push([t("kv.sent"), size(item.uploadLength || 0)]);
    cells.push([t("kv.upspeed"), speed(item.uploadSpeed || 0)]);
    cells.push([t("kv.ratio"), String(item.ratio || 0)]);
    if (item.infoHash) cells.push([t("kv.infohash"), item.infoHash]);
  }
  cells.push([t("kv.folder"), item.dir || "—"]);
  if (item.filename) cells.push([t("kv.file"), item.filename]);
  if (item.errorMessage) cells.push([t("kv.error"), item.errorMessage]);
  $("dKv").innerHTML = cells
    .map(([k, v]) => "<div>" + k + "<b>" + escapeHtml(v) + "</b></div>")
    .join("");

  // Aktif olan ozel tabin icerigini guncelle
  await renderDetailTabContent(item.gid, activeTab);
}

/* ---------- veri dongusu ---------- */
async function tick() {
  try {
    const snap = await call("snapshot");
    state.items = snap.items || [];
    state.settings = snap.settings || {};
    const stat = snap.stat || {};

    state.items.forEach((item) => {
      const previous = state.lastDone.get(item.gid) || 0;
      if (item.completedLength > previous) state.sessionBytes += item.completedLength - previous;
      state.lastDone.set(item.gid, item.completedLength);
    });

    state.trace.push(stat.downloadSpeed || 0);
    state.trace.shift();
    const value = (stat.downloadSpeed || 0) / 1048576;
    $("speed").textContent = value >= 10 ? value.toFixed(0) : value.toFixed(1);
    $("mActive").textContent = stat.numActive || 0;
    $("mWait").textContent = stat.numWaiting || 0;
    $("mUp").textContent = speed(stat.uploadSpeed || 0);
    $("mTotal").textContent = size(state.sessionBytes);
    if (snap.lang && snap.lang !== currentLang()) {
      // Dil degistiyse butun sabit metinleri yeniden yaz (ayarlardan aninda doner)
      setLang(snap.lang);
      applyStatic();
    }
    $("engineDot").className = "dot" + (snap.engine_ok ? " ok" : "");
    $("engineText").textContent = snap.engine_ok ? t("engine.running") : t("engine.stopped");
    $("dirHint").textContent = snap.download_dir || "";
    $("dirHint").title = snap.download_dir || "";

    drawTrace();
    renderCounts();
    renderList();
    await renderDrawer();
    await bekleyenYokla();
  } catch (err) {
    $("engineDot").className = "dot";
    $("engineText").textContent = t("engine.offline");
  }
  setTimeout(tick, POLL_MS);
}

/* ---------- eylemler ---------- */
$("list").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-act]");
  const row = event.target.closest(".row");
  if (button) {
    event.stopPropagation();
    const { act, gid } = button.dataset;
    try {
      if (act === "files") { await torrentVeilAc(gid); return; }
      if (act === "seed") { await seedAc(gid); return; }
      if (act === "open") await call("open_item_folder", gid);
      else if (act === "retry") {
        const rowId = Number(button.dataset.id);
        if (!rowId) throw new Error(t("err.noRetry"));
        await call("retry", rowId);
        toast(t("toast.retried"));
      } else await call("control", act, gid, false);
      if (act === "remove" && state.selected === gid) state.selected = null;
    } catch (err) { toast(err.message, true); }
    return;
  }
  if (row) {
    state.selected = state.selected === row.dataset.gid ? null : row.dataset.gid;
    renderList();
    renderDrawer();
  }
});
$("dClose").onclick = () => { state.selected = null; renderList(); renderDrawer(); };

document.querySelectorAll(".filter").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll(".filter").forEach((b) => b.classList.remove("on"));
    button.classList.add("on");
    state.filter = button.dataset.f;
    renderList();
  };
});
$("search").oninput = (event) => { state.search = event.target.value; renderList(); };

$("pauseAll").onclick = () => call("control", "pause_all", "", false).catch((e) => toast(e.message, true));
$("resumeAll").onclick = () => call("control", "resume_all", "", false).catch((e) => toast(e.message, true));
$("clearDone").onclick = async () => {
  try {
    const out = await call("clear_finished");
    toast(t("toast.cleared", { n: out.removed || 0 }));
  } catch (err) { toast(err.message, true); }
};
$("openFolder").onclick = () => call("open_download_dir").catch((e) => toast(e.message, true));

/* ---------- kipler ---------- */
function openVeil(id) { $(id).classList.add("open"); }
function closeVeil(id) {
  $(id).classList.remove("open");
  // Ayarlar kapaninca motor listesini bosuna sorgulamayi birak
  if (id === "setVeil" && state.motorTimer) {
    clearInterval(state.motorTimer);
    state.motorTimer = null;
  }
   if (id === "seedVeil" && state.seedTimer) {
     clearInterval(state.seedTimer);
     state.seedTimer = null;
   }
  if (id === "torrentVeil") {
    torState.acik = false;
    torState.nonce = (torState.nonce || 0) + 1;
    // Askida kalan metrik istegi bu pencereyle birlikte terk edilir; kilidi tasimazsak
    // yeniden acilan pencere hic metrik cekemez
    torState.metrikInFlight = false;
    if (state.torTimer) {
      clearInterval(state.torTimer);
      state.torTimer = null;
    }
  }
  // LinkGrabber kapanirsa surunen probe'lari durdur (yeni is yok zaten)
  if (id === "lgVeil") call("linkgrabber_iptal").catch(() => {});
}
document.querySelectorAll("[data-close]").forEach((button) => {
  button.onclick = () => closeVeil(button.dataset.close);
});
document.querySelectorAll(".veil").forEach((veil) => {
  veil.addEventListener("click", (event) => { if (event.target === veil) closeVeil(veil.id); });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") document.querySelectorAll(".veil.open").forEach((v) => closeVeil(v.id));
});

$("addBtn").onclick = () => {
  $("addErr").textContent = "";
  $("quality").value = state.settings.video_quality || "best";
  openVeil("addVeil");
  $("urls").focus();
};
$("addGo").onclick = async () => {
  const lines = $("urls").value.split("\n").map((s) => s.trim()).filter(Boolean);
  if (!lines.length) { $("addErr").textContent = t("err.noLink"); return; }
  const payload = {
    urls: lines,
    quality: $("quality").value,
    audio_only: $("audioOnly").checked || $("quality").value === "audio",
    playlist: $("playlist").checked,
    dest_dir: $("dest").value.trim(),
    start_at: $("startAt").value.trim(),
  };
  try {
    const out = await call("add_links", payload);
    closeVeil("addVeil");
    $("urls").value = "";
    let message = t("toast.started", { n: out.added });
    if (out.scheduled) message = t("toast.scheduled", { n: out.scheduled });
    if (out.failed && out.failed.length) {
      message += t("toast.failed", { n: out.failed.length });
      toast(message + ": " + out.failed[0], true);
    } else {
      toast(message);
    }
  } catch (err) { $("addErr").textContent = err.message; }
};

/* ---------- LinkGrabber (v1.5) ----------
   Akis: metin yapistir -> analiz (ayikla+normalize+tekil) ->
   liste -> canli filtre (ara/joker + tur + domain + boyut) ->
   "+ boyutlari tara" -> sec -> toplu ekle.
   Filtre kurali YALNIZCA core'da (linkgrabber.ogeleri_filtrele); panel
   yalnizca linkgrabber_suz'u cagirir ve gosterilen indeksleri cizer. */
const lgState = { ogeler: [], gosterim: [], filtre: { sadece: [], domain: "", ara: "" } };

function lgTurEtiketi(tur) {
  const anahtar = "lg.tur." + tur;
  const metin = t(anahtar);
  return metin === anahtar ? escapeHtml(tur) : metin;
}

let lgSuzTimer = null;
function lgSuzGecikmeli() {
  clearTimeout(lgSuzTimer);
  lgSuzTimer = setTimeout(lgSuz, 160);
}

async function lgSuz() {
  if (!lgState.ogeler.length) { lgRender(); return; }
  const filtre = {
    sadece: Array.from($("lgSadece").selectedOptions)
      .map((o) => o.value).filter((v) => v !== "all"),
    domain: $("lgDomain").value || "",
    ara: $("lgAra").value.trim(),
    min_boyut: bsBoyutMin($("lgBoyut").value),
    max_boyut: bsBoyutMax($("lgBoyut").value),
  };
  lgState.filtre = filtre;
  const gosterilenler = lgState.ogeler.filter((o) => o.secili).length;
  try {
    const out = await call("linkgrabber_suz", lgState.ogeler, filtre);
    if (out.ok) {
      lgState.gosterim = out.indeks || [];
      const secili = out.indeks.filter((i) => lgState.ogeler[i] && lgState.ogeler[i].secili).length;
      $("lgDurum").textContent = t("lg.listCount", {
        g: out.gosterilen,
        n: out.toplam,
      }) + " · " + t("lg.sonuc", { n: out.toplam, m: secili || gosterilenler });
      $("lgGo").disabled = secili === 0;
      $("lgGo").textContent = t("lg.go", { n: secili });
      lgDomainDoldur(out.domainler || []);
      lgRender();
    }
  } catch (err) { /* bridge yoksa liste eski haliyle kalsin */ }
}

function lgDomainDoldur(domainler) {
  const guncel = $("lgDomain").value;
  const hepsiBir = domainler.length === 0 || (domainler.length === 1 && domainler[0] === "");
  $("lgDomain").innerHTML = '<option value="">' + t("lg.tum") + "</option>" +
    domainler.filter(Boolean).map((d) =>
      `<option value="${escapeHtml(d)}"${d === guncel ? " selected" : ""}>${escapeHtml(d)}</option>`).join("");
  if (hepsiBir) $("lgDomain").value = "";
}

function bsBoyutMin(deger) {
  if (deger === ">1GB") return 1 << 30;
  if (deger === ">100MB") return 100 * (1 << 20);
  if (deger === ">10MB") return 10 * (1 << 20);
  return null;
}

function bsBoyutMax(deger) {
  if (deger === "<10MB") return 10 * (1 << 20);
  if (deger === "<100MB") return 100 * (1 << 20);
  return null;
}

function lgRender() {
  const liste = $("lgListe");
  const durum = $("lgDurum");
  if (!lgState.ogeler.length) {
    liste.innerHTML = '<div class="lg-bos">' + t("lg.bos") + "</div>";
    durum.textContent = t("lg.durumBos");
    $("lgGo").disabled = true;
    return;
  }
  const indeks = lgState.gosterim && lgState.gosterim.length
    ? lgState.gosterim : lgState.ogeler.map((_, i) => i);
  const secili = lgState.ogeler.filter((o) => o.secili).length;
  durum.textContent = t("lg.listCount", { g: indeks.length, n: lgState.ogeler.length }) +
    " · " + t("lg.sonuc", { n: lgState.ogeler.length, m: secili });
  $("lgGo").disabled = secili === 0;
  $("lgGo").textContent = t("lg.go", { n: secili });
  liste.innerHTML = indeks.map((i) => {
    const o = lgState.ogeler[i];
    const boyut = o.probed ? (o.size ? size(Number(o.size)) : t("lg.boyutYok")) : "…";
    const ad = o.filename || "—";
    const onceki = o.oncekiIndirme ? ` <span class="lg-onceki">⚠ ${t("lg.uyariOnceki")}</span>` : "";
    return `<label class="lg-satir${o.secili ? " secili" : ""}${o.oncekiIndirme ? " onceki" : ""}">
      <input type="checkbox" data-i="${i}" ${o.secili ? "checked" : ""}>
      <span class="lg-tur ${o.tur}">${lgTurEtiketi(o.tur)}</span>
      <span class="lg-ad">${escapeHtml(ad)}${onceki}</span>
      <span class="lg-boyut">${o.probed ? boyut : "…"}</span>
      <span class="lg-url">${escapeHtml(o.url)}</span>
    </label>`;
  }).join("");
  liste.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.onchange = () => {
      lgState.ogeler[Number(cb.dataset.i)].secili = cb.checked;
      lgRender();
    };
  });
  const eskiSayisi = lgState.ogeler.filter((o) => o.oncekiIndirme && o.secili).length;
  if (eskiSayisi) {
    durum.textContent += " · " + t("lg.oncekiKaldir");
    durum.style.cursor = "pointer";
    durum.onclick = () => {
      for (const o of lgState.ogeler) if (o.oncekiIndirme) o.secili = false;
      lgRender();
    };
  } else {
    durum.style.cursor = "";
    durum.onclick = null;
  }
}

async function linkgrabberAnaliz() {
  const metin = $("lgMetin").value || "";
  if (!metin.trim()) { toast(t("err.noLink"), true); return; }
  $("lgDurum").textContent = t("lg.analizDurum");
  try {
    const out = await call("linkgrabber_analiz", metin, {});
    const ogeler = (out.ogeler || []).map((o) => ({
      ...o, secili: true, probed: false, filename: "", size: null,
    }));
    const onceki = await call("linkgrabber_onceki", ogeler.map((o) => o.url));
    if (onceki && onceki.ok && onceki.onceki) {
      const set = new Set(onceki.onceki);
      for (const o of ogeler) o.oncekiIndirme = set.has(o.url);
    } else {
      for (const o of ogeler) o.oncekiIndirme = false;
    }
    lgState.ogeler = ogeler;
    lgState.gosterim = lgState.ogeler.map((_, i) => i);
    lgSuz();
    const eski = ogeler.filter((o) => o.oncekiIndirme).length;
    toast(t("lg.bulundu", { n: lgState.ogeler.length })
      + (eski ? " · " + t("lg.oncekiUyari", { n: eski }) : ""));
  } catch (err) { toast(err.message, true); }
}

async function linkgrabberProbe() {
  const secili = lgState.ogeler.filter((o) => o.secili);
  if (!secili.length) { toast(t("err.noLink"), true); return; }
  $("lgDurum").textContent = t("lg.probeDurum");
  try {
    const out = await call("linkgrabber_probe", secili.map((o) => o.url), 8);
    if (out.ogeler) {
      for (const bilgi of out.ogeler) {
        const hedef = lgState.ogeler.find((o) => o.url === bilgi.url);
        if (hedef) {
          hedef.probed = true;
          hedef.filename = bilgi.filename && bilgi.filename !== "download" ? bilgi.filename : "";
          hedef.size = bilgi.size;
          if (bilgi.kategori) hedef.kategori = bilgi.kategori;
        }
      }
    }
    lgSuz();
    toast(t("lg.probeBitti"));
  } catch (err) { toast(err.message, true); }
}

async function linkgrabberEkle() {
  const secili = lgState.ogeler.filter((o) => o.secili);
  if (!secili.length) { toast(t("err.noLink"), true); return; }
  const secim = {
    dest_dir: $("lgDest").value.trim(),
    quality: $("quality").value,
  };
  try {
    const out = await call("linkgrabber_ekle", secili.map((o) => o.url), secim);
    closeVeil("lgVeil");
    $("lgMetin").value = "";
    lgState.ogeler = [];
    lgState.gosterim = [];
    lgRender();
    let message = t("toast.started", { n: out.added });
    if (out.scheduled) message = t("toast.scheduled", { n: out.scheduled });
    if (out.failed && out.failed.length) toast(message + ": " + out.failed[0], true);
    else toast(message);
  } catch (err) { toast(err.message, true); }
}

/* ---------- LinkGrabber paneli (browser handoff dahil) ----------
   Paneli acip filtreleri sifirlayan ortak yardimci. `lgBtn` tiklamasi ve
   uzantidan gelen handoff (`window.afudmLinkgrabber`) bunu kullanir. */
function lgPanelAc() {
  $("lgDomain").value = lgState.filtre.domain || "";
  $("lgSadece").value = "all";
  $("lgAra").value = "";
  $("lgBoyut").value = "";
  $("quality").value = state.settings.video_quality || "best";
  openVeil("lgVeil");
  lgRender();
  $("lgMetin").focus();
}

$("lgBtn").onclick = lgPanelAc;
$("lgAnaliz").onclick = linkgrabberAnaliz;
$("lgProbe").onclick = linkgrabberProbe;
$("lgGo").onclick = linkgrabberEkle;
$("lgSadece").onchange = lgSuz;
$("lgDomain").onchange = lgSuz;
$("lgBoyut").onchange = lgSuz;
$("lgAra").oninput = lgSuzGecikmeli;

/* ---------- seed penceresi (core/manager.seed_tazele) ----------
   aria2 CALISAN torrente tracker EKLEMEZ (olculdu); tazeleme, isi kaldirip
   ayni dizine yeniden eklemekle olur — inen parcalar korunur. */
let seedGid = "";

function seedSatir(etiket, deger) {
  return '<span class="k">' + escapeHtml(etiket) + '</span><span class="v">' +
    escapeHtml(String(deger)) + "</span>";
}

async function seedCiz() {
  const bilgi = await call("seed_bilgi", seedGid);
  $("seedBaslik").textContent = bilgi.baslik || "";
  $("seedKv").innerHTML = [
    seedSatir(t("seed.seed"), bilgi.seed),
    seedSatir(t("seed.conn"), bilgi.baglanti),
    seedSatir(t("seed.tracker"), bilgi.tracker),
    seedSatir(t("seed.havuz"), bilgi.havuz),
    seedSatir(t("seed.yas"), bilgi.liste_yasi_saat === null
      ? t("seed.hicyok") : t("seed.saat", { n: bilgi.liste_yasi_saat })),
    seedSatir(t("seed.dht"), t(bilgi.dht ? "seed.on" : "seed.off")),
    seedSatir(t("seed.ekSayi"), bilgi.ek_sayisi || 0),
  ].join("");
  // Tarama ozeti: olu tracker'lar elendigi icin liste kisa gorunur, sasirtmasin
  const tarama = bilgi.tarama || {};
  $("seedTarama").textContent = tarama.toplam
    ? t("seed.taramaOzet", { canli: tarama.canli || 0, toplam: tarama.toplam,
                             olu: tarama.olu || 0, tanyan: tarama.tanyan || 0 })
    : t("seed.taramaYok");
  // Kullanici yazarken ustune YAZMA: yalniz kutu bosken/degismemisken doldur.
  if (document.activeElement !== $("seedEk") && !$("seedEk").dataset.kirli) {
    $("seedEk").value = bilgi.ek_trackerlar || "";
  }
}

async function seedAc(gid) {
  seedGid = gid;
  $("seedErr").textContent = "";
  $("seedKv").innerHTML = "";
  delete $("seedEk").dataset.kirli;
  openVeil("seedVeil");
  try {
    await seedCiz();
  } catch (err) { $("seedErr").textContent = err.message; }
  // Canli tut: yeniden duyurudan sonra seed'in ARTTIGINI gormek gerekiyor.
  if (state.seedTimer) clearInterval(state.seedTimer);
  state.seedTimer = setInterval(() => seedCiz().catch(() => {}), 2000);
}

$("seedGo").onclick = async () => {
  $("seedErr").textContent = "";
  $("seedGo").disabled = true;
  const eskiYazi = $("seedGo").textContent;
  $("seedGo").textContent = t("seed.calisiyor");
  try {
    const out = await call("seed_tazele", seedGid);
    seedGid = out.gid || seedGid;      // yeniden eklenince GID DEGISIR
    toast(t("seed.bitti", { n: out.tracker || 0 }));
  } catch (err) { $("seedErr").textContent = err.message; }
  $("seedGo").disabled = false;
  $("seedGo").textContent = eskiYazi;
};

$("seedEk").oninput = () => { $("seedEk").dataset.kirli = "1"; };
$("seedKaydet").onclick = async () => {
  try {
    const out = await call("seed_tracker_kaydet", $("seedEk").value);
    $("seedEk").value = out.liste || "";
    delete $("seedEk").dataset.kirli;
    toast(t("seed.eklendi", { n: out.sayi || 0 }));
  } catch (err) { $("seedErr").textContent = err.message; }
};

/* Tracker saglik taramasi (core/tracker_saglik.py): klasordeki butun listeleri
   okur, her adrese GERCEKTEN sorar, cevap vermeyenleri eler. Olculdu: 192
   adresin 151'i oluydu ve aria2 her duyuruda hepsini bekliyordu. */
$("seedTara").onclick = async () => {
  const dugme = $("seedTara");
  const eskiYazi = dugme.textContent;
  dugme.disabled = true;
  dugme.textContent = t("seed.tariyor");
  $("seedErr").textContent = "";
  try {
    const out = await call("tracker_tara", seedGid);
    toast(t("seed.taramaBitti", { canli: out.canli || 0, olu: out.olu || 0 }));
    await seedCiz();
  } catch (err) { $("seedErr").textContent = err.message; }
  dugme.disabled = false;
  dugme.textContent = eskiYazi;
};

$("seedKlasor").onclick = () => {
  call("tracker_klasoru_ac").catch((err) => { $("seedErr").textContent = err.message; });
};

/* ---------- Torrent dosya agaci (core/manager.torrent_dosyalari, torrent_secimi_ayarla) ---------- */
const torState = {
  gid: "",
  baslik: "",
  dosyalar: [],
  filtre: "",
  gosterimLimiti: 250,
  hepsiniGoster: false,
  secimler: new Set(),
  katlanmislar: new Set(),
  sonBasari: null,
  acik: false,
  nonce: 0,
  metrikInFlight: false,
};

function torMetrikleriSifirla(hazirDegilMesaj) {
  const bar = $("torMetrikBar");
  if (bar) bar.style.display = "grid";
  $("torSeedVal").textContent = "—";
  $("torPeersVal").textContent = "—";
  $("torRatioVal").textContent = "—";
  $("torDownVal").textContent = "—";
  $("torUpVal").textContent = "—";
  $("torTrackersVal").textContent = "—";
  if (hazirDegilMesaj) {
    $("torSeedVal").textContent = t("tor.metaNotReady");
  }
}
async function torMetrikleriGuncelle(gid) {
  // Pencere kimligini cagri aninda yakala; await sonrasi degistiyse yanit BAYAT demektir
  const pencereNonce = torState.nonce;
  if (!gid || torState.gid !== gid || !torState.acik) return;
  if (torState.metrikInFlight) return;
  torState.metrikInFlight = true;
  try {
    const out = await call("torrent_metrikleri", gid);
    if (!torState.acik || torState.gid !== gid || torState.nonce !== pencereNonce) return;
    if (!out || !out.ok || out.hazir_degil) {
      torMetrikleriSifirla(Boolean(out && out.hazir_degil));
      if (out && !out.ok) {
        const detay = out.error || out.neden || "";
        $("torBilgi").textContent = detay
          ? t("tor.metricsFailedDetail", { detay })
          : t("tor.metricsFailed");
        $("torBilgi").setAttribute("data-tur", "metrik-hata");
        $("torBilgi").style.display = "block";
      }
      return;
    }
    const m = out.metrikler || {};
    $("torSeedVal").textContent = (m.num_seeders || 0) + (m.seeder ? " (" + t("tor.seeding") + ")" : "");
    $("torPeersVal").textContent = (m.connections || 0) + " (" + (m.peers_seeders || 0) + "S / " + (m.peers_leechers || 0) + "L)";
    $("torRatioVal").textContent = String(m.ratio !== undefined ? m.ratio : 0);
    $("torDownVal").textContent = speed(m.download_speed || 0);
    $("torUpVal").textContent = speed(m.upload_speed || 0) + " [" + size(m.upload_length || 0) + "]";
    $("torTrackersVal").textContent = (m.tracker_sayisi || 0) + " (" + (m.canli_tracker || 0) + " " + t("eng.installed") + ")";
    torState.sonBasari = Date.now();
    if ($("torBilgi").getAttribute("data-tur") === "metrik-hata" || $("torBilgi").textContent.includes("...")) {
      $("torBilgi").style.display = "none";
      $("torBilgi").removeAttribute("data-tur");
    }
  } catch (_) {
    if (!torState.acik || torState.gid !== gid || torState.nonce !== pencereNonce) return;
    // Ag veya RPC anlik yanitsiz kalirsa metrikleri bozma
    if (torState.sonBasari) {
      const sn = Math.floor((Date.now() - torState.sonBasari) / 1000);
      $("torBilgi").textContent = t("tor.retryMetrics", { sn });
    } else {
      $("torBilgi").textContent = t("tor.metricsInitialError");
    }
    $("torBilgi").setAttribute("data-tur", "metrik-hata");
    $("torBilgi").style.display = "block";
  } finally {
    // Yalniz KENDI penceremizin kilidini birak; bayat istek taze pencereyi serbest birakmasin
    if (torState.nonce === pencereNonce) torState.metrikInFlight = false;
  }
}

function torAgacKur(dosyalar) {
  const kok = { ad: "", tamYol: "", klasor: true, cocuklar: {}, dosyalar: [] };
  for (const d of dosyalar) {
    const parcalar = d.yol_parcalari && d.yol_parcalari.length
      ? d.yol_parcalari
      : (d.ad ? [d.ad] : ["unnamed"]);
    let cur = kok;
    for (let i = 0; i < parcalar.length - 1; i++) {
      const p = parcalar[i];
      if (!cur.cocuklar[p]) {
        const altYol = (cur.tamYol ? cur.tamYol + "/" : "") + p;
        cur.cocuklar[p] = { ad: p, tamYol: altYol, klasor: true, cocuklar: {}, dosyalar: [] };
      }
      cur = cur.cocuklar[p];
    }
    cur.dosyalar.push(d);
  }
  return kok;
}

function torDugumDosyalari(dugum) {
  const liste = [...dugum.dosyalar];
  for (const k in dugum.cocuklar) {
    liste.push(...torDugumDosyalari(dugum.cocuklar[k]));
  }
  return liste;
}

function torDugumSecimDurumu(dugum, secimler) {
  const hepsi = torDugumDosyalari(dugum);
  if (!hepsi.length) return "none";
  let seciliSayisi = 0;
  for (const d of hepsi) {
    if (secimler.has(d.indeks)) seciliSayisi++;
  }
  if (seciliSayisi === 0) return "none";
  if (seciliSayisi === hepsi.length) return "all";
  return "some";
}

function torFiltrele(dosyalar, arama) {
  if (!arama) return dosyalar;
  const q = arama.trim().toLocaleLowerCase("tr-TR");
  return dosyalar.filter((d) => {
    const ad = (d.ad || "").toLocaleLowerCase("tr-TR");
    const yol = (d.yol || "").toLocaleLowerCase("tr-TR");
    return ad.includes(q) || yol.includes(q);
  });
}

function torSecimSayaclari(dosyalar, secimler) {
  let seciliSayi = 0;
  let seciliBoyut = 0;
  let toplamBoyut = 0;
  for (const d of dosyalar) {
    const b = Number(d.boyut || 0);
    toplamBoyut += b;
    if (secimler.has(d.indeks)) {
      seciliSayi++;
      seciliBoyut += b;
    }
  }
  return {
    toplam: dosyalar.length,
    secili: seciliSayi,
    toplamBoyut,
    seciliBoyut,
  };
}

function torSayacGuncelle(prefix = "tor") {
  const s = torSecimSayaclari(torState.dosyalar, torState.secimler);
  $(prefix + "Sayac").textContent = t("tor.count", {
    secili: s.secili,
    toplam: s.toplam,
    seciliBoyut: size(s.seciliBoyut),
    toplamBoyut: size(s.toplamBoyut),
  });
}

function torAgacDugumleriCiz(dugum, derinlik, satirlar, ctx) {
  const klasorAdlari = Object.keys(dugum.cocuklar).sort((a, b) => a.localeCompare(b));
  for (const k of klasorAdlari) {
    if (ctx.kalan <= 0) return;
    const alt = dugum.cocuklar[k];
    const altDosyalar = torDugumDosyalari(alt);
    if (!altDosyalar.length) continue;
    const katlanmis = torState.katlanmislar.has(alt.tamYol);
    const secimDurum = torDugumSecimDurumu(alt, torState.secimler);
    const pad = derinlik * 18;

    let toplamAltBoyut = 0;
    for (const d of altDosyalar) toplamAltBoyut += Number(d.boyut || 0);

    satirlar.push(
      '<div class="tor-satir klasor" style="padding-left:' + (10 + pad) + 'px" data-klasor="' + escapeHtml(alt.tamYol) + '">' +
        '<span class="tor-ok" data-act="katla" data-yol="' + escapeHtml(alt.tamYol) + '">' + (katlanmis ? "▶" : "▼") + "</span>" +
        '<input type="checkbox" data-act="klasor-sec" data-yol="' + escapeHtml(alt.tamYol) + '"' +
          (secimDurum === "all" ? " checked" : "") + (secimDurum === "some" ? ' data-indeterminate="1"' : "") + ">" +
        '<span class="tor-simge">📁</span>' +
        '<span class="tor-ad" title="' + escapeHtml(alt.ad) + '">' + escapeHtml(alt.ad) + "</span>" +
        '<span class="tor-boyut">' + size(toplamAltBoyut) + "</span>" +
        '<span class="tor-yuzde-wrap"></span>' +
      "</div>"
    );

    if (!katlanmis) {
      torAgacDugumleriCiz(alt, derinlik + 1, satirlar, ctx);
    }
  }

  const siraliDosyalar = [...dugum.dosyalar].sort((a, b) => (a.ad || "").localeCompare(b.ad || ""));
  for (const d of siraliDosyalar) {
    if (ctx.kalan <= 0) return;
    const pad = derinlik * 18;
    const secili = torState.secimler.has(d.indeks);
    const yuzde = Number(d.yuzde || 0);
    satirlar.push(
      '<div class="tor-satir dosya" style="padding-left:' + (10 + pad) + 'px" data-indeks="' + d.indeks + '">' +
        '<span class="tor-ok bos"></span>' +
        '<input type="checkbox" data-act="dosya-sec" data-indeks="' + d.indeks + '"' + (secili ? " checked" : "") + ">" +
        '<span class="tor-simge">📄</span>' +
        '<span class="tor-ad" title="' + escapeHtml(d.ad) + '">' + escapeHtml(d.ad) + "</span>" +
        '<span class="tor-boyut">' + (d.boyut_insan || size(d.boyut || 0)) + "</span>" +
        '<div class="tor-yuzde-wrap">' +
          '<div class="tor-yuzde-bar"><div class="tor-yuzde-dolgu" style="width:' + Math.min(100, Math.max(0, yuzde)) + '%"></div></div>' +
          '<span class="tor-yuzde-metin">' + yuzde.toFixed(1) + "%</span>" +
        "</div>" +
      "</div>"
    );
    ctx.kalan--;
  }
}

function torAgacCiz(prefix = "tor") {
  const agacKutu = $(prefix + "Agac");
  const limitBar = $(prefix + "LimitBar");
  const limitNot = $(prefix + "LimitNot");
  const bilgiKutu = $(prefix + "Bilgi");

  if (!torState.dosyalar.length) {
    agacKutu.innerHTML = "";
    limitBar.style.display = "none";
    return;
  }

  const filtrelenmis = torFiltrele(torState.dosyalar, torState.filtre);
  if (!filtrelenmis.length) {
    agacKutu.innerHTML = "";
    bilgiKutu.textContent = t("tor.empty");
    bilgiKutu.style.display = "block";
    limitBar.style.display = "none";
    return;
  }
  bilgiKutu.style.display = "none";

  const kok = torAgacKur(filtrelenmis);
  const sinir = torState.hepsiniGoster ? 100000 : torState.gosterimLimiti;
  const ctx = { kalan: sinir };
  const satirlar = [];
  torAgacDugumleriCiz(kok, 0, satirlar, ctx);

  agacKutu.innerHTML = satirlar.join("");

  // Indeterminate checkbox'lari DOM'da aktiflestir
  agacKutu.querySelectorAll('input[data-indeterminate="1"]').forEach((el) => {
    el.indeterminate = true;
  });

  if (!torState.hepsiniGoster && filtrelenmis.length > torState.gosterimLimiti) {
    limitBar.style.display = "flex";
    limitNot.textContent = t("tor.limitNotice", {
      gosterilen: Math.min(torState.gosterimLimiti, filtrelenmis.length),
      toplam: filtrelenmis.length,
    });
    $(prefix + "LimitHepsi").textContent = t("tor.showAll", { n: filtrelenmis.length });
  } else {
    limitBar.style.display = "none";
  }

  torSayacGuncelle(prefix);
}

async function torrentVeilAc(gid) {
  const pencereNonce = ++torState.nonce;
  torState.acik = true;
  torState.gid = gid;
  torState.filtre = "";
  torState.hepsiniGoster = false;
  torState.katlanmislar.clear();
  torState.sonBasari = null;
  $("torErr").textContent = "";
  $("torAra").value = "";
  $("torGid").textContent = gid;
  torMetrikleriSifirla(false);
  if (state.torTimer) {
    clearInterval(state.torTimer);
    state.torTimer = null;
  }

   const oge = state.items.find((i) => i.gid === gid);
   torState.baslik = oge ? (oge.title || oge.filename || gid) : gid;
   $("torBaslik").textContent = torState.baslik;

   $("torBilgi").style.display = "none";
   $("torAgac").innerHTML = "";
   $("torLimitBar").style.display = "none";
   $("torUygula").disabled = true;
   openVeil("torrentVeil");
  torMetrikleriGuncelle(gid).catch(() => {});
  let retryCount = 0;
  let agacHazir = false;
  let inFlight = false;

  async function dosyalariCek() {
    if (inFlight) return false;
    if (!torState.acik || torState.nonce !== pencereNonce) return false;
    inFlight = true;
    try {
      const out = await call("torrent_dosyalari", torState.gid);
      if (!torState.acik || torState.nonce !== pencereNonce) return false;

      if (!out || !out.ok) throw new Error((out && out.error) || t("err.failed"));

      if (out.hazir_degil) {
        if (!torState.acik || torState.nonce !== pencereNonce) return false;
        torState.dosyalar = [];
        torState.secimler.clear();
        $("torBilgi").textContent = out.neden || t("tor.notReady");
        $("torBilgi").style.display = "block";
        $("torSayac").textContent = "";
        $("torUygula").disabled = true;
        if (++retryCount > 30) {
          $("torErr").textContent = t("tor.timeout");
        }
        return false;
      }

      if (!torState.acik || torState.nonce !== pencereNonce) return false;
      torState.gid = out.gid || torState.gid; // resolved gid
      $("torGid").textContent = torState.gid;
      torState.dosyalar = out.dosyalar || [];
      torState.secimler = new Set();
      for (const d of torState.dosyalar) {
        if (d.secili) torState.secimler.add(d.indeks);
      }

      $("torUygula").disabled = false;
      torAgacCiz();
      agacHazir = true;
      return true;
    } catch (err) {
      if (!torState.acik || torState.nonce !== pencereNonce) return false;
      $("torErr").textContent = err.message;
      $("torBilgi").textContent = err.message;
      $("torBilgi").style.display = "block";
      agacHazir = true; // stop retrying on fatal error
      return true;
    } finally {
      inFlight = false;
    }
  }

  dosyalariCek();
  state.torTimer = setInterval(() => {
    if (torState.gid && torState.acik && torState.nonce === pencereNonce) {
      torMetrikleriGuncelle(torState.gid).catch(() => {});
      if (!agacHazir && retryCount <= 30 && !inFlight) dosyalariCek();
    }
  }, 2000);
}

/* Torrent dosya agaci etkilesimleri (tests/torrent_ui_test.py bekler: $("torSayac") $("torAra") $("torSecHepsi") $("torSecHicbiri") $("torSecTers") $("torLimitHepsi") $("torLimitBar") $("torLimitNot") $("torBilgi") $("torAgac")) */
function torOlaylariBagla(prefix) {
  $(prefix + "Agac").addEventListener("click", (event) => {
    const hedef = event.target;
    const ok = hedef.closest('[data-act="katla"]');
    if (ok) {
      const yol = ok.dataset.yol;
      if (torState.katlanmislar.has(yol)) torState.katlanmislar.delete(yol);
      else torState.katlanmislar.add(yol);
      torAgacCiz(prefix);
      return;
    }
    if (hedef.dataset.act === "klasor-sec") {
      const yol = hedef.dataset.yol;
      const durum = hedef.checked;
      const altDosyalar = torState.dosyalar.filter((d) => {
        return d.parent_yol === yol || (d.parent_yol && d.parent_yol.startsWith(yol + "/"));
      });
      for (const d of altDosyalar) {
        if (durum) torState.secimler.add(d.indeks);
        else torState.secimler.delete(d.indeks);
      }
      torAgacCiz(prefix);
      return;
    }
    if (hedef.dataset.act === "dosya-sec") {
      const indeks = Number(hedef.dataset.indeks);
      if (hedef.checked) torState.secimler.add(indeks);
      else torState.secimler.delete(indeks);
      torAgacCiz(prefix);
      return;
    }
  });
  $(prefix + "Ara").oninput = () => {
    torState.filtre = $(prefix + "Ara").value;
    torAgacCiz(prefix);
  };
  $(prefix + "LimitHepsi").onclick = () => {
    torState.hepsiniGoster = true;
    torAgacCiz(prefix);
  };
  $(prefix + "SecHepsi").onclick = () => {
    for (const d of torState.dosyalar) torState.secimler.add(d.indeks);
    torAgacCiz(prefix);
  };
  $(prefix + "SecHicbiri").onclick = () => {
    torState.secimler.clear();
    torAgacCiz(prefix);
  };
  $(prefix + "SecTers").onclick = () => {
    for (const d of torState.dosyalar) {
      if (torState.secimler.has(d.indeks)) torState.secimler.delete(d.indeks);
      else torState.secimler.add(d.indeks);
    }
    torAgacCiz(prefix);
  };
}

torOlaylariBagla("tor");
torOlaylariBagla("kayTor");


$("torUygula").onclick = async () => {
  if (!torState.gid) return;
  $("torErr").textContent = "";
  const dugme = $("torUygula");
  const eskiYazi = dugme.textContent;
  dugme.disabled = true;
  dugme.textContent = t("tor.applying");

  const seciliIndeksler = Array.from(torState.secimler).sort((a, b) => a - b);
  // Tum dosyalar secildiyse bos liste gonderilir (aria2 select-file="" tum dosyalar demek)
  const gonderilecek = seciliIndeksler.length === torState.dosyalar.length ? [] : seciliIndeksler;

  try {
    const out = await call("torrent_secimi_ayarla", torState.gid, gonderilecek);
    if (!out.ok) throw new Error(out.error || t("err.failed"));
    const msg = gonderilecek.length === 0
      ? t("tor.appliedAll")
      : t("tor.applied", { n: seciliIndeksler.length });
    toast(msg);
    if (state.torTimer) {
      clearInterval(state.torTimer);
      state.torTimer = null;
    }
    closeVeil("torrentVeil");
  } catch (err) {
    $("torErr").textContent = err.message;
  } finally {
    dugme.disabled = false;
    dugme.textContent = eskiYazi;
  }
};


/* ---------- Ayarlar > Seed listeleri (core/tracker_saglik.py) ----------
   Dosya eklemek icin trackers/ klasorune elle kopyalamak gerekiyordu; burasi
   ayni klasoru arayuzden yonetir. Liste degisince Python tarafi taramayi
   bayatlatip arka planda yeniden olcer — canli adresler torrentlere oradan
   uygulanir. */
async function seedListeCiz() {
  let out;
  try {
    out = await call("seed_dosyalari");
  } catch (err) {
    $("sSeedOzet").textContent = err.message;
    return;
  }
  const kutu = $("sSeedListe");
  kutu.innerHTML = "";
  const dosyalar = out.dosyalar || [];
  if (!dosyalar.length) {
    const bos = document.createElement("div");
    bos.className = "hint";
    bos.textContent = t("set.seedBos");
    kutu.appendChild(bos);
  }
  for (const d of dosyalar) {
    const satir = document.createElement("div");
    satir.className = "seed-dosya";
    const ad = document.createElement("span");
    ad.className = "seed-ad";
    ad.textContent = d.ad;                  // dosya adi kullanicidan gelir: metin olarak bas
    ad.title = d.ad;
    const sayi = document.createElement("span");
    sayi.className = "seed-sayi";
    sayi.textContent = t("set.seedAdres", { n: d.sayi });
    const sil = document.createElement("button");
    sil.className = "btn ghost seed-sil";
    sil.textContent = t("set.seedSil");
    sil.onclick = async () => {
      if (!confirm(t("set.seedSilOnay") + "\n" + d.ad)) return;
      try {
        await call("seed_dosya_sil", d.ad);
        toast(t("set.seedSilindi", { ad: d.ad }));
        await seedListeCiz();
      } catch (err) { toast(err.message, true); }
    };
    satir.append(ad, sayi, sil);
    kutu.appendChild(satir);
  }
  const tarama = out.tarama || {};
  $("sSeedOzet").textContent = tarama.toplam
    ? t("set.seedOzet", {
        adres: out.adres || 0, canli: tarama.canli || 0, olu: tarama.olu || 0,
        saat: out.tarama_yasi_saat === null ? "?" : out.tarama_yasi_saat })
    : t("set.seedOzetYok", { adres: out.adres || 0 });
  $("sSeedOto").checked = !!out.otomatik;
}

$("sSeedEkle").onclick = async () => {
  try {
    const out = await call("seed_dosya_ekle", "");
    if (out.iptal) return;                   // kullanici dosya secicisini kapatti
    toast(out.zaten ? t("set.seedZaten", { ad: out.ad })
                    : t("set.seedEklendi", { ad: out.ad, n: out.sayi || 0 }));
    await seedListeCiz();
  } catch (err) { toast(err.message, true); }
};

$("sSeedKlasor").onclick = () => {
  call("tracker_klasoru_ac").catch((err) => toast(err.message, true));
};

$("sSeedTara").onclick = async () => {
  const dugme = $("sSeedTara");
  const eskiYazi = dugme.textContent;
  dugme.disabled = true;
  dugme.textContent = t("set.seedTariyor");
  try {
    const out = await call("tracker_tara", "");
    toast(t("set.seedTaraBitti", { canli: out.canli || 0, olu: out.olu || 0 }));
    await seedListeCiz();
  } catch (err) { toast(err.message, true); }
  dugme.disabled = false;
  dugme.textContent = eskiYazi;
};

/* ---------- Chrome'a ekle (core/chrome_kurulum.py) ---------- */
function chromeCiz(durum) {
  const adimlar = durum.adimlar || {};
  document.querySelectorAll("#chrAdimlar li").forEach((satir) => {
    let hal = adimlar[satir.dataset.adim] || "";
    if (satir.dataset.adim === "baglandi") {
      hal = durum.baglandi ? "tamam" : (adimlar.dogrula === "tamam" ? "calisiyor" : "");
    }
    satir.className = hal === "bekliyor" ? "" : hal;
  });
  const sonuc = $("chrSonuc");
  if (durum.baglandi) {
    sonuc.textContent = t("chr.ok");
    sonuc.className = "chr-sonuc iyi";
  } else if (durum.sonuc === "hata") {
    sonuc.textContent = t(durum.mesaj === "chrome_yok" ? "chr.noChrome" : "chr.fail");
    sonuc.className = "chr-sonuc kotu";
    $("chrElle").open = true;  // otomasyon takildiysa elle yol hemen gorunsun
  } else if (durum.sonuc === "kuruldu") {
    sonuc.textContent = t("chr.waitPair");
    sonuc.className = "chr-sonuc";
  } else {
    sonuc.textContent = "";
    sonuc.className = "chr-sonuc";
  }
  $("chrAuto").disabled = !!durum.calisiyor || !!durum.baglandi;
}

async function chromeIzle() {
  if (!$("chromeVeil").classList.contains("open")) {
    clearInterval(state.chromeTimer);
    state.chromeTimer = null;
    return;
  }
  try { chromeCiz(await call("chrome_ilerleme")); } catch (_) { /* kopru yoksa sessiz */ }
}

$("openChrome").onclick = async () => {
  try {
    const bilgi = await call("chrome_hazirla");
    $("chrKlasor").textContent = bilgi.klasor;
    $("chrKlasor").title = bilgi.klasor;
    if (!bilgi.chrome) {
      chromeCiz({ sonuc: "hata", mesaj: "chrome_yok" });
      $("chrAuto").disabled = true;
    }
  } catch (err) { toast(err.message, true); }
  openVeil("chromeVeil");
  chromeIzle();
  clearInterval(state.chromeTimer);
  state.chromeTimer = setInterval(chromeIzle, 700);
};
$("chrAuto").onclick = async () => {
  $("chrAuto").disabled = true;
  try { await call("chrome_otomatik"); } catch (err) { toast(err.message, true); }
  chromeIzle();
};
document.querySelectorAll("[data-kopya]").forEach((dugme) => {
  dugme.onclick = async () => {
    try {
      await call("chrome_kopyala", dugme.dataset.kopya);
      toast(t("chr.copied"));
    } catch (err) { toast(err.message, true); }
  };
});

$("openSettings").onclick = async () => {
  const s = state.settings;
  $("sLang").value = s.language || "auto";
  $("sDir").value = s.download_dir || "";
  $("sSplit").value = s.split ?? 64;
  $("sConn").value = s.max_conn_per_server ?? 16;
  $("sConc").value = s.max_concurrent ?? 5;
  $("sSpeed").value = s.max_speed_kb ?? 0;
  $("sMode").value = s.hiz_profili || "normal";
  $("sRatio").value = s.seed_ratio ?? 1;
  $("sChat").value = s.telegram_chat_id || "";
  $("sToken").value = s.telegram_bot_token || "";
  $("sClip").checked = !!s.clipboard_watch;
  $("sTrackers").checked = !!s.auto_update_trackers;
  $("sNotify").checked = !!s.notify_telegram;
  $("sShutdown").checked = !!s.shutdown_when_done;
  $("sSleep").checked = !!s.sleep_when_done;
  gucDurumu();
  $("sKaydet").checked = s.kaydetme_penceresi !== false;
  $("sKategori").checked = s.kategori_klasorleri !== false;
  $("sTepsi").checked = s.tepsiye_kucult !== false;
  $("sBasTepside").checked = s.baslangicta_tepside !== false;
  sistemDurumu();
  telefonDurumu();
  seedListeCiz();
  $("sSeedEk").value = s.ek_trackerlar || "";
  $("sVideoAltyaziDiller").value = s.video_altyazi_diller || "";
  $("sVideoOtoAltyazi").checked = !!s.video_oto_altyazi;
  $("sVideoAltyaziGoem").checked = !!s.video_altyazi_goem;
  $("sVideoKucukResim").value = s.video_kucuk_resim || "";
  $("sVideoUstveriGoem").checked = !!s.video_ustveri_goem;
  $("sVideoBolumler").value = s.video_bolumler || "";
  $("sVideoSponsorblock").value = s.video_sponsorblock || "";
  $("sVideoBolumAraligi").value = s.video_bolum_araligi || "";
  $("sVideoKapsayici").value = s.video_kapsayici || "";
  $("sVideoSesFormati").value = s.video_ses_formati || "";
  $("sVideoDosyaSablonu").value = s.video_dosya_sablonu || "";
  $("sVideoTarayiciCerezi").value = s.video_tarayici_cerezi || "";
  $("sSeedEkOzet").textContent = "";
  surumuCiz();
  try {
    const info = await call("api_info");
    $("apiHint").textContent =
      t("hint.api", { port: info.port });
  } catch (_) { $("apiHint").textContent = ""; }
  renderEngines();
  if (state.motorTimer) clearInterval(state.motorTimer);
  state.motorTimer = setInterval(renderEngines, 1000);
  openVeil("setVeil");
};

/* Rules Engine: editor state is local until the explicit save action. */
let rulesDraft = [];
const ruleFields = ["domain","extension","filename","size_mb","protocol","category"];
const ruleOps = ["eq","neq","contains","ends_with","regex","in","gt","lt"];
const ruleActions = ["dest_dir","proxy","max_speed_kb","split","start_after","automation_script"];
const ruleId = () => "rule-" + Date.now() + "-" + Math.random().toString(16).slice(2);
function rulesRender() {
  const root=$("rulesList"); if(!rulesDraft.length){root.innerHTML='<div class="empty">'+escapeHtml(t("rules.empty"))+'</div>';return;}
  root.innerHTML=rulesDraft.map((r,i)=>{const cs=(r.conditions||[]).map((c,j)=>'<div class="rule-row"><select data-f="'+i+'" data-j="'+j+'">'+ruleFields.map(v=>'<option '+(c.field===v?'selected':'')+'>'+v+'</option>').join('')+'</select><select data-o="'+i+'" data-j="'+j+'">'+ruleOps.map(v=>'<option '+(c.op===v?'selected':'')+'>'+v+'</option>').join('')+'</select><input data-v="'+i+'" data-j="'+j+'" value="'+escapeHtml(Array.isArray(c.value)?c.value.join(','):c.value||'')+'"><button data-cdel="'+i+'" data-j="'+j+'">×</button></div>').join('');const as=Object.entries(r.actions||{}).map(([k,v])=>'<div class="rule-row"><select data-a="'+i+'" data-k="'+k+'">'+ruleActions.map(x=>'<option '+(x===k?'selected':'')+'>'+x+'</option>').join('')+'</select><input data-av="'+i+'" data-k="'+k+'" value="'+escapeHtml(v)+'"><button data-adel="'+i+'" data-k="'+k+'">×</button></div>').join('');return '<div class="rule-card"><div class="rule-head"><input type="checkbox" data-active="'+i+'" '+(r.active?'checked':'')+'><input data-name="'+i+'" value="'+escapeHtml(r.name||'')+'" placeholder="'+escapeHtml(t("rules.name"))+'"><select data-match="'+i+'"><option value="all">'+escapeHtml(t("rules.all"))+'</option><option value="any" '+(r.match_type==='any'?'selected':'')+'>'+escapeHtml(t("rules.any"))+'</option></select><button data-up="'+i+'">↑</button><button data-down="'+i+'">↓</button><button data-copy="'+i+'">'+escapeHtml(t("rules.copy"))+'</button><button data-del="'+i+'">'+escapeHtml(t("rules.delete"))+'</button></div><div class="rule-rows">'+cs+'<button data-addc="'+i+'">'+escapeHtml(t("rules.addCondition"))+'</button></div><div class="rule-rows">'+as+'<button data-adda="'+i+'">'+escapeHtml(t("rules.addAction"))+'</button></div></div>';}).join('');
}
$("rulesOpen").onclick=async()=>{try{rulesDraft=(await call("rules_list")).rules||[];rulesRender();openVeil("rulesVeil");}catch(e){toast(e.message,true);}};
$("rulesNew").onclick=()=>{rulesDraft.push({id:ruleId(),name:"",active:true,match_type:"all",conditions:[],actions:{}});rulesRender();};
$("rulesList").onchange=e=>{const x=e.target,i=Number(x.dataset.f??x.dataset.o??x.dataset.v??x.dataset.a??x.dataset.av??x.dataset.active??x.dataset.name??x.dataset.match),r=rulesDraft[i],j=Number(x.dataset.j);if(!r)return;if(x.dataset.active!==undefined)r.active=x.checked;else if(x.dataset.name!==undefined)r.name=x.value;else if(x.dataset.match!==undefined)r.match_type=x.value;else if(x.dataset.f!==undefined)r.conditions[j].field=x.value;else if(x.dataset.o!==undefined)r.conditions[j].op=x.value;else if(x.dataset.v!==undefined)r.conditions[j].value=x.value.includes(',')?x.value.split(',').map(v=>v.trim()):x.value;else if(x.dataset.a!==undefined){const v=r.actions[x.dataset.k];delete r.actions[x.dataset.k];r.actions[x.value]=v;rulesRender();}else if(x.dataset.av!==undefined)r.actions[x.dataset.k]=x.value;};
$("rulesList").onclick=e=>{const x=e.target,i=Number(x.dataset.up??x.dataset.down??x.dataset.copy??x.dataset.del??x.dataset.addc??x.dataset.adda??x.dataset.cdel??x.dataset.adel),r=rulesDraft[i];if(!r)return;if(x.dataset.up!==undefined&&i)[rulesDraft[i-1],rulesDraft[i]]=[r,rulesDraft[i-1]];else if(x.dataset.down!==undefined&&i<rulesDraft.length-1)[rulesDraft[i+1],rulesDraft[i]]=[r,rulesDraft[i+1]];else if(x.dataset.copy!==undefined)rulesDraft.splice(i+1,0,{...r,id:ruleId(),conditions:r.conditions.map(c=>({...c})),actions:{...r.actions}});else if(x.dataset.del!==undefined)rulesDraft.splice(i,1);else if(x.dataset.addc!==undefined)r.conditions.push({field:"domain",op:"eq",value:""});else if(x.dataset.adda!==undefined)r.actions.max_speed_kb="";else if(x.dataset.cdel!==undefined)r.conditions.splice(Number(x.dataset.j),1);else if(x.dataset.adel!==undefined)delete r.actions[x.dataset.k];rulesRender();};
$("rulesSave").onclick=async()=>{try{const out=await call("rules_save",rulesDraft);if(!out.ok)throw new Error(out.error);closeVeil("rulesVeil");toast(t("toast.saved"));}catch(e){$("rulesErr").textContent=e.message;}};
$("rulesRun").onclick=async()=>{try{const out=await call("rules_simulate",$("rulesUrl").value.trim()),names=(out.matched_rules||[]).map(r=>r.name).join(', ');$("rulesResult").textContent=names?t("rules.match",{n:names}):t("rules.noMatch");if((out.conflicts||[]).length)$("rulesResult").textContent+=" · "+t("rules.conflict",{items:out.conflicts.join(', ')});}catch(e){$("rulesResult").textContent=e.message;}};

/* ---------- sistem ayarlari: baslangic + .torrent/magnet (core/baslangic.py,
   core/iliskilendir.py) ---------- */
async function sistemDurumu() {
  try {
    const bilgi = await call("sistem_durumu");
    $("sBaslangic").checked = !!bilgi.baslangic;
    const torrent = (bilgi.torrent || {}).torrent || {};
    const magnet = (bilgi.torrent || {}).magnet || {};
    $("sTorrent").checked = !!(torrent.kayitli && magnet.kayitli);
    // Windows'un varsayilan uygulama secimi (UserChoice) disaridan
    // degistirilemez: kayit tamamsa bile kullaniciya dogruyu soyle.
    $("torrentHint").textContent = !$("sTorrent").checked ? ""
      : t(torrent.varsayilan ? "hint.torrentOk" : "hint.torrentDefault");
  } catch (_) { /* Windows disi ya da erisim yok: kutular oldugu gibi kalir */ }
}

async function sistemAyarlariniUygula() {
  const hatalar = [];
  try {
    // Kisayolun argumani da burada guncellenir (--tepside)
    await call("baslangic_ayarla", $("sBaslangic").checked, $("sBasTepside").checked);
  } catch (err) { hatalar.push(err.message); }
  try {
    await call("torrent_iliskilendir", $("sTorrent").checked);
  } catch (err) { hatalar.push(err.message); }
  if (hatalar.length) toast(hatalar[0], true);
}

/* Windows'un varsayilan uygulama ekrani: .torrent secimini YALNIZ kullanici
   yapabilir (UserChoice hash korumali), en fazla dogru ekrani acabiliriz. */
$("sVarsayilan").onclick = async () => {
  try {
    await call("varsayilan_uygulama_ekrani");
    toast(t("hint.varsayilan"));
  } catch (err) { toast(err.message, true); }
};

/* ---------- telefon arayuzu (ui/mobil.html) ----------
   Kutu acilinca yerel API 0.0.0.0'a gecer ve adres burada gorunur. Ayar
   ANINDA uygulanir (sunucu yeniden kurulur), yeniden baslatma gerekmez. */
async function telefonDurumu() {
  try {
    const bilgi = await call("telefon_durumu");
    $("sTelefon").checked = !!bilgi.acik;
    $("telefonKutu").style.display = bilgi.acik ? "" : "none";
    $("sTelefonAdres").value = bilgi.adres || "";
    $("sTelefonQr").src = bilgi.qr || "";
    if (bilgi.acik && !bilgi.adres) toast(t("err.agYok"), true);
  } catch (_) { /* kopru hazir degil */ }
}

$("sTelefon").onchange = async () => {
  try {
    const bilgi = await call("telefon_ayarla", $("sTelefon").checked);
    $("telefonKutu").style.display = bilgi.acik ? "" : "none";
    $("sTelefonAdres").value = bilgi.adres || "";
    $("sTelefonQr").src = bilgi.qr || "";
    if (bilgi.acik && !bilgi.adres) toast(t("err.agYok"), true);
  } catch (err) { toast(err.message, true); }
};

$("sTelefonKopya").onclick = async () => {
  const adres = $("sTelefonAdres").value;
  if (!adres) return;
  try {
    await navigator.clipboard.writeText(adres);
    toast(t("toast.kopyalandi"));
  } catch (_) {
    $("sTelefonAdres").select();       // pano kapaliysa: secili birak, elle kopyalasin
    document.execCommand("copy");
    toast(t("toast.kopyalandi"));
  }
};

/* Telefondan uyandirma: tarayici UDP gonderemez, bu yuzden uyandirmayi
   telefondaki bir WoL uygulamasi yapar — burada MAC'i ve kartin hazir olup
   olmadigini gosteriyoruz (bkz. core/guc.py). */
async function gucDurumu() {
  try {
    const bilgi = await call("guc_durumu");
    $("sMac").value = bilgi.mac || "";
    const anahtar = bilgi.wol === true ? "wol.acik"
      : bilgi.wol === false ? "wol.kapali" : "wol.bilinmiyor";
    let metin = t(anahtar, { kart: bilgi.kart || "?" });
    if (!bilgi.hazir) metin += t("wol.hazirDegil");
    $("wolDurum").textContent = metin;
  } catch (_) { $("wolDurum").textContent = ""; }
}

$("sMacKopya").onclick = async () => {
  if (!$("sMac").value) return;
  try {
    await navigator.clipboard.writeText($("sMac").value);
    toast(t("toast.kopyalandi"));
  } catch (_) {
    $("sMac").select();
    document.execCommand("copy");
    toast(t("toast.kopyalandi"));
  }
};

/* ---------- motorlar (Ayarlar icinde) ---------- */
async function renderEngines() {
  const kutu = $("engines");
  if (!kutu) return;
  let bilgi;
  try {
    bilgi = await call("motor_durumu");
  } catch (_) {
    return;
  }
  const satirlar = [];
  for (const ad of Object.keys(bilgi.motorlar)) {
    const m = bilgi.motorlar[ad];
    const ilerleme = bilgi.ilerleme[ad] || {};
    let rozet;
    let dugme = "";
    if (ilerleme.durum === "iniyor") {
      const yuzde = ilerleme.toplam
        ? Math.round((ilerleme.inen / ilerleme.toplam) * 100) : 0;
      rozet = '<span class="rozet">' + escapeHtml(t("eng.downloading", { yuzde: yuzde })) + "</span>";
    } else if (ilerleme.durum === "hata") {
      rozet = '<span class="rozet hata" title="' + escapeHtml(ilerleme.hata || "") + '">'
        + escapeHtml(t("eng.failed")) + "</span>";
      dugme = '<button data-motor="' + ad + '">'
        + escapeHtml(t("eng.download", { mb: m.indirme_boyutu_mb })) + "</button>";
    } else if (m.var) {
      rozet = '<span class="rozet">' + escapeHtml(t("eng.installed")) + " · " + m.boyut_mb + " MB</span>";
    } else if (m.kaynak === "sistem") {
      // Klasorde yok ama Windows'ta kurulu: gizlemek yerine acikca soyle.
      rozet = '<span class="rozet sistem" title="' + escapeHtml(t("eng.fromSystemTip")) + '">'
        + escapeHtml(t("eng.fromSystem")) + "</span>";
      dugme = '<button data-motor="' + ad + '">'
        + escapeHtml(t("eng.download", { mb: m.indirme_boyutu_mb })) + "</button>";
    } else {
      rozet = '<span class="rozet eksik">' + escapeHtml(m.zorunlu ? t("eng.required") : "—") + "</span>";
      dugme = '<button data-motor="' + ad + '">'
        + escapeHtml(t("eng.download", { mb: m.indirme_boyutu_mb })) + "</button>";
    }
    satirlar.push(
      '<div class="engine-row"><span class="ad">' + escapeHtml(ad) + "</span>" +
      '<span class="ne">' + escapeHtml(t("eng." + ad)) + "</span>" +
      rozet + dugme + "</div>"
    );
  }
  kutu.innerHTML = satirlar.join("");
}

$("engines").addEventListener("click", async (event) => {
  const dugme = event.target.closest("button[data-motor]");
  if (!dugme) return;
  dugme.disabled = true;
  try {
    await call("motor_indir", dugme.dataset.motor);
    renderEngines();
  } catch (err) {
    toast(err.message, true);
    dugme.disabled = false;
  }
});
$("pairBtn").onclick = async () => {
  try {
    const out = await call("start_pairing", 120);
    toast(t("toast.pairing", { port: out.port }));
  } catch (err) { toast(err.message, true); }
};

$("setGo").onclick = async () => {
  const payload = {
    language: $("sLang").value,
    download_dir: $("sDir").value.trim(),
    split: Number($("sSplit").value) || 64,
    max_conn_per_server: Number($("sConn").value) || 16,
    max_concurrent: Number($("sConc").value) || 5,
    max_speed_kb: Number($("sSpeed").value) || 0,
    hiz_profili: $("sMode").value || "normal",
    seed_ratio: Number($("sRatio").value) || 0,
    telegram_chat_id: $("sChat").value.trim(),
    telegram_bot_token: $("sToken").value.trim(),
    clipboard_watch: $("sClip").checked,
    auto_update_trackers: $("sTrackers").checked,
    notify_telegram: $("sNotify").checked,
    shutdown_when_done: $("sShutdown").checked,
    sleep_when_done: $("sSleep").checked,
    kaydetme_penceresi: $("sKaydet").checked,
    kategori_klasorleri: $("sKategori").checked,
    tepsiye_kucult: $("sTepsi").checked,
    baslangicta_tepside: $("sBasTepside").checked,
    tracker_otomatik_tara: $("sSeedOto").checked,
    video_altyazi_diller: $("sVideoAltyaziDiller").value.trim(),
    video_oto_altyazi: $("sVideoOtoAltyazi").checked,
    video_altyazi_goem: $("sVideoAltyaziGoem").checked,
    video_kucuk_resim: $("sVideoKucukResim").value,
    video_ustveri_goem: $("sVideoUstveriGoem").checked,
    video_bolumler: $("sVideoBolumler").value,
    video_sponsorblock: $("sVideoSponsorblock").value.trim(),
    video_bolum_araligi: $("sVideoBolumAraligi").value.trim(),
    video_kapsayici: $("sVideoKapsayici").value,
    video_ses_formati: $("sVideoSesFormati").value,
    video_dosya_sablonu: $("sVideoDosyaSablonu").value.trim(),
    video_tarayici_cerezi: $("sVideoTarayiciCerezi").value,
  };
  try {
    await call("settings_save", payload);
    // Windows'a dokunan iki ayar (Baslangic klasoru / kayit defteri) ayri
    // gider: biri patlarsa digerleri ve ayarlar yine de kaydedilmis olsun.
    await sistemAyarlariniUygula();
    closeVeil("setVeil");
    toast(t("toast.saved"));
  } catch (err) { toast(err.message, true); }
};

/* ---------- klasor agaci (core/kaydet.py) ----------
   Tek bir pencere; klasorSec() cagrilinca acilir ve secilen yolu dondurur.
   Alt klasorler ISTENDIKCE okunur: tum disk hicbir zaman taranmaz. */
let klasorSoz = null;   // acik secimin cozucusu

function agacSatiri(oge, derinlik) {
  const satir = document.createElement("div");
  satir.className = "dugum";
  satir.style.paddingLeft = 6 + derinlik * 14 + "px";
  satir.dataset.yol = oge.yol;
  satir.dataset.derinlik = String(derinlik);
  const ok = document.createElement("span");
  ok.className = "ok" + (oge.alt ? "" : " bos");
  ok.textContent = oge.alt ? "▸" : "";
  const ad = document.createElement("span");
  ad.className = "ad";
  // Kisayolun adi dile gore yazilir; disk ve alt klasorler kendi adiyla kalir.
  const anahtar = oge.anahtar && oge.anahtar !== "disk" ? "klas." + oge.anahtar : "";
  ad.textContent = anahtar ? t(anahtar) : oge.ad;
  ad.title = oge.yol;
  satir.append(ok, ad);
  return satir;
}

function agacSec(satir) {
  document.querySelectorAll("#agac .dugum.on").forEach((d) => d.classList.remove("on"));
  satir.classList.add("on");
  $("klasYol").value = satir.dataset.yol;
}

async function agacAc(satir) {
  const derinlik = Number(satir.dataset.derinlik) + 1;
  if (satir.classList.contains("acik")) {          // kapat: alt satirlari sil
    satir.classList.remove("acik");
    satir.querySelector(".ok").textContent = "▸";
    let sonraki = satir.nextSibling;
    while (sonraki && Number(sonraki.dataset.derinlik) >= derinlik) {
      const silinecek = sonraki;
      sonraki = sonraki.nextSibling;
      silinecek.remove();
    }
    return;
  }
  const out = await call("klasor_alt", satir.dataset.yol);
  satir.classList.add("acik");
  satir.querySelector(".ok").textContent = "▾";
  let imlec = satir;
  (out.ogeler || []).forEach((alt) => {
    const yeni = agacSatiri(alt, derinlik);
    imlec.after(yeni);
    imlec = yeni;
  });
}

$("agac").addEventListener("click", async (event) => {
  const satir = event.target.closest(".dugum");
  if (!satir) return;
  agacSec(satir);
  if (event.target.classList.contains("ok") && !event.target.classList.contains("bos")) {
    try { await agacAc(satir); } catch (err) { $("klasErr").textContent = err.message; }
  }
});
/* Ag konumunu listeden kaldirma: uzerine SAG TIK. Silme degil, yalniz
   kisayolu listeden cikarir — paylasimdaki dosyalara DOKUNULMAZ. */
$("agac").addEventListener("contextmenu", async (event) => {
  const satir = event.target.closest(".dugum");
  if (!satir || Number(satir.dataset.derinlik) !== 0) return;
  if (!satir.dataset.yol.startsWith("\\\\")) return;
  event.preventDefault();
  if (!confirm(t("klas.agSil") + "\n" + satir.dataset.yol)) return;
  try {
    await call("ag_konumu_sil", satir.dataset.yol);
    await agaciYenile();
  } catch (err) { $("klasErr").textContent = err.message; }
});

$("agac").addEventListener("dblclick", async (event) => {
  const satir = event.target.closest(".dugum");
  if (satir && satir.querySelector(".ok").textContent) {
    try { await agacAc(satir); } catch (err) { $("klasErr").textContent = err.message; }
  }
});

async function klasorSec(baslangic) {
  $("klasErr").textContent = "";
  $("klasYol").value = baslangic || "";
  await agaciYenile();
  openVeil("klasorVeil");
  return new Promise((coz) => { klasorSoz = coz; });
}

function klasorKapat(yol) {
  closeVeil("klasorVeil");
  const coz = klasorSoz;
  klasorSoz = null;
  if (coz) coz(yol);
}

$("klasCancel").onclick = () => klasorKapat("");
$("klasOk").onclick = () => {
  const yol = $("klasYol").value.trim();
  if (!yol) { $("klasErr").textContent = t("err.noFolder"); return; }
  klasorKapat(yol);
};
$("klasYeni").onclick = async () => {
  const ust = $("klasYol").value.trim();
  if (!ust) { $("klasErr").textContent = t("err.noFolder"); return; }
  const ad = prompt(t("klas.newAsk"), "");
  if (!ad) return;
  try {
    const out = await call("klasor_yeni", ust, ad);
    $("klasYol").value = out.yol;
    $("klasErr").textContent = "";
  } catch (err) { $("klasErr").textContent = err.message; }
};
$("klasSistem").onclick = async () => {
  // Windows'un kendi klasor secicisi: agactan bulunamayan yerler icin kacis yolu
  try {
    const out = await call("klasor_gozat", $("klasYol").value.trim());
    if (out.yol) klasorKapat(out.yol);
  } catch (err) { $("klasErr").textContent = err.message; }
};
/* Ortulunun disina tiklamak ve ESC de secimi BITIRMELI: yoksa klasorSec()'in
   sozu asili kalir ve kaydetme penceresi bir daha yanit vermez. */
$("klasorVeil").addEventListener("click", (event) => {
  if (event.target === $("klasorVeil") && klasorSoz) klasorKapat("");
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && klasorSoz) klasorKapat("");
});

/* Modem/NAS paylasimi: UNC yolu eklenir, dogrulanir ve agacta kisayol olur.
   OLCULDU: aria2 UNC yoluna sorunsuz iniyor, ek ayar gerekmiyor. */
$("klasAg").onclick = async () => {
  const yol = prompt(t("klas.agSor"), "\\\\");
  if (!yol) return;
  try {
    const out = await call("ag_konumu_ekle", yol);
    $("klasErr").textContent = "";
    $("klasYol").value = out.yol;
    await agaciYenile();
    toast(t("klas.agEklendi"));
  } catch (err) { $("klasErr").textContent = err.message; }
};

async function agaciYenile() {
  const govde = $("agac");
  govde.innerHTML = "";
  const out = await call("klasor_kisayollar");
  (out.ogeler || []).forEach((oge) => govde.append(agacSatiri(oge, 0)));
}

$("destPick").onclick = async () => {
  const yol = await klasorSec($("dest").value.trim() || state.settings.download_dir || "");
  if (yol) $("dest").value = yol;
};

/* ---------- kaydetme penceresi (IDM'in "indirme bilgisi" penceresi) ----------
   Link nereden gelirse gelsin (pano, uzanti) once burada durur: dosya adi,
   klasor, kategori ve ne zaman baslayacagi secilir. */
const kayit = { kimlik: null, url: "", kind: "", klasorler: {}, ana: "" };

function kategoriDoldur(bilgi) {
  const secici = $("kayCat");
  secici.innerHTML = "";
  Object.keys(bilgi.klasorler || {}).forEach((anahtar) => {
    const secenek = document.createElement("option");
    secenek.value = anahtar;
    secenek.textContent = t("kay.c." + anahtar);
    secici.append(secenek);
  });
  secici.value = bilgi.kategori;
}

function kayHedefYaz() {
  // Kategori klasorleri kapaliysa hepsi ana klasore iner.
  $("kayDest").value = kayit.klasorler[$("kayCat").value] || kayit.ana;
}

async function kaydetAc(istek) {
  const bilgi = await call("kaydet_bilgi", istek.url || "");
  kayit.kimlik = istek.id === undefined ? null : istek.id;
  kayit.url = istek.url || "";
  kayit.kind = istek.kind || bilgi.kind;
  kayit.klasorler = bilgi.kategori_klasorleri ? bilgi.klasorler : {};
  kayit.ana = bilgi.ana;
  kayit.preGid = null;
  torState.dosyalar = [];
  $("kayTorWrap").style.display = kayit.kind === "torrent" ? "block" : "none";
  
  $("kayUrl").textContent = kayit.url;
  $("kayUrl").title = kayit.url;
  $("kayName").value = istek.filename || istek.title || bilgi.dosya_adi || "";
  kategoriDoldur(bilgi);
  kayHedefYaz();
  $("kayQualityWrap").style.display = kayit.kind === "video" ? "" : "none";
  $("kayVideoGelismisWrap").style.display = kayit.kind === "video" ? "" : "none";
  $("kayVideoGelismisWrap").open = false;
  ["AltyaziDiller", "Sponsorblock", "BolumAraligi", "DosyaSablonu"].forEach((ad) => { $("kayVideo" + ad).value = ""; });
  ["KucukResim", "Bolumler", "Kapsayici", "SesFormati", "TarayiciCerezi"].forEach((ad) => { $("kayVideo" + ad).value = ""; });
  ["OtoAltyazi", "AltyaziGoem", "UstveriGoem"].forEach((ad) => { $("kayVideo" + ad).checked = false; });
  $("kayQuality").value = istek.quality || state.settings.video_quality || "best";
  $("kayNow").checked = true;
  $("kayAt").value = "";
  $("kayErr").textContent = "";
  $("kayQueue").textContent = "";
  openVeil("kaydetVeil");
  $("kayName").focus();

  if (kayit.kind === "torrent" && kayit.url) {
    $("kayTorBilgi").style.display = "block";
    $("kayTorBilgi").textContent = t("tor.fetchingMeta", "Torrent bilgisi alınıyor...");
    $("kayTorAgac").innerHTML = "";
    $("kayTorLimitBar").style.display = "none";
    $("kayTorSayac").textContent = "";
    
    call("torrent_on_ekle", kayit.url).then(out => {
      if (out.ok) {
        kayit.preGid = out.gid;
        torState.gid = out.gid;
        torState.filtre = "";
        torState.hepsiniGoster = false;
        torState.katlanmislar.clear();
        torState.secimler.clear();
        kayTorYokla(out.gid);
      } else {
        $("kayTorBilgi").textContent = out.error;
      }
    }).catch(e => {
        $("kayTorBilgi").textContent = e.message;
    });
  }


  // dlman v1.12.0 yaklasimi: pencere aninda acilir, arka planda Content-Disposition
  // ve MIME turu yoklanir; kullanici adi degistirmediyse otomatik guncellenir.
  if (kayit.kind === "http" && kayit.url && /^https?:\/\//i.test(kayit.url)) {
    const baslangicAd = $("kayName").value;
    call("probe_link", kayit.url).then((probe) => {
      if (!probe || !probe.ok) return;
      if ($("kayName").value === baslangicAd && probe.filename) {
        $("kayName").value = probe.filename;
        if (probe.kategori && probe.kategori !== "genel") {
          $("kayCat").value = probe.kategori;
          kayHedefYaz();
        }
      }
      if (probe.size) {
        const devam = probe.resumable ? " · devam edebilir" : "";
        $("kayQueue").textContent = size(probe.size) + devam;
      }
    }).catch(() => {});
  }
}

$("kayCat").onchange = kayHedefYaz;
$("kayPick").onclick = async () => {
  const yol = await klasorSec($("kayDest").value.trim() || kayit.ana);
  if (yol) $("kayDest").value = yol;
};
$("kayAt").onfocus = () => { $("kayLater").checked = true; };

const observer = new MutationObserver((mutations) => {
  mutations.forEach((m) => {
    if (m.attributeName === "class" && !$("kaydetVeil").classList.contains("open")) {
      if (kayit.preGid) {
        call("torrent_on_iptal", kayit.preGid).catch(()=>{});
        kayit.preGid = null;
      }
      const kimlik = kayit.kimlik;
      kayit.kimlik = null;
      if (kimlik !== null) {
        call("bekleyen_iptal", kimlik).catch(()=>{});
        bekleyenYokla();
      }
    }
  });
});
observer.observe($("kaydetVeil"), { attributes: true });

$("kayCancel").onclick = () => { closeVeil("kaydetVeil"); };

async function kayTorYokla(gid) {
  if (kayit.preGid !== gid || !$("kaydetVeil").classList.contains("open")) return;
  try {
    const out = await call("torrent_dosyalari", gid);
    if (!out.ok) throw new Error(out.error || t("err.failed"));
    if (out.hazir_degil) {
      setTimeout(() => kayTorYokla(gid), 1500);
      return;
    }
    $("kayTorBilgi").style.display = "none";
    torState.dosyalar = out.dosyalar || [];
    torState.secimler = new Set();
    for (const d of torState.dosyalar) {
      if (d.secili) torState.secimler.add(d.indeks);
    }
    if (torState.secimler.size === 0 && torState.dosyalar.length > 0) {
       for (const d of torState.dosyalar) torState.secimler.add(d.indeks);
    }
    torAgacCiz("kayTor");
  } catch (err) {
    $("kayTorBilgi").textContent = err.message;
  }
}

$("kayGo").onclick = async () => {
  const secim = {
    filename: $("kayName").value.trim(),
    dest_dir: $("kayDest").value.trim(),
    kategori: $("kayCat").value,
    quality: kayit.kind === "video" ? $("kayQuality").value : "",
    audio_only: kayit.kind === "video" && $("kayQuality").value === "audio",
    start_at: $("kayLater").checked ? $("kayAt").value.trim() : "",
    altyazi_diller: $("kayVideoAltyaziDiller").value.trim(),
    oto_altyazi: $("kayVideoOtoAltyazi").checked ? true : "",
    altyazi_goem: $("kayVideoAltyaziGoem").checked ? true : "",
    kucuk_resim: $("kayVideoKucukResim").value.trim(),
    ustveri_goem: $("kayVideoUstveriGoem").checked ? true : "",
    bolumler: $("kayVideoBolumler").value.trim(),
    sponsorblock: $("kayVideoSponsorblock").value.trim(),
    bolum_araligi: $("kayVideoBolumAraligi").value.trim(),
    kapsayici: $("kayVideoKapsayici").value.trim(),
    ses_formati: $("kayVideoSesFormati").value.trim(),
    dosya_sablonu: $("kayVideoDosyaSablonu").value.trim(),
    tarayici_cerezi: $("kayVideoTarayiciCerezi").value.trim(),
  };
  
  if (kayit.kind === "torrent" && kayit.preGid && torState.dosyalar.length > 0) {
    secim.adopt_gid = kayit.preGid;
    const secili = Array.from(torState.secimler).sort((a, b) => a - b);
    secim.selected_files = secili.length === torState.dosyalar.length ? [] : secili;
  } else if (kayit.kind === "torrent" && kayit.preGid) {
    secim.adopt_gid = kayit.preGid;
  }
  
  kayit.preGid = null;
  const kimlik = kayit.kimlik;
  kayit.kimlik = null;
  
  try {
    if (kimlik !== null) {
      await call("bekleyen_onayla", kimlik, secim);
    } else {
      await call("add_links", { urls: [kayit.url], ...secim });
    }
    closeVeil("kaydetVeil");
    toast(secim.start_at ? t("toast.scheduled", { n: 1 }) : t("toast.started", { n: 1 }));
    bekleyenYokla();
  } catch (err) { $("kayErr").textContent = err.message; }
};

/* Tarayicidan gelen istek: Python pencereyi one getirip afudmBekleyen() cagirir.
   Cagri kaybolursa (sayfa henuz hazir degildi) tick yine de bulur. */
async function bekleyenYokla() {
  let ogeler = [];
  try {
    ogeler = (await call("bekleyen_listesi")).ogeler || [];
  } catch (_) { return; }
  // Gosterilen istek listeden DUSMEZ (onay/iptalde duser): sayarken cikarilir.
  const kalan = ogeler.length - (kayit.kimlik === null ? 0 : 1);
  if ($("kaydetVeil").classList.contains("open")) {
    // Pencere acikken de sayac islesin: arkada biriken istekler gorulsun.
    $("kayQueue").textContent = kalan > 0 ? t("kay.queue", { n: kalan }) : "";
    return;
  }
  if (!ogeler.length) return;
  try {
    await kaydetAc(ogeler[0]);
    $("kayQueue").textContent = ogeler.length > 1 ? t("kay.queue", { n: ogeler.length - 1 }) : "";
  } catch (err) { toast(err.message, true); }
}

window.afudmBekleyen = () => { bekleyenYokla(); };

/* ---------- pano yakalama teklifi (Python cagirir) ---------- */
window.afudmClipboard = async (url) => {
  // Kaydetme penceresi kapaliysa (ayar) eski davranis: link ekleme penceresi.
  if (state.settings.kaydetme_penceresi === false) {
    $("urls").value = url;
    $("addErr").textContent = t("toast.clipboard");
    openVeil("addVeil");
    return;
  }
  try {
    await kaydetAc({ url });
  } catch (err) { toast(err.message, true); }
};

/* ---------- browser handoff (Python cagirir) ----------
   Uzanti "Sayfadaki linkleri LinkGrabber'a gönder" dediginde buraya ham metin
   duser: panel acilir, metin analiz kutusuna konur ve analiz hemen calisir. */
window.afudmLinkgrabber = async (metin, dosya) => {
  lgPanelAc();
  $("lgMetin").value = metin || "";
  lgRender();
  await linkgrabberAnaliz();
};

/* ---------- ozel baslik cubugu (core/pencere.py) ---------- */
window.afudmPencere = async () => {
  if (!window.pywebview || !window.pywebview.api.pencere_durumu) return;
  const durum = await window.pywebview.api.pencere_durumu();
  document.documentElement.classList.toggle("ozel-baslik", !!durum.ozel);
  document.documentElement.classList.toggle("buyuk", !!durum.buyuk);
  $("wcMax").title = t(durum.buyuk ? "win.restore" : "win.max");
};
$("wcMin").onclick = () => window.pywebview.api.pencere_kucult();
$("wcMax").onclick = async () => { await window.pywebview.api.pencere_buyut(); window.afudmPencere(); };
$("wcClose").onclick = () => window.pywebview.api.pencere_kapat();
document.querySelectorAll(".wc-edge").forEach((kenar) => {
  kenar.addEventListener("mousedown", (event) => {
    if (event.button === 0) window.pywebview.api.pencere_kenar(kenar.dataset.edge);
  });
});
// Buyut/geri al Windows'tan da gelebilir (cift tik, Snap, Win+Yukari): simgeyi esitle.
let pencereZamanlayici;
window.addEventListener("resize", () => {
  clearTimeout(pencereZamanlayici);
  pencereZamanlayici = setTimeout(() => window.afudmPencere(), 120);
});

window.addEventListener("pywebviewready", () => {
  state.ready = true;
  window.afudmPencere();
  surumuYukle();
});
tick();
drawTrace();

/* ---------- Sag tik menusu + pano ------------------------------------
   WebView2'de pywebview varsayilan sag tik menusunu ve tarayici kisayollarini
   DEBUG bayragina bagli aciyor (edgechromium.py): surumde ikisi de kapaliydi,
   yani ne "bagliyi kopyala" vardi ne de Ctrl+C. Kisayollari core/pencere.py
   geri actik; menuyu burada kendimiz ciziyoruz.

   Pano islemleri Python uzerinden (Windows `clip` + panoyu dogrudan okuma):
   navigator.clipboard gomulu pencerede izin isteyip sessizce dusuyor. */
const ctxKutu = $("ctx");  // canvas baglami (ctx) ile karismasin

async function panoyaYaz(metin) {
  if (!metin) return false;
  try {
    const out = await call("panoya_kopyala", metin);
    return !!out.ok;
  } catch (_) { return false; }
}

async function panodanOku() {
  try {
    const out = await call("panodan_oku");
    return out.metin || "";
  } catch (_) { return ""; }
}

function ctxKapat() { ctxKutu.hidden = true; ctxKutu.innerHTML = ""; }

/* ogeler: {etiket, calis, pasif} | "ayrac" | {baslik: "..."} */
function ctxAc(x, y, ogeler) {
  ctxKutu.innerHTML = "";
  for (const oge of ogeler) {
    if (oge === "ayrac") { ctxKutu.appendChild(document.createElement("hr")); continue; }
    if (oge.baslik !== undefined) {
      const ust = document.createElement("div");
      ust.className = "ctx-url";
      ust.textContent = oge.baslik;         // adres kullanicidan gelir: metin olarak bas
      ust.title = oge.baslik;
      ctxKutu.appendChild(ust);
      continue;
    }
    const dugme = document.createElement("button");
    dugme.type = "button";
    dugme.textContent = oge.etiket;
    dugme.disabled = !!oge.pasif;
    dugme.onclick = async () => {
      ctxKapat();
      try { await oge.calis(); } catch (err) { toast(err.message, true); }
    };
    ctxKutu.appendChild(dugme);
  }
  ctxKutu.hidden = false;
  // Once goster, SONRA olc: gizliyken genislik/yukseklik 0 gelir ve menu
  // ekranin disina tasardi.
  const kutu = ctxKutu.getBoundingClientRect();
  ctxKutu.style.left = Math.max(4, Math.min(x, innerWidth - kutu.width - 6)) + "px";
  ctxKutu.style.top = Math.max(4, Math.min(y, innerHeight - kutu.height - 6)) + "px";
}

addEventListener("click", (event) => { if (!ctxKutu.contains(event.target)) ctxKapat(); }, true);
addEventListener("blur", ctxKapat);
addEventListener("resize", ctxKapat);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") ctxKapat(); });

/* Metin kutulari: kes/kopyala/yapistir/tumunu sec.
   Yapistirma Python'dan gelir, boylece izin penceresi cikmaz. */
function metinMenusu(alan) {
  const secili = alan.value.slice(alan.selectionStart, alan.selectionEnd);
  const yaz = (metin) => {
    const bas = alan.selectionStart;
    const son = alan.selectionEnd;
    alan.value = alan.value.slice(0, bas) + metin + alan.value.slice(son);
    alan.selectionStart = alan.selectionEnd = bas + metin.length;
    // oninput dinleyicileri (ornegin "kirli" isareti) calissin
    alan.dispatchEvent(new Event("input", { bubbles: true }));
  };
  return [
    { etiket: t("ctx.cut"), pasif: !secili || alan.readOnly,
      calis: async () => { if (await panoyaYaz(secili)) yaz(""); } },
    { etiket: t("ctx.copy"), pasif: !secili,
      calis: async () => { if (await panoyaYaz(secili)) toast(t("ctx.copied")); } },
    { etiket: t("ctx.paste"), pasif: alan.readOnly,
      calis: async () => { const m = await panodanOku(); if (m) yaz(m); } },
    "ayrac",
    { etiket: t("ctx.selectAll"), calis: async () => alan.select() },
  ];
}

document.addEventListener("contextmenu", async (event) => {
  const alan = event.target.closest("input[type=text], input:not([type]), input[type=search], textarea");
  if (alan) {
    event.preventDefault();
    ctxAc(event.clientX, event.clientY, metinMenusu(alan));
    return;
  }
  const satir = event.target.closest("#list .row");
  if (!satir) return;
  event.preventDefault();
  const gid = satir.dataset.gid;
  const oge = state.items.find((i) => i.gid === gid);
  if (!oge) return;
  const adres = oge.source || "";
  const ad = oge.filename || "";
  const yol = ad ? (oge.dir ? oge.dir.replace(/[\/]+$/, "") + "\\" + ad : ad) : (oge.dir || "");
  ctxAc(event.clientX, event.clientY, [
    { baslik: adres || oge.title || gid },
    { etiket: t("ctx.copyLink"), pasif: !adres,
      calis: async () => { if (await panoyaYaz(adres)) toast(t("ctx.copied")); } },
    { etiket: t("ctx.copyPath"), pasif: !yol,
      calis: async () => { if (await panoyaYaz(yol)) toast(t("ctx.copied")); } },
    { etiket: t("ctx.copyName"), pasif: !ad,
      calis: async () => { if (await panoyaYaz(ad)) toast(t("ctx.copied")); } },
    "ayrac",
    { etiket: t("ctx.openFile"), pasif: oge.status !== "complete",
      calis: () => call("dosya_ac", gid) },
    { etiket: t("ctx.openFolder"), calis: () => call("open_item_folder", gid) },
    "ayrac",
    { etiket: t("ctx.again"), pasif: !adres,
      calis: async () => {
        $("urls").value = adres;
        $("addErr").textContent = "";
        $("quality").value = state.settings.video_quality || "best";
        openVeil("addVeil");
        $("urls").focus();
      } },
  ]);
});

/* Kisayollar acilinca Ctrl+R / F5 / Ctrl+P de geliyor: yeniden yukleme
   arayuzu sifirlar, yazdirma anlamsiz. Kopyala/yapistir kalsin, bunlar gitsin. */
document.addEventListener("keydown", (event) => {
  const k = (event.key || "").toLowerCase();
  if (event.key === "F5" || ((event.ctrlKey || event.metaKey) && (k === "r" || k === "p"))) {
    event.preventDefault();
  }
});

/* ---------- Surum (core/surum.py) ----------------------------------
   Kullanici hangi kopyayi calistirdigini gorebilmeli: sol seritte kisa,
   Ayarlar'da uzanti surumuyle birlikte. Kopru hazir olmadan cagrilirsa
   sessizce bos kalir — surum gostergesi yuzunden arayuz patlamasin. */
let surumBilgisi = null;

async function surumuYukle() {
  if (surumBilgisi) return surumBilgisi;
  try {
    surumBilgisi = await call("surum_bilgi");
  } catch (_) { return null; }
  $("brandSurum").textContent = "v" + surumBilgisi.surum;
  return surumBilgisi;
}

async function surumuCiz() {
  const bilgi = await surumuYukle();
  const kutu = $("sSurum");
  kutu.innerHTML = "";
  if (!bilgi) { kutu.textContent = t("set.surumYok"); return; }
  const satir = (etiket, deger) => {
    const d = document.createElement("div");
    d.textContent = etiket + " ";
    const b = document.createElement("b");
    b.textContent = deger;
    d.appendChild(b);
    kutu.appendChild(d);
  };
  satir(t("set.surumUygulama"), bilgi.surum);
  if (bilgi.uzanti) satir(t("set.surumUzanti"), bilgi.uzanti);
}

/* ---------- Ayarlar > kendi tracker'larin (elle yapistirma) ---------- */
$("sSeedEkYapistir").onclick = async () => {
  const metin = await panodanOku();
  if (!metin) { $("sSeedEkOzet").textContent = t("set.seedEkPanoBos"); return; }
  const alan = $("sSeedEk");
  alan.value = (alan.value.trim() ? alan.value.replace(/\s*$/, "") + "\n" : "") + metin.trim();
  $("sSeedEkOzet").textContent = "";
};

$("sSeedEkKaydet").onclick = async () => {
  try {
    // seed_tracker_kaydet gecersiz satirlari ayiklar ve TEMIZ listeyi geri verir
    const out = await call("seed_tracker_kaydet", $("sSeedEk").value);
    $("sSeedEk").value = out.liste || "";
    state.settings.ek_trackerlar = out.liste || "";
    $("sSeedEkOzet").textContent = t("set.seedEkKayitli", { n: out.sayi || 0 });
    toast(t("set.seedEkKayitli", { n: out.sayi || 0 }));
  } catch (err) { $("sSeedEkOzet").textContent = err.message; }
};
