//! SAHIBI: Ekip F4b. Python app.py Api metotlarinin bu ekibe dusen kismi.
//! `dispatch` ad bu dosyaya aitse Some(yanit), degilse None doner.
//!
//! Kapsam: sunucu_* (yonetim paneli: yonetim.rs), start_pairing, telefon_* (LAN: yonetim.rs),
//! share_* / agda_paylas / dosya_sec_ve_paylas / paylasim_stop (tunel: yonetim.rs), yerelden_sor /
//! tarayicidan_sor (bekleyen kuyruk), motor_indir, butunluk_*, guc_durumu, simdi_uyu,
//! reliability_recovery_preview, ayarlari_dogrula_kaydet, ag_konumlari_listele, ana_pencere_kapandi,
//! security_rotate_token, tracker_klasoru_ac, seed_tracker_kaydet, windows.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use afudm_api::erisim::{ErisimDeposu, HizSinirlayici};
use afudm_core::butunluk;
use afudm_engine::engines;
use afudm_extras::g1::{automation, reliability};
use afudm_extras::h::{esleme, paylasim, smb};
use afudm_types::{AfuError, ApiCtx, JsonMap, Result};
use serde_json::{json, Value as Json};
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

use crate::bridge::{self, cevap, hata, kilit, Kabuk};
use crate::window::{self, ANA};
use crate::yonetim;

/// Python `shared_files` (kopru tarafi): token -> (yol, olusturulma zamani, unix sn).
static PAYLASIMLAR: Mutex<BTreeMap<String, (PathBuf, f64)>> = Mutex::new(BTreeMap::new());
/// Python `shared_files` icindeki SMB alanlari (share_name, staging_path). Yalniz Windows'ta dolar.
static SMB_PAYLASIMLAR: Mutex<BTreeMap<String, smb::SmbPaylasim>> = Mutex::new(BTreeMap::new());
/// Python `_motor_ilerleme`: motor adi -> durum.
static MOTOR_ILERLEME: Mutex<BTreeMap<String, Json>> = Mutex::new(BTreeMap::new());
/// Python `_sunucu_hata`: son yonetim sunucusu acilis hatasi.
static SUNUCU_HATA: Mutex<String> = Mutex::new(String::new());

const PAYLASILAMAZ: &str =
    "Sadece tamamlanmış tekil dosyalar paylaşılabilir veya dosya diskte bulunamadı.";
const SMB_UYARI_YONETICI: &str =
    "SMB paylaşımı için yönetici izni bulunamadı; HTTP LAN bağlantısı hazırlandı.";

/// Tek giris: kopru_h'nin sahip oldugu ad ise yanit, degilse None.
pub fn dispatch(k: &Kabuk, name: &str, a: &[Json]) -> Option<Json> {
    let yanit = match name {
        // --- yonetim paneli ---
        "sunucu_durumu" => ctx_ile(k, |c| cevap(sunucu_durumu(c))),
        "sunucu_ayarla" => ctx_ile(k, |c| cevap(sunucu_ayarla(c, b_arg(a, 0)))),
        "sunucu_yeniden" => ctx_ile(k, |c| cevap(sunucu_yeniden(c))),
        "sunucu_panel_ac" => ctx_ile(k, |_| sunucu_panel_ac()),
        "sunucu_anahtarlar" => ctx_ile(k, |c| cevap(sunucu_anahtarlar(c))),
        "sunucu_anahtar_olustur" => ctx_ile(k, |c| {
            cevap(sunucu_anahtar_olustur(c, s(a, 0), s(a, 1), s(a, 2)))
        }),
        "sunucu_anahtar_rotasyon" => ctx_ile(k, |c| {
            cevap(anahtar_cagri(c, "anahtar_rotasyon", n(a, 0), None))
        }),
        "sunucu_anahtar_iptal" => ctx_ile(k, |c| {
            cevap(anahtar_cagri(c, "anahtar_iptal", n(a, 0), None))
        }),
        "sunucu_anahtar_sil" => ctx_ile(k, |c| cevap(anahtar_sil(c, n(a, 0)))),
        "sunucu_anahtar_rol" => ctx_ile(k, |c| {
            cevap(anahtar_cagri(
                c,
                "anahtar_rol_ayarla",
                n(a, 0),
                Some(s(a, 1)),
            ))
        }),
        "sunucu_istemciler" => ctx_ile(k, |c| cevap(sunucu_istemciler(c, n(a, 0)))),
        "sunucu_istemci_iptal" => ctx_ile(k, |c| cevap(sunucu_istemci_iptal(c, n(a, 0)))),
        "sunucu_istemci_temizle" => ctx_ile(k, |c| {
            cevap(sunucu_istemci_temizle(
                c,
                a.first().and_then(Json::as_i64).unwrap_or(7),
            ))
        }),
        "sunucu_kilit_temizle" => ctx_ile(k, |c| cevap(sunucu_kilit_temizle(c))),
        "sunucu_profiller" => ctx_ile(k, |c| cevap(sunucu_profiller(c))),
        "sunucu_profil_kaydet" => ctx_ile(k, |c| {
            cevap(sunucu_profil_kaydet(
                c,
                &a.first()
                    .and_then(Json::as_object)
                    .cloned()
                    .unwrap_or_default(),
            ))
        }),
        "sunucu_profil_sil" => ctx_ile(k, |c| cevap(sunucu_profil_sil(c, n(a, 0)))),
        "sunucu_profil_etkinlestir" => ctx_ile(k, |c| cevap(sunucu_profil_etkinlestir(c, n(a, 0)))),

        // --- eslestirme ve telefon ---
        "start_pairing" => {
            let saniye = a.first().and_then(Json::as_f64).unwrap_or(120.0);
            esleme::eslesme_ac(saniye);
            json!({"ok": true, "seconds": saniye as i64, "port": port(k)})
        }
        "telefon_durumu" => ctx_ile(k, |c| cevap(Ok(telefon_durumu(k, c)))),
        "telefon_ayarla" => ctx_ile(k, |c| cevap(telefon_ayarla(k, c, b_arg(a, 0)))),

        // --- paylasim ---
        "share_create" => ctx_ile(k, |c| cevap(share_create(k, c, s(a, 0)))),
        "agda_paylas" => ctx_ile(k, |c| cevap(agda_paylas(k, c, s(a, 0)))),
        "share_list" => cevap(Ok(share_list(k))),
        "share_delete" => share_delete(s(a, 0)),
        "dosya_sec_ve_paylas" => ctx_ile(k, |c| cevap(dosya_sec_ve_paylas(k, c))),
        "paylasim_stop" => ctx_ile(k, |c| {
            paylasim_durdur(c);
            Json::Null
        }),

        // --- bekleyen indirme istekleri ---
        "yerelden_sor" => yerelden_sor(
            k,
            a.first()
                .and_then(Json::as_object)
                .cloned()
                .unwrap_or_default(),
        ),
        "tarayicidan_sor" => tarayicidan_sor(
            k,
            a.first()
                .and_then(Json::as_object)
                .cloned()
                .unwrap_or_default(),
        ),

        // --- diger Api metotlari ---
        "windows" => Json::Null,
        "ayarlari_dogrula_kaydet" => ctx_ile(k, |c| {
            cevap(ayarlari_dogrula_kaydet(
                c,
                &a.first()
                    .and_then(Json::as_object)
                    .cloned()
                    .unwrap_or_default(),
            ))
        }),
        "ag_konumlari_listele" => ctx_ile(k, |c| cevap(ag_konumlari_listele(c))),
        "ana_pencere_kapandi" => {
            window::indirme_kapat(&k.app);
            Json::Null
        }
        "motor_indir" => motor_indir(k, s(a, 0)),
        "butunluk_tara" => butunluk_cagri(k, |m| butunluk::butunluk_tara(m, s(a, 0))),
        "butunluk_onar" => butunluk_cagri(k, |m| butunluk::butunluk_onar(m, s(a, 0), s(a, 1))),
        "butunluk_hepsini_tara" => butunluk_cagri(k, butunluk::butunluk_hepsini_tara),
        "guc_durumu" => guc_durumu(),
        "simdi_uyu" => json!({"ok": automation::uyut()}),
        "reliability_recovery_preview" => ctx_ile(k, |c| {
            cevap(
                c.manager
                    .current_download_dir()
                    .and_then(|ana| reliability::recovery_preview(&*c.store, &ana, n(a, 0))),
            )
        }),
        "security_rotate_token" => security_rotate_token(k),
        "tracker_klasoru_ac" => tracker_klasoru_ac(k),
        "seed_tracker_kaydet" => ctx_ile(k, |c| cevap(seed_tracker_kaydet(c, s(a, 0)))),
        _ => return None,
    };
    Some(yanit)
}

// --- yardimcilar -------------------------------------------------------------

fn s(a: &[Json], i: usize) -> &str {
    bridge::s(a, i)
}

fn b_arg(a: &[Json], i: usize) -> bool {
    bridge::b(a, i)
}

fn n(a: &[Json], i: usize) -> i64 {
    bridge::n(a, i)
}

fn ctx_ile(k: &Kabuk, f: impl FnOnce(&ApiCtx) -> Json) -> Json {
    match k.ctx.get() {
        Some(c) => f(c),
        None => bridge::motor_hazir_degil(),
    }
}

fn port(k: &Kabuk) -> u16 {
    k.port.get().copied().unwrap_or(0)
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn harita(v: Json) -> JsonMap {
    v.as_object().cloned().unwrap_or_default()
}

fn depo(c: &ApiCtx) -> ErisimDeposu {
    ErisimDeposu::new(c.store.clone())
}

/// Python `{"ok": True, **sonuc}`.
fn ok_birlestir(sonuc: Json) -> Json {
    let mut cikti = json!({"ok": true});
    if let (Some(hedef), Json::Object(kaynak)) = (cikti.as_object_mut(), sonuc) {
        hedef.extend(kaynak);
    }
    cikti
}

/// Python: ValueError -> BAD_REQUEST; diger hatalar genel hata metni.
fn bad(e: AfuError) -> Json {
    match e {
        AfuError::Invalid(m) => json!({"ok": false, "code": "BAD_REQUEST", "error": m}),
        diger => hata(diger.to_string()),
    }
}

fn ok_veya_kotu(sonuc: Result<Json>) -> Result<Json> {
    Ok(match sonuc {
        Ok(v) => ok_birlestir(v),
        Err(e) => bad(e),
    })
}

pub(crate) fn ayar_str(c: &ApiCtx, anahtar: &str) -> String {
    c.store
        .get(anahtar)
        .ok()
        .flatten()
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_default()
}

pub(crate) fn ayar_int(c: &ApiCtx, anahtar: &str) -> i64 {
    c.store
        .get(anahtar)
        .ok()
        .flatten()
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
}

pub(crate) fn ayar_bool(c: &ApiCtx, anahtar: &str) -> bool {
    c.store
        .get(anahtar)
        .ok()
        .flatten()
        .is_some_and(|v| bridge::truthy(&v))
}

fn kisalt(metin: &str, adet: usize) -> String {
    metin.chars().take(adet).collect()
}

fn ad_of(yol: &Path) -> String {
    yol.file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default()
}

// --- yonetim paneli (sunucu_*) ---------------------------------------------

/// Python `sunucu_ayarlari`: etkin profil varsa onun degerleri, yoksa genel ayarlar.
pub(crate) fn sunucu_ayarlari(c: &ApiCtx) -> Result<Json> {
    let profil_id = ayar_int(c, "sunucu_profil_id");
    if profil_id != 0 {
        let profil = depo(c).call("profil", &harita(json!({"profil_id": profil_id})))?;
        if profil.is_object() {
            return Ok(json!({
                "adres": profil["adres"],
                "port": profil["port"],
                "originler": profil["originler"],
                "istek_limiti": profil["istek_limiti"],
                "profil_id": profil["id"],
                "profil_ad": profil["ad"],
            }));
        }
    }
    let adres = ayar_str(c, "sunucu_adres");
    let port = ayar_int(c, "sunucu_port");
    let limit = ayar_int(c, "sunucu_istek_limiti");
    Ok(json!({
        "adres": if adres.is_empty() { "yerel".to_string() } else { adres },
        "port": if port == 0 { 6821 } else { port },
        "originler": ayar_str(c, "sunucu_izinli_originler"),
        "istek_limiti": if limit == 0 { 120 } else { limit },
        "profil_id": 0,
        "profil_ad": "",
    }))
}

/// Python `limitci`: istek siniri ayarlardan kurulur.
pub(crate) fn limitci(c: &ApiCtx) -> Result<HizSinirlayici> {
    let ayar = sunucu_ayarlari(c)?;
    let limit = ayar["istek_limiti"].as_u64().unwrap_or(120).max(1) as usize;
    let hatali = match ayar_int(c, "sunucu_hatali_limit") {
        0 => 8,
        v => v as u32,
    };
    let kilit_saniye = match ayar_int(c, "sunucu_kilit_saniye") {
        0 => 300,
        v => v as u32,
    };
    Ok(HizSinirlayici::new(limit, hatali, kilit_saniye))
}

/// Python `sunucu_durumu`: calisan panel bilgisi (yoksa ayarlar), limit durumu.
pub(crate) fn sunucu_durumu(c: &ApiCtx) -> Result<Json> {
    let ayar = sunucu_ayarlari(c)?;
    let bilgi = yonetim::sunucu_bilgi();
    let (calisiyor, port, url, lan_url, istek, red, baslangic) = match &bilgi {
        Some(b) => {
            let lan_url = if b.lan && !b.lan_ip.is_empty() {
                format!("http://{}:{}/panel", b.lan_ip, b.port)
            } else {
                String::new()
            };
            (
                true,
                b.port as i64,
                format!("http://127.0.0.1:{}/panel", b.port),
                lan_url,
                b.istek,
                b.red,
                b.baslangic,
            )
        }
        None => (
            false,
            ayar["port"].as_i64().unwrap_or(6821),
            String::new(),
            String::new(),
            0,
            0,
            0.0,
        ),
    };
    Ok(json!({
        "ok": true,
        "sunucu": {
            "calisiyor": calisiyor,
            "istenen": ayar_bool(c, "sunucu_acik"),
            "adres": ayar["adres"],
            "port": port,
            "url": url,
            "lan_url": lan_url,
            "profil_id": ayar["profil_id"],
            "profil_ad": ayar["profil_ad"],
            "hata": kilit(&SUNUCU_HATA).clone(),
            "istek_sayisi": istek,
            "reddedilen": red,
            "baslangic": baslangic,
        },
        "limit": limitci(c)?.call("durum", "")?,
    }))
}

pub(crate) fn sunucu_ayarla(c: &ApiCtx, acik: bool) -> Result<Json> {
    if acik {
        let yonetici_var = depo(c)
            .call("yonetici_var_mi", &JsonMap::new())?
            .as_bool()
            .unwrap_or(false);
        if !yonetici_var {
            return Ok(json!({
                "ok": false,
                "code": "ANAHTAR_YOK",
                "error": "once bir yonetici erisim anahtari olustur",
            }));
        }
        return sunucu_baslat(c);
    }
    sunucu_durdur(c)
}

/// Python `sunucu_baslat`: paneli acar; acilamazsa SUNUCU_ACILAMADI ve hata kaydi.
fn sunucu_baslat(c: &ApiCtx) -> Result<Json> {
    match yonetim::sunucu_ac(c) {
        Ok(_) => {
            *kilit(&SUNUCU_HATA) = String::new();
            c.store.set("sunucu_acik", json!(true))?;
            let durum = sunucu_durumu(c)?;
            Ok(ok_birlestir(durum["sunucu"].clone()))
        }
        Err(mesaj) => {
            *kilit(&SUNUCU_HATA) = mesaj.clone();
            c.store
                .log("error", &format!("yonetim sunucusu acilamadi: {mesaj}"), "");
            Ok(json!({"ok": false, "code": "SUNUCU_ACILAMADI", "message": mesaj, "error": mesaj}))
        }
    }
}

pub(crate) fn sunucu_durdur(c: &ApiCtx) -> Result<Json> {
    yonetim::sunucu_kapat();
    c.store.set("sunucu_acik", json!(false))?;
    c.store.log("info", "yonetim sunucusu kapatildi", "");
    Ok(json!({"ok": true, "calisiyor": false}))
}

fn sunucu_yeniden(c: &ApiCtx) -> Result<Json> {
    sunucu_durdur(c)?;
    sunucu_baslat(c)
}

/// Python `sunucu_panel_ac`: calisiyorsa paneli varsayilan tarayicida acar (anahtar URL'ye konmaz).
fn sunucu_panel_ac() -> Json {
    match yonetim::sunucu_bilgi() {
        None => json!({"ok": false, "code": "SUNUCU_KAPALI", "error": "sunucu kapali"}),
        Some(b) => {
            let url = format!("http://127.0.0.1:{}/panel", b.port);
            match bridge::hidden_cmd("explorer.exe").arg(&url).spawn() {
                Ok(_) => json!({"ok": true, "url": url}),
                Err(e) => {
                    json!({"ok": false, "code": "ACILAMADI", "error": kisalt(&e.to_string(), 200)})
                }
            }
        }
    }
}

pub(crate) fn sunucu_anahtarlar(c: &ApiCtx) -> Result<Json> {
    let anahtarlar = depo(c).call("anahtarlar", &JsonMap::new())?;
    Ok(json!({"ok": true, "roller": ["yonetici", "salt_okur"], "anahtarlar": anahtarlar}))
}

pub(crate) fn sunucu_anahtar_olustur(
    c: &ApiCtx,
    ad: &str,
    rol: &str,
    not_metni: &str,
) -> Result<Json> {
    ok_veya_kotu(depo(c).call(
        "anahtar_olustur",
        &harita(json!({"ad": ad, "rol": rol, "not_metni": not_metni})),
    ))
}

/// Python anahtar_rotasyon / anahtar_iptal / anahtar_rol_ayarla (ValueError -> BAD_REQUEST).
pub(crate) fn anahtar_cagri(
    c: &ApiCtx,
    eylem: &str,
    key_id: i64,
    rol: Option<&str>,
) -> Result<Json> {
    let mut veri = json!({"key_id": key_id});
    if let Some(rol) = rol {
        veri["rol"] = json!(rol);
    }
    ok_veya_kotu(depo(c).call(eylem, &harita(veri)))
}

/// Python `anahtar_sil`: ValueError yakalanmaz (genel hata).
pub(crate) fn anahtar_sil(c: &ApiCtx, key_id: i64) -> Result<Json> {
    Ok(ok_birlestir(
        depo(c).call("anahtar_sil", &harita(json!({"key_id": key_id})))?,
    ))
}

pub(crate) fn sunucu_istemciler(c: &ApiCtx, dakika: i64) -> Result<Json> {
    let istemciler = depo(c).call("istemciler", &harita(json!({"dakika": dakika})))?;
    Ok(json!({"ok": true, "istemciler": istemciler}))
}

pub(crate) fn sunucu_istemci_iptal(c: &ApiCtx, client_id: i64) -> Result<Json> {
    let sonuc = depo(c).call("oturum_iptal", &harita(json!({"client_id": client_id})))?;
    c.store.log(
        "info",
        &format!("istemci oturumu iptal edildi (#{client_id})"),
        "",
    );
    Ok(ok_birlestir(sonuc))
}

pub(crate) fn sunucu_istemci_temizle(c: &ApiCtx, gun: i64) -> Result<Json> {
    let silinen = depo(c).call("oturumlari_temizle", &harita(json!({"gun": gun})))?;
    Ok(json!({"ok": true, "silinen": silinen}))
}

/// Kaba kuvvet kilidi: sunucu calismiyorsa sayac bos kalir; yine de Python'daki yanit sekli doner.
pub(crate) fn sunucu_kilit_temizle(c: &ApiCtx) -> Result<Json> {
    let temizlenen = limitci(c)?.call("kilitleri_temizle", "")?;
    Ok(json!({"ok": true, "temizlenen": temizlenen}))
}

pub(crate) fn sunucu_profiller(c: &ApiCtx) -> Result<Json> {
    let profiller = depo(c).call("profiller", &JsonMap::new())?;
    Ok(json!({"ok": true, "profiller": profiller, "etkin": ayar_int(c, "sunucu_profil_id")}))
}

/// Python `profil_kaydet`: eksik/bos alanlar Python'daki `or` varsayilanlariyla doldurulur.
pub(crate) fn sunucu_profil_kaydet(c: &ApiCtx, veri: &JsonMap) -> Result<Json> {
    let al = |anahtar: &str, varsayilan: Json| {
        veri.get(anahtar)
            .filter(|v| bridge::truthy(v))
            .cloned()
            .unwrap_or(varsayilan)
    };
    let girdi = json!({
        "ad": al("ad", json!("")),
        "adres": al("adres", json!("yerel")),
        "port": al("port", json!(0)),
        "originler": al("originler", json!("")),
        "istek_limiti": al("istek_limiti", json!(120)),
        "profil_id": al("id", json!(0)),
    });
    let sonuc = match depo(c).call("profil_kaydet", &harita(girdi)) {
        Ok(v) => v,
        Err(e) => return Ok(bad(e)),
    };
    let yeniden_gerekli = Some(ayar_int(c, "sunucu_profil_id")) == sonuc["id"].as_i64();
    let mut cikti = ok_birlestir(sonuc);
    cikti["sunucu_yeniden_gerekli"] = json!(yeniden_gerekli);
    Ok(cikti)
}

pub(crate) fn sunucu_profil_sil(c: &ApiCtx, profil_id: i64) -> Result<Json> {
    Ok(ok_birlestir(depo(c).call(
        "profil_sil",
        &harita(json!({"profil_id": profil_id})),
    )?))
}

pub(crate) fn sunucu_profil_etkinlestir(c: &ApiCtx, profil_id: i64) -> Result<Json> {
    if profil_id != 0
        && depo(c)
            .call("profil", &harita(json!({"profil_id": profil_id})))?
            .is_null()
    {
        return Ok(json!({"ok": false, "code": "BAD_REQUEST", "error": "profil bulunamadi"}));
    }
    c.store.set("sunucu_profil_id", json!(profil_id))?;
    Ok(json!({"ok": true, "etkin": profil_id, "sunucu_yeniden_gerekli": true}))
}

// --- eslestirme ve telefon -------------------------------------------------

/// Python `telefon_durumu`: acik ise LAN adresi (token'li /m baglantisi) ve QR.
fn telefon_durumu(k: &Kabuk, c: &ApiCtx) -> Json {
    let acik = ayar_bool(c, "lan_erisimi");
    let adres = if acik {
        yonetim::lan_adres(c).unwrap_or_default()
    } else {
        String::new()
    };
    let qr = if adres.is_empty() {
        String::new()
    } else {
        yonetim::qr_uri(&adres)
    };
    json!({"ok": true, "acik": acik, "adres": adres, "qr": qr, "port": port(k)})
}

/// Python `telefon_ayarla`: LAN dinleyicisini ac/kapat; acilamazsa lan_bind_failed (ayar yazilmaz).
fn telefon_ayarla(k: &Kabuk, c: &ApiCtx, acik: bool) -> Result<Json> {
    if acik {
        if yonetim::lan_ac(port(k)).is_err() {
            return Ok(
                json!({"ok": false, "error": "lan_bind_failed", "acik": ayar_bool(c, "lan_erisimi")}),
            );
        }
    } else {
        yonetim::lan_kapat();
    }
    c.store.set("lan_erisimi", json!(acik))?;
    c.store.set("api_port", json!(port(k)))?;
    Ok(telefon_durumu(k, c))
}

// --- paylasim ----------------------------------------------------------------

fn dosya_yolu(c: &ApiCtx, gid: &str) -> Result<Option<PathBuf>> {
    Ok(c.manager
        .resolve_item_path(gid)?
        .filter(|yol| yol.is_file()))
}

/// Python `_paylasim_url`: LAN hostu (yoksa 127.0.0.1) ile yerel indirme adresi.
fn paylasim_url(k: &Kabuk, token: &str) -> String {
    let ip = yonetim::lan_ip();
    let host = if ip.is_empty() {
        "127.0.0.1".to_string()
    } else {
        ip
    };
    format!("http://{host}:{}/s/{token}", port(k))
}

/// Python `_internet_linki`: ayar aciksa tuneli acar; hata anahtari Python ile ayni.
fn internet_linki(c: &ApiCtx, token: &str) -> (String, String) {
    if c.store.get("internet_paylasim").ok().flatten() == Some(json!(false)) {
        return (String::new(), String::new());
    }
    match yonetim::internet_baslat(c) {
        Ok(taban) => (format!("{taban}/s/{token}"), String::new()),
        Err(anahtar) => (String::new(), anahtar.to_string()),
    }
}

/// Python `_paylasim_sonucu`. Internet linki varsa o, yoksa yerel adres kullanilir.
fn paylasim_sonucu(k: &Kabuk, c: &ApiCtx, token: &str, yol: &Path, uyari: &str) -> Json {
    let yerel = paylasim_url(k, token);
    let (internet, internet_hata) = internet_linki(c, token);
    let kullanilacak = if internet.is_empty() {
        yerel.clone()
    } else {
        internet.clone()
    };
    let qr = yonetim::qr_uri(&kullanilacak);
    json!({
        "ok": true,
        "transport": "http",
        "token": token,
        "url": kullanilacak,
        "local_url": yerel,
        "internet_url": internet,
        "qr": qr,
        "filename": ad_of(yol),
        "smb": "",
        "warning": uyari,
        "internet_error_key": internet_hata,
    })
}

fn paylasim_kaydet(yol: &Path) -> String {
    let token = paylasim::paylasim_ekle(yol.to_path_buf());
    kilit(&PAYLASIMLAR).insert(token.clone(), (yol.to_path_buf(), simdi()));
    token
}

fn share_create(k: &Kabuk, c: &ApiCtx, gid: &str) -> Result<Json> {
    let Some(yol) = dosya_yolu(c, gid)? else {
        return Ok(json!({"ok": false, "error": PAYLASILAMAZ}));
    };
    let token = paylasim_kaydet(&yol);
    Ok(paylasim_sonucu(k, c, &token, &yol, ""))
}

/// Python `agda_paylas`: Windows'ta SMB paylasimi denenir; olmazsa HTTP baglantisi doner.
fn agda_paylas(k: &Kabuk, c: &ApiCtx, gid: &str) -> Result<Json> {
    let Some(yol) = dosya_yolu(c, gid)? else {
        return Ok(json!({"ok": false, "error": PAYLASILAMAZ}));
    };
    let token = paylasim_kaydet(&yol);
    let mut uyari = SMB_UYARI_YONETICI.to_string();
    let mut transport = "http";
    let mut unc = String::new();
    if cfg!(windows) {
        match smb::paylas_olustur(&token, &yol) {
            Ok(paylasim) => {
                unc = paylasim.unc.clone();
                kilit(&SMB_PAYLASIMLAR).insert(token.clone(), paylasim);
                transport = "smb";
                uyari = String::new();
            }
            Err(e) => {
                uyari = format!(
                    "SMB paylaşımı açılamadı ({}); HTTP LAN bağlantısı ve QR hazırlandı.",
                    kisalt(&e.to_string(), 120)
                );
            }
        }
    }
    let mut sonuc = paylasim_sonucu(k, c, &token, &yol, &uyari);
    sonuc["transport"] = json!(transport);
    sonuc["smb"] = json!(unc);
    sonuc["warning"] = json!(uyari);
    Ok(sonuc)
}

/// Python `share_list`: bu kopru uzerinden olusturulan paylasimlar, yeniler en ustte.
/// Telefon (HTTP /share_create) ile acilan tokenlar bu listede yer almaz (bkz. SONUC_F4b).
fn share_list(k: &Kabuk) -> Json {
    let kayitlar = kilit(&PAYLASIMLAR).clone();
    let tunel = yonetim::tunel_url();
    let mut satirlar: Vec<(f64, Json)> = kayitlar
        .iter()
        .map(|(token, (yol, olusturuldu))| {
            let yerel = paylasim_url(k, token);
            let internet = tunel
                .as_ref()
                .map(|taban| format!("{taban}/s/{token}"))
                .unwrap_or_default();
            let url = if internet.is_empty() {
                yerel.clone()
            } else {
                internet.clone()
            };
            let boyut = std::fs::metadata(yol).map(|m| m.len()).unwrap_or(0);
            (
                *olusturuldu,
                json!({
                    "token": token,
                    "url": url,
                    "local_url": yerel,
                    "internet_url": internet,
                    "filename": ad_of(yol),
                    "size": boyut,
                    "created": olusturuldu,
                }),
            )
        })
        .collect();
    satirlar.sort_by(|x, y| y.0.total_cmp(&x.0));
    json!({"ok": true, "shares": satirlar.into_iter().map(|(_, j)| j).collect::<Vec<_>>()})
}

/// SMB kaydini kaldirir. Hata varsa kayit kalir (Python ile ayni). Donus: kalan sorunlar.
fn smb_temizle(token: &str) -> Vec<String> {
    let Some(paylasim) = kilit(&SMB_PAYLASIMLAR).remove(token) else {
        return Vec::new();
    };
    let sorunlar = smb::paylas_kaldir(&paylasim);
    if !sorunlar.is_empty() {
        kilit(&SMB_PAYLASIMLAR).insert(token.to_string(), paylasim);
    }
    sorunlar
}

/// Python `share_delete`. Paylasim kalmazsa tunel ve dar sunucu kapanir.
fn share_delete(token: &str) -> Json {
    let kayitli = kilit(&PAYLASIMLAR).contains_key(token);
    if !kayitli && paylasim::paylasim_bul(token).is_none() {
        return json!({"ok": false, "error": "Paylaşım bulunamadı."});
    }
    let sorunlar = smb_temizle(token);
    if !sorunlar.is_empty() {
        return json!({
            "ok": false,
            "error": format!("Paylaşım kaynakları temizlenemedi: {}", sorunlar.join("; ")),
        });
    }
    paylasim::paylasim_sil(token);
    kilit(&PAYLASIMLAR).remove(token);
    if kilit(&PAYLASIMLAR).is_empty() {
        yonetim::tuneli_durdur();
    }
    json!({"ok": true})
}

fn dosya_sec_ve_paylas(k: &Kabuk, c: &ApiCtx) -> Result<Json> {
    if k.app.get_webview_window(ANA).is_none() {
        return Ok(json!({"ok": false}));
    }
    let secim = k
        .app
        .dialog()
        .file()
        .blocking_pick_files()
        .unwrap_or_default();
    if secim.is_empty() {
        return Ok(json!({"ok": false, "error": "Dosya seçimi iptal edildi."}));
    }
    let mut dosyalar = Vec::new();
    for dosya in secim {
        let Ok(yol) = dosya.into_path() else {
            continue;
        };
        if !yol.is_file() {
            continue;
        }
        let token = paylasim_kaydet(&yol);
        dosyalar.push(paylasim_sonucu(k, c, &token, &yol, ""));
    }
    if dosyalar.is_empty() {
        return Ok(json!({"ok": false, "error": "Geçerli dosya seçilmedi."}));
    }
    Ok(json!({"ok": true, "files": dosyalar}))
}

/// Python `paylasim_stop`: SMB temizligi basarili olan paylasimlar kaldirilir; hatalilar kalir.
/// Tunel ve dar sunucu her durumda kapanir (Python ile ayni).
fn paylasim_durdur(c: &ApiCtx) {
    let tokenler: Vec<String> = kilit(&PAYLASIMLAR).keys().cloned().collect();
    for token in tokenler {
        let sorunlar = smb_temizle(&token);
        if sorunlar.is_empty() {
            paylasim::paylasim_sil(&token);
            kilit(&PAYLASIMLAR).remove(&token);
        } else {
            c.store.log(
                "error",
                &format!("Paylaşım temizliği tamamlanamadı: {}", sorunlar.join("; ")),
                "",
            );
        }
    }
    yonetim::tuneli_durdur();
}

/// Python `ayarlari_dogrula_kaydet`: ayar kaydi + internet paylasimi kapaliysa paylasimi durdur.
fn ayarlari_dogrula_kaydet(c: &ApiCtx, payload: &JsonMap) -> Result<Json> {
    let sonuc = bridge::ayar_kaydet(c, payload)?;
    if sonuc["ok"] == json!(true) && sonuc["ayarlar"]["internet_paylasim"] == json!(false) {
        paylasim_durdur(c);
    }
    Ok(sonuc)
}

fn ag_konumlari_listele(c: &ApiCtx) -> Result<Json> {
    let ham = ayar_str(c, "ag_konumlari");
    let konumlar: Vec<&str> = ham.lines().filter(|x| !x.trim().is_empty()).collect();
    Ok(json!({"ok": true, "konumlar": konumlar}))
}

// --- bekleyen indirme istekleri (yerelden_sor / tarayicidan_sor) -----------

/// Python `bekleyen_onayla`'nin indirme kismi: secimle birlestirilmis istegi manager.add ile baslatir.
fn indir_onayla(c: &ApiCtx, t: &JsonMap) -> Json {
    let metin = |anahtar: &str| {
        t.get(anahtar)
            .and_then(Json::as_str)
            .unwrap_or("")
            .to_string()
    };
    let url = metin("url").trim().to_string();
    let kind = match metin("kind") {
        k if k.is_empty() => afudm_core::queue::detect_kind(&url).to_string(),
        k => k,
    };
    let ad = afudm_db::kaydet::guvenli_dosya_adi(&metin("filename"));
    let hedef = match yonetim::hedef_klasor(
        c,
        &metin("dest_dir"),
        &url,
        &kind,
        &metin("kategori"),
        false,
    ) {
        Ok(h) => h,
        Err(e) => {
            c.store
                .log("error", &format!("Download approval failed: {e}"), "");
            return json!({"ok": false, "error": e});
        }
    };
    let mut istek = JsonMap::new();
    istek.insert("source".into(), json!(url));
    istek.insert("kind".into(), json!(kind));
    if let Some(h) = hedef {
        istek.insert("dest_dir".into(), json!(h));
    }
    istek.insert(
        "quality".into(),
        t.get("quality").cloned().unwrap_or(Json::Null),
    );
    istek.insert(
        "audio_only".into(),
        json!(t.get("audio_only").and_then(Json::as_bool).unwrap_or(false)),
    );
    istek.insert("start_at".into(), json!(metin("start_at")));
    istek.insert(
        "headers".into(),
        t.get("headers").cloned().unwrap_or_else(|| json!({})),
    );
    istek.insert(
        "filename".into(),
        if kind == "http" && !ad.is_empty() {
            json!(ad)
        } else {
            Json::Null
        },
    );
    istek.insert(
        "title".into(),
        if kind == "video" && !ad.is_empty() {
            json!(ad)
        } else {
            t.get("title").cloned().unwrap_or(Json::Null)
        },
    );
    istek.insert(
        "cookies".into(),
        t.get("cookies").cloned().unwrap_or(Json::Null),
    );
    istek.insert(
        "user_agent".into(),
        t.get("user_agent").cloned().unwrap_or(Json::Null),
    );
    match c.manager.add(&istek) {
        Ok(sonuc) if sonuc["ok"] == json!(false) => {
            let hata_metni = sonuc["error"]
                .as_str()
                .unwrap_or("Download rejected")
                .to_string();
            c.store.log(
                "error",
                &format!("Download approval failed: {hata_metni}"),
                "",
            );
            json!({"ok": false, "error": hata_metni})
        }
        Ok(sonuc) => {
            if let Ok(ana) = c.manager.current_download_dir() {
                let _ = afudm_db::kaydet::son_klasoru_hatirla(&*c.store, &ana, t);
            }
            c.store.log("info", "Download approval accepted", "");
            ok_birlestir(sonuc)
        }
        Err(e) => {
            c.store
                .log("error", &format!("Download approval failed: {e}"), "");
            json!({"ok": false, "error": e.to_string()})
        }
    }
}

/// Kuyrugun onayini bekleyen is parcacigi: onay gelirse indirmeyi baslatir, iptal ise biter.
fn onay_bekle(ctx: ApiCtx, rx: mpsc::Receiver<Option<JsonMap>>) {
    std::thread::spawn(move || {
        if let Ok(Some(secim)) = rx.recv() {
            let _ = indir_onayla(&ctx, &secim);
        }
    });
}

/// Python `yerelden_sor`: masaustu dosya iliskilendirmesi; ana panelde onay bekler.
fn yerelden_sor(k: &Kabuk, mut istek: JsonMap) -> Json {
    let Some(ctx) = k.ctx.get().cloned() else {
        return bridge::motor_hazir_degil();
    };
    istek.insert("source".into(), json!("desktop"));
    let (kimlik, rx) = k.ui.kuyruga_ekle(istek);
    onay_bekle(ctx, rx);
    window::goster(&k.app);
    if let Some(w) = k.app.get_webview_window(ANA) {
        let _ = w.eval("window.afudmBekleyen && window.afudmBekleyen()");
    }
    json!(kimlik)
}

/// Python `tarayicidan_sor`: uzanti istegini bekletir; yalniz ayri indirme penceresini gosterir.
fn tarayicidan_sor(k: &Kabuk, istek: JsonMap) -> Json {
    if istek.get("prompt_source").and_then(Json::as_str) == Some("desktop") {
        return yerelden_sor(k, istek);
    }
    let Some(ctx) = k.ctx.get().cloned() else {
        return bridge::motor_hazir_degil();
    };
    let mut istek = istek;
    istek.insert("source".into(), json!("browser"));
    let (kimlik, rx) = k.ui.kuyruga_ekle(istek);
    onay_bekle(ctx, rx);
    let _ = window::indirme_goster(&k.app);
    json!(kimlik)
}

// --- motor, butunluk, guc, kurtarma, token, tracker -----------------------

/// Python `motor_indir`: arka planda indirir; ilerleme MOTOR_ILERLEME'de tutulur.
fn motor_indir(k: &Kabuk, ad: &str) -> Json {
    {
        let mut ilerleme = kilit(&MOTOR_ILERLEME);
        let suruyor = ilerleme
            .get(ad)
            .and_then(|v| v.get("durum"))
            .and_then(Json::as_str)
            == Some("iniyor");
        if suruyor {
            return json!({"ok": true, "zaten": true});
        }
        ilerleme.insert(
            ad.to_string(),
            json!({"durum": "iniyor", "inen": 0, "toplam": 0}),
        );
    }
    let app_dir = k.app_dir.clone();
    let ad_t = ad.to_string();
    let basla = std::thread::Builder::new().spawn(move || {
        let ilerleme = |inen: u64, toplam: u64| {
            kilit(&MOTOR_ILERLEME).insert(
                ad_t.clone(),
                json!({"durum": "iniyor", "inen": inen, "toplam": toplam}),
            );
        };
        let kayit = match engines::indir(&app_dir, &ad_t, &ilerleme) {
            Ok(v) => json!({"durum": "bitti", "boyut_mb": v.get("boyut_mb").cloned().unwrap_or(Json::Null)}),
            Err(e) => json!({"durum": "hata", "hata": kisalt(&e.to_string(), 200)}),
        };
        kilit(&MOTOR_ILERLEME).insert(ad_t, kayit);
    });
    match basla {
        Ok(_) => json!({"ok": true}),
        Err(e) => {
            kilit(&MOTOR_ILERLEME).insert(
                ad.to_string(),
                json!({"durum": "hata", "hata": kisalt(&e.to_string(), 100)}),
            );
            json!({"ok": false, "error": e.to_string()})
        }
    }
}

/// Python servis.butunluk_* : hata `ok/code/message/error` sozlesmesiyle doner.
fn butunluk_cagri(k: &Kabuk, f: impl FnOnce(&afudm_core::Manager) -> Result<Json>) -> Json {
    match k.ek.get() {
        Some(e) => match f(&e.core) {
            Ok(v) => v,
            Err(err) => bridge::servis_hata(err.to_string()),
        },
        None => bridge::motor_hazir_degil(),
    }
}

/// Python `guc.durum`: aktif ag karti, WOL durumu ve uyandirmaya hazirlik.
fn guc_durumu() -> Json {
    let (ad, mac, aciklama) = aktif_kart();
    let wol = wol_durumu(&ad);
    json!({
        "ok": true,
        "kart": ad,
        "mac": mac,
        "aciklama": aciklama,
        "wol": wol,
        "hazir": uyandirmaya_hazir(),
    })
}

fn powershell(komut: &str) -> String {
    bridge::hidden_cmd("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            komut,
        ])
        .output()
        .map(|cikti| String::from_utf8_lossy(&cikti.stdout).trim().to_string())
        .unwrap_or_default()
}

fn aktif_kart() -> (String, String, String) {
    let ham = powershell(
        "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | \
         Select-Object -First 1 Name,MacAddress,InterfaceDescription | \
         ForEach-Object { $_.Name + '|' + $_.MacAddress + '|' + $_.InterfaceDescription }",
    );
    kart_ayristir(&ham)
}

/// Python aktif_kart ayristirmasi: "ad|mac|aciklama" ilk satiri; mac buyuk harf.
fn kart_ayristir(ham: &str) -> (String, String, String) {
    let Some(satir) = ham.lines().next() else {
        return (String::new(), String::new(), String::new());
    };
    let parcalar: Vec<&str> = satir.split('|').collect();
    if parcalar.len() < 2 {
        return (String::new(), String::new(), String::new());
    }
    (
        parcalar[0].trim().to_string(),
        parcalar[1].trim().to_uppercase(),
        parcalar
            .get(2)
            .map(|p| p.trim().to_string())
            .unwrap_or_default(),
    )
}

fn wol_durumu(kart_adi: &str) -> Option<bool> {
    if kart_adi.is_empty() {
        return None;
    }
    let ham = powershell(&format!(
        "(Get-NetAdapterPowerManagement -Name '{kart_adi}' -ErrorAction SilentlyContinue).WakeOnMagicPacket"
    ));
    wol_ayristir(&ham)
}

/// Python wol_acik_mi ayristirmasi. Taninmayan deger None (okunamadi).
fn wol_ayristir(ham: &str) -> Option<bool> {
    match ham.trim().to_lowercase().as_str() {
        "enabled" | "1" | "true" => Some(true),
        "disabled" | "0" | "false" => Some(false),
        _ => None,
    }
}

fn uyandirmaya_hazir() -> bool {
    let ham = powershell("powercfg -devicequery wake_armed");
    uyandirma_metni_destekli(&ham)
}

/// Python regex `(ethernet|wi-?fi|wireless|network|realtek|intel\(r\) )` (buyuk/kucuk harf duyarsiz).
fn uyandirma_metni_destekli(ham: &str) -> bool {
    let kucuk = ham.to_lowercase();
    [
        "ethernet",
        "wifi",
        "wi-fi",
        "wireless",
        "network",
        "realtek",
        "intel(r) ",
    ]
    .iter()
    .any(|desen| kucuk.contains(*desen))
}

/// Python `security_rotate_token`: token dosyasini yeniler; acik panel/uc noktasi dosyasi guncellenir.
fn security_rotate_token(k: &Kabuk) -> Json {
    let Some(c) = k.ctx.get() else {
        return bridge::motor_hazir_degil();
    };
    match afudm_api::security::rotate_token(&c.data_dir) {
        Ok(()) => {
            let _ = afudm_api::write_endpoint(c, port(k));
            json!({"ok": true, "message": "Yeni anahtar etkin; eski anahtar aninda gecersiz."})
        }
        Err(e) => hata(e.to_string()),
    }
}

/// Python `tracker_klasoru_ac`: tracker klasorunu hazirlar ve Explorer'da acar.
fn tracker_klasoru_ac(k: &Kabuk) -> Json {
    let klasor = k.app_dir.join("trackers");
    afudm_core::torrent::saglik::klasoru_hazirla(&klasor);
    bridge::gezgin_ac(&klasor, false);
    json!({"ok": true})
}

/// Python `seed_tracker_kaydet`: elle eklenen trackerlari ayiklar ve saklar.
fn seed_tracker_kaydet(c: &ApiCtx, metin: &str) -> Result<Json> {
    let temiz = afudm_core::torrent::trackers::ayikla(metin);
    let liste = temiz.join("\n");
    c.store.set("ek_trackerlar", json!(liste))?;
    Ok(json!({"ok": true, "sayi": temiz.len(), "liste": liste}))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ok_birlestir_alanlari_ekler() {
        let cikti = ok_birlestir(json!({"id": 3, "ad": "x"}));
        assert_eq!(cikti, json!({"ok": true, "id": 3, "ad": "x"}));
    }

    #[test]
    fn gecersiz_girdi_bad_request_doner() {
        let cikti = bad(AfuError::Invalid(
            "rol 'yonetici' veya 'salt_okur' olmali".into(),
        ));
        assert_eq!(cikti["code"], "BAD_REQUEST");
        assert_eq!(cikti["ok"], false);
        let diger = bad(AfuError::Db("kilit".into()));
        assert_eq!(diger["ok"], false);
        assert!(diger.get("code").is_none());
    }

    #[test]
    fn kart_satiri_ayristirilir_ve_mac_buyuk_harf() {
        let (ad, mac, aciklama) = kart_ayristir("Ethernet|aa-bb-cc-dd-ee-ff|Realtek PCIe GbE\r\n");
        assert_eq!(ad, "Ethernet");
        assert_eq!(mac, "AA-BB-CC-DD-EE-FF");
        assert_eq!(aciklama, "Realtek PCIe GbE");
        assert_eq!(
            kart_ayristir(""),
            (String::new(), String::new(), String::new())
        );
    }

    #[test]
    fn wol_metni_true_false_veya_bilinmez() {
        assert_eq!(wol_ayristir("Enabled\r\n"), Some(true));
        assert_eq!(wol_ayristir("0"), Some(false));
        assert_eq!(wol_ayristir(""), None);
    }

    #[test]
    fn uyandirma_metni_ag_kartini_tanir() {
        assert!(uyandirma_metni_destekli("Intel(R) Wi-Fi 6 AX201"));
        assert!(uyandirma_metni_destekli("Realtek Gaming GbE"));
        assert!(!uyandirma_metni_destekli("Keyboard HID"));
    }
}
