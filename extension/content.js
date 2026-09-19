/* AfuDM video paneli — oynayan videonun ustunde "AfuDM ile indir" + kalite secimi.

   Her cercevede calisir (all_frames): gomulu oynaticilar cogunlukla baska bir
   sitenin iframe'indedir ve video istegi O cerceveden gider. Dugme sayfanin
   stillerinden etkilenmesin diye golge DOM icindedir.

   Kaliteleri bu betik BULMAZ: arka plan (background.js) bu sekmede yakaladigi
   HLS/DASH/dosya isteklerinden ya da AfuDM'in yt-dlp yoklamasindan uretir.
*/
(() => {
  if (window.__afudmPanel) return;
  window.__afudmPanel = true;

  const EN_KUCUK_EN = 240;
  const EN_KUCUK_BOY = 135;
  const GIZLEME_MS = 5000;
  const t = (anahtar, ...yer) => chrome.i18n.getMessage(anahtar, yer) || anahtar;

  /* etkin: ANA ANAHTAR (uzantiAcik) ve video dugmesi ayari (videoCatch)
     birlikte. Ikisinden biri kapaliysa dugme hic cizilmez. */
  let etkin = true;
  let konum = "ust-sag";          // hazir konum (bkz. YERLESIM)
  let ozelYer = null;             // kullanicinin surukleyip biraktigi yer {x, y}
  const KAYNAK = location.origin;

  async function ayarlariOku() {
    try {
      const a = await chrome.runtime.sendMessage({ type: "panelAyar", origin: KAYNAK });
      if (!a) return;
      etkin = a.acik !== false;
      konum = a.konum || "ust-sag";
      ozelYer = a.ozel || null;
      if (!etkin) gizle(true); else konumla();
    } catch (_) { /* arka plan uykuda: varsayilanlarla devam */ }
  }
  ayarlariOku();
  chrome.storage.onChanged.addListener((degisen) => {
    if (degisen.videoCatch || degisen.uzantiAcik || degisen.panelKonum || degisen.panelOzel) {
      ayarlariOku();
    }
  });

  let host = null;
  let kok = null;
  let surukleniyor = false;
  let hedefVideo = null;
  let gizlemeZamani = 0;
  let menuAcik = false;

  function kur() {
    host = document.createElement("afudm-panel");
    host.style.cssText = "all:initial;position:fixed;z-index:2147483647;top:0;left:0;display:none;";
    kok = host.attachShadow({ mode: "open" });
    kok.innerHTML = `
      <style>
        :host { all: initial; }
        .kutu { font: 13px/1.3 "Segoe UI", system-ui, sans-serif; color: #e6eaf0; }
        .ana {
          display: inline-flex; align-items: center; gap: 7px; cursor: pointer;
          background: #0f131aee; color: #e6eaf0; border: 1px solid #5b9dff;
          border-radius: 6px; padding: 6px 11px; font: inherit; font-weight: 600;
          box-shadow: 0 4px 16px #0008;
          /* Surukleme: tarayicinin kendi kaydirma/secim jesti araya girmesin */
          touch-action: none; user-select: none; cursor: grab;
        }
        .ana:active { cursor: grabbing; }
        .ana:hover { background: #1c2a3f; }
        .ana svg { width: 14px; height: 14px; stroke: #5b9dff; fill: none; stroke-width: 2; }
        .menu {
          margin-top: 6px; min-width: 210px; max-height: 300px; overflow: auto;
          background: #14181ff5; border: 1px solid #2a3340; border-radius: 6px;
          box-shadow: 0 8px 24px #000a; padding: 4px 0;
        }
        .secenek {
          display: flex; justify-content: space-between; gap: 14px; width: 100%;
          padding: 7px 12px; background: none; border: 0; color: #e6eaf0;
          font: inherit; text-align: left; cursor: pointer;
        }
        .secenek:hover { background: #5b9dff2e; }
        .secenek small { color: #8a97a8; font-variant-numeric: tabular-nums; }
        .bilgi { padding: 8px 12px; color: #8a97a8; }
        .bilgi.iyi { color: #46c98b; }
        .bilgi.kotu { color: #f2678a; }
      </style>
      <div class="kutu">
        <button class="ana" type="button">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0l-5-5m5 5l5-5M4 20h16"/></svg>
          <span>${t("vpDownload")}</span>
        </button>
        <div class="menu" hidden></div>
      </div>`;
    const ana = kok.querySelector(".ana");
    ana.addEventListener("click", (olay) => {
      olay.preventDefault();
      olay.stopPropagation();
      if (surukleBirakildi) { surukleBirakildi = false; return; }  // surukleme sonu, tiklama degil
      menuAcik ? menuyuKapat() : menuyuAc();
    });
    suruklemeyiKur(ana);
    host.addEventListener("mouseenter", () => { gizlemeZamani = 0; });
    host.addEventListener("mouseleave", () => { gizlemeZamani = Date.now() + GIZLEME_MS; });
    yerlestirKok();
  }

  // Tam ekranda yalniz tam ekran ogesinin icindekiler gorunur: panel oraya tasinir.
  function yerlestirKok() {
    const kap = document.fullscreenElement || document.documentElement;
    if (host && host.parentNode !== kap) kap.appendChild(host);
  }

  function menu() { return kok.querySelector(".menu"); }

  function bilgi(metin, tur = "") {
    menu().hidden = false;
    menu().innerHTML = "";
    const satir = document.createElement("div");
    satir.className = "bilgi " + tur;
    satir.textContent = metin;
    menu().appendChild(satir);
  }

  function menuyuKapat() {
    menuAcik = false;
    menu().hidden = true;
    gizlemeZamani = Date.now() + GIZLEME_MS;
  }

  /* Surukleyip birakma: kullanici dugmeyi istedigi yere tasir, yeri SITE
     BAZINDA hatirlanir. Esik olmadan surukleme yapilirsa her tiklama kayma
     sayilir ve menu acilmaz; 4 piksel gecilmeden tiklama tiklamadir. */
  const SURUKLEME_ESIGI = 4;
  let surukleBirakildi = false;

  function suruklemeyiKur(dugme) {
    let bas = null;
    dugme.addEventListener("pointerdown", (olay) => {
      if (olay.button !== 0 || !hedefVideo) return;
      const kutu = host.getBoundingClientRect();
      bas = { x: olay.clientX, y: olay.clientY, ust: kutu.top, sol: kutu.left, tasindi: false };
      dugme.setPointerCapture(olay.pointerId);
    });
    dugme.addEventListener("pointermove", (olay) => {
      if (!bas) return;
      const dx = olay.clientX - bas.x;
      const dy = olay.clientY - bas.y;
      if (!bas.tasindi && Math.abs(dx) + Math.abs(dy) < SURUKLEME_ESIGI) return;
      bas.tasindi = true;
      surukleniyor = true;                       // konumla() araya girmesin
      if (menuAcik) menuyuKapat();
      gizlemeZamani = 0;                         // surukleme sirasinda kaybolmasin
      host.style.top = Math.max(4, bas.ust + dy) + "px";
      host.style.left = Math.max(4, bas.sol + dx) + "px";
    });
    const birak = (olay) => {
      if (!bas) return;
      const tasindi = bas.tasindi;
      bas = null;
      surukleniyor = false;
      if (!tasindi) return;
      surukleBirakildi = true;                   // hemen ardindan gelen click yutulur
      gizlemeZamani = Date.now() + GIZLEME_MS;
      const kutu = hedefVideo && hedefVideo.getBoundingClientRect();
      if (!kutu || !kutu.width || !kutu.height) return;
      const yer = host.getBoundingClientRect();
      ozelYer = { x: (yer.left - kutu.left) / kutu.width,
                  y: (yer.top - kutu.top) / kutu.height };
      chrome.runtime.sendMessage({ type: "panelYer", origin: KAYNAK, x: ozelYer.x, y: ozelYer.y })
        .catch(() => { /* arka plan uykuda: yer bu oturumda gecerli */ });
      if (olay && olay.pointerId !== undefined && dugme.hasPointerCapture(olay.pointerId)) {
        dugme.releasePointerCapture(olay.pointerId);
      }
    };
    dugme.addEventListener("pointerup", birak);
    dugme.addEventListener("pointercancel", birak);
  }

  async function menuyuAc() {
    menuAcik = true;
    gizlemeZamani = 0;
    // Bu videoya MediaKeys kurulduysa akis sifreli: sormaya gerek yok.
    if (hedefVideo && hedefVideo.mediaKeys) { bilgi(t("vpDrm"), "kotu"); return; }
    bilgi(t("vpSearching"));
    let yanit;
    try {
      const { metinler, basliklar } = await listeleriOku();
      yanit = await chrome.runtime.sendMessage({ type: "videoOptions", frameUrl: location.href,
                                                texts: metinler, headers: basliklar });
    } catch (_) {
      yanit = { ok: false, error: t("notifyNotRunning") };
    }
    if (!menuAcik) return;
    if (!yanit || !yanit.ok) {
      bilgi((yanit && yanit.error) || t("vpNone"), "kotu");
      return;
    }
    if (!yanit.options.length) {
      // DRM'li akis hicbir yontemle inmez: sebep bu, "bulunamadi" degil.
      if (drmVar()) { bilgi(t("vpDrm"), "kotu"); return; }
      // Sebep arka plandan gelir; gelmezse eski genel metne duser.
      bilgi(t(yanit.reason || "vpNone"), "kotu");
      return;
    }
    menu().innerHTML = "";
    for (const secenek of yanit.options) {
      const dugme = document.createElement("button");
      dugme.type = "button";
      dugme.className = "secenek";
      const ad = document.createElement("span");
      ad.textContent = secenek.label;
      const ek = document.createElement("small");
      ek.textContent = secenek.detail || "";
      dugme.append(ad, ek);
      dugme.addEventListener("click", (olay) => {
        olay.preventDefault();
        olay.stopPropagation();
        indir(secenek);
      });
      menu().appendChild(dugme);
    }
  }

  /* --- Maestro koprusu (content-maestro.js, MAIN world) --------------
     Oynaticinin KENDI istegiyle gelen liste govdesi burada birikir. Yeniden
     indirmeye (re-fetch) gore farki: CORS yok, Referer/cerez dogru, imzali
     adres henuz gecerli. Sayfa bu mesajlari taklit edebilir; en kotu ihtimalle
     kalite listesi yanlis cikar — hicbir yetki/veri disari verilmez. */
  const MAESTRO = "afudm-maestro";
  const yasayanListeler = new Map();   // adres -> metin
  const listeBasliklari = new Map();   // adres -> oynaticinin gonderdigi basliklar
  let drmSebebi = "";

  addEventListener("message", (olay) => {
    if (olay.source !== window) return;
    const veri = olay.data;
    if (!veri || veri.__afudm !== MAESTRO) return;
    if (veri.tur === "drm") {
      drmSebebi = String(veri.sebep || "drm");
    } else if (veri.tur === "liste" && typeof veri.url === "string"
               && typeof veri.metin === "string") {
      yasayanListeler.set(veri.url, veri.metin.slice(0, 2_000_000));
      if (veri.istek && typeof veri.istek === "object") {
        listeBasliklari.set(veri.url, veri.istek);
      }
      if (yasayanListeler.size > 16) {
        const ilk = yasayanListeler.keys().next().value;
        yasayanListeler.delete(ilk);
        listeBasliklari.delete(ilk);
      }
    }
  });
  // Maestro document_start'ta calisti: biz gelmeden once yakaladiklarini iste.
  postMessage({ __afudm: MAESTRO, tur: "tazele" }, "*");

  /* Sifreli akis (Widevine/PlayReady): video elemanina MediaKeys kurulduysa
     parcalar inse bile oynatilamaz. "Bulunamadi" demek yaniltici olur. */
  function drmVar() {
    if (drmSebebi) return true;
    for (const video of document.querySelectorAll("video")) {
      if (video.mediaKeys) return true;
    }
    return false;
  }

  /* Oynatma listelerinin metni: ONCE maestro'nun sakladigi yasayan govde.
     Yalniz o adreste hic kayit yoksa bu cerceveden yeniden indirmeyi deneriz
     (maestro'dan once yuklenmis oynaticilar, <video src> ile gelen listeler). */
  async function listeleriOku() {
    const metinler = {};
    let adresler = [];
    try {
      ({ playlists: adresler = [] } = await chrome.runtime.sendMessage({ type: "videoPlaylists" }));
    } catch (_) {
      return { metinler, basliklar: {} };
    }
    const basliklar = {};
    await Promise.all(adresler.map(async (adres) => {
      const yasayan = yasayanListeler.get(adres);
      if (typeof yasayan === "string") {
        metinler[adres] = yasayan;
        const bas = listeBasliklari.get(adres);
        if (bas && Object.keys(bas).length) basliklar[adres] = bas;
        return;
      }
      try {
        const yanit = await fetch(adres, { credentials: "include" });
        if (yanit.ok) metinler[adres] = (await yanit.text()).slice(0, 2_000_000);
      } catch (_) { /* arka plan yeniden dener */ }
    }));
    return { metinler, basliklar };
  }

  async function indir(secenek) {
    bilgi(t("vpSending"));
    let yanit;
    try {
      yanit = await chrome.runtime.sendMessage({ type: "videoGrab", option: secenek, frameUrl: location.href });
    } catch (_) {
      yanit = { ok: false, error: t("notifyNotRunning") };
    }
    if (yanit && yanit.ok) {
      bilgi(t("msgQueued"), "iyi");
      setTimeout(menuyuKapat, 1800);
    } else {
      bilgi((yanit && yanit.error) || t("msgAddFailed"), "kotu");
    }
  }

  function yeterliBuyuk(video) {
    const kutu = video.getBoundingClientRect();
    return kutu.width >= EN_KUCUK_EN && kutu.height >= EN_KUCUK_BOY;
  }

  function goster(video) {
    if (!etkin || !yeterliBuyuk(video)) return;
    if (!host) kur();
    hedefVideo = video;
    yerlestirKok();
    host.style.display = "block";
    konumla();
    if (!menuAcik) gizlemeZamani = Date.now() + GIZLEME_MS;
  }

  function gizle(zorla = false) {
    if (!host || (menuAcik && !zorla)) return;
    if (zorla && menuAcik) menuyuKapat();
    host.style.display = "none";
  }

  /* Hazir konumlar. "ust-sag" VARSAYILAN: dugme videonun USTUNDE, disarida
     durur — oynaticinin kendi dugmelerinin (ayarlar, tam ekran, altyazi)
     hicbirini kapatmaz. Digerleri videonun ICINDEKI koseler. */
  const YERLESIM = {
    "ust-sag":  (k, g, y) => [k.top - y - 6, k.right - g],
    "ic-ust-sag": (k, g) => [k.top + 10, k.right - g - 10],
    "ic-ust-sol": (k) => [k.top + 10, k.left + 10],
    "ic-alt-sag": (k, g, y) => [k.bottom - y - 10, k.right - g - 10],
    "ic-alt-sol": (k, g, y) => [k.bottom - y - 10, k.left + 10],
  };

  function konumla() {
    if (!host || !hedefVideo || host.style.display === "none" || surukleniyor) return;
    const kutu = hedefVideo.getBoundingClientRect();
    if (!hedefVideo.isConnected || kutu.width < EN_KUCUK_EN || kutu.bottom < 0 || kutu.top > innerHeight) {
      gizle(true);
      return;
    }
    const olcu = host.getBoundingClientRect();
    const genislik = olcu.width || 150;
    const yukseklik = olcu.height || 30;
    let ust;
    let sol;
    if (ozelYer) {
      // Oranli saklanir: video buyuyup kuculse de dugme ayni yerde kalir.
      ust = kutu.top + ozelYer.y * kutu.height;
      sol = kutu.left + ozelYer.x * kutu.width;
    } else {
      const yerlesim = YERLESIM[konum] || YERLESIM["ust-sag"];
      [ust, sol] = yerlesim(kutu, genislik, yukseklik);
      // Video sayfanin en ustundeyse "ustunde" yer kalmaz: icine al.
      if (konum === "ust-sag" && ust < 4) ust = kutu.top + 10;
    }
    host.style.top = Math.max(4, Math.min(ust, innerHeight - yukseklik - 4)) + "px";
    host.style.left = Math.max(4, Math.min(sol, innerWidth - genislik - 4)) + "px";
  }

  // "play" kabarmaz; yakalama asamasinda belgeye takilan dinleyici tum videolari gorur.
  document.addEventListener("play", (olay) => {
    if (olay.target instanceof HTMLVideoElement) goster(olay.target);
  }, true);
  document.addEventListener("mouseover", (olay) => {
    const video = olay.target instanceof HTMLVideoElement ? olay.target
      : (olay.target.closest && olay.target.closest("video"));
    if (video && (!video.paused || video.currentTime > 0)) goster(video);
  }, true);
  document.addEventListener("fullscreenchange", () => { yerlestirKok(); konumla(); });
  addEventListener("scroll", konumla, true);
  addEventListener("resize", konumla);
  setInterval(() => {
    konumla();
    if (gizlemeZamani && Date.now() > gizlemeZamani) {
      gizlemeZamani = 0;
      gizle();
    }
  }, 400);

  // --- Sayfa ici Toast Bildirimi (dlman v1.9.1 esinlenmesi) ---
  let toastHost = null;
  let toastKok = null;
  let toastZamanlayici = null;

  function toastKur() {
    if (toastHost) return;
    toastHost = document.createElement("afudm-toast");
    toastHost.style.cssText = "all:initial;position:fixed;z-index:2147483647;top:20px;right:20px;pointer-events:none;";
    toastKok = toastHost.attachShadow({ mode: "open" });
    const stil = document.createElement("style");
    stil.textContent = `
      .toast {
        display: flex; align-items: center; gap: 10px;
        background: rgba(15, 23, 42, 0.95);
        color: #f1f5f9; border: 1px solid rgba(59, 130, 246, 0.4);
        border-radius: 10px; padding: 10px 16px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5), 0 8px 10px -6px rgba(0,0,0,0.4);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px; line-height: 1.4;
        opacity: 0; transform: translateY(-12px) scale(0.96);
        transition: opacity 0.25s ease, transform 0.25s ease;
        max-width: 360px; pointer-events: auto; backdrop-filter: blur(8px);
      }
      .toast.acik { opacity: 1; transform: translateY(0) scale(1); }
      .icon {
        width: 24px; height: 24px; flex-shrink: 0;
        background: #2563eb; border-radius: 6px;
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-weight: bold; font-size: 12px;
      }
      .govde { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
      .baslik { font-weight: 600; font-size: 13px; color: #fff; }
      .mesaj { font-size: 12px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px; }
    `;
    const kutu = document.createElement("div");
    kutu.className = "toast";
    const icon = document.createElement("div");
    icon.className = "icon";
    icon.textContent = "A";
    const govde = document.createElement("div");
    govde.className = "govde";
    const baslik = document.createElement("div");
    baslik.className = "baslik";
    baslik.id = "tBaslik";
    baslik.textContent = "AfuDM";
    const mesaj = document.createElement("div");
    mesaj.className = "mesaj";
    mesaj.id = "tMesaj";
    govde.appendChild(baslik);
    govde.appendChild(mesaj);
    kutu.appendChild(icon);
    kutu.appendChild(govde);
    toastKok.appendChild(stil);
    toastKok.appendChild(kutu);
    (document.body || document.documentElement).appendChild(toastHost);
  }

  function toastGoster(baslikMetni, mesajMetni) {
    toastKur();
    if (!toastKok) return;
    const kutu = toastKok.querySelector(".toast");
    const b = toastKok.getElementById("tBaslik");
    const m = toastKok.getElementById("tMesaj");
    if (b) b.textContent = baslikMetni || "AfuDM";
    if (m) m.textContent = mesajMetni || "";
    if (kutu) kutu.classList.add("acik");
    clearTimeout(toastZamanlayici);
    toastZamanlayici = setTimeout(() => {
      if (kutu) kutu.classList.remove("acik");
    }, 3500);
  }

  // --- Secili alandaki baglantilari ayiklama ---
  function seciliBaglantilariBul() {
    const secim = window.getSelection();
    if (!secim || secim.isCollapsed || secim.rangeCount === 0) return [];
    const bulunanlar = new Set();

    try {
      const range = secim.getRangeAt(0);
      const container = range.commonAncestorContainer;
      const parent = container.nodeType === Node.ELEMENT_NODE ? container : container.parentElement;
      if (parent) {
        const linkler = parent.querySelectorAll("a[href]");
        for (const a of linkler) {
          if (secim.containsNode(a, true)) {
            const h = a.href;
            if (h && /^(https?|magnet):/i.test(h)) bulunanlar.add(h);
          }
        }
      }
    } catch (_) {}

    const metin = secim.toString();
    const urlRegex = /(?:https?:\/\/[^\s<>"']+|magnet:\?[^\s<>"']+)/gi;
    let match;
    while ((match = urlRegex.exec(metin)) !== null) {
      bulunanlar.add(match[0]);
    }
    return Array.from(bulunanlar);
  }

  chrome.runtime.onMessage.addListener((msg, sender, reply) => {
    if (msg.type === "afudmToast") {
      toastGoster(msg.baslik, msg.mesaj);
      reply({ ok: true });
    } else if (msg.type === "seciliLinkleriAl") {
      reply({ links: seciliBaglantilariBul() });
    }
  });
  // Betik video zaten oynarken yuklenmis olabilir
  for (const video of document.querySelectorAll("video")) {
    if (!video.paused) goster(video);
  }
})();
