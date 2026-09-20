/* Maestro'nun MAIN world ve servis calisani arasindaki ortak veri siniri. */
(() => {
  const INDIRME_BASLIK_IZIN = new Set(["range", "content-type", "content-length", "accept"]);
  globalThis.AfuDMMaestroGuvenlik = Object.freeze({
    baslikIzinli(ad) {
      return typeof ad === "string" && INDIRME_BASLIK_IZIN.has(ad.toLowerCase());
    },
  });
})();
