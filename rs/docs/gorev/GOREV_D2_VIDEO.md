# Ekip D2: Video indirme + birleştirme (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

Ekip D torrent tarafını bitirdi; video tarafı yarım kaldı. `video_ekle_ic` hâlâ `todo!()`.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\video.rs ve C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\src\video\ alt modülleri
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core\Cargo.toml: yalnız [dependencies] sonuna satır ekle
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_D2.md
DOKUNMA: torrent.rs, queue.rs ve bunların alt modülleri (aynı anda Entegrasyon-1 onlarda çalışıyor), lib.rs, butunluk.rs.

## Python kaynağı
📍 P\core\manager.py add() video dalı (536–845; "video" ve "VideoJob" ara). Kapsam: video iş yönetimi, yt-dlp süreci, ilerleme ayrıştırma, iptal ve durdurma, snapshot'a video satırı verme.
📍 mp4mux, mp4kutu ve video birleştirme kodu: P\core altında "mux" geçen dosyaları ara (grep -rl mux).
📍 Motor yolu: afudm-engine'deki `engines::yol(app_dir, "yt-dlp")` ve `"ffmpeg"` (A ekibinin crate'i; yalnız kullan).
📍 Testler: P\tests\mux_test.py, mux_ayristirma_test.py, video_pro_test.py, video_merger_dosyaadi_test.py, video_yetim_kayit_test.py, video_cerez_test.py, video_ui_test.py, video_debug_duzeltme_test.py.
Snapshot bağlantısı: video satırlarını video.rs içinde `pub(crate) fn video_satirlari(m: &Manager) -> Vec<Json>` olarak hazırla. queue.rs'e bağlamayı ben yapacağım.
Süreçler penceresiz açılsın (CREATE_NO_WINDOW).

## Bitiş
- video.rs içinde `todo!()` kalmasın.
- `cargo test -p afudm-core` ve `cargo clippy -p afudm-core --all-targets -- -D warnings` çıktısını SONUC'a yapıştır. queue/torrent yüzünden kırmızı kalan bir şey varsa senin hatan değil; yaz, düzeltme.
- Soru sorup durma. Belirsiz noktada Python davranışını seç ve not düş.
