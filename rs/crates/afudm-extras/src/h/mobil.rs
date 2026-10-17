//! Telefon arayuzu ve PWA dosyalari. Python: api/server.py GET `/m`, `/manifest.webmanifest`,
//! `/i18n.js`, `/sw.js`, `/ikon.png`. Dosyalar `<app_dir>\ui\` altindan okunur (Python paths.UI).
//! Sayfa anahtarsiz gelir; API cagrilari anahtari kendi basligiyla yapar.

use std::path::Path;

use afudm_types::ApiCtx;
use axum::body::Body;
use axum::extract::State;
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};

/// Dosyayi verilen baslik ve onbellek politikasiyla gonderir (Python `_sayfa_gonder`).
fn sayfa(yol: &Path, tur: &str, onbellek: &str, ek: &[(&str, &str)]) -> Response {
    let govde = match std::fs::read(yol) {
        Ok(g) => g,
        Err(_) => return super::hata(StatusCode::NOT_FOUND, "SAYFA_YOK", "sayfa bulunamadi"),
    };
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

/// `GET /m` ve `/m/`: telefon arayuzu (mobil.html), onbellek yok.
pub async fn m(State(ctx): State<ApiCtx>) -> Response {
    sayfa(
        &ctx.app_dir.join("ui").join("mobil.html"),
        "text/html; charset=utf-8",
        "no-store",
        &[],
    )
}

/// `GET /manifest.webmanifest`.
pub async fn manifest(State(ctx): State<ApiCtx>) -> Response {
    sayfa(
        &ctx.app_dir.join("ui").join("manifest.webmanifest"),
        "application/manifest+json; charset=utf-8",
        "no-cache",
        &[],
    )
}

/// `GET /i18n.js`.
pub async fn i18n(State(ctx): State<ApiCtx>) -> Response {
    sayfa(
        &ctx.app_dir.join("ui").join("i18n.js"),
        "text/javascript; charset=utf-8",
        "no-cache",
        &[],
    )
}

/// `GET /sw.js`: Worker tum kok yolu kapsar.
pub async fn sw(State(ctx): State<ApiCtx>) -> Response {
    sayfa(
        &ctx.app_dir.join("ui").join("sw.js"),
        "text/javascript; charset=utf-8",
        "no-cache",
        &[("Service-Worker-Allowed", "/")],
    )
}

/// `GET /ikon.png` (dosya adi `icon.png`).
pub async fn ikon(State(ctx): State<ApiCtx>) -> Response {
    sayfa(
        &ctx.app_dir.join("ui").join("icon.png"),
        "image/png",
        "public, max-age=31536000",
        &[],
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eksik_sayfa_sayfa_yok_doner() {
        let yol = std::env::temp_dir().join("afudm_h_olmayan_sayfa.html");
        let _ = std::fs::remove_file(&yol);
        let yanit = sayfa(&yol, "text/html; charset=utf-8", "no-store", &[]);
        assert_eq!(yanit.status(), StatusCode::NOT_FOUND);
    }

    #[test]
    fn mevcut_sayfa_basliklariyla_gelir() {
        let yol = std::env::temp_dir().join(format!("afudm_h_sw_{}.js", std::process::id()));
        std::fs::write(&yol, b"self.x=1;").unwrap();
        let yanit = sayfa(
            &yol,
            "text/javascript; charset=utf-8",
            "no-cache",
            &[("Service-Worker-Allowed", "/")],
        );
        assert_eq!(yanit.status(), StatusCode::OK);
        assert_eq!(yanit.headers()["service-worker-allowed"], "/");
        assert_eq!(yanit.headers()["cache-control"], "no-cache");
        let _ = std::fs::remove_file(&yol);
    }
}
