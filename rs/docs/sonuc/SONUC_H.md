# SONUC: Ekip H (paylasim, tunel, SMB, mobil eslestirme)

Kapsam: `crates\afudm-extras\src\h\` + `crates\afudm-extras\Cargo.toml` (yalniz `[dependencies]`).
Dokunulmadi: `extras\src\lib.rs`, `g1\`, `g2\`, `afudm-core`, `afudm-api`, kok `Cargo.toml`, `afudm-types`.
Python kaynagi yalniz okundu. Gercek tunel acilmadi; testler sahte surecle calisti.

## Yazilan dosyalar
- `C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\src\h\mod.rs` (router, ortak hata yanitlari)
- `...\src\h\paylasim.rs` (paylasim deposu, Range, /s/ akisi, /share_create, dar sunucu)
- `...\src\h\tunel.rs` (TunelYoneticisi, surec soyutlamasi, izleyici)
- `...\src\h\smb.rs` (net share yasam dongusu)
- `...\src\h\esleme.rs` (/pair, eslestirme penceresi, token okuma)
- `...\src\h\mobil.rs` (/m, manifest, i18n.js, sw.js, ikon.png)
- `...\crates\afudm-extras\Cargo.toml`: eklenen bagimliliklar `afudm-engine`, `base64`, `rand`, `futures-util = "0.3"`, `tokio` (fs, io-util ozellikleri). Cargo.lock cargo tarafindan guncellendi.

## Python -> Rust karsilastirma
| Python | Rust | Durum |
|---|---|---|
| paylasim_sunucusu `_range_coz` | `paylasim::range_coz` | ✅ (Option donusu; buyuk sayilar doygunluk ile) |
| paylasim_sunucusu `PaylasimSunucusu.start/stop/port` | `PaylasimSunucusu::baslat/durdur/port` | ✅ ⚠ durdur join(timeout=2) yerine ayirir (acik indirme varken bloklanmaz) |
| `_PaylasimHandler._serve` (dar) | `paylasim::dar_servis` | ✅ bos 404, Range, HEAD (axum GET+HEAD) |
| api/server.py GET `/s/` (ana) | `paylasim::s_ana` | ✅ ⚠ dosya acilamazsa Python yanit basladiktan sonra keser; Rust 500 AKIS_HATASI doner |
| api/server.py POST `/share_create` | `paylasim::share_create` | ✅ ⚠ gid sayisal ise Python devam eder; Rust GID_GEREKLI doner |
| server.py `_yol_kok_icinde` | `paylasim::kok_icinde` | ✅ (UNC/NUL reddi, symlink cozumu, bilesen karsilastirma) |
| server.py `Content-Disposition` + `quote` | `icerik_disposition`, `quote` | ✅ ana (yedek "indirilen_dosya") / dar (yedek "dosya") ayri |
| `secrets.token_urlsafe(12)` | `paylasim_ekle` | ✅ 16 karakter, padding'siz |
| tunel.py `TunnelManager.start` (iki deneme) | `TunelYoneticisi::baslat` | ✅ |
| tunel.py `_read_url` (30 sn, stdout+stderr) | `url_bekle` | ✅ ⚠ stderr ayri okunur (Python'da birlesik) |
| tunel.py `_watch` (tek yeniden baslatma) | `izle` | ✅ kimlik sayaci ile eski izleyici biter |
| tunel.py `stop` | `TunelYoneticisi::durdur` | ✅ ⚠ terminate yerine kill (Windows'ta ayni) |
| tunel.py `_URL` regex | `trycloudflare_url_bul` | ✅ buyuk/kucuk harf duyarsiz |
| tunel.py CREATE_NO_WINDOW | `GercekFabrika::baslat` | ✅ |
| engines.yol(app_dir,"cloudflared") | `tunel::cloudflared_yolu` | ✅ |
| smb_paylasim `acik_paylasimlar` | `smb::acik_paylasimlar` + `paylasim_adlari` | ✅ ⚠ net icin 15 sn zaman asimi yok; cikti UTF-8 lossy (ad kontrolu ASCII) |
| smb_paylasim `artiklari_temizle` | `smb::artiklari_temizle` | ✅ |
| app.py `agda_paylas` (SMB kismi) | `smb::paylas_olustur` | ✅ ⚠ HTTP/QR/uyari metinleri ve orkestrasyon app'te (F) kalir |
| app.py `_paylasim_kaynaklarini_temizle` | `smb::paylas_kaldir` | ✅ |
| api/server.py GET `/pair` | `esleme::pair` | ✅ ⚠ ConnectInfo gerekir (asagida) |
| LocalAPI.open_pairing / son_eslesme | `esleme::eslesme_ac`, `son_eslesme` | ✅ |
| app.py start_pairing(seconds) | `esleme::eslesme_ac` | ⚠ cagri app (F) tarafinda baglanmali |
| GET `/m`, `/manifest.webmanifest`, `/i18n.js`, `/sw.js`, `/ikon.png` | `mobil::*` | ✅ basliklar ve SAYFA_YOK birebir |
| app.py `share_list` / `share_delete` / `_paylasim_url` / `_internet_linki` / QR | yok | ⚠ Api orkestrasyonu; `paylasim_sil`/`paylasim_bul` primitifleri var, listeleme ve QR eklenmedi |
| core/db.py `mobile_devices` tablosu | yok | 📍 Python'da YALNIZ SEMA var (core/db.py satir 223-230, `_v5_mobile_devices`); hicbir kod bu tabloyu okumuyor/yazmiyor. Gorevdeki "store.query/execute ile mobile_devices" kullanimi Python'da karsiligi olmadigi icin Rust'ta yazilmadi. |

## Sozlesme sorunlari (Claude / E / F icin)
1. `/pair` icin `ConnectInfo<SocketAddr>` gerekir. Serve `into_make_service_with_connect_info` ile calismali. Bilgi yoksa istek yerel sayilmaz ve 403 ESLESME_YEREL_GEREKLI doner (guvenli taraf).
2. Kimlik: H router T/A kontrolu yapmaz. E'nin `with_auth` katmani `/share_create` icin T, `/pair`, `/m`, `/manifest.webmanifest`, `/i18n.js`, `/sw.js`, `/ikon.png`, `/s/*` icin A muafiyetini uygulamali. Python'daki `/s/` rate-limit muafiyeti de E'de.
3. CORS yazilmadi; E katmaninda kalir (Python `_cors` ana sunucuda vardi).
4. Token: `/pair` token'ini `data_dir\api_token.txt` dosyasindan her istekte okur. Python `self.token` bellekte tutuyordu; E'nin rotate islemi dosyayi guncellerse H ayni anda gorur.
5. Paylasim deposu, Python `_Handler.shared_files` gibi process-ici statiktir (`paylasim_ekle/bul/sil`). Ana sunucu ve dar sunucu ayni depoyu okur.
6. Dar sunucu otomatik baslamaz. F, tunel oncesi `PaylasimSunucusu::baslat()` cagirip donen portu `TunelYoneticisi::baslat(port)`a vermeli.
7. `resolve_item_path` icin varsayim: Python'daki (`tell_status` complete + store `target_path`) mantigi Manager tarafinda ayni. Dogrulanmadi.
8. `ApiCtx` tek bir `Store` tasiyor; mobile_devices icin Store sorgusu gerekmedi (bkz. yukarida 📍).

## Testler
Komut: `cargo test -p afudm-extras h::` -> **22 passed, 0 failed**.
Kapsam: range_coz (bos, aralik, suffix, gecersiz, buyuk sayi), quote, Content-Disposition, token uzunlugu, kok_icinde sinirlari, govde ayrisma, dar sunucuya gercek TCP ile Range istegi (206 + Content-Range + govde "234"), dar sunucu bilinmeyen token (404), tunel URL bulucu, tunel URL alma + argumanlar (sahte surec), iki deneme sonrasi hata, izleyici tek yeniden baslatma ve ikinci cikista hata, durdurma sonrasi izleyici etkisizligi, esleme penceresi, token dosyasi okuma, smb cikti ayristirma, mobil sayfa basliklari.

Son 30 satir (`cargo test -p afudm-extras`, tum crate):
```
test h::tunel::tests::url_bulucu_python_gibi ... ok
test g2::linkgrabber::tests::ayiklar_http_ftp_magnet ... FAILED
test h::paylasim::tests::dar_sunucu_range_ile_dosya_verir ... ok
test h::mobil::tests::mevcut_sayfa_basliklariyla_gelir ... ok
test h::tunel::tests::durdur_izleyiciyi_etkisiz_kilar ... ok
test h::tunel::tests::izleyici_surec_cikinca_bir_kez_yeniden_baslatir ... ok

failures:

---- g2::kurallar::tests::evaluate_oncelik_ve_kullanici stdout ----

thread 'g2::kurallar::tests::evaluate_oncelik_ve_kullanici' (39140) panicked at crates\afudm-extras\src\g2\kurallar.rs:267:9:
assertion `left == right` failed
  left: String("D:/Dusuk")
 right: "D:/Yuksek"
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

---- g2::linkgrabber::tests::ayiklar_http_ftp_magnet stdout ----

thread 'g2::linkgrabber::tests::ayiklar_http_ftp_magnet' (37604) panicked at crates\afudm-extras\src\g2\linkgrabber.rs:386:9:
assertion failed: c.contains(&"https://ornek.com/dosya.iso".to_string())


failures:
    g2::kurallar::tests::evaluate_oncelik_ve_kullanici
    g2::linkgrabber::tests::ayiklar_http_ftp_magnet

test result: FAILED. 54 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.38s
error: test failed, to rerun pass `-p afudm-extras --lib`
```
Iki basarisiz test (`g2::kurallar`, `g2::linkgrabber`) Ekip G2'nin kodu; H'nin degil.

Build: `cargo build -p afudm-extras` -> basarili (uyari yok).
Clippy: `cargo clippy -p afudm-extras -- -D warnings` -> h/ modulunde hata yok. Crate'te 6 lint hatasi var, hepsi `g2\` dosyalarinda (eklenti.rs, eklenti_servis.rs, kurallar.rs, mod.rs). Benim degil.
Bicim: `rustfmt --check` h/mod.rs icin temiz (rustfmt yalniz h/ dosyalarina uygulandi; `cargo fmt -p` g1/g2'ye dokunacagi icin kullanilmadi).

## Test edilmeyen public fonksiyonlar (⚠ eksik)
- `paylasim::share_create`, `paylasim::s_ana`, `esleme::pair`: handler duzeyi testi icin `ManagerApi` (~60 metot) ve `Store` (~50 metot) sahte uygulamasi gerekir. Yazilmadi. Cekirdek mantik ayri fonksiyonlarda test edildi (kok_icinde, govde_coz, range_coz, token_oku, eslesme penceresi).
- `TunelYoneticisi::gercek`, `tunel::cloudflared_yolu`: sistem/motor bagimli; test yazilmadi.
- `PaylasimSunucusu::port`: dolayli olarak baslat testinde kullaniliyor, ayri test yok.
- `smb::acik_paylasimlar`, `artiklari_temizle`, `paylas_olustur`, `paylas_kaldir`: gercek `net share` cagrilari sistem yan etkisi yaratir (agda paylasim acar). Test edilmedi; yalniz ayristirma (`paylasim_adlari`) test edildi.

## Bitti mi?
- Tum `todo!()` yok. Python'dan tasinmasi gereken H fonksiyonlarinin cekirdegi tamam.
- Acik kalanlar: yukaridaki ⚠ listesi (orkestrasyon app F'de, handler testleri icin sahte ManagerApi/Store), 📍 mobile_devices (Python'da kullanilmiyor), ve Sozlesme sorunlari 1-8.
- Commit atilmadi (kural geregi Claude atar).
