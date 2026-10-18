# Entegrasyon-1: A/B/C/E toparlama (opencode)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

Codex kotası bitti; A, B, C ve E ekipleri işi yarım bıraktı. Sen derleme, test ve clippy'yi yeşile çekeceksin, ayrıca eksik küçük parçaları tamamlayacaksın.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-engine\ (her şey)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db\ (her şey)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-api\ (her şey)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\queue.rs ve queue\ alt modülleri
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\torrent.rs: aşağıdaki 3. ve 4. maddelerle sınırlı
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_A.md, SONUC_B.md, SONUC_C.md, SONUC_E.md (güncelle ya da yaz)
DOKUNMA: video.rs, butunluk.rs, afudm-extras, app\, afudm-types, afudm-core\src\lib.rs.

## Yapılacaklar (sırayla)
1. 📍 crates\afudm-engine\src\tests.rs:177: `case!("aria2.tellStatus",[...],{"gid":"g"},...)`. Üçüncü argüman ham JSON yazılmış; `json!({"gid":"g"})` yap ve aynı kalıptaki diğer satırları da düzelt. Kontrol: `cargo test -p afudm-engine`.
2. 📍 crates\afudm-api\src\tests.rs:530 ve 538: `limiter.ayarla(..)` çağrılıyor ama crates\afudm-api\src\erisim.rs:380 `impl HizSinirlayici` içinde `ayarla` yok. Python karşılığı P\core\erisim.py'deki hız sınırlayıcının canlı ayar güncellemesi; metodu oradan taşı. Kontrol: `cargo test -p afudm-api`.
3. SÖZLEŞME DEĞİŞTİ (Claude): `ManagerApi::torrent_dosyalari` artık `Result<Json>` dönüyor. Biçim: `{"dosyalar":[...], "hazir_degil":bool, "neden":str, "gid":str}` (Python TorrentDosyaListesi).
   - torrent.rs:519 imzasını ve iki "hazir_degil" dönüşünü (541, 547) buna göre değiştir. Neden metni: "Magnet ustverisi henuz gelmedi; dosya listesi hazir degil."
   - API'de /torrent/dosyalar yanıtını P\api\server.py:599–610'daki gibi kur.
4. Ortak durum ikilenmiş: queue.rs `State` içinde de, torrent.rs `State` içinde de `removed_gids` ve `preview_gids` var. Tek kaynak queue State olsun. torrent.rs'teki kullanımları `m.queue_state` üzerinden yap, torrent State'teki kopyaları kaldır.
5. Proxy: P\core\proxy.py (141 satır) eksik. `crates\afudm-core\src\queue\proxy.rs` olarak taşı. queue.rs ekleme yolunda ve torrent.rs'teki `TODO(proxy)` noktalarında Python'daki gibi uygula.
6. 📍 crates\afudm-core\src\queue\files.rs:195: clippy hatası; düzelt.
7. Şu crate'lerin her biri için `cargo test -p X` ve `cargo clippy -p X --all-targets -- -D warnings` temiz olsun: afudm-engine, afudm-db, afudm-api, afudm-core. afudm-core'da video.rs'in `todo!()` gövdesi başka ekibin işi; onun derlenmesi yeterli.
8. SONUC_A/B/C/E: her biri taşınan fonksiyon listesini (✅/⚠) ve gerçek test çıktısını içersin.

Not: Bu makinede cargo internete erişebiliyor. Ayrı bir CARGO_HOME ya da yerel önbellek KURMA; varsayılanı kullan.
SONUC (genel): C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_FIX1.md, içinde her maddenin gerçek komut çıktısı.
