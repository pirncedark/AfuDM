# Entegrasyon-2: video, tamamlanma zinciri, bütünlük bağlantısı (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- crates\afudm-core\src\queue.rs ve queue\ alt modülleri
- crates\afudm-core\src\video.rs ve video\ alt modülleri (yalnız bağlantı için gereken küçük değişiklik)
- crates\afudm-core\src\butunluk.rs (yalnız bağlantı)
- crates\afudm-extras\src\g1\ (yalnız 4. madde)
- docs\sonuc\SONUC_FIX2.md
DOKUNMA: app\ (Ekip F çalışıyor), afudm-types, afudm-core\src\lib.rs, afudm-api, afudm-engine, afudm-db.

## Yapılacaklar
1. Video bağlantısı (docs\sonuc\SONUC_D2.md "açık kalanlar"). queue.rs'te Python manager.py'nin video çağırdığı her yere bağla:
   - pause → video::durdur
   - remove → video::kaldir
   - pause_all → video::tumunu_durdur
   - snapshot → video::video_satirlari (satırları Python'daki sırayla ekle)
   - start → video::yetimleri_duzelt
   - hız/aktif sayısı → video::aktif_sayisi, video::hiz_toplami
   Python'da her çağrının yerini bul (manager.py içinde "_video" ara).
2. Tamamlanma zinciri: Python manager._on_complete (P\core\manager.py:2628) ve çağrıldığı yerler (843 video, 2358 aria2).
   - Rust'ta `pub(crate) fn tamamlandi(m:&Manager, title:&str, size:u64, gid:&str)` yaz (queue.rs).
   - İçinde Python'daki sırayla: bütünlük denetimi (crate::butunluk), Telegram bildirimi (notify_telegram), UI bildirimi (m.ui.notify).
   - En sonda `m.tamamlandi_kancalari` içindeki her kancayı `{"title","size","gid"}` ile çağır. Otomasyon buraya kabuktan bağlanır; core extras'a bağımlı OLMASIN.
   - aria2 tamamlanmasını Python hangi döngüde yakalıyorsa (2358 civarı) Rust'ta da aynı yerde yakala; video işi bitince de çağır.
3. aria2c IPv6 bayrağı ve sistem proxy yedeği (SONUC_D2 madde 3). Python'da netcheck.py ve proxy.py var; proxy queue\proxy.rs'e taşındı. Video tarafında (yt-dlp argümanları) aynı proxy ve IPv6 kararını kullan.
4. G1 eksiği: reliability diagnostics içindeki "engines" anahtarı. afudm-engine `engines::durum(app_dir)` var; g1 diagnostics_preview / export'a ekle. (afudm-extras Cargo.toml'a afudm-engine zaten ekli; değilse [dependencies] sonuna ekle.)
5. Testler: her bağlantı için en az bir sahte Aria2 / Store testi. Kontrol: `cargo test -p afudm-core -p afudm-extras` ve `cargo clippy -p afudm-core -p afudm-extras --all-targets -- -D warnings` yeşil.

Soru sorup durma; belirsizlikte Python davranışını seç ve not düş.
SONUC: docs\sonuc\SONUC_FIX2.md, gerçek cargo çıktısıyla.
