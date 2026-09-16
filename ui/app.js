/* AfuDM arayuz mantigi. Python tarafina pywebview koprusuyle konusur. */

const $ = (id) => document.getElementById(id);
const POLL_MS = 700;
const TRACE_POINTS = 180;

const state = {
  filter: "all",
  motorTimer: null,
  search: "",
  selected: null,
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
async function renderDrawer() {
  const drawer = $("drawer");
  if (!state.selected) { drawer.className = "drawer"; return; }
  const item = state.items.find((i) => i.gid === state.selected);
  if (!item) { drawer.className = "drawer"; return; }
  drawer.className = "drawer open";
  $("dTitle").textContent = item.title || item.gid;
  $("dGid").textContent = item.gid;
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

  const wrap = $("dPeersWrap");
  if (item.kind !== "torrent") { wrap.innerHTML = ""; return; }
  let peers = [];
  try { peers = (await call("peers", item.gid)).peers || []; } catch (_) { peers = []; }
  if (!peers.length) {
    wrap.innerHTML = '<div class="hint">Peer bulunmadi. DHT ve guncel tracker listesi taramaya devam ediyor.</div>';
    return;
  }
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
}
document.querySelectorAll("[data-close]").forEach((button) => {
  button.onclick = () => closeVeil(button.dataset.close);
});
document.querySelectorAll(".veil").forEach((veil) => {
  veil.addEventListener("click", (event) => { if (event.target === veil) veil.classList.remove("open"); });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") document.querySelectorAll(".veil.open").forEach((v) => v.classList.remove("open"));
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

$("openSettings").onclick = async () => {
  const s = state.settings;
  $("sLang").value = s.language || "auto";
  $("sDir").value = s.download_dir || "";
  $("sSplit").value = s.split ?? 64;
  $("sConn").value = s.max_conn_per_server ?? 16;
  $("sConc").value = s.max_concurrent ?? 5;
  $("sSpeed").value = s.max_speed_kb ?? 0;
  $("sRatio").value = s.seed_ratio ?? 1;
  $("sChat").value = s.telegram_chat_id || "";
  $("sToken").value = s.telegram_bot_token || "";
  $("sClip").checked = !!s.clipboard_watch;
  $("sTrackers").checked = !!s.auto_update_trackers;
  $("sNotify").checked = !!s.notify_telegram;
  $("sShutdown").checked = !!s.shutdown_when_done;
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
    seed_ratio: Number($("sRatio").value) || 0,
    telegram_chat_id: $("sChat").value.trim(),
    telegram_bot_token: $("sToken").value.trim(),
    clipboard_watch: $("sClip").checked,
    auto_update_trackers: $("sTrackers").checked,
    notify_telegram: $("sNotify").checked,
    shutdown_when_done: $("sShutdown").checked,
  };
  try {
    await call("settings_save", payload);
    closeVeil("setVeil");
    toast(t("toast.saved"));
  } catch (err) { toast(err.message, true); }
};

/* ---------- pano yakalama teklifi (Python cagirir) ---------- */
window.afudmClipboard = (url) => {
  $("urls").value = url;
  $("addErr").textContent = t("toast.clipboard");
  openVeil("addVeil");
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

window.addEventListener("pywebviewready", () => { state.ready = true; window.afudmPencere(); });
tick();
drawTrace();
