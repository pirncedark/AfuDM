# SONUC D2 — Video (indirme + birlestirme)

Ekip: D2 (video). Gorev: docs/gorev/GOREV_D2_VIDEO.md.
Durum: video.rs ve video/ altindaki tum `todo!()` govdeleri dolu. Kalan `todo!()` yok.

## Yazilan dosyalar
- `crates/afudm-core/src/video.rs` (yeniden yazildi; probe kodu korundu)
- `crates/afudm-core/src/video/mp4mux.rs` (MP4 okuma/birlestirme, mp4mux.py)
- `crates/afudm-core/src/video/is.rs` (VideoJob: komut, surec, pompa, iptal, kayit sekli)
- `crates/afudm-core/src/video/secim.rs` (format secimi, guvenli_ad, birlesik_dosya_bul, arac yollari)
- `crates/afudm-core/src/video/ilerleme.rs` (aria2/yt-dlp cikti ayristirma, yedek_karari)
- `crates/afudm-core/src/video/hata.rs` (kullaniciya giden hata metinleri, dil secimi)
- `crates/afudm-core/src/video/cerez.rs` (cerez dogrulama, Netscape dosyasi)
- `docs/sonuc/SONUC_D2.md` (bu dosya)
- `crates/afudm-core/Cargo.toml`: BU EKIP DEGISTIRMEDI. Yeni bagimlilik gerekmedi (regex, rand, log, serde_json zaten var). Dosyadaki `afudm-db` ve `winreg` eklerini baska bir ajan koymus.

## Sozlesme (C ekibinin baglamasi gereken noktalar)
- `queue::launch` -> `crate::video::video_ekle_ic(m, &req)` ZATEN cagiriyor; donus `Json::String("yt:<n>")`, C'nin `as_str()` okumasiyla uyumlu.
- Asagidaki `pub(crate)` fonksiyonlar hazir, C henuz cagirmiyor (bu yuzden `#[allow(dead_code)]` var). Baglanmasi gerekenler:
  - `video::durdur(m, gid) -> bool`: queue::pause icinde `gid.starts_with("yt:")` dalinda.
  - `video::kaldir(m, gid) -> Option<PathBuf>`: queue::remove yt dalinda; donen yolu C silsin (delete_files ise).
  - `video::tumunu_durdur(m)`: queue::pause_all yt dalinda.
  - `video::video_satirlari(m) -> Vec<Json>`: snapshot'a video satirlari.
  - `video::aktif_sayisi(m)`, `video::hiz_toplami(m)`: idle kontrolu ve istatistik.
  - `video::yetimleri_duzelt(m) -> Result<()>`: acilista (Python __init__ -> _recover_orphan_video_jobs).
  - resume (yt): Python `_launch(row)` yolu; C'nin launch'i video_ekle_ic'i cagirdigi icin ek fonksiyon gerekmez.
- `video::video_ekle_ic` icin `req["options"]` nesnesi okunur (C'nin gonderdigi sekil). Cerez: `req["cookies"]`.

## Python fonksiyon listesi (✅ tamam / ⚠ eksik + neden)

### video/ytdlp.py
- ✅ CREATE_NO_WINDOW -> `is.rs` / `video.rs` (creation_flags 0x08000000)
- ✅ PROGRESS_TAG / PROGRESS_TEMPLATE -> `ilerleme.rs`
- ✅ QUALITY_FORMATS, COMBINED_FORMATS, _KENDI_MUX -> `secim.rs`
- ✅ format_secimi -> `secim::format_secimi`
- ✅ guvenli_ad -> `secim::guvenli_ad`
- ✅ birlesik_dosya_bul -> `secim::birlesik_dosya_bul`
- ✅ ffmpeg_hazir / ffmpeg_dir -> `secim::ffmpeg_yolu` (engine\ffmpeg.exe, yoksa PATH)
- ✅ ytdlp_path -> `video::ytdlp_yolu` (kurali mevcuttu)
- ⚠ available() / version(): Rust tarafinda cagiran yok; port edilmedi. C/F ihtiyac duyarsa eklenir.
- ✅ is_video_site -> `secim::is_video_site` (C'nin tur tespiti icin; su an cagiran yok, allow var)
- ✅ probe / probe_sonucu -> `video::probe_video`, `video::probe_sonucu` (onceden vardi)
- ✅ _HATA_CUMLERI, _HATA_VARSILAN, anlasilir_hata, kullanici_hata -> `hata.rs`, `is.rs`
- ✅ VideoJob.build_cmd -> `is::VideoJob::komut` (tum bayraklar; Video Pro alanlari dahil)
- ✅ VideoJob.start -> `is::baslat`
- ✅ _DEST_RE, _ARIA_RE, _UNITS, _bytes, _eta_seconds -> `ilerleme.rs`
- ✅ _parse_aria, _parse_progress, _num -> `ilerleme.rs` + `is.rs` (uygulama)
- ✅ _hedef_satirini_isle -> `is::VideoJob::hedef_satirini_isle`
- ✅ _akisi_oku (stdout+stderr birlesik, \r ve \n ile satir bolme, tail 30) -> `is::akisi_oku`
- ✅ _pump (yedek deneme aria2c / cerezsiz, hata metni) -> `is::pump`
- ✅ yedek_karari -> `ilerleme::yedek_karari`
- ✅ _dis_indirici_vardi -> `ortam.aria2c.is_some()`
- ✅ _birlesik_dosya_kontrol -> `VideoJob::birlesik_dosya_kontrol`
- ✅ _kendi_birlestir (ffmpegsiz iki parca birlestirme; atomik gecici dosya; numarali ad) -> `is::kendi_birlestir`
- ✅ stop -> `is::durdur` (taskkill /T /F ile agac)
- ✅ display_title, to_dict -> `VideoJob::display_title`, `VideoJob::satir`
- ⚠ _proksi (proxy): `_proksi` tam port edilmedi. Yalniz is icin acik proxy (options.proxy; kural motoru zaten global proxy'yi oraya yaziyor) kullaniliyor. SISTEM proxy yedegi yok.
- ⚠ aria2c IPv6 kapatma (`netcheck.aria2_ipv6_args`): Rust'ta karsiligi yok (afudm-engine icinde private `ipv6_usable`, afudm-core bagimli degil). Sonuc: IPv6 yokken aria2c AAAA denemesi yapabilir. Ekip G/A ile ortak fonksiyon cikarilmali.
- ⚠ aria2c proxy argumani: P.parcala/komut_secenekleri Rust'ta yok; `is::proxy_ayrimi` basit ayiriciyla yapiyor (tip://kullanici:sifre@adres). Kenar durumlar (ozel karakterli sifre) dogrulanmadi.

### video/mp4mux.py
- ✅ izi_oku (duz + parcali MP4, mvex/trex, co64, ctts/stss/elst), birlestir -> `mp4mux.rs`
- ✅ tum yazici (stts/ctts/stss/stsc/stsz/stco/co64, tkhd/mdhd/hdlr/vmhd/smhd/dinf/elst, mvhd/moov, ftyp, mdat 32/64 bit)

### video/mp4kutu.py
- ⚠ PORT EDILMEDI. Hicbir Python modulu import etmiyor (`grep -rn mp4kutu` bos). Arastirma amacli salt-okur bir kutu okuyucu; birlestirmenin kullandigi okuyucu mp4mux.izi_oku (Rust'ta karsiligi var).

### core/manager.py (video dali)
- ✅ add() video dali (options eslemesi) -> `video::video_ekle_ic` (C'nin queue::add/launch'i tarafindan cagrilir; rules/cerez isi C'de)
- ✅ _launch_video -> `video_ekle_ic` (yt:<n> sayaci: store.max_video_seq ile baslar)
- ✅ _on_video_update -> `video::gozlemci` (store.update_by_gid; tamamlanmada bir kez bildirim)
- ✅ probe_video -> `video::probe_video`
- ✅ pause (yt dali) -> `video::durdur`
- ✅ remove (yt dali, dosya yolu) -> `video::kaldir` (yol kacisi kontrolu ile)
- ✅ pause_all (yt dali) -> `video::tumunu_durdur`
- ⚠ resume (yt dali): kendi kodu yok; C'nin launch'i `video_ekle_ic`'i cagirarak karsilar (Python `_launch(row)` ile ayni).
- ✅ _recover_orphan_video_jobs -> `video::yetimleri_duzelt` (cagiran yok, C baglayacak)
- ✅ snapshot/video satirlari -> `video::video_satirlari`; idle/istatistik -> `aktif_sayisi`, `hiz_toplami`
- ⚠ _on_complete: YALNIZ loglama + Windows bildirimi (ui.notify) portlandi. EKSIK: butunluk_tara (bozuk indirme kontrolu), automation.enqueue_download, Telegram bildirimi. Bunlar C/G ekiplerinin fonksiyonlari; C baglayacak.
- ⚠ resolve_item_path yt dali (manager 1098): video isinin dosya yolunu veren yardimci yok. C'nin cozunurlemesi icin `video::kaldir`'a benzer bir `dosya_yolu(m, gid)` eklenebilir; su an eklenmedi.
- ⚠ _cerez_birak / _cerezler bellek sozlugu: cerez bilgisi C'nin `state.cookies` icinde; video tarafi cerez dosyasini `video::cerez::sil` ile is bitince siler (Python ile ayni).

### core/cerez.py
- ✅ temizle, netscape, dosya_yaz, sil, artiklari_temizle -> `video/cerez.rs` (artiklari_temizle cagiran yok; C acilista baglamali)
- ⚠ baslik() (aria2 Cookie basligi): yalniz aria2 icin; Rust aria2 yolu C'de. Port edilmedi.

### core/lang.py (video ile ilgili anahtarlar)
- ✅ err.needFfmpeg, err.needFfmpegAudio, note.ffmpegEmbedSkipped (TR/EN) -> `hata::lang_t`
- ✅ system_language -> `hata::sistem_tr_mi` (GetUserDefaultUILanguage, 0x1F = TR; diger diller -> EN)
- Not: Rust'ta ortak bir lang modulu yok; metinler `hata.rs`'de yerel tutuldu (Python'daki birebir metin).

## Davranis esitligi notlari
- Hata metinleri Python ile birebir (TR/EN). Ham yt-dlp metni `ham_hata` alaninda korunur; ekrana tek cumle gider.
- `kendi_birlestir`: parca 2 degilse ya da MP4 degilse dokunmaz (Python ile ayni). Hedef ad: "Baslik.mp4", "(birlesik)", "(birlesik N)" — var olan ezilmez.
- Cerez dosyasi `data\cerez\<anahtar>.txt`, is bitince/iptalde silinir.
- Surecler CREATE_NO_WINDOW ile acilir; iptal `taskkill /T /F` ile agaci oldurur.
- Python'da bir hata bulunmadi (📍 yok). Gozlenen tek tuhaflik: `_kendi_birlestir` hata olunca `error` alanina yaziyor ama durum `complete` kaliyor; Rust aynen koruyor.
- Pompa: stdout ve stderr ayri okuyucu thread'lerinden kanala akar; job kilidi surec beklerken TUTULMAZ (to_dict/iptal bloklanmaz).

## Test ve dogrulama
- Birim testleri: 34 (video). Kapsam: format secimi, guvenli_ad, birlesik dosya bulma, hata metinleri, aria/progress/hedef ayristirma, yedek karari, build_cmd bayraklari (ffmpeg var/yok, cerez, playlist, ses), cikti satirlarinin kayda islenmesi, cerez dosyasi, MP4 okuma/yazma roundtrip, yigin/ctts/stss kurallari, bozuk dosya hatasi.
- Python testlerinden tasinanlar: format_test (format/ad), video_cerez_test (yedek karari), video_pro_test (build_cmd bayraklari), video_debug_duzeltme_test (hata metni, ilerleme birimleri, cts isaretli/isaretsiz), mux_test + mux_ayristirma_test (mp4 okuma/birlestirme). video_merger_dosyaadi_test (birlesik dosya adi) kismen. video_panel_test ve video_ui_test UI testleri: Rust'ta UI yok, port edilmedi. video_yetim_kayit_test: Store sahte nesnesi gerektiriyor, unit test yazilmadi (yetimleri_duzelt elle gozden gecirildi).
- GERCEK ARAC TESTLERI (`#[ignore]`, varsayilan atlanir):
  - `video::is::testler::gercek_yt_dlp_indirme_tamamlanir`: gercek yt-dlp (Python311\Scripts\yt-dlp.exe) + yerel HTTP (127.0.0.1:8765) uzerinden 320x240 ornek.mp4 indirildi; durum `complete`, dosya kaynakla ayni boyutta (17204 bayt). PASS.
  - `video::mp4mux::testler::gercek_ffmpeg_dosyalari_birlestirilir`: ffmpeg ile uretilmis UC kombinasyon (duz video+duz ses; parcali video+parcali ses; parcali video+duz ses) birlestirildi. ffprobe: h264 75 kare + AAC, sure 3.0 sn. `ffmpeg -f null` cozumlemesi hatasiz. Video kareleri kaynakla bit-bit ayni (framemd5 ozeti eslesti: 88e7c9cf...). PASS.
  - Calistirma: `AFU_E2E_YTDLP=... AFU_E2E_URL=... AFU_E2E_DEST=... cargo test -p afudm-core -- --ignored gercek_yt_dlp` ; `AFU_E2E_VIDEO/SES/CIKTI=... cargo test -p afudm-core -- --ignored gercek_ffmpeg`.
  - Gercek YouTube (ayri ses+video, googlevideo) ile test EDILMEDI: ag erisimi ve YouTube hesabi gerekiyor. Birlestirme yolu sentetik + ffmpeg ciktilariyla dogrulandi.

### cargo test -p afudm-core (son 30 satir)
```
test video::is::testler::ffmpegsiz_kendi_mux_formati_ve_gomme_notu ... ok
test video::is::testler::dosya_adi_yuzde_kacisi ... ok
test video::is::testler::satir_ve_baslik_kayit_sekli ... ok
test video::mp4mux::testler::gercek_ffmpeg_dosyalari_birlestirilir ... ignored
test video::ilerleme::testler::hedef_satirlari_ayristirilir ... ok
test video::is::testler::ses_istegi_mp3_ve_playlist_sablonu ... ok
test video::ilerleme::testler::aria_ozet_satiri_okunur ... ok
test video::is::testler::cikti_satirlari_ilerlemeyi_ve_hedefi_gunceller ... ok
test video::mp4mux::testler::yiginlar_saniyede_boler ... ok
test video::mp4mux::testler::ctts_ve_stss_gereksizse_yazilmaz ... ok
test video::secim::testler::ses_istegi_audio_formatina_gider ... ok
test video::secim::testler::video_sitesi_ayirimi ... ok
test video::mp4mux::testler::duz_mp4_okunur_ornek_ve_kodek_dogru ... ok
test video::secim::testler::birlesik_formatlar_ve_rakamli_kalite ... ok
test video::mp4mux::testler::bozuk_dosya_hata_verir ... ok
test video::secim::testler::guvenli_ad_yasak_karakterleri_ve_bosluklari_temizler ... ok
test video::testler::entries_yoksa_sifir_ve_playlist_degil ... ok
test video::testler::probe_formatlari_ve_varsayilanlari_cikarir ... ok
test video::secim::testler::birlesik_cikti_parca_adindan_bulunur ... ok
test video::mp4mux::testler::birlestir_video_ve_sesi_tek_dosyada_toplar ... ok
test butunluk::tests::aria2_ve_html_blok_bozuk_bloklari_verir ... ok

test result: ok. 83 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out; finished in 0.18s
```

### cargo clippy -p afudm-core --all-targets -- -D warnings (son 30 satir)
```
    Checking afudm-types v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-types)
    Checking afudm-db v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db)
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 8.76s
```
(Son calistirmada butunluk.rs'deki 3 lint de kapanmis; clippy temiz.)

## Kalanlar / C ve G ekiplerine
1. queue.rs: yukaridaki 6 cagriyi baglamak (durdur, kaldir, tumunu_durdur, video_satirlari, yetimleri_duzelt, aktif_sayisi/hiz_toplami).
2. _on_complete zinciri (butunluk, otomasyon, Telegram) C/G ile baglanacak.
3. aria2c IPv6 bayragi ve sistem proxy yedegi: ortak fonksiyon (netcheck/proxy karsiligi) gerekiyor.
4. mp4kutu.py: port edilmedi (import eden yok); istenirse arastirma araci olarak ayri tutulur.
