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


async function config() {
  const stored = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

function endpoint(cfg, path) {
  return `http://127.0.0.1:${cfg.port}${path}`;
}

/* AfuDM'in API portu SABIT DEGIL: 6811 doluysa (onceki calismanin TIME_WAIT
   artigi, ikinci kopya, baska bir program) LocalAPI bir sonraki porta gecer.
   Uzanti kayitli portu kullandigi icin uygulama ACIKKEN "AfuDM kapali" derdi.
   Cozum: kayitli port cevap vermezse araligi tara, bulunani KAYDET. */
const PORT_ILK = 6811;
const PORT_SON = 6820;
// Kapali bir porta baglanti Windows'ta ~2 sn surer: sure sinirlanmazsa ve
// portlar SIRAYLA denense tarama 20 sn'yi bulur ve arayuz "AfuDM kapali" der.
const PING_MS = 1200;

async function ping(port) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/ping`,
      { method: "GET", signal: AbortSignal.timeout(PING_MS) });
    return response.ok;
  } catch (_) {
    return false;
  }
}

/* Butun araligi AYNI ANDA dener, cevap verenlerin en kucugunu secer.

   Yalniz kayitli port AfuDM'in KENDI araligindaysa taranir: kullanici bilerek
   baska bir port yazdiysa (ornegin baska makineye tunel) onun secimi ezilmez. */
async function portTara(cfg) {
  if (cfg.port < PORT_ILK || cfg.port > PORT_SON) return false;
  const portlar = [];
  for (let port = PORT_ILK; port <= PORT_SON; port++) portlar.push(port);
  const sonuc = await Promise.all(portlar.map(ping));
  const bulunan = portlar.find((_, i) => sonuc[i]);
  if (bulunan === undefined) return false;
  cfg.port = bulunan;                                // cagiran hemen kullansin
  await chrome.storage.local.set({ port: bulunan });
  return true;
}

async function afudmAlive(cfg) {
  if (await ping(cfg.port)) return true;
  return portTara(cfg);
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
  /* interactive: AfuDM indirmeyi HEMEN baslatmaz, once kaydetme penceresini
     acar (klasor/ad/kategori secimi). Ayar kapaliysa uygulama yok sayar ve
     dogrudan baslatir; karar AfuDM'in, uzantinin degil. */
  const payload = { user_agent: navigator.userAgent, interactive: true, ...body };
  if (!payload.cookies) payload.cookies = await cookiesFor(cfg, payload.url);
  // Port kaymis olabilir: gondermeden once dogrula (tarama gerekirse cfg.port guncellenir)
  if (!(await ping(cfg.port))) await portTara(cfg);
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
    const sonuc = await sendToAfudm(cfg, {
      url,
      kind: "http",
      filename: item.filename ? item.filename.split(/[\\/]/).pop() : undefined,
      headers: item.referrer ? { Referer: item.referrer } : {},
    });
    chrome.downloads.cancel(item.id, () => chrome.downloads.erase({ id: item.id }));
    notify(chrome.i18n.getMessage(sonuc.pending ? "msgPending" : "notifyResumed"));
  } catch (error) {
    notify(chrome.i18n.getMessage("notifyHandoffFailed") + error.message);
  }
});

/* --- 2) Sayfadaki medyayi izle ------------------------------------- */
/* Yakalananlar chrome.storage.session'da: MV3 service worker ~30 sn bosta
   kalinca KAPANIR, bellekteki liste gider. Kullanici videoyu izleyip dakikalar
   sonra "indir" dediginde adresler hala burada olmali. */
const MEDYA_SINIRI = 40;
// HLS/DASH parcalari ve yan dosyalar: tek basina ise yaramaz
const PARCA = /\.(ts|m4s|aac|vtt|webvtt|srt|key|jpg|jpeg|png|gif|webp)(\?|$)/i;
let yazmaZinciri = Promise.resolve();

function medyaTuru(url, icerikTuru = "") {
  const tur = icerikTuru.toLowerCase();
  if (/mpegurl/.test(tur) || /\.m3u8(\?|$)/i.test(url)) return "hls";
  if (/dash\+xml/.test(tur) || /\.mpd(\?|$)/i.test(url)) return "dash";
  if (/^(video|audio)\//.test(tur) || /\.(mp4|webm|mkv|mp3|m4a|flv|mov)(\?|$)/i.test(url)) return "file";
  return "";
}

async function medyaListesi(tabId) {
  const anahtar = "medya:" + tabId;
  return (await chrome.storage.session.get(anahtar))[anahtar] || [];
}

function medyaKaydet(details, tur, boyut = 0) {
  // Ayni anda gelen istekler birbirinin yazdigini ezmesin: sirayla yaz.
  yazmaZinciri = yazmaZinciri.then(async () => {
    const anahtar = "medya:" + details.tabId;
    const liste = await medyaListesi(details.tabId);
    const mevcut = liste.find((kayit) => kayit.url === details.url);
    if (mevcut) {
      if (boyut && !mevcut.size) mevcut.size = boyut;
    } else {
      liste.unshift({ url: details.url, kind: tur, type: details.type, frameId: details.frameId,
                      size: boyut, ts: Date.now() });
    }
    await chrome.storage.session.set({ [anahtar]: liste.slice(0, MEDYA_SINIRI) });
  }).catch(() => {});
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0 || PARCA.test(details.url)) return;
    const tur = medyaTuru(details.url);
    if (tur) medyaKaydet(details, tur);
  },
  { urls: ["<all_urls>"] }
);

// Uzantisi olmayan adresler (ornegin /playlist?id=3) icerik turunden taninir.
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    if (details.tabId < 0 || PARCA.test(details.url)) return;
    const baslik = (ad) => (details.responseHeaders || [])
      .find((h) => h.name.toLowerCase() === ad)?.value || "";
    const tur = medyaTuru(details.url, baslik("content-type"));
    if (!tur) return;
    // Aralik istegi (206) toplam boyutu Content-Range'de tasir.
    const aralik = baslik("content-range").match(/\/(\d+)$/);
    const boyut = Number(aralik ? aralik[1] : baslik("content-length")) || 0;
    if (tur === "file" && boyut && boyut < 256 * 1024) return; // simge / ses efekti
    medyaKaydet(details, tur, boyut);
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove("medya:" + tabId));
// Sekme yeni sayfaya gecince eski sayfanin medyasi karismasin.
chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) chrome.storage.session.remove("medya:" + details.tabId);
});

/* --- 2b) Kendiliginden eslesme ------------------------------------ */
/* AfuDM'in "Chrome'a ekle" otomasyonu kurulumdan ONCE eslestirme penceresini
   acar; uzanti kurulur kurulmaz anahtari alir, kullanici hicbir sey yapmaz.
   Pencere kapaliysa /pair reddeder (403) — anahtar yalniz o sirada verilir.
   Service worker uyuyabilecegi icin tekrar denemeler chrome.alarms ile. */
const ESLESME_ALARMI = "afudm-eslesme";
const ESLESME_SURESI_MS = 10 * 60 * 1000;

async function kendiligindenEslesme() {
  const cfg = await config();
  if (cfg.token) {
    chrome.alarms.clear(ESLESME_ALARMI);
    return true;
  }
  for (let port = 6811; port <= 6820; port++) {
    try {
      const yanit = await fetch(`http://127.0.0.1:${port}/pair`);
      const veri = await yanit.json();
      if (veri.ok && veri.token) {
        await chrome.storage.local.set({ port, token: veri.token, enabled: true });
        chrome.alarms.clear(ESLESME_ALARMI);
        notify(chrome.i18n.getMessage("msgPaired"));
        return true;
      }
    } catch (_) { /* bu portta AfuDM yok */ }
  }
  const { eslesmeBitis = 0 } = await chrome.storage.local.get("eslesmeBitis");
  if (Date.now() > eslesmeBitis) chrome.alarms.clear(ESLESME_ALARMI);
  return false;
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({ eslesmeBitis: Date.now() + ESLESME_SURESI_MS });
  chrome.alarms.create(ESLESME_ALARMI, { periodInMinutes: 0.5 });
  kendiligindenEslesme();
});
chrome.runtime.onStartup.addListener(() => { kendiligindenEslesme(); });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ESLESME_ALARMI) kendiligindenEslesme();
});

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
    const media = await medyaListesi(tab?.id ?? -1);
    target = media.length ? media[0].url : (tab?.url || "");
    kind = media.length ? "http" : "video";
  }
  if (!target) {
    notify(chrome.i18n.getMessage("notifyNoAddress"));
    return;
  }
  try {
    const sonuc = await sendToAfudm(cfg, { url: target, kind, headers: tab?.url ? { Referer: tab.url } : {} });
    notify(chrome.i18n.getMessage(sonuc.pending ? "msgPending" : "msgQueued"));
  } catch (error) {
    notify(chrome.i18n.getMessage("notifyAddFailed") + error.message);
  }
});

/* --- 4) Video paneli (content.js) --------------------------------- */
function insanBoyut(bayt) {
  if (!bayt) return "";
  const birim = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (bayt >= 1024 && i < birim.length - 1) { bayt /= 1024; i++; }
  return bayt.toFixed(i > 1 ? 1 : 0) + " " + birim[i];
}

function mbps(bit) {
  return bit ? (bit / 1e6).toFixed(bit < 1e7 ? 1 : 0) + " Mbps" : "";
}

/* HLS ana listesi: her kalite bir #EXT-X-STREAM-INF satiri. Tek kalite listesi
   (medya listesi) ise #EXTINF parcalari icerir; o zaman tek secenek vardir. */
function hlsKaliteleri(metin) {
  const kaliteler = new Map(); // yukseklik -> en yuksek bant genisligi
  for (const satir of metin.split(/\r?\n/)) {
    if (!satir.startsWith("#EXT-X-STREAM-INF")) continue;
    const boy = Number((satir.match(/RESOLUTION=\d+x(\d+)/) || [])[1]) || 0;
    const bant = Number((satir.match(/[:,]BANDWIDTH=(\d+)/) || [])[1]) || 0;
    if (boy && bant >= (kaliteler.get(boy) || 0)) kaliteler.set(boy, bant);
  }
  return kaliteler;
}

function dashKaliteleri(metin) {
  const kaliteler = new Map();
  for (const temsil of metin.match(/<Representation\b[^>]*>/g) || []) {
    const boy = Number((temsil.match(/height="(\d+)"/) || [])[1]) || 0;
    const bant = Number((temsil.match(/bandwidth="(\d+)"/) || [])[1]) || 0;
    if (boy && bant >= (kaliteler.get(boy) || 0)) kaliteler.set(boy, bant);
  }
  return kaliteler;
}

/* Yuksekligin yaninda ne oldugu da yazilsin: 2160p/1440p/1080p60 gibi bir ad
   ve yanina bicim + boyut (ya da bant genisligi). Kullanici hangi cozunurlugun
   inecegini SECMEDEN once gormeli. */
const VIDEO_UZANTI = /\.(mp4|webm|mkv|mov|flv|avi|m4v)(\?|$)/i;

function dosyaAdi(url) {
  try {
    return decodeURIComponent(new URL(url).pathname.split("/").pop() || "").slice(0, 40);
  } catch (_) {
    return "";
  }
}

function kaliteAdi(boy, fps) {
  const ad = boy + "p";
  return fps && fps >= 50 ? ad + Math.round(fps) : ad;
}

function kaliteSecenekleri(kaynak, kaliteler, referer) {
  const secenekler = [...kaliteler.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([boy, bilgi]) => {
      // bilgi: sayi (bant genisligi, HLS/DASH) ya da {fps, ext, filesize} (yt-dlp)
      const sayi = typeof bilgi === "number";
      const ayrinti = sayi
        ? mbps(bilgi)
        : [bilgi.ext, insanBoyut(bilgi.filesize)].filter(Boolean).join(" · ");
      return { label: kaliteAdi(boy, sayi ? 0 : bilgi.fps), detail: ayrinti, url: kaynak,
               kind: "video", quality: String(boy), referer };
    });
  secenekler.push({ label: chrome.i18n.getMessage("vpAudio"), detail: "mp3", url: kaynak, kind: "video",
                    quality: "audio", audio_only: true, referer });
  return secenekler;
}

/* yt-dlp format listesini "1080p60 · mp4 · 248 MB" satirlarina indirger:
   her yukseklikten TEK satir, buyukten kucuge. */
function kaliteListesi(info) {
  const enIyi = new Map();
  for (const bicim of info.formats || []) {
    if (!bicim.height || !bicim.vcodec || bicim.vcodec === "none") continue;
    const onceki = enIyi.get(bicim.height);
    if (onceki && onceki.filesize && !bicim.filesize) continue;
    enIyi.set(bicim.height, bicim);
  }
  return [...enIyi.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([boy, bicim]) => ({
      height: boy,
      label: kaliteAdi(boy, bicim.fps),
      detail: [bicim.ext, insanBoyut(bicim.filesize)].filter(Boolean).join(" · "),
    }));
}

async function afudmGet(cfg, yol) {
  const yanit = await fetch(endpoint(cfg, yol), { headers: { "X-AfuDM-Token": cfg.token } });
  const veri = await yanit.json().catch(() => ({}));
  if (!yanit.ok || veri.ok === false) {
    throw new Error(veri.error || chrome.i18n.getMessage("msgNoResponse", [String(yanit.status)]));
  }
  return veri;
}

/* Once videonun oldugu cercevenin istekleri (gomulu oynatici), sonra en yenisi. */
async function siraliMedya(sender) {
  const medya = await medyaListesi(sender.tab?.id ?? -1);
  const ayniCerceve = (m) => (m.frameId === sender.frameId ? 1 : 0);
  return medya.sort((a, b) => ayniCerceve(b) - ayniCerceve(a) || b.ts - a.ts);
}

/* Oynatma listesi metni: once content.js'in oynatici cercevesinden okudugu
   (dogru Referer + cerezler — hotlink korumali siteler service worker'in
   Referer'siz istegini 403 ile reddeder), yoksa service worker kendisi dener. */
async function listeMetni(kayit, metinler) {
  if (metinler && typeof metinler[kayit.url] === "string") return metinler[kayit.url];
  const yanit = await fetch(kayit.url, { credentials: "include" });
  if (!yanit.ok) throw new Error(String(yanit.status));
  return yanit.text();
}

async function videoSecenekleri(cfg, sender, frameUrl, metinler) {
  if (!(await afudmAlive(cfg))) {
    return { ok: false, error: chrome.i18n.getMessage("notifyNotRunning") };
  }
  const referer = frameUrl || sender.url || sender.tab?.url || "";
  const medya = await siraliMedya(sender);

  const secenekler = [];
  let tekKaliteEklendi = false;
  for (const kayit of medya.filter((m) => m.kind === "hls" || m.kind === "dash").slice(0, 6)) {
    try {
      const metin = await listeMetni(kayit, metinler);
      const kaliteler = kayit.kind === "hls" ? hlsKaliteleri(metin) : dashKaliteleri(metin);
      if (kaliteler.size) {
        secenekler.push(...kaliteSecenekleri(kayit.url, kaliteler, referer));
        break; // ana liste bulundu: tek kalite listeleri onun parcasidir
      }
      if (kayit.kind === "hls" && /#EXTINF/.test(metin) && !tekKaliteEklendi) {
        tekKaliteEklendi = true;
        secenekler.push({ label: "HLS", detail: chrome.i18n.getMessage("vpStream"), url: kayit.url,
                          kind: "video", quality: "best", referer });
      }
    } catch (_) { /* erisilemeyen liste: siradakine gec */ }
  }
  const dosyaSecenekleri = [];
  const dosyalar = new Set();
  let videoDosyasiVar = false;
  for (const kayit of medya.filter((m) => m.kind === "file").slice(0, 8)) {
    if (dosyalar.has(kayit.url) || dosyalar.size >= 4) continue;
    dosyalar.add(kayit.url);
    if (VIDEO_UZANTI.test(kayit.url)) videoDosyasiVar = true;
    // Dosya ADI yazilsin: YouTube'da yakalananlarin hepsi ".mp3" oldugu icin
    // eski etiket ("Dosya · MP3") DORT KEZ AYNI gorunuyordu.
    const ad = dosyaAdi(kayit.url);
    dosyaSecenekleri.push({
      label: ad || chrome.i18n.getMessage("vpFile"),
      detail: insanBoyut(kayit.size), url: kayit.url, kind: "http", referer,
      boyut: Number(kayit.size) || 0,
    });
  }

  /* Ham sayfa istekleri COZUNURLUGU SOYLEMEZ. YouTube'da yakalananlar
     arayuzun uyari sesleridir (success.mp3, open.mp3, no_input.mp3...):
     kullanici kalite listesi yerine dort tane ayni "Dosya · MP3" goruyordu.
     Gercek cozunurluk listesi yt-dlp'den gelir — HLS/DASH ana listesi de
     indirilebilir bir VIDEO dosyasi da yoksa sayfayi AfuDM'e sor. */
  if (!secenekler.length && !videoDosyasiVar) {
    const sayfa = sender.tab?.url || referer;
    try {
      const { info } = await afudmGet(cfg, "/probe?url=" + encodeURIComponent(sayfa));
      const kaliteler = new Map();
      for (const bicim of info.formats || []) {
        if (!bicim.height || !bicim.vcodec || bicim.vcodec === "none") continue;
        // Ayni yukseklikten birden cok bicim gelir; boyutu BILINENI yegle.
        const onceki = kaliteler.get(bicim.height);
        if (onceki && onceki.filesize && !bicim.filesize) continue;
        kaliteler.set(bicim.height, { fps: bicim.fps, ext: bicim.ext, filesize: bicim.filesize });
      }
      if (kaliteler.size) secenekler.push(...kaliteSecenekleri(sayfa, kaliteler, referer));
    } catch (_) { /* yt-dlp bu sayfayi bilmiyor: yalniz ham dosyalar kalir */ }
  }
  /* Gercek kalite listesi varken sayfanin kendi ses efektleri (success.mp3,
     open.mp3...) listeyi kirletiyordu: kalite varsa yalniz VIDEO dosyalari ve
     1 MB ustu dosyalar kalir, kucuk arayuz sesleri dusurulur. */
  const KUCUK = 1024 * 1024;
  const temiz = secenekler.length
    ? dosyaSecenekleri.filter((s) => VIDEO_UZANTI.test(s.url) || (s.boyut || 0) >= KUCUK)
    : dosyaSecenekleri;
  return { ok: true, options: [...secenekler, ...temiz] };
}

async function videoIndir(cfg, sender, secenek, frameUrl) {
  if (!secenek || !/^https?:/i.test(secenek.url || "")) {
    return { ok: false, error: chrome.i18n.getMessage("notifyNoAddress") };
  }
  const referer = secenek.referer || frameUrl || sender.tab?.url || "";
  try {
    await sendToAfudm(cfg, {
      url: secenek.url,
      kind: secenek.kind,
      quality: secenek.quality,
      audio_only: !!secenek.audio_only,
      // HLS adresinde yt-dlp anlamli baslik bulamaz ("master"): sekme basligi kullanilir.
      title: secenek.kind === "video" ? (sender.tab?.title || "") : undefined,
      headers: referer ? { Referer: referer } : {},
    });
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

/* --- 5) Acilir pencere istekleri ---------------------------------- */
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    const cfg = await config();
    if (message.type === "status") {
      reply({ alive: await afudmAlive(cfg), cfg });
    } else if (message.type === "media") {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      reply({ media: await medyaListesi(tab?.id ?? -1), pageUrl: tab?.url || "" });
    } else if (message.type === "add") {
      try {
        reply({ ok: true, result: await sendToAfudm(cfg, message.payload) });
      } catch (error) {
        reply({ ok: false, error: error.message });
      }
    } else if (message.type === "probe") {
      // Acilir pencere: bu adreste GERCEKTEN hangi cozunurlukler var?
      if (!(await afudmAlive(cfg))) {
        reply({ ok: false, error: chrome.i18n.getMessage("notifyNotRunning") });
      } else {
        try {
          const { info } = await afudmGet(cfg, "/probe?url=" + encodeURIComponent(message.url));
          reply({ ok: true, qualities: kaliteListesi(info), title: info.title || "" });
        } catch (error) {
          reply({ ok: false, error: error.message });
        }
      }
    } else if (message.type === "videoPlaylists") {
      reply({ playlists: (await siraliMedya(sender))
        .filter((m) => m.kind === "hls" || m.kind === "dash").slice(0, 6).map((m) => m.url) });
    } else if (message.type === "videoOptions") {
      reply(await videoSecenekleri(cfg, sender, message.frameUrl, message.texts));
    } else if (message.type === "videoGrab") {
      reply(await videoIndir(cfg, sender, message.option, message.frameUrl));
    } else if (message.type === "save") {
      await chrome.storage.local.set(message.cfg);
      reply({ ok: true });
    }
  })();
  return true; // asenkron yanit
});
