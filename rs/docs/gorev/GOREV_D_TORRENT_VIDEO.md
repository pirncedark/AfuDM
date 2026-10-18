# Ekip D: Çekirdek-2, Torrent + Video (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\torrent.rs ve torrent\ alt modülleri
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\video.rs ve video\ alt modülleri
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\Cargo.toml: yalnız [dependencies] sonuna satır ekle. C ekibi de ekleyebilir; var olan satırı değiştirme.
- DOKUNMA: lib.rs, queue.rs, butunluk.rs.

## C ekibinin senden beklediği fonksiyonlar (imzalar sabit)
```rust
// torrent.rs: manager.py add() içindeki torrent dalı
pub(crate) fn torrent_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json>;
// video.rs: manager.py add() içindeki video dalı
pub(crate) fn video_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json>;
// torrent.rs: snapshot satırındaki torrent alanları (seed, peers, metrik)
pub(crate) fn snapshot_alanlari(m: &Manager, status: &Json) -> JsonMap;
```
Bunları İLK yaz. Gövdeleri bitmese bile imzalar derlensin, çünkü C ekibi bunları çağıracak.

## Python kaynağı. P = C:\Users\afuuu\Desktop\afuproject\AfuDM
📍 P\core\manager.py add() içindeki torrent ve video dalları (536–845): magnet, .torrent dosyası, torrent_on_ekle akışı.
📍 Seed: seed_bilgi 1510, tracker_tara 1545, seed_dosyalari 1570, seed_dosya_ekle 1594, seed_dosya_sil 1605, seed_tazele 1623.
📍 Torrent: peers 1879, torrent_on_ekle 1899, torrent_on_iptal 1929, torrent_dosyalari 1977, torrent_dosya_secimini_kaydet 2036, torrent_secimi_ayarla 2054, torrent_dosya_secimleri 2090, torrent_metrikleri 2093.
📍 Video:
  - probe_video 846.
  - Video indirme ve birleştirme: yt-dlp / ffmpeg çağrısı (P\core\engines.py). manager.py içinde "mux", "ffmpeg", "yt-dlp" kelimelerini ara.
  - İlgili testler: P\tests\mux_test.py, mux_ayristirma_test.py, video_*_test.py.
📍 P\core\trackers.py (201), P\core\tracker_saglik.py (352).

Motor yolları: afudm-engine'deki `engines::yol(app_dir, "yt-dlp")` fonksiyonunu kullan (A ekibi yazıyor). Henüz yoksa yolu geçici olarak app_dir\engine\yt-dlp.exe diye kendin kur.
Ortak durum: torrent.rs / video.rs içindeki `pub struct State`. removed_hashes C ekibinin State'inde (`m.queue_state`).

## Test
- Sahte Aria2 kullan.
- Karşılık gelen Python testleri: P\tests\torrent_*_test.py, seed_*_test.py, trackerlar_test.py, tracker_saglik_test.py, mux_test.py, video_*_test.py.

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_D.md
