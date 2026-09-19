/* AfuDM telefon arayuzu — service worker (v1.7.5 Mobile & PWA).
 *
 * Iki kural her seyin onunde:
 *   1) ANAHTAR DISKE YAZILMAZ. Adres "?k=<anahtar>" tasir; hem onbellek
 *      anahtari hem de saklanan yanit sorgu dizesinden ARINDIRILIR.
 *   2) API yanitlari (kimlikli JSON) HICBIR ZAMAN onbellege girmez.
 * Onbellege yalnizca kabuk girer: sayfa, ikon, manifest.
 */
const SURUM = "afudm-v1.7.5-1";
const KABUK = `afudm-kabuk-${SURUM}`;
const KABUK_YOLLARI = ["/m", "/ikon.png", "/manifest.webmanifest"];

/* Sorgu dizesi anahtar tasiyabilir: onbellege yalniz pathname ile bakilir. */
function onbellekIstegi(yol) {
  return new Request(new URL(yol, self.location.origin).href);
}

/* Yanitin KENDISI de url alaninda "?k=..." tasir. Govdeyi yeni bir Response'a
   kopyalayip adresi dusuruyoruz; boylece anahtar onbellek dosyasina girmez. */
async function temizKopya(yanit) {
  const govde = await yanit.clone().arrayBuffer();
  return new Response(govde, {
    status: yanit.status,
    statusText: yanit.statusText,
    headers: yanit.headers,
  });
}

self.addEventListener("install", (olay) => {
  olay.waitUntil(
    caches.open(KABUK)
      .then((onbellek) => onbellek.addAll(KABUK_YOLLARI))
      .then(() => self.skipWaiting()),   // yeni surum beklemesin
  );
});

self.addEventListener("activate", (olay) => {
  olay.waitUntil(
    caches.keys().then((anahtarlar) => Promise.all(
      anahtarlar
        .filter((anahtar) => anahtar.startsWith("afudm-kabuk-") && anahtar !== KABUK)
        .map((anahtar) => caches.delete(anahtar)),
    )).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (olay) => {
  if (olay.request.method !== "GET") return;
  const url = new URL(olay.request.url);
  // Kendi kokumuz disi ve kabuk disi her sey (yani tum API) dokunulmadan gecer.
  if (url.origin !== self.location.origin) return;
  if (!KABUK_YOLLARI.includes(url.pathname)) return;

  /* Sayfa AGDAN ONCE denenir: masaustunde AfuDM guncellenince telefon eski
     arayuzde kalmasin. Ag yoksa onbellekteki kabuk doner (cevrimdisi acilis).
     Ikon ve manifest degismiyor, onlar once onbellekten. */
  const agOnce = url.pathname === "/m";

  olay.respondWith((async () => {
    const onbellek = await caches.open(KABUK);
    const anahtar = onbellekIstegi(url.pathname);

    if (!agOnce) {
      const kayitli = await onbellek.match(anahtar);
      if (kayitli) return kayitli;
    }
    try {
      const yanit = await fetch(olay.request);
      if (yanit.ok) await onbellek.put(anahtar, await temizKopya(yanit));
      return yanit;
    } catch (hata) {
      const kayitli = await onbellek.match(anahtar);
      if (kayitli) return kayitli;
      throw hata;
    }
  })());
});
