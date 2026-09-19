/* tests/torrent_yaris_test.mjs
   AfuDM v1.7 Torrent Pro - Torrent RPC yaris durumlari (race condition),
   in-flight kilitleri, gecikmis yanit (stale response) ve pencere kimligi
   (nonce) davranis testleri.
   Ag gerektirmez. ui/app.js'i vm uzerinde calistirarak GERCEK davranisi test eder.
*/

import { readFileSync } from "node:fs";
import vm from "node:vm";

const appJsKod = readFileSync(new URL("../ui/app.js", import.meta.url), "utf8");
const i18nJsKod = readFileSync(new URL("../ui/i18n.js", import.meta.url), "utf8");

class SahteCanvasGradient {
  addColorStop() {}
}

class SahteCanvasCtx {
  setTransform() {}
  clearRect() {}
  beginPath() {}
  moveTo() {}
  lineTo() {}
  stroke() {}
  fill() {}
  closePath() {}
  createLinearGradient() { return new SahteCanvasGradient(); }
}

class SahteElement {
  constructor(id) {
    this.id = id;
    this.textContent = "";
    this.value = "";
    this.style = {};
    this.disabled = false;
    this.innerHTML = "";
    this.clientWidth = 300;
    this.clientHeight = 100;
    this.width = 300;
    this.height = 100;
    this.dataset = {};
    this.classList = {
      _set: new Set(),
      add: (c) => this.classList._set.add(c),
      remove: (c) => this.classList._set.delete(c),
      contains: (c) => this.classList._set.has(c),
    };
    this._attrs = new Map();
    this._listeners = new Map();
  }
  getContext() { return new SahteCanvasCtx(); }
  setAttribute(k, v) { this._attrs.set(k, String(v)); }
  getAttribute(k) { return this._attrs.has(k) ? this._attrs.get(k) : null; }
  removeAttribute(k) { this._attrs.delete(k); }
  addEventListener(event, fn) {
    if (!this._listeners.has(event)) this._listeners.set(event, []);
    this._listeners.get(event).push(fn);
  }
  dispatchEvent(event) {
    const list = this._listeners.get(event.type || event) || [];
    for (const fn of list) fn(event);
  }
  appendChild(child) { return child; }
  closest() { return null; }
}

class SahteMutationObserver {
  constructor(callback) { this.callback = callback; }
  observe() {}
  disconnect() {}
  takeRecords() { return []; }
}

function ortamOlustur(rpcHandler) {
  const elements = new Map();
  function getEl(id) {
    if (!elements.has(id)) {
      elements.set(id, new SahteElement(id));
    }
    return elements.get(id);
  }

  const timers = [];
  const sahteWindow = {
    pywebview: {
      api: new Proxy({}, {
        get: (_target, prop) => (...args) => rpcHandler(prop, ...args)
      })
    },
    setTimeout: (fn, ms, ...args) => {
      const t = setTimeout(fn, ms, ...args);
      timers.push(t);
      return t;
    },
    clearTimeout: (t) => clearTimeout(t),
    setInterval: (fn, ms, ...args) => {
      const t = setInterval(fn, ms, ...args);
      timers.push(t);
      return t;
    },
    clearInterval: (t) => clearInterval(t),
    addEventListener: () => {},
    removeEventListener: () => {},
    devicePixelRatio: 1,
    MutationObserver: SahteMutationObserver,
    Date,
    Math,
    Number,
    String,
    Boolean,
    Array,
    Set,
    Map,
    Promise,
    Error,
    document: {
      getElementById: (id) => getEl(id),
      querySelectorAll: (_sel) => [],
      createElement: (tag) => new SahteElement(tag),
      addEventListener: () => {},
    },
    console: {
      log: () => {},
      error: () => {},
      warn: () => {},
    },
  };
  sahteWindow.window = sahteWindow;
  sahteWindow.document.defaultView = sahteWindow;

  const baglam = vm.createContext(sahteWindow);
  vm.runInContext(i18nJsKod, baglam);
  vm.runInContext(appJsKod, baglam);

  return {
    baglam,
    sahteWindow,
    getEl,
    temizle: () => {
      for (const t of timers) {
        clearTimeout(t);
        clearInterval(t);
      }
    }
  };
}

let toplamHata = 0;
function dogrula(ad, kosul, detay = "") {
  if (kosul) {
    console.log("OK   " + ad);
  } else {
    console.log("HATA " + ad + (detay ? " -> " + detay : ""));
    toplamHata++;
  }
}

console.log("=== Torrent Pro Yaris ve In-Flight Davranis Testleri ===");

// ---------------------------------------------------------------------------
// SENARYO 1: Yavas RPC: dosyalariCek ucarken ikinci cagri yapilir -> ikinci istek UCMAZ (in-flight)
// ---------------------------------------------------------------------------
{
  console.log("\n1) dosyalariCek in-flight engelleme (yavas RPC devam ederken ikinci istek engellenmeli)");
  let rpcCount = 0;
  let rpcResolver = null;

  const { baglam, temizle } = ortamOlustur((method, ...args) => {
    if (method === "torrent_dosyalari") {
      rpcCount++;
      return new Promise((resolve) => {
        rpcResolver = resolve;
      });
    }
    if (method === "torrent_metrikleri") {
      return Promise.resolve({ ok: true, metrikler: {} });
    }
    return Promise.resolve({ ok: true });
  });

  // torrentVeilAc otomatik ilk dosyalariCek cagirir
  const p1 = vm.runInContext("torrentVeilAc('gid_1')", baglam);

  dogrula("Ilk RPC uctu", rpcCount === 1, `rpcCount: ${rpcCount}`);

  // Bekleyelim (state.torTimer kurulmus durumda, ama inFlight=true oldugu icin yeni istek cikmamali)
  await new Promise((r) => setTimeout(r, 20));

  dogrula("RPC yaniti donmeden ikinci torrent_dosyalari istegi ucmadi", rpcCount === 1, `rpcCount: ${rpcCount}`);

  // RPC'yi sonlandiralim
  if (rpcResolver) {
    rpcResolver({
      ok: true,
      gid: "gid_1",
      dosyalar: [{ indeks: 0, ad: "file1.mp4", secili: true }]
    });
  }
  await p1;
  await new Promise((r) => setTimeout(r, 10));

  // Simdi agac hazirlandi, torState.dosyalar yuklendi
  const dosyalar = vm.runInContext("torState.dosyalar", baglam);
  dogrula("RPC tamamlaninca dosyalar basariyla yuklendi", Array.isArray(dosyalar) && dosyalar.length === 1);

  temizle();
}

// ---------------------------------------------------------------------------
// SENARYO 2: RPC HATA atar -> in-flight kilidi SERBEST kalir, sonraki cagri ucabilir (kalici kilit YOK)
// ---------------------------------------------------------------------------
{
  console.log("\n2) RPC hata atinca in-flight kilidinin serbest kalmasi (finally blogu)");
  let rpcCount = 0;
  let hataFirlat = true;

  const { baglam, getEl, temizle } = ortamOlustur((method, ...args) => {
    if (method === "torrent_dosyalari") {
      rpcCount++;
      if (hataFirlat) {
        return Promise.reject(new Error("Aga baglanilamadi"));
      }
      return Promise.resolve({
        ok: true,
        gid: "gid_2",
        dosyalar: [{ indeks: 0, ad: "deneme.mkv", secili: true }]
      });
    }
    return Promise.resolve({ ok: true });
  });

  await vm.runInContext("torrentVeilAc('gid_2')", baglam);
  await new Promise((r) => setTimeout(r, 15));

  dogrula("Ilk cagri hata ile sonlandi ve torErr gosterildi", getEl("torErr").textContent.includes("Aga baglanilamadi"));

  // Simdi hata duzeldi ve yeni bir torrentVeilAc cagrisi yapildi
  hataFirlat = false;
  await vm.runInContext("torrentVeilAc('gid_2')", baglam);
  await new Promise((r) => setTimeout(r, 15));

  dogrula("Hata sonrasi in-flight kilidi kalici kilitlenmedi, yeni RPC gonderildi", rpcCount >= 2, `rpcCount: ${rpcCount}`);
  const dosyalar = vm.runInContext("torState.dosyalar", baglam);
  dogrula("Sonraki cagri basariyla dosyayi yukledi", Array.isArray(dosyalar) && dosyalar.length === 1);

  temizle();
}

// ---------------------------------------------------------------------------
// SENARYO 3: Pencere kapatilir, gecikmis yanit doner -> DOM'a/state'e HIC yazilmaz
// ---------------------------------------------------------------------------
{
  console.log("\n3) Pencere kapatilip gecikmis yanit dondugunde DOM ve state korunumu");
  let rpcResolver = null;

  const { baglam, getEl, temizle } = ortamOlustur((method, ...args) => {
    if (method === "torrent_dosyalari") {
      return new Promise((resolve) => {
        rpcResolver = resolve;
      });
    }
    return Promise.resolve({ ok: true, metrikler: {} });
  });

  // Pencere acildi
  vm.runInContext("torrentVeilAc('gid_yavas')", baglam);
  await new Promise((r) => setTimeout(r, 10));

  // Pencere kapatildi
  vm.runInContext("closeVeil('torrentVeil')", baglam);
  const acikDurum = vm.runInContext("torState.acik", baglam);
  dogrula("closeVeil torrentVeil acik durumunu false yapti", acikDurum === false);

  // Gecikmis RPC yaniti simdi donuyor
  rpcResolver({
    ok: true,
    gid: "gid_yavas",
    dosyalar: [{ indeks: 0, ad: "asla_yazilmamali.iso", secili: true }]
  });

  await new Promise((r) => setTimeout(r, 20));

  const dosyalar = vm.runInContext("torState.dosyalar", baglam);
  dogrula("Kapanan pencerenin gecikmis verisi torState.dosyalar'a yazilmadi", !dosyalar || dosyalar.length === 0, `dosyalar: ${JSON.stringify(dosyalar)}`);
  dogrula("Uygula butonu aktif edilmedi", getEl("torUygula").disabled === true);

  temizle();
}

// ---------------------------------------------------------------------------
// SENARYO 4: Pencere kapatilip AYNI GID ile yeniden acilir, eski pencerenin gecikmis yaniti doner -> yeni pencerenin verisini EZMEZ
// ---------------------------------------------------------------------------
{
  console.log("\n4) AYNI GID ile pencere kapatilip acildiginda eski RPC yanitinin yeni veriyi ezmemesi (nonce korumasi)");
  let rpc1Resolver = null;
  let rpc2Resolver = null;
  let cagrilar = 0;

  const { baglam, getEl, temizle } = ortamOlustur((method, ...args) => {
    if (method === "torrent_dosyalari") {
      cagrilar++;
      if (cagrilar === 1) {
        return new Promise((resolve) => { rpc1Resolver = resolve; });
      } else {
        return new Promise((resolve) => { rpc2Resolver = resolve; });
      }
    }
    return Promise.resolve({ ok: true, metrikler: {} });
  });

  // 1. Acilis: Eski istek yola cikar
  vm.runInContext("torrentVeilAc('gid_ayni')", baglam);
  await new Promise((r) => setTimeout(r, 10));
  const nonce1 = vm.runInContext("torState.nonce", baglam);

  // Kullanici pencereyi kapatir
  vm.runInContext("closeVeil('torrentVeil')", baglam);

  // Kullanici AYNI GID ile pencereyi TEKRAR acar (yeni bir pencere oturumu)
  vm.runInContext("torrentVeilAc('gid_ayni')", baglam);
  await new Promise((r) => setTimeout(r, 10));
  const nonce2 = vm.runInContext("torState.nonce", baglam);

  dogrula("Yeniden acilista nonce artti ve farklilasti", nonce2 > nonce1, `nonce1: ${nonce1}, nonce2: ${nonce2}`);

  // Simdi 2. acilisin taze verisi yanitlansin
  rpc2Resolver({
    ok: true,
    gid: "gid_ayni",
    dosyalar: [{ indeks: 1, ad: "taze_yeni_dosya.mkv", secili: true }]
  });
  await new Promise((r) => setTimeout(r, 20));

  let dosyalar = vm.runInContext("torState.dosyalar", baglam);
  dogrula("Taze dosya yuklendi", dosyalar && dosyalar.length === 1 && dosyalar[0].ad === "taze_yeni_dosya.mkv");

  // Eski pencerenin gecikmis cevabi SIMDI ulasti (eski bayat veri)
  rpc1Resolver({
    ok: true,
    gid: "gid_ayni",
    dosyalar: [{ indeks: 99, ad: "bayat_eski_dosya.avi", secili: true }]
  });
  await new Promise((r) => setTimeout(r, 20));

  // Taze veri ezilmemeli!
  dosyalar = vm.runInContext("torState.dosyalar", baglam);
  const halaTaze = dosyalar && dosyalar.length === 1 && dosyalar[0].ad === "taze_yeni_dosya.mkv";
  dogrula("Eski pencerenin gecikmis yaniti yeni pencerenin verisini EZMEDI", halaTaze, `Mevcut dosyalar: ${JSON.stringify(dosyalar)}`);

  temizle();
}

// ---------------------------------------------------------------------------
// SENARYO 5: torMetrikleriGuncelle icin ayni senaryolar (in-flight, hata, stale response, ayni GID ile acilis)
// ---------------------------------------------------------------------------
{
  console.log("\n5) torMetrikleriGuncelle in-flight, hata ve gecikmis RPC (stale response) korumasi");
  let metrikResolver1 = null;
  let metrikResolver2 = null;
  let metrikCagrisi = 0;

  const { baglam, getEl, temizle } = ortamOlustur((method, ...args) => {
    if (method === "torrent_metrikleri") {
      metrikCagrisi++;
      if (metrikCagrisi === 1) {
        return new Promise((resolve) => { metrikResolver1 = resolve; });
      } else {
        return new Promise((resolve) => { metrikResolver2 = resolve; });
      }
    }
    return Promise.resolve({ ok: true, dosyalar: [] });
  });

  // Pencere acilsin
  vm.runInContext("torrentVeilAc('gid_metrik')", baglam);
  await new Promise((r) => setTimeout(r, 10));

  dogrula("Metrik RPC ilk cagrisi uctu", metrikCagrisi === 1, `metrikCagrisi: ${metrikCagrisi}`);

  // 5.1: Ilk metrik cagrisi havadayken ikinci cagri yapilir -> in-flight kilidi engellemeli
  vm.runInContext("torMetrikleriGuncelle('gid_metrik')", baglam);
  await new Promise((r) => setTimeout(r, 10));
  dogrula("Metrik uctayken ikinci istek gonderilmedi (in-flight korumasi)", metrikCagrisi === 1, `metrikCagrisi: ${metrikCagrisi}`);

  // 5.2: Pencere kapatilir ve ayni GID ile yeniden acilir
  vm.runInContext("closeVeil('torrentVeil')", baglam);

  // NOT: Eger 1. metrik istegi hala havadaysa (inFlight=true) ve closeVeil bu kilidi
  // serbest birakmadiysa veya metrik cagrisi pencere kapatilinca inFlight kaldiysa
  // yeni pencere acilinca metrik cagrisi yapilamaz.
  vm.runInContext("torrentVeilAc('gid_metrik')", baglam);
  await new Promise((r) => setTimeout(r, 10));

  // Ikinci acilisin metrik cagirisi baslamis olmali
  const ikinciCagriUctu = metrikCagrisi >= 2;
  dogrula("Yeniden acilisla 2. metrik cagirisi yapildi", ikinciCagriUctu, `metrikCagrisi: ${metrikCagrisi}`);

  if (ikinciCagriUctu && typeof metrikResolver2 === "function") {
    // Taze yanit gelsin
    metrikResolver2({
      ok: true,
      metrikler: {
        download_speed: 5000000,
        upload_speed: 1000000,
        num_seeders: 42
      }
    });
    await new Promise((r) => setTimeout(r, 20));

    dogrula("Taze metrik ekrana yansidi (seed=42)", getEl("torSeedVal").textContent.includes("42"));

    // Eski bayat metrik yaniti SIMDI donuyor (seed=1 olan bayat yanit)
    metrikResolver1({
      ok: true,
      metrikler: {
        download_speed: 100,
        upload_speed: 50,
        num_seeders: 1
      }
    });
    await new Promise((r) => setTimeout(r, 20));

    // Eski bayat yanit taze metrigi bozmamali
    const tohumSayisiHala42 = getEl("torSeedVal").textContent.includes("42");
    dogrula("Eski oturumun gecikmis metrik yaniti taze metrigi EZMEDI", tohumSayisiHala42, `Mevcut SeedVal: ${getEl("torSeedVal").textContent}`);
  } else {
    dogrula("Taze metrik ekrana yansidi (seed=42)", false, "2. metrik cagrisi ucamadigi icin test edilemedi");
    dogrula("Eski oturumun gecikmis metrik yaniti taze metrigi EZMEDI", false, "2. metrik cagrisi ucamadigi icin test edilemedi");
  }

  // 5.3: Hata durumunda in-flight kilidi serbest kaliyor mu?
  console.log("\n5.3) Metrik RPC hata atinca in-flight kilidinin serbest kalmasi");
  let metrikHataSayaci = 0;
  const ortamHata = ortamOlustur((method, ...args) => {
    if (method === "torrent_metrikleri") {
      metrikHataSayaci++;
      if (metrikHataSayaci === 1) {
        return Promise.reject(new Error("Metrik ag hatasi"));
      }
      return Promise.resolve({
        ok: true,
        metrikler: { num_seeders: 99 }
      });
    }
    return Promise.resolve({ ok: true, dosyalar: [] });
  });

  await ortamHata.baglam.torrentVeilAc('gid_hata_test');
  await new Promise((r) => setTimeout(r, 15));
  dogrula("Ilk metrik cagrisi hata ile sonlandi", metrikHataSayaci === 1);

  // Hata sonrasi in-flight kilidi serbest kalmis olmali, sonraki cagri ucmali
  await ortamHata.baglam.torMetrikleriGuncelle('gid_hata_test');
  await new Promise((r) => setTimeout(r, 15));
  dogrula("Hata sonrasi metrik in-flight serbest kaldi ve 2. cagri basariyla yapildi", metrikHataSayaci === 2, `metrikHataSayaci: ${metrikHataSayaci}`);

  ortamHata.temizle();
  temizle();
}

console.log("\n=======================================================");
if (toplamHata > 0) {
  console.log(`BASARISIZ: ${toplamHata} kontrol dustu!`);
  process.exit(1);
} else {
  console.log("Hepsi gecti");
  process.exit(0);
}
