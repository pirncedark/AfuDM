/* content-maestro.js cevrimdisi duman testi: sahte bir sayfa ortami kurar,
   fetch/XHR yamalarinin listeyi yakalayip postMessage ile disari verdigini
   ve DRM bildiriminin gittigini dogrular. Ag GEREKTIRMEZ. */
import { readFileSync } from "node:fs";
import vm from "node:vm";

const kod = readFileSync(new URL("../extension/content-maestro.js", import.meta.url), "utf8");
const gelen = [];
const HLS = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720\n720.m3u8\n";

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

const pencere = {
  fetch: async (u) => (/[.]m3u8/.test(u) ? sahteYanit(u, HLS, "application/vnd.apple.mpegurl")
                                        : sahteYanit(u, "PNG", "image/png")),
  postMessage(veri) { gelen.push(veri); },
  addEventListener(tur, fn) { if (tur === "message") this._dinleyici = fn; },  // testte baglam icinden cagrilir
  XMLHttpRequest: function () {},
  navigator: { requestMediaKeySystemAccess: async () => ({}) },
  TextDecoder,
};
pencere.window = pencere;
pencere.XMLHttpRequest.prototype = {
  open() {}, setRequestHeader() {}, send() {}, addEventListener(t, f) { this._yuk = f; },
  getAllResponseHeaders: () => "content-type: application/dash+xml\r\nauthorization: gizli\r\n",
  getResponseHeader: (a) => (a.toLowerCase() === "content-type" ? "application/dash+xml" : ""),
};
pencere.HTMLMediaElement = function () {};
pencere.HTMLMediaElement.prototype = { setMediaKeys() {} };

const kap = vm.createContext(pencere);
vm.runInContext(kod, kap);

let hata = 0;
const dogrula = (ad, kosul) => { console.log((kosul ? "OK  " : "HATA") + " " + ad); if (!kosul) hata++; };

// 1) fetch ile gelen m3u8 yakalanmali
await pencere.fetch("https://ornek.test/master.m3u8");
await new Promise((r) => setTimeout(r, 10));
const liste = gelen.find((m) => m.tur === "liste");
dogrula("fetch listesi yakalandi", !!liste);
dogrula("govde tasindi", liste && liste.metin.includes("EXT-X-STREAM-INF"));
dogrula("set-cookie yanit basliklarindan elendi", liste && !("set-cookie" in liste.yanit));

// 2) m3u8 olmayan istek yakalanmamali
gelen.length = 0;
await pencere.fetch("https://ornek.test/ikon.png");
await new Promise((r) => setTimeout(r, 10));
dogrula("duz istek yakalanmadi", gelen.length === 0);

// 3) XHR ile .mpd
const xhr = new pencere.XMLHttpRequest();
xhr.open("GET", "https://ornek.test/manifest.mpd");
xhr.setRequestHeader("X-Imza", "abc");
xhr.setRequestHeader("Authorization", "Bearer gizli");
xhr.send();
xhr.status = 200;
xhr.responseType = "";
xhr.responseText = '<MPD><Representation height="1080" bandwidth="500000"/></MPD>';
xhr.responseURL = "https://ornek.test/manifest.mpd";
xhr._yuk();
const mpd = gelen.find((m) => m.tur === "liste" && m.url.endsWith(".mpd"));
dogrula("XHR listesi yakalandi", !!mpd);
dogrula("oynatici basligi tasindi", mpd && mpd.istek["x-imza"] === "abc");
dogrula("Authorization elendi", mpd && !("authorization" in mpd.istek));

// 4) DRM
gelen.length = 0;
await pencere.navigator.requestMediaKeySystemAccess("com.widevine.alpha");
dogrula("DRM bildirildi", gelen.some((m) => m.tur === "drm" && m.sebep.includes("widevine")));

// 5) tazele: content.js gec yuklenirse birikenler yeniden yayinlanir
gelen.length = 0;
// Mesaj, vm BAGLAMININ icinden atilmali: maestro olay.source === window
// karsilastirmasi yapiyor, disaridaki nesne kimligi ayni degil.
vm.runInContext('_dinleyici({ source: window, data: { __afudm: "afudm-maestro", tur: "tazele" } })', kap);
dogrula("tazele birikenleri yeniden yayinladi", gelen.filter((m) => m.tur === "liste").length >= 2);
dogrula("tazele DRM durumunu da yineledi", gelen.some((m) => m.tur === "drm"));

console.log(hata ? `${hata} KONTROL DUSTU` : "TUM KONTROLLER GECTI");
process.exit(hata ? 1 : 0);

