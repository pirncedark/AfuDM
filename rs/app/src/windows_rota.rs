//! HTTP /windows-integration (Python api/server.py + core/windows_integration.py).
//! GET: durum. POST {id, action=apply|remove|test}. Kayitlar HKCU altinda, kullanici duzeyi.
//! Sapma: Python kaldirmada onceki agaci yedekten geri yukler; burada yalniz AfuDM'in kendi
//! anahtarlari silinir (sahiplik isareti store'da tutulur, `winint_backup_<id>`).

use std::sync::Mutex;

use afudm_types::{ApiCtx, Json};
use axum::{
    body::Bytes,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
    Router,
};
use serde_json::json;
use winreg::enums::HKEY_CURRENT_USER;
use winreg::RegKey;

/// Python windows_integration.ROOT (cift ters egik cizgi Python'daki gibi korunur).
const ROOT: &str = r"Software\\Classes";
const TARAMA_VARSAYILAN: &str = "idle";

static TARAMA: Mutex<Option<Json>> = Mutex::new(None);

pub fn router(ctx: ApiCtx) -> Router {
    Router::new()
        .route("/windows-integration", get(durum_rota).post(islem_rota))
        .layer(axum::extract::DefaultBodyLimit::max(
            afudm_extras::g2::GOVDE_SINIRI,
        ))
        .with_state(ctx)
}

fn hata(kod: StatusCode, kod_metni: &str, mesaj: &str) -> Response {
    (
        kod,
        axum::Json(json!({"ok": false, "code": kod_metni, "error": mesaj, "message": mesaj})),
    )
        .into_response()
}

async fn durum_rota(State(ctx): State<ApiCtx>) -> Response {
    (StatusCode::OK, axum::Json(durum(&ctx))).into_response()
}

async fn islem_rota(
    State(ctx): State<ApiCtx>,
    govde: Result<Bytes, axum::extract::rejection::BytesRejection>,
) -> Response {
    let veri: Json = match afudm_extras::g2::govde_oku(govde) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let ident = veri
        .get("id")
        .and_then(Json::as_str)
        .unwrap_or("")
        .to_string();
    let action = veri
        .get("action")
        .and_then(Json::as_str)
        .unwrap_or("")
        .to_string();
    let sonuc = match action.as_str() {
        "apply" => uygula(&ctx, &ident).map(|_| durum(&ctx)),
        "remove" => kaldir(&ctx, &ident).map(|_| durum(&ctx)),
        "test" => test(&ctx, &ident),
        _ => {
            return hata(
                StatusCode::BAD_REQUEST,
                "BAD_REQUEST",
                "action apply, remove veya test olmali",
            )
        }
    };
    match sonuc {
        Ok(v) => (StatusCode::OK, axum::Json(v)).into_response(),
        Err(e) => hata(StatusCode::BAD_REQUEST, "BAD_REQUEST", &e),
    }
}

/// Python ITEMS. Bilinmeyen kimlik hata doner.
fn yol_of(ident: &str) -> Result<String, String> {
    let alt = match ident {
        "context" => r"*\\shell\\AfuDM.Download",
        "protocol" => "afudm",
        "afup" => ".afup",
        _ => return Err("bilinmeyen Windows entegrasyonu".into()),
    };
    Ok(format!(r"{ROOT}\{alt}"))
}

fn hkcu() -> RegKey {
    RegKey::predef(HKEY_CURRENT_USER)
}

fn komut() -> String {
    crate::entegrasyon::komut().unwrap_or_default()
}

fn kayitli(ident: &str) -> bool {
    let cmd = komut();
    let deger = match ident {
        "context" | "protocol" => hkcu()
            .open_subkey(format!(r"{}\command", yol_of(ident).unwrap_or_default()))
            .and_then(|k| k.get_value::<String, _>(""))
            .ok()
            .map(|v| v == cmd),
        "afup" => hkcu()
            .open_subkey(format!(r"{ROOT}\\.afup"))
            .and_then(|k| k.get_value::<String, _>(""))
            .ok()
            .map(|v| v == "AfuDM.afup"),
        _ => None,
    };
    deger.unwrap_or(false)
}

fn sahiplik_anahtari(ident: &str) -> String {
    format!("winint_backup_{ident}")
}

fn sahipmi(ctx: &ApiCtx, ident: &str) -> bool {
    matches!(ctx.store.get(&sahiplik_anahtari(ident)), Ok(Some(v)) if !v.is_null())
}

fn agac_sil(yol: &str) {
    let _ = hkcu().delete_subkey_all(yol);
}

fn yaz_deger(anahtar: &RegKey, ad: &str, deger: &str) -> std::io::Result<()> {
    anahtar.set_value(ad, &deger)
}

/// Python _write: once agaci sil, sonra kaydi yaz.
pub fn uygula(ctx: &ApiCtx, ident: &str) -> Result<(), String> {
    let yol = yol_of(ident)?;
    let io = |e: std::io::Error| e.to_string();
    ctx.store
        .set(&sahiplik_anahtari(ident), json!({}))
        .map_err(|e| e.to_string())?;
    agac_sil(&yol);
    let cmd = komut();
    match ident {
        "context" => {
            let (k, _) = hkcu().create_subkey(&yol).map_err(io)?;
            yaz_deger(&k, "", "AfuDM ile indir").map_err(io)?;
            let ico = ctx.app_dir.join("ui").join("afudm.ico");
            yaz_deger(&k, "Icon", &ico.display().to_string()).map_err(io)?;
            let (c, _) = k.create_subkey("command").map_err(io)?;
            yaz_deger(&c, "", &cmd).map_err(io)?;
        }
        "protocol" => {
            let (k, _) = hkcu().create_subkey(&yol).map_err(io)?;
            yaz_deger(&k, "", "URL:AfuDM Download").map_err(io)?;
            yaz_deger(&k, "URL Protocol", "").map_err(io)?;
            let (c, _) = k.create_subkey(r"shell\open\command").map_err(io)?;
            yaz_deger(&c, "", &cmd).map_err(io)?;
        }
        _ => {
            let (k, _) = hkcu().create_subkey(&yol).map_err(io)?;
            yaz_deger(&k, "", "AfuDM.afup").map_err(io)?;
            let (o, _) = k.create_subkey("OpenWithProgids").map_err(io)?;
            yaz_deger(&o, "AfuDM.afup", "").map_err(io)?;
            let progid = format!(r"{ROOT}\AfuDM.afup");
            agac_sil(&progid);
            let (p, _) = hkcu().create_subkey(&progid).map_err(io)?;
            yaz_deger(&p, "", "AfuDM paket dosyasi").map_err(io)?;
            let (c, _) = p.create_subkey(r"shell\open\command").map_err(io)?;
            yaz_deger(&c, "", &cmd).map_err(io)?;
        }
    }
    Ok(())
}

/// Python _remove: yalniz bu uygulamanin sahiplendigi kayitlar silinir.
pub fn kaldir(ctx: &ApiCtx, ident: &str) -> Result<(), String> {
    let yol = yol_of(ident)?;
    if !sahipmi(ctx, ident) {
        return Ok(());
    }
    agac_sil(&yol);
    if ident == "afup" {
        agac_sil(&format!(r"{ROOT}\AfuDM.afup"));
    }
    ctx.store
        .set(&sahiplik_anahtari(ident), Json::Null)
        .map_err(|e| e.to_string())?;
    Ok(())
}

/// Python test: kayitli mi + durum.
pub fn test(ctx: &ApiCtx, ident: &str) -> Result<Json, String> {
    yol_of(ident)?;
    let kayit = kayitli(ident);
    Ok(json!({"ok": kayit, "registered": kayit, "status": durum(ctx)}))
}

/// Python WindowsIntegration.status() ile ayni anahtarlar.
pub fn durum(_ctx: &ApiCtx) -> Json {
    let tarama = TARAMA
        .lock()
        .ok()
        .and_then(|g| g.clone())
        .unwrap_or_else(|| json!({"state": TARAMA_VARSAYILAN, "path": "", "detail": ""}));
    json!({
        "ok": true,
        "integrations": {
            "context": {"registered": kayitli("context"), "scope": "current_user"},
            "protocol": {"registered": kayitli("protocol"), "scope": "current_user"},
            "afup": {"registered": kayitli("afup"), "scope": "current_user"},
            "torrent": {"registered": false, "scope": "current_user"},
        },
        "scan": tarama,
        "service": {
            "supported": false,
            "state": "unavailable",
            "reason": "Windows service host is not packaged in this build.",
        },
    })
}
