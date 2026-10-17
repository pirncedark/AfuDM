//! SAHIBI: Ekip H. Paylasim (HTTP + dar sunucu), tunel, SMB, mobil eslestirme.
//! Python: core/paylasim_sunucusu.py, core/tunel.py, core/smb_paylasim.py,
//! api/server.py (/pair, /m, /share_create, /s/...), app.py (start_pairing, share_*).
//! Kimlik dogrulama (T/A) E ekibinin `with_auth` katmanindadir; bu router yalniz H uclarini tanimlar.

pub mod esleme;
pub mod mobil;
pub mod paylasim;
pub mod smb;
pub mod tunel;

use afudm_types::{AfuError, ApiCtx};
use axum::extract::DefaultBodyLimit;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::Json;
use serde_json::json;

/// Python api/server.py `_Handler` H rotalari.
pub fn router(ctx: ApiCtx) -> axum::Router {
    axum::Router::new()
        .route("/pair", get(esleme::pair))
        .route("/m", get(mobil::m))
        .route("/m/", get(mobil::m))
        .route("/manifest.webmanifest", get(mobil::manifest))
        .route("/i18n.js", get(mobil::i18n))
        .route("/sw.js", get(mobil::sw))
        .route("/ikon.png", get(mobil::ikon))
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

/// Manager/Store/motor hatasi (API_SOZLESME: Invalid 400, NotFound 404, Engine 502,
/// Unavailable 503, digerleri 500): {"ok":false,"error":"..."}.
pub(crate) fn afu_hata(e: &AfuError) -> Response {
    let durum = match e {
        AfuError::Invalid(_) => StatusCode::BAD_REQUEST,
        AfuError::NotFound(_) => StatusCode::NOT_FOUND,
        AfuError::Engine(_) => StatusCode::BAD_GATEWAY,
        AfuError::Unavailable(_) => StatusCode::SERVICE_UNAVAILABLE,
        _ => StatusCode::INTERNAL_SERVER_ERROR,
    };
    (durum, Json(json!({"ok": false, "error": e.to_string()}))).into_response()
}
