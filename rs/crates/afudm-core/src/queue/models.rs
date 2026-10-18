//! Python core/models.py request validation. Cookies remain outside persisted options.
use super::{invalid, number, text, truthy};
use afudm_types::{Json, JsonMap, Result};
use chrono::{Local, NaiveDateTime, NaiveTime, TimeZone};
use regex::Regex;
use serde_json::json;

pub(super) fn parse_time(value: &Json) -> Result<Option<f64>> {
    let raw = if let Some(s) = value.as_str() {
        s.trim().to_owned()
    } else if value.is_null() {
        String::new()
    } else {
        value.to_string()
    };
    if raw.is_empty() {
        return Ok(None);
    }
    if raw.chars().all(|c| c.is_ascii_digit()) {
        return Ok(raw.parse().ok());
    }
    for fmt in ["%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"] {
        if let Ok(dt) = NaiveDateTime::parse_from_str(&raw, fmt) {
            if let Some(dt) = Local.from_local_datetime(&dt).earliest() {
                return Ok(Some(dt.timestamp() as f64));
            }
        }
    }
    if let Ok(t) = NaiveTime::parse_from_str(&raw, "%H:%M") {
        let now = Local::now();
        if let Some(dt) = Local
            .from_local_datetime(&now.date_naive().and_time(t))
            .earliest()
        {
            let ts = dt.timestamp() as f64;
            return Ok(Some(if ts <= now.timestamp() as f64 {
                ts + 86400.0
            } else {
                ts
            }));
        }
    }
    Err(invalid(format!(
        "zamanlama anlasilamadi: {raw:?} ('23:30' veya 'YYYY-AA-GG SS:DD')"
    )))
}

fn string_field(data: &JsonMap, key: &str, max: usize) -> Result<String> {
    let Some(value) = data.get(key).filter(|v| !v.is_null() && **v != json!("")) else {
        return Ok(String::new());
    };
    let s = value
        .as_str()
        .ok_or_else(|| invalid(format!("{key} metin olmali")))?;
    let s = s.split_whitespace().collect::<Vec<_>>().join(" ");
    if s.chars().count() > max {
        return Err(invalid(format!("{key} cok uzun (>{max} karakter)")));
    }
    Ok(s)
}

pub(super) fn normalize(data: &JsonMap) -> Result<JsonMap> {
    let source = data
        .get("source")
        .filter(|v| truthy(v))
        .or_else(|| data.get("url"));
    let source = source.and_then(Json::as_str).unwrap_or("").trim();
    if source.is_empty() {
        return Err(invalid("bos link"));
    }
    if source.chars().count() > 8192 {
        return Err(invalid("baglanti cok uzun (>8192)"));
    }
    let mut req = data.clone();
    req.insert("source".into(), json!(source));
    let headers = data
        .get("headers")
        .filter(|v| !v.is_null())
        .cloned()
        .unwrap_or(json!({}));
    let h = headers
        .as_object()
        .ok_or_else(|| invalid("headers sozluk olmali"))?;
    if h.len() > 40 {
        return Err(invalid("en fazla 40 ozel baslik"));
    }
    req.insert("headers".into(), headers);
    for (key, max) in [("title", 200), ("user_agent", 512)] {
        if let Some(s) = data.get(key).and_then(Json::as_str) {
            req.insert(
                key.into(),
                json!(s
                    .split_whitespace()
                    .collect::<Vec<_>>()
                    .join(" ")
                    .chars()
                    .take(max)
                    .collect::<String>()),
            );
        }
    }
    if let Some(px) = data.get("proxy").filter(|v| !v.is_null()) {
        let px = px
            .as_str()
            .ok_or_else(|| invalid("proxy metin olmali"))?
            .trim();
        if px.chars().count() > 1024 {
            return Err(invalid("proxy adresi cok uzun (> 1024)"));
        }
        req.insert(
            "proxy".into(),
            if px.is_empty() { Json::Null } else { json!(px) },
        );
    }
    if let Some(check) = data
        .get("checksum")
        .filter(|v| !v.is_null() && **v != json!(""))
    {
        let check = text(check).trim().to_owned();
        let (kind, hex) = check
            .split_once([':', '='])
            .ok_or_else(|| invalid("checksum 'tip:hex' biciminde olmali (orn. sha-256:...)"))?;
        if kind.is_empty()
            || !kind.chars().all(|c| c.is_ascii_alphanumeric() || c == '-')
            || hex.is_empty()
            || !hex.chars().all(|c| c.is_ascii_hexdigit())
        {
            return Err(invalid(
                "checksum 'tip:hex' biciminde olmali (orn. sha-256:...)",
            ));
        }
        let lower = kind.to_lowercase();
        let kind = match lower.as_str() {
            "sha1" => "sha-1",
            "sha256" => "sha-256",
            "sha512" => "sha-512",
            "md5" | "sha-1" | "sha-224" | "sha-256" | "sha-384" | "sha-512" => lower.as_str(),
            _ => {
                return Err(invalid(format!(
                    "checksum tipi desteklenmiyor: {kind} (md5 | sha-1 | sha-256 | sha-512)"
                )))
            }
        };
        req.insert(
            "checksum".into(),
            json!(format!("{kind}={}", hex.to_lowercase())),
        );
    }
    if data.get("start_after").is_none_or(Json::is_null) {
        if let Some(value) = data.get("start_at").filter(|v| truthy(v)) {
            req.insert("start_after".into(), json!(parse_time(value)?));
        }
    } else if let Some(v) = data.get("start_after") {
        if !v.is_number() {
            return Err(invalid("start_after sayi olmali"));
        }
    }
    for (key, max) in [
        ("altyazi_diller", 200),
        ("sponsorblock", 200),
        ("bolum_araligi", 64),
        ("dosya_sablonu", 1000),
    ] {
        req.insert(key.into(), json!(string_field(data, key, max)?));
    }
    for (key, values, max) in [
        ("kucuk_resim", &["goem", "dosya"][..], usize::MAX),
        ("bolumler", &["goem", "ayir"][..], usize::MAX),
        ("kapsayici", &["mp4", "mkv", "webm"][..], 32),
        (
            "ses_formati",
            &["mp3", "m4a", "aac", "opus", "flac", "wav"][..],
            32,
        ),
        (
            "tarayici_cerezi",
            &[
                "chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi", "safari",
            ][..],
            128,
        ),
    ] {
        let s = string_field(data, key, max)?.to_lowercase();
        if !s.is_empty() && !values.contains(&s.as_str()) {
            return Err(invalid(format!(
                "{key} su degerlerden biri olmali: {}",
                values.join(", ")
            )));
        }
        req.insert(key.into(), json!(s));
    }
    for (key, pattern, format) in [
        (
            "sponsorblock",
            r"^[A-Za-z0-9_]+(?:,[A-Za-z0-9_]+)*$",
            "kategori listesi",
        ),
        (
            "bolum_araligi",
            r"^(?:\d{2}:\d{2}:\d{2}|\d{2}:\d{2})-(?:\d{2}:\d{2}:\d{2}|\d{2}:\d{2})$",
            "SS:DD:SS-SS:DD:SS veya DD:SS-DD:SS",
        ),
    ] {
        let s = req.get(key).and_then(Json::as_str).unwrap_or("");
        if !s.is_empty()
            && !Regex::new(pattern)
                .map_err(|e| invalid(e.to_string()))?
                .is_match(s)
        {
            return Err(invalid(format!("{key} {format} biciminde olmali")));
        }
    }
    for key in [
        "audio_only",
        "playlist",
        "oto_altyazi",
        "altyazi_goem",
        "ustveri_goem",
    ] {
        req.insert(key.into(), json!(data.get(key).is_some_and(truthy)));
    }
    Ok(req)
}

pub(super) fn cookies(raw: Option<&Json>) -> Vec<Json> {
    let Some(raw) = raw.and_then(Json::as_array) else {
        return vec![];
    };
    let mut total = 0;
    let mut out = Vec::new();
    for c in raw.iter().take(300) {
        let (Some(name), Some(value), Some(domain)) = (
            c.get("name").and_then(Json::as_str),
            c.get("value").map(|v| v.as_str()).unwrap_or(Some("")),
            c.get("domain").and_then(Json::as_str),
        ) else {
            continue;
        };
        if name.is_empty()
            || name.contains([';', '=', ' '])
            || value.contains(';')
            || domain.is_empty()
            || domain.contains([';', ' '])
            || [name, value, domain]
                .iter()
                .any(|s| s.contains(['\r', '\n', '\t', '\0']))
        {
            continue;
        }
        total += name.chars().count() + value.chars().count();
        if total > 32768 {
            break;
        }
        let path = c
            .get("path")
            .and_then(Json::as_str)
            .filter(|s| s.starts_with('/') && !s.contains(['\r', '\n', '\t', '\0', ';']))
            .unwrap_or("/");
        out.push(json!({"name":name,"value":value,"domain":domain,"path":path,"secure":c.get("secure").is_some_and(truthy),"hostOnly":c.get("hostOnly").map(truthy).unwrap_or(!domain.starts_with('.')),"expirationDate":number(&c["expirationDate"]).max(0)}));
    }
    out
}
