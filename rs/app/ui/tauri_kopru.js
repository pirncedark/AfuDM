/* AfuDM Tauri koprusu (Ekip F). pywebview'in yerini alir:
   window.pywebview.api.<ad>(...args) -> Tauri "api_call" komutu.
   app.js ve download.js degismeden calisir. Asil P\ui dosyalari bu kopyadan etkilenmez. */
(function () {
  const invoke = (ad, args) =>
    window.__TAURI__.core.invoke("api_call", { name: ad, args: args });
  const api = new Proxy({}, {
    get(_hedef, ad) {
      if (typeof ad !== "string" || ad === "then") return undefined;
      return (...args) => invoke(ad, args);
    },
  });
  window.pywebview = { api: api };

  // Ozel baslik suruklemesi: WebView2 CSS app-region'i desteklemez (style.css .trace).
  // Surukle = .trace uzerinde sol tus; cift tik = buyut/geri al. Dugmeler haric.
  const surukleme_alani = (hedef) =>
    hedef instanceof Element &&
    hedef.closest(".ozel-baslik .trace") &&
    !hedef.closest(".engine, .wc, .wc-edge");
  document.addEventListener("mousedown", (e) => {
    if (e.button === 0 && surukleme_alani(e.target)) invoke("pencere_surukle", []);
  });
  document.addEventListener("dblclick", (e) => {
    if (surukleme_alani(e.target)) invoke("pencere_buyut", []);
  });

  // LinkGrabber: kabuk bekleyen metni window.afudmLinkgrabber ile iletir; sayfa hazir olunca
  // bekleyen varsa teslim edilir (Python window.events.loaded -> sayfa_hazir).
  window.addEventListener("load", () => {
    if (window.__TAURI__ && window.__TAURI__.core) window.__TAURI__.core.invoke("sayfa_hazir");
  });

  // Arayuz pywebviewready olayini bekler; dinleyiciler kurulduktan sonra tetiklenir.
  setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 0);
})();
