# R1 — Rust yayın hattı

Durum: KISMEN UYGULANDI; YAYINA HAZIR DEĞİL. 2026-10-18.

## Değişen dosyalar

- `.github/workflows/release.yml`: PyInstaller yerine sabit Rust 1.98.1, iki workspace için locked test/clippy, Rust paketleme ve doğrulama. Tag/main kontrolleri, checksum, sürüm notu SHA doldurma ve yayın adımları korunuyor. Python testleri korundu; pywebview yalnız bu testlerin bağımlılığı olarak kaldı.
- `.github/workflows/ci.yml`: Windows Rust fmt/test/clippy işi eklendi. Python işleri korundu.
- `.github/workflows/quality-gate.yml`: aynı Rust işi eklendi, toplu quality-gate sonucuna bağlandı. Python işleri korundu.
- `scripts/build_release_rust.ps1`: sürüm kapısı, locked release build (`--no-default-features`, test-kapisi kapalı), temiz ve benzersiz staging, `AfuDM/AfuDM.exe`, zorunlu motor ve extension, beklenen ZIP ve staging yolları. `-Offline` kullanılabilir. Mevcut ZIP/staging varsa silmek yerine durur.
- `scripts/verify_release.ps1`: varsayılan Python denetimi korundu; `-PackageType Rust` ile tam kök yolları, kullanıcı verisi/yol kaçışı/tekrar kontrolü, x64 PE ve ProductVersion denetimi eklendi.
- `scripts/smoke_test.ps1`: varsayılan Python denetimi korundu. Rust paket denetiminden sonra, aşağıdaki kaynak engeli nedeniyle runtime smoke başarı sonucu üretmez; EXE başlatmadan hata verir.
- `release-please-config.json`: `rs/Cargo.toml` için `$.workspace.package.version`, `rs/app/Cargo.toml` için `$.package.version` TOML updater; Tauri için `$.version` JSON updater eklendi.
- `rs/app/tauri.conf.json`: açık `version: 3.0.0` alanı eklendi.
- Bu sonuç dosyası. Rust TOML sürümleri zaten 3.0.0 olduğu için değiştirilmedi. Python dosyası değiştirilmedi. Yasaklanan git komutları kullanılmadı, pencere açılmadı.

## Paket içeriğinin kaynak gerekçesi

`rs/app/src/main.rs` uygulama dizinini current_exe.parent() ile buluyor; `boot.rs` bu dizini motora iletiyor. `rs/crates/afudm-engine/src/engines.rs` zorunlu motoru `engine/aria2c.exe` yolunda arıyor. yt-dlp, ffmpeg, cloudflared isteğe bağlı; asgari pakete eklenmedi, ihtiyaçta motor yöneticisi indiriyor.

`tauri.conf.json` frontendDist=`ui`; `window.rs` WebviewUrl::App kullanıyor. Tauri codegen önbellek kaynağında, dev_url yokken frontendDist dizininin EmbeddedAssets içine alındığı doğrulandı. Tray simgesi include_image!, yönetim paneli include_bytes! ile gömülüyor. Harici ui/ ve icons/ kopyası gerekmiyor. `kopru_g.rs:791` tarayıcı eklentisini EXE yanındaki extension/ dizininden okuyor; bu dizin pakette var.

Artık gerekmeyen Python paket içerikleri: `_internal/`, Python DLL/stdlib ve PyInstaller yükleyicisi, `core/`, `app.py`, `afuadm.py`, diğer Python modülleri, pywebview/pystray/Pillow/qrcode Python bağımlılıkları, dış `ui/` ve simge kopyaları. README runtime gereksinimi değil. `data/`, downloads ve kullanıcı ayarları pakete alınmıyor. Güncelleme eski Python artıklarını silmez; eski dosyaların kullanıcı kurulumunda kalabilmesi ayrı temizlik işidir.

ZIP adı ve kökü korunur: `AfuDM-v<surum>-win64.zip` → `AfuDM/AfuDM.exe`. T2'nin eski Python güncelleyici provası tekrar yapılmadı; bu görevde üretim ZIP'i oluşmadığı için uyumluluğun yeni uçtan uca provası yok.

## Kapsam dışında kalan engeller / gereken karar

1. `core/surum.py:19` hâlâ **2.9.9**, Rust workspace/app ve Tauri **3.0.0**. İstenen eşitlik kapısı doğru şekilde duruyor. core/surum.py izinli yazma listesinde değil; bu dosyaya 3.0.0 geçişi için ayrı görev gerekiyor. Rust sürümünü eski sürüm gibi göstererek veya kapıyı atlayarak paket üretilmedi.
2. Bu worktree'de `engine/aria2c.exe` yok. Yayın workflow'u mevcut Python motor indirme adımını koruyor; yerel çevrimdışı paket için motorun bu kopyada hazırlanması gerekiyor. Kullanıcının ana kopyasından dosya kopyalanmadı.
3. `rs/crates/afudm-engine/src/daemon.rs:15` RPC başlangıcı 6810, sonu 6830; yeni daemon bu aralığı sabit kullanıyor. Üretim app, API için AFUDM_PORT'u kabul etse de RPC için karşılığı yok. `rs/app/src/main.rs` single-instance ikinci süreci mevcut uygulamanın penceresine yöneltebilir. Gerçek üretim EXE'sini burada başlatmak korunan portlara/pencereye dokunabilir. test-kapisi ile farklı bir EXE'yi sınamak üretim paketinin provası sayılamaz. Bu iki kaynak dosyası yazma listesi dışında. Üretim için izole RPC ve single-instance atlama yolu sağlayan ayrı görev gerekli; ardından Rust runtime smoke uygulanıp geçirilmelidir. Şimdiki smoke bu nedenle yayınlamayı engeller; tamamlanmış bir runtime testi değildir.
4. Taşınabilir EXE'nin temiz Windows ortamındaki WebView2/VC runtime gereksinimleri gerçek paketle sınanmadı. Yayın sunucusunun hazır ortamı son kullanıcı bilgisayarını temsil etmez.

Görevdeki “başka dosya gerekiyorsa dur ve SONUC'ta sor” sınırı gereği yukarıdaki kaynaklara yazılmadı. Kapsam dışı gereken iş: core/surum.py sürüm eşitlemesi ve üretim app/daemon izolasyon desteği. Etkileşimli soru sorulmadı.

## release-please belge doğrulaması

Context7 `/googleapis/release-please`, customizing.md sorgusu başarıyla döndü. TOML için type=toml + path + jsonpath, JSON için type=json + path + jsonpath resmi belgede doğrulandı. İşaret yorumu gerektirmeyen bu yöntem kullanıldı.

Kaynak: https://github.com/googleapis/release-please/blob/main/docs/customizing.md

## Gerçek yerel çıktılar

### Paketleme kapısı

Komut: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release_rust.ps1 -Offline`

```text
version gate: 2.9.9 ['3.0.0', '3.0.0', '3.0.0']
Rust/Tauri/surum.py uyusmuyor
EXIT: 1
```

ZIP üretilmedi. Dolayısıyla gerçek üretim ZIP'i üzerinde verify/smoke BAŞARILI iddiası yok.

### Statik ve olumsuz paket kontrolleri

```text
release.yml YAML OK 3 jobs
ci.yml YAML OK 4 jobs
quality-gate.yml YAML OK 8 jobs
scripts/build_release_rust.ps1 PowerShell parse OK
scripts/verify_release.ps1 PowerShell parse OK
scripts/smoke_test.ps1 PowerShell parse OK
wrong-root rejected OK; exit 1
user-data rejected OK; exit 1
traversal rejected OK; exit 1
missing-engine rejected OK; exit 1
```

Olumsuz kontroller geçici sentetik ZIP'ler kullanır; gerçek release ZIP'i veya başarılı runtime provası değildir. Değişen dosyalarda LF kontrol edildi. git diff --check: exit 0.

### Rust fmt

```text
cargo fmt --manifest-path rs/Cargo.toml --all -- --check
EXIT: 0
cargo fmt --manifest-path rs/app/Cargo.toml --all -- --check
EXIT: 0
```

## Öz denetim ve kararlar

Öz denetim yapıldı; bağımsız ajan incelemesi yapılmadı. Tam yayın provası yokken yayın hazır sonucu verilmedi.

Çalışma sırasında başka işlerin boot.rs, kopru_h.rs, afudm-core queue/tests.rs, extras guncelleme.rs ve reliability.rs dosyalarında değişiklik yaptığı gözlendi. Bu dosyalara müdahale edilmedi. Yukarıdaki testler çalıştırıldıkları kaynak anını doğrular; eşzamanlı değişikliklerin sonraki hali için ortak entegrasyon kapısı tekrar gereklidir.

Release EXE kaynak sürüm kontrolü (çalıştırmadan): ProductVersion=3.0.0, FileVersion=3.0.0.

Son statik kontrolde YAML ayrıştırması tekrar geçti; ci.yml ve quality-gate.yml içindeki mevcut Python/Android/security/package işleri HEAD sürümüyle nesne bazında aynı bulundu (yalnız toplu sonuç işi Rust sonucunu da bekliyor). Değişen tüm R1 dosyaları LF.

Ruling: Sürüm uyumsuzluğu korunarak kapı kapalı bırakıldı; Python sürüm kaynağı kapsam dışında. Maliyet: sürüm eşitlemesi yapılana kadar yayın yok.

Ruling: Üretim runtime smoke güvenli izolasyon desteği gelene kadar hata verir. Maliyet: bu kaynak değişikliği gelene kadar Rust yayın işi yeşil olamaz.

Ruling: Mevcut staging/ZIP otomatik silinmez. Maliyet: aynı çalışma dizininde tekrar paketlemede önceki çıktının sahibi tarafından kaldırılması veya ayrı çalışma kopyası gerekir.

Minor/deferred: Yok. Blokajlar yukarıda açıkça listelenmiştir.

### Doğrulama çıktısı 33795

```text
Finished `release` profile [optimized] target(s) in 3m 43s
```

### Doğrulama çıktısı 72440

```text
test bridge::tests::servis_hatasi_python_sozlesmesi ... ok
test bridge::tests::ok_ile_nesneye_ok_ekler ... ok
test kopru_g::tests::defender_durum_varsayilani_idle ... ok
test bridge::tests::torrent_metrik_hatasi_hazir_degil_alanini_tasir ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test bridge::tests::orphan_metni_iki_bicimi_de_taniyar ... ok
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::uuid_bi�imi_ve_surumu ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test yonetim::tests::filtre_ve_arama ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok

test result: ok. 27 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

EXIT: 0
COMMAND: cargo clippy --locked --offline --manifest-path rs/app/Cargo.toml --all-targets -- -D warnings
    Checking afudm-types v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-types)
    Checking afudm-engine v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-engine)
    Checking afudm-db v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db)
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Checking afudm-api v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-api)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.88s
EXIT: 0
```

### Doğrulama çıktısı 93611

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

EXIT: 0
COMMAND: cargo clippy --locked --offline --manifest-path rs/Cargo.toml --all-targets -- -D warnings
    Checking afudm-types v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-types)
    Checking afudm-db v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db)
    Checking afudm-engine v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-engine)
    Checking afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Checking afudm-api v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-api)
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 3.10s
EXIT: 0
```


## Tur 2/5 ? devam kontrol? (2026-10-18)

?lk i?lem olarak `git status --short`, `git diff --stat` ve `git diff` okundu. ?nceki turda uygulanm?? yay?n hatt? yeniden yaz?lmad?; ?nceki build/test/clippy ?al??malar? tekrarlanmad?. Bu tur yaln?z bu SONUC dosyas? g?ncellendi.

G?ncel kaynakta engeller s?r?yor:

- Python s?r?m? 2.9.9; Rust workspace/app ve Tauri s?r?m? 3.0.0. E?itlik sa?lanm?yor.
- Bu worktree i?inde engine/aria2c.exe yok.
- ?retim main.rs single-instance eklentisini kullan?yor; daemon.rs varsay?lan RPC aral??? 6810?6830. G?venli ?retim smoke izolasyonu hen?z eklenmemi?.

G?revdeki a??k s?n?r: ?Bu listenin d???ndaki dosyaya yazma; ba?ka dosya gerekiyorsa dur ve SONUC'ta sor.? Bu nedenle core/surum.py, main.rs ve daemon.rs de?i?tirilmedi. Kalan zorunlu i? i?in kapsam geni?letilmesi gerekiyor: s?r?m? 3.0.0'a e?itleme, ?retim EXE'sinde izole RPC ve single-instance atlama deste?i; ard?ndan eksik motor haz?rlan?p ger?ek ZIP/verify/runtime smoke provas? yap?lmal?. ?u anda R1 tamamlanm?? veya yay?na haz?r de?ildir.

Bu turda ?al??t?r?lan salt kontrol ??kt?lar?:

```text
VERSION: 2.9.9 ['3.0.0', '3.0.0', '3.0.0'] MATCH: False
LOCAL ENGINE: False
release YAML OK 3 jobs
ci YAML OK 4 jobs
ci existing jobs preserved OK
quality-gate YAML OK 8 jobs
quality-gate existing jobs preserved OK
scripts/build_release_rust.ps1 LF OK
scripts/verify_release.ps1 LF OK
scripts/smoke_test.ps1 LF OK
scripts/build_release_rust.ps1 PowerShell parse OK
scripts/verify_release.ps1 PowerShell parse OK
scripts/smoke_test.ps1 PowerShell parse OK
git diff --check: EXIT 0
```

Yasak git komutlar? ?al??t?r?lmad?. Pencere veya ?retim EXE'si a??lmad?; korunan portlar ve ana kopya kullan?lmad?. Sonraki turda bu ?? engel de?i?mediyse ayn? build/test kontrollerini tekrar etmek ilerleme sa?lamaz.
