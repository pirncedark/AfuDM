use crate::text;
use afudm_types::{AfuError, Json, JsonMap, Result};
use chrono::{Local, NaiveDateTime, NaiveTime, TimeZone};
pub(crate) fn truthy(v: &Json) -> bool {
    match v {
        Json::Null => false,
        Json::Bool(v) => *v,
        Json::String(v) => !v.is_empty(),
        Json::Array(v) => !v.is_empty(),
        Json::Object(v) => !v.is_empty(),
        Json::Number(v) => v.as_f64() != Some(0.0),
    }
}
pub(crate) fn boolean(data: &JsonMap, key: &str) -> Result<bool> {
    match data.get(key) {
        None | Some(Json::Null) => Ok(false),
        Some(Json::Bool(v)) => Ok(*v),
        Some(Json::String(v)) => match v.trim().to_lowercase().as_str() {
            "true" | "1" => Ok(true),
            "false" | "0" | "" | "no" => Ok(false),
            _ => Err(AfuError::Invalid(format!(
                "{key} boolean olmali (true/false/1/0)"
            ))),
        },
        _ => Err(AfuError::Invalid(format!(
            "{key} boolean olmali (true/false/1/0)"
        ))),
    }
}
fn bad(message: impl Into<String>) -> AfuError {
    AfuError::Invalid(message.into())
}
fn time_spec(value: &Json) -> Result<Json> {
    let raw = match value {
        Json::String(v) => v.clone(),
        _ => value.to_string(),
    };
    let s = raw.trim();
    if s.is_empty() {
        return Ok(Json::Null);
    }
    if s.chars().all(|c| c.is_ascii_digit()) {
        if let Ok(n) = s.parse::<f64>() {
            return Ok(serde_json::json!(n));
        }
    }
    for format in ["%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"] {
        if let Ok(dt) = NaiveDateTime::parse_from_str(s, format) {
            if let Some(dt) = Local.from_local_datetime(&dt).earliest() {
                return Ok(serde_json::json!(dt.timestamp() as f64));
            }
        }
    }
    if let Ok(t) = NaiveTime::parse_from_str(s, "%H:%M") {
        let now = Local::now();
        if let Some(dt) = Local
            .from_local_datetime(&now.date_naive().and_time(t))
            .earliest()
        {
            let mut stamp = dt.timestamp();
            if stamp <= now.timestamp() {
                stamp += 86400
            }
            return Ok(serde_json::json!(stamp as f64));
        }
    }
    Err(bad(format!(
        "zamanlama anlasilamadi: {s:?} ('23:30' veya 'YYYY-AA-GG SS:DD')"
    )))
}
pub(crate) fn normalize(mut data: JsonMap) -> Result<JsonMap> {
    let url = if text(&data, "url").is_empty() {
        text(&data, "source")
    } else {
        text(&data, "url")
    }
    .trim()
    .to_string();
    if url.is_empty() {
        return Err(bad("bos link"));
    }
    if url.chars().count() > 8192 {
        return Err(bad("baglanti cok uzun (>8192)"));
    }
    data.insert("source".into(), Json::String(url));
    data.remove("url");
    for key in [
        "audio_only",
        "playlist",
        "oto_altyazi",
        "altyazi_goem",
        "ustveri_goem",
    ] {
        let b = boolean(&data, key)?;
        data.insert(key.into(), Json::Bool(b));
    }
    if !data.get("headers").is_some_and(truthy) {
        data.insert("headers".into(), serde_json::json!({}));
    }
    let Some(headers) = data.get("headers").and_then(Json::as_object) else {
        return Err(bad("headers sozluk olmali"));
    };
    if headers.len() > 40 {
        return Err(bad("en fazla 40 ozel baslik"));
    }
    for (key, max) in [("title", 200), ("user_agent", 512)] {
        if let Some(Json::String(v)) = data.get(key) {
            let normalized = v
                .split_whitespace()
                .collect::<Vec<_>>()
                .join(" ")
                .chars()
                .take(max)
                .collect::<String>();
            data.insert(key.into(), Json::String(normalized));
        }
    }
    if let Some(v) = data.get("proxy").filter(|v| !v.is_null()) {
        let Some(v) = v.as_str() else {
            return Err(bad("proxy metin olmali"));
        };
        let v = v.trim();
        if v.chars().count() > 1024 {
            return Err(bad("proxy adresi cok uzun (> 1024)"));
        }
        let v = if v.is_empty() {
            Json::Null
        } else {
            Json::String(v.into())
        };
        data.insert("proxy".into(), v);
    }
    for (key, max) in [
        ("altyazi_diller", 200),
        ("sponsorblock", 200),
        ("bolum_araligi", 64),
        ("dosya_sablonu", 1000),
        ("kapsayici", 32),
        ("ses_formati", 32),
        ("tarayici_cerezi", 128),
    ] {
        let v = match data.get(key) {
            None | Some(Json::Null) => "".into(),
            Some(Json::String(v)) => v.split_whitespace().collect::<Vec<_>>().join(" "),
            _ => return Err(bad(format!("{key} metin olmali"))),
        };
        if v.chars().count() > max {
            return Err(bad(format!("{key} cok uzun (>{max} karakter)")));
        }
        data.insert(key.into(), Json::String(v));
    }
    for (key, choices) in [
        ("kucuk_resim", &["goem", "dosya"][..]),
        ("bolumler", &["goem", "ayir"][..]),
        ("kapsayici", &["mp4", "mkv", "webm"][..]),
        (
            "ses_formati",
            &["mp3", "m4a", "aac", "opus", "flac", "wav"][..],
        ),
        (
            "tarayici_cerezi",
            &[
                "chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi", "safari",
            ][..],
        ),
    ] {
        if data
            .get(key)
            .is_some_and(|v| !v.is_null() && !v.is_string())
        {
            return Err(bad(format!("{key} metin olmali")));
        }
        let v = text(&data, key).trim().to_lowercase();
        if !v.is_empty() && !choices.contains(&v.as_str()) {
            return Err(bad(format!(
                "{key} su degerlerden biri olmali: {}",
                choices.join(", ")
            )));
        }
        data.insert(key.into(), Json::String(v));
    }
    let sponsor = text(&data, "sponsorblock");
    if !sponsor.is_empty()
        && sponsor
            .split(',')
            .any(|v| v.is_empty() || !v.chars().all(|c| c.is_ascii_alphanumeric() || c == '_'))
    {
        return Err(bad("sponsorblock bicimi gecersiz (kategori listesi)"));
    }
    let interval = text(&data, "bolum_araligi");
    if !interval.is_empty() {
        let parts = interval.split('-').collect::<Vec<_>>();
        if parts.len() != 2
            || parts.iter().any(|part| {
                let t = part.split(':').collect::<Vec<_>>();
                !(t.len() == 2 || t.len() == 3)
                    || t.iter()
                        .any(|s| s.len() != 2 || !s.bytes().all(|b| b.is_ascii_digit()))
            })
        {
            return Err(bad(
                "bolum_araligi bicimi gecersiz (SS:DD:SS-SS:DD:SS veya DD:SS-DD:SS)",
            ));
        }
    }
    if let Some(v) = data
        .get("checksum")
        .filter(|v| !v.is_null() && **v != Json::String(String::new()))
    {
        let raw = if let Some(s) = v.as_str() {
            s.to_owned()
        } else {
            v.to_string()
        };
        let raw = raw.trim();
        let Some((kind, hex)) = raw.split_once([':', '=']) else {
            return Err(bad(
                "checksum 'tip:hex' biciminde olmali (orn. sha-256:...)",
            ));
        };
        if hex.is_empty() || !hex.bytes().all(|c| c.is_ascii_hexdigit()) {
            return Err(bad(
                "checksum 'tip:hex' biciminde olmali (orn. sha-256:...)",
            ));
        }
        let kind = kind.to_lowercase();
        let normalized = match kind.as_str() {
            "md5" => "md5",
            "sha1" | "sha-1" => "sha-1",
            "sha-224" => "sha-224",
            "sha256" | "sha-256" => "sha-256",
            "sha-384" => "sha-384",
            "sha512" | "sha-512" => "sha-512",
            _ => {
                return Err(bad(format!(
                    "checksum tipi desteklenmiyor: {kind} (md5 | sha-1 | sha-256 | sha-512)"
                )))
            }
        };
        data.insert(
            "checksum".into(),
            Json::String(format!("{normalized}={}", hex.to_lowercase())),
        );
    }
    if let Some(v) = data
        .get("start_at")
        .filter(|v| !v.is_null() && **v != Json::String(String::new()))
    {
        let v = time_spec(v)?;
        data.insert("start_after".into(), v);
    }
    // HTTP Python mapping intentionally drops fields accepted only by the desktop bridge.
    for key in [
        "interactive",
        "prompt_source",
        "kategori",
        "adopt_gid",
        "selected_files",
        "start_at",
    ] {
        data.remove(key);
    }
    Ok(data)
}
