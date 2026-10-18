//! Uzanti/telefon eslestirme penceresi ve `GET /pair`.
//! Python: api/server.py `/pair` (satir 509), api/server.py LocalAPI.open_pairing / son_eslesme,
//! app.py start_pairing. Pencere kisa surelidir; anahtar yalniz pencere acikken ve yalniz
//! yerel istemciye verilir.

use std::net::SocketAddr;
use std::path::Path;
use std::sync::{Mutex, MutexGuard};
use std::time::{SystemTime, UNIX_EPOCH};

use afudm_types::{AfuError, ApiCtx, Result};
use axum::extract::{ConnectInfo, Request, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

/// Python `_Handler.pair_until` (unix saniye; 0 = kapali).
static ESLESME_BITIS: Mutex<f64> = Mutex::new(0.0);
/// Python `_Handler.son_eslesme`.
static SON_ESLESME: Mutex<f64> = Mutex::new(0.0);

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn kilit(m: &Mutex<f64>) -> MutexGuard<'_, f64> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Python `open_pairing(seconds)`: pencereyi `saniye` kadar acar; bitis zamanini (unix sn) doner.
pub fn eslesme_ac(saniye: f64) -> f64 {
    let bitis = simdi() + saniye;
    *kilit(&ESLESME_BITIS) = bitis;
    bitis
}

/// Eslestirme penceresi su an acik mi.
pub fn eslesme_acik() -> bool {
    simdi() < *kilit(&ESLESME_BITIS)
}

/// Son anahtar verilis zamani (unix sn); 0 = hic.
pub fn son_eslesme() -> f64 {
    *kilit(&SON_ESLESME)
}

/// Python `_Handler.token` kaynagi: `data\api_token.txt`. Anahtar metni hata mesajina YAZILMAZ.
pub fn token_oku(veri: &Path) -> Result<String> {
    let ham = std::fs::read_to_string(veri.join("api_token.txt"))?;
    let token = ham.trim().to_string();
    if token.is_empty() {
        return Err(AfuError::Io("api_token.txt bos".into()));
    }
    Ok(token)
}

/// `GET /pair`: yalniz loopback ve acik pencerede `{"ok":true,"token":...}`.
/// Istemci adresi (ConnectInfo) yoksa guvenli tarafta kalip yerel degil sayilir.
pub async fn pair(State(ctx): State<ApiCtx>, istek: Request) -> Response {
    let yerel = istek
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|c| c.0.ip().is_loopback())
        .unwrap_or(false);
    if !yerel {
        return super::hata(
            StatusCode::FORBIDDEN,
            "ESLESME_YEREL_GEREKLI",
            "uzanti eslestirmesi yalniz bu bilgisayardan yapilabilir",
        );
    }
    if !eslesme_acik() {
        return super::hata(
            StatusCode::FORBIDDEN,
            "ESLESME_KAPALI",
            "eslestirme kapali — AfuDM'de Ayarlar > Uzantiyi bagla'ya bas",
        );
    }
    match token_oku(&ctx.data_dir) {
        Ok(token) => {
            *kilit(&SON_ESLESME) = simdi();
            Json(json!({"ok": true, "token": token})).into_response()
        }
        Err(e) => super::afu_hata(&e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pencere_ac_ve_kapat_suresi() {
        let bitis = eslesme_ac(120.0);
        assert!(eslesme_acik());
        assert!(bitis > simdi() + 100.0);
        eslesme_ac(-1.0);
        assert!(!eslesme_acik());
    }

    #[test]
    fn token_dosyasi_okunur_ve_bos_reddedilir() {
        let klasor = std::env::temp_dir().join(format!("afudm_h_esleme_{}", std::process::id()));
        std::fs::create_dir_all(&klasor).unwrap();
        std::fs::write(klasor.join("api_token.txt"), "abc_DEF-123\n").unwrap();
        assert_eq!(token_oku(&klasor).unwrap(), "abc_DEF-123");
        std::fs::write(klasor.join("api_token.txt"), "  \n").unwrap();
        assert!(token_oku(&klasor).is_err());
        let _ = std::fs::remove_dir_all(&klasor);
    }
}
