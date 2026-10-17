# Ekip C: Çekirdek-1, Kuyruk (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

Amaç: manager.py'nin ekleme, kuyruk, liste ve kontrol kısmı.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\queue.rs (tüm todo!() gövdeleri senin)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\queue\ alt modülleri (models.rs, dosya_adi.rs ...); bunları yaratabilirsin.
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\Cargo.toml: yalnız [dependencies] sonuna satır ekle. D ekibi de ekleme yapabilir; var olan satırı değiştirme.
- DOKUNMA: lib.rs, torrent.rs, video.rs, butunluk.rs.

## Python kaynağı. P\core\manager.py (P = C:\Users\afuuu\Desktop\afuproject\AfuDM)
📍 Ayar ve mod: start 144, stop 169, hiz_limiti_kb 194, apply_settings 204, set_mode 219, baglanti_ayarla 244, update_settings 286, current_download_dir 320.
📍 Kaynak inceleme: detect_kind 325, is_supported_source 336, magnet_infohash 348, gecmis_sources 442, find_duplicate 460, guess_name 503, clean_title 507, is_metadata_only 512.
📍 add_completed_file 519.
📍 add 536–845 (EN KRİTİK):
  - Kopya tespiti, zamanlanmış başlatma, kategori klasörleri.
  - `_removed_hashes.discard` (551) korunmalı; 17 Eki düzeltmesi.
  - Torrent türü için `crate::torrent::torrent_ekle_ic(m, &req)` çağır.
  - Video türü için `crate::video::video_ekle_ic(m, &req)` çağır.
  - Bu iki fonksiyonu D ekibi yazıyor; imzaları `pub(crate) fn xxx_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json>`. Henüz yoksa D'nin dosyasına DOKUNMA; SONUC'ta "bekliyor" yaz.
📍 Kontrol: pause 850, resume 872, remove 886–1047 (silinen torrent hash'i), resolve_item_path 1048, pause_all 1283, resume_all 1297, retry 1321, renew 1343.
📍 snapshot 1695–1878:
  - Satır JSON'u BİREBİR aynı olmalı; arayüz ve eklenti buna bağlı.
  - Silinen hash filtresi (1716 civarı): `infohash in removed and row is None`.
  - Torrent alanları için D'nin `crate::torrent::snapshot_alanlari(m, &status) -> JsonMap` fonksiyonunu çağır.
📍 Diğer: servers 2168, can_release_ui 2192, notify_telegram 2693 ve bunların kullandığı özel yardımcılar (adı _ ile başlayanlar).
📍 P\core\models.py (275): DownloadRequest ayrıştırma ve doğrulama → queue/models.rs. Hata metinleri aynı olsun.
📍 P\core\dosya_adi.py (438) ve P\core\iliskilendir.py: yalnız add'in kullandığı kısımlar.

Ortak durum: queue.rs içindeki `pub struct State`'e alan ekle (removed_hashes vb.). D ekibi removed_hashes'e erişecek; alanı `pub` yap.

## Test
- Sahte Store ve sahte Aria2 (bellek içi) kullan.
- Karşılık gelen Python testleri: P\tests\manager_test.py, torrent_fix_regression_test.py, kuyruk_test.py, orphan_remove_test.py, bulk_and_parent_remove_test.py, dosya_adi_test.py, pending_persistence_test.py.

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_C.md
