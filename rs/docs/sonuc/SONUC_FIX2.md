# SONUC FIX2 — Entegrasyon-2 (video, tamamlanma zinciri, bütünlük, IPv6/proxy, G1 engines)

Ekip: Entegrasyon-2. Görev: docs/gorev/GOREV_FIX2_ENTEGRASYON.md. Python kaynağı yalnız okundu.

## Yazılan dosyalar
- crates/afudm-core/src/queue.rs (pause/stop/pause_all/start/can_release_ui/find_duplicate bağlantıları; `tamamlandi`; `insan_boyut`; State'ten ölü `video_jobs`/`video_stoppers` alanları kaldırıldı)
- crates/afudm-core/src/queue/netcheck.rs (YENİ: IPv6 kararı)
- crates/afudm-core/src/queue/files.rs (remove ve resolve yt dalları)
- crates/afudm-core/src/queue/shaping.rs (snapshot: tamamlanma yakalama, video satırları, hız/aktif toplamları; `language` pub(super))
- crates/afudm-core/src/queue/tests.rs (9 yeni test)
- crates/afudm-core/src/video.rs (bitenler kuyruğu, köprü fonksiyonları, test yardımcıları)
- crates/afudm-core/src/video/is.rs (IPv6 bayrağı, proxy normalizasyonu, 1 yeni test)
- crates/afudm-extras/src/g1/reliability.rs ve g1/mod.rs (engines anahtarı)

## 1. Video bağlantısı
- ✅ pause (yt) -> video::durdur
- ✅ remove (yt) -> video::kaldir (güvenli ad kontrolü + queue::safe)
- ✅ pause_all (yt) -> video::tumunu_durdur
- ✅ snapshot video satırları -> video::video_satirlari (aria2 satırlarından sonra, Python sırası)
- ✅ snapshot stat hız/aktif -> video::hiz_toplami / video::aktif_sayisi
- ✅ start -> video::yetimleri_duzelt (Python __init__ ile aynı görev; Rust'ta start'ta)
- ✅ can_release_ui (active|waiting) -> video::calisan_veya_bekleyen_var (ek)
- ✅ stop -> video::aktif_isleri_kapat (ek; Python stop aktif süreçleri kapatır, durumu korur)
- ✅ find_duplicate canlı kimlikler -> video::gidler (ek; Python find_duplicate ile aynı)
- ✅ resolve yt -> video::dosya_yolu (ek)
- ⚠ Python resolve yt dalı output_path/target_path adaylarına da bakar; VideoJob'da bu alanlar yok, yalnız dest_dir+filename kullanıldı.
- 📍 Python'daki `_launch(row)` yolu resume için zaten video_ekle_ic'e gidiyor; ek değişiklik gerekmedi.

## 2. Tamamlanma zinciri
- ✅ `pub(crate) fn tamamlandi(m, title, size, gid)` (queue.rs). Sıra: log -> butunluk_tara -> (bozuk: log + UI bildirimi + DÖN) -> (sağlam: artık kontrol dosyasını sil) -> Telegram (notify_telegram ayarı açıksa) -> UI bildirimi -> m.tamamlandi_kancalari her biri {"title","size","gid"}.
- ✅ aria2: shaping::snapshot içinde status complete + followedBy yok + known_complete'e ilk ekleme -> tamamlandi (Python _sync_aria2 ile aynı).
- ✅ video: gözlemci tamamlanınca video::bitenler kuyruğuna yazar (dedup bildirilen ile); snapshot başında boşaltılıp tamamlandi'ye girer.
- ⚠ Sıra: görev dosyasındaki sıra izlendi. Python'da Windows bildirimi Telegram'dan önce çalışıyordu; fark bilinçli değil, görev sırası esas alındı.
- ⚠ Python _on_complete'in shutdown_when_done / sleep_when_done adımları port edilmedi (güç/kabuk sorumluluğu, görev listesinde yok).
- ⚠ aria2 tarafındaki Python _cerez_birak ve _auth_gerekli_temizle yan işleri port edilmedi (çerez modülü C ekibinde).
- ⚠ Video tamamlanması snapshot çağrısına bağlıdır (Python'da anlık). Kabuk snapshot'ı periyodik çağırmıyorsa bildirim gecikir.
- ⚠ Telegram çağrısı senkron (notify_telegram, 15 sn zaman aşımı); Python ayrı thread kullanır. Snapshot bu süre kadar bloklanabilir.
- 📍 Python ile aynı davranış: known_complete açılışta boş başlar; açılışta var olan tamamlanmış aria2 kayıtları için de tamamlandi zinciri bir kez çalışır (düzeltilmedi, Python'da da böyle).

## 3. IPv6 ve proxy
- ✅ queue/netcheck.rs: ipv6_usable (UDP connect, paket gönderilmez, OnceLock ile önbellek) ve aria2_ipv6_args (Python netcheck.py ile birebir mantık; yerel/ULA adresleri yaramaz sayılır).
- ✅ video/is.rs komut: dış indirici (aria2c) argümanlarına IPv6 yoksa `--disable-ipv6=true` (Python ytdlp.py ile aynı konum).
- ✅ video/is.rs proxy_ayrimi: queue::proxy::parcala + aria2_secenekleri (Python proxy.komut_secenekleri ile aynı normalizasyon; geçersiz adres proxysiz çalışır).
- ⚠ afudm-engine/src/daemon.rs içinde ayrı bir ipv6_usable kopyası var (aria2 daemon başlatma). afudm-engine bu görevin dışında olduğu için dokunulmadı. 📍 İki kopya tek fonksiyona bağlanmalı (öneri: queue::netcheck::ipv6_usable pub yapılıp engine'e taşınır, Claude kararı).
- ⚠ "Sistem proxy yedeği": queue/proxy.rs içindeki proksi_bul zinciri (is-açık -> sistem -> genel) zaten mevcut; ek değişiklik yapılmadı.

## 4. G1 eksiği: engines
- ✅ reliability::diagnostics_preview(store, app_dir) ve diagnostics_export(store, data, app_dir): "engines" anahtarı = afudm_engine::engines::durum(app_dir) (Python diagnostics_preview ile aynı anahtar). g1/mod.rs rotaları güncellendi; çağıran başka yer yok.

## 5. Testler (bağlantı başına sahte Aria2/Store testi)
- queue::tests: tamamlandi_kancalari_dogru_yukle_calisir; aria2_tamamlanmasi_snapshotta_bir_kez_zincire_girer; video_tamamlanmasi_snapshotta_bir_kez_zincire_girer; video_duraklat_ve_kaldir_kayitlari_gunceller; video_tumunu_durdur_yalniz_bitmemis_isleri_durdurur; video_yetim_kayitlari_acilista_duraklatilir; video_kapanista_kayit_durumu_korunur; video_isi_yinelenen_kontrolunde_canli_sayilir.
- queue::netcheck: yalniz_genel_unicast_yaramali; ipv6_argumani_bilinen_bicimde.
- video::is: dis_indirici_ipv6_ve_proxy_argumanlari (ipv6 bayrağı, sistemin ölçtüğü değerle tutarlı).
- g1::reliability: tani_maskeli_disa_aktarilir (engines anahtarı kontrolü eklendi).
- Gerçek yt-dlp/aria2 uçtan uca testleri çalıştırılmadı (ignored testler mevcut D2 kapsamında).

## Sözleşme sorunları
- Yok. afudm-types, afudm-core/src/lib.rs, afudm-engine, afudm-db, app\ değiştirilmedi.
- Not: Cargo.toml değişmedi; yeni bağımlılık yok.

## Kapsam kontrolü
git status: yalnız görevdeki dosyalar değişti (queue.rs, queue/{files,shaping,tests,netcheck}.rs, video.rs, video/is.rs, g1/{mod,reliability}.rs). `app/` Ekip F'ye ait, dokunulmadı. Commit/Notam yazılmadı.

## Test ve doğrulama
Komutlar (çalışma dizini: AfuDM_rs\rs):
- cargo build -p afudm-core -p afudm-extras
- cargo test -p afudm-core -p afudm-extras
- cargo clippy -p afudm-core -p afudm-extras --all-targets -- -D warnings
- rustfmt --check: değişen dosyalar temiz.

### cargo build (son satırlar)
```
   Compiling afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.53s
BUILD_EXIT=0
```

### cargo test (son 30 satır)
```
test h::smb::tests::kok_afudm_network_shares_adinda ... ok
test h::smb::tests::net_share_ciktisi_sadece_afudm_adlarini_alir ... ok
test h::tunel::tests::url_bulucu_python_gibi ... ok
test h::tunel::tests::url_yoksa_iki_denemeden_sonra_hata ... ok
test g2::linkgrabber::tests::panel_filtresi_wildcard_ve_boyut ... ok
test g1::reliability::tests::tani_maskeli_disa_aktarilir ... ok
test g2::eklenti_servis::entegrasyon::ozet_uyusmazligi_kurulumu_durdurur ... ok
test g2::eklenti_servis::entegrasyon::guncelle_yanlis_paketi_reddeder ... ok
test g2::linkgrabber::tests::ayiklar_http_ftp_magnet ... ok
test g2::eklenti_servis::entegrasyon::kur_listele_ayar_kaldir_akisi ... ok
test g1::reliability::tests::yedek_olusur_listelenir_ve_geri_yuklenir ... ok
test h::tunel::tests::durdur_izleyiciyi_etkisiz_kilar ... ok
test h::tunel::tests::izleyici_surec_cikinca_bir_kez_yeniden_baslatir ... ok
test g1::guncelleme::tests::kontrol_ag_hatasinda_turkce_hata ... ok

test result: ok. 87 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.04s

   Doc-tests afudm_core

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_extras

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

TEST_EXIT=0
```

### cargo clippy -D warnings (son satırlar)
```
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.99s
CLIPPY_EXIT=0
```

## Ek madde 6 (koordinatör): kabuğun Manager yardımcılarına erişimi
Kabuk (app) için `afudm_core::queue::` altında `pub fn` yapıldı. İmzalar Python ile aynı; Manager gerektirmeyenler serbest fonksiyon.
- ✅ `detect_kind(source) -> &'static str` (serbest)
- ✅ `is_supported_source(source) -> bool` (serbest)
- ✅ `magnet_infohash(source) -> String` (serbest; kucuk harf hex)
- ✅ `guess_name(source) -> String` (serbest; Python resolve_filename(source))
- ✅ `clean_title(title) -> String` (serbest)
- ✅ `gecmis_sources(m, limit) -> Result<Vec<String>>`
- ✅ `find_duplicate(m, source) -> Result<Option<Json>>` (artik pub)
- ✅ `hiz_limiti_kb(m, ayarlar: Option<&JsonMap>) -> Result<i64>` (None ise store.all_settings)
- ✅ `apply_settings(m) -> Result<()>`
- ✅ `probe_url_info(m, url) -> Result<Json>`: Python dosya_adi.probe_url_info ile birebir. Yeni modul `queue/probe.rs`: Content-Disposition (RFC 6266 ve filename* RFC 5987), MIME uzantisi tablosu, guvenli dosya adi (DOS aygit adlari, 200 karakter), HEAD + Range 0-0 GET yedegi, 3 sn zaman asimi. Donus alanlari: ok, filename, size, content_type, resumable, final_url.
- ✅ `kaydet_bilgi` ve `probe_link` icin gereken tek core eksigi probe_url_info idi. kategori_tahmin ve kategori klasorleri zaten afudm-db/src/kaydet.rs icinde. Kabuk tarafindaki kaydet_bilgi/probe_link govdeleri bu crate'te portlanmadi (kabuğun isi).

Ek testler (queue/tests.rs): dosya_adi_cozumlemesi_python_ile_ayni_sonuc_verir; probe_url_info_yerel_sunucudan_basliklari_okur (gercek yerel HTTP sunucusu); probe_url_info_erisilemeyen_ve_http_disi_kaynaklar; hiz_limiti_ve_gecmis_kaynaklar_ayarlara_gore_doner.

Acik notlar:
- 📍 Python probe'undaki Range basligi `bytes 0-0` ("bytes=0-0" olmali) aynen korundu; Python davranisi esas alindi, duzeltme yok.
- ⚠ filename* icinde iso-8859-1 charset'i icin Python latin-1 cozer; Rust bu durumda UTF-8 cozer (kucuk fark).
- ⚠ detect_kind Rust'ta sabit host listesi kullanir; Python ytdlp.is_video_site ile tam ayni olmayabilir (onceki ekipten gelen kod, degistirilmedi).

Son dogrulama (gercek cikti):
### cargo test (son 30 satir)
```
test h::smb::tests::net_share_ciktisi_sadece_afudm_adlarini_alir ... ok
test h::tunel::tests::url_bulucu_python_gibi ... ok
test h::tunel::tests::baslat_url_dondurur_ve_argumanlar_dogru ... ok
test h::tunel::tests::url_yoksa_iki_denemeden_sonra_hata ... ok
test h::paylasim::tests::dar_sunucu_range_ile_dosya_verir ... ok
test h::paylasim::tests::kok_icinde_sinirlar ... ok
test g2::eklenti_servis::entegrasyon::ozet_uyusmazligi_kurulumu_durdurur ... ok
test g2::eklenti_servis::entegrasyon::guncelle_yanlis_paketi_reddeder ... ok
test g2::eklenti_servis::entegrasyon::kur_listele_ayar_kaldir_akisi ... ok
test g2::linkgrabber::tests::ayiklar_http_ftp_magnet ... ok
test g1::reliability::tests::yedek_olusur_listelenir_ve_geri_yuklenir ... ok
test h::tunel::tests::durdur_izleyiciyi_etkisiz_kilar ... ok
test h::tunel::tests::izleyici_surec_cikinca_bir_kez_yeniden_baslatir ... ok
test g1::guncelleme::tests::kontrol_ag_hatasinda_turkce_hata ... ok

test result: ok. 87 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.05s

   Doc-tests afudm_core

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_extras

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

TEST_EXIT=0
```
### cargo clippy -D warnings
```
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.03s
CLIPPY_EXIT=0
```
