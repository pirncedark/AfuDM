# SONUC 301A — Üç güvenlik düzeltmesi

## Uygulanan değişiklikler

1. **XFF güveni:** `yonetim.rs::proxy_istemci_ip`, ayar açıkken yalnız gerçek peer IPv4/IPv6 loopback ise son XFF değerini kabul eder. LAN istemcisi hız sınırı ve giriş kilidindeki kimliğini sahte XFF ile değiştiremez. Ayar kapalıyken peer kullanımı korunur. IPv4/IPv6, LAN sahteciliği, kapalı ayar ve eksik başlık birim testinde doğrulanır.
2. **QR eşleştirmesi:** `lan_adres`, kalıcı token yerine `/m?code=...` üretir. Kod 32 rastgele bayttır, bellekte veri dizinine bağlı tutulur ve 300 saniye geçerlidir. `/pair?code=...` kodu kilit altında atomik olarak tüketip kimliği döndürür. Yanlış, süresi dolmuş ve tekrar kullanılan kod reddedilir. Kullanılmamış kod süre dolana kadar aynı QR olarak gösterilir; tüketimden sonra yeni kod üretilir. Kimlik yanıtında `Cache-Control: no-store` ve `Referrer-Policy: no-referrer` vardır. Kodsuz yerel uzantı eşleştirmesinin loopback ve açık pencere şartı korunur.
3. **Çocuk portu:** ebeveynin boş port bağlayıp bırakması kaldırıldı. Çocuk `serve` içinde doğrudan OS'nin seçtiği porta bağlanır; socket elindeyken gerçek portu yalnız ebeveynin stdout borusuna bildirir. Ebeveyn geçerli ve satırı tamamlanmış port bildirimi gelmeden HTTP isteği göndermez. Hatalı veya eksik bildirimde yalnız kendi çocuğunu kapatır. İstemcide proxy ve yönlendirme kapalıdır. Boru sonrasında boşaltılır; stderr mevcut çocuk günlüğünde kalır.

### Port çözümünün gerekçesi

Görevde izin verilen doğrudan bağlanma + pipe seçeneği kullanıldı. Böylece ek nonce protokolü ve public hazır-olma rotası gerekmez; eski port seçme/bırakma yarış aralığı ortadan kalkar. Port ağdaki bir servisten öğrenilmez. Gerçek alt süreç testi çocuğun kendi portundan yanıt verdiğini; socket testi bağlı porta başka dinleyici bağlanamadığını doğrular. Bu çözüm aynı kullanıcı altında ele geçirilmiş süreçlere karşı yeni bir işletim sistemi izolasyonu iddiası taşımaz.

### Eski telefonların geçişi

Bir sürüm boyunca eski `?k=` bağlantısı kabul edilir. Mobil sayfa kimliği mevcut `afudm_anahtar` yerel saklama alanına aktarır ve API çağrılarında `X-AfuDM-Token` başlığını kullanır. `history.replaceState`, hem `k` hem `code` sorgusunu betiğin başında hemen temizler; referrer meta etiketi adres sızıntısını önler. Temiz `/m` adresiyle açılan kayıtlı telefon aynı kimlikle devam eder. Yeni kodun `/pair` değiş tokuşu tamamlanmadan API çağrısı yapılmaz. Süresi dolmuş kodda eski kayıtlı token'a sessizce dönülmez. Yeniden bağlan alanı yeni kodlu adresleri kabul eder; farklı sunucunun kodunu bu sunucuya göndermez.

## 301A dosyaları

- `rs/app/src/yonetim.rs`: XFF sınırı, QR adresi ve proxy birim testi.
- `rs/app/ui/mobil.html`: eşleştirme, eski bağlantı geçişi, URL temizliği, yeniden bağlanma.
- `rs/crates/afudm-extras/src/h/esleme.rs`: kod üretimi, süre/tek kullanım, `/pair` ve üç birim testi.
- `rs/crates/afudm-api/src/listener.rs`: çocuk port borusu, güvenli istemci ve gerçek alt süreç dahil regresyon testleri.
- `rs/crates/afudm-api/src/lib.rs`: koordinatör onayıyla kapsama alındı; çocuk socket bağlama ve port bildirimi.
- `rs/tests_hata/guvenlik_301a.py`: geçici veri/rastgele port ile gerçek LAN QR değiş tokuşu.
- `rs/tests_hata/mobil_301a.test.cjs`: altı mobil JavaScript regresyon testi.
- Bu rapor ile `301A_*.log` / `301A_checks.json`: gerçek kontrol kayıtları (loglar git tarafından yok sayılıyor).

Yeni Python işlevi taşınmadı; mevcut Rust akışlarındaki üç güvenlik düzeltmesi tamamlandı. Bu görevde kalan `todo!()` veya sözleşme engeli yok. Önceki rapordaki lib.rs kapsam engeli koordinatör onayıyla kalktı.

## Çalışma sınırları

Başlangıçta `git status` ve `git diff` incelendi; önceki turun kodu tekrar uygulanmadı. Paralel 301B değişiklikleri (queue, engine, DB, API security/tests ve güncelleme) korundu; bu turda bu dosyalara yazılmadı. Yasak git işlemleri kullanılmadı. Pencere açılmadı. Çalışan kullanıcı uygulamasına, kullanıcı veri klasörüne, AfuDM/AfuDM_rs kaynaklarına yazılmadı. Ağ testleri geçici veri ve kendilerinin başlattığı süreçleri kullanır; Python referansı salt okunur kullanılır.

## Doğrulama

Tum 11 kontrol EXIT 0 ile tamamlandi. Ana Rust workspace: 251 passed, 0 failed, 2 ignored; uygulama: 30 passed, 0 failed; mobil: 6 passed, 0 failed.

Iki ignored test mevcut gercek yt-dlp indirme ve ffmpeg birlestirme testleridir; bu gorevin guvenlik testleri ignored degildir.

Sanal workspace icin bicim kontrolu `rs` icinde `cargo fmt --all --check`, uygulama icin `rs/app` icinde `cargo fmt --check` olarak calistirildi. Ilk Node `--test` calistirmasi sandbox alt surec izninde EPERM verdi; test dosyasi dogrudan `node` ile ayni node:test harness kullanilarak calistirildi ve 6/6 gecti.

### Gercek komut ciktilari (son 30 satir)

`cargo test --manifest-path rs/Cargo.toml`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
   Doc-tests afudm_core

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_db

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_engine

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_extras

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_types

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

```

Birim test ozetleri (ayni gercek logdan):

```text
test result: ok. 16 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.24s
test result: ok. 110 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out; finished in 4.05s
test result: ok. 16 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.25s
test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 20.25s
test result: ok. 97 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.03s
```

`cargo clippy --manifest-path rs/Cargo.toml --all-targets -- -D warnings`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.98s
```

`cargo test --manifest-path rs/app/Cargo.toml`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::defender_durum_varsayilani_idle ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test bridge::tests::servis_hatasi_python_sozlesmesi ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::uuid_biçimi_ve_surumu ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::fix8_telefon_paylasimi_ui_defterinde ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test yonetim::tests::filtre_ve_arama ... ok
test yonetim::tests::proxy_yalniz_loopback_peer_icin_guvenilir ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test boot::tests::fix8_restore_eski_wal_shm_temizler ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok

test result: ok. 30 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

```

`cargo clippy --manifest-path rs/app/Cargo.toml --all-targets -- -D warnings`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\app)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 2.32s
```

`cargo fmt --all --check`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs`; EXIT 0

```text
(cikti yok)
```

`cargo fmt --check`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\app`; EXIT 0

```text
(cikti yok)
```

`node rs/tests_hata/mobil_301a.test.cjs`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
✔ QR temizlenir; degis tokus bitmeden kalici token ile API cagrilmaz (2.525ms)
✔ eski k baglantisi hemen temizlenir ve header akisina aktarilir (1.5711ms)
✔ suresi dolan QR eski saklanan kimlikle sessizce devam etmez (1.3518ms)
✔ kayitli telefon temiz adresle kimligini kullanmaya devam eder (1.0576ms)
✔ yeniden baglan alani yeni QR kodunu degistirir (1.3719ms)
✔ baska sunucunun QR kodu mevcut sunucuya gonderilmez (0.9708ms)
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 16.3327
```

`python -B rs/tests_hata/verify.py`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
build_feature 0
test_feature 0
clippy_feature 0
build_default 0
test_default 0
clippy_default 0
format_owned 0
```

`python -B rs/tests_hata/guvenlik_301a.py`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
QR_LAN: GECTI (kalici token yok; yanlis kod, tek kullanim, yeni kod, API kimligi, kapali yerel esleme)
CLEANUP: GECTI (yalniz sahip olunan test surecleri)
```

`python -B rs/tests_hata/hepsi.py --only network`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
READY py API=54053 gate=54056 isolated data
READY rs API=54108 gate=54124 isolated data
START network
READY py API=54166 gate=54168 fresh data
READY rs API=54235 gate=54262 fresh data
END network
CLEANUP all owned processes stopped: True
RESULT network GECTI
```

`git diff --check`

Calisma dizini: `C:\Users\afuuu\Desktop\afuproject\AfuDM_301`; EXIT 0

```text
(cikti yok)
```

### Ek build kontrolu

`cargo build --manifest-path rs/Cargo.toml -p afudm-api -p afudm-extras`

EXIT 0

```text
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.41s
```

`verify.py` icinde feature/default build, test, clippy ve format kontrollerinin yedisi de EXIT 0. Test kapisi feature ikilisinde mevcut, production ikilisinde yok.

Ag testi cleanup kaydi:

```json
{
  "all_owned_processes_stopped": true,
  "remaining": []
}
```

## 3.0.1-A devam — listener bozuk JSON karantinasi (2026-10-18)

read_record, JSON cozumleme hatasinda 3.0.1-B afudm_engine::daemon::quarantine_json yardimcisini cagirir ve Json::Null dondurur. Yardimci <ad>.corrupt-YYYYmmdd-HHMMSS dosyasini koruyarak tasir ve log yazar. deliver_once, state queued olmadigi icin bu kaydi gondermez. Dosya okuma ve sifre cozme hatalari hata olarak kalir.

Mevcut record_tests testleri tamamlandi: bozuk kayit testi duzeltme oncesinde EOF while parsing a value hatasiyla FAILED (1 passed; 1 failed), duzeltme sonrasinda 2 passed; 0 failed. Testler Null, kuyruktan cikarma, tarih bicimi, tekrarlanan karantinada yedekleri koruma, gecerli kayit ve eksik dosya davranisini denetler.

Bu turda yalniz listener.rs ve bu sonuc dosyasi duzenlendi. Baska dosya degisikligi gerekmedi.

### cargo test --manifest-path rs\Cargo.toml

Calisma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_301
EXIT 0

```text
cargo.exe :    Compiling afudm-api v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-api)
At line:11 char:18
+     $captured = (& cargo @checkArgs 2>&1 | Out-String -Width 4096)
+                  ~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (   Compiling af...ates\afudm-api):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

   Compiling afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-extras)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 8.27s
     Running unittests src\lib.rs (rs\target\debug\deps\afudm_api-60726d629c0f2e4f.exe)

running 18 tests
test listener::port_tests::pipe_child_fixture ... ok
test listener::port_tests::eksik_sahte_ve_gecersiz_port_bildirimi_reddedilir ... ok
test tests::limiter_live_settings_preserve_attempts_and_locks ... ok
test listener::port_tests::cocuk_portu_yalniz_borudan_ve_baglandiktan_sonra_ogrenilir ... ok
test listener::record_tests::corrupt_record_is_quarantined_without_replay_or_backup_loss ... ok
test tests::serve_passes_client_addr_as_connect_info ... ok
test transfer::tests::windows_names_and_header_encoding ... ok
test listener::port_tests::boru_bildirimi_gelmeden_http_baslamaz ... ok
test listener::port_tests::gercek_cocuk_borusu_yeni_portu_bildirir ... ok
test tests::omniget_corrupt_endpoint_does_not_break_token_rotation ... ok
test tests::access_keys_sessions_roles_and_limiter ... ok
test listener::record_tests::valid_record_round_trips_and_missing_record_remains_an_io_error ... ok
test tests::add_control_torrent_and_error_mapping ... ok
test tests::cors_and_body_limit ... ok
test tests::blob_streams_and_rejects_client_paths ... ok
test tests::python_uyumlu_rotalar_ve_yetenekler ... ok
test tests::authentication_rotation_and_json_errors ... ok
test tests::serve_and_listener_use_ephemeral_ports ... ok

test result: ok. 18 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.24s

     Running unittests src\lib.rs (rs\target\debug\deps\afudm_core-135b2225045eab73.exe)

running 112 tests
test butunluk::tests::artik_aria2_tam_iken_silinir ... ok
test butunluk::tests::gercek_json_hata_sayfasi_bozuk ... ok
test butunluk::tests::blok_indir_206_yoksa_reddeder ... ok
test butunluk::tests::blok_indir_206_ve_dogru_veri ... ok
test butunluk::tests::html_iceren_sahte_rar_bozuk_ve_html_uzantisi_saglam ... ok
test butunluk::tests::tara_boyut_uyusmazligi_eksik ... ok
test butunluk::tests::rastgele_veri_json_gibi_baslasa_bozuk_sayilmaz ... ok
test butunluk::tests::butunluk_onar_kayit_yoksa_neden_doner ... ok
test butunluk::tests::butunluk_hepsini_tara_python_gibi_hata_verir ... ok
test butunluk::tests::butunluk_tara_kayit_yoksa_bulunamadi ... ok
test butunluk::tests::yanlis_imza_bozuk ... ok
test butunluk::tests::butunluk_tara_bozuk_kaydi_hataya_yazar ... ok
test butunluk::tests::aria2_var_ve_bos_dosya_eksik ... ok
test queue::proxy::tests::parcala_http_ve_socks_sekmeleri ... ok
test queue::netcheck::testler::yalniz_genel_unicast_yaramali ... ok
test queue::proxy::tests::parcala_kimlik_ve_hatalar ... ok
test queue::proxy::tests::aria2_secenekleri_ve_url ... ok
test queue::proxy::tests::sistem_adresi_http_girdisini_secer ... ok
test queue::tests::dosya_adi_cozumlemesi_python_ile_ayni_sonuc_verir ... ok
test queue::tests::empty_snapshot_has_python_envelope ... ok
test queue::netcheck::testler::ipv6_argumani_bilinen_bicimde ... ok
test butunluk::tests::tara_saglam_zip_gecer ... ok
test queue::tests::acilis_kurtarmasi_aria2da_olmayan_bitmemis_kaydi_yeniden_ekler ... ok
test queue::tests::missing_pause_resume_and_connection_fail_without_writes ... ok
test queue::tests::invalid_add_retry_renew_and_local_file ... ok
test queue::tests::lifecycle_and_telegram_without_configuration ... ok
test butunluk::tests::html_yanit_206_olsa_da_reddedilir ... ok
test queue::tests::http_add_duplicate_controls_and_retry ... ok
test butunluk::tests::aria2_tam_ve_yarim ... ok
test queue::tests::hiz_limiti_ve_gecmis_kaynaklar_ayarlara_gore_doner ... ok
test queue::tests::omniget_403_retries_once_with_preserved_request ... ok
test queue::tests::completed_file_registration_and_resolve ... ok
test queue::tests::omniget_corrupt_auth_marker_is_quarantined ... ok
test queue::tests::fix8_filename_motor_kokunden_cikamaz ... ok
test queue::tests::phone_path_uses_engine_before_db_without_filename_guessing ... ok
test queue::tests::profiles_restore_normal_limit ... ok
test queue::tests::omniget_only_real_http_403_is_retried ... ok
test queue::tests::request_and_filename_contracts ... ok
test queue::tests::settings_validation_is_all_or_nothing ... ok
test queue::tests::probe_url_info_yerel_sunucudan_basliklari_okur ... ok
test queue::tests::omniget_html_content_type_does_not_skip_binary_integrity ... ok
test queue::tests::special_servers_and_orphan_remove ... ok
test queue::tests::parent_child_remove_hides_orphans_and_allows_hash_readd ... ok
test butunluk::tests::tara_html_hata_sayfasi_bozuk_sayilir ... ok
test queue::tests::renew_updates_url_and_clears_auth_requirement ... ok
test queue::tests::snapshot_does_not_process_completion ... ok
test queue::tests::sleeping_video_completion_does_not_query_or_wake_aria2 ... ok
test queue::tests::scheduled_add_persists_without_launch_or_cookies_in_options ... ok
test queue::tests::sync_persists_errors_and_does_not_wake_sleeping_engine ... ok
test queue::tests::sync_dispatches_video_completion_once ... ok
test queue::tests::tamamlandi_kancalari_dogru_yukle_calisir ... ok
test torrent::bencode::testler::bozuk_torrent_bos_hash_doner ... ok
test torrent::bencode::testler::fazla_veri_hatadir ... ok
test queue::tests::video_isi_yinelenen_kontrolunde_canli_sayilir ... ok
test torrent::bencode::testler::sozluk_ve_liste_cozulur ... ok
test torrent::bencode::testler::info_hash_info_sozlugunun_sha1i ... ok
test queue::tests::video_duraklat_ve_kaldir_kayitlari_gunceller ... ok
test queue::tests::video_tumunu_durdur_yalniz_bitmemis_isleri_durdurur ... ok
test torrent::saglik::testler::host_port_ayrisir ... ok
test queue::tests::video_yetim_kayitlari_acilista_duraklatilir ... ok
test queue::tests::video_kapanista_kayit_durumu_korunur ... ok
test queue::tests::remove_rejects_outside_files_and_root_directory ... ok
test torrent::saglik::testler::tara_bos_liste_sifir_sayar ... ok
test torrent::trackers::testler::birlesik_url_ayrilir_ve_ws_elenir ... ok
test queue::tests::video_completion_waits_for_sync_not_snapshot ... ok
test torrent::trackers::testler::tekrarlar_buyuk_kucuk_harf_duyarsiz_silinir ... ok
test torrent::trackers::testler::yerel_ve_yasak_adresler_cikar ... ok
test torrent::saglik::testler::dosya_sil_yol_kacisini_reddeder ... ok
test torrent::trackers::testler::yildiz_ve_tirnak_temizlenir ... ok
test video::cerez::testler::bozuk_ve_yasak_cerezler_atilir ... ok
test video::hata::testler::ham_hata_gizlenir_ipucuna_gore_cumle_secilir ... ok
test video::hata::testler::acik_dil_secimi ... ok
test video::cerez::testler::netscape_bicimi ... ok
test queue::tests::sync_persists_completion_once_before_purge_and_snapshot_reads_db ... ok
test video::cerez::testler::dosya_yaz_sil_ve_artik_temizligi ... ok
test video::hata::testler::ffmpeg_notu_oldugu_gibi_gecer ... ok
test video::ilerleme::testler::ilerleme_satiri_na_ve_bozuk_degerleri_sifirlar ... ok
test video::ilerleme::testler::yedek_karari_yalniz_belli_hatalarda_tekrarlar ... ok
test video::hata::testler::bilinmeyen_hata_varsayilan_cumle ... ok
test video::ilerleme::testler::eta_bicimleri ... ok
test torrent::saglik::testler::dosya_ekle_bos_listeyi_reddeder ... ok
test torrent::saglik::testler::dosya_ekle_ayni_kumeyi_zaten_olarak_bildirir ... ok
test video::is::testler::dosya_adi_yuzde_kacisi ... ok
test video::is::testler::dis_indirici_ipv6_ve_proxy_argumanlari ... ok
test video::is::testler::birlestirilecek_parca_sayisi_degilse_dokunmaz ... ok
test video::is::testler::cerez_dosyasi_tarayici_cerezinden_onceliklidir ... ok
test video::is::testler::durdur_isareti_ve_durum ... ok
test video::is::testler::ffmpeg_varken_birlesik_mp4_ve_ayri_iz_formati ... ok
test video::is::testler::gercek_yt_dlp_indirme_tamamlanir ... ignored
test video::is::testler::ffmpegsiz_kendi_mux_formati_ve_gomme_notu ... ok
test video::is::testler::satir_ve_baslik_kayit_sekli ... ok
test video::is::testler::proxy_ayrimi_kimlik_ve_adres ... ok
test video::mp4mux::testler::ctts_ve_stss_gereksizse_yazilmaz ... ok
test video::mp4mux::testler::gercek_ffmpeg_dosyalari_birlestirilir ... ignored
test video::is::testler::ses_istegi_mp3_ve_playlist_sablonu ... ok
test video::mp4mux::testler::yiginlar_saniyede_boler ... ok
test video::secim::testler::birlesik_formatlar_ve_rakamli_kalite ... ok
test video::secim::testler::guvenli_ad_yasak_karakterleri_ve_bosluklari_temizler ... ok
test video::secim::testler::ses_istegi_audio_formatina_gider ... ok
test video::secim::testler::video_sitesi_ayirimi ... ok
test video::testler::entries_yoksa_sifir_ve_playlist_degil ... ok
test video::ilerleme::testler::hedef_satirlari_ayristirilir ... ok
test video::testler::probe_formatlari_ve_varsayilanlari_cikarir ... ok
test video::mp4mux::testler::bozuk_dosya_hata_verir ... ok
test video::secim::testler::birlesik_cikti_parca_adindan_bulunur ... ok
test video::ilerleme::testler::aria_ozet_satiri_okunur ... ok
test video::is::testler::cikti_satirlari_ilerlemeyi_ve_hedefi_gunceller ... ok
test video::mp4mux::testler::duz_mp4_okunur_ornek_ve_kodek_dogru ... ok
test video::mp4mux::testler::birlestir_video_ve_sesi_tek_dosyada_toplar ... ok
test queue::tests::omniget_html_error_blocks_completion_and_preserves_file ... ok
test butunluk::tests::aria2_ve_html_blok_bozuk_bloklari_verir ... ok
test queue::tests::probe_url_info_erisilemeyen_ve_http_disi_kaynaklar ... ok

test result: ok. 110 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out; finished in 4.10s

     Running unittests src\lib.rs (rs\target\debug\deps\afudm_db-5dfe8ef5171e6397.exe)

running 16 tests
test tests::omniget_corrupt_pending_uses_calendar_quarantine_and_defaults ... ok
test tests::plugins_preserve_install_time_decode_and_filter_updates ... ok
test tests::rules_are_ordered_and_failed_replace_rolls_back ... ok
test tests::settings_normalization_and_portable_paths ... ok
test tests::settings_boundaries_normalize_and_report_all_without_secrets ... ok
test tests::scheduling_selections_queries_and_json_values ... ok
test tests::durable_automation_resume_retry_cancel ... ok
test tests::store_settings_downloads_and_events ... ok
test tests::omniget_json_reader_preserves_valid_and_repeated_corrupt_files ... ok
test tests::shared_store_is_send_sync_and_serializes_concurrent_writes ... ok
test tests::pending_expiry_corruption_and_failed_write_preserve_request ... ok
test tests::categories_names_folder_tree_network_and_last_folder ... ok
test tests::pending_requests_persist_deduplicate_protect_secrets_and_restore ... ok
test tests::legacy_v2_existing_gid_and_auto_accept_migration ... ok
test tests::real_database_byte_copy_preserves_python_table_counts ... ok
test tests::migrations_zero_two_four_and_ten_preserve_records_and_reopen ... ok

test result: ok. 16 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.18s

     Running unittests src\lib.rs (rs\target\debug\deps\afudm_engine-b593c5dce2b2eb4d.exe)

running 12 tests
test tests::rpc_error_shapes_match_python ... ok
test tests::motor_status_and_missing_are_portable ... ok
test tests::omniget_corrupt_session_marker_is_quarantined ... ok
test tests::secrets_and_session_credentials_survive_migration_safely ... ok
test engines::tests::download_checksum_failure_and_invalid_binary_preserve_existing_engine ... ok
test tests::rpc_default_status_keys_match_python_for_each_poll ... ok
test tests::rpc_all_trait_methods_send_python_methods_and_parameters ... ok
test tests::daemon_arguments_and_listener_detection_match_python ... ok
test engines::tests::sha256_successfully_verified_before_installing_direct_binary ... ok
test engines::tests::download_extracts_only_named_zip_member_and_validates_executable ... ok
test tests::rpc_rejects_bad_http_json_and_rpc_shapes_without_panics_or_secrets ... ok
test tests::real_aria2_random_port_ownership_idle_and_http_download ... ok

test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 20.04s

     Running unittests src\lib.rs (rs\target\debug\deps\afudm_extras-07a294a9ea39abda.exe)

running 97 tests
test g1::automation::tests::komut_parcalama_tirnaklari_korur ... ok
test g1::chrome::tests::calisirken_ikinci_baslatma_reddedilir ... ok
test g1::chrome::tests::baslangic_durumu_bos ... ok
test g1::chrome::tests::bekle_bitsin_sonuc_hazirsa_hemen_doner ... ok
test g1::guncelleme::tests::durum_baslangici_hazir ... ok
test g1::chrome::tests::betik_yer_tutucularini_doldurur ... ok
test g1::guncelleme::tests::fix8_ps_tum_tirnaklari_kacirir ... ok
test g1::guncelleme::tests::fix8_govde_zaman_asimi_sinirli ... ok
test g1::guncelleme::tests::kontrol_taslak_ve_yabanci_url_reddedilir ... ok
test g1::guncelleme::tests::kontrol_verisinden_yeni_surum_bulur ... ok
test g1::guncelleme::tests::parcala_surum_karsilastirir ... ok
test g1::guncelleme::tests::uygulama_betigi_yer_tutucuları_doldurur ... ok
test g1::guncelleme::tests::fix8_beklenen_boyut_asimi_reddedilir ... ok
test g1::guncelleme::tests::otomatik_ayar_ve_son_kontrol ... ok
test g1::automation::tests::iptal_ve_yeniden_deneme ... ok
test g1::guncelleme::tests::uygula_mesgul_ve_paketsiz_dallari ... ok
test g1::guncelleme::tests::yanlis_sha_reddedilir_ve_zip_silinir ... ok
test g1::automation::tests::etkin_adimlar_kuyruga_girer ... ok
test g1::automation::tests::rename_ve_move_yolu_gunceller ... ok
test g1::reliability::tests::proxy_kimligi_atilir ... ok
test g1::automation::tests::checksum_dogru_ve_yanlis ... ok
test g1::guncelleme::tests::omniget_corrupt_update_state_is_quarantined ... ok
test g1::guncelleme::tests::hazir_degisen_dosyada_false_doner ... ok
test g1::guncelleme::tests::indir_dogrula_ve_bekle_dali ... ok
test g1::reliability::tests::maskele_anahtar_adina_gore_gizler ... ok
test g2::cerez::tests::bozuk_cerez_atilir ... ok
test g2::cerez::tests::cookie_basligi_ve_netscape ... ok
test g1::reliability::tests::mask_url_ve_metin_sirlarini_siler ... ok
test g1::reliability::tests::kurtarma_olmayan_satir_hata_verir ... ok
test g1::reliability::tests::saglik_temiz_veritabaninda_ok ... ok
test g1::reliability::tests::kurtarma_onizlemesi_sunucudan_dogrular ... ok
test g2::eklenti::tests::surum_karsilastirma ... ok
test g2::cerez::tests::boyut_siniri_uygulanir ... ok
test g2::eklenti::tests::manifest_normallestirir ... ok
test g2::eklenti::tests::manifest_hatalari ... ok
test g2::eklenti::tests::ayar_dogrulama_atomik ... ok
test g2::eklenti::tests::paket_incele_ve_ozet ... ok
test g2::eklenti_servis::tests::host_baslatma_bu_surumde_basarisiz ... ok
test g2::eklenti_servis::tests::islem_durumu_ve_iptal_ozeti ... ok
test g2::cerez::tests::dosya_yaz_sil_ve_artik_temizligi ... ok
test g2::govde_tests::bos_govde_nesne_sayilir_ve_hatalar_python_metniyle_doner ... ok
test g2::kurallar::tests::baglam_alanlari ... ok
test g2::kurallar::tests::gecersiz_oncelik_hata_verir ... ok
test g2::kurallar::tests::evaluate_oncelik_ve_kullanici ... ok
test g2::kurallar::tests::kosullar_all_ve_any ... ok
test g2::eklenti::tests::uzanti_ve_manifest_yok ... ok
test g2::kurallar::tests::normalize_alanlari_ve_hata ... ok
test g2::eklenti::tests::zip_slip_reddedilir ... ok
test g2::linkgrabber::tests::domain_taklit_engellenir ... ok
test g2::linkgrabber::tests::iptal_yeni_probe_baslatmaz ... ok
test g2::linkgrabber::tests::normalize_python_ile_ayni ... ok
test g2::kurallar::tests::regex_ve_boyut ... ok
test g2::linkgrabber::tests::onceki_ve_domainler ... ok
test g2::linkgrabber::tests::probe_eszamanli_ve_onbellek ... ok
test g2::linkgrabber::tests::tekil_les_kurallari ... ok
test g2::py::tests::esitlik_sayisal ... ok
test g2::py::tests::str_ve_int_python_gibi ... ok
test g2::linkgrabber::tests::tur_tahmini ... ok
test g2::py::tests::truthy_python_gibi ... ok
test g2::url_parca::tests::ayristirma_python_ile_ayni ... ok
test g2::url_parca::tests::birlestir_bos_sorguyu_atar ... ok
test g2::url_parca::tests::magnet_semasi_netloc_almaz ... ok
test h::esleme::tests::mobil_kod_suresi_dolunca_reddedilir ... ok
test h::esleme::tests::mobil_kod_eszamanli_yalniz_bir_kisiye_verilir ... ok
test h::esleme::tests::mobil_kod_tek_kullanimlik_ve_veri_dizinine_baglidir ... ok
test h::esleme::tests::pencere_ac_ve_kapat_suresi ... ok
test h::esleme::tests::token_dosyasi_okunur_ve_bos_reddedilir ... ok
test h::paylasim::tests::dar_sunucu_bilinmeyen_token_bos_404 ... ok
test h::paylasim::tests::disposition_ascii_ve_yedek ... ok
test h::paylasim::tests::fix8_ortak_defter_yol_zaman_ve_silmeyi_tutar ... ok
test h::paylasim::tests::govde_bos_ve_bozuk ... ok
test h::paylasim::tests::kok_icinde_sinirlar ... ok
test g2::linkgrabber::tests::panel_filtresi_wildcard_ve_boyut ... ok
test h::paylasim::tests::quote_python_gibi ... ok
test h::paylasim::tests::range_araliklar ... ok
test h::paylasim::tests::range_bos_baslik_tum_dosya ... ok
test h::paylasim::tests::range_gecersizler ... ok
test h::paylasim::tests::token_urlsafe_uzunluk ... ok
test h::smb::tests::bos_cikti_bos_liste ... ok
test h::smb::tests::kok_afudm_network_shares_adinda ... ok
test h::smb::tests::net_share_ciktisi_sadece_afudm_adlarini_alir ... ok
test h::tests::statik_dosyalar_gomulu_ve_python_basliklariyla_gelir ... ok
test h::tunel::tests::baslat_url_dondurur_ve_argumanlar_dogru ... ok
test h::paylasim::tests::dar_sunucu_range_ile_dosya_verir ... ok
test h::tunel::tests::url_bulucu_python_gibi ... ok
test h::tunel::tests::url_yoksa_iki_denemeden_sonra_hata ... ok
test g1::reliability::tests::tani_maskeli_disa_aktarilir ... ok
test g2::linkgrabber::tests::ayiklar_http_ftp_magnet ... ok
test g2::eklenti_servis::entegrasyon::ozet_uyusmazligi_kurulumu_durdurur ... ok
test g2::eklenti_servis::entegrasyon::guncelle_yanlis_paketi_reddeder ... ok
test g1::reliability::tests::fix8_buyuk_zip_girdisi_reddedilir ... ok
test g2::eklenti_servis::entegrasyon::kur_listele_ayar_kaldir_akisi ... ok
test g1::reliability::tests::fix8_yeni_sema_reddedilir ... ok
test g1::reliability::tests::yedek_olusur_listelenir_ve_geri_yuklenir ... ok
test h::tunel::tests::durdur_izleyiciyi_etkisiz_kilar ... ok
test h::tunel::tests::izleyici_surec_cikinca_bir_kez_yeniden_baslatir ... ok
test g1::guncelleme::tests::kontrol_ag_hatasinda_turkce_hata ... ok

test result: ok. 97 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.02s

     Running unittests src\lib.rs (rs\target\debug\deps\afudm_types-3acb32dc4058a786.exe)

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_api

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_core

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_db

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_engine

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_extras

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_types

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

```


### cargo clippy --manifest-path rs\Cargo.toml --all-targets -- -D warnings

Calisma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_301
EXIT 0

```text
cargo.exe :     Checking afudm-api v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-api)
At line:11 char:18
+     $captured = (& cargo @checkArgs 2>&1 | Out-String -Width 4096)
+                  ~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (    Checking af...ates\afudm-api):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.62s
```


### cargo fmt --manifest-path rs\Cargo.toml --all -- --check

Calisma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_301
EXIT 0

```text
```


Dogrulama sonucu: cargo test EXIT 0 (253 passed, 2 ignored, 0 failed); clippy EXIT 0; fmt --check EXIT 0. Yukaridaki NativeCommandError satirlari Windows PowerShell'in Cargo stderr ilerleme mesajlarini bicimlendirmesidir; Cargo cikis kodlari uc kontrolde de 0'dir. Ek dosya duzenleme ihtiyaci veya bekleyen soru yok.
