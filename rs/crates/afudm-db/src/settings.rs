//! Python defaults and atomic field validation; errors carry unchanged i18n keys.
use afudm_types::{AfuError, Json, JsonMap, Result};
use serde_json::json;

pub fn default_settings() -> JsonMap {
    // Literal generated from db.py DEFAULTS, without importing or running Python.
    match json!({"language": "auto", "download_dir": "", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "max_upload_kb": 100, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": true, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": true, "telegram_bot_token": "", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": true, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": true, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": true, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 6821, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false})
    {
        Json::Object(map) => map,
        _ => JsonMap::new(),
    }
}
pub(crate) fn py_string(v: &Json) -> String {
    match v {
        Json::String(s) => s.clone(),
        Json::Null => "None".into(),
        Json::Bool(b) => if *b { "True" } else { "False" }.into(),
        _ => v.to_string(),
    }
}
pub(crate) fn python_int(v: &Json) -> Option<i64> {
    match v {
        Json::Number(n) => n.as_i64().or_else(|| {
            n.as_f64()
                .filter(|v| v.fract() == 0.0 && *v >= i64::MIN as f64 && *v < i64::MAX as f64)
                .map(|n| n as i64)
        }),
        Json::String(s) => {
            let s = s.trim();
            let digits = s.strip_prefix(['+', '-']).unwrap_or(s);
            if !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit()) {
                s.parse().ok()
            } else {
                None
            }
        }
        _ => None,
    }
}
fn fail(key: &str) -> AfuError {
    AfuError::Invalid(key.into())
}
fn proxy_parts(raw: &str) -> Result<(String, String)> {
    let (scheme, host) = match raw.split_once("://") {
        Some((s, h)) => (s.trim().to_lowercase(), h),
        None => ("http".into(), raw),
    };
    if !["http", "https", "socks5", "socks5h", "socks4"].contains(&scheme.as_str()) {
        return Err(fail("err.proxyScheme"));
    }
    let address = host.rsplit('@').next().unwrap_or("").trim();
    let (hostname, port) = address
        .split_once(':')
        .ok_or_else(|| fail("err.proxyFormat"))?;
    if hostname.is_empty()
        || hostname
            .chars()
            .any(|c| c.is_whitespace() || ":/@".contains(c))
        || port.is_empty()
        || !port.bytes().all(|b| b.is_ascii_digit())
    {
        return Err(fail("err.proxyFormat"));
    }
    if !port
        .parse::<u32>()
        .ok()
        .is_some_and(|p| (1..=65535).contains(&p))
    {
        return Err(fail("err.proxyPort"));
    }
    Ok((scheme, address.into()))
}
pub fn proxy_maskele(proxy: &Json) -> String {
    let raw = if crate::store::truthy(proxy) {
        py_string(proxy)
    } else {
        String::new()
    };
    let raw = raw.trim();
    if raw.is_empty() {
        return String::new();
    }
    proxy_parts(raw)
        .map(|(s, h)| format!("{s}://{h}"))
        .unwrap_or_else(|_| "<proxy>".into())
}
fn string_or_empty(v: &Json) -> String {
    if crate::store::truthy(v) {
        py_string(v)
    } else {
        String::new()
    }
}
fn normalize(key: &str, v: &Json) -> Result<Json> {
    match key {
        "api_port" | "api_listen_port" | "snail_speed_kb" | "max_concurrent" | "max_upload_kb" => {
            let (lo, hi, error) = match key {
                "snail_speed_kb" => (1, 1_000_000, "err.snailRange"),
                "max_concurrent" => (1, 20, "err.invalidValue"),
                "max_upload_kb" => (0, 1_000_000, "err.invalidValue"),
                _ => (1024, 65535, "err.portRange"),
            };
            let n = python_int(v)
                .filter(|n| (lo..=hi).contains(n))
                .ok_or_else(|| fail(error))?;
            Ok(json!(n))
        }
        "proxy" => {
            let raw = string_or_empty(v);
            let raw = raw.trim();
            if raw.chars().count() > 1024 {
                return Err(fail("err.proxyLong"));
            }
            if !raw.is_empty() {
                proxy_parts(raw)?;
            }
            Ok(json!(raw))
        }
        "clipboard_exts" => {
            let raw = match v.as_array() {
                Some(a) => a.iter().map(py_string).collect::<Vec<_>>().join(","),
                None => string_or_empty(v),
            };
            let mut out: Vec<String> = vec![];
            for p in raw
                .split(|c: char| c == ',' || c == ';' || c.is_whitespace())
                .filter(|s| !s.is_empty())
            {
                if p.contains(['*', '?', '/', '\\', ':']) {
                    return Err(fail("err.extWildcard"));
                }
                let e = p.to_lowercase();
                let e = e.trim_start_matches('.');
                if e.is_empty()
                    || e.len() > 24
                    || !e.as_bytes()[0].is_ascii_alphanumeric()
                    || !e.bytes().all(|b| {
                        b.is_ascii_lowercase() || b.is_ascii_digit() || b"._+-".contains(&b)
                    })
                {
                    return Err(fail("err.extInvalid"));
                }
                if !out.iter().any(|s| s == e) {
                    out.push(e.into())
                }
            }
            Ok(json!(out.join(",")))
        }
        "ag_konumlari" => {
            let rows = match v.as_array() {
                Some(a) => a.iter().map(py_string).collect::<Vec<_>>(),
                None => string_or_empty(v).lines().map(str::to_owned).collect(),
            };
            let mut out: Vec<String> = vec![];
            for row in rows {
                let path = row.trim().replace('/', "\\");
                let path = path.trim_end_matches('\\');
                if path.is_empty() {
                    continue;
                }
                let body = path
                    .strip_prefix("\\\\")
                    .ok_or_else(|| fail("err.netPathFormat"))?;
                let parts: Vec<_> = body.split('\\').collect();
                if parts.len() < 2
                    || parts
                        .iter()
                        .any(|s| s.is_empty() || s.contains(['*', '?', '<', '>', '|', '"']))
                {
                    return Err(fail("err.netPathFormat"));
                }
                if !out.iter().any(|s| s.to_lowercase() == path.to_lowercase()) {
                    out.push(path.into())
                }
            }
            Ok(json!(out.join("\n")))
        }
        _ => Ok(v.clone()),
    }
}
/// Returns only normalized changes (current values are not rewritten).
/// As in Python, every invalid field is collected before returning an error.
pub fn validate(changes: &JsonMap, _current: &JsonMap) -> Result<JsonMap> {
    let mut clean = JsonMap::new();
    let mut errors = Vec::new();
    for (k, v) in changes {
        match normalize(k, v) {
            Ok(v) => {
                clean.insert(k.clone(), v);
            }
            Err(e) => errors.push(json!({"alan":k,"mesaj_anahtari":e.to_string()})),
        }
    }
    if !errors.is_empty() {
        return Err(AfuError::Invalid(json!(errors).to_string()));
    }
    Ok(clean)
}
