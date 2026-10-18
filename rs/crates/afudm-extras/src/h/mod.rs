//! SAHIBI: Ekip H. Paylasim (HTTP + dar sunucu), tunel, SMB, mobil eslestirme.
//! Python: core/paylasim_sunucusu.py, core/tunel.py, core/smb_paylasim.py,
//! api/server.py (/pair, /m, /share_create, /s/...), app.py (start_pairing, share_*).
//! Kimlik dogrulama (T/A) E ekibinin `with_auth` katmanindadir; bu router yalniz H uclarini tanimlar.

pub mod esleme;
pub mod paylasim;
pub mod smb;
pub mod tunel;

use afudm_types::{AfuError, ApiCtx};
use axum::body::Body;
use axum::extract::DefaultBodyLimit;
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::Json;
use serde_json::json;

// Telefon arayuzu ve PWA dosyalari derleme aaninda exe'ye gomulur (Python: paths.UI).
// Kaynak rs/app/ui, P\ui ile birebir ayni; exe yaninda ui klasoru beklenmez.
const MOBIL_HTML: &[u8] = include_bytes!("../../../../app/ui/mobil.html");
const MANIFEST: &[u8] = include_bytes!("../../../../app/ui/manifest.webmanifest");
const I18N_JS: &[u8] = include_bytes!("../../../../app/ui/i18n.js");
const SW_JS: &[u8] = include_bytes!("../../../../app/ui/sw.js");
const IKON_PNG: &[u8] = include_bytes!("../../../../app/ui/icon.png");

/// Gomulu dosyayi Python `_sayfa_gonder` basliklariyla dondurur.
fn gomulu(govde: &'static [u8], tur: &str, onbellek: &str, ek: &[(&str, &str)]) -> Response {
    let mut yanit = Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, tur)
        .header(header::CACHE_CONTROL, onbellek);
    for (ad, deger) in ek {
        yanit = yanit.header(*ad, *deger);
    }
    yanit
        .body(Body::from(govde))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}
/// `GET /m` ve `/m/`: mobil.html, onbellek yok.
async fn mobil_sayfa() -> Response {
    gomulu(MOBIL_HTML, "text/html; charset=utf-8", "no-store", &[])
}
async fn manifest_dosya() -> Response {
    gomulu(
        MANIFEST,
        "application/manifest+json; charset=utf-8",
        "no-cache",
        &[],
    )
}
async fn i18n_dosya() -> Response {
    gomulu(I18N_JS, "text/javascript; charset=utf-8", "no-cache", &[])
}
/// `GET /sw.js`: Worker tum kok yolu kapsar.
async fn sw_dosya() -> Response {
    gomulu(
        SW_JS,
        "text/javascript; charset=utf-8",
        "no-cache",
        &[("Service-Worker-Allowed", "/")],
    )
}
async fn ikon_dosya() -> Response {
    gomulu(IKON_PNG, "image/png", "public, max-age=31536000", &[])
}

/// Python api/server.py `_Handler` H rotalari.
pub fn router(ctx: ApiCtx) -> axum::Router {
    axum::Router::new()
        .route("/pair", get(esleme::pair))
        .route("/m", get(mobil_sayfa))
        .route("/m/", get(mobil_sayfa))
        .route("/manifest.webmanifest", get(manifest_dosya))
        .route("/i18n.js", get(i18n_dosya))
        .route("/sw.js", get(sw_dosya))
        .route("/ikon.png", get(ikon_dosya))
        .route(
            "/share_create",
            post(paylasim::share_create).layer(DefaultBodyLimit::max(8 * 1024 * 1024)),
        )
        .route("/s/{token}", get(paylasim::s_ana))
        .with_state(ctx)
}

/// Python api/server.py `_hata`: {"ok":false,"code","message","error"} (message ve error ayni metin).
pub(crate) fn hata(durum: StatusCode, kod: &str, mesaj: &str) -> Response {
    (
        durum,
        Json(json!({"ok": false, "code": kod, "message": mesaj, "error": mesaj})),
    )
        .into_response()
}

/// Manager/Store/motor hatasi: Python uyumlu ortak govde ({ok,code,message,error}).
pub(crate) fn afu_hata(e: &AfuError) -> Response {
    afudm_api::hata_yaniti(e)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn statik_dosyalar_gomulu_ve_python_basliklariyla_gelir() {
        let m = mobil_sayfa().await;
        assert_eq!(m.status(), StatusCode::OK);
        assert_eq!(m.headers()["cache-control"], "no-store");
        assert!(m.headers()["content-type"]
            .to_str()
            .unwrap()
            .starts_with("text/html"));
        assert_eq!(
            manifest_dosya().await.headers()["cache-control"],
            "no-cache"
        );
        assert_eq!(i18n_dosya().await.headers()["cache-control"], "no-cache");
        let sw = sw_dosya().await;
        assert_eq!(sw.headers()["service-worker-allowed"], "/");
        assert_eq!(sw.headers()["cache-control"], "no-cache");
        let ikon = ikon_dosya().await;
        assert_eq!(ikon.headers()["content-type"], "image/png");
        assert_eq!(ikon.headers()["cache-control"], "public, max-age=31536000");
        assert!(!MOBIL_HTML.is_empty() && !MANIFEST.is_empty() && !I18N_JS.is_empty());
        assert!(!SW_JS.is_empty() && !IKON_PNG.is_empty());
    }
}
