# SONUC F4b: kopru_h.rs + yonetim.rs (koordinator kararlari sonrasi, 2. tur)

Durum: TAMAM (derleme/clippy/test/release yesil; Api ad karsilastirmasinda bagli olmayan ad = 0). Canli uctan uca testler yapilmadi (asagida "Test edilmeyenler").

## Degisen / yeni dosyalar

- `app\src\kopru_h.rs`: F4b komutlari (sunucu_*, start_pairing, telefon_*, share_*, agda_paylas, dosya_sec_ve_paylas, paylasim_stop, yerelden_sor, tarayicidan_sor, windows, motor_indir, butunluk_*, guc_durumu, simdi_uyu, reliability_recovery_preview, ayarlari_dogrula_kaydet, ag_konumlari_listele, ana_pencere_kapandi, security_rotate_token, tracker_klasoru_ac, seed_tracker_kaydet).
- `app\src\yonetim.rs` (YENI): yonetim paneli HTTP sunucusu (6821, api/web.py karsiligi), LAN dinleyicisi (telefon), QR (PNG data-URI), internet tuneli + dar paylasim sunucusu.
- `app\src\bridge.rs`: yalniz gorunurluk (`pub(crate)`: kilit, hata, cevap, s/b/n, motor_hazir_degil, ayar_kaydet, gezgin_ac, hidden_cmd, truthy, Kabuk.app) + `TauriUi::kuyruga_ekle` (bekleyen kuyruk, yeni yardimci; mevcut onay/iptal mantigi degismedi).
- `app\src\boot.rs`: 2 satir: `yonlendiriciyi_kaydet(uygulama.clone())` ve `acilista(&ctx, port)` (acilista: lan_erisimi ve sunucu_acik ayarlarina gore dinleyici baslatir).
- `app\src\main.rs`: `mod yonetim;`.
- `app\Cargo.toml`: `qrcode = "0.14"`, `image = { version = "0.25", default-features = false, features = ["png"] }`, `base64 = "0.22"`.
- Yalniz gorunurluk (mantik degismedi): `crates\afudm-api\src\security.rs` (`rotate_token` -> pub), `crates\afudm-api\src\lib.rs` (`pub mod security`), `crates\afudm-core\src\torrent.rs` (`pub mod saglik`, `pub mod trackers`).
- `docs\sonuc\SONUC_F4b.md` (bu dosya). Commit yapilmadi.

## Kararlarin uygulanmasi

1. QR: `qrcode` ile matris; Python `_qr_uret` ile ayni bicim: PNG, `data:image/png;base64,...`, kutu 6 px, kenar 2 modul, koyu `#0f131a`, acik `#e6eaf0`. Bayt-duzeyi cikti Python `qrcode`'unkiyle birebir ayni olmayabilir (kodlayici farki); bicim aynidir.
2. Bes ad:
   - `security_rotate_token`: `afudm_api::security::rotate_token` + `write_endpoint`.
   - `tracker_klasoru_ac`: `afudm_core::torrent::saglik::klasoru_hazirla` + Explorer.
   - `seed_tracker_kaydet`: `afudm_core::torrent::trackers::ayikla` + `ek_trackerlar`.
   - `yerelden_sor` / `tarayicidan_sor`: Python `_bekleyenler` akisi, `TauriUi` kuyrugu ile (`kuyruga_ekle`). Onay (`bekleyen_onayla`) gelince bekleyen is parcacigi `indir_onayla` ile indirmeyi baslatir (Python `bekleyen_onayla` indirme kismi: manager.add + son_klasor). Iptal/pencere kapanisi (None) indirme yapmadan biter.
   - `windows`: Python `windows` property'si `_windows` / `manager.windows` dondurur; Rust'ta ikisi de yok, `null` doner.
3. Yonetim sunucusu ve LAN:
   - Yonetim paneli (`yonetim.rs`): api/web.py ile ayni kapilar: hiz siniri (`HizSinirlayici`), origin allowlist (kendi adresler + profil/genel `originler`), CSRF basligi (durum degistiren istekler), anahtar (`X-AfuDM-Key` / Bearer; `dogrula`), rol (`erisim::izinli`), oturum (`oturum_dokun`), `kullanim_isle`. Uclar: GET `/api/ping`, `/`, `/panel`, `/varlik/*`, `/api/yetenekler|durum|liste|ayarlar|olaylar|anahtarlar|istemciler|profiller`; POST `/api/oturum`, `/oturum/kapat`, `/ekle`, `/kontrol`, `/yeniden-dene`, `/temizle`, `/hiz-profili`, `/ayarlar`, `/anahtar/*`, `/istemci/*`, `/kilit/temizle`, `/profil/*`, `/sunucu/durdur`. Adres: `yerel` -> 127.0.0.1, `lan` -> 0.0.0.0; port 6821'den +9'a kadar.
   - LAN: ana API ayni yonlendiriciyle, LAN IP'sinde (`lan_ip:6811`) ikinci dinleyici olarak acilir. Ana dinleyici loopback'te kalir (Windows'ta ayni porta iki farkli adres baglanabilir). Telefon adresi `http://ip:port/m?k=TOKEN`, QR bu adresten uretilir.
   - Acilista (boot): `lan_erisimi` ve `sunucu_acik` (yonetici anahtari varsa) ayarlarina gore baslar.
4. Api ad karsilastirmasi: `Python Api public metot sayisi: 146`, `Rust tarafinda bagli ad sayisi: 146`, `HIC BAGLI OLMAYAN:` (bos).

## Sinirlar / bilinen farklar (durust liste)

- Yonetim paneli `limit` durumu: `sunucu_durumu` ayarlardan yeni bir `HizSinirlayici` kurup durumunu dondurur; calisan panelin sayaclari degil. Kilit temizligi de bu yuzden calisan panelin kilidini temizlemez (kilit `kilitleri_temizle` cagrisi calisan sayaci degil, gecici olani etkiler). Duzeltme: calisan panelin limiterini `yonetim` uzerinden sunmak (sonraki tur).
- `share_list` ve `share_delete`: yalniz kopru uzerinden olusturulan tokenlar (telefon `/share_create` ile acilanlar `paylasim.rs`'te listelenemez).
- `ekle` (panel): `start_at` (zamanlama) ve Python'un tum DownloadRequest alanlari (altyazi, sponsorblock, bolum vb.) tasinmadi; yalniz source/kind/dest_dir/filename|title/quality/audio_only/playlist. Hedef klasor kurali Python `hedef_klasor` ile ayni, uzaktan kok kontrolu sozel (yol onek karsilastirmasi, `resolve()` yok).
- `baglanti-ayarla` (panel): Rust'ta karsiligi yok, `NOT_IMPLEMENTED` doner.
- Onay akisi (`indir_onayla`): Python'daki probe/uzanti tamamlama (`dosya_adi.probe_url_info`, `ensure_extension`) yok; dosya adi yalniz `guvenli_dosya_adi` ile. Hedef klasor: Python `hedef_klasor` (secilen > kategori > None).
- `motor_indir` ilerlemesi `MOTOR_ILERLEME` icinde tutulur; `bridge.rs` `motor_durumu` icindeki `"ilerleme": {}` hala baglanmadi (tek satir, bridge kapsami disinda birakildi).
- QR: bayt-duzeyi kodlayici farki olabilir (bicim ayni).
- Internet tuneli: `TunelYoneticisi::gercek` + dar sunucu (`/s/{token}` yalniz) baglandi; cloudflared yoksa `share.cloudflaredMissing`, tunel hatasi `share.tunnelError`. Canli tunel acilmadi.
- `telefon_durumu.adres`: LAN dinleyicisi calisiyorsa dolu (token'li /m adresi); calismiyorsa bos.
- `guc_durumu`: Python'daki 20 sn PowerShell zaman asimi yok.
- `dosya_sec_ve_paylas`, `paylasim_stop` toast gosterimi (Python `toast(...)`) yok.
- Python kaynagindaki bozuk Turkce metinler (U+FFFD) Rust'ta duzeltilmis metinle yazildi (📍).

## Dogrulama (gercek ciktilar)

Clippy (`cargo clippy --manifest-path app\Cargo.toml -- -D warnings`): cikis 0.

Testler (`cargo test --manifest-path app\Cargo.toml`):
```
test result: ok. 23 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
TEST_EXIT=0
```
(kopru_h: 6 test, yonetim: 4 test, F4a ve diger testler.)

Release (`cargo build --release --manifest-path app\Cargo.toml`):
```
Finished `release` profile [optimized] target(s) in 2m 58s
BUILD_EXIT=0
```

Api ad karsilastirmasi (`scratchpad\api_karsilastir.py`):
```
Python Api public metot sayisi: 146
Rust tarafinda bagli ad sayisi: 146
HIC BAGLI OLMAYAN:
```

## Test edilmeyenler (durust liste)

- Yonetim paneli HTTP uclari, LAN dinleyicisi, QR gorseli ve internet tuneli canli calistirilmedi. Panel yalniz Tauri `sunucu_ayarla` cagrisiyla acilir; HTTP API bunu sunmaz. Pencere acilmadi, izole kopya calistirilmadi.
- Windows SMB, PowerShell tabanli guc_durumu gercek makinede calistirilmadi.
- Bekleyen akis (yerelden_sor/tarayicidan_sor): kuyruk ve onay mantigi kod seviyesinde; uctan uca indirme baslatma sinanmadi.
- Birim testleri yardimci fonksiyonlara yonelik (QR bicimi, sorgu cozucu, filtre/arama, yol normalizasyonu, kart/WOL ayristirma).

## Acik noktalar

1. Calisan panelin limiter durumunu/kilit temizligini `yonetim` uzerinden sunmak (sonraki tur).
2. Telefon ekle/zamanlama ve panel'in tam DownloadRequest alanlari (Python paritesi).
3. `motor_durumu` icinde `ilerleme` alaninin `MOTOR_ILERLEME`'ye baglanmasi (bridge, tek satir).
4. Canli test: panel (6821), LAN (telefon), tunel ve bekleyen onay akisinin uctan uca dogrulanmasi.

Yikici git komutu kullanilmadi. Notam'a yazilmadi.
