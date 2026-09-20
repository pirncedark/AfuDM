/* Maestro el sikismasi — izole dunyada document_start'ta calisir.

   MAIN world betigi ile izole icerik betigi arasinda document uzerinden
   kurulan HER kanal, sayfa o ana kadar calismissa gozlenebilir. Guvenligi
   saglayan sey zamanlama (document_start'ta sayfadan once davranmak) ve
   tek-seferlik el sikismadir. Kanal ayrintilari yalniz izole dunyadaki bu
   yuvada tutulur; document_idle'daki content.js ayni yuvadan devralir. */
(() => {
  const YUVA = "__afudmMaestroKanali";
  if (globalThis[YUVA]) return;

  const rastgele = () => {
    const bayt = crypto.getRandomValues(new Uint8Array(24));
    return Array.from(bayt, (b) => b.toString(16).padStart(2, "0")).join("");
  };
  const kanal = Object.freeze({
    veri: `afudm-maestro-veri-${rastgele()}`,
    komut: `afudm-maestro-komut-${rastgele()}`,
    jeton: rastgele(),
  });

  Object.defineProperty(globalThis, YUVA, {
    value: kanal, configurable: false, enumerable: false, writable: false,
  });
  document.dispatchEvent(new CustomEvent("afudm-maestro-baslat", { detail: {
    __afudm: "afudm-maestro", ...kanal,
  }}));
})();
