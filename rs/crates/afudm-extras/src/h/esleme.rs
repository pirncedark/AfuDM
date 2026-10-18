//! Uzanti/telefon eslestirme penceresi ve `GET /pair`.
//! Python: api/server.py `/pair` (satir 509), api/server.py LocalAPI.open_pairing / son_eslesme,
//! app.py start_pairing. Pencere kisa surelidir; anahtar yalniz pencere acikken ve yalniz
//! yerel istemciye verilir.

use rand::RngCore;
use serde::Deserialize;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use afudm_types::{AfuError, ApiCtx, Result};
use axum::extract::{ConnectInfo, Query, Request, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

/// Python `_Handler.pair_until` (unix saniye; 0 = kapali).
static ESLESME_BITIS: Mutex<f64> = Mutex::new(0.0);
/// Python `_Handler.son_eslesme`.
static SON_ESLESME: Mutex<f64> = Mutex::new(0.0);

// Kodlar diske yazilmaz; ayni veri dizinindeki kullanilmamis QR yenilenmez.
struct MobilKod {
    veri: PathBuf,
    kod: String,
    bitis: Instant,
}
static MOBIL_KODLAR: Mutex<Vec<MobilKod>> = Mutex::new(Vec::new());

/// QR icin 5 dakika gecerli, tek kullanimlik rastgele eslestirme kodu.
pub fn mobil_kod_uret(veri: &Path) -> String {
    let mut kodlar = MOBIL_KODLAR.lock().unwrap_or_else(|e| e.into_inner());
    let simdi = Instant::now();
    kodlar.retain(|k| k.bitis > simdi);
    if let Some(k) = kodlar.iter().find(|k| k.veri == veri) {
        return k.kod.clone();
    }
    let mut bayt = [0u8; 32];
    rand::rng().fill_bytes(&mut bayt);
    let kod: String = bayt.iter().map(|b| format!("{b:02x}")).collect();
    kodlar.push(MobilKod {
        veri: veri.into(),
        kod: kod.clone(),
        bitis: simdi + Duration::from_secs(300),
    });
    kod
}

fn mobil_kod_tuket(veri: &Path, kod: &str) -> bool {
    let mut kodlar = MOBIL_KODLAR.lock().unwrap_or_else(|e| e.into_inner());
    kodlar.retain(|k| k.bitis > Instant::now());
    let Some(i) = kodlar.iter().position(|k| k.veri == veri && k.kod == kod) else {
        return false;
    };
    kodlar.remove(i);
    true
}

#[derive(Deserialize)]
pub struct EslemeSorgu {
    code: Option<String>,
}

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

/// `GET /pair?code=...`: tek kullanimlik mobil kod; kodsuz istek eski yerel uzanti akisidir.
/// Istemci adresi (ConnectInfo) yoksa guvenli tarafta kalip yerel degil sayilir.
pub async fn pair(
    State(ctx): State<ApiCtx>,
    Query(sorgu): Query<EslemeSorgu>,
    istek: Request,
) -> Response {
    if let Some(kod) = sorgu.code {
        if !mobil_kod_tuket(&ctx.data_dir, &kod) {
            return super::hata(
                StatusCode::FORBIDDEN,
                "ESLESME_KODU_GECERSIZ",
                "Baglanti suresi doldu. Bilgisayardaki QR kodunu yeniden okut.",
            );
        }
        return esleme_yaniti(&ctx);
    }
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
    esleme_yaniti(&ctx)
}

fn esleme_yaniti(ctx: &ApiCtx) -> Response {
    match token_oku(&ctx.data_dir) {
        Ok(token) => {
            *kilit(&SON_ESLESME) = simdi();
            (
                [
                    ("cache-control", "no-store"),
                    ("referrer-policy", "no-referrer"),
                ],
                Json(json!({"ok": true, "token": token})),
            )
                .into_response()
        }
        Err(e) => super::afu_hata(&e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mobil_kod_tek_kullanimlik_ve_veri_dizinine_baglidir() {
        let veri = PathBuf::from("test-301a-tek-kullanim");
        let kod = mobil_kod_uret(&veri);
        assert_eq!(kod.len(), 64);
        assert_eq!(kod, mobil_kod_uret(&veri));
        assert!(!mobil_kod_tuket(Path::new("baska-veri"), &kod));
        assert!(!mobil_kod_tuket(&veri, "yanlis"));
        assert!(mobil_kod_tuket(&veri, &kod));
        assert!(!mobil_kod_tuket(&veri, &kod));
        assert_ne!(mobil_kod_uret(&veri), kod);
    }

    #[test]
    fn mobil_kod_suresi_dolunca_reddedilir() {
        let veri = PathBuf::from("test-301a-sure");
        let kod = mobil_kod_uret(&veri);
        {
            let mut kodlar = MOBIL_KODLAR.lock().unwrap();
            let kayit = kodlar.iter_mut().find(|k| k.veri == veri).unwrap();
            assert!(kayit.bitis <= Instant::now() + Duration::from_secs(300));
            kayit.bitis = Instant::now() - Duration::from_secs(1);
        }
        assert!(!mobil_kod_tuket(&veri, &kod));
        assert_ne!(mobil_kod_uret(&veri), kod);
    }

    #[test]
    fn mobil_kod_eszamanli_yalniz_bir_kisiye_verilir() {
        let veri = PathBuf::from("test-301a-yaris");
        let kod = mobil_kod_uret(&veri);
        let sonuc = std::thread::scope(|scope| {
            let a = scope.spawn(|| mobil_kod_tuket(&veri, &kod));
            let b = scope.spawn(|| mobil_kod_tuket(&veri, &kod));
            usize::from(a.join().unwrap()) + usize::from(b.join().unwrap())
        });
        assert_eq!(sonuc, 1);
    }

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
