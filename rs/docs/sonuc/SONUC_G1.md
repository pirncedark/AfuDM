# SONUC: Ekip G1 (güncelleme, güvenilirlik, bütünlük, otomasyon) — TAMAM (sözleşme notlarıyla)

## Durum
- ✅ `butunluk.rs` içindeki 3 `todo!()` (butunluk_tara, butunluk_onar, butunluk_hepsini_tara) doldu. Crate genelinde `todo!()` kalmadı (`grep` ile doğrulandı).
- ✅ `g1/` modülü: guncelleme, reliability, automation, chrome. HTTP rotaları (`/reliability/*`) ve `pub fn` arayüzleri var.
- ⚠ Dört madde sözleşmede karşılığı olmadığı için eksik ya da farklı (aşağıda "Sözleşme sorunları"): restore'un canlı swap'ı, health/restart_engine, tani.engines, extract için tar/gz.
- Commit atılmadı (görev kuralı). Çalışan AfuDM.exe ve 6811 portuna dokunulmadı. GitHub'a gerçek istek atılmadı; güncelleme testleri yerel sahte sunucuyla yapıldı.

## Yazılan / değiştirilen dosyalar
- `rs\crates\afudm-core\src\butunluk.rs` — 3 `todo!()` gövdesi + tara / aria2_kontrol_tam_mi / artik_kontrol_dosyasini_sil / blok_indir / onarim_iscisi (Python `_repair_thread`) / head_kontrol. 18 test (Python `tests/butunluk_test.py` senaryoları + 13 Ekim "rastgele veri JSON gibi başlasa bozuk sayılmaz" testi dahil).
- `rs\crates\afudm-core\Cargo.toml` — `afudm-db.workspace = true` (yalnız `[dependencies]` sonuna; testte SqliteStore için). `winreg = "0.56"` satırı başka bir ajan tarafından `[target.'cfg(windows)'.dependencies]` altına eklenmişti; `queue/proxy.rs` için gerekli, bu yüzden çökme nedeniydi (`winreg` bulunamadı). Benim yanlışlıkla eklediğim çift satır silindi.
- `rs\crates\afudm-extras\Cargo.toml` — `[dependencies]` sonuna: rusqlite, sha2, sha1, md-5, zip (deflate), regex, chrono, ureq, afudm-db. Ayrıca yeni bir `[target.'cfg(windows)'.dependencies]` başlığı altında `winreg` (kural "yalnız [dependencies]" idi; bu bir sapma, onay gerekir).
- `rs\crates\afudm-extras\src\g1\mod.rs` — router (`/reliability/integrity`, `/backup`, `/diagnostics-preview`, `/diagnostics-export`; hata biçimi afudm-api ile aynı), test sahte HTTP sunucusu.
- `rs\crates\afudm-extras\src\g1\guncelleme.rs` — kontrol, indir_ve_dogrula, hazir, uygulama_betigi, uygula_paket, `Guncelleme` durum nesnesi (kontrol_ve_kaydet, indir, durum, otomatik_ayarla, son_kontrol, uygula). 11 test.
- `rs\crates\afudm-extras\src\g1\uygula.ps1` — Python `_uygulama_betigi` şablonu (birebir; yer tutucular: __BASE__, __SOURCE__, __BACKUP__, __PID__).
- `rs\crates\afudm-extras\src\g1\reliability.rs` — integrity, backup (VACUUM INTO + zip), backups, restore (doğrulama + hazırlama), diagnostics_preview / export, mask / maskele / proxy_maskele, recovery_preview. 8 test.
- `rs\crates\afudm-extras\src\g1\automation.rs` — `Otomasyon` (enqueue_download, retry, cancel, start/stop, döngü), adımlar: checksum, extract(zip), move, rename, script, notify, power; `uyut()` (powrprof FFI). 5 test.
- `rs\crates\afudm-extras\src\g1\chrome.rs` + `chrome_ekle.ps1` — chrome_yolu (winreg App Paths + ortam), sayfayi_ac, panoya_kopyala, betik_dosyasi (UTF-8 BOM), `OtomatikEkleme`, bekle_bitsin. Betik Python BETIK'iyle birebir taşındı. 4 test.
- `rs\docs\sonuc\SONUC_G1.md` — bu dosya.

## Python → Rust fonksiyon tablosu
| Python | Rust | Durum |
|---|---|---|
| manager.butunluk_tara (2447) | core butunluk::butunluk_tara | ✅ |
| manager.butunluk_onar (2468) + _repair_thread | butunluk::butunluk_onar + onarim_iscisi | ✅ (Python'daki ölü 403/404 dalı da atlandı; HTTP hata metni ureq'den gelir ⚠) |
| manager.butunluk_hepsini_tara (2614) | butunluk::butunluk_hepsini_tara | ✅ |
| butunluk.tara / aria2_kontrol_tam_mi / artik_kontrol_dosyasini_sil / blok_indir | aynı adlar | ✅ (if/elif zinciri ve HTML/JSON ezmesi birebir) |
| guncelleme.kontrol / _parcala | guncelleme::kontrol, parcala, kontrol_verisinden | ✅ (Python tarafında gerçek API çağrısı test edilmedi; yalnız ağ-hatası yolu gerçek ağda test edildi) |
| guncelleme.indir_ve_dogrula | guncelleme::indir_ve_dogrula (+ _onekli test varyantı) | ✅ |
| guncelleme.hazir | guncelleme::hazir | ✅ |
| guncelleme._uygulama_betigi / uygula | uygulama_betigi, uygula_paket | ✅ (PowerShell betiği birebir; spawn yalnız son kontrolden sonra) |
| guncelleme._guvenli_zip_yolu | guvenli_zip_yolu | ✅ |
| app.guncelleme_kontrol / otomatik_ayarla / son_kontrol / indir / durum / uygula | Guncelleme::kontrol_ve_kaydet / otomatik_ayarla / son_kontrol / indir / durum / uygula (+ mesgul_nedeni) | ✅ (bekleyen_var parametresi ⚠ aşağıda) |
| reliability.integrity | reliability::integrity | ✅ |
| reliability.backup / backups | reliability::backup / backups | ✅ (manifest içeriği Python ile aynı) |
| reliability.restore | reliability::restore | ⚠ yedek doğrulanır, `restore_bekleyen.db` olarak hazırlanır; canlı swap yok (bkz. sözleşme 1) |
| reliability.diagnostics_preview / export | reliability::diagnostics_preview / diagnostics_export | ⚠ "engines" anahtarı yok (sözleşme 2) |
| reliability._sir_maskele / mask / proxy_maskele | maskele, mask, proxy_maskele | ✅ (regex yüklenemezse hepsi `***`: kapalı taraf) |
| reliability.recovery_preview | reliability::recovery_preview | ✅ (hata türü adları Python'a yakın: HTTPError / URLError / ValueError) |
| reliability.health / restart_engine | — | ❌ sözleşmede rpc.alive / daemon yok (sözleşme 2) |
| automation.enqueue_download / retry / cancel | Otomasyon::enqueue_download / retry / cancel | ✅ |
| automation._run (checksum) | calistir → hesapla (md5, sha1, sha256, sha384, sha512) | ✅ |
| automation._run (extract) | calistir → arsiv_cikar | ⚠ yalnız .zip (Python tar/gz da açar) |
| automation._run (move / rename) | calistir (move / rename dalları) | ✅ |
| automation._run (script) | betik_calistir (tırnak korumalı ayrıştırma, 300 sn zaman aşımı) | ✅ |
| automation._run (notify) | ui.notify("AfuDM", ...) | ✅ |
| automation._run (power) + guc.uyut | guc_adimi + uyut (SetSuspendState) | ✅ kodu yazıldı; gerçek uyku/kapatma test edilmedi |
| chrome_kurulum.chrome_yolu / sayfayi_ac / panoya_kopyala / _betik_dosyasi | chrome::chrome_yolu / sayfayi_ac / panoya_kopyala / betik_dosyasi | ✅ |
| chrome_kurulum.OtomatikEkleme | chrome::OtomatikEkleme (baslat / durum) | ✅ (`once` geri çağrısı yok ⚠; betik stderr'i yutuluyor ⚠) |
| chrome_kurulum.bekle_bitsin | chrome::bekle_bitsin | ✅ |

## Sözleşme sorunları (Claude / Ekip F için)
1. **Restore'un canlı swap'ı yok.** `Store` trait'inde bağlantı kapatma / yeniden açma yok. Rust `restore` yedeği doğrulayıp `data\restore_bekleyen.db` olarak bırakıyor ve `restart_required: true, staged: ...` döndürüyor. Uygulama açılışında bu dosyanın `afudm.db` yerine uygulanması gerekir (Python'un `shutil.move` + `Store` yeniden kurulumu karşılığı). Yapılmazsa geri yükleme fiilen uygulanmaz.
2. **ManagerApi'de eksikler:** `rpc.alive()` ve `daemon.stop/start` yok → `reliability_health` ve `reliability_restart_engine` yazılamadı; `engines.durum()` yok → diagnostics'te `engines` anahtarı eksik.
3. **Otomasyon bağlantısı:** `Manager` yapısında `automation` alanı yok. Python `_on_complete` içinde `automation.enqueue_download` ve `butunluk_tara` çağrılıyor; Rust tarafında bu bağlantı kurulmalı (`Otomasyon::new(store, ui)` + `start()`), `queue`'nun tamamlanma kancası Claude'un kararı.
4. **Onay bekleyen işler:** `guncelleme_uygula` Python'da `self._bekleyenler.ozet()` kullanıyor; bu sözleşmede yok. Rust `uygula(..., bekleyen_var: bool, ...)` alıyor — app bu değeri hesaplayıp vermeli.
5. **Paketli sürüm bayrağı:** `Guncelleme::new(data, base, paketli)` ve `uygula`'nın `paketli` argümanı app tarafından verilir (Python `sys.frozen` karşılığı).
6. **Cargo kuralı sapması:** extras'ta yeni `[target.'cfg(windows)'.dependencies]` başlığı açıldı; afudm-db her iki crate'te `[dependencies]` altında (sadece test kullanıyor; `[dev-dependencies]` olsaydı daha temiz olurdu). Onay gerekir.
7. **Pre-existing build hatası:** `afudm-core` `queue/proxy.rs` `winreg` kullanıyor ama core Cargo.toml'da yoktu; başka bir ajan ekledi, derleme düzeldi.
8. **2.9.x güncelleyici uyumu (paket düzeni):** Python 2.9.x `indir_ve_dogrula` şunları bekliyor, 3.0 paketi aynen uymalı: zip adı `AfuDM-v<sürüm>-win64.zip`; yanında `AfuDM-v<sürüm>-win64.zip.sha256` (içerik `<hash>  <zip adı>`); zip içinde `AfuDM/AfuDM.exe` (tek üst klasör `AfuDM`). 2.9.x'in uygula betiği üst düzey öğeleri kopyalar (`data`, `downloads`, `plugins` hariç; `engine` birleştirilir). Rust tarafı aynı düzeni bekler ve üretir. Sürüm karşılaştırması: Rust `CARGO_PKG_VERSION` (3.0.0) kullanır; Python 2.9.6'dır (bilinçli).
9. **Sembolik bağlantılar:** Rust `tarama` her iki yerde de (indir ve hazir) sembolik bağlantıları atlar; Python'da indir sırasında dahil ediliyordu. Zip'te zaten bulunmamaları beklendiğinden etkisi yok, ama fark olarak not edildi.

## Test ve doğrulama (gerçek çıktı)
- `cargo test -p afudm-core` → `test result: ok. 83 passed; 0 failed; 2 ignored` (butunluk: 18 test).
- `cargo test -p afudm-extras` → `test result: ok. 87 passed; 0 failed; 0 ignored` (g1: 28 test; g2/h testleri de yeşil).
- `cargo clippy -p afudm-core -- -D warnings` → çıkış kodu 0.
- `cargo clippy -p afudm-extras -- -D warnings` → çıkış kodu 0.
- `rustfmt --check` (g1 dosyaları ve butunluk.rs) → temiz. Satır sonları LF (CR sayısı 0).
- Test kapsamı: butunluk (tara, aria2 kontrol dosyası, blok_indir 206/HTML reddi, onar hata yolu, hepsini_tara); guncelleme (sürüm ayrıştırma, GitHub yanıt ayrıştırma, taslak ve yabancı URL reddi, ağ hatası metni, sahte sunucudan indirme + sha256 doğrulama, yanlış sha reddi, hazir değişiklik algılama, betik yer tutucuları, son kontrol, mesgul dalları); reliability (maskeleme, proxy kimliği, bütünlük, yedek→listele→geri yükle→dış yol reddi, tanı dışa aktarımında sır yok, kurtarma önizlemesi sahte sunucuyla); automation (kuyruk, checksum doğru/yanlış, rename + move, iptal/yeniden deneme, script tırnak ayrıştırma); chrome (betik yer tutucuları, durum makinesi, bekle_bitsin).
- **Doğrulanmadı (canlı):** GitHub'a gerçek istek; Chrome UI otomasyonu (fiziksel test gerekir); uyku/kapatma (güç adımı test edilmedi, test ortamını kapatmamak için). Kullanıcının fiziksel testi önerilir.
