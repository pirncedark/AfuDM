(() => {
  const $ = (id) => document.getElementById(id);
  let active = null;
  let runningGid = "";
  let busy = false;
  let dil = "tr";

  let defaults = {};
  let qualityDirty = false;
  let nameDirty = false;
  let folderDirty = false;
  let folderReset = false;
  let lastReset = 0;
  const t = (key) => lang.t(key);

  const size = (b) => {
    if (b < 1024) return b + " B";
    if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
    if (b < 1073741824) return (b / 1048576).toFixed(1) + " MB";
    return (b / 1073741824).toFixed(2) + " GB";
  };
  const speed = (b) => b > 0 ? size(b) + "/s" : "—";
  const clock = (s) => {
    if (s <= 0) return "—";
    if (s < 60) return s + " sn";
    if (s < 3600) return Math.floor(s / 60) + " dk " + (s % 60) + " sn";
    const h = Math.floor(s / 3600);
    return h + " sa " + Math.floor((s % 3600) / 60) + " dk";
  };

  function translate() {
    lang.setLang(dil);
    lang.applyStatic();
    document.title = "AfuDM \u2014 " + t("download.title");
    if (!runningGid) $("progressLabel").textContent = t("download.starting");
  }

  async function refresh() {
    if (!window.pywebview?.api || busy) return;
    const state = await window.pywebview.api.pencere_durumu();
    if (state.hidden) return;
    if (state.reset !== lastReset) {
      lastReset = state.reset;
      window.afudmDownloadReset();
    }
    dil = await window.pywebview.api.dil();
    translate();
    await window.pywebview.api.baslik(document.title);
    const pending = await window.pywebview.api.bekleyen_listesi();
    const ogeler = (pending.ogeler || []).filter((item) => item.source === "browser");
    if (ogeler.length) {
      runningGid = "";
      $("confirmPane").hidden = false;
      $("progressPane").hidden = true;
    }
    if (runningGid) {
      const { item = {} } = await window.pywebview.api.indirme_durumu(runningGid);
      $("confirmPane").hidden = true;
      $("progressPane").hidden = false;
      if (!item.gid) {
        $("progressLabel").textContent = t("download.failed");
        return;
      }
      $("progressName").textContent = item.filename || item.title || t("download.title");
      const p = Math.round(Number(item.progress) || 0);
      $("progress").value = p;
      let text = p + "%";
      if (item.status === "complete") {
        text = t("download.done");
      } else if (item.status === "error") {
        text = t("download.failed");
      } else if (item.status === "active") {
        text = `${p}% \u2014 ${speed(item.downloadSpeed)} \u2014 ${clock(item.eta)} \u2014 ${size(item.completedLength || 0)} / ${size(item.totalLength || 0)}`;
      }
      $("progressLabel").textContent = text;
      return;
    }
    if (!ogeler.length) return;
    const item = ogeler[0];
    if (active?.id === item.id) return;

    $("start").disabled = true;
    busy = true;
    const selectedId = item.id;
    let video = false;
    try {
      const shown = await window.pywebview.api.bekleyen_goster(selectedId);
      if (!shown?.ok) {
        return;
      }
      defaults = await window.pywebview.api.kaydet_bilgi(item.url, item.filename || "", item.kind || "");
      video = (item.kind || defaults.kind) === "video";
      qualityDirty = false;
      nameDirty = false;
      folderDirty = false;
      folderReset = false;
      $("qualityWrap").hidden = !video;
      $("quality").value = item.audio_only ? "audio" : item.quality || defaults.video_quality || "best";

      $("url").textContent = item.url;
      $("name").value = item.filename || (video ? "" : item.title || defaults.dosya_adi || "");
      $("folder").value = defaults.son_klasor || ((defaults.kategori_klasorleri && defaults.klasorler?.[defaults.kategori]) || defaults.ana || "");
      $("error").textContent = "";

      active = item;
    } finally {
      $("start").disabled = false;
      busy = false;
    }
    if (!video && /^https?:\/\//i.test(item.url) && window.pywebview.api.probe_link) {
      const initialName = $("name").value;
      const initialFolder = $("folder").value;
      Promise.resolve().then(() => window.pywebview.api.probe_link(item.url)).then((info) => {
        if (!info?.ok || active !== item || busy) return;
        if (!nameDirty && $("name").value === initialName && info.filename) $("name").value = info.filename;
        if (info.kategori) {
          defaults.kategori = info.kategori;
          if (!folderDirty && !folderReset && $("folder").value === initialFolder && defaults.kategori_klasorleri) {
            $("folder").value = defaults.son_klasor || (defaults.klasorler?.[info.kategori] || defaults.ana || "");
          }
        }
      }).catch(() => {});
    }
  }

  async function cancel() {
    if (!active || busy) return;
    await window.pywebview.api.bekleyen_iptal(active.id);
    active = null;
    await refresh();
  }

  $("quality").onchange = () => { qualityDirty = true; };
  $("name").oninput = () => { nameDirty = true; };
  $("folder").oninput = () => { folderDirty = true; };
  $("browse").onclick = async () => {
    try {
      const out = await window.pywebview.api.klasor_gozat($("folder").value);
      if (!out || out.ok === false) throw new Error();
      if (out.yol) { folderDirty = true; folderReset = false; $("folder").value = out.yol; $("error").textContent = ""; }
    } catch {
      $("error").textContent = t("download.browseFailed");
    }
  };
  $("resetFolder").onclick = () => {
    folderDirty = false;
    folderReset = true;
    $("folder").value = (defaults.kategori_klasorleri && defaults.klasorler?.[defaults.kategori]) || defaults.ana || "";
  };
  $("cancel").onclick = cancel;
  $("start").onclick = async () => {
    if (!active || busy) return;
    busy = true;
    $("start").disabled = true;
    try {
      const out = await window.pywebview.api.bekleyen_onayla(active.id, {
        filename: $("name").value.trim(), dest_dir: $("folder").value.trim(),
        ...(nameDirty ? {filename_edited: true} : {}),
        ...(folderDirty ? {folder_edited: true} : {}),
        ...(folderReset ? {folder_reset: true} : {}),
        kategori: defaults.kategori || "genel",
        ...((active.kind || defaults.kind) === "video" ? {
          quality: !qualityDirty && active.quality ? active.quality : $("quality").value,
          audio_only: !qualityDirty && active.audio_only !== undefined ? active.audio_only : $("quality").value === "audio",
        } : {}),
      });
      if (!out.ok) throw new Error(out.error_code || out.error || "failed");
      active = null;
      runningGid = out.gid || "";
      $("confirmPane").hidden = !!runningGid;
      $("progressPane").hidden = !runningGid;
    } catch (error) {
      $("error").textContent = error.message === "folder" ? t("download.folderError") : t("download.failed");
    } finally {
      busy = false;
      $("start").disabled = false;
    }
  };
  $("close").onclick = () => { runningGid = ""; window.pywebview.api.kapat(); };
  window.afudmDownloadReset = () => {
    active = null;
    qualityDirty = false;
    runningGid = "";
    $("confirmPane").hidden = false;
    $("progressPane").hidden = true;
    $("error").textContent = "";
  };
  window.afudmDownloadRefresh = refresh;
  window.addEventListener("pywebviewready", refresh);
  setInterval(refresh, 800);
})();
