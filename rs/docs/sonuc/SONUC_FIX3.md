# SONUC FIX3: Entegrasyon-3, uyum testi farklarını kapatma

Durum: 9 madde uygulandı. `cargo test -p afudm-api -p afudm-extras` yeşil (98 test), `cargo clippy -p afudm-api -p afudm-extras --all-targets -- -D warnings` temiz. Uyum testi (`tests_parity`) KOŞULMADI (görev gereği; F3 bitince Claude koşacak).

## Yazılan dosyalar

- `crates\afudm-api\src\lib.rs`: hata gövdesi (`hata_yaniti`, `bilinmeyen_yol`), `/capabilities` varsayılanı, `/probe` 400, `/settings` GET 404, `/windows-integration` rotası ve `windows_unavailable` kaldırıldı.
- `crates\afudm-api\src\tests.rs`: eşleme testi güncellendi, `python_uyumlu_rotalar_ve_yetenekler` eklendi.
- `crates\afudm-api\Cargo.toml`: `afudm-engine` bağımlılığı (`motorlar` için). Döngü yok: engine yalnız `afudm-types`'a bağlı.
- `crates\afudm-extras\Cargo.toml`: `afudm-api` bağımlılığı (ortak hata gövdesi için). Döngü yok.
- `crates\afudm-extras\src\g1\mod.rs`: `/reliability/*` POST, GET 404; hata gövdesi ortak yardımcıya bağlı.
- `crates\afudm-extras\src\g2\mod.rs`: `afu_hatasi` ortak yardımcıya bağlı (`/rules`, `/eklenti*`, `/linkgrabber`).
- `crates\afudm-extras\src\h\mod.rs`: statik dosyalar gömülü; `afu_hata` ortak yardımcıya bağlı; birim testi eklendi.
- `docs\API_SOZLESME.md`: hata sözleşmesi, `/capabilities`, Windows uçları ve `/m` satırları güncellendi.
- `Cargo.lock`: cargo tarafından güncellendi (yeni bağımlılık kenarları).

## Madde durumu

1. ✅ Hata gövdesi: `afudm_api::hata_yaniti` tek kaynak. `{ok,code,message,error}`. g1, g2 ve h bunu çağırıyor. Döngü olmadığı için kopya yapılmadı.
2. ✅ `/capabilities`: Store kaydı yoksa Python varsayılanı (200). 503 yok.
3. ✅ `GET /settings`: 404 `BILINMEYEN_YOL`. POST aynı.
4. ⚠ `/control` boş gid: GID_GEREKLI EKLENMEDİ. Gerekçe: Python gerçekte `KAYIT_YOK` 400 `kayit bulunamadi: ` döndürüyor (ham sonuç `sonuc_son.json` adım 4.5; kaynak `core\manager.py:851` `pause` → `KayitYok`). Rust'ta `pause("")` `NotFound` üretiyor ve eşleme artık 400 `KAYIT_YOK` veriyor; metin birebir aynı. Görev metnindeki "GID_GEREKLI" Python paritesine aykırı olurdu. Karar Claude'a: görev metni mi, gerçek Python davranışı mı.
5. ✅ `/probe`: her hata 400 (Python GET /probe ile aynı). Boş url yt-dlp'den `Engine` hatası alıyor; eşleme 400 `INTERNAL` ve genel metin veriyor (Python 7.2 ile birebir).
6. ✅ `/control` resume aria2 hatası: 500 `INTERNAL` `beklenmeyen bir sunucu hatasi olustu` (Python 4.2 ile birebir). Not: bu eşleme TÜM Engine hatalarına uygulanır (Python'da aria2/yt-dlp hataları genel 500'dür). Engine iç metni artık istemciye gitmez.
7. ✅ `/reliability/integrity`, `/backup`, `/diagnostics-preview`, `/diagnostics-export`: Python yalnız POST (`api\server.py` do_POST); Rust POST, GET 404. Görevde yalnız iki uç yazıyordu; backup ve diagnostics-export da aynı durumda olduğu için onlar da düzeltildi.
8. ✅ Statik dosyalar: kök neden `app_dir\ui` klasörünün exe yanında olmaması (404). Çözüm: `include_bytes!` ile `rs\app\ui` (`mobil.html`, `manifest.webmanifest`, `i18n.js`, `sw.js`, `icon.png`) gömüldü. `rs\app\ui` ile `P\ui` dosyaları `cmp` ile birebir aynı doğrulandı. Başlıklar Python ile aynı (`no-store`, `no-cache`, `Service-Worker-Allowed: /`, `public, max-age=31536000`).
   - Gömme handler'ları `h\mod.rs` içinde. `h\mobil.rs` görev listesinde olmadığı için DEĞİŞTİRİLMEDİ. Artık router tarafından kullanılmıyor ama `pub` olduğu için clippy uyarmıyor. H ekibi silmeli.
9. ✅ `/windows-integration`: afudm-api rotası ve `windows_unavailable` kaldırıldı. Şu an afudm-api'de bu yol 404 döner; F3 app tarafında GET ve POST rotasını eklemeli. `API_SOZLESME.md` buna göre güncellendi.

## Kararlar ve sözleşme notları (Claude onayı gerekli)

- Eşleme (Python `core/hata.py` hata_json ile aynı): Invalid → 400 BAD_REQUEST; NotFound → 400 KAYIT_YOK (önceki 404); Io → 400 IO; Unavailable → 503 KULLANILAMIYOR; Engine, Db, Other → 500 INTERNAL + genel metin.
- Bu, önceki "Engine 502" sözleşmesinin yerine geçiyor. Görev "Python paritesi esas" dediği için uygulandı; API_SOZLESME güncellendi.
- `/capabilities` `surum` ve `uzanti_surumu` Rust derleme sürümünü (`CARGO_PKG_VERSION`, 3.0.0) yazar. Python 2.9.6 yazıyor. Birebir eşleştirmek sahte sürüm bildirmek olurdu; bu fark bilerek bırakıldı.
- `/capabilities` `motorlar` alanı `afudm_engine::engines::durum` ile gerçek motor durumundan üretiliyor.

## Test çıktısı (son koşu, özet)

```
cargo test -p afudm-api -p afudm-extras
test result: ok. 10 passed; 0 failed   (afudm-api, lib + tests)
test result: ok. 88 passed; 0 failed   (afudm-extras)
cargo clippy -p afudm-api -p afudm-extras --all-targets -- -D warnings
    Finished `dev` profile ... (uyarı yok)
```

Yeni/güncellenen testler: `add_control_torrent_and_error_mapping` (eşleme ve probe 400), `python_uyumlu_rotalar_ve_yetenekler` (GET /settings 404, windows 404, capabilities 200 + anahtarlar, /renew hata gövdesi), `h::tests::statik_dosyalar_gomulu_ve_python_basliklariyla_gelir`.

Boşluk: g1 reliability uçlarının POST/GET yöntem davranışı için ayrı birim testi yok. extras'ta `ManagerApi` sahtesi gerektiği için pahalıydı; doğrulama Claude'un `tests_parity` koşusuna kaldı.

## Bilinen eksik / kapsam dışı

- `app\` (F3) ve `tests_parity\` (T1) dokunulmadı. `app\Cargo.toml` ve `app\Cargo.lock` git'te değişik görünüyor; bunlar benim değil.
- `h\mobil.rs` artık ölü kod (yukarıda).
- `/windows-integration` F3'te.
- Uyum testi koşulmadı.
