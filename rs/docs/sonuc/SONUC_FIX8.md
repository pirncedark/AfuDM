# FIX8 inceleme sonucu

Durum: TAMAMLANDI — altı düzeltme uygulandı; istenen tüm kontroller exit code 0 ile geçti.

Kontrol: workspace testleri ve Clippy temiz; uygulama 29/29 test ve Clippy temiz; verify.py 7/7 kontrol geçti; bridge GECTI (113 çağrı, 0 fark). Test süreçlerinin tamamı kapandı.

## Kapsam
- app/src/boot.rs: bekleyen geri yukleme oncesi eski WAL/SHM kaldirilir; kaldirma hatasi geri yuklemeyi durdurur.
- app/src/kopru_h.rs ve crates/afudm-extras/src/h/paylasim.rs: HTTP ve UI tek defteri kullanir; created burada tutulur. Liste JSON alanlari ve sirasi korunur. Silme, toplu durdurma ve son paylasim kontrolu ortak deftere bakar.
- crates/afudm-core/src/queue.rs ve queue/tests.rs: aria2 out icin mevcut probe::guvenli_dosya_adi kullanilir; bos/gecersiz ad reddedilir.
- crates/afudm-extras/src/g1/reliability.rs: ZIP DB girdisi en fazla 2 GiB; sinirli io::copy ile diske akitilir. Integrity ve user_version denetlenir, reddedilen gecici DB temizlenir.
- crates/afudm-extras/src/g1/guncelleme.rs: govde zaman asimi 900 saniye. Release asset boyutu zip_size ile tasinir; asset/content-length sinirindan once yazma durur. ASCII ve dort Unicode tek tirnak iki katina cikarilir.

## Kirmizi -> yesil kaniti
Uygulama: fix8_restore_eski_wal_shm_temizler ve fix8_telefon_paylasimi_ui_defterinde once FAILED; duzeltme sonrasi 2 passed.
Core: fix8_filename_motor_kokunden_cikamaz once FAILED (..\..\Startup\x.exe aria2 out'a aynen gitti); duzeltme sonrasi 1 passed.
Extras: fix8_ps_tum_tirnaklari_kacirir, fix8_govde_zaman_asimi_sinirli, fix8_beklenen_boyut_asimi_reddedilir, fix8_yeni_sema_reddedilir, fix8_buyuk_zip_girdisi_reddedilir once 5 FAILED; duzeltme sonrasi 5 passed.
Ortak defter icin ek yol/zaman/silme testi eklendi.

## Sozlesme ve sinirlar
DB migration ust siniri schema.rs icinde 10 olarak ozel tutuluyor, disa acik sabit yok. Sahiplik siniri nedeniyle baska dosya degistirilmedi: yeni bellek SqliteStore migration sonucu user_version okunarak desteklenen surum bulunur.
Python kaynagi degistirilmedi; kullanici verisi/6810/6811/gercek AfuDM.exe hedeflenmedi. Testler headless ve izole gecici veriyle calisir. release.yml ve scripts/ degistirilmedi. Yasak git komutlari calistirilmadi.
Yeni Python fonksiyonu tasinmadi; gorevdeki alti Rust duzeltmesi uygulandi. Kapsamda todo! kalmadi.

## Python 2.9.x onerisi
📍 C:/Users/afuuu/Desktop/afuproject/AfuDM/core/manager.py:695: istemcinin filename degerini aria2 out'a vermeden tek guvenli dosya adi bilesenine indir; /, \, :, NUL, . ve .. ile kok disina yazmayi onle. Python dosyasina dokunulmadi.

## Gercek kontrol ciktilari
Her komut icin cikis kodu ve son 30 satir:

### `cargo build -p afudm-core -p afudm-extras`

Exit code: 0

```text
   Compiling afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
   Compiling afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.43s
```

### `cargo test`

Exit code: 0

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

### `cargo clippy --all-targets -- -D warnings`

Exit code: 0

```text
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.71s
```

### `cargo clippy --manifest-path app/Cargo.toml -- -D warnings`

Exit code: 0

```text
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 3.28s
```

### `cargo test --manifest-path app/Cargo.toml`

Exit code: 0

```text
test bridge::tests::torrent_metrik_hatasi_hazir_degil_alanini_tasir ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test bridge::tests::servis_hatasi_python_sozlesmesi ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test bridge::tests::ok_ile_nesneye_ok_ekler ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::uuid_biçimi_ve_surumu ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::filtre_ve_arama ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test kopru_h::tests::fix8_telefon_paylasimi_ui_defterinde ... ok
test boot::tests::fix8_restore_eski_wal_shm_temizler ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok

test result: ok. 29 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

```

### `python -B tests_hata/verify.py`

Exit code: 0

```text
build_feature 0
test_feature 0
clippy_feature 0
build_default 0
test_default 0
clippy_default 0
format_owned 0
```

### `python -B tests_hata/hepsi.py --only bridge`

Exit code: 0

```text
BRIDGE sunucu_anahtar_rotasyon: equal=True
BRIDGE sunucu_anahtar_sil: equal=True
BRIDGE sunucu_anahtarlar: equal=True
BRIDGE sunucu_ayarla: equal=True
BRIDGE sunucu_durumu: equal=True
BRIDGE sunucu_istemci_iptal: equal=True
BRIDGE sunucu_istemci_temizle: equal=True
BRIDGE sunucu_istemciler: equal=True
BRIDGE sunucu_kilit_temizle: equal=True
BRIDGE sunucu_profil_etkinlestir: equal=True
BRIDGE sunucu_profil_kaydet: equal=True
BRIDGE sunucu_profil_sil: equal=True
BRIDGE sunucu_profiller: equal=True
BRIDGE sunucu_yeniden: equal=True
BRIDGE surum_bilgi: equal=True
BRIDGE telefon_ayarla: equal=True
BRIDGE telefon_durumu: equal=True
BRIDGE torrent_dosyalari: equal=True
BRIDGE torrent_metrikleri: equal=True
BRIDGE torrent_on_ekle: equal=True
BRIDGE torrent_on_iptal: equal=True
BRIDGE torrent_secimi_ayarla: equal=True
BRIDGE windows_integration_status: equal=True
BRIDGE windows_integration_test: equal=False
BRIDGE reliability_recovery_preview [gecerli]: equal=True
BRIDGE reliability_restore [gecerli]: equal=True
BRIDGE windows_integration_test [gecerli]: equal=True
END bridge
CLEANUP all owned processes stopped: True
RESULT bridge GECTI
```

## Son denetim

### verification

```json
[
  {
    "name": "build_feature",
    "command": [
      "cargo",
      "build",
      "--manifest-path",
      "app/Cargo.toml",
      "--features",
      "test-kapisi",
      "--offline"
    ],
    "exit_code": 0,
    "gate_path_in_binary": true
  },
  {
    "name": "test_feature",
    "command": [
      "cargo",
      "test",
      "--manifest-path",
      "app/Cargo.toml",
      "--features",
      "test-kapisi",
      "--offline"
    ],
    "exit_code": 0
  },
  {
    "name": "clippy_feature",
    "command": [
      "cargo",
      "clippy",
      "--manifest-path",
      "app/Cargo.toml",
      "--features",
      "test-kapisi",
      "--offline",
      "--",
      "-D",
      "warnings"
    ],
    "exit_code": 0
  },
  {
    "name": "build_default",
    "command": [
      "cargo",
      "build",
      "--manifest-path",
      "app/Cargo.toml",
      "--offline"
    ],
    "exit_code": 0,
    "gate_path_in_binary": false
  },
  {
    "name": "test_default",
    "command": [
      "cargo",
      "test",
      "--manifest-path",
      "app/Cargo.toml",
      "--offline"
    ],
    "exit_code": 0
  },
  {
    "name": "clippy_default",
    "command": [
      "cargo",
      "clippy",
      "--manifest-path",
      "app/Cargo.toml",
      "--offline",
      "--",
      "-D",
      "warnings"
    ],
    "exit_code": 0
  },
  {
    "name": "format_owned",
    "command": [
      "rustfmt",
      "--edition",
      "2021",
      "--check",
      "--config",
      "skip_children=true",
      "app/src/main.rs",
      "app/src/test_kapisi.rs"
    ],
    "exit_code": 0
  }
]
```

### bridge

```json
{
  "status": "GECTI",
  "unique_public_methods": 146,
  "called": 113,
  "skipped": 36,
  "differences": 0
}
```

### cleanup

```json
{
  "all_owned_processes_stopped": true,
  "remaining": []
}
```

Yalniz degistirilen 7 Rust dosyasinda rustfmt --edition 2021 --check --config skip_children=true: exit code 0.
Git diff --check (yalniz sahip olunan Rust dosyalari): exit code 0.
