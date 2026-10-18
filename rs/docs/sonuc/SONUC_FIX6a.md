# SONUC FIX6a: köprü yanıt biçimi farkları (app\src + tests_hata köprü listesi)

Durum: KALDI. `python -B tests_hata\hepsi.py --only bridge` son koşuda KALDI. Kalan iki sayılan satır Rust biçim farkı değil: biri 6b'ye iletildi, diğeri test verisi eksikliği.

## Yazılan dosyalar
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app\src\bridge.rs`
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app\src\entegrasyon.rs`
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app\src\kopru_h.rs`
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_hata\scenarios.py` (yalnız `bridge()` ve iki yardımcı sabit/fonksiyon; 6b karşılaştırma mantığına dokunulmadı)
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_hata\bin\AfuDM_test.exe` yeniden derlenip kopyalandı (verify.py akışı, app\src dışı; 6b bilgilensin).

Kullanıcının 6810/6811 AfuDM'ine, AfuDM\data'ya ve AfuDM.exe'ye dokunulmadı. Git komutu çalıştırılmadı. Windows kayıt defterine yazan hiçbir test çalıştırılmadı (apply/remove harness'te atlandı).

## Koordinatör kararları ve uygulanışı
1. boot_hata: `sistem_durumu` Python biçimine döndü (boot_hata yok). Boot hatası artık hem ctx hazırsa store log'una (`boot_hatasi`) yazılır hem de Rust'a özel `tani_boot` komutundan okunur (`{ok, boot_hata}`). `#[allow(dead_code)]` kaldırıldı; boot.rs/test_kapisi.rs değişmedi.
2. İstisna vakaları: her biri için geçerli + geçersiz çift.
   - Geçerli vakalar ayrı satır olarak ölçülür (`... [gecerli]`): `reliability_restore` (aynı koşuda üretilen yedek), `reliability_recovery_preview` (izole veride indirme satırı aranır), `windows_integration_test` (`torrent`, salt okuma).
   - Geçersiz vakalar `muaf: Python istisna, Rust zarif hata` olarak işaretlendi ve ölçüme girmez.
   - `windows_integration_apply` / `windows_integration_remove`: harness'te tamamen atlandı (muaf; kayıt defterine yazmaz).
3. butunluk_hepsini_tara: 6b'ye koordinatör iletecek. Ayrıntı aşağıda.

## Sonuç tablosu (son koşu, bridge_run4)
- ✅ Eşit (ölçülen): automation_cancel, automation_retry, bekleyen_iptal, control, link_yenile, motor_durumu, retry, sistem_durumu, surum_bilgi, torrent_dosyalari, torrent_metrikleri, torrent_on_ekle, torrent_on_iptal, torrent_secimi_ayarla, windows_integration_status, reliability_restore [gecerli], windows_integration_test [gecerli]
- ⚠ Açık, ölçülen: butunluk_hepsini_tara (6b, crates tarafı), reliability_recovery_preview [gecerli] (izole veride indirme satırı yok; gate'i düşürüyor)
- ⚪ Muaf (ölçüme girmez): reliability_recovery_preview (geçersiz), reliability_restore (geçersiz), windows_integration_test (geçersiz), windows_integration_apply, windows_integration_remove

## Düzeltmeler (Python sözleşmesine)
- `bekleyen_iptal`: kimlik yoksa da `{ok:true}`.
- `surum_bilgi`: `{surum, uzanti}`; uzanti `extension\manifest.json` sürümü.
- `motor_durumu`: `engines::durum` (tüm Python alanları).
- `sistem_durumu`: `torrent.{torrent,magnet}.{kayitli,varsayilan}`. Önceki Rust yapısı arayüzün beklediği yapıyla uyuşmuyordu (UI hatası). `varsayilan` için `entegrasyon::varsayilan_mi` eklendi (UserChoice, yoksa HKCR, yalnız okur).
- `windows_integration_status`: `windows_rota::durum` + torrent/startup/notify/defender bindirmesi.
- `windows_integration_apply/remove`: protocol/context/afup ve bilinmeyen kimlik `windows_rota`'ya gider (Python `self.windows`). Notify/defender store bayrağı.
- `windows_integration_test`: notify/defender Python biçimi; diğerleri `windows_rota::test`.
- `retry`, `link_yenile`: başarıda `ok:true` + manager alanları; hata `{ok, code:"ISLEM_HATASI", message, error}`.
- `control`: başarı `{ok, action, gid}`; orphan remove; bilinmeyen eylem `BILINMEYEN_EYLEM`.
- `butunluk_tara/onar/hepsini_tara` (kopru_h.rs): hata `servis_hata` biçimi.
- Torrent metotları: hata `{ok, error_code:"engine", error, error_details}`; metrics hatası ayrıca `hazir_degil`, `neden`.
- `automation_retry/cancel`: `{ok:true, job}`.
- `reliability_restore`: Python'da olmayan `staged` alanı köprü yanıtından çıkarıldı (arayüz kullanmıyordu).
- Protokol yardımcıları (`protokol_ac/kapat/kayitli`, `PROTOKOL`) artık kullanılmadığı için kaldırıldı.

## butunluk_hepsini_tara (6b'ye iletilecek)
- Python: harness'te `{ok:false, code, message, error}` döndü (ISLEM_HATASI).
- Rust: `{ok, sonuclar, taranan}` başarı döndü. Kaynak `crates\afudm-core\src\butunluk.rs:101`. Rust per-öğe hatayı `sonuclar` içine yazıyor.
- Python `butunluk_tara` per-öğe için `{ok:false, durum:"bulunamadi"}` döndürüyor; dış istisnanın hangi öğeden çıktığı bu turda kanıtlanamadı. 6b incelemeli.

## Açık kalan iki madde
1. `reliability_recovery_preview [gecerli]`: izole test verisinde indirme satırı yok, Python ve Rust ikisi de "gecerli girdi uretilemedi" döndü; harness bunu eşit saymıyor, gate düşüyor. Çözüm: harness'in ya da önceki bir vakanın izole veriye bir indirme satırı eklemesi (tests_hata 6b/Claude kararı).
2. `butunluk_hepsini_tara` farkı (yukarıda).

## Bilinen eksikler (kapatılmadı)
- `control`: `pause_all`, `resume_all`, `ayarla` yok.
- `windows_integration_test` notify: Python bildirim gösterir; Rust yalnız bayrağı okur.
- `windows_integration_status.scan`: sabit `idle` (Defender taraması yok).
- `sistem_durumu.torrent.kayitli`: Rust komut eşitliği (önceki semantik korundu); Python kayıt anahtarı varlığı.
- `motor_durumu.ilerleme`: `{}`.
- `rustfmt --check`: bridge.rs'de bu görevle ilgisiz eski biçim farkları var; tüm dosya biçimlendirilmedi.

## Doğrulama (gerçek çıktı)
`cargo test --manifest-path app/Cargo.toml --features test-kapisi --offline`
```
test result: ok. 28 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s
```
`cargo clippy --manifest-path app/Cargo.toml --features test-kapisi --offline -- -D warnings`
```
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.61s
```
`python -B tests_hata\hepsi.py --only bridge` (son koşu, bridge_run4)
```
BRIDGE butunluk_hepsini_tara: equal=False
BRIDGE reliability_recovery_preview: equal=False        (geçersiz, muaf)
BRIDGE reliability_restore: equal=False                 (geçersiz, muaf)
BRIDGE windows_integration_test: equal=False            (geçersiz, muaf)
BRIDGE reliability_recovery_preview [gecerli]: equal=False
BRIDGE reliability_restore [gecerli]: equal=True
BRIDGE windows_integration_test [gecerli]: equal=True
CLEANUP all owned processes stopped: True
RESULT bridge KALDI
EXIT=1
```

## Süreç ve dosya notları
- Benim koşum süreçleri harness tarafından kapatıldı (CLEANUP True).
- 6b ajanına ait süreçler (ör. `hepsi.py --only crash`, pid 46092 ve alt süreçleri) ve 03:00–06:12 arasından kalan `afudm_t1_*` süreçleri dokunulmadan bırakıldı.
- Commit edilmemiş, benim olmayan değişiklikler: `app/Cargo.toml`, `app/src/main.rs`, `app/src/test_kapisi.rs`. Dokunulmadı.
- Notam'a yazılmadı.
