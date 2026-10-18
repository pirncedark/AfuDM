//! Queue and manager operations ported from core/manager.py (team C).
mod dosya_adi;
mod files;
mod models;
pub(crate) mod netcheck;
mod probe;
pub mod proxy;
mod rules;
mod settings;
mod shaping;
mod sync;
#[cfg(test)]
mod tests;

use crate::Manager;
use afudm_types::{AfuError, Json, JsonMap, Result};
use serde_json::json;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::MutexGuard;

/// Shared queue state. D may use removed_hashes and register video snapshots/stop callbacks.
#[derive(Default)]
pub struct State {
    pub removed_hashes: HashSet<String>,
    pub removed_gids: HashSet<String>,
    pub preview_gids: HashSet<String>,
    pub auth_required_gids: HashSet<String>,
    /// Python _known_complete: aria2 tamamlanmasi tamamlandi zincirine bir kez girer.
    pub known_complete: HashSet<String>,
    pub cookies: HashMap<i64, Vec<Json>>,
    /// Acilis kurtarmasi (kesilenleri_kurtar) motor ilk kez uyanik senkronda bir kez calisir.
    pub kurtarma_bitti: bool,
    pub last_error: String,
    pub settings_errors: Vec<Json>,
    pub started: bool,
}

fn state(m: &Manager) -> Result<MutexGuard<'_, State>> {
    m.queue_state
        .lock()
        .map_err(|_| AfuError::Other("kuyruk kilidi kullanilamiyor".into()))
}
fn invalid(message: impl Into<String>) -> AfuError {
    AfuError::Invalid(message.into())
}
fn text(value: &Json) -> &str {
    value.as_str().unwrap_or("")
}
fn number(value: &Json) -> i64 {
    value
        .as_i64()
        .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
        .or_else(|| value.as_f64().map(|n| n as i64))
        .unwrap_or(0)
}
fn truthy(value: &Json) -> bool {
    match value {
        Json::Null => false,
        Json::Bool(b) => *b,
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
        _ => value.as_f64().is_some_and(|v| v != 0.0),
    }
}
fn now() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}
fn map(value: Json) -> JsonMap {
    value.as_object().cloned().unwrap_or_default()
}
fn options(row: &Json) -> JsonMap {
    row.get("options")
        .and_then(Json::as_object)
        .cloned()
        .or_else(|| {
            row.get("options")
                .and_then(Json::as_str)
                .and_then(|s| serde_json::from_str(s).ok())
        })
        .unwrap_or_default()
}
fn row_id(row: &Json) -> i64 {
    number(&row["id"])
}
fn required_row(m: &Manager, gid: &str) -> Result<Json> {
    m.store
        .by_gid(gid)?
        .ok_or_else(|| AfuError::NotFound(format!("kayit bulunamadi: {gid}")))
}
fn setting(m: &Manager, key: &str, default: Json) -> Result<Json> {
    Ok(m.store.get(key)?.filter(truthy).unwrap_or(default))
}
const ACTIVE: [&str; 5] = ["queued", "active", "waiting", "paused", "scheduled"];

pub fn start(m: &Manager) -> Result<()> {
    if state(m)?.started {
        return Ok(());
    }
    let auth = m.data_dir.join("aria2.auth-required.json");
    let saved: Vec<Json> = std::fs::read(auth)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or_default();
    state(m)?.auth_required_gids = saved
        .iter()
        .filter_map(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .collect();
    // Daemon/process ownership stays with the shell/engine. RPC is injected into Manager.
    settings::apply(m)?;
    crate::video::yetimleri_duzelt(m)?;
    state(m)?.started = true;
    m.store.log("info", "AfuDM basladi", "");
    Ok(())
}

pub fn stop(m: &Manager) -> Result<()> {
    crate::video::aktif_isleri_kapat(m);
    sync_aria2(m)?;
    if !m.rpc().sleeping() {
        let _ = m.rpc().call("aria2.purgeDownloadResult", vec![]);
    }
    let _ = m.rpc().save_session();
    let _ = m.rpc().shutdown(false);
    let mut s = state(m)?;
    s.started = false;
    s.cookies.clear();
    drop(s);
    m.store.log("info", "AfuDM kapandi", "");
    Ok(())
}

pub fn set_mode(m: &Manager, ad: &str) -> Result<Json> {
    let ad = ad.trim().to_lowercase();
    if !["snail", "normal", "turbo"].contains(&ad.as_str()) {
        return Err(invalid(format!(
            "gecersiz hiz profili: {ad} (snail|normal|turbo olmali)"
        )));
    }
    m.store.set("hiz_profili", json!(ad))?;
    settings::apply(m)?;
    Ok(
        json!({"ok":true,"profil":ad,"limit_kb":settings::speed_limit(&m.store.all_settings()?),"durum":"degisti"}),
    )
}

pub fn baglanti_ayarla(
    m: &Manager,
    gid: &str,
    baglanti: Option<i64>,
    hiz_kb: Option<i64>,
) -> Result<Json> {
    let row = required_row(m, gid)?;
    if gid.starts_with("yt:") {
        return Err(invalid("video islerinde canli ayar desteklenmez"));
    }
    let mut sec = JsonMap::new();
    if let Some(n) = baglanti {
        if !(1..=64).contains(&n) {
            return Err(invalid("baglanti sayisi 1-64 araliginda olmali"));
        }
        sec.insert("max-connection-per-server".into(), json!(n.to_string()));
    }
    if let Some(n) = hiz_kb {
        if n < 0 {
            return Err(invalid("hiz negatif KB/s olamaz"));
        }
        sec.insert(
            "max-download-limit".into(),
            json!(if n == 0 { "0".into() } else { format!("{n}K") }),
        );
    }
    if !sec.is_empty() {
        m.rpc().change_option(gid, &sec).map_err(|e| {
            // Python manager.py: "canli degistirilemedi: %s" % str(exc)[:160]
            let neden: String = e.to_string().chars().take(160).collect();
            invalid(format!("canli degistirilemedi: {neden}"))
        })?;
        let mut opts = options(&row);
        if let Some(n) = baglanti {
            opts.insert("baglanti".into(), json!(n));
        }
        if let Some(n) = hiz_kb {
            opts.insert("hiz_kb".into(), json!(n));
        }
        m.store
            .update_by_id(row_id(&row), &map(json!({"options":opts})))?;
        m.store.log(
            "info",
            &format!("is ayarlari canli degistirildi: {}", text(&row["title"])),
            gid,
        );
    }
    Ok(json!({"ok":true,"gid":gid,"baglanti":baglanti,"hiz_kb":hiz_kb}))
}

pub fn update_settings(m: &Manager, changes: &JsonMap) -> Result<Json> {
    settings::update(m, changes)
}
pub fn current_download_dir(m: &Manager) -> Result<String> {
    Ok(setting(
        m,
        "download_dir",
        json!(m.app_dir.join("downloads").to_string_lossy()),
    )?
    .as_str()
    .unwrap_or("")
    .to_owned())
}

pub fn add_completed_file(m: &Manager, path: &Path) -> Result<Json> {
    let path = path
        .canonicalize()
        .map_err(|_| invalid("Dosya indirme klasöründe olmalı."))?;
    let root = PathBuf::from(current_download_dir(m)?)
        .canonicalize()
        .map_err(|_| invalid("Dosya indirme klasöründe olmalı."))?;
    if path.parent() != Some(root.as_path()) || !path.is_file() {
        return Err(invalid("Dosya indirme klasöründe olmalı."));
    }
    let mut bytes: [u8; 16] = rand::random();
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    let gid = format!(
        "local:{}",
        bytes.iter().map(|b| format!("{b:02x}")).collect::<String>()
    );
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let size = path.metadata()?.len();
    let id = m.store.add(
        "http",
        &gid,
        Some(&name),
        root.to_str(),
        Some(&map(json!({"local_file":true}))),
        None,
        Some(&gid),
    )?;
    m.store.update_by_id(id,&map(json!({"filename":name,"status":"complete","total_bytes":size,"done_bytes":size,"finished_at":now()})))?;
    m.store
        .log("info", "Tarayıcıdan gelen dosya kaydedildi.", "");
    Ok(json!({"id":id,"gid":gid,"kind":"http"}))
}

pub fn add(m: &Manager, req: &JsonMap) -> Result<Json> {
    let req = models::normalize(req)?;
    let source = text(&req["source"]);
    if !dosya_adi::supported(source) {
        return Err(invalid(
            "gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali",
        ));
    }
    let kind = req
        .get("kind")
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| dosya_adi::detect_kind(source));
    let guard = m
        .kilit
        .lock()
        .map_err(|_| AfuError::Other("yonetici kilidi kullanilamiyor".into()))?;
    state(m)?
        .removed_hashes
        .remove(&dosya_adi::magnet_hash(source));
    if let Some(duplicate) = find_duplicate(m, source)? {
        let paused_preview = kind == "torrent"
            && duplicate["status"] == "paused"
            && !text(&duplicate["gid"]).is_empty()
            && m.store.by_gid(text(&duplicate["gid"]))?.is_none();
        if !paused_preview
            && !(req.get("adopt_gid").is_some_and(truthy)
                && req.get("adopt_gid") == duplicate.get("gid"))
        {
            let title = duplicate
                .get("title")
                .and_then(Json::as_str)
                .filter(|s| !s.is_empty())
                .map(str::to_owned)
                .unwrap_or_else(|| source.chars().take(60).collect());
            return Err(invalid(format!(
                "{} zaten kuyrukta: {title}",
                if kind == "torrent" {
                    "bu torrent"
                } else {
                    "bu baglanti"
                }
            )));
        }
    }
    let defaults = map(
        json!({"dest_dir":current_download_dir(m)?,"proxy":setting(m,"proxy",json!(""))?,"max_speed_kb":setting(m,"max_speed_kb",json!(0))?,"split":setting(m,"max_conn_per_server",json!(16))?}),
    );
    let (effective, trace) = rules::evaluate(&m.store.rules_list()?, defaults, &req, kind);
    let dest = effective
        .get("dest_dir")
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .unwrap_or(current_download_dir(m)?);
    let start_after = req
        .get("start_after")
        .filter(|v| truthy(v))
        .and_then(Json::as_f64)
        .or(models::parse_time(
            effective.get("start_after").unwrap_or(&json!("")),
        )?);
    std::fs::create_dir_all(&dest)?;
    let mut opts = map(
        json!({"quality":req.get("quality").filter(|v|truthy(v)).cloned().unwrap_or(setting(m,"video_quality",json!("best"))?),"audio_only":req["audio_only"],"playlist":req["playlist"],"headers":req["headers"],"filename":req.get("filename").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"user_agent":req.get("user_agent").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"title":req.get("title").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"proxy":effective.get("proxy").cloned().unwrap_or(json!("")),"hiz_kb":effective.get("max_speed_kb").cloned().unwrap_or(json!(0)),"baglanti":effective.get("split").cloned().unwrap_or(json!(0)),"rules_trace":trace,"checksum":req.get("checksum").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"adopt_gid":req.get("adopt_gid"),"selected_files":req.get("selected_files")}),
    );
    for key in [
        "altyazi_diller",
        "oto_altyazi",
        "altyazi_goem",
        "kucuk_resim",
        "ustveri_goem",
        "bolumler",
        "sponsorblock",
        "bolum_araligi",
        "kapsayici",
        "ses_formati",
        "dosya_sablonu",
        "tarayici_cerezi",
    ] {
        let fallback = if ["oto_altyazi", "altyazi_goem", "ustveri_goem"].contains(&key) {
            json!(false)
        } else {
            json!("")
        };
        opts.insert(
            key.into(),
            req.get(key)
                .filter(|v| truthy(v))
                .cloned()
                .unwrap_or(setting(m, &format!("video_{key}"), fallback)?),
        );
    }
    let title = opts
        .get("title")
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| dosya_adi::guess(source));
    let id = m.store.add(
        kind,
        source,
        Some(&title),
        Some(&dest),
        Some(&opts),
        start_after,
        None,
    )?;
    let cookies = models::cookies(req.get("cookies"));
    if !cookies.is_empty() {
        state(m)?.cookies.insert(id, cookies);
    }
    drop(guard);
    if let Some(when) = start_after {
        m.store.log("info", "indirme zamanlandi", "");
        return Ok(json!({"id":id,"kind":kind,"scheduled_for":when}));
    }
    let row = m
        .store
        .by_id(id)?
        .ok_or_else(|| AfuError::NotFound("kayit bulunamadi".into()))?;
    launch(m, &row)
}

fn live_statuses(m: &Manager) -> Result<Vec<Json>> {
    let rpc = m.rpc();
    let mut live = rpc.tell_active(&[])?;
    live.extend(rpc.tell_waiting(0, 200, &[])?);
    live.extend(rpc.tell_stopped(0, 200, &[])?);
    Ok(live)
}

/// Python Manager.find_duplicate: ayni is kuyrukta mi (canli kayit dondurur).
pub fn find_duplicate(m: &Manager, source: &str) -> Result<Option<Json>> {
    let hash = dosya_adi::magnet_hash(source);
    let live = match live_statuses(m) {
        Ok(v) => Some(v),
        Err(_) => {
            state(m)?.last_error = "motor durum bilgisi alinamadi".into();
            None
        }
    };
    if !hash.is_empty() {
        if let Some(status) = live
            .as_ref()
            .into_iter()
            .flatten()
            .find(|s| text(&s["infoHash"]).to_lowercase() == hash)
        {
            return Ok(Some(shaping::aria(m, status)?));
        }
    }
    let video_gids = crate::video::gidler(m);
    for row in m.store.list(None, 300)? {
        if !ACTIVE.contains(&text(&row["status"])) {
            continue;
        }
        if dosya_adi::url_key(text(&row["source"])) != dosya_adi::url_key(source)
            && (hash.is_empty() || dosya_adi::magnet_hash(text(&row["source"])) != hash)
        {
            continue;
        }
        let gid = text(&row["gid"]);
        if row["status"] == "scheduled"
            || (row["status"] == "queued" && gid.is_empty())
            || live.is_none()
            || video_gids.contains(gid)
            || live
                .as_ref()
                .is_some_and(|l| l.iter().any(|s| s["gid"] == gid))
        {
            return Ok(Some(row));
        }
        m.store.update_by_id(row_id(&row),&map(json!({"status":"error","finished_at":now(),"error":"motorda karsiligi kalmadi (uygulama kapanmis olabilir)"})))?;
        m.store.log(
            "warn",
            &format!("olu kayit temizlendi: {}", text(&row["title"])),
            gid,
        );
    }
    Ok(None)
}

fn connection_options(opts: &JsonMap) -> JsonMap {
    let mut out = JsonMap::new();
    let conn = number(opts.get("baglanti").unwrap_or(&Json::Null));
    let speed = number(opts.get("hiz_kb").unwrap_or(&Json::Null));
    if (1..=64).contains(&conn) {
        out.insert("max-connection-per-server".into(), json!(conn.to_string()));
    }
    if speed > 0 {
        out.insert("max-download-limit".into(), json!(format!("{speed}K")));
    }
    out
}

fn request_headers(opts: &JsonMap, cookies: &[Json]) -> Vec<String> {
    let mut headers: Vec<_> = opts
        .get("headers")
        .and_then(Json::as_object)
        .into_iter()
        .flatten()
        .map(|(k, v)| {
            format!(
                "{k}: {}",
                v.as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| v.to_string())
            )
        })
        .collect();
    if !cookies.is_empty() {
        headers.push(format!(
            "Cookie: {}",
            cookies
                .iter()
                .map(|c| format!("{}={}", text(&c["name"]), text(&c["value"])))
                .collect::<Vec<_>>()
                .join("; ")
        ));
    }
    headers
}

fn launch(m: &Manager, row: &Json) -> Result<Json> {
    let id = row_id(row);
    let kind = text(&row["kind"]);
    let opts = options(row);
    let cookies = state(m)?.cookies.get(&id).cloned().unwrap_or_default();
    let dest = row
        .get("dest_dir")
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .unwrap_or(current_download_dir(m)?);
    let result: Result<String> = (|| {
        if ["torrent", "video"].contains(&kind) {
            // D receives both normalized flat fields and the persisted row/options. It returns gid or {gid,...}.
            let mut req = opts.clone();
            req.extend(row.as_object().cloned().unwrap_or_default());
            req.insert("row_id".into(), json!(id));
            req.insert("options".into(), json!(opts));
            req.insert("dest_dir".into(), json!(dest));
            req.insert("cookies".into(), json!(cookies));
            let result = if kind == "torrent" {
                crate::torrent::torrent_ekle_ic(m, &req)?
            } else {
                crate::video::video_ekle_ic(m, &req)?
            };
            let gid = result
                .as_str()
                .or_else(|| result.get("gid").and_then(Json::as_str))
                .filter(|s| !s.is_empty())
                .ok_or_else(|| AfuError::Engine("motor indirme kimligi dondurmedi".into()))?;
            return Ok(gid.to_owned());
        }
        let mut aria = connection_options(&opts);
        aria.insert("dir".into(), json!(dest));
        for (a, b) in [("user_agent", "user-agent"), ("checksum", "checksum")] {
            if let Some(v) = opts.get(a).filter(|v| truthy(v)) {
                aria.insert(b.into(), v.clone());
            }
        }
        if let Some(v) = opts.get("filename").filter(|v| truthy(v)) {
            let ad = probe::guvenli_dosya_adi(v.as_str().unwrap_or(""));
            if ad.is_empty() {
                return Err(AfuError::Invalid(
                    "Dosya adi uygun degil. Baska bir ad sec.".into(),
                ));
            }
            aria.insert("out".into(), json!(ad));
        }
        let headers = request_headers(&opts, &cookies);
        if !headers.is_empty() {
            aria.insert("header".into(), json!(headers));
        }
        if let Some(p) = proxy::proksi_bul(m, &opts)? {
            aria.extend(proxy::aria2_secenekleri(&p));
        }
        m.rpc().add_uri(&[text(&row["source"]).into()], Some(&aria))
    })();
    let gid = match result {
        Ok(gid) => gid,
        Err(error) => {
            m.store.update_by_id(
                id,
                &map(json!({"status":"error","error":"indirme baslatilamadi","finished_at":now()})),
            )?;
            m.store.log(
                "error",
                "baslatilamadi: motor indirmeyi baslatamadi",
                text(&row["gid"]),
            );
            return Err(error);
        }
    };
    m.store.attach_gid(id, &gid)?;
    m.store.log(
        "info",
        &format!("basladi [{kind}]: {}", text(&row["title"])),
        &gid,
    );
    let mut accepted = HashSet::from([gid.clone()]);
    if let Some(adopt) = opts.get("adopt_gid").and_then(Json::as_str) {
        accepted.insert(adopt.into());
    }
    let previews = state(m)?.preview_gids.clone();
    for _ in 0..=previews.len() {
        let before = accepted.len();
        for preview in &previews {
            if let Ok(status) = m.rpc().tell_status(preview, &["followedBy"]) {
                if status["followedBy"]
                    .as_array()
                    .is_some_and(|children| children.iter().any(|c| accepted.contains(text(c))))
                {
                    accepted.insert(preview.clone());
                }
            }
        }
        if accepted.len() == before {
            break;
        }
    }
    state(m)?.preview_gids.retain(|p| !accepted.contains(p));
    Ok(json!({"id":id,"gid":gid,"kind":kind}))
}

pub fn pause(m: &Manager, gid: &str) -> Result<bool> {
    required_row(m, gid)?;
    if gid.starts_with("yt:") {
        if !crate::video::durdur(m, gid) {
            return Ok(false);
        }
    } else if m.rpc().pause(gid, true).is_err() {
        return Ok(false);
    }
    m.store
        .update_by_gid(gid, &map(json!({"status":"paused"})))?;
    Ok(true)
}

pub fn resume(m: &Manager, gid: &str) -> Result<bool> {
    if state(m)?.auth_required_gids.contains(gid) {
        return Err(invalid(
            "Kaydedilen oturumdaki giris bilgisi silindi; yeni bilgilerle indirmeyi Yenile.",
        ));
    }
    let row = required_row(m, gid)?;
    if gid.starts_with("yt:") {
        m.store
            .update_by_id(row_id(&row), &map(json!({"status":"queued","gid":null})))?;
        let row = m
            .store
            .by_id(row_id(&row))?
            .ok_or_else(|| invalid("kayit bulunamadi"))?;
        launch(m, &row)?;
    } else {
        m.rpc().unpause(gid)?;
        m.store
            .update_by_gid(gid, &map(json!({"status":"active"})))?;
    }
    Ok(true)
}

pub fn remove(m: &Manager, gid: &str, delete_files: bool) -> Result<bool> {
    files::remove(m, gid, delete_files)
}
pub fn resolve_item_path(m: &Manager, gid: &str) -> Result<Option<PathBuf>> {
    files::resolve(m, gid)
}
pub fn phone_download_path(m: &Manager, gid: &str) -> Result<Option<PathBuf>> {
    files::phone_path(m, gid)
}

pub fn pause_all(m: &Manager) -> Result<()> {
    let _ = m.rpc().pause_all();
    crate::video::tumunu_durdur(m);
    Ok(())
}

pub fn resume_all(m: &Manager) -> Result<()> {
    let auth = state(m)?.auth_required_gids.clone();
    if auth.is_empty() {
        let _ = m.rpc().unpause_all();
    } else if let Ok(mut statuses) = m.rpc().tell_active(&[]) {
        if let (Ok(waiting), Ok(stopped)) = (
            m.rpc().tell_waiting(0, 1000, &[]),
            m.rpc().tell_stopped(0, 1000, &[]),
        ) {
            statuses.extend(waiting);
            statuses.extend(stopped);
            for s in statuses {
                let gid = text(&s["gid"]);
                if !gid.is_empty() && !auth.contains(gid) && s["status"] == "paused" {
                    let _ = m.rpc().unpause(gid);
                }
            }
        }
    }
    for row in m.store.list(None, 1000)? {
        if row["status"] == "paused" && text(&row["gid"]).starts_with("yt:") {
            resume(m, text(&row["gid"]))?;
        }
    }
    Ok(())
}

pub fn retry(m: &Manager, row_id: i64) -> Result<Json> {
    let row = m
        .store
        .by_id(row_id)?
        .ok_or_else(|| invalid("kayit bulunamadi"))?;
    let old = text(&row["gid"]);
    if state(m)?.auth_required_gids.contains(old) {
        return Err(invalid(
            "Bu indirme yeni giris bilgisi gerektiriyor; Yenile akisini kullanin.",
        ));
    }
    m.store.update_by_id(
        row_id,
        &map(json!({"status":"queued","gid":null,"error":null})),
    )?;
    if !old.is_empty() {
        state(m)?.removed_gids.insert(old.into());
        let _ = m.rpc().remove_result(old);
    }
    launch(
        m,
        &m.store
            .by_id(row_id)?
            .ok_or_else(|| invalid("kayit bulunamadi"))?,
    )
}

pub fn renew(
    m: &Manager,
    gid: &str,
    yeni_url: &str,
    headers: Option<&JsonMap>,
    cookies: Option<&[Json]>,
    user_agent: Option<&str>,
) -> Result<Json> {
    let url = yeni_url.trim();
    if !["http://", "https://", "ftp://"]
        .iter()
        .any(|s| url.to_lowercase().starts_with(s))
    {
        return Err(invalid("yeni adres http(s) veya ftp olmali"));
    }
    let row = required_row(m, gid)?;
    if !["http", "ftp"].contains(&text(&row["kind"])) {
        return Err(invalid(format!(
            "{} isleri yenilenemez — yalnizca http(s)/ftp indirmeleri",
            text(&row["kind"])
        )));
    }
    let status = match m.rpc().tell_status(gid, &["status", "files", "dir"]) {
        Ok(s) => s,
        Err(_) => {
            if ["complete", "error"].contains(&text(&row["status"])) {
                json!({"status":row["status"]})
            } else {
                return Err(invalid("motor o isi bilmiyor: indirme bulunamadi"));
            }
        }
    };
    let uris = status["files"]
        .as_array()
        .and_then(|f| f.first())
        .and_then(|f| f["uris"].as_array());
    let old = uris
        .and_then(|u| {
            u.iter()
                .find(|u| u["status"] == "used")
                .or_else(|| u.first())
        })
        .map(|u| text(&u["uri"]))
        .filter(|s| !s.is_empty())
        .unwrap_or(text(&row["source"]));
    let mut opts = options(&row);
    let mut hdrs = opts
        .get("headers")
        .and_then(Json::as_object)
        .cloned()
        .unwrap_or_default();
    if let Some(h) = headers {
        hdrs.extend(
            h.iter()
                .filter(|(k, v)| !k.is_empty() && truthy(v))
                .map(|(k, v)| (k.clone(), v.clone())),
        );
    }
    opts.insert("headers".into(), json!(hdrs));
    if let Some(ua) = user_agent.filter(|s| !s.is_empty()) {
        opts.insert("user_agent".into(), json!(ua));
    }
    let clean = models::cookies(cookies.map(|c| json!(c)).as_ref());
    if !clean.is_empty() {
        state(m)?.cookies.insert(row_id(&row), clean.clone());
    }
    let basliklar = request_headers(&opts, &clean);
    let mut aria = JsonMap::new();
    if !basliklar.is_empty() {
        aria.insert("header".into(), json!(basliklar));
    }
    if let Some(ua) = opts.get("user_agent").filter(|v| truthy(v)) {
        aria.insert("user-agent".into(), ua.clone());
    }
    let active = status["status"] == "active";
    let failed = status["status"] == "error";
    let (new_gid, changed, new_status) = if status["status"] == "complete" {
        let path = status["files"]
            .as_array()
            .and_then(|f| f.first())
            .and_then(|f| f.get("path"))
            .and_then(Json::as_str)
            .map(PathBuf::from)
            .unwrap_or(
                PathBuf::from(
                    row.get("dest_dir")
                        .and_then(Json::as_str)
                        .unwrap_or(&current_download_dir(m)?),
                )
                .join(text(&row["title"])),
            );
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_file(format!("{}.aria2", path.to_string_lossy()));
        let _ = m.rpc().remove_result(gid);
        aria.extend(connection_options(&opts));
        if let Some(dir) = row.get("dest_dir").filter(|v| truthy(v)) {
            aria.insert("dir".into(), dir.clone());
        }
        aria.insert("gid".into(), json!(gid));
        let new_gid = match m.rpc().add_uri(&[url.into()], Some(&aria)) {
            Ok(g) => g,
            Err(_) => {
                aria.remove("gid");
                m.rpc().add_uri(&[url.into()], Some(&aria))?
            }
        };
        (new_gid, 1, json!("active"))
    } else {
        if active {
            let _ = m.rpc().pause(gid, false);
        }
        let changed: Result<i64> = (|| {
            let n = m
                .rpc()
                .change_uri(gid, 1, &[old.into()], &[url.into()], 0)?;
            if !aria.is_empty() {
                m.rpc().change_option(gid, &aria)?;
            }
            Ok(n)
        })();
        let changed = match changed {
            Ok(n) => n,
            Err(_) => {
                if active {
                    let _ = m.rpc().unpause(gid);
                }
                return Err(invalid("adres degistirilemedi: motor adresi degistiremedi"));
            }
        };
        (
            gid.to_owned(),
            changed,
            if active || failed {
                json!("active")
            } else {
                status["status"].clone()
            },
        )
    };
    m.store.update_by_id(
        row_id(&row),
        &map(json!({"gid":new_gid,"source":url,"options":opts,"error":null,"status":new_status})),
    )?;
    clear_auth(m, gid)?;
    if active || failed {
        let _ = m.rpc().unpause(&new_gid);
    }
    m.store.log("info", "adres yenilendi", &new_gid);
    Ok(json!({"ok":true,"gid":new_gid,"eski":old,"yeni":url,"degisen":changed}))
}

fn clear_auth(m: &Manager, gid: &str) -> Result<()> {
    let remaining = {
        let mut s = state(m)?;
        if !s.auth_required_gids.remove(gid) {
            return Ok(());
        }
        s.auth_required_gids.iter().cloned().collect::<Vec<_>>()
    };
    std::fs::write(
        m.data_dir.join("aria2.auth-required.json"),
        serde_json::to_vec(&remaining)?,
    )?;
    Ok(())
}

/// Acilis kurtarmasi: DB'de bitmemis (active/waiting/paused) http/torrent kaydinin gid'i aria2'de
/// yoksa ayni dir/out/secenekle yeniden eklenir. Oturum dosyasi bos kaldigi icin (--save-session-interval=0)
/// aria2 --continue=true ile .aria2 kontrol dosyasindan devam eder. Duraklatilmis kayit duraklatilmis eklenir.
/// Oturum bilgisi silinmis (auth_required) gid'ler atlanir; "Yenile" akisi onlari yeniden baslatir.
/// Cerezler yalniz bellekte tutulur; yeniden eklenen cerezli kayitlar 401/403 ile hata durumuna duser.
fn kesilenleri_kurtar(m: &Manager) -> Result<usize> {
    let mut motorda = HashSet::new();
    for liste in [
        m.rpc().tell_active(&[])?,
        m.rpc().tell_waiting(0, 1000, &[])?,
        m.rpc().tell_stopped(0, 1000, &[])?,
    ] {
        motorda.extend(liste.iter().map(|s| text(&s["gid"]).to_owned()));
    }
    let mut kurtarilan = 0;
    for row in m.store.list(None, 1000)? {
        let kind = text(&row["kind"]);
        let status = text(&row["status"]);
        let gid = text(&row["gid"]);
        let toplam = number(&row["total_bytes"]);
        let tamam = toplam > 0 && number(&row["done_bytes"]) >= toplam;
        if !["http", "torrent"].contains(&kind)
            || !["active", "waiting", "paused"].contains(&status)
            || gid.is_empty()
            || gid.starts_with("yt:")
            || gid.starts_with("row:")
            || tamam
            || motorda.contains(gid)
            || state(m)?.auth_required_gids.contains(gid)
        {
            continue;
        }
        let yeni = match launch(m, &row) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let yeni_gid = text(&yeni["gid"]).to_owned();
        if status == "paused" {
            m.rpc().pause(&yeni_gid, true)?;
            m.store
                .update_by_gid(&yeni_gid, &map(json!({"status":"paused"})))?;
        }
        m.store.log(
            "info",
            "kesilen indirme acilista yeniden baslatildi",
            &yeni_gid,
        );
        kurtarilan += 1;
    }
    Ok(kurtarilan)
}

/// Python _sync_aria2: persist engine progress without requiring a snapshot reader.
pub fn sync_aria2(m: &Manager) -> Result<()> {
    let completed = {
        let _guard = m
            .kilit
            .lock()
            .map_err(|_| AfuError::Other("yonetici kilidi kullanilamiyor".into()))?;
        // Uyuyan motoru uyandirmaz; kurtarma motor uyanikken ilk senkronda bir kez calisir.
        let kurtarma_bekliyor = !state(m)?.kurtarma_bitti;
        if kurtarma_bekliyor && !m.rpc().sleeping() && kesilenleri_kurtar(m).is_ok() {
            state(m)?.kurtarma_bitti = true;
        }
        sync::collect(m)?
    };
    sync::notify(m, completed);
    Ok(())
}

pub fn snapshot(m: &Manager) -> Result<Json> {
    shaping::snapshot(m)
}
pub fn servers(m: &Manager, gid: &str) -> Result<Vec<Json>> {
    if gid.starts_with("yt:") || gid.starts_with("row:") {
        return Ok(vec![]);
    }
    Ok(m.rpc().get_servers(gid).unwrap_or_default())
}

pub fn can_release_ui(m: &Manager) -> Result<bool> {
    if !m.rpc().sleeping() {
        return Ok(false);
    }
    if !state(m)?.preview_gids.is_empty() || crate::video::calisan_veya_bekleyen_var(m) {
        return Ok(false);
    }
    for status in [
        "active",
        "waiting",
        "queued",
        "scheduled",
        "repairing",
        "paused",
    ] {
        if !m.store.list(Some(status), 1)?.is_empty() {
            return Ok(false);
        }
    }
    for key in ["lan_erisimi", "sunucu_acik"] {
        if m.store.get(key)?.as_ref().is_some_and(truthy) {
            return Ok(false);
        }
    }
    Ok(!m
        .store
        .automation_jobs("", 10000)?
        .iter()
        .any(|j| ["queued", "running"].contains(&text(&j["status"]))))
}

pub fn notify_telegram(m: &Manager, message: &str) -> Result<bool> {
    let token = setting(
        m,
        "telegram_bot_token",
        json!(std::env::var("TELEGRAM_BOT_TOKEN").unwrap_or_default()),
    )?;
    let chat = setting(m, "telegram_chat_id", json!(""))?;
    if !truthy(&token) || !truthy(&chat) {
        return Ok(false);
    }
    let chat = chat
        .as_str()
        .map(str::to_owned)
        .unwrap_or_else(|| chat.to_string());
    let url = format!("https://api.telegram.org/bot{}/sendMessage", text(&token));
    let config = ureq::Agent::config_builder()
        .timeout_global(Some(std::time::Duration::from_secs(15)))
        .build();
    let agent: ureq::Agent = config.into();
    Ok(agent
        .post(&url)
        .send_form([
            ("chat_id", chat.as_str()),
            ("text", message),
            ("parse_mode", "HTML"),
        ])
        .is_ok_and(|r| r.status().as_u16() == 200))
}

/// Python human_size (manager.py): KB/MB birimleri, bir ondalik.
fn insan_boyut(bayt: f64) -> String {
    let mut n = bayt;
    for birim in ["B", "KB", "MB", "GB", "TB"] {
        if n.abs() < 1024.0 {
            return if birim == "B" {
                format!("{} B", n as i64)
            } else {
                format!("{n:.1} {birim}")
            };
        }
        n /= 1024.0;
    }
    format!("{n:.1} PB")
}

/// Python _on_complete(): bitmis indirme icin butunluk denetimi, Telegram, UI bildirimi ve
/// en sonda kabugun kancalari (otomasyon). Bozuk indirme kancalara gitmez.
pub(crate) fn tamamlandi(m: &Manager, title: &str, size: u64, gid: &str) {
    m.store.log(
        "info",
        &format!("tamamlandi: {title} ({})", insan_boyut(size as f64)),
        gid,
    );
    let bildirim = setting(m, "windows_notifications", json!(true))
        .map(|v| truthy(&v))
        .unwrap_or(true);
    let tara = crate::butunluk::butunluk_tara(m, gid).unwrap_or(Json::Null);
    if tara["ok"] == true && tara["durum"] == "bozuk" {
        m.store.log(
            "warn",
            &format!("Bozuk indi: {title} - {}", text(&tara["neden"])),
            gid,
        );
        if bildirim {
            m.ui.notify("AfuDM", "Bozuk indi: Yeniden indirmeniz gerekebilir.");
        }
        return;
    }
    if tara["ok"] == true && tara["durum"] == "saglam" {
        if let Ok(Some(dosya)) = resolve_item_path(m, gid) {
            crate::butunluk::artik_kontrol_dosyasini_sil(&dosya);
        }
    }
    let telegram = setting(m, "notify_telegram", json!(false))
        .map(|v| truthy(&v))
        .unwrap_or(false);
    if telegram {
        let dil = shaping::language(text(
            &setting(m, "language", json!("auto")).unwrap_or(json!("auto")),
        ));
        let baslik = if dil == "en" {
            "✅ AfuDM download finished"
        } else {
            "✅ AfuDM indirme tamamlandı"
        };
        let _ = notify_telegram(
            m,
            &format!("{baslik}\n{title}\n{}", insan_boyut(size as f64)),
        );
    }
    if bildirim {
        m.ui.notify("AfuDM", &format!("Indirme tamamlandi: {title}"));
    }
    let yuk = json!({"title": title, "size": size, "gid": gid});
    if let Ok(kancalar) = m.tamamlandi_kancalari.lock() {
        for kanca in kancalar.iter() {
            kanca(&yuk);
        }
    }
}

/// Python Manager.detect_kind (statik): torrent, video veya http.
pub fn detect_kind(source: &str) -> &'static str {
    dosya_adi::detect_kind(source)
}

/// Python Manager.is_supported_source (statik): motorun acabilecegi kaynak mi.
pub fn is_supported_source(source: &str) -> bool {
    dosya_adi::supported(source)
}

/// Python Manager.magnet_infohash (statik): magnet info hash (kucuk harf hex), yoksa bos.
pub fn magnet_infohash(source: &str) -> String {
    dosya_adi::magnet_hash(source)
}

/// Python Manager.guess_name (statik): kaynaktan guvenli dosya adi.
pub fn guess_name(source: &str) -> String {
    probe::guess_name(source)
}

/// Python Manager.clean_title (statik): "[METADATA]" ekini kaldirir.
pub fn clean_title(title: &str) -> String {
    probe::clean_title(title)
}

/// Python Manager.gecmis_sources: DB'deki tum kaynak adresleri (en fazla limit).
pub fn gecmis_sources(m: &Manager, limit: usize) -> Result<Vec<String>> {
    Ok(m.store
        .list(None, limit)?
        .iter()
        .map(|r| text(&r["source"]).to_string())
        .collect())
}

/// Python Manager.hiz_limiti_kb: aktif profile gore toplam hiz siniri (KB/s; 0 = sinirsiz).
pub fn hiz_limiti_kb(m: &Manager, ayarlar: Option<&JsonMap>) -> Result<i64> {
    let ayarlar = match ayarlar {
        Some(a) => a.clone(),
        None => m.store.all_settings()?,
    };
    Ok(settings::speed_limit(&ayarlar))
}

/// Python Manager.apply_settings: ayarlari aria2 global seceneklerine uygular.
pub fn apply_settings(m: &Manager) -> Result<()> {
    settings::apply(m)
}

/// Python probe_url_info: HEAD ve gerekirse 1 baytlik Range GET ile dosya adi, boyut, tur.
pub fn probe_url_info(_m: &Manager, url: &str) -> Result<Json> {
    probe::probe_url_info(url)
}
