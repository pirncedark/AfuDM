# SONUC: Ekip D (torrent + video) — KISMI (torrent tamam, video gövdesi bekliyor)

## Durum
- ✅ Torrent tarafı: `todo!()` kalmadı. Python `manager.py` torrent bölümü (1510–2093, torrent dalı 536–845'in torrent kısmı), `trackers.py`, `tracker_saglik.py` Rust'a taşındı.
- ✅ Video: `probe_video` taşındı.
- ⚠ Video: `video_ekle_ic` hâlâ `todo!()`. Bunun için `video/ytdlp.py` 275–831 (VideoJob süreç yöneticisi), `video/mp4mux.py` (611), `video/mp4kutu.py` (127) ve `core/engines.py` yt-dlp/ffmpeg kısmı taşınmalı. Bu oturumda bağlam bütçesi bunu tamamlamaya yetmedi; ayrı bir iş olarak ele alınmalı.
- Notam kaydına yazılmadı (koordinatör tutuyor).

## Yazılan / değiştirilen dosyalar
- `rs\crates\afudm-core\src\torrent.rs` (imzalar sabit; gövdeler dolu)
- `rs\crates\afudm-core\src\torrent\trackers.rs` (trackers.py)
- `rs\crates\afudm-core\src\torrent\saglik.rs` (tracker_saglik.py)
- `rs\crates\afudm-core\src\torrent\bencode.rs` (bencode + .torrent info hash)
- `rs\crates\afudm-core\src\video.rs` (probe_video; video_ekle_ic stub)
- `rs\crates\afudm-core\Cargo.toml`: benim eklediğim `base64.workspace = true`, `sha1 = "0.10"`. Aynı anda eklediğim `rand`/`ureq` satırlarını diğer ekibin satırlarıyla çakıştığı için sildim; onların satırlarına dokunulmadı.
- Dokunulmadı: lib.rs, queue.rs, butunluk.rs, afudm-types.

## Fonksiyon tablosu
| Fonksiyon | Durum |
|---|---|
| torrent_ekle_ic | ✅ (adopt / .torrent / magnet; çıktı `{"gid": ...}`) |
| snapshot_alanlari | ✅ (kapsam varsayımı, aşağıda) |
| seed_bilgi | ✅ |
| tracker_tara | ✅ |
| seed_dosyalari | ✅ |
| seed_dosya_ekle | ✅ |
| seed_dosya_sil | ✅ |
| seed_tazele | ✅ |
| peers | ✅ |
| torrent_on_ekle | ⚠ proxy katmanı yok (aşağıda) |
| torrent_on_iptal | ✅ (removed_gids torrent::State'te; aşağıda) |
| torrent_dosyalari | ⚠ hazir_degil/neden sözleşmede yok (aşağıda) |
| torrent_dosya_secimini_kaydet | ✅ |
| torrent_secimi_ayarla | ✅ |
| torrent_dosya_secimleri | ✅ |
| torrent_metrikleri | ✅ |
| probe_video | ✅ |
| video_ekle_ic | ⚠ `todo!()` (VideoJob portu yok) |

## Testler (gerçek çıktı, gerçek çalışma alanı)
`cargo test -p afudm-core` son satırlar:
```
test torrent::trackers::testler::yerel_ve_yasak_adresler_cikar ... ok
test torrent::trackers::testler::tekrarlar_buyuk_kucuk_harf_duyarsiz_silinir ... ok
test torrent::saglik::testler::dosya_ekle_bos_listeyi_reddeder ... ok
test torrent::saglik::testler::dosya_ekle_ayni_kumeyi_zaten_olarak_bildirir ... ok
test video::testler::entries_yoksa_sifir_ve_playlist_degil ... ok
test video::testler::probe_formatlari_ve_varsayilanlari_cikarir ... ok
test queue::tests::settings_validation_is_all_or_nothing ... ok
test torrent::trackers::testler::birlesik_url_ayrilir_ve_ws_elenir ... ok

test result: ok. 29 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.03s
   Doc-tests afudm_core
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```
Torrent testleri: 13 (bencode 4, trackers 4, saglik 5). Video testleri: 2.

`cargo clippy -p afudm-core -- -D warnings` son satırlar:
```
    Checking ureq v3.4.2
    Checking url v2.5.8
    Checking rand_chacha v0.9.0
    Checking rand v0.9.5
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
error: call to `set_readonly` with argument `false`
   --> crates\afudm-core\src\queue\files.rs:195:17
    = note: `-D clippy::permissions-set-readonly-false` implied by `-D warnings`
error: could not compile `afudm-core` (lib) due to 1 previous error
```
Clippy hatası C ekibinin `queue/files.rs` dosyasında; benim dosyalarımda clippy temiz (torrent ve video için uyarı yok). C'nin dosyasına dokunmadım.

## Sözleşme sorunları / 📍 (Claude'a)
1. **torrent_dosyalari**: Python `TorrentDosyaListesi` `hazir_degil` ve `neden` alanlarını taşıyor; API (`api/server.py` 599–605) bunu okuyor. `afudm-types` sözleşmesi `Result<Vec<Json>>` döndürdüğü için bu bilgi kayboluyor. Şu an "hazır değil" durumunda boş dizi dönülüyor. Çözüm: dönüş tipi genişletilmeli (ör. `{hazir_degil, neden, dosyalar}`) veya trait değiştirilmeli.
2. **Proxy**: Python `_proksi(options)` + `P.aria2_secenekleri` (core/proxy.py) Rust'ta yok. `torrent_on_ekle` ve `torrent_ekle_ic` içinde `TODO(proxy)` olarak işaretli; proxy katmanı taşınınca eklenmeli.
3. **removed_gids / preview_gids**: Python'da `_removed_gids` ve `_preview_gids` Manager'da ortak. Ben bunları `torrent::State` içinde tuttum (pub alanlar). Snapshot tarafında (C ekibi) okunacaksa ya bu state'e erişim fonksiyonu eklenmeli ya da alanlar queue state'ine taşınmalı.
4. **snapshot_alanlari kapsamı (varsayım)**: "seed, peers, metrik" olarak yorumladım. Torrent değilse boş harita, torrent ise `numSeeders, seeder, connections, uploadSpeed, uploadLength, ratio, infoHash, numPieces`. C ekibi farklı bir alan seti bekliyorsa bildirsin.

## Varsayımlar (Python davranışı seçildi, belirsiz noktalar)
- Python `BASE` = `Manager::app_dir`; `DATA` = `Manager::data_dir`. `trackers/` klasörü `app_dir\trackers`, önbellek `data_dir\trackers.txt`.
- yt-dlp yolu: `app_dir\engine\yt-dlp.exe` varsa o, yoksa sistemdeki `yt-dlp` (Python `_bundled_or_system` mantığı). Yerel yardımcı; `afudm-engine::yol` kullanılmadı (crate bağımlılığı eklenmedi).
- `_seed_taramasini_bayatlat`: Python'daki `threading.Thread` yerine `std::thread::spawn`; Manager Arc'lı olmadığı için store/rpc/yollar klonlanıyor.
- Bencode derinlik sınırı 32 (Python `_bencode_oku` ile aynı); `.torrent` info-hash taramasında Python'da derinlik sınırı yok, Rust'ta bu sınır uygulanıyor (çok derin torrent'lerde fark olabilir).
- Yuvarlama: Python `round` yerine `(x*10^n).round()/10^n` (yarım değerlerde küçük fark olabilir).
- IPv4/IPv6 "yerel" sınıflaması Python `ipaddress.is_private/is_reserved` için yaklaşık; kenar aralıklarda fark olabilir.

## C ekibinin dosyasındaki durum (düzeltilmedi)
İlk denemede `queue.rs` derlemeyi durdurdu (E0282, closure tip açıklaması) ve `queue/files.rs` yoktu. Bu sırada doğrulamayı, workspace'in kopyası üzerinde queue.rs'i yamalayarak yaptım (kopya scratchpad'de, gerçek dosyaya dokunulmadı). Sonradan C ekibi dosyayı düzeltti; gerçek çalışma alanında `cargo test -p afudm-core` artık geçiyor. Kalan tek clippy hatası C'nin `queue/files.rs:195` satırında.

## Kalan iş (Ekip D)
1. `video/ytdlp.py` 275–831 → `VideoJob` (süreç, ilerleme ayrıştırma, aria2c, birleştirme) ve `video_ekle_ic`.
2. `video/mp4mux.py` + `video/mp4kutu.py` → MP4 birleştirme (testler: `tests/mux_test.py`, `mux_ayristirma_test.py`, `video_*_test.py`).
3. `core/engines.py` yt-dlp/ffmpeg yolu ve indirme (afudm-engine ile çakışmaması için sahiplik kararı Claude'a).
4. Yukarıdaki sözleşme sorunları (1–3) Claude tarafından kararlaştırılınca proxy ve hazir_degil eklenmeli.
5. `cargo clippy -p afudm-core -- -D warnings` yeşil olması için C'nin `queue/files.rs:195` satırı (C ekibinin işi).
