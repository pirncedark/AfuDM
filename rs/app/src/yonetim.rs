//! Yonetim paneli (HTTP, varsayilan 6821), LAN dinleyicisi (telefon) ve internet paylasim tuneli.
//! Python: api/web.py (YonetimSunucusu, _Handler), app.py (telefon_*, _internet_linki),
//! core/tunel.py, core/paylasim_sunucusu.py. Erisim kurallari afudm_api::erisim deposundan okunur.

use std::collections::BTreeSet;
use std::net::{SocketAddr, TcpListener as StdListener};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use afudm_api::erisim::{self, ErisimDeposu, HizSinirlayici};
use afudm_extras::h::{
    esleme, paylasim,
    tunel::{self, TunelYoneticisi},
};
use afudm_types::{AfuError, ApiCtx, JsonMap, Result};
use axum::body::Body;
use axum::extract::{ConnectInfo, State};
use axum::http::{header, response::Builder, HeaderMap, Method, StatusCode, Uri};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::Router;
use serde_json::{json, Value as Json};
use tokio::sync::oneshot;

use crate::bridge::kilit;
use crate::kopru_h;

const PANEL_HTML: &[u8] = include_bytes!("../ui/panel.html");
const I18N_JS: &[u8] = include_bytes!("../ui/i18n.js");
const STYLE_CSS: &[u8] = include_bytes!("../ui/style.css");
const GOVDE_LIMITI: usize = 2_000_000;
const CSRF_BASLIK: &str = "X-AfuDM-CSRF";
const ANAHTAR_BASLIK: &str = "x-afudm-key";
const OTURUM_BASLIK: &str = "x-afudm-oturum";

/// Calisan yonetim paneli. Durum sayaclari atomiktir; istekler birbirini beklemez.
pub struct Panel {
    ctx: ApiCtx,
    port: u16,
    lan: bool,
    lan_ip: String,
    limit: HizSinirlayici,
    istek: AtomicU64,
    red: AtomicU64,
    baslangic: f64,
}

struct Calisan {
    kapat: Option<oneshot::Sender<()>>,
    port: u16,
    panel: Arc<Panel>,
}

struct LanCalisan {
    kapat: Option<oneshot::Sender<()>>,
    port: u16,
    ip: String,
}

/// Panel durumu (sunucu_durumu icin).
pub struct PanelBilgi {
    pub port: u16,
    pub lan: bool,
    pub lan_ip: String,
    pub istek: u64,
    pub red: u64,
    pub baslangic: f64,
}

static YONETIM: Mutex<Option<Calisan>> = Mutex::new(None);
static LAN: Mutex<Option<LanCalisan>> = Mutex::new(None);
static YONLENDIRICI: OnceLock<Router> = OnceLock::new();
static DAR: Mutex<Option<(oneshot::Sender<()>, u16)>> = Mutex::new(None);
static TUNEL: Mutex<Option<TunelYoneticisi>> = Mutex::new(None);

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Ana API yonlendiricisi (boot.rs, with_auth uygulanmis hali). LAN dinleyicisi bunu sunar.
pub fn yonlendiriciyi_kaydet(yonlendirici: Router) {
    let _ = YONLENDIRICI.set(yonlendirici);
}

/// Python `lan_ip`: UDP rota secimi, paket gonderilmez. Loopback ise bos.
pub(crate) fn lan_ip() -> String {
    let ip = std::net::UdpSocket::bind("0.0.0.0:0")
        .and_then(|soket| {
            soket.connect("10.255.255.255:1")?;
            soket.local_addr()
        })
        .map(|adres| adres.ip().to_string())
        .unwrap_or_default();
    if ip.starts_with("127.") {
        String::new()
    } else {
        ip
    }
}

/// Python `_PaylasmayanSunucu`: istenen porttan baslayip `aralik` deneme yapar; ilk acilani doner.
fn bagla(ip: &str, istenen: u16, aralik: u16) -> std::result::Result<(StdListener, u16), String> {
    let mut son = String::from("port yok");
    for port in istenen..istenen.saturating_add(aralik) {
        match StdListener::bind((ip, port)) {
            Ok(dinleyici) => {
                dinleyici.set_nonblocking(true).map_err(|e| e.to_string())?;
                let gercek = dinleyici.local_addr().map(|a| a.port()).unwrap_or(port);
                return Ok((dinleyici, gercek));
            }
            Err(e) => son = e.to_string(),
        }
    }
    Err(format!(
        "yonetim sunucusu portu acilamadi ({}-{}): {son}",
        istenen,
        istenen.saturating_add(aralik).saturating_sub(1)
    ))
}

/// Dinleyiciyi tokio uzerinde calistirir; `rx` tetiklenince nazikce kapanir.
fn sun(dinleyici: StdListener, yonlendirici: Router, rx: oneshot::Receiver<()>) {
    tauri::async_runtime::spawn(async move {
        let Ok(l) = tokio::net::TcpListener::from_std(dinleyici) else {
            return;
        };
        let _ = axum::serve(
            l,
            yonlendirici.into_make_service_with_connect_info::<SocketAddr>(),
        )
        .with_graceful_shutdown(async {
            let _ = rx.await;
        })
        .await;
    });
}

// --- yonetim paneli --------------------------------------------------------

/// Python `sunucu_baslat` (basarili dal): paneli acar, port doner. Zaten aciksa mevcut port.
pub fn sunucu_ac(ctx: &ApiCtx) -> std::result::Result<u16, String> {
    if let Some(c) = kilit(&YONETIM).as_ref() {
        return Ok(c.port);
    }
    let ayar = kopru_h::sunucu_ayarlari(ctx).map_err(|e| e.to_string())?;
    let lan = ayar["adres"].as_str() == Some("lan");
    let istenen = ayar["port"].as_u64().unwrap_or(6821) as u16;
    let (dinleyici, port) = bagla(if lan { "0.0.0.0" } else { "127.0.0.1" }, istenen, 10)?;
    let lan_ip = if lan { lan_ip() } else { String::new() };
    let limit = kopru_h::limitci(ctx).map_err(|e| e.to_string())?;
    let limit_degeri = ayar["istek_limiti"].as_u64().unwrap_or(120);
    let panel = Arc::new(Panel {
        ctx: ctx.clone(),
        port,
        lan,
        lan_ip,
        limit,
        istek: AtomicU64::new(0),
        red: AtomicU64::new(0),
        baslangic: simdi(),
    });
    let (kapat, rx) = tokio::sync::oneshot::channel();
    let yonlendirici = Router::new().fallback(istek).with_state(panel.clone());
    sun(dinleyici, yonlendirici, rx);
    ctx.store.log(
        "info",
        &format!("yonetim sunucusu acildi (port {port}, limit {limit_degeri})"),
        "",
    );
    *kilit(&YONETIM) = Some(Calisan {
        kapat: Some(kapat),
        port,
        panel,
    });
    Ok(port)
}

/// Paneli kapatir. Kapaliyken cagrilmasi hata degildir.
pub fn sunucu_kapat() {
    if let Some(mut c) = kilit(&YONETIM).take() {
        if let Some(kapat) = c.kapat.take() {
            let _ = kapat.send(());
        }
    }
}

/// Calisan panelin bilgisi; kapaliysa None.
pub fn sunucu_bilgi() -> Option<PanelBilgi> {
    kilit(&YONETIM).as_ref().map(|c| PanelBilgi {
        port: c.port,
        lan: c.panel.lan,
        lan_ip: c.panel.lan_ip.clone(),
        istek: c.panel.istek.load(Ordering::Relaxed),
        red: c.panel.red.load(Ordering::Relaxed),
        baslangic: c.panel.baslangic,
    })
}

// --- LAN dinleyicisi (telefon) ---------------------------------------------

/// Python `telefon_ayarla(True)` / LocalAPI.lan_ayarla: ana API portunu yerel aga (LAN IP) acar.
/// Ana dinleyici loopback'te kalir; bu ayri bir LAN IP dinleyicisidir.
pub fn lan_ac(port: u16) -> std::result::Result<String, String> {
    if let Some(c) = kilit(&LAN).as_ref() {
        return Ok(c.ip.clone());
    }
    let ip = lan_ip();
    if ip.is_empty() {
        return Err("lan_bind_failed".into());
    }
    let yonlendirici = YONLENDIRICI
        .get()
        .cloned()
        .ok_or_else(|| "lan_bind_failed".to_string())?;
    let dinleyici =
        StdListener::bind((ip.as_str(), port)).map_err(|_| "lan_bind_failed".to_string())?;
    dinleyici
        .set_nonblocking(true)
        .map_err(|_| "lan_bind_failed".to_string())?;
    let (kapat, rx) = tokio::sync::oneshot::channel();
    sun(dinleyici, yonlendirici, rx);
    *kilit(&LAN) = Some(LanCalisan {
        kapat: Some(kapat),
        port,
        ip: ip.clone(),
    });
    Ok(ip)
}

/// LAN dinleyicisini kapatir (kapaliyken no-op).
pub fn lan_kapat() {
    if let Some(mut c) = kilit(&LAN).take() {
        if let Some(kapat) = c.kapat.take() {
            let _ = kapat.send(());
        }
    }
}

/// LAN adresi yalniz kisa omurlu eslestirme kodu tasir. LAN kapaliysa None.
pub fn lan_adres(ctx: &ApiCtx) -> Option<String> {
    let (ip, port) = {
        let g = kilit(&LAN);
        let c = g.as_ref()?;
        (c.ip.clone(), c.port)
    };
    esleme::token_oku(&ctx.data_dir).ok()?;
    let kod = esleme::mobil_kod_uret(&ctx.data_dir);
    Some(format!("http://{ip}:{port}/m?code={kod}"))
}

/// Python `_qr_uret`: adresi PNG data-URI olarak uretir (box 6, kenar 2, #0f131a / #e6eaf0).
pub fn qr_uri(metin: &str) -> String {
    let Ok(kod) = qrcode::QrCode::with_error_correction_level(metin.as_bytes(), qrcode::EcLevel::M)
    else {
        return String::new();
    };
    let modul = kod.width();
    let renkler = kod.to_colors();
    const KUTU: usize = 6;
    const KENAR: usize = 2;
    let boyut = (modul + 2 * KENAR) * KUTU;
    let mut resim =
        image::RgbImage::from_pixel(boyut as u32, boyut as u32, image::Rgb([230, 234, 240]));
    for y in 0..modul {
        for x in 0..modul {
            if matches!(renkler[y * modul + x], qrcode::types::Color::Dark) {
                let bx = (x + KENAR) * KUTU;
                let by = (y + KENAR) * KUTU;
                for dy in 0..KUTU {
                    for dx in 0..KUTU {
                        resim.put_pixel(
                            (bx + dx) as u32,
                            (by + dy) as u32,
                            image::Rgb([15, 19, 26]),
                        );
                    }
                }
            }
        }
    }
    let mut bayt = Vec::new();
    let kodlayici = image::codecs::png::PngEncoder::new(&mut bayt);
    if image::ImageEncoder::write_image(
        kodlayici,
        resim.as_raw(),
        boyut as u32,
        boyut as u32,
        image::ExtendedColorType::Rgb8,
    )
    .is_err()
    {
        return String::new();
    }
    use base64::Engine;
    format!(
        "data:image/png;base64,{}",
        base64::engine::general_purpose::STANDARD.encode(bayt)
    )
}

// --- internet paylasimi (dar sunucu + cloudflared) -------------------------

fn dar_baslat(ctx: &ApiCtx) -> std::result::Result<u16, &'static str> {
    if let Some((_, port)) = kilit(&DAR).as_ref() {
        return Ok(*port);
    }
    let (dinleyici, port) = bagla("127.0.0.1", 0, 1).map_err(|_| "share.tunnelError")?;
    let (kapat, rx) = tokio::sync::oneshot::channel();
    // Dar sunucu YALNIZ /s/{token} yolunu sunar; tune acilan yuzey yonetim paneli degildir.
    let yonlendirici = Router::new()
        .route("/s/{token}", get(paylasim::s_ana))
        .with_state(ctx.clone());
    sun(dinleyici, yonlendirici, rx);
    *kilit(&DAR) = Some((kapat, port));
    Ok(port)
}

fn dar_kapat() {
    if let Some((kapat, _)) = kilit(&DAR).take() {
        let _ = kapat.send(());
    }
}

/// Python `_internet_linki` tabani: tuneli acar (ya da calisani doner). Hata anahtari Python ile ayni.
pub fn internet_baslat(ctx: &ApiCtx) -> std::result::Result<String, &'static str> {
    if let Some(t) = kilit(&TUNEL).as_ref() {
        if t.aktif() {
            return Ok(t.url().trim_end_matches('/').to_string());
        }
    }
    let exe = tunel::cloudflared_yolu(&ctx.app_dir).ok_or("share.cloudflaredMissing")?;
    let port = dar_baslat(ctx)?;
    if let Some(eski) = kilit(&TUNEL).take() {
        eski.durdur();
    }
    let t = TunelYoneticisi::gercek(exe);
    match t.baslat(port) {
        Ok(url) => {
            let temiz = url.trim_end_matches('/').to_string();
            *kilit(&TUNEL) = Some(t);
            Ok(temiz)
        }
        Err(_) => {
            t.durdur();
            dar_kapat();
            Err("share.tunnelError")
        }
    }
}

/// Aktif tunelin taban adresi (`/s/token` eklenmeden).
pub fn tunel_url() -> Option<String> {
    kilit(&TUNEL)
        .as_ref()
        .filter(|t| t.aktif())
        .map(|t| t.url().trim_end_matches('/').to_string())
}

/// Python paylasim_stop / son paylasim silindiginde: tuneli ve dar sunucuyu kapatir.
pub fn tuneli_durdur() {
    if let Some(t) = kilit(&TUNEL).take() {
        t.durdur();
    }
    dar_kapat();
}

/// Boot sonrasi: ayar aciksa LAN dinleyicisini ve yonetim panelini baslatir (Python main akisi).
pub fn acilista(ctx: &ApiCtx, port: u16) {
    if ctx
        .store
        .get("lan_erisimi")
        .ok()
        .flatten()
        .is_some_and(|v| crate::bridge::truthy(&v))
    {
        if let Err(e) = lan_ac(port) {
            ctx.store
                .log("error", &format!("LAN dinleyicisi acilamadi: {e}"), "");
        }
    }
    let sunucu_acik = ctx
        .store
        .get("sunucu_acik")
        .ok()
        .flatten()
        .is_some_and(|v| crate::bridge::truthy(&v));
    if sunucu_acik
        && depo(ctx)
            .call("yonetici_var_mi", &JsonMap::new())
            .ok()
            .and_then(|v| v.as_bool())
            == Some(true)
    {
        if let Err(e) = sunucu_ac(ctx) {
            ctx.store
                .log("error", &format!("yonetim sunucusu acilamadi: {e}"), "");
        }
    }
}

// --- HTTP yanitlari --------------------------------------------------------

fn depo(c: &ApiCtx) -> ErisimDeposu {
    ErisimDeposu::new(c.store.clone())
}

fn cors(b: Builder, origin: Option<&str>) -> Builder {
    let mut b = b;
    if let Some(o) = origin {
        b = b
            .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, o)
            .header(header::VARY, "Origin");
    }
    b.header(
        header::ACCESS_CONTROL_ALLOW_HEADERS,
        "Content-Type, X-AfuDM-Key, X-AfuDM-Oturum, X-AfuDM-CSRF",
    )
    .header(header::ACCESS_CONTROL_ALLOW_METHODS, "GET, POST, OPTIONS")
    .header(header::ACCESS_CONTROL_MAX_AGE, "600")
}

fn yanit(durum: StatusCode, govde: &Json, origin: Option<&str>, ek: &[(&str, String)]) -> Response {
    let bayt = serde_json::to_vec(govde).unwrap_or_default();
    let mut b = Response::builder()
        .status(durum)
        .header(header::CONTENT_TYPE, "application/json; charset=utf-8")
        .header(header::CACHE_CONTROL, "no-store")
        .header("X-Content-Type-Options", "nosniff")
        .header("Referrer-Policy", "no-referrer");
    for (ad, deger) in ek {
        b = b.header(*ad, deger.as_str());
    }
    cors(b, origin)
        .body(Body::from(bayt))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}

fn cors_yanit(durum: StatusCode, origin: Option<&str>) -> Response {
    cors(Response::builder().status(durum), origin)
        .body(Body::empty())
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}

fn dosya(tur: &str, govde: &'static [u8]) -> Response {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, tur)
        .header(header::CACHE_CONTROL, "no-store")
        .header("X-Content-Type-Options", "nosniff")
        .header("Referrer-Policy", "no-referrer")
        .body(Body::from(govde))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}

fn hata_json(kod: &str, mesaj: &str) -> Json {
    json!({"ok": false, "code": kod, "message": mesaj, "error": mesaj})
}

fn sonuc_yanit(sonuc: Result<Json>, origin: Option<&str>) -> Response {
    match sonuc {
        Ok(v) => yanit(StatusCode::OK, &v, origin, &[]),
        Err(e) => yanit(
            StatusCode::BAD_REQUEST,
            &hata_json("BAD_REQUEST", &e.to_string()),
            origin,
            &[],
        ),
    }
}

// --- kapi (anahtar, rol, origin, hiz siniri, CSRF, oturum) -----------------

struct Kimlik {
    id: i64,
    rol: String,
    ad: String,
}

impl Panel {
    /// Python `_izinli_originler`: kendi adresler + etkin profilin/genel ayarin listesi.
    fn originler(&self) -> BTreeSet<String> {
        let port = self.port;
        let mut kume = BTreeSet::new();
        kume.insert(format!("http://127.0.0.1:{port}"));
        kume.insert(format!("http://localhost:{port}"));
        if !self.lan_ip.is_empty() {
            kume.insert(format!("http://{}:{port}", self.lan_ip));
        }
        if let Ok(ayar) = kopru_h::sunucu_ayarlari(&self.ctx) {
            let ham = ayar["originler"].as_str().unwrap_or("");
            for parca in ham.replace(',', "\n").lines() {
                let temiz = parca.trim().trim_end_matches('/');
                if !temiz.is_empty() {
                    kume.insert(temiz.to_string());
                }
            }
        }
        kume
    }
}

/// (origin uygun mu, izinli origin degeri). Origin yoksa uygun ve None.
fn origin_kontrol(p: &Panel, h: &HeaderMap) -> (bool, Option<String>) {
    let ham = h
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if ham.chars().any(|c| (c as u32) < 32) {
        return (false, None);
    }
    let origin = ham.trim().trim_end_matches('/').to_string();
    if origin.is_empty() {
        return (true, None);
    }
    if p.originler().contains(&origin) {
        (true, Some(origin))
    } else {
        (false, None)
    }
}

fn anahtar_al(h: &HeaderMap) -> String {
    let dogrudan = h
        .get(ANAHTAR_BASLIK)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .trim()
        .to_string();
    if !dogrudan.is_empty() {
        return dogrudan;
    }
    h.get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|y| y.len() > 7 && y[..7].eq_ignore_ascii_case("bearer "))
        .map(|y| y[7..].trim().to_string())
        .unwrap_or_default()
}

fn istemci_ip(p: &Panel, peer: SocketAddr, h: &HeaderMap) -> String {
    let guven = p
        .ctx
        .store
        .get("sunucu_proxy_guven")
        .ok()
        .flatten()
        .is_some_and(|v| crate::bridge::truthy(&v));
    proxy_istemci_ip(guven, peer, h)
}

fn proxy_istemci_ip(guven: bool, peer: SocketAddr, h: &HeaderMap) -> String {
    let mut ip = peer.ip().to_string();
    if guven && peer.ip().is_loopback() {
        if let Some(xff) = h.get("x-forwarded-for").and_then(|v| v.to_str().ok()) {
            if let Some(son) = xff.split(',').map(str::trim).next_back() {
                if !son.is_empty() {
                    ip = son.to_string();
                }
            }
        }
    }
    ip
}

fn reddet(
    p: &Panel,
    durum: u16,
    kod: &str,
    mesaj: &str,
    origin: Option<&str>,
    ek: &[(&str, String)],
) -> Response {
    p.red.fetch_add(1, Ordering::Relaxed);
    let durum = StatusCode::from_u16(durum).unwrap_or(StatusCode::FORBIDDEN);
    yanit(durum, &hata_json(kod, mesaj), origin, ek)
}

/// Python `_yetkilendir`: sirasiyla hiz siniri, origin, CSRF, anahtar, rol, oturum.
// Hata yaniti dogrudan HTTP yanitidir (kutulamaya gerek yok; istek basina bir kez olusur).
#[allow(clippy::result_large_err)]
fn kapi(
    p: &Panel,
    peer: SocketAddr,
    h: &HeaderMap,
    izin: &str,
    yazma: bool,
    origin_uygun: bool,
    origin: Option<&str>,
) -> std::result::Result<Kimlik, Response> {
    let ip = istemci_ip(p, peer, h);
    let izin_yanit = match p.limit.call("izin_ver", &ip) {
        Ok(v) => v,
        Err(_) => {
            return Err(reddet(
                p,
                500,
                "INTERNAL",
                "hiz siniri okunamadi",
                origin,
                &[],
            ));
        }
    };
    if !izin_yanit[0].as_bool().unwrap_or(false) {
        let saniye = (izin_yanit[1].as_f64().unwrap_or(0.0) + 1.0) as i64;
        return Err(reddet(
            p,
            429,
            "COK_FAZLA_ISTEK",
            &format!("cok fazla istek — {saniye} saniye sonra tekrar dene"),
            origin,
            &[("Retry-After", saniye.to_string())],
        ));
    }
    if !origin_uygun {
        return Err(reddet(
            p,
            403,
            "ORIGIN_REDDEDILDI",
            "bu adresten gelen istekler izinli degil",
            None,
            &[],
        ));
    }
    if yazma
        && h.get(CSRF_BASLIK)
            .and_then(|v| v.to_str().ok())
            .is_none_or(|v| v.trim().is_empty())
    {
        return Err(reddet(
            p,
            403,
            "CSRF_BASLIGI_YOK",
            &format!("durum degistiren istek {CSRF_BASLIK} basligi ister"),
            origin,
            &[],
        ));
    }
    let sunulan = anahtar_al(h);
    let kayit = if sunulan.is_empty() {
        Json::Null
    } else {
        depo(&p.ctx)
            .call("dogrula", &harita(json!({"sunulan": sunulan})))
            .unwrap_or(Json::Null)
    };
    if !kayit.is_object() {
        let _ = p.limit.call("hatali", &ip);
        let (kod, mesaj) = if sunulan.is_empty() {
            ("ANAHTAR_GEREKLI", "erisim anahtari gerekli")
        } else {
            ("GECERSIZ_ANAHTAR", "anahtar gecersiz veya iptal edilmis")
        };
        return Err(reddet(p, 401, kod, mesaj, origin, &[]));
    }
    let _ = p.limit.call("basarili", &ip);
    let rol = kayit["rol"].as_str().unwrap_or("").to_string();
    let id = kayit["id"].as_i64().unwrap_or(0);
    let ad = kayit["ad"].as_str().unwrap_or("").to_string();
    if !erisim::izinli(&rol, izin) {
        return Err(reddet(
            p,
            403,
            "YETKI_YOK",
            &format!("bu islem icin 'yonetici' rolu gerekir (rolun: {rol})"),
            origin,
            &[],
        ));
    }
    let oturum = h
        .get(OTURUM_BASLIK)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .trim()
        .to_string();
    if !oturum.is_empty() && kopru_h::ayar_bool(&p.ctx, "sunucu_istemci_kaydi") {
        let dokun = depo(&p.ctx)
            .call("oturum_dokun", &harita(json!({"oturum": oturum, "ip": ip})))
            .unwrap_or(Json::Null);
        if dokun.is_null() {
            return Err(reddet(
                p,
                401,
                "OTURUM_IPTAL",
                "oturumun iptal edildi — yeniden baglan",
                origin,
                &[],
            ));
        }
    }
    let _ = depo(&p.ctx).call("kullanim_isle", &harita(json!({"key_id": id})));
    p.istek.fetch_add(1, Ordering::Relaxed);
    Ok(Kimlik { id, rol, ad })
}

fn harita(v: Json) -> JsonMap {
    v.as_object().cloned().unwrap_or_default()
}

/// Python `_yol`: sondaki bolu kesilir; bos yol "/".
fn yol_norm(ham: &str) -> String {
    let t = ham.trim_end_matches('/');
    if t.is_empty() {
        "/".to_string()
    } else {
        t.to_string()
    }
}

/// Basit sorgu cozucu (percent + '+').
fn coz(ham: &str) -> String {
    let b = ham.as_bytes();
    let mut cikti = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'+' => {
                cikti.push(b' ');
                i += 1;
            }
            b'%' if i + 2 < b.len() => {
                match std::str::from_utf8(&b[i + 1..i + 3])
                    .ok()
                    .and_then(|h| u8::from_str_radix(h, 16).ok())
                {
                    Some(v) => {
                        cikti.push(v);
                        i += 3;
                    }
                    None => {
                        cikti.push(b'%');
                        i += 1;
                    }
                }
            }
            c => {
                cikti.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&cikti).into_owned()
}

fn sorgu_al(uri: &Uri) -> Vec<(String, String)> {
    uri.query()
        .unwrap_or("")
        .split('&')
        .filter(|p| !p.is_empty())
        .map(|p| {
            let (ad, deger) = p.split_once('=').unwrap_or((p, ""));
            (coz(ad), coz(deger))
        })
        .collect()
}

fn sorgu_deger(sorgu: &[(String, String)], ad: &str) -> String {
    sorgu
        .iter()
        .find(|(a, _)| a == ad)
        .map(|(_, d)| d.clone())
        .unwrap_or_default()
}

fn get_izin(yol: &str) -> Option<&'static str> {
    match yol {
        "/api/yetenekler" | "/api/durum" | "/api/liste" | "/api/ayarlar" | "/api/olaylar" => {
            Some("oku")
        }
        "/api/anahtarlar" | "/api/istemciler" | "/api/profiller" => Some("yonet"),
        _ => None,
    }
}

fn post_izin(yol: &str) -> Option<&'static str> {
    match yol {
        "/api/oturum" | "/api/oturum/kapat" => Some("oku"),
        "/api/ekle"
        | "/api/kontrol"
        | "/api/yeniden-dene"
        | "/api/temizle"
        | "/api/hiz-profili"
        | "/api/baglanti-ayarla" => Some("yaz"),
        "/api/ayarlar" => Some("ayar"),
        "/api/anahtar/olustur"
        | "/api/anahtar/rotasyon"
        | "/api/anahtar/iptal"
        | "/api/anahtar/sil"
        | "/api/anahtar/rol"
        | "/api/istemci/iptal"
        | "/api/istemci/temizle"
        | "/api/kilit/temizle"
        | "/api/profil/kaydet"
        | "/api/profil/sil"
        | "/api/profil/etkinlestir"
        | "/api/sunucu/durdur" => Some("yonet"),
        _ => None,
    }
}

/// Python `IZINLER` karsiligi (oturum yanitindaki izin listesi, alfabetik).
fn izin_listesi(rol: &str) -> Vec<&'static str> {
    match rol {
        "yonetici" => vec!["ayar", "oku", "yaz", "yonet"],
        "salt_okur" => vec!["oku"],
        _ => vec![],
    }
}

// --- istek islemcisi -------------------------------------------------------

async fn istek(
    State(p): State<Arc<Panel>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    metot: Method,
    uri: Uri,
    basliklar: HeaderMap,
    govde: Body,
) -> Response {
    let yol = yol_norm(uri.path());
    let (origin_uygun, origin) = origin_kontrol(&p, &basliklar);
    if metot == Method::OPTIONS {
        let durum = if origin_uygun {
            StatusCode::NO_CONTENT
        } else {
            StatusCode::FORBIDDEN
        };
        return cors_yanit(durum, origin.as_deref());
    }
    let origin_ref = origin.as_deref();
    if metot == Method::GET {
        match yol.as_str() {
            "/api/ping" => {
                return yanit(
                    StatusCode::OK,
                    &json!({"ok": true, "app": "AfuDM", "panel": true}),
                    None,
                    &[],
                )
            }
            "/" | "/panel" => return dosya("text/html; charset=utf-8", PANEL_HTML),
            "/varlik/i18n.js" => return dosya("application/javascript; charset=utf-8", I18N_JS),
            "/varlik/style.css" => return dosya("text/css; charset=utf-8", STYLE_CSS),
            _ => {}
        }
        let Some(izin) = get_izin(&yol) else {
            return yanit(
                StatusCode::NOT_FOUND,
                &hata_json("BILINMEYEN_YOL", "bilinmeyen yol"),
                origin_ref,
                &[],
            );
        };
        let kimlik = match kapi(&p, peer, &basliklar, izin, false, origin_uygun, origin_ref) {
            Ok(k) => k,
            Err(r) => return r,
        };
        let sorgu = sorgu_al(&uri);
        return sonuc_yanit(get_calistir(&p, &yol, &sorgu, &kimlik), origin_ref);
    }
    if metot == Method::POST {
        let Some(izin) = post_izin(&yol) else {
            return yanit(
                StatusCode::NOT_FOUND,
                &hata_json("BILINMEYEN_YOL", "bilinmeyen yol"),
                origin_ref,
                &[],
            );
        };
        let kimlik = match kapi(&p, peer, &basliklar, izin, true, origin_uygun, origin_ref) {
            Ok(k) => k,
            Err(r) => return r,
        };
        let bayt = match axum::body::to_bytes(govde, GOVDE_LIMITI).await {
            Ok(b) => b,
            Err(_) => {
                return yanit(
                    StatusCode::PAYLOAD_TOO_LARGE,
                    &hata_json(
                        "GOVDE_HATASI",
                        "istek govdesi en fazla 2000000 bayt olabilir",
                    ),
                    origin_ref,
                    &[],
                )
            }
        };
        let veri: JsonMap = if bayt.is_empty() {
            JsonMap::new()
        } else {
            match serde_json::from_slice::<Json>(&bayt) {
                Ok(Json::Object(m)) => m,
                Ok(_) => JsonMap::new(),
                Err(_) => {
                    return yanit(
                        StatusCode::BAD_REQUEST,
                        &hata_json("GOVDE_HATASI", "gecersiz JSON govdesi"),
                        origin_ref,
                        &[],
                    )
                }
            }
        };
        let ip = istemci_ip(&p, peer, &basliklar);
        let ua: String = basliklar
            .get(header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
            .unwrap_or("")
            .chars()
            .take(120)
            .collect();
        let oturum = basliklar
            .get(OTURUM_BASLIK)
            .and_then(|v| v.to_str().ok())
            .unwrap_or("")
            .trim()
            .to_string();
        return sonuc_yanit(
            post_calistir(&p, &yol, &veri, &kimlik, &ip, &ua, &oturum),
            origin_ref,
        );
    }
    yanit(
        StatusCode::METHOD_NOT_ALLOWED,
        &hata_json("BILINMEYEN_YOL", "bilinmeyen yol"),
        origin_ref,
        &[],
    )
}

fn get_calistir(p: &Panel, yol: &str, sorgu: &[(String, String)], k: &Kimlik) -> Result<Json> {
    let c = &p.ctx;
    match yol {
        "/api/yetenekler" => Ok(json!({
            "ok": true,
            "app": "AfuDM",
            "surum": env!("CARGO_PKG_VERSION"),
            "api": 2,
            "kip": "rust",
            "roller": ["yonetici", "salt_okur"],
            "rol": k.rol,
        })),
        "/api/durum" => {
            let snap = c.manager.snapshot()?;
            let ogeler = snap["items"].as_array().cloned().unwrap_or_default();
            let aktif = ogeler.iter().filter(|o| o["status"] == "active").count();
            let mut cikti = json!({
                "ok": true,
                "app": "AfuDM",
                "surum": env!("CARGO_PKG_VERSION"),
                "kip": "rust",
                "aktif_indirme": aktif,
                "toplam_indirme": ogeler.len(),
                "hiz": snap["speed"].clone(),
                "indirme_klasoru": c.manager.current_download_dir()?,
                "rol": k.rol,
            });
            if let (Some(hedef), Json::Object(kaynak)) =
                (cikti.as_object_mut(), kopru_h::sunucu_durumu(c)?)
            {
                hedef.extend(kaynak);
            }
            Ok(cikti)
        }
        "/api/liste" => {
            let mut snap = c.manager.snapshot()?;
            let f = match sorgu_deger(sorgu, "filtre").trim().to_lowercase().as_str() {
                "" => "all".to_string(),
                x => x.to_string(),
            };
            let ara = sorgu_deger(sorgu, "arama").trim().to_lowercase();
            let ogeler: Vec<Json> = snap["items"]
                .as_array()
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .filter(|o| filtreye_uyar(o, &f) && (ara.is_empty() || arama_uyar(o, &ara)))
                .collect();
            snap["items"] = Json::Array(ogeler);
            snap["ok"] = json!(true);
            Ok(snap)
        }
        "/api/ayarlar" => Ok(json!({"ok": true, "settings": c.store.all_settings()?})),
        "/api/olaylar" => {
            let gid = sorgu_deger(sorgu, "gid");
            let limit = sorgu_deger(sorgu, "limit")
                .parse::<usize>()
                .unwrap_or(60)
                .clamp(1, 500);
            Ok(json!({"ok": true, "events": c.store.recent_events(limit, &gid)?}))
        }
        "/api/anahtarlar" => kopru_h::sunucu_anahtarlar(c),
        "/api/istemciler" => {
            let dakika = sorgu_deger(sorgu, "dakika").parse::<i64>().unwrap_or(0);
            kopru_h::sunucu_istemciler(c, dakika)
        }
        "/api/profiller" => kopru_h::sunucu_profiller(c),
        _ => Ok(hata_json("BILINMEYEN_YOL", "bilinmeyen yol")),
    }
}

fn filtreye_uyar(oge: &Json, f: &str) -> bool {
    let durum = oge["status"].as_str().unwrap_or("");
    let tur = oge["kind"].as_str().unwrap_or("");
    match f {
        "active" | "paused" | "complete" | "error" => durum == f,
        "video" | "torrent" | "http" => tur == f,
        _ => true,
    }
}

fn arama_uyar(oge: &Json, ara: &str) -> bool {
    ["title", "filename", "source"]
        .iter()
        .any(|a| oge[*a].as_str().unwrap_or("").to_lowercase().contains(ara))
}

fn post_calistir(
    p: &Panel,
    yol: &str,
    veri: &JsonMap,
    k: &Kimlik,
    ip: &str,
    ua: &str,
    oturum: &str,
) -> Result<Json> {
    let c = &p.ctx;
    let id = veri.get("id").and_then(Json::as_i64).unwrap_or(0);
    let metin = |anahtar: &str| {
        veri.get(anahtar)
            .and_then(Json::as_str)
            .unwrap_or("")
            .to_string()
    };
    match yol {
        "/api/oturum" => {
            let mut oturum_kodu = String::new();
            if kopru_h::ayar_bool(c, "sunucu_istemci_kaydi") {
                if let Json::String(s) = depo(c).call(
                    "oturum_ac",
                    &harita(json!({"key_id": k.id, "rol": k.rol, "ip": ip, "istemci": ua})),
                )? {
                    oturum_kodu = s;
                }
            }
            Ok(json!({
                "ok": true,
                "rol": k.rol,
                "anahtar_adi": k.ad,
                "oturum": oturum_kodu,
                "csrf_baslik": CSRF_BASLIK,
                "izinler": izin_listesi(&k.rol),
            }))
        }
        "/api/oturum/kapat" => {
            if !oturum.is_empty() {
                let dokun =
                    depo(c).call("oturum_dokun", &harita(json!({"oturum": oturum, "ip": ip})))?;
                if let Some(oid) = dokun.get("id").and_then(Json::as_i64) {
                    depo(c).call("oturum_iptal", &harita(json!({"client_id": oid})))?;
                }
            }
            Ok(json!({"ok": true}))
        }
        "/api/ekle" => ekle(p, veri),
        "/api/kontrol" => {
            let eylem = {
                let a = metin("action");
                if a.is_empty() {
                    metin("eylem")
                } else {
                    a
                }
            };
            let gid = metin("gid");
            let dosyalari_sil = veri
                .get("delete_files")
                .and_then(Json::as_bool)
                .unwrap_or(false);
            let sonuc = match eylem.trim() {
                "pause" => c.manager.pause(&gid).map(|_| ()),
                "resume" => c.manager.resume(&gid).map(|_| ()),
                "remove" => c.manager.remove(&gid, dosyalari_sil).map(|_| ()),
                "pause_all" => c.manager.pause_all(),
                "resume_all" => c.manager.resume_all(),
                _ => Err(AfuError::Invalid("bilinmeyen islem".into())),
            };
            Ok(match sonuc {
                Ok(()) => json!({"ok": true}),
                Err(e) => json!({"ok": false, "code": "BAD_REQUEST", "error": e.to_string()}),
            })
        }
        "/api/baglanti-ayarla" => Ok(json!({
            "ok": false,
            "code": "NOT_IMPLEMENTED",
            "error": "bu islem bu surumde henuz yok",
        })),
        "/api/yeniden-dene" => c.manager.retry(id),
        "/api/temizle" => Ok(json!({"ok": true, "removed": c.store.clear_finished()?})),
        "/api/hiz-profili" => {
            let sonuc = c.manager.set_mode(&metin("profil"));
            Ok(match sonuc {
                Ok(v) => {
                    let mut cikti = json!({"ok": true});
                    if let (Some(h), Json::Object(kaynak)) = (cikti.as_object_mut(), v) {
                        h.extend(kaynak);
                    }
                    cikti
                }
                Err(e) => json!({"ok": false, "code": "BAD_REQUEST", "error": e.to_string()}),
            })
        }
        "/api/ayarlar" => {
            let payload = veri
                .get("settings")
                .and_then(Json::as_object)
                .cloned()
                .unwrap_or_else(|| veri.clone());
            Ok(match c.manager.update_settings(&payload) {
                Ok(kayit) => json!({"ok": true, "settings": kayit}),
                Err(e) => json!({"ok": false, "code": "AYAR_HATASI", "error": e.to_string()}),
            })
        }
        "/api/anahtar/olustur" => {
            kopru_h::sunucu_anahtar_olustur(c, &metin("ad"), &metin("rol"), &metin("not_metni"))
        }
        "/api/anahtar/rotasyon" => kopru_h::anahtar_cagri(c, "anahtar_rotasyon", id, None),
        "/api/anahtar/iptal" => kopru_h::anahtar_cagri(c, "anahtar_iptal", id, None),
        "/api/anahtar/sil" => kopru_h::anahtar_sil(c, id),
        "/api/anahtar/rol" => {
            kopru_h::anahtar_cagri(c, "anahtar_rol_ayarla", id, Some(&metin("rol")))
        }
        "/api/istemci/iptal" => kopru_h::sunucu_istemci_iptal(c, id),
        "/api/istemci/temizle" => {
            let gun = veri
                .get("gun")
                .and_then(Json::as_i64)
                .filter(|g| *g != 0)
                .unwrap_or(7);
            kopru_h::sunucu_istemci_temizle(c, gun)
        }
        "/api/kilit/temizle" => kopru_h::sunucu_kilit_temizle(c),
        "/api/profil/kaydet" => kopru_h::sunucu_profil_kaydet(c, veri),
        "/api/profil/sil" => kopru_h::sunucu_profil_sil(c, id),
        "/api/profil/etkinlestir" => kopru_h::sunucu_profil_etkinlestir(c, id),
        "/api/sunucu/durdur" => {
            // Python: yanit gonderildikten sonra kapanir (0.5 sn gecikme).
            let ctx = c.clone();
            tauri::async_runtime::spawn(async move {
                tokio::time::sleep(Duration::from_millis(500)).await;
                let _ = kopru_h::sunucu_durdur(&ctx);
            });
            Ok(json!({"ok": true, "kapaniyor": true}))
        }
        _ => Ok(hata_json("BILINMEYEN_YOL", "bilinmeyen yol")),
    }
}

/// Python `servis.ekle`: link listesi icin manager.add; kismi basari `failed` ile raporlanir.
fn ekle(p: &Panel, veri: &JsonMap) -> Result<Json> {
    let c = &p.ctx;
    let mut urller: Vec<String> = veri
        .get("urls")
        .and_then(Json::as_array)
        .map(|a| {
            a.iter()
                .filter_map(Json::as_str)
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect()
        })
        .unwrap_or_default();
    if urller.is_empty() {
        let tek = veri
            .get("url")
            .or_else(|| veri.get("source"))
            .and_then(Json::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        if !tek.is_empty() {
            urller.push(tek);
        }
    }
    if urller.is_empty() {
        return Ok(json!({"ok": false, "code": "BAD_REQUEST", "error": "link gerekli"}));
    }
    let tek_ad = if urller.len() == 1 {
        afudm_db::kaydet::guvenli_dosya_adi(
            veri.get("filename").and_then(Json::as_str).unwrap_or(""),
        )
    } else {
        String::new()
    };
    let secilen = veri
        .get("dest_dir")
        .and_then(Json::as_str)
        .unwrap_or("")
        .to_string();
    let kategori = veri
        .get("kategori")
        .and_then(Json::as_str)
        .unwrap_or("")
        .to_string();
    let mut eklenen = 0usize;
    let mut hatalar: Vec<String> = Vec::new();
    for url in urller {
        let kind = afudm_core::queue::detect_kind(&url).to_string();
        let sonuc = (|| -> std::result::Result<(), String> {
            let hedef = hedef_klasor(c, &secilen, &url, &kind, &kategori, true)?;
            let mut istek = JsonMap::new();
            istek.insert("source".into(), json!(url));
            istek.insert("kind".into(), json!(kind));
            if let Some(h) = hedef {
                istek.insert("dest_dir".into(), json!(h));
            }
            if !tek_ad.is_empty() {
                let anahtar = if kind == "video" { "title" } else { "filename" };
                if kind == "http" || kind == "video" {
                    istek.insert(anahtar.into(), json!(tek_ad));
                }
            }
            if let Some(q) = veri.get("quality").filter(|v| crate::bridge::truthy(v)) {
                istek.insert("quality".into(), q.clone());
            }
            istek.insert(
                "audio_only".into(),
                json!(veri
                    .get("audio_only")
                    .and_then(Json::as_bool)
                    .unwrap_or(false)),
            );
            istek.insert(
                "playlist".into(),
                json!(veri
                    .get("playlist")
                    .and_then(Json::as_bool)
                    .unwrap_or(false)),
            );
            match c.manager.add(&istek) {
                Ok(s) if s["ok"] == json!(false) => Err(s["error"]
                    .as_str()
                    .unwrap_or("indirme reddedildi")
                    .to_string()),
                Ok(_) => Ok(()),
                Err(e) => Err(e.to_string()),
            }
        })();
        match sonuc {
            Ok(()) => eklenen += 1,
            Err(mesaj) => hatalar.push(format!(
                "{}: {}",
                url.chars().take(48).collect::<String>(),
                mesaj.chars().take(120).collect::<String>()
            )),
        }
    }
    if eklenen == 0 && !hatalar.is_empty() {
        return Ok(
            json!({"ok": false, "code": "EKLENEMEDI", "error": hatalar[0], "failed": hatalar}),
        );
    }
    Ok(json!({"ok": true, "added": eklenen, "scheduled": 0, "failed": hatalar}))
}

/// Python `hedef_klasor`: secilen yol > kategori kurali > genel varsayilan (None).
/// Uzaktan (panel) istekte secilen yol indirme kokunun altinda olmalidir.
pub(crate) fn hedef_klasor(
    c: &ApiCtx,
    secilen: &str,
    url: &str,
    kind: &str,
    kategori: &str,
    uzaktan: bool,
) -> std::result::Result<Option<String>, String> {
    let ana = c
        .manager
        .current_download_dir()
        .map_err(|e| e.to_string())?;
    if !secilen.is_empty() {
        if uzaktan && !PathBuf::from(secilen).starts_with(PathBuf::from(&ana)) {
            return Err("hedef klasor izinli kok dizin disinda".into());
        }
        return Ok(Some(secilen.to_string()));
    }
    if !kopru_h::ayar_bool(c, "kategori_klasorleri") {
        return Ok(None);
    }
    let kat = if kategori.is_empty() {
        afudm_db::kaydet::kategori_tahmin(url, kind, "")
    } else {
        kategori.to_string()
    };
    Ok(Some(afudm_db::kaydet::kategori_klasoru(&ana, &kat)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn proxy_yalniz_loopback_peer_icin_guvenilir() {
        let mut h = HeaderMap::new();
        h.insert(
            "x-forwarded-for",
            "198.51.100.1, 203.0.113.8".parse().unwrap(),
        );
        for (guven, peer, beklenen) in [
            (true, "192.168.1.8:42", "192.168.1.8"),
            (false, "127.0.0.1:42", "127.0.0.1"),
            (true, "127.0.0.1:42", "203.0.113.8"),
            (true, "[::1]:42", "203.0.113.8"),
        ] {
            assert_eq!(proxy_istemci_ip(guven, peer.parse().unwrap(), &h), beklenen);
        }
        assert_eq!(
            proxy_istemci_ip(true, "127.0.0.1:42".parse().unwrap(), &HeaderMap::new()),
            "127.0.0.1"
        );
    }

    #[test]
    fn qr_png_data_uri_olusur() {
        let uri = qr_uri("http://192.168.1.5:6811/m?k=abc");
        assert!(uri.starts_with("data:image/png;base64,"));
        assert!(uri.len() > 100);
    }

    #[test]
    fn sorgu_cozulur() {
        assert_eq!(coz("a+b%20c"), "a b c");
        assert_eq!(coz("%C3%BC"), "ü");
    }

    #[test]
    fn yol_sondaki_bolu_kesilir() {
        assert_eq!(yol_norm("/api/durum/"), "/api/durum");
        assert_eq!(yol_norm("/"), "/");
    }

    #[test]
    fn filtre_ve_arama() {
        let oge = json!({"status": "active", "kind": "http", "title": "Film", "filename": "a.mp4", "source": "https://x"});
        assert!(filtreye_uyar(&oge, "active"));
        assert!(!filtreye_uyar(&oge, "paused"));
        assert!(arama_uyar(&oge, "film"));
    }
}
