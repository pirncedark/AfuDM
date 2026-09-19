/* Acilir pencere: durum, hizli ekleme, sayfadaki medya, baglanti ayarlari. */

const $ = (id) => document.getElementById(id);

function say(message, kind = "") {
  $("note").textContent = message;
  $("note").className = "note " + kind;
}

function ask(message) {
  return new Promise((resolve) => chrome.runtime.sendMessage(message, resolve));
}

async function refresh() {
  const status = await ask({ type: "status" });
  $("dot").className = "dot" + (status.alive ? " ok" : "");
  $("state").textContent = status.alive
    ? chrome.i18n.getMessage("stateRunning", [String(status.cfg.port)])
    : chrome.i18n.getMessage("stateOff");
  $("port").value = status.cfg.port;
  $("token").value = status.cfg.token;
  $("minSize").value = status.cfg.minSizeMB;
  $("uzantiAcik").checked = status.cfg.uzantiAcik !== false;
  $("kapaliNot").hidden = status.cfg.uzantiAcik !== false;
  $("panelKonum").value = status.cfg.panelKonum || "ust-sag";
  $("enabled").checked = status.cfg.enabled;
  $("sendCookies").checked = status.cfg.sendCookies;
  $("videoCatch").checked = status.cfg.videoCatch;
  if (!status.cfg.token) {
    say(chrome.i18n.getMessage("msgTokenEmpty"), "bad");
  }

  const found = await ask({ type: "media" });
  if (!$("url").value && found.pageUrl) $("url").value = found.pageUrl;
  if (found.media.length) {
    $("mediaWrap").style.display = "block";
    $("media").innerHTML = found.media
      .map((entry, index) =>
        '<div><span title="' + entry.url.replace(/"/g, "&quot;") + '">' +
        entry.url.split("/").pop().slice(0, 44) +
        '</span><button data-i="' + index + '">' + chrome.i18n.getMessage("btnGet") + "</button></div>")
      .join("");
    $("media").querySelectorAll("button").forEach((button) => {
      button.onclick = () => send(found.media[Number(button.dataset.i)].url, "http");
    });
  }
}

/* Kalite listesi SABIT degil: AfuDM'e (yt-dlp) sorup bu adreste GERCEKTEN
   hangi cozunurluklerin oldugunu yazar. Boylece kullanici "1080p" secip
   aslinda 720p inmesiyle karsilasmaz; olmayan kalite listede gorunmez. */
let probeEdilen = "";

const VARSAYILAN_KALITE = [
  { height: "1080", label: "1080p", detail: "" },
  { height: "720", label: "720p", detail: "" },
];

function kaliteleriYaz(qualities) {
  if (!qualities.length) qualities = VARSAYILAN_KALITE;   // bilinmiyorsa eski liste
  const secili = $("quality").value;
  const audio = '<option value="audio">' +
    (chrome.i18n.getMessage("qAudio") || "Sadece ses (mp3)") + "</option>";
  $("quality").innerHTML =
    '<option value="best">' + (chrome.i18n.getMessage("qBest") || "En iyi kalite") + "</option>" +
    qualities.map((q) =>
      '<option value="' + q.height + '">' + q.label + (q.detail ? " · " + q.detail : "") +
      "</option>").join("") + audio;
  if ([...$("quality").options].some((o) => o.value === secili)) $("quality").value = secili;
}

async function kaliteleriGetir(sessiz) {
  const url = $("url").value.trim();
  if (!/^https?:/i.test(url)) {
    if (!sessiz) say(chrome.i18n.getMessage("msgNoUrl"), "bad");
    return;
  }
  probeEdilen = url;
  if (!sessiz) say(chrome.i18n.getMessage("msgProbing"));
  const result = await ask({ type: "probe", url });
  if ($("url").value.trim() !== url) return;   // kullanici adresi degistirdi
  if (!result || !result.ok) {
    if (!sessiz) say(result && result.error ? result.error : chrome.i18n.getMessage("msgNoQualities"), "bad");
    return;
  }
  if (!result.qualities.length) {
    if (!sessiz) say(chrome.i18n.getMessage("msgNoQualities"), "bad");
    return;
  }
  kaliteleriYaz(result.qualities);
  say(chrome.i18n.getMessage("msgQualities", [String(result.qualities.length)]), "ok");
}

async function send(url, kind) {
  if (!url) { say(chrome.i18n.getMessage("msgNoUrl"), "bad"); return; }
  const quality = $("quality").value;
  const result = await ask({
    type: "add",
    payload: {
      url,
      kind,
      quality,
      audio_only: quality === "audio",
    },
  });
  if (result.ok) {
    say(chrome.i18n.getMessage("msgQueued"), "ok");
  } else {
    say(result.error || chrome.i18n.getMessage("msgAddFailed"), "bad");
  }
}

/* Ana anahtar ve konum ANINDA kaydedilir: "Ayarlari kaydet"e basmak
   gerekseydi kullanici uzantiyi kapattim sanip acik birakirdi. */
$("uzantiAcik").onchange = async () => {
  await ask({ type: "save", cfg: { uzantiAcik: $("uzantiAcik").checked } });
  $("kapaliNot").hidden = $("uzantiAcik").checked;
  say(chrome.i18n.getMessage($("uzantiAcik").checked ? "msgUzantiAcildi" : "msgUzantiKapandi"),
      $("uzantiAcik").checked ? "ok" : "");
};

$("panelKonum").onchange = async () => {
  await ask({ type: "save", cfg: { panelKonum: $("panelKonum").value } });
  say(chrome.i18n.getMessage("msgKonumKaydedildi"), "ok");
};

/* Surukleyip birakilan yer hazir konumu EZER: sifirlamadan liste secimi
   gorunmez olurdu. Tek sitenin degil, hepsinin kaydi silinir. */
$("konumSifirla").onclick = async () => {
  await ask({ type: "save", cfg: { panelOzel: {} } });
  say(chrome.i18n.getMessage("msgKonumSifirlandi"), "ok");
};

$("add").onclick = () => send($("url").value.trim(), undefined);
$("probe").onclick = () => kaliteleriGetir(false);
// Adres degisince eski kalite listesi yaniltmasin
$("url").addEventListener("input", () => {
  if (probeEdilen && $("url").value.trim() !== probeEdilen) {
    probeEdilen = "";
    kaliteleriYaz([]);
  }
});
$("save").onclick = async () => {
  await ask({
    type: "save",
    cfg: {
      port: Number($("port").value) || 6811,
      token: $("token").value.trim(),
      minSizeMB: Number($("minSize").value) || 0,
      enabled: $("enabled").checked,
      sendCookies: $("sendCookies").checked,
      videoCatch: $("videoCatch").checked,
      uzantiAcik: $("uzantiAcik").checked,
      panelKonum: $("panelKonum").value,
    },
  });
  say(chrome.i18n.getMessage("msgSaved"), "ok");
  refresh();
};
/* AfuDM'in portu sabit degil (6811 doluysa bir sonrakine gecer): once yazili
   portu, sonra araligi dene. Boylece kullanici port aramak zorunda kalmaz. */
async function pairDene(port) {
  try {
    return await fetch(`http://127.0.0.1:${port}/pair`);
  } catch (_) {
    return null;
  }
}

$("pair").onclick = async () => {
  const yazili = Number($("port").value) || 6811;
  const portlar = [yazili];
  for (let p = 6811; p <= 6820; p++) if (p !== yazili) portlar.push(p);
  const yanitlar = await Promise.all(portlar.map(pairDene));   // hepsi AYNI ANDA
  const i = yanitlar.findIndex(Boolean);
  const port = i === -1 ? yazili : portlar[i];
  const response = yanitlar[i];
  if (!response) {
    say(chrome.i18n.getMessage("notifyNotRunning"), "bad"); // AfuDM kapali / port yanlis
    return;
  }
  $("port").value = port;
  const data = await response.json().catch(() => ({}));
  if (!data.ok) {
    // Sunucunun Turkce metni yerine tarayici dilinde anlat.
    say(response.status === 403 ? chrome.i18n.getMessage("msgPairClosed")
      : chrome.i18n.getMessage("msgNoResponse", [String(response.status)]), "bad");
    return;
  }
  await ask({ type: "save", cfg: { port, token: data.token, enabled: true } });
  say(chrome.i18n.getMessage("msgPaired"), "ok");
  refresh();
};

$("url").addEventListener("keydown", (event) => {
  if (event.key === "Enter") $("add").click();
});

refresh();

/* HTML'deki sabit metinleri tarayici diline gore yaz (Chrome kendisi yapmaz). */
document.querySelectorAll("[data-i18n]").forEach((node) => {
  const text = chrome.i18n.getMessage(node.getAttribute("data-i18n"));
  if (text) node.textContent = text;
});
