/* AfuDM maestro — sayfanin KENDI ortaminda (MAIN world) calisan dinleyici.

   NEDEN: Kalite listesi (HLS .m3u8 / DASH .mpd) oynaticiya BIR KEZ, dogru
   Referer + cerez + imzali adresle gelir. Uzanti o adresi sonradan yeniden
   istediginde (re-fetch) sik sik 403/CORS yiyor ya da imza suresi doluyor.
   Cozum: istegi biz yapmiyoruz — oynaticinin KENDI istegini dinleyip yanit
   GOVDESINI yaninda saklıyoruz. "Yasayan" metin budur.

   Bu betik sayfanin ortaminda calisir, yani sayfa onu gorebilir; bu yuzden:
     - hicbir uzanti API'si (chrome.*) KULLANILMAZ,
     - disari yalniz rastgele adli CustomEvent kanaliyla veri gonderilir,
     - yalniz izin listesindeki medya basliklari aktarilir.

   Yakalananlar content.js'e (izole dunya) ozel olay kanaliyla akar; content.js
   listeleriOku() icinde yeniden indirmek yerine bu metni kullanir.
*/
(() => {
  if (window.__afudmMaestro) return;
  window.__afudmMaestro = true;

  // Politikayi document_start'ta, sayfa betikleri calismadan ONCE sabitle.
  // Cagri aninda globalThis'ten okumak, sayfaya suzgeci degistirme firsati
  // birakir; kapaniste tutulan bu referans onu kapatir.
  const POLITIKA = globalThis.AfuDMHeaderPolicy;

  const IMZA = "afudm-maestro";
  const EN_COK_BAYT = 2 * 1024 * 1024;   // liste govdesi ust siniri (2 MB)
  const LISTE = /\.(m3u8|mpd)(\?|$)/i;
  const LISTE_TURU = /(mpegurl|dash\+xml|vnd\.apple\.mpegurl)/i;
  let kanal = null;

  /* content.js document_idle'da yuklenir; ilk liste ondan ONCE gecebilir.
     Bu yuzden yakalananlar burada da DURUR ve content.js "tazele" dedigi an
     yeniden yayinlanir. Aksi halde ilk acilista panel bos kalirdi. */
  const depo = new Map();                // adres -> {metin, istek, yanit}
  const EN_COK_KAYIT = 12;
  let drmSebebi = "";

  function listeMi(url, icerikTuru) {
    return LISTE.test(url || "") || LISTE_TURU.test(icerikTuru || "");
  }

  function basliklariSuz(cift) {
    // Politika yuklenmediyse basliklari HIC gonderme (guvenli varsayilan).
    return POLITIKA ? POLITIKA.temizle(cift) : {};
  }

  function olayYolla(tur, veri = {}) {
    if (!kanal) return;
    try {
      document.dispatchEvent(new CustomEvent(kanal.veri, {
        detail: { __afudm: IMZA, jeton: kanal.jeton, tur, ...veri },
      }));
    } catch (_) { /* veri klonlanamadi: onemli degil */ }
  }

  function duyur(kayit) {
    olayYolla("liste", kayit);
  }

  function yolla(url, govde, istekBasliklari, yanitBasliklari) {
    if (!govde) return;
    const adres = String(url);
    const kayit = {
      url: adres,
      metin: govde.slice(0, EN_COK_BAYT),
      istek: istekBasliklari || {},
      yanit: yanitBasliklari || {},
    };
    const vardi = depo.has(adres);
    depo.set(adres, kayit);                       // tazesi eskisini ezsin (imza yenilenir)
    while (depo.size > EN_COK_KAYIT) depo.delete(depo.keys().next().value);
    if (!vardi) duyur(kayit);
  }

  function drmBildir(sebep) {
    drmSebebi = String(sebep);
    olayYolla("drm", { sebep: drmSebebi });
  }

  /* content.js yuklenince "tazele" der; o ana kadar birikenler ona akar. */
  function elSikisma(olay) {
    if (kanal) return;
    const veri = olay.detail;
    if (!veri || veri.__afudm !== IMZA || typeof veri.veri !== "string"
        || typeof veri.komut !== "string" || typeof veri.jeton !== "string"
        || veri.jeton.length < 32) return;
    kanal = { veri: veri.veri, komut: veri.komut, jeton: veri.jeton };
    // Ilk gecerli kabulden sonra ikinci bir denemeyi hic gozlemleme.
    document.removeEventListener("afudm-maestro-baslat", elSikisma);
    document.addEventListener(kanal.komut, (komut) => {
      const istek = komut.detail;
      if (!istek || istek.__afudm !== IMZA || istek.jeton !== kanal.jeton
          || istek.tur !== "tazele") return;
      for (const kayit of depo.values()) duyur(kayit);
      if (drmSebebi) olayYolla("drm", { sebep: drmSebebi });
    });
    for (const kayit of depo.values()) duyur(kayit);
  }
  document.addEventListener("afudm-maestro-baslat", elSikisma);

  /* --- fetch ------------------------------------------------------- */
  const asilFetch = window.fetch;
  if (typeof asilFetch === "function") {
    window.fetch = function (girdi, ayar) {
      const sonuc = asilFetch.apply(this, arguments);
      try {
        const adres = typeof girdi === "string" ? girdi
          : (girdi && girdi.url) || String(girdi);
        // Istek basliklari: Request nesnesinde de, init.headers'ta da olabilir.
        const ham = [];
        try {
          const h = (ayar && ayar.headers) || (girdi && girdi.headers);
          if (h) {
            if (typeof h.forEach === "function") h.forEach((d, a) => ham.push([String(a).toLowerCase(), String(d)]));
            else if (Array.isArray(h)) for (const [a, d] of h) ham.push([String(a).toLowerCase(), String(d)]);
            else for (const a of Object.keys(h)) ham.push([a.toLowerCase(), String(h[a])]);
          }
        } catch (_) { /* basliklar okunamadi */ }
        const istek = basliklariSuz(ham);
        return sonuc.then((yanit) => {
          try {
            const tur = yanit.headers && yanit.headers.get("content-type");
            if (yanit.ok && listeMi(adres, tur)) {
              // Yanit AKISTIR: bir kez okunur. Kopyasini biz okuruz ki
              // oynatici kendi yanitini bozulmamis halde alsin.
              const yanitB = basliklariSuz([...(yanit.headers || [])]);
              yanit.clone().text()
                .then((metin) => {
                  /* Uzanti listeyi webRequest'ten gelen ISTEK adresiyle arar;
                     yonlendirme varsa yanit.url ondan farklidir. Ikisini de
                     kaydederiz, yoksa yonlendirilen listeler eslesmez. */
                  yolla(adres, metin, istek, yanitB);
                  if (yanit.url && yanit.url !== adres) yolla(yanit.url, metin, istek, yanitB);
                })
                .catch(() => {});
            }
          } catch (_) { /* yok say */ }
          return yanit;
        });
      } catch (_) {
        return sonuc;
      }
    };
  }

  /* --- XMLHttpRequest ---------------------------------------------- */
  const XHR = window.XMLHttpRequest;
  if (XHR && XHR.prototype) {
    const asilAc = XHR.prototype.open;
    const asilBaslik = XHR.prototype.setRequestHeader;
    const asilGonder = XHR.prototype.send;

    XHR.prototype.open = function (yontem, adres) {
      try {
        this.__afudmUrl = String(adres);
        this.__afudmBaslik = [];
      } catch (_) { /* yok say */ }
      return asilAc.apply(this, arguments);
    };

    XHR.prototype.setRequestHeader = function (ad, deger) {
      try {
        if (Array.isArray(this.__afudmBaslik)) {
          this.__afudmBaslik.push([String(ad).toLowerCase(), String(deger)]);
        }
      } catch (_) { /* yok say */ }
      return asilBaslik.apply(this, arguments);
    };

    XHR.prototype.send = function () {
      try {
        this.addEventListener("load", () => {
          try {
            if (this.status < 200 || this.status >= 300) return;
            const adres = this.responseURL || this.__afudmUrl || "";
            const istekAdresi = this.__afudmUrl || adres;
            const tur = this.getResponseHeader && this.getResponseHeader("content-type");
            if (!listeMi(adres, tur)) return;
            // responseText yalniz "" ve "text" turlerinde okunabilir; arraybuffer
            // gelen oynaticilar icin govdeyi cozeriz (liste her zaman UTF-8 metin).
            let metin = "";
            const rt = this.responseType;
            if (!rt || rt === "text") metin = this.responseText || "";
            else if (rt === "arraybuffer" && this.response) {
              metin = new TextDecoder("utf-8", { fatal: false })
                .decode(new Uint8Array(this.response, 0, Math.min(this.response.byteLength, EN_COK_BAYT)));
            }
            if (!metin) return;
            const yanitB = basliklariSuz(
              (this.getAllResponseHeaders() || "").split(/\r?\n/)
                .map((s) => { const i = s.indexOf(":"); return i < 0 ? ["", ""] : [s.slice(0, i).toLowerCase().trim(), s.slice(i + 1).trim()]; })
            );
            const istekB = basliklariSuz(this.__afudmBaslik || []);
            yolla(adres, metin, istekB, yanitB);
            if (istekAdresi !== adres) yolla(istekAdresi, metin, istekB, yanitB);
          } catch (_) { /* yok say */ }
        });
      } catch (_) { /* yok say */ }
      return asilGonder.apply(this, arguments);
    };
  }

  /* --- DRM (Widevine/PlayReady) ------------------------------------ */
  /* MediaKeys kurulduysa akis SIFRELIDIR: parcalar insin bile oynatilamaz,
     hicbir indirici cozemez. Kullaniciya "bulunamadi" demek yanlis olur —
     "korumali" demek dogrudur. */
  try {
    const asilErisim = navigator.requestMediaKeySystemAccess;
    if (typeof asilErisim === "function") {
      navigator.requestMediaKeySystemAccess = function (sistem) {
        try { drmBildir(String(sistem || "eme")); } catch (_) { /* yok say */ }
        return asilErisim.apply(this, arguments);
      };
    }
    const asilKur = HTMLMediaElement.prototype.setMediaKeys;
    if (typeof asilKur === "function") {
      HTMLMediaElement.prototype.setMediaKeys = function (anahtar) {
        try { if (anahtar) drmBildir((anahtar.keySystem) || "mediakeys"); } catch (_) { /* yok say */ }
        return asilKur.apply(this, arguments);
      };
    }
  } catch (_) { /* EME yok: onemli degil */ }
})();
