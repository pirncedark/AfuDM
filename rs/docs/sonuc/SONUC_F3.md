# SONUC F3: Tauri köprüsünü tamamlama (Ekip F3)

Durum: KISMİ. 8 maddenin 7'si uygulandı; madde 3 (Python Api metotlarının tamamı) YAPILMADI, yalnız bir alt kümesi bağlandı. "henüz yok" listesinin büyük bölümü kalıyor (aşağıda).

## Madde durumu

| # | Madde | Durum | Not |
|---|---|---|---|
| 1 | Core dışa açma + kaydet_bilgi / probe_link | ✅ | Core dışa açma (detect_kind, is_supported_source, magnet_infohash, guess_name, clean_title, gecmis_sources, find_duplicate, hiz_limiti_kb, apply_settings) ve `queue::probe_url_info` başka ekip (Entegrasyon-2) tarafından yapıldı; ben yalnız köprüyü bağladım (`kaydet_bilgi`, `probe_link`). |
| 2 | reliability_restart_engine | ✅ | `IdleRpc::restart()` (afudm-engine/src/idle.rs): daemon.stop (oturum kaydı dahil) + start(20 sn), sleeping=false. Manager aynı IdleRpc'yi tuttuğu için rpc referansı değişmez. Köprü: `reliability_restart_engine`. |
| 3 | Python Api metotlarının tamamı | ⚠ KISMİ | Aşağıda "bağlanan" ve "henüz yok" listeleri. |
| 4 | LinkGrabber paneli iletimi | ✅ | Python `window.afudmLinkgrabber(metin, dosya)` (app.js:2804) `eval` ile çağrılır. Rust `open_linkgrabber` metni bekleyen olarak saklar, pencereyi açar; sayfa hazır olunca (`tauri_kopru.js` load → `sayfa_hazir` komutu, yalnız ana pencere) bekleyeni teslim eder. Eski `afudm-linkgrabber` olay yayını kaldırıldı (dinleyen yoktu). |
| 5 | Güncelleme zamanlaması | ✅ (kod + derleme; gerçek indirme/uygulama test edilmedi) | `app/src/guncelleme_zamanla.rs`: açılıştan 120 sn sonra ve 6 saatte bir; 24 saat önbellek; otomatik açıksa paketli kurulumda indirir ve durum "bitti" olunca `uygula(otomatik=true)`; "bekle" dönerse 60 sn'de bir yeniden dener (en fazla 6 saat). |
| 6 | Video/indirme tamamlanma yoklaması | ✅ (kod; pencere kapalıyken davranış test edilmedi) | `app/src/izleme.rs`: motor uykudayken 5 sn, aktifken 0.5 sn aralıkla `snapshot()` çağırır (tamamlanma snapshot okunurken tetiklenir: `queue::shaping::snapshot`). Uykudayken snapshot ÇAĞRILMAZ (IdleRpc her çağrıda motoru uyandırır). |
| 7 | shutdown_when_done / sleep_when_done | ✅ (kod; gerçek kapatma/uyku çalıştırılmadı) | `app/src/guc.rs`: tamamlanma kancası (`tamamlandi_kancasi_ekle`). Kapatma: `shutdown /s /t 60`; kapatma kapalıysa uyku: 20 sn bekle, hâlâ boşsa `rundll32 powrprof.dll,SetSuspendState 0,0,0`. Python `_on_complete` ile aynı öncelik sırası ve "yeni iş var" iptali. |
| 8 | torrent_dosyalari Json | ✅ | Köprü artık core'un döndürdüğü `hazir_degil`, `neden`, `gid`, `dosyalar` alanlarını aynen taşır (`hazir_degil=false` varsayımı kaldırıldı). |

Ek madde (Entegrasyon/koordinatör isteği): `/windows-integration` HTTP rotası → ✅ `app/src/windows_rota.rs` (GET durum, POST {id, action=apply|remove|test}); `boot.rs` içinde `with_auth`'tan önce birleşik router'a merge edildi. afudm-api'ye dokunulmadı.

## Madde 3 — bağlanan komutlar (bridge.rs dispatch)

Yeni bağlananlar: `kaydet_bilgi`, `probe_link`, `settings_save`, `clear_finished`, `loglar`, `link_yenile`, `automation_jobs`, `rules_list`, `item_yolu`, `dosya_ac`, `panoya_kopyala`, `panodan_oku`, `reliability_restart_engine`, `sayfa_hazir` (yeni Tauri komutu).

Önceden bağlı olanlar (değişmedi): pencere, kabuk, klasör, reliability (integrity/backup/backups/diagnostics/restore/health), güncelleme (kontrol/durum/otomatik/son_kontrol/indir/uygula), automation_retry/cancel, eklenti_listesi/etkinlestir, motor (snapshot, peers, seed_*, tracker_tara, torrent_*, control, retry).

## Madde 3 — henüz yok (kalan, Python yeri ile)

- `add_links` (servis.ekle: kısmi başarı raporu, en kritik eksik: arayüzün ana "ekle" akışı), `probe`, `proxy_testi`, `port_durumu`, `ayar_rozetleri`, `defender_scan`, `loglar` dışı olay sorguları.
- `linkgrabber_analiz / suz / iptal / onceki / probe / ekle` (app.py 505-600; core/linkgrabber modülü Rust'ta yok).
- `rules_save`, `rules_simulate`, `download_rules`.
- `cerez`, `chrome_*`, eklenti uçları (`eklenti_kur/incele/guncelle/kaldir/ayar_kaydet/gunluk/islem`).
- `sunucu_*` (durum/ayarla/anahtar/istemci/profil), `start_pairing`, `share_*`, `dosya_sec_ve_paylas`, `agda_paylas`, `telefon_*`.
- `butunluk_tara / onar / hepsini_tara`, `tracker_klasoru_ac`, `seed_tracker_kaydet`, `security_rotate_token`, `motor_indir`, `simdi_uyu`, `guc_durumu`, `ayarlari_dogrula_kaydet` (settings_save ile aynı, alan bazlı hata yok), `open_download_dir` (zaten bağlı).

## Sapmalar ve 📍 notlar

- 📍 Madde 1 `probe_url_info` imzası: `probe_url_info(m, url)` (koordinatör onaylı).
- 📍 Madde 4 alan adı: Python ikinci parametreye `dosya` der; Rust tarafındaki bayrak `uyari` idi, JS'e `dosya` olarak iletilir (anlamı Rust kaynağındaki gibi, doğrulanmadı).
- 📍 Madde 6 aralığı: görev "2–5 sn" diyor; Python'un gerçek değeri POLL_INTERVAL=0.5 sn (aktif) ve 5 sn (uyku). Python değerleri kullanıldı.
- 📍 Madde 7 uyku: Python ctypes `SetSuspendState` yerine aynı API `rundll32` ile çağrılır. Dönüş değeri başarısızlığını yakalamaz (yalnız süreç çıkış kodu).
- 📍 `settings_save`: Python AyarGecersiz alan bazlı hatalar üretir; Rust `update_settings` tek hata döndürdüğü için yanıt `err.invalidValue` genel hatasıdır.
- 📍 `dosya_ac`: Python `os.startfile`; Rust `explorer.exe <dosya>` (aynı sonuç, varsayılan uygulama).
- 📍 `item_yolu` / `dosya_ac`: Python snapshot öğelerinden okur; Rust store kaydından (`dest_dir`, `filename`, `source`) ve `resolve_item_path`'ten okur. Snapshot'ta olmayan ama DB'de olan kayıtlar için sonuç farklı olabilir.
- 📍 `panoya_kopyala`: `clip` UTF-16LE (Python ile aynı). `panodan_oku`: Win32 yerine `Get-Clipboard -Raw` (UTF-8).
- 📍 `/windows-integration` ve köprünün `windows_integration_*` komutları FARKLI yüzeyler: HTTP rotası Python `core/windows_integration.py` (anahtarlar: context, protocol, afup); Api metotları (`app.py windows_integration_status`) aynı durumu torrent/startup/notify/defender ile genişletir. Köprü hâlâ ikinci şekli döndürüyor; birleştirilmedi (Entegrasyon-3 ile karar gerekir).
- 📍 Python hataları (düzeltilmedi, kayıt): (a) `windows_integration.py` ITEMS yolları ve ROOT `r"Software\\Classes"` çift ters eğik çizgi içeriyor; Rust aynı literalleri kullandı. (b) `status()` içinde torrent her zaman `registered: false`. (c) `probe_url_info` 2. adımda `Range: bytes 0-0` (geçersiz biçim; `bytes=0-0` olmalı).
- 📍 Windows entegrasyonu HTTP sürümünde yedek/geri yükleme yok: kaldırmada yalnız AfuDM'in kendi anahtarları silinir (sahiplik `winint_backup_<id>` store anahtarıyla). Python'daki önceki ağacı geri yükleme eksik.
- 📍 `kaydet_bilgi` / `probe_link` kategori tahmini Python `kategori_tahmin` ile aynı fonksiyon (afudm-db) üzerinden.

## Değişen dosyalar (F3, rs\ altında)

- `app\src\bridge.rs`: köprü komutları, LinkGrabber bekleyen/teslim, `sayfa_hazir`, `Ek.rpc: Arc<IdleRpc>`, `Ek.core: Arc<Manager>`, torrent_dosyalari düzeltmesi, reliability_diagnostics çağrıları (`app_dir` parametresi, G1 imzası değişmişti).
- `app\src\boot.rs`: Ek kurulumu, tamamlanma kancası (guc), zamanlayıcılar (guncelleme_zamanla, izleme), windows_rota merge, modül yorumu düzeltmesi (clippy).
- `app\src\guc.rs` (yeni), `app\src\guncelleme_zamanla.rs` (yeni), `app\src\izleme.rs` (yeni), `app\src\windows_rota.rs` (yeni).
- `app\src\main.rs`: modül kayıtları, `sayfa_hazir` komut kaydı.
- `app\Cargo.toml`: `axum = "0.8"` (afudm-api ile aynı sürüm).
- `app\ui\tauri_kopru.js`: LinkGrabber olay dinleyicisi → load'da `sayfa_hazir`. (Koordinatör app\ui'nin Entegrasyon-3'e ait olduğunu bildirdi; bu yalnız köprü dosyası, gerekli değişiklik.)
- `crates\afudm-engine\src\idle.rs`: `IdleRpc::restart()`.
- `docs\sonuc\SONUC_F3.md` (bu dosya).

Çakışma notu: Çalışma sırasında `queue.rs`, `queue/probe.rs`, `queue/tests.rs`, `bridge.rs`, `boot.rs`, `main.rs`, `guncelleme_zamanla.rs`, `izleme.rs` ve `reliability.rs` başka oturumlar tarafından da değiştirildi. Benim değişikliklerim korundu; başkalarının değişiklikleri geri alınmadı. `afudm-core/src/queue*` ve `afudm-extras/src/g1/reliability.rs` bana ait değil; yalnız köprü tarafındaki çağrıları uyarladım.

## Doğrulama (gerçek çıktılar)

Clippy (`cargo clippy --manifest-path app\Cargo.toml -- -D warnings`), son çalıştırma:
```
    Checking afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.94s
CLIPPY_EXIT=0
```
(Not: `afudm-extras` g1/mod.rs'te kullanılmayan `serde_json::json` uyarısı bir ara görünüp kayboldu; diğer ekip dosyası.)

Test (`cargo test -p afudm-core -p afudm-extras -p afudm-engine`), son çalıştırma:
```
test result: ok. 98 passed; 0 failed; 2 ignored; ...   (afudm-core)
test result: ok. 11 passed; 0 failed; ...               (afudm-extras)
test result: ok. 86 passed; 0 failed; ...               (afudm-engine)
```
Engine testi bir önceki turda 87 idi, şimdi 86; bu değişiklik benim kodumdan gelmiyor (yeni test eklemedim, engine testini silmedim). Diff'i kontrol edilmeli.

Release build (`cargo build --release --manifest-path app\Cargo.toml`): `Finished release profile [optimized] target(s) in 2m 38s`, çıkış 0. Exe: `app\target\release\AfuDM.exe` (14291456 bayt).

Headless uçtan uca (izole kopya: `scratchpad\hedef\AfuDM.exe`, AFUDM_PORT=6851, veri `hedef\data`, indirme `hedef\downloads`; yerel Range destekli sunucu 6852; pencere açılmadı; kullanıcının 3 Python AfuDM süreci dokunulmadan kaldı):
- `/ping` → `{"app":"AfuDM","ok":true}` (boot ~20 sn).
- HTTP `/add` (8388608 bayt): gid `d55e33be5cf608ef`, tamamlandı; SHA-256 kaynak ve indirilen dosyada eşit: `2f3b1e615c8780b4c977d6270cb147ba400e0f29248d10dbd20cbb2a4b1cf657`. Otomasyon `notify` işi `complete`.
- Torrent (`/add` yerel .torrent, web-seed `url-list` = 6852): gid `45b543fb3e6d1890`, `completedLength=8388608 / totalLength=8388608`, SHA-256 eşit. Durum `active` (seed aşamasında, seed-ratio 1.0). Torrent'in ilk denemesi test kurulumu hatasıydı (önceki test.bin dosyası + Python http.server Range desteksizliği), kod hatası değil.
- `GET /windows-integration` token ile → 200 `{"integrations":{context,protocol,afup,torrent},"ok":true,"scan":{...},"service":{...}}`; token yoksa 401.
- `POST /windows-integration {"id":"context","action":"test"}` → 200 `{"ok":false,"registered":false,...}` (test kayıtlı değil; apply/remove çalıştırılmadı, HKCU'ya yazılmadı).
- `POST` geçersiz action → 400 `{"code":"BAD_REQUEST","error":"action apply, remove veya test olmali",...}`.

Test edilmeyenler (dürüst liste): pencere ve WebView davranışı (LinkGrabber UI teslimi, sürükleme, klasör diyaloğu); shutdown/sleep (kapatma yapılmadı; kod derlendi); güncelleme indirme/uygulama zamanlayıcısı (kod derlendi); reliability_restart_engine (çalıştırılmadı); izleme döngüsünün pencere kapalıyken davranışı; köprü komutlarının tamamı (yalnız HTTP ve kabuk döngüleri canlı test edildi); Windows kayıt defteri yazma (apply/remove bilerek çağrılmadı).

## Sonraki adımlar (önerilen)

1. Madde 3'ün kalan büyük bölümü: önce `add_links` (servis.ekle) ve linkgrabber (analiz/probe/ekle), sonra rules, sunucu/paylaşım/telefon.
2. `windows` yüzeylerini birleştirme kararı (HTTP vs Api).
3. Python hatalarının 📍 kaydı (ROOT çift ters eğik çizgi, torrent registered=false, Range header) kullanıcıya bildirilmeli.
4. Pencere açık testi (LinkGrabber, güncelleme, kapatma/uyku) kullanıcının fiziksel testine kaldı.

Commit yapılmadı (ekip kuralı: commit Claude'da).
