/* MAIN world ve service worker tarafinda ortak medya basligi politikasi.

   TEHDIT MODELI: bu betik MAIN world'de SAYFANIN global nesnesine yazar, yani
   sayfadaki her betik (reklam, ele gecirilmis 3. taraf kutuphane) ona erisebilir.
   Bu yuzden disari SADECE bir fonksiyon verilir ve o fonksiyonun davranisini
   degistirebilecek hicbir yuzey birakilmaz:
     1. Izin listesi kapanis (closure) icinde tutulur — disaridan okunamaz,
        eklenemez. (Nesne ozelligi olsaydi `Object.freeze` onu KORUMAZDI:
        freeze nesneyi dondurur ama icindeki Set'in `add`'ini engellemez.)
     2. Global yuva `writable:false, configurable:false` tanimlanir — aksi halde
        sayfa `globalThis.AfuDMHeaderPolicy = {temizle: c => Object.fromEntries(c)}`
        diyerek suzgeci tumuyle etkisizlestirir ve basliklar yeniden sizar.
   Kara liste DEGIL dar izin listesi kullanilir: kara listede unutulan her
   baslik (x-csrf-token, x-api-key, authorization, ...) sizinti demektir. */
(() => {
  const IZINLI = ["referer", "origin", "user-agent", "accept", "accept-language", "range"];
  const EN_COK = 6;
  const DEGER_SINIRI = 1024;

  function temizle(torba) {
    const temiz = {};
    if (!torba || typeof torba[Symbol.iterator] !== "function") return temiz;
    let sayi = 0;
    for (const [hamAd, deger] of torba) {
      if (sayi >= EN_COK || typeof hamAd !== "string" || typeof deger !== "string") continue;
      const ad = hamAd.toLowerCase();
      // \r\n iceren deger baslik enjeksiyonuna kapi acar: dusur.
      if (!IZINLI.includes(ad) || /[\r\n]/.test(deger)) continue;
      temiz[ad] = deger.slice(0, DEGER_SINIRI);
      sayi++;
    }
    return temiz;
  }

  const politika = Object.freeze({ temizle });
  try {
    Object.defineProperty(globalThis, "AfuDMHeaderPolicy", {
      value: politika,
      writable: false,
      configurable: false,
      enumerable: false,
    });
  } catch (_) {
    // Ozellik zaten tanimliysa (ayni sayfaya iki kez enjeksiyon) dokunma:
    // ilk tanim zaten yazilamaz olandir.
  }
})();
