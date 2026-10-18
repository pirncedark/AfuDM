//! SAHIBI: Ekip G2. Bu klasordeki her seyi o ekip yazar.
//!
//! Icerik: eklenti sistemi (eklenti.rs, eklenti_servis.rs), tarayici cerezleri (cerez.rs),
//! LinkGrabber cekirdegi (linkgrabber.rs), indirme kurallari (kurallar.rs).
//! HTTP rotalari bu dosyada: /rules, /eklentiler, /eklenti, /eklenti/gunluk, /eklenti/islem, /linkgrabber.

pub mod cerez;
pub mod eklenti;
pub mod eklenti_servis;
pub mod kurallar;
pub mod linkgrabber;
mod py;
mod url_parca;

use afudm_types::{AfuError, ApiCtx, Json, Store};
use axum::{
    body::Bytes,
    extract::{Query, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json as Cevap, Router,
};
use eklenti_servis::EklentiServisi;
use py::{py_str, truthy};
use serde_json::json;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Clone)]
struct Durum {
    store: Arc<dyn Store>,
    ui: Arc<dyn afudm_types::UiBridge>,
    servis: EklentiServisi,
}

/// Python `_hata`: {"ok": false, "code", "message", "error"} (`message` ve `error` birlikte).
fn hata(durum: u16, kod: &str, mesaj: &str) -> Response {
    (
        StatusCode::from_u16(durum).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
        Cevap(json!({"ok": false, "code": kod, "message": mesaj, "error": mesaj})),
    )
        .into_response()
}

/// Ortak Python uyumlu hata govdesi (afudm-api::hata_yaniti).
fn afu_hatasi(e: AfuError) -> Response {
    afudm_api::hata_yaniti(&e)
}

/// Python `_govde_oku`: bos govde {} sayilir; bozuk JSON ve JSON nesnesi olmayan govde
/// GOVDE_HATASI metniyle reddedilir.
fn govde(bytes: &Bytes) -> std::result::Result<Json, &'static str> {
    if bytes.is_empty() {
        return Ok(json!({}));
    }
    match serde_json::from_slice::<Json>(bytes) {
        Ok(v) if v.is_object() => Ok(v),
        Ok(_) => Err("Istek bicimi uygun degil. Yeniden dene."),
        Err(_) => Err("Istek okunamadi. Yeniden dene."),
    }
}

/// Python `_boolean_al`: true/false/1/0 metinleri ve bool/None kabul edilir; digeri hata.
fn boolean_al(data: &Json, anahtar: &str) -> std::result::Result<bool, String> {
    match data.get(anahtar) {
        None | Some(Json::Null) => Ok(false),
        Some(Json::Bool(b)) => Ok(*b),
        Some(Json::String(s)) => match s.trim().to_lowercase().as_str() {
            "true" | "1" => Ok(true),
            "false" | "0" | "" | "no" => Ok(false),
            _ => Err(format!("{anahtar} boolean olmali (true/false/1/0)")),
        },
        Some(_) => Err(format!("{anahtar} boolean olmali (true/false/1/0)")),
    }
}

/// Python `str(data.get(k) or "")`.
fn metin_al(data: &Json, anahtar: &str) -> String {
    match data.get(anahtar) {
        Some(v) if truthy(v) => py_str(v),
        _ => String::new(),
    }
}

/// G2 HTTP rotalari. Auth (`with_auth`) uygulama tarafinda, birlestirmeden sonra uygulanir.
pub fn router(ctx: ApiCtx) -> Router {
    let servis = servis_olustur(&ctx);
    router_with(ctx, servis)
}

/// Eklenti servisini dis taraf olusturur. Pywebview koprusu ile HTTP ayni ornegi
/// paylasmalidir (Python'da tek `manager.eklentiler` vardir).
pub fn servis_olustur(ctx: &ApiCtx) -> EklentiServisi {
    EklentiServisi::new(ctx.store.clone(), &ctx.app_dir, &ctx.data_dir)
}

/// `router` ile ayni rotalar; hazir bir `EklentiServisi` kullanir.
pub fn router_with(ctx: ApiCtx, servis: EklentiServisi) -> Router {
    let durum = Durum {
        store: ctx.store.clone(),
        ui: ctx.ui.clone(),
        servis,
    };
    Router::new()
        .route("/rules", get(kurallari_listele).post(kurallari_kaydet))
        .route("/eklentiler", get(eklenti_listesi))
        .route("/eklenti", post(eklenti_eylem))
        .route("/eklenti/gunluk", get(eklenti_gunluk))
        .route("/eklenti/islem", get(eklenti_islem))
        .route("/linkgrabber", post(linkgrabber_gonder))
        .with_state(durum)
}

async fn kurallari_listele(State(d): State<Durum>) -> Response {
    match d.store.rules_list() {
        Ok(rules) => Cevap(json!({"ok": true, "rules": rules})).into_response(),
        Err(e) => afu_hatasi(e),
    }
}

async fn kurallari_kaydet(State(d): State<Durum>, body: Bytes) -> Response {
    let data = match govde(&body) {
        Ok(v) => v,
        Err(m) => return hata(400, "GOVDE_HATASI", m),
    };
    let Some(gelen) = data.get("rules").and_then(Json::as_array) else {
        return hata(400, "BAD_REQUEST", "rules liste olmali");
    };
    let normal = match kurallar::kurallari_normalize(gelen, |sira| format!("api-rule-{sira}")) {
        Ok(n) => n,
        Err(e) => return afu_hatasi(e),
    };
    if let Err(e) = d.store.rules_save(&normal) {
        return afu_hatasi(e);
    }
    match d.store.rules_list() {
        Ok(rules) => Cevap(json!({"ok": true, "rules": rules})).into_response(),
        Err(e) => afu_hatasi(e),
    }
}

async fn eklenti_listesi(State(d): State<Durum>) -> Response {
    match d.servis.liste() {
        Ok(v) => Cevap(v).into_response(),
        Err(e) => afu_hatasi(e),
    }
}

async fn eklenti_gunluk(
    State(d): State<Durum>,
    Query(q): Query<HashMap<String, String>>,
) -> Response {
    let ad = q.get("ad").cloned().unwrap_or_default();
    match d.servis.gunluk(&ad) {
        Ok(v) => Cevap(v).into_response(),
        Err(e) => afu_hatasi(e),
    }
}

async fn eklenti_islem(State(d): State<Durum>) -> Response {
    Cevap(d.servis.islem()).into_response()
}

async fn eklenti_eylem(State(d): State<Durum>, body: Bytes) -> Response {
    let data = match govde(&body) {
        Ok(v) => v,
        Err(m) => return hata(400, "GOVDE_HATASI", m),
    };
    let eylem = metin_al(&data, "eylem");
    let ad = metin_al(&data, "ad");
    let yol = metin_al(&data, "yol");
    let s = &d.servis;
    let sonuc = match eylem.as_str() {
        "incele" => s.incele(&yol),
        "kur" => {
            let onay: Option<Vec<String>> = match data.get("onaylanan_izinler") {
                None | Some(Json::Null) => None,
                Some(Json::Array(a)) => Some(a.iter().map(py_str).collect()),
                Some(_) => Some(Vec::new()),
            };
            s.kur(&yol, onay.as_deref())
        }
        "guncelle" => s.guncelle(&ad, &yol),
        "geri_al" => s.elle_geri_al(&ad),
        "kaldir" => s.kaldir(&ad),
        "etkinlestir" => match boolean_al(&data, "acik") {
            Ok(acik) => s.etkinlestir(&ad, acik),
            Err(m) => return hata(400, "BAD_REQUEST", &m),
        },
        "yeniden_baslat" => s.yeniden_baslat(&ad),
        "ayar" => {
            let ayarlar = match data.get("ayarlar") {
                Some(v) if truthy(v) => v.clone(),
                _ => json!({}),
            };
            s.ayar_kaydet(&ad, &ayarlar)
        }
        "islem_iptal" => Ok(s.islem_iptal()),
        _ => return hata(400, "BILINMEYEN_EYLEM", "bilinmeyen eklenti eylemi"),
    };
    match sonuc {
        Ok(v) => Cevap(v).into_response(),
        Err(e) => afu_hatasi(e),
    }
}

/// Python `/linkgrabber`: metni arayuzdeki LinkGrabber paneline iletir (UiBridge::open_linkgrabber).
async fn linkgrabber_gonder(State(d): State<Durum>, body: Bytes) -> Response {
    let data = match govde(&body) {
        Ok(v) => v,
        Err(m) => return hata(400, "GOVDE_HATASI", m),
    };
    let metin = metin_al(&data, "metin");
    let metin = metin.trim();
    let uyari = match boolean_al(&data, "dosya") {
        Ok(v) => v,
        Err(m) => return hata(400, "BAD_REQUEST", &m),
    };
    if metin.is_empty() {
        return hata(400, "BAD_REQUEST", "metin gerekli");
    }
    if !d.ui.open_linkgrabber(metin, uyari) {
        return hata(503, "UI_YOK", "LinkGrabber paneli kullanilamiyor");
    }
    Cevap(serde_json::json!({"ok": true, "pending": true})).into_response()
}

#[cfg(test)]
mod govde_tests {
    use super::govde;
    use axum::body::Bytes;

    #[test]
    fn bos_govde_nesne_sayilir_ve_hatalar_python_metniyle_doner() {
        assert_eq!(govde(&Bytes::new()).unwrap(), serde_json::json!({}));
        assert_eq!(
            govde(&Bytes::from_static(b"{bozuk")).unwrap_err(),
            "Istek okunamadi. Yeniden dene."
        );
        assert_eq!(
            govde(&Bytes::from_static(b"[]")).unwrap_err(),
            "Istek bicimi uygun degil. Yeniden dene."
        );
        assert!(govde(&Bytes::from_static(b"{\"metin\":\"a\"}")).is_ok());
    }
}
