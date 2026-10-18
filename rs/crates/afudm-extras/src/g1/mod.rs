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
use axum::body::Bytes;
use axum::extract::rejection::BytesRejection;
use axum::extract::DefaultBodyLimit;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::{Json as AxumJson, Router};

/// Python api/server.py: /reliability/* yalniz POST (do_POST); GET 404 BILINMEYEN_YOL.
pub fn router(ctx: ApiCtx) -> Router {
    Router::new()
        .route(
            "/reliability/integrity",
            post(integrity_rota).get(afudm_api::bilinmeyen_yol),
        )
        .route(
            "/reliability/backup",
            post(backup_rota).get(afudm_api::bilinmeyen_yol),
        )
        .route(
            "/reliability/diagnostics-preview",
            post(tani_onizleme_rota).get(afudm_api::bilinmeyen_yol),
        )
        .route(
            "/reliability/diagnostics-export",
            post(tani_disa_aktar_rota).get(afudm_api::bilinmeyen_yol),
        )
        .layer(DefaultBodyLimit::max(crate::g2::GOVDE_SINIRI))
        .with_state(ctx)
}

async fn integrity_rota(
    State(ctx): State<ApiCtx>,
    govde: std::result::Result<Bytes, BytesRejection>,
) -> Response {
    if let Err(r) = crate::g2::govde_oku(govde) {
        return r;
    }
    yanit(reliability::integrity(&*ctx.store))
}

async fn backup_rota(
    State(ctx): State<ApiCtx>,
    govde: std::result::Result<Bytes, BytesRejection>,
) -> Response {
    if let Err(r) = crate::g2::govde_oku(govde) {
        return r;
    }
    yanit(reliability::backup(&*ctx.store, &ctx.data_dir, "manual"))
}

async fn tani_onizleme_rota(
    State(ctx): State<ApiCtx>,
    govde: std::result::Result<Bytes, BytesRejection>,
) -> Response {
    if let Err(r) = crate::g2::govde_oku(govde) {
        return r;
    }
    yanit(reliability::diagnostics_preview(&*ctx.store, &ctx.app_dir))
}

async fn tani_disa_aktar_rota(
    State(ctx): State<ApiCtx>,
    govde: std::result::Result<Bytes, BytesRejection>,
) -> Response {
    if let Err(r) = crate::g2::govde_oku(govde) {
        return r;
    }
    yanit(reliability::diagnostics_export(
        &*ctx.store,
        &ctx.data_dir,
        &ctx.app_dir,
    ))
}

/// Python do_POST once `_govde_oku` yapar: bozuk govde islemi calistirmadan 400/413 GOVDE_HATASI.
fn yanit(sonuc: afudm_types::Result<Json>) -> Response {
    match sonuc {
        Ok(v) => (StatusCode::OK, AxumJson(v)).into_response(),
        Err(e) => hata_yaniti(e),
    }
}

/// afudm-api ile ayni Python uyumlu hata govdesi ({ok,code,message,error}).
fn hata_yaniti(e: AfuError) -> Response {
    afudm_api::hata_yaniti(&e)
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
