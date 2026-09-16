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
  $("enabled").checked = status.cfg.enabled;
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

$("add").onclick = () => send($("url").value.trim(), undefined);
$("save").onclick = async () => {
  await ask({
    type: "save",
    cfg: {
      port: Number($("port").value) || 6811,
      token: $("token").value.trim(),
      minSizeMB: Number($("minSize").value) || 0,
      enabled: $("enabled").checked,
    },
  });
  say(chrome.i18n.getMessage("msgSaved"), "ok");
  refresh();
};
$("pair").onclick = async () => {
  const port = Number($("port").value) || 6811;
  let response;
  try {
    response = await fetch(`http://127.0.0.1:${port}/pair`);
  } catch (_) {
    say(chrome.i18n.getMessage("notifyNotRunning"), "bad"); // AfuDM kapali / port yanlis
    return;
  }
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
