/* content-maestro.js cevrimdisi duman testi: sahte bir sayfa ortami kurar,
   fetch/XHR yamalarinin listeyi yakalayip ozel CustomEvent kanaliyla disari
   verdigini ve DRM bildiriminin gittigini dogrular. Ag GEREKTIRMEZ. */
import { readFileSync } from "node:fs";
import { randomBytes, webcrypto } from "node:crypto";
import vm from "node:vm";

const politikaKodu = readFileSync(new URL("../extension/header-policy.js", import.meta.url), "utf8");
const kod = readFileSync(new URL("../extension/content-maestro.js", import.meta.url), "utf8");
const kanalKodu = readFileSync(new URL("../extension/maestro-kanal.js", import.meta.url), "utf8");
const gelen = [];
const HLS = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720\n720.m3u8\n";
const rastgele = () => randomBytes(24).toString("hex"); // content.js: 24 bayt = 192 bit
const SahteCustomEvent = globalThis.CustomEvent || class CustomEvent {
  constructor(type, init = {}) { this.type = type; this.detail = init.detail; }
};

class SahteBelge {
  constructor() { this.dinleyiciler = new Map(); }
  addEventListener(tur, fn) {
    if (!this.dinleyiciler.has(tur)) this.dinleyiciler.set(tur, new Set());
    this.dinleyiciler.get(tur).add(fn);
  }
  removeEventListener(tur, fn) { this.dinleyiciler.get(tur)?.delete(fn); }
  dispatchEvent(olay) {
    for (const fn of [...(this.dinleyiciler.get(olay.type) || [])]) fn.call(this, olay);
    return true;
  }
}

class SahteBaslik {
  constructor(o) { this.o = o; }
  get(ad) { return this.o[ad.toLowerCase()]; }
  [Symbol.iterator]() { return Object.entries(this.o)[Symbol.iterator](); }
}

function sahteYanit(url, govde, tur) {
  return {
    ok: true, url, headers: new SahteBaslik({ "content-type": tur, "set-cookie": "a=b" }),
    clone() { return { text: async () => govde }; },
  };
}

const belge = new SahteBelge();
const pencere = {
  fetch: async (u) => (/[.]m3u8/.test(u) ? sahteYanit(u, HLS, "application/vnd.apple.mpegurl")
                                        : sahteYanit(u, "PNG", "image/png")),
  XMLHttpRequest: function () {},
  navigator: { requestMediaKeySystemAccess: async () => ({}) },
  TextDecoder,
  crypto: webcrypto,
  document: belge,
  CustomEvent: SahteCustomEvent,
};
pencere.window = pencere;
pencere.XMLHttpRequest.prototype = {
  open() {}, setRequestHeader() {}, send() {}, addEventListener(t, f) { this._yuk = f; },
  getAllResponseHeaders: () => "content-type: application/dash+xml\r\nauthorization: gizli\r\nx-api-key: gizli\r\ncookie: a=b\r\nreferer: https://oynatici.test/\r\n",
  getResponseHeader: (a) => (a.toLowerCase() === "content-type" ? "application/dash+xml" : ""),
};
pencere.HTMLMediaElement = function () {};
pencere.HTMLMediaElement.prototype = { setMediaKeys() {} };

const kap = vm.createContext(pencere);
// Manifest'teki sira: politika MAIN world'e maestro'dan once yuklenir.
vm.runInContext(politikaKodu, kap);
vm.runInContext(kod, kap);
// Manifest sirasi: MAIN world dinleyicisi, sonra izole dunya el sikismasi.
vm.runInContext(kanalKodu, kap);
const { jeton: JETON, veri: VERI_OLAYI, komut: KOMUT_OLAYI } = pencere.__afudmMaestroKanali;

// Sayfa ancak eklentinin document_start el sikismasindan sonra calisabilir.
// Bu sahte deneme kabul edilmemeli ve gercek kanali degistirememeli.
const SAHTE_VERI_OLAYI = `afudm-maestro-veri-${rastgele()}`;
const SAHTE_KOMUT_OLAYI = `afudm-maestro-komut-${rastgele()}`;
let sahteAkis = 0;
belge.addEventListener(SAHTE_VERI_OLAYI, () => { sahteAkis++; });
belge.dispatchEvent(new SahteCustomEvent("afudm-maestro-baslat", { detail: {
  __afudm: "afudm-maestro", veri: SAHTE_VERI_OLAYI, komut: SAHTE_KOMUT_OLAYI, jeton: rastgele(),
}}));

// content.js'in dinleyicisinin testteki karsiligi: yalniz dogru jetonlu veri akar.
belge.addEventListener(VERI_OLAYI, (olay) => {
  const veri = olay.detail;
  if (veri?.__afudm === "afudm-maestro" && veri.jeton === JETON) gelen.push(veri);
});

let hata = 0;
const dogrula = (ad, kosul) => { console.log((kosul ? "OK  " : "HATA") + " " + ad); if (!kosul) hata++; };
dogrula("izole document_start el sikismasi gercek kanali kurdu", !!JETON && !!VERI_OLAYI && !!KOMUT_OLAYI);
dogrula("sayfanin sahte el sikismasi reddedildi", sahteAkis === 0);

// 1) fetch ile gelen m3u8 yakalanmali
await pencere.fetch("https://ornek.test/master.m3u8", { headers: {
  Referer: "https://oynatici.test/", Authorization: "Bearer gizli", "X-Api-Key": "gizli", Cookie: "a=b",
}});
await new Promise((r) => setTimeout(r, 10));
const liste = gelen.find((m) => m.tur === "liste");
dogrula("fetch listesi yakalandi", !!liste);
dogrula("govde tasindi", liste && liste.metin.includes("EXT-X-STREAM-INF"));
dogrula("gizli basliklar disari sizmadi", liste && !["authorization", "x-api-key", "cookie", "set-cookie"].some((ad) => ad in liste.istek || ad in liste.yanit));
dogrula("izinli referer basligi tasindi", liste && liste.istek.referer === "https://oynatici.test/");

// 2) m3u8 olmayan istek yakalanmamali
gelen.length = 0;
await pencere.fetch("https://ornek.test/ikon.png");
await new Promise((r) => setTimeout(r, 10));
dogrula("duz istek yakalanmadi", gelen.length === 0);

// 3) XHR ile .mpd
const xhr = new pencere.XMLHttpRequest();
xhr.open("GET", "https://ornek.test/manifest.mpd");
xhr.setRequestHeader("Referer", "https://oynatici.test/");
xhr.setRequestHeader("Authorization", "Bearer gizli");
xhr.setRequestHeader("X-Api-Key", "gizli");
xhr.setRequestHeader("Cookie", "a=b");
xhr.send();
xhr.status = 200;
xhr.responseType = "";
xhr.responseText = '<MPD><Representation height="1080" bandwidth="500000"/></MPD>';
xhr.responseURL = "https://ornek.test/manifest.mpd";
xhr._yuk();
const mpd = gelen.find((m) => m.tur === "liste" && m.url.endsWith(".mpd"));
dogrula("XHR listesi yakalandi", !!mpd);

// 4) DRM
gelen.length = 0;
await pencere.navigator.requestMediaKeySystemAccess("com.widevine.alpha");
dogrula("DRM bildirildi", gelen.some((m) => m.tur === "drm" && m.sebep.includes("widevine")));

// 5) Kabulden sonraki ikinci el sikisma mevcut kanali degistiremez.
gelen.length = 0;
belge.dispatchEvent(new SahteCustomEvent("afudm-maestro-baslat", { detail: {
  __afudm: "afudm-maestro", veri: SAHTE_VERI_OLAYI, komut: SAHTE_KOMUT_OLAYI, jeton: rastgele(),
}}));
belge.dispatchEvent(new SahteCustomEvent(KOMUT_OLAYI, { detail: {
  __afudm: "afudm-maestro", tur: "tazele", jeton: JETON,
}}));
dogrula("ikinci el sikismasi kanali degistiremedi", sahteAkis === 0 && gelen.some((m) => m.tur === "liste"));

// 6) Yanlis jetonlu komut veya veri, maestro/content kanalinda kabul edilmez.
gelen.length = 0;
belge.dispatchEvent(new SahteCustomEvent(KOMUT_OLAYI, { detail: {
  __afudm: "afudm-maestro", tur: "tazele", jeton: "yanlis-jeton",
}}));
belge.dispatchEvent(new SahteCustomEvent(VERI_OLAYI, { detail: {
  __afudm: "afudm-maestro", tur: "liste", jeton: "yanlis-jeton", url: "https://sahte.test/x.m3u8", metin: "sahte",
}}));
dogrula("yanlis jetonlu tazele ve liste reddedildi", gelen.length === 0);

console.log(hata ? `${hata} KONTROL DUSTU` : "TUM KONTROLLER GECTI");
process.exit(hata ? 1 : 0);
