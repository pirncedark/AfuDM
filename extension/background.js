/* AfuDM link yakalayici — indirmeyi tarayicidan alir, AfuDM'e devreder.

   Akis:
     1. Tarayici bir indirme baslatinca (downloads.onCreated) AfuDM'e sor.
     2. AfuDM ayakta ve dosya turu bize uygunsa: tarayici indirmesini iptal et,
        isi AfuDM'e ver.
     3. AfuDM kapaliysa hicbir seye dokunma — tarayici kendi isini yapar.
     4. Sayfadaki video/m3u8 istekleri kaydedilir; kullanici sag tik veya
        açılır pencereden "AfuDM ile indir" der.
     5. Giris gerektiren siteler icin tarayicinin O ADRESE gonderecegi cerezler
        ve tarayici kimligi (User-Agent) de yollanir; AfuDM bunlari diske/
        veritabanina yazmaz (core/cerez.py).
*/

const DEFAULTS = {
  enabled: true,
  port: 6811,
  token: "",
  minSizeMB: 1,
  skipExtensions: "html,htm,css,js,json,xml,svg,ico,woff,woff2,txt",
  videoCatch: true,
  sendCookies: true,
};

const mediaByTab = new Map(); // tabId -> [{url, type, ts}]

async function config() {
  const stored = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

function endpoint(cfg, path) {
  return `http://127.0.0.1:${cfg.port}${path}`;
}

async function afudmAlive(cfg) {
  try {
    const response = await fetch(endpoint(cfg, "/ping"), { method: "GET" });
    return response.ok;
  } catch (_) {
    return false;
  }
}

/* Tarayicinin BU adrese gonderecegi cerezler. getAll({url}) alan adi, yol ve
   secure eslesmesini tarayicinin kendisi gibi yapar: baska siteye cerez gitmez. */
async function cookiesFor(cfg, url) {
  if (!cfg.sendCookies || !/^https?:/i.test(url || "")) return [];
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map(({ name, value, domain, path, secure, hostOnly, expirationDate }) =>
      ({ name, value, domain, path, secure, hostOnly, expirationDate }));
  } catch (_) {
    return [];
  }
}

async function sendToAfudm(cfg, body) {
  const payload = { user_agent: navigator.userAgent, ...body };
  if (!payload.cookies) payload.cookies = await cookiesFor(cfg, payload.url);
  const response = await fetch(endpoint(cfg, "/add"), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-AfuDM-Token": cfg.token },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || chrome.i18n.getMessage("msgNoResponse", [String(response.status)]));
  }
  return data;
}

function notify(message, title = "AfuDM") {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon128.png",
    title,
    message,
  });
}

function extensionOf(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    const dot = path.lastIndexOf(".");
    return dot === -1 ? "" : path.slice(dot + 1);
  } catch (_) {
    return "";
  }
}

/* --- 1) Tarayici indirmesini devral --------------------------------- */
chrome.downloads.onCreated.addListener(async (item) => {
  const cfg = await config();
  // Yonlendirmelerden SONRAKI adres: cerezler de bu adrese gore secilir,
  // boylece aria2 yonlendirme zincirinde cerezi baska alana tasimaz.
  const url = item.finalUrl || item.url;
  if (!cfg.enabled || !url || url.startsWith("blob:") || url.startsWith("data:")) {
    return;
  }
  const skip = cfg.skipExtensions.split(",").map((s) => s.trim()).filter(Boolean);
  if (skip.includes(extensionOf(url))) return;
  if (item.fileSize > 0 && item.fileSize < cfg.minSizeMB * 1048576) return;
  if (!(await afudmAlive(cfg))) return; // AfuDM kapali: tarayici devam etsin

  try {
    await sendToAfudm(cfg, {
      url,
      kind: "http",
      filename: item.filename ? item.filename.split(/[\\/]/).pop() : undefined,
      headers: item.referrer ? { Referer: item.referrer } : {},
    });
    chrome.downloads.cancel(item.id, () => chrome.downloads.erase({ id: item.id }));
    notify(chrome.i18n.getMessage("notifyResumed"));
  } catch (error) {
    notify(chrome.i18n.getMessage("notifyHandoffFailed") + error.message);
  }
});

/* --- 2) Sayfadaki medyayi izle ------------------------------------- */
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0) return;
    const url = details.url;
    const isMedia =
      /\.(m3u8|mpd|mp4|webm|mkv|mp3|m4a|flv)(\?|$)/i.test(url) ||
      details.type === "media";
    if (!isMedia) return;
    const list = mediaByTab.get(details.tabId) || [];
    if (!list.some((entry) => entry.url === url)) {
      list.unshift({ url, type: details.type, ts: Date.now() });
      mediaByTab.set(details.tabId, list.slice(0, 25));
    }
  },
  { urls: ["<all_urls>"] }
);
chrome.tabs.onRemoved.addListener((tabId) => mediaByTab.delete(tabId));

/* --- 3) Sag tik menusu -------------------------------------------- */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "afudm-link",
    title: chrome.i18n.getMessage("menuLink"),
    contexts: ["link", "image", "video", "audio"],
  });
  chrome.contextMenus.create({
    id: "afudm-page-video",
    title: chrome.i18n.getMessage("menuPageVideo"),
    contexts: ["page", "video"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const cfg = await config();
  if (!(await afudmAlive(cfg))) {
    notify(chrome.i18n.getMessage("notifyNotRunning"));
    return;
  }
  let target = "";
  let kind;
  if (info.menuItemId === "afudm-link") {
    target = info.linkUrl || info.srcUrl || "";
  } else {
    const media = mediaByTab.get(tab?.id ?? -1) || [];
    target = media.length ? media[0].url : (tab?.url || "");
    kind = media.length ? "http" : "video";
  }
  if (!target) {
    notify(chrome.i18n.getMessage("notifyNoAddress"));
    return;
  }
  try {
    await sendToAfudm(cfg, { url: target, kind, headers: tab?.url ? { Referer: tab.url } : {} });
    notify(chrome.i18n.getMessage("msgQueued"));
  } catch (error) {
    notify(chrome.i18n.getMessage("notifyAddFailed") + error.message);
  }
});

/* --- 4) Acilir pencere istekleri ---------------------------------- */
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    const cfg = await config();
    if (message.type === "status") {
      reply({ alive: await afudmAlive(cfg), cfg });
    } else if (message.type === "media") {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      reply({ media: mediaByTab.get(tab?.id ?? -1) || [], pageUrl: tab?.url || "" });
    } else if (message.type === "add") {
      try {
        reply({ ok: true, result: await sendToAfudm(cfg, message.payload) });
      } catch (error) {
        reply({ ok: false, error: error.message });
      }
    } else if (message.type === "save") {
      await chrome.storage.local.set(message.cfg);
      reply({ ok: true });
    }
  })();
  return true; // asenkron yanit
});
