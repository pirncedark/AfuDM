//! Dosya paylasimi. Python: api/server.py `/share_create` ve `GET /s/<token>` (ana sunucu),
//! core/paylasim_sunucusu.py (yalniz `/s/` dinleyen dar sunucu; tunel bunu hedefler),
//! app.py `share_create`.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard};

use afudm_types::ApiCtx;
use axum::body::{Body, Bytes};
use axum::extract::{Path as AxPath, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::Json as AxJson;
use base64::Engine;
use futures_util::stream;
use rand::RngCore;
use serde_json::{json, Value};
use std::io::SeekFrom;
use tokio::io::{AsyncReadExt, AsyncSeekExt};
use tokio::sync::oneshot;

/// Python `_Handler.shared_files` (token -> {"path"}). Ana sunucu ve dar sunucu ayni depoyu okur.
static PAYLASIMLAR: Mutex<BTreeMap<String, PathBuf>> = Mutex::new(BTreeMap::new());

fn kilit() -> MutexGuard<'static, BTreeMap<String, PathBuf>> {
    PAYLASIMLAR.lock().unwrap_or_else(|e| e.into_inner())
}

/// Python `secrets.token_urlsafe(12)`: 12 rastgele bayt, padding'siz URL-safe base64.
/// Yolu saklar, tokenı doner.
pub fn paylasim_ekle(yol: PathBuf) -> String {
    let mut bayt = [0u8; 12];
    rand::rng().fill_bytes(&mut bayt);
    let token = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bayt);
    kilit().insert(token.clone(), yol);
    token
}

/// Tokenin dosya yolunu doner; yoksa None.
pub fn paylasim_bul(token: &str) -> Option<PathBuf> {
    kilit().get(token).cloned()
}

/// Paylasimi kaldirir; varsa true.
pub fn paylasim_sil(token: &str) -> bool {
    kilit().remove(token).is_some()
}

/// Python `_range_coz` (paylasim_sunucusu.py). Donus: (baslangic, uzunluk).
/// Bos baslik tum dosyayi verir. Gecersiz/doyurulamayan aralik Err.
/// Sayilar tasarsa Python'daki buyuk tamsayi davranisi icin doygunluk (saturating) kullanilir.
pub fn range_coz(baslik: &str, boyut: u64) -> Option<(u64, u64)> {
    if baslik.is_empty() {
        return Some((0, boyut));
    }
    if boyut == 0 {
        return None;
    }
    let govde = baslik.trim().strip_prefix("bytes=")?;
    let (sol, sag) = govde.split_once('-')?;
    if !sol.bytes().all(|b| b.is_ascii_digit()) || !sag.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    if sol.is_empty() {
        let sonek = if sag.is_empty() { 0 } else { sayi(sag) };
        if sonek == 0 {
            return None;
        }
        let baslangic = boyut.saturating_sub(sonek);
        return Some((baslangic, boyut - baslangic));
    }
    let baslangic = sayi(sol);
    let bitis = if sag.is_empty() {
        boyut - 1
    } else {
        sayi(sag).min(boyut - 1)
    };
    if baslangic >= boyut || bitis < baslangic {
        return None;
    }
    Some((baslangic, bitis - baslangic + 1))
}

fn sayi(s: &str) -> u64 {
    s.bytes().fold(0u64, |a, b| {
        a.saturating_mul(10).saturating_add(u64::from(b - b'0'))
    })
}

/// Python `urllib.parse.quote` (guvenli: `/`, harf, rakam, `_.-~`).
pub fn quote(s: &str) -> String {
    let mut cikti = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"_.-~/".contains(&b) {
            cikti.push(b as char);
        } else {
            cikti.push_str(&format!("%{b:02X}"));
        }
    }
    cikti
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Mod {
    /// Ana sunucu (`/s/`, LocalAPI): hatada JSON, ASCII ad yedegi "indirilen_dosya".
    Ana,
    /// Dar sunucu (tunel hedefi): hatada bos 404, ASCII ad yedegi "dosya".
    Dar,
}

/// Python `Content-Disposition`: ASCII ad (non-ASCII ve `"` atilir) + RFC 5987 `filename*`.
fn icerik_disposition(ad: &str, mod_: Mod) -> String {
    let yedek = match mod_ {
        Mod::Ana => "indirilen_dosya",
        Mod::Dar => "dosya",
    };
    let ascii: String = ad.chars().filter(|c| c.is_ascii() && *c != '"').collect();
    let ascii = if ascii.is_empty() {
        yedek.to_string()
    } else {
        ascii
    };
    format!(
        "attachment; filename=\"{ascii}\"; filename*=UTF-8''{}",
        quote(ad)
    )
}

fn bos_veya_hata(mod_: Mod) -> Response {
    match mod_ {
        Mod::Ana => super::hata(
            StatusCode::INTERNAL_SERVER_ERROR,
            "AKIS_HATASI",
            "Dosya aktarimi baslatilamadi",
        ),
        Mod::Dar => StatusCode::NOT_FOUND.into_response(),
    }
}

fn aralik_basligi(basliklar: &HeaderMap) -> &str {
    basliklar
        .get(header::RANGE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
}

/// Dosyayi (Range destekli) parca parca akitir. Python `_dosya_akis_gonder` / dar `_serve`.
async fn dosya_yaniti(yol: &Path, baslik: &str, mod_: Mod) -> Response {
    let boyut = match tokio::fs::metadata(yol).await {
        Ok(m) if mod_ == Mod::Ana || m.is_file() => m.len(),
        _ => return bos_veya_hata(mod_),
    };
    let (baslangic, uzunluk) = match range_coz(baslik, boyut) {
        Some(v) => v,
        None => {
            return Response::builder()
                .status(StatusCode::RANGE_NOT_SATISFIABLE)
                .header(header::CONTENT_RANGE, format!("bytes */{boyut}"))
                .header(header::CONTENT_LENGTH, "0")
                .body(Body::empty())
                .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
        }
    };
    let mut dosya = match tokio::fs::File::open(yol).await {
        Ok(f) => f,
        Err(_) => return bos_veya_hata(mod_),
    };
    if baslangic > 0 && dosya.seek(SeekFrom::Start(baslangic)).await.is_err() {
        return bos_veya_hata(mod_);
    }
    let kismi = !baslik.is_empty();
    let ad = yol
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let mut yanit = Response::builder()
        .status(if kismi {
            StatusCode::PARTIAL_CONTENT
        } else {
            StatusCode::OK
        })
        .header(header::CONTENT_TYPE, "application/octet-stream")
        .header(header::CONTENT_DISPOSITION, icerik_disposition(&ad, mod_))
        .header(header::CONTENT_LENGTH, uzunluk.to_string())
        .header(header::ACCEPT_RANGES, "bytes");
    if kismi {
        let son = baslangic + uzunluk.saturating_sub(1);
        yanit = yanit.header(
            header::CONTENT_RANGE,
            format!("bytes {baslangic}-{son}/{boyut}"),
        );
    }
    let akis = stream::unfold((dosya, uzunluk), |(mut f, kalan)| async move {
        if kalan == 0 {
            return None;
        }
        let n = kalan.min(256 * 1024) as usize;
        let mut tampon = vec![0u8; n];
        match f.read(&mut tampon).await {
            Ok(0) => None,
            Ok(k) => {
                tampon.truncate(k);
                Some((
                    Ok::<Bytes, std::io::Error>(Bytes::from(tampon)),
                    (f, kalan - k as u64),
                ))
            }
            Err(e) => Some((Err(e), (f, 0))),
        }
    });
    yanit
        .body(Body::from_stream(akis))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}

/// `GET /s/{token}` (ana sunucu). Python: api/server.py do_GET `/s/`. Anahtar gerektirmez.
pub async fn s_ana(AxPath(token): AxPath<String>, basliklar: HeaderMap) -> Response {
    let Some(yol) = paylasim_bul(&token) else {
        return super::hata(
            StatusCode::NOT_FOUND,
            "SAYFA_YOK",
            "Paylasim bulunamadi veya suresi doldu",
        );
    };
    dosya_yaniti(&yol, aralik_basligi(&basliklar), Mod::Ana).await
}

/// Dar sunucunun tek rotasi. Python `_PaylasimHandler._serve`: yanit yoksa bos 404.
async fn dar_servis(AxPath(token): AxPath<String>, basliklar: HeaderMap) -> Response {
    match paylasim_bul(&token) {
        Some(yol) if yol.is_file() => {
            dosya_yaniti(&yol, aralik_basligi(&basliklar), Mod::Dar).await
        }
        _ => StatusCode::NOT_FOUND.into_response(),
    }
}

fn dar_yonlendirici() -> axum::Router {
    axum::Router::new().route("/s/{token}", axum::routing::get(dar_servis))
}

/// Yol ayiricisi/yollari normalize eder; Windows `\\?\` on ekini atar.
fn cozumle(yol: &Path) -> Option<PathBuf> {
    let tam = yol.canonicalize().ok()?;
    let metin = tam.to_string_lossy().into_owned();
    if let Some(kisa) = metin.strip_prefix(r"\\?\") {
        if !kisa.starts_with("UNC\\") {
            return Some(PathBuf::from(kisa));
        }
    }
    Some(tam)
}

/// Python `_yol_kok_icinde`: sozdizimi reddi (UNC, NUL) + gercek (symlink cozulmus) yol kok icinde mi.
pub fn kok_icinde(yol: &Path, kok: &Path) -> bool {
    let ham = yol.to_string_lossy();
    if ham.is_empty() || ham.contains('\0') || ham.starts_with("\\\\") || ham.starts_with("//") {
        return false;
    }
    let (Some(y), Some(k)) = (cozumle(yol), cozumle(kok)) else {
        return false;
    };
    let bilesenler = |p: &Path| -> Vec<String> {
        p.components()
            .map(|c| c.as_os_str().to_string_lossy().to_lowercase())
            .collect()
    };
    let (yp, kp) = (bilesenler(&y), bilesenler(&k));
    kp.len() <= yp.len() && kp.iter().zip(&yp).all(|(a, b)| a == b)
}

/// Govdeyi JSON nesnesi olarak okur. Bos govde {} sayilir (Python `_govde_oku`).
/// Bozuk ya da JSON nesnesi olmayan govde None doner; cagiran 400 GOVDE_HATASI yazar.
fn govde_coz(ham: &[u8]) -> Option<Value> {
    if ham.is_empty() {
        return Some(json!({}));
    }
    match serde_json::from_slice::<Value>(ham) {
        Ok(v) if v.is_object() => Some(v),
        _ => None,
    }
}

/// `POST /share_create` {"gid":"g"} -> {"ok":true,"token","filename"}.
/// Python: api/server.py do_POST `/share_create` (hazir ve kok icinde tekil dosya).
pub async fn share_create(State(ctx): State<ApiCtx>, govde: Bytes) -> Response {
    let Some(veri) = govde_coz(&govde) else {
        return super::hata(
            StatusCode::BAD_REQUEST,
            "GOVDE_HATASI",
            "Istek bicimi uygun degil. Yeniden dene.",
        );
    };
    let gid = veri
        .get("gid")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    if gid.is_empty() {
        return super::hata(StatusCode::BAD_REQUEST, "GID_GEREKLI", "gid gerekli");
    }
    let yol = match ctx.manager.resolve_item_path(&gid) {
        Ok(Some(y)) => y,
        Ok(None) => {
            return super::hata(
                StatusCode::NOT_FOUND,
                "HAZIR_DEGIL",
                "Dosya hazir degil veya yolu bulunamadi",
            )
        }
        Err(e) => return super::afu_hata(&e),
    };
    let kok = match ctx.manager.current_download_dir() {
        Ok(k) => k,
        Err(e) => return super::afu_hata(&e),
    };
    if !kok_icinde(&yol, Path::new(&kok)) {
        return super::hata(
            StatusCode::FORBIDDEN,
            "HEDEF_DISARIDA",
            "dosya indirme kokunun disinda",
        );
    }
    let yol = match cozumle(&yol) {
        Some(y) if y.is_file() => y,
        _ => {
            return super::hata(
                StatusCode::NOT_FOUND,
                "BULUNAMADI",
                "Sadece tekil dosyalar paylasilabilir veya dosya diskte yok",
            )
        }
    };
    let ad = yol
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let token = paylasim_ekle(yol);
    AxJson(json!({"ok": true, "token": token, "filename": ad})).into_response()
}

/// Python `PaylasimSunucusu`: 127.0.0.1 uzerinde rastgele port, yalniz `/s/<token>`.
/// Tunel bu porta baglanir; boylece internete yalniz paylasim acilir.
#[derive(Default)]
pub struct PaylasimSunucusu {
    port: u16,
    kapat_sinyali: Option<oneshot::Sender<()>>,
    is_parcasi: Option<std::thread::JoinHandle<()>>,
}

impl PaylasimSunucusu {
    pub fn port(&self) -> u16 {
        self.port
    }

    /// Calisiyorsa mevcut portu, degilse yeni portu baglar ve dinletir.
    pub fn baslat(&mut self) -> std::io::Result<u16> {
        if self.is_parcasi.is_some() {
            return Ok(self.port);
        }
        let dinleyici = std::net::TcpListener::bind("127.0.0.1:0")?;
        dinleyici.set_nonblocking(true)?;
        let port = dinleyici.local_addr()?.port();
        let (tx, rx) = oneshot::channel::<()>();
        let parca = std::thread::Builder::new()
            .name("afudm-paylasim-sunucu".into())
            .spawn(move || {
                let calisma = match tokio::runtime::Builder::new_current_thread()
                    .enable_all()
                    .build()
                {
                    Ok(c) => c,
                    Err(e) => {
                        log::warn!("paylasim sunucusu calisma zamani kurulamadi: {e}");
                        return;
                    }
                };
                calisma.block_on(async move {
                    let liste = match tokio::net::TcpListener::from_std(dinleyici) {
                        Ok(l) => l,
                        Err(e) => {
                            log::warn!("paylasim sunucusu dinleyicisi hazirlanamadi: {e}");
                            return;
                        }
                    };
                    let sonuc = axum::serve(liste, dar_yonlendirici())
                        .with_graceful_shutdown(async {
                            let _ = rx.await;
                        })
                        .await;
                    if let Err(e) = sonuc {
                        log::warn!("paylasim sunucusu durdu: {e}");
                    }
                });
            })?;
        self.port = port;
        self.kapat_sinyali = Some(tx);
        self.is_parcasi = Some(parca);
        Ok(port)
    }

    /// Kapatma sinyali gonderir. Python'daki join(timeout=2) yerine iş parcacigi ayrilir:
    /// acik bir indirme varsa durdurma bloklanmaz.
    pub fn durdur(&mut self) {
        if let Some(tx) = self.kapat_sinyali.take() {
            let _ = tx.send(());
        }
        self.is_parcasi.take();
        self.port = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpStream;

    fn gecici_dosya(ad: &str, icerik: &[u8]) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let klasor =
            std::env::temp_dir().join(format!("afudm_h_paylasim_{}_{nanos}", std::process::id()));
        std::fs::create_dir_all(&klasor).unwrap();
        let yol = klasor.join(ad);
        std::fs::write(&yol, icerik).unwrap();
        yol
    }

    #[test]
    fn range_bos_baslik_tum_dosya() {
        assert_eq!(range_coz("", 10), Some((0, 10)));
        assert_eq!(range_coz("", 0), Some((0, 0)));
    }

    #[test]
    fn range_araliklar() {
        assert_eq!(range_coz("bytes=0-99", 1000), Some((0, 100)));
        assert_eq!(range_coz("bytes=5-", 10), Some((5, 5)));
        assert_eq!(range_coz("bytes=5-500", 10), Some((5, 5)));
        assert_eq!(range_coz("bytes=-3", 10), Some((7, 3)));
        assert_eq!(range_coz("bytes=-99", 10), Some((0, 10)));
    }

    #[test]
    fn range_gecersizler() {
        assert_eq!(range_coz("bytes=10-", 10), None);
        assert_eq!(range_coz("bytes=5-2", 10), None);
        assert_eq!(range_coz("bytes=-0", 10), None);
        assert_eq!(range_coz("bytes=-", 10), None);
        assert_eq!(range_coz("items=0-1", 10), None);
        assert_eq!(range_coz("bytes=0-1-2", 10), None);
        assert_eq!(range_coz("bytes=0-1", 0), None);
        assert_eq!(range_coz("bytes=99999999999999999999999999-", 10), None);
    }

    #[test]
    fn quote_python_gibi() {
        assert_eq!(quote("a b.pdf"), "a%20b.pdf");
        assert_eq!(quote("ğ_1-~"), "%C4%9F_1-~");
        assert_eq!(quote("dir/x"), "dir/x");
    }

    #[test]
    fn disposition_ascii_ve_yedek() {
        assert_eq!(
            icerik_disposition("ğ.pdf", Mod::Ana),
            "attachment; filename=\".pdf\"; filename*=UTF-8''%C4%9F.pdf"
        );
        assert_eq!(
            icerik_disposition("ğğ", Mod::Dar),
            "attachment; filename=\"dosya\"; filename*=UTF-8''%C4%9F%C4%9F"
        );
        assert_eq!(
            icerik_disposition("ğ", Mod::Ana),
            "attachment; filename=\"indirilen_dosya\"; filename*=UTF-8''%C4%9F"
        );
    }

    #[test]
    fn token_urlsafe_uzunluk() {
        let t = paylasim_ekle(PathBuf::from("x"));
        assert_eq!(t.len(), 16);
        assert!(t
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'));
        assert_eq!(paylasim_bul(&t), Some(PathBuf::from("x")));
        assert!(paylasim_sil(&t));
        assert_eq!(paylasim_bul(&t), None);
    }

    #[test]
    fn kok_icinde_sinirlar() {
        let kok = std::env::temp_dir().join(format!("afudm_h_kok_{}", std::process::id()));
        std::fs::create_dir_all(kok.join("alt")).unwrap();
        let ic = kok.join("alt").join("a.bin");
        std::fs::write(&ic, b"x").unwrap();
        assert!(kok_icinde(&ic, &kok));
        assert!(!kok_icinde(&kok.join("..").join("disari.bin"), &kok));
        assert!(!kok_icinde(Path::new("\\\\server\\paylasim\\a"), &kok));
        assert!(!kok_icinde(Path::new(""), &kok));
    }

    #[test]
    fn govde_bos_ve_bozuk() {
        assert_eq!(govde_coz(b""), Some(json!({})));
        assert!(govde_coz(b"[1]").is_none());
        assert!(govde_coz(b"{bozuk").is_none());
    }

    #[test]
    fn dar_sunucu_range_ile_dosya_verir() {
        let yol = gecici_dosya("veri.bin", b"0123456789");
        let token = paylasim_ekle(yol);
        let mut sunucu = PaylasimSunucusu::default();
        let port = sunucu.baslat().unwrap();
        let mut akim = TcpStream::connect(("127.0.0.1", port)).unwrap();
        let istek = format!(
            "GET /s/{token} HTTP/1.1\r\nHost: x\r\nRange: bytes=2-4\r\nConnection: close\r\n\r\n"
        );
        akim.write_all(istek.as_bytes()).unwrap();
        let mut yanit = Vec::new();
        akim.read_to_end(&mut yanit).unwrap();
        let metin = String::from_utf8_lossy(&yanit).into_owned();
        assert!(metin.starts_with("HTTP/1.1 206"), "{metin}");
        assert!(
            metin
                .to_ascii_lowercase()
                .contains("content-range: bytes 2-4/10"),
            "{metin}"
        );
        assert!(metin.ends_with("234"), "{metin}");
        sunucu.durdur();
        paylasim_sil(&token);
    }

    #[test]
    fn dar_sunucu_bilinmeyen_token_bos_404() {
        let mut sunucu = PaylasimSunucusu::default();
        let port = sunucu.baslat().unwrap();
        let mut akim = TcpStream::connect(("127.0.0.1", port)).unwrap();
        akim.write_all(b"GET /s/yok-token HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            .unwrap();
        let mut yanit = Vec::new();
        akim.read_to_end(&mut yanit).unwrap();
        assert!(String::from_utf8_lossy(&yanit).starts_with("HTTP/1.1 404"));
        sunucu.durdur();
    }
}
