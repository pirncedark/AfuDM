# SONUC_FIX9 — PR #122 CI düzeltmeleri

## Durum ve dosyalar
Önceki turun değişiklikleri git status/git diff ile incelendi; yeniden uygulanmadı. Bu turda doğrulamalar tamamlandı. Görevdeki düzeltmeler yerelde doğrulandı; tam offline paket 84 geçti / 5 başarısız sonucuyla tamamlandı. CI tamamen yeşil olarak raporlanamaz.

- `rs/crates/afudm-db/src/tests.rs`: kaynak DB yoksa eprintln ve erken return; varsa eski kopya doğrulaması çalışır.
- `tests/release_tools_test.py`: ci.yml PyInstaller kontrolü korunur. release.yml Rust betiğinin arşivlemeden önce çağrılması, cargo build release/locked/manifest argümanları, hata durumunda durulması ve exe kopyalamanın paketlemeden önce olması doğrulanır. Görev dosyasının bu dosyaya özel izni uygulandı.
- `rs/app/ui/app.js`: mobil indirme URL'si ayrıştırılır; http/https/ftp/blob kabul edilir. javascript/data ve bozuk URL'ler engellenir.
- `rs/app/ui/i18n.js`: innerHTML yerine metin düğümleri ve b/em elemanları kurulur; bilinmeyen anahtar metin olarak gösterilir.
- `rs/docs/sonuc/SONUC_FIX9.md`: bu rapor.

`git show origin/main:ui/app.js` ve `git show origin/main:ui/i18n.js` ile karşılaştırıldı: main'de de doğrudan href ve innerHTML mevcut. Hazır düzeltme bulunmadığından görevde izin verilen güvenli DOM yaklaşımı kullanıldı.

Yeni Python fonksiyonu taşınmadı; sözleşme değişikliği ve kapsamda todo! yok. Başka kaynak dosya düzenlenmedi. Yasak git komutları çalıştırılmadı, pencere açılmadı. Kullanıcının 6810/6811 portlarındaki uygulamasına istek yapılmadı. DB testi mevcut kaynak dosyaları yalnız okur/kopyalar; SQLite geçici kopyaya bağlanır.

## Gerçek doğrulama çıktıları

### cargo test --manifest-path rs/Cargo.toml -p afudm-db
Çıkış: 0
```text
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.20s
     Running unittests src\lib.rs (rs\target\debug\deps\afudm_db-6d5dbbc59a628e15.exe)

running 14 tests
test tests::settings_normalization_and_portable_paths ... ok
test tests::settings_boundaries_normalize_and_report_all_without_secrets ... ok
test tests::rules_are_ordered_and_failed_replace_rolls_back ... ok
test tests::plugins_preserve_install_time_decode_and_filter_updates ... ok
test tests::durable_automation_resume_retry_cancel ... ok
test tests::scheduling_selections_queries_and_json_values ... ok
test tests::store_settings_downloads_and_events ... ok
test tests::pending_expiry_corruption_and_failed_write_preserve_request ... ok
test tests::shared_store_is_send_sync_and_serializes_concurrent_writes ... ok
test tests::categories_names_folder_tree_network_and_last_folder ... ok
test tests::pending_requests_persist_deduplicate_protect_secrets_and_restore ... ok
test tests::legacy_v2_existing_gid_and_auto_accept_migration ... ok
test tests::real_database_byte_copy_preserves_python_table_counts ... ok
test tests::migrations_zero_two_four_and_ten_preserve_records_and_reopen ... ok

test result: ok. 14 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.16s

   Doc-tests afudm_db

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

Kaynak DB mevcutken test ayrıca --nocapture ile geçti. Kaynak-yok yolu koddan incelendi; kaynak dosyası taşınarak/silinerek taklit edilmedi.

### python -B tests/release_tools_test.py
Çıkış: 0
```text
.........
----------------------------------------------------------------------
Ran 9 tests in 0.003s

OK
```

### cargo build --manifest-path rs/Cargo.toml -p afudm-db
Çıkış: 0
```text
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.14s
```

### cargo clippy --manifest-path rs/Cargo.toml -p afudm-db -- -D warnings
Çıkış: 0
```text
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.19s
```

### cargo fmt --manifest-path rs/Cargo.toml --all -- --check
Çıkış: 0; çıktı yok.

### node --check rs/app/ui/app.js ve node --check rs/app/ui/i18n.js
Her ikisi çıkış: 0; çıktı yok.

### Rust UI için doğrudan Node VM davranış kontrolü
Dosyalar değiştirilmeden stdin üzerinden gerçek Rust UI kaynakları çalıştırıldı. DOM taklidi innerHTML atamasında hata verir. TR/EN chr.m2/m3/m4 metinleri ve b/em biçimi, zararlı/bilinmeyen anahtarlar, beş izinli URL ve javascript/data/bozuk URL reddi assert ile denetlendi.
Çıkış: 0
```text
PASS Rust UI i18n: TR/EN formatting and hostile DOM keys
PASS Rust UI mobile: 5 safe URLs accepted; javascript/data/malformed rejected
```

### git diff --check ve dosya biçimi
Çıkış: 0; çıktı yok. Dört değişen kaynak dosya UTF-8 ve LF (CRLF=0).

## Doğrulama sınırları
CodeQL CLI bu ortamda yok. GitHub CodeQL analizinde iki bildirimin kapandığı henüz doğrulanmadı; davranış kontrolleri CodeQL çalıştırmasının yerine geçmez.

## Tam çevrimdışı paket
### powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1
Çıkış: 1. Gerçek son çıktı:
```text
GECTI  tests/tepsi_test.py
GECTI  tests/tunel_test.py
GECTI  tests/uzanti_boyut_test.py
GECTI  tests/video_ui_test.py
GECTI  tests/arayuz_debug_duzeltme_test.mjs
GECTI  tests/extension_pending_message_test.mjs
GECTI  tests/maestro_test.mjs

SONUC: 84 gecti, 5 basarisiz
```
Başarısız testler ve gerçek hata parçaları:
```text
BASARISIZ  tests/download_window_ui_test.mjs (exit 1)
AssertionError [ERR_ASSERTION]: Playwright download prompt UI failed
null !== 0
at file:///C:/Users/afuuu/Desktop/afuproject/AfuDM_rs/tests/download_window_ui_test.mjs:146:8
BASARISIZ  tests/download_window_layout_test.py (exit 1)
BASARISIZ  tests/ui_startup_test.py (exit 1)
BASARISIZ  tests/ui_ux_gate_test.py (exit 1)
PermissionError: [WinError 5] Erişim engellendi
BASARISIZ  tests/guc_test.py (exit 1)
[DUSTU] kart adi geldi
[DUSTU] MAC 6 bloktan olusuyor
BASARISIZ: kart adi geldi, MAC 6 bloktan olusuyor
```
Üç Python Playwright testinde asyncio/windows_utils.py pipe oluştururken CreateFile erişimi reddedildi. Node download_window_ui_test.mjs aynı Python layout testini spawnSync ile çağırır; çocuk süreç status=null döndü. Bu Node hatasının WinError 5 ile aynı nedenden kaynaklandığı kesin doğrulanmadı. Güç testinde ortamdan beklenen kart/MAC bilgisi alınamadı.

Geçenler arasında release_tools_test.py ve runner içindeki diğer Node UI testleri var. Bu eski Python UI testlerinin Rust UI kopyasını hedeflemediği için ayrıca gerçek rs/app/ui dosyaları üzerinde yukarıdaki Node VM denetimi yapıldı.

## Kalan doğrulama
- GitHub'da CodeQL'i yeniden çalıştırıp iki bildirimin kapandığını doğrula.
- Süreç oluşturma izni ve ağ kartı erişimi olan CI ortamında tam offline paketi yeniden çalıştır.
- Bu beş başarısız testin kaynakları görevdeki izinli dosyalar arasında değil; değiştirilmedi. Kaynak düzeltmesi gerekirse ayrı sahiplik/görev gerekli.
