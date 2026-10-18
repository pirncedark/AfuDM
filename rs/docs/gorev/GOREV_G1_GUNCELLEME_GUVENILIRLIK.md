# Ekip G1: Güncelleme, güvenilirlik, bütünlük, otomasyon (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\src\g1\ (mod.rs ve alt dosyalar)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\butunluk.rs (3 todo!(): butunluk_tara, butunluk_onar, butunluk_hepsini_tara)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\Cargo.toml ve C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\Cargo.toml: yalnız [dependencies] sonuna satır ekle
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_G1.md
DOKUNMA: extras\src\lib.rs, g2\, h\, core\src\lib.rs, queue*, torrent*, video*.

## Python kaynağı
📍 P\core\guncelleme.py (232). KRİTİK; kullanıcı kuralı: her GitHub sürümü bütün kullanıcılara otomatik güncelleme olarak gider.
   - api.github.com/repos/pirncedark/AfuDM/releases/latest denetimi.
   - Zip + sha256 indirme, doğrulama, uygulama (exe değiştirme + yeniden başlatma).
   - 3.0 exe'si sonraki 3.x sürümlerini aynı yolla güncelleyebilmeli. Zip adı `AfuDM-vX-win64.zip`.
   - P\core\guncelleme.py zip içinde hangi dosyaları bekliyor? SONUC'ta yaz. 2.9.x güncelleyicisi 3.0 zip'ini açabilmeli; 3.0 zip düzeni buna uymak zorunda.
📍 P\core\reliability.py (200): yedek, geri yükleme, tanı, sağlık. Rotalar: /reliability/backup, /reliability/integrity (P\api\server.py'de ara).
📍 P\core\automation.py (95): otomasyon iş kuyruğu (store.automation_*).
📍 Bütünlük: P\core\butunluk.py (218) + P\core\manager.py butunluk_tara 2447, butunluk_onar 2468, butunluk_hepsini_tara 2614 ve yardımcıları → core\src\butunluk.rs.
   - 13 Eki düzeltmesi korunmalı: yanlış "hasarlı blok" alarmı olmasın. İlgili testleri P\tests altında bul.
📍 P\core\chrome_kurulum.py (337): Chrome eklentisi kurulum yardımı.
HTTP rotaları g1::router(ctx) içinde olsun; yanıt biçimi P\api\server.py ile birebir. Kimlik doğrulamayı app katmanı ekler; sen ekleme.
Arayüz (app.py Api) karşılıkları: guncelleme_kontrol, guncelleme_otomatik_ayarla, guncelleme_son_kontrol, guncelleme_indir, guncelleme_durum, guncelleme_uygula, reliability_*. Bunları g1'de `pub fn` olarak ver; F ekibi Tauri komutuna bağlayacak.

## Bitiş
- `cargo test -p afudm-extras` ve `cargo test -p afudm-core` + clippy (-D warnings) çıktısı SONUC'ta olsun.
- Gerçek GitHub'a yalnız OKUMA isteği atabilirsin. İndirme testini yerel sahte sunucuyla yap. Çalışan AfuDM.exe'yi DEĞİŞTİRME.
