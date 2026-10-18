# SONUÇ 301B — OmniGet fikirleri ve APK uyum denetimi

Durum (tur 5/5): 403 merdiveni, HTML hata kontrolü ve izinli JSON okuyucularının karantinası doğrulandı. APK uyumu ve PR incelemesi raporlandı. Çökme testi FINISHED, exit_code=0; Rust HTTP ve torrent GECTI, tüm test süreçleri kapandı. Tek açık kapsam engeli: 301A sahipli listener.rs read_record karantinası.

## Beşinci tur — nihai doğrulama

Önce git status ve git diff incelendi. Üretim kodu değiştirilmedi; yalnız bu rapor güncellendi. Önceki PID 48660 tamamlandı; ikinci crash çalıştırıcısı açılmadı.

| Taraf | İndirme | Sonuç | SHA doğru | Yeniden başlatma sonrası Range |
| --- | --- | --- | --- | --- |
| py | http | KALDI | false | false |
| rs | http | GECTI | true | true |
| py | torrent | KALDI | false | false |
| rs | torrent | GECTI | true | true |

Rust HTTP ve torrent için SQLite bütünlüğü `ok`, son dosya taramasında bozuk parça 0. Python referansında açılış kurtarması bulunmadığından iki KALDI satırı korunmuştur; hepsi.py crash kapısı yalnız Rust satırlarını değerlendirir.

Gerçek `301b-crash-tur3.log` son satırları:

```text
CRASH torrent progress [0.288, 0.282]
CRASH torrent py: stopping at 41.2%; session=0 bytes
CRASH torrent rs: stopping at 40.9%; session=0 bytes
CRASH torrent py: restarting; resume deadline 300 seconds
CRASH torrent py: KALDI
CRASH torrent rs: restarting; resume deadline 300 seconds
CRASH torrent rs: GECTI
END crash
CLEANUP all owned processes stopped: True
RESULT crash GECTI
```

Gerçek `runner_progress.json`:

```json
{"status":"FINISHED","selected":["crash"],"completed":["crash"],"exit_code":0}
```

Gerçek `cleanup.json`:

```json
{"all_owned_processes_stopped":true,"remaining":[]}
```

Bu turdaki kontroller:

- `cargo test --manifest-path rs/Cargo.toml omniget -- --nocapture`: exit 0; API 1 + core 5 + db 2 + engine 1 + extras 1 = 10 test geçti.
- `python -B rs/tests_hata/test_301b.py`: exit 0; 1 test, 1.052s; gerçek tellStatus aşağıda.
- `git diff --check`: exit 0, çıktı boş.
- Workspace/app tam testleri, clippy, fmt ve verify.py önceki turda geçen günlükleriyle aşağıda kayıtlıdır; üretim kodu değişmediği için bu tur tekrarlanmadı.

```text
Real tellStatus: {"errorCode": "22", "errorMessage": "The response status is not successful. status=403", "status": "error"}
Ran 1 test in 1.052s
OK
```

📍 Kalan iş: `rs/crates/afudm-api/src/listener.rs:424` içindeki `read_record`, satır 425 üzerinde JSON ayrıştırma hatasını karantinaya almadan döndürüyor. GOREV_301B bu dosyaya yazmayı açıkça yasaklıyor; 301A sahibi bu yolu karantina + güvenli varsayılan davranışı ve bozuk kayıt testiyle tamamlamalı. Bu nedenle 3. maddenin tüm uygulama kapsamı tamamen bitti sayılmıyor.

**APK tarafında 3.0 için zorunlu güncelleme yok.** Yerel PR #90 incelemesinde TorrentWorker.kt metin çatışmaları raporlu; birleştirme yapılmadı.

Yasak git işlemi, pencere veya emülatör açılması ve kullanıcı data klasörüne yazma yapılmadı.

## Dördüncü tur — güncel doğrulama

`git status --short` ve `git diff` incelendi; yapılan uygulama tekrarlanmadı. 3. turdaki PID 48660 hâlâ çalıştığından ikinci crash süreci başlatılmadı. 301A sahibinin dosyalarına yazılmadı.

| Komut | Çıkış | Günlük |
| --- | --- | --- |
| cargo test --manifest-path rs/Cargo.toml | 0 | [workspace](301b-tur4-workspace-test.log) |
| cargo clippy --manifest-path rs/Cargo.toml --all-targets -- -D warnings | 0 | [clippy](301b-tur4-clippy.log) |
| cargo fmt --manifest-path rs/Cargo.toml --all -- --check | 0, çıktı boş | [fmt](301b-tur4-fmt.log) |
| cargo test --manifest-path rs/app/Cargo.toml | 0, 30 test geçti | [app](301b-tur4-app-test.log) |
| python -B rs/tests_hata/verify.py | 0, 7 kontrol geçti | [verify](301b-tur4-verify.log) |
| python -B rs/tests_hata/test_301b.py | 0, 1 test geçti, 1.066s | Gerçek tellStatus: errorCode=22, mesajda status=403 |
| git diff --check | 0, çıktı boş | — |

Gerçek verify çıktısı:

```text
verify exit=0
build_feature 0
test_feature 0
clippy_feature 0
build_default 0
test_default 0
clippy_default 0
format_owned 0
```

### Dördüncü tur crash devam kaydı (16:17:46)

Yeni crash süreci başlatılmadı. Önceki PID 48660 çalışıyor. Rust HTTP sonucu GECTI: SHA doğru, sıfır bozuk parça, yeniden başlatma sonrası Range isteği var. Python HTTP ve torrent referansları KALDI. Rust torrent yeniden başladı; sonuç henüz yok. Tam çalıştırma bitene kadar exit 0 veya temizlik iddiası yapılmaz. `cleanup.json` eski çalıştırmaya ait olabilir; yalnız runner FINISHED olduktan sonra kullanılmalı.

Devam gerekirse: PID 48660, `301b-crash-tur3.log`, `301b-crash-tur3.err.log` ve `rs/tests_hata/rapor/runner_progress.json` okunmalı. Yeni test başlatılmamalı.

## Üçüncü tur — doğrulama ve devam kaydı

Git status/diff incelendi; önceki uygulama tekrarlanmadı. Üretim kodu değiştirilmedi.

`cargo test --manifest-path rs/Cargo.toml omniget -- --nocapture`: exit 0; API 1, core 5, db 2, engine 1, extras 1 olmak üzere **10 test geçti**.

`python -B rs/tests_hata/test_301b.py`: exit 0; 1 test, 1.035 saniye. Gerçek aria2 çıktısı: `errorCode=22`, `errorMessage=The response status is not successful. status=403`.

`git diff --check`: exit 0, çıktı boş.

### Çökme testi devam noktası

Önceki `301b-crash.log` yalnız Python HTTP başarısızlığını ve Rust yeniden başlatma başlangıcını içerir; tam test sonucu değildir. Önceki hepsi.py süreci kalmadığı doğrulandı.

Yeni komut: `python -B rs/tests_hata/hepsi.py --only crash`. Start-Process -WindowStyle Hidden ile başlatıldı. PID: `48660` (301b-crash-tur3.pid). Günlük: [301b-crash-tur3.log](301b-crash-tur3.log); stderr: [301b-crash-tur3.err.log](301b-crash-tur3.err.log).

Sonraki turda **yeni test başlatmadan önce** bu PID ve günlük kontrol edilmeli. `rs/tests_hata/rapor/crash.json` HTTP/torrent sonuçlarını, runner_progress.json bitiş/exit_code bilgisini, cleanup.json test süreçlerinin kapanmasını içerir. Rapor dizini başka çalıştırıcılarla ortaktır; yalnız selected=[crash] ve bu çalıştırmanın zamanına ait sonuçlar kullanılmalı.

Kapsam engeli sürüyor: `rs/crates/afudm-api/src/listener.rs` içindeki read_record bozuk JSON için karantina yapmıyor. Görev dosyaya yazmayı açıkça yasaklıyor; 301A sahibi tarafından tamamlanmalı.

Üçüncü tur ara gözlemi: Python HTTP referansı tekrar KALDI; Rust yeniden başlatıldı. Teste ait geçici SQLite dosyası salt okunur kontrol edildiğinde Rust indirmesi `active`, `done_bytes=90603520`, `total_bytes=201326592` durumundaydı (çökme öncesindeki yaklaşık %40 ilerlemenin üzerinde). Bu yalnız ara gözlemdir; SHA ve devam isteği doğrulanmadan GECTI sayılmadı.

## Uygulananlar

1. **403 merdiveni:** Yalnız HTTP(S), aria2 errorCode `22` ve mesajda ayrı sayı olarak `403` olduğunda bir kez yeniden deneme. Deneme options içinde kalıcıdır; ikinci 403 normal hata olur. Aynı kaynak, gerçek dir/out, kayıtlı başlıklar ve bellekteki çerezler korunur. Eksik User-Agent/Accept/Range/Sec-Fetch başlıkları eklenir. Olay loglanır, sırlar loglanmaz. Yeni gid aynı DB kaydına bağlanır; eski gid snapshot listesinden çıkarılır. Oturum kimlik bilgileri güvenlik nedeniyle temizlenmiş işler otomatik denenmez.
2. **HTML hata kontrolü:** HTTP tamamlanınca ilk 512 bayt okunur. Kısa dosya, baştaki boşluk/BOM ve büyük harfler desteklenir. Beklenmeyen HTML için DB ve snapshot hata durumuna geçer; tamamlanma kancaları çalışmaz. Dosya korunur. .htm/.html veya açıkça Content-Type text/html istenmiş dosyalar kabul edilir. Mesaj: “Sunucu dosya yerine bir hata sayfası gönderdi. Bağlantıyı tarayıcıda açıp yeniden dene.”
3. **JSON karantinası:** Bozuk durum dosyası aynı klasörde `.corrupt-YYYYmmdd-HHMMSS` adıyla saklanır, loglanır ve varsayılanla devam edilir. Saat UTC'dir. Aynı saniyedeki yedekler ezilmez; boş sonraki zaman adı seçilir. Hard-link hedefi atomik ayırır, ardından kaynak kaldırılır. İçerik/sırlar loglanmaz. Yeni bağımlılık yok.

## Dosyalar ve kapsam

- rs/crates/afudm-core/src/queue.rs; queue/safety.rs (yeni), sync.rs, shaping.rs, tests.rs
- rs/crates/afudm-db/src/kaydet.rs ve tests.rs
- rs/crates/afudm-engine/src/daemon.rs ve tests.rs
- rs/crates/afudm-api/src/security.rs ve tests.rs
- rs/crates/afudm-extras/src/g1/guncelleme.rs (testler aynı dosyada)
- rs/tests_hata/test_301b.py; bu rapor ve kontrol günlükleri

Python'dan taşınan yeni fonksiyon yok; mevcut Rust sync_aria2/tamamlandi/launch akışları ve JSON okuma yolları güncellendi.

OmniGet kodu açılmadı/kopyalanmadı/uyarlanmadı. Pencere ve emülatör açılmadı. Yasak git işlemleri yapılmadı. Kullanıcının data klasörü ve 6810/6811 kullanılmadı. AfuTube ve AfuDM_Mobile yalnız okundu. 301A sahibinin dosyalarına yazılmadı. Python karşılaştırma testleri kaynak dosyaları yalnız okuyarak geçici dizinde çalıştı.

## JSON okuma envanteri

Arama: `rg -n 'serde_json::(from_str|from_slice|from_reader)' rs/crates rs/app/src`.

| Modül / disk dosyası | Sonuç |
| --- | --- |
| core/queue.rs — aria2.auth-required.json | Karantina + boş liste |
| engine/daemon.rs — aria2.auth-required.json | Karantina + boş liste |
| db/kaydet.rs — pending_downloads.json | Nanosaniye adı takvim biçimine getirildi; sürüm/ID doğrulaması korunur |
| api/security.rs — api_endpoint.json | Token yenilemede karantina; varsayılan endpoint yok |
| extras/g1/guncelleme.rs — guncelleme/hazir.json | Karantina + hazır değil |
| extras/g1/guncelleme.rs — guncelleme/kontrol.json | Karantina + zaman=0 |
| api/listener.rs read_record — listener kuyruk JSON kayıtları | KALAN: ayrıştırma hatası Result döndürür. Görev bu dosyaya dokunmayı yasaklar; 301A sahibinin ele alması gerekir. |
| app/bridge.rs — extension/manifest.json | Durum/ayar değil, kurulu eklentinin paket bildirimi; değiştirilmedi |

Diğer eşleşmeler SQLite hücreleri, ağ/API/RPC yanıtları, yt-dlp stdout/Chrome olayları, indirilmiş dosya içeriği doğrulaması ve test girdileridir; disk durum dosyası değildir.

## APK uyumu — salt okunur

**APK tarafında 3.0 için zorunlu güncelleme yok.**

Görevdeki 6811/X-AfuDM-Token/pair/snapshot/add/share_create/dosya taramasında Kotlin/Java/TS/TSX eşleşmesi bulunmadı.

- AfuTube downloader/DownloadEngine.kt WorkManager başlatır; DownloadWorker.kt cihazdaki YoutubeDL, TorrentWorker.kt cihazdaki aria2c motorunu kullanır. Masaüstü HTTP API bağlantısı bulunmadı.
- AfuDM_Mobile/src/services/DownloadService.ts Expo FileSystem.createDownloadResumable ile cihazda indirir; src/app/browser.tsx dış cobalt.tools API'sini çağırır. Masaüstü eşleştirme/QR istemcisi bulunmadı.
- 301A QR/eşleştirme değişikliğinden etkilenen mevcut APK çağrısı yok; Rust endpointleriyle karşılaştırılacak masaüstü API çağrısı bulunmuyor.

## PR #90 — yerel origin referansları

Fetch yapılmadı; PR'nin güncel sunucu durumu doğrulanmadı. Görevdeki #90/dal esas alındı. Birleştirme yapılmadı.

`git log --oneline origin/main..origin/feat/afutube-klasor`:

```text
ac2975c feat(afutube): indirmeleri gorunur afutube klasorune kaydet
99ec760 feat(afutube): indirmelere klasoru acma ve paylasma
```

`git diff --stat origin/main...origin/feat/afutube-klasor`: 11 dosya, 331 ekleme, 19 silme. DownloadFolder.kt, DownloadActions.kt, bunların JUnit testleri, DownloadEngine/DownloadWorker/TorrentWorker/DownloadsScreen, FileProvider yolları ve Gradle bağımlılıkları değişir.

İçerik: Download/afutube görünür klasörü, Android MediaStore yayımlama, eski/yeni geçici klasörlerde yarım dosya temizliği, klasör açma/paylaşma eylemleri.

`git merge-tree <merge-base> origin/main origin/feat/afutube-klasor`: TorrentWorker.kt içinde iki metin çatışması var. DownloadWorker.kt ve downloader/build.gradle.kts iki tarafta değişse de metinsel çatışma işareti yok. TorrentWorker değişiklikleri mevcut aria2c akışına uyarlanmalı. İlk turdaki --write-tree denemesi ortak git nesne dizinine yazma izni nedeniyle reddedildi; salt okunur üç parametreli biçimle inceleme tamamlandı.

## Test yaklaşımı ve ilk tur

403, HTML ve bozuk auth JSON testleri önce mevcut uygulamada başarısız izlendi (3 başarısız). Pending karantina adı testi eski nanosaniye biçiminde başarısız oldu. Uygulama sonrası hedefli testler geçti.

İlk turdaki gerçek aria2 testi:

```text
Real tellStatus: {"errorCode": "22", "errorMessage": "The response status is not successful. status=403", "status": "error"}
Ran 1 test in 1.382s
OK
```

İlk tur genel Rust testi extras test exe'sinde geçici os error 32 dosya kilidine takıldı; ikinci tur tam çalıştırma geçti. İlk tur verify build_feature sonrasında kesilmişti; ikinci tur 7 adımı da geçti.

## İkinci tur kontrolleri — gerçek çıktı

### cargo test --manifest-path rs/Cargo.toml

Exit: 0

[301b-workspace-test.log](301b-workspace-test.log)

```text
test result: ok. 16 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.24s
test result: ok. 110 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out; finished in 4.06s
test result: ok. 16 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.27s
test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 20.46s
test result: ok. 97 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.03s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
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

### cargo clippy --manifest-path rs/Cargo.toml --all-targets -- -D warnings

Exit: 0

[301b-clippy.log](301b-clippy.log)

```text
cargo :     Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-core)
At line:2 char:1
+ cargo clippy --manifest-path rs/Cargo.toml --all-targets -- -D warnin ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (    Checking af...tes\afudm-core):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

    Checking afudm-api v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-api)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 2.10s
```

### cargo test --manifest-path rs/app/Cargo.toml

Exit: 0

[301b-app-test.log](301b-app-test.log)

```text
test bridge::tests::torrent_metrik_hatasi_hazir_degil_alanini_tasir ... ok
test kopru_g::tests::defender_durum_varsayilani_idle ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::uuid_biçimi_ve_surumu ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::fix8_telefon_paylasimi_ui_defterinde ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test yonetim::tests::filtre_ve_arama ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test yonetim::tests::proxy_yalniz_loopback_peer_icin_guvenilir ... ok
test boot::tests::fix8_restore_eski_wal_shm_temizler ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok

test result: ok. 30 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

```

### python -B rs/tests_hata/verify.py

Exit: 0

[301b-verify.log](301b-verify.log)

```text
build_feature 0
test_feature 0
clippy_feature 0
build_default 0
test_default 0
clippy_default 0
format_owned 0
```

### cargo fmt --manifest-path rs/Cargo.toml --all -- --check

Exit: 0; stdout/stderr empty.

### PR #90 diff --stat (raw)

```text
 AfuTube/app/src/main/res/xml/file_paths.xml        |   2 +
 AfuTube/downloader/build.gradle.kts                |   1 +
 .../com/afudm/afutube/downloader/DownloadEngine.kt |  11 +-
 .../com/afudm/afutube/downloader/DownloadFolder.kt | 137 +++++++++++++++++++++
 .../com/afudm/afutube/downloader/DownloadWorker.kt |   9 +-
 .../com/afudm/afutube/downloader/TorrentWorker.kt  |   5 +-
 .../afudm/afutube/downloader/DownloadFolderTest.kt |  39 ++++++
 AfuTube/feature/downloads/build.gradle.kts         |   3 +
 .../afutube/feature/downloads/DownloadActions.kt   |  79 ++++++++++++
 .../afutube/feature/downloads/DownloadsScreen.kt   |  35 ++++--
 .../feature/downloads/DownloadActionsTest.kt       |  29 +++++
 11 files changed, 331 insertions(+), 19 deletions(-)
```
