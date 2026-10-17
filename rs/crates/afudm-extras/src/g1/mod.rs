//! SAHIBI: Ekip G1. Bu klasordeki her seyi o ekip yazar.
//!
//! Alt modüller (Python karsiligi):
//! - guncelleme  — core/guncelleme.py + app.py guncelleme_*
//! - reliability — core/reliability.py + app.py reliability_*
//! - automation  — core/automation.py (indirme sonrasi adimlar)
//! - chrome      — core/chrome_kurulum.py (Chrome uzanti ekleme)
//!
//! HTTP: `router` Python api/server.py'deki /reliability/* GET rotalarini verir (ayni yol, ayni yanit).
//! Kimlik dogrulama app katmani tarafindan eklenir.

pub mod automation;
pub mod chrome;
pub mod guncelleme;
pub mod reliability;

use afudm_types::{AfuError, ApiCtx, Json};
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json as AxumJson, Router};
use serde_json::json;

pub fn router(ctx: ApiCtx) -> Router {
    Router::new()
        .route("/reliability/integrity", get(integrity_rota))
        .route("/reliability/backup", get(backup_rota))
        .route("/reliability/diagnostics-preview", get(tani_onizleme_rota))
        .route("/reliability/diagnostics-export", get(tani_disa_aktar_rota))
        .with_state(ctx)
}

async fn integrity_rota(State(ctx): State<ApiCtx>) -> Response {
    yanit(reliability::integrity(&*ctx.store))
}

async fn backup_rota(State(ctx): State<ApiCtx>) -> Response {
    yanit(reliability::backup(&*ctx.store, &ctx.data_dir, "manual"))
}

async fn tani_onizleme_rota(State(ctx): State<ApiCtx>) -> Response {
    yanit(reliability::diagnostics_preview(&*ctx.store))
}

async fn tani_disa_aktar_rota(State(ctx): State<ApiCtx>) -> Response {
    yanit(reliability::diagnostics_export(&*ctx.store, &ctx.data_dir))
}

fn yanit(sonuc: afudm_types::Result<Json>) -> Response {
    match sonuc {
        Ok(v) => (StatusCode::OK, AxumJson(v)).into_response(),
        Err(e) => hata_yaniti(e),
    }
}

/// afudm-api ile ayni hata biçimi: {"ok": false, "error": "..."}.
fn hata_yaniti(e: AfuError) -> Response {
    let durum = match &e {
        AfuError::Invalid(_) => StatusCode::BAD_REQUEST,
        AfuError::NotFound(_) => StatusCode::NOT_FOUND,
        AfuError::Engine(_) => StatusCode::BAD_GATEWAY,
        AfuError::Unavailable(_) => StatusCode::SERVICE_UNAVAILABLE,
        _ => StatusCode::INTERNAL_SERVER_ERROR,
    };
    (
        durum,
        AxumJson(json!({"ok": false, "error": e.to_string()})),
    )
        .into_response()
}

/// Testler icin yerel HTTP sahte sunucusu (gercek internet kullanilmaz).
#[cfg(test)]
pub(crate) mod test_sunucu {
    use std::io::{BufRead, BufReader, Write};
    use std::net::TcpListener;

    /// Verilen yollara govde dondurur; bilinmeyen yol 404 alir. Yanit: "http://127.0.0.1:<port>".
    pub fn baslat(rotalar: Vec<(&str, Vec<u8>)>) -> String {
        let rotalar = rotalar.into_iter().map(|(y, g)| (y, "", g)).collect();
        baslat_basliklarla(rotalar)
    }

    /// `ek` satirlari (ornegin "ETag: \"x\"\r\n") her yanita eklenir.
    pub fn baslat_basliklarla(rotalar: Vec<(&str, &str, Vec<u8>)>) -> String {
        let dinleyici = TcpListener::bind("127.0.0.1:0").expect("sahte sunucu bind");
        let adres = dinleyici.local_addr().expect("adres");
        let rotalar: Vec<(String, String, Vec<u8>)> = rotalar
            .into_iter()
            .map(|(y, e, g)| (y.to_string(), e.to_string(), g))
            .collect();
        std::thread::spawn(move || {
            for akis in dinleyici.incoming().take(64).flatten() {
                let mut akis = akis;
                let Ok(klon) = akis.try_clone() else {
                    continue;
                };
                let mut okuyucu = BufReader::new(klon);
                let mut ilk = String::new();
                if okuyucu.read_line(&mut ilk).is_err() {
                    continue;
                }
                loop {
                    let mut satir = String::new();
                    match okuyucu.read_line(&mut satir) {
                        Ok(0) | Err(_) => break,
                        Ok(_) if satir == "\r\n" || satir == "\n" => break,
                        Ok(_) => {}
                    }
                }
                let mut parca = ilk.split_whitespace();
                let yontem = parca.next().unwrap_or("GET").to_string();
                let yol = parca
                    .next()
                    .unwrap_or("/")
                    .split('?')
                    .next()
                    .unwrap_or("/")
                    .to_string();
                let (durum, ek, govde) = match rotalar.iter().find(|(y, _, _)| *y == yol) {
                    Some((_, ek, g)) => ("200 OK", ek.clone(), g.clone()),
                    None => ("404 Not Found", String::new(), b"yok".to_vec()),
                };
                let baslik = format!(
                    "HTTP/1.1 {durum}\r\nContent-Length: {}\r\n{ek}Connection: close\r\n\r\n",
                    govde.len()
                );
                let _ = akis.write_all(baslik.as_bytes());
                if yontem != "HEAD" {
                    let _ = akis.write_all(&govde);
                }
                let _ = akis.flush();
            }
        });
        format!("http://{adres}")
    }
}
