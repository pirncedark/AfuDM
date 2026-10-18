use super::*;

pub(super) fn speed_limit(settings: &JsonMap) -> i64 {
    let profile = settings
        .get("hiz_profili")
        .and_then(Json::as_str)
        .unwrap_or("normal")
        .trim()
        .to_lowercase();
    match profile.as_str() {
        "turbo" => 0,
        "snail" => number(
            settings
                .get("snail_speed_kb")
                .filter(|v| truthy(v))
                .unwrap_or(&json!(100)),
        )
        .max(0),
        _ => number(settings.get("max_speed_kb").unwrap_or(&Json::Null)).max(0),
    }
}

pub(super) fn apply(m: &Manager) -> Result<()> {
    let settings = m.store.all_settings()?;
    let limit = speed_limit(&settings);
    let upload = number(settings.get("max_upload_kb").unwrap_or(&json!(100))).max(0);
    let seed = settings
        .get("seed_ratio")
        .and_then(|v| {
            v.as_f64()
                .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
        })
        .unwrap_or(1.0);
    let options = map(
        json!({"max-concurrent-downloads":number(settings.get("max_concurrent").unwrap_or(&json!(5))).to_string(),"split":number(settings.get("split").unwrap_or(&json!(64))).to_string(),"max-connection-per-server":number(settings.get("max_conn_per_server").unwrap_or(&json!(16))).to_string(),"max-overall-download-limit":if limit>0{format!("{limit}K")}else{"0".into()},"max-overall-upload-limit":if upload>0{format!("{upload}K")}else{"0".into()},"seed-ratio":format!("{seed:?}")}),
    );
    if m.rpc().change_global_option(&options).is_err() {
        state(m)?.last_error = "motor ayarlari uygulanamadi".into();
    }
    Ok(())
}

fn integer(value: &Json) -> Option<i64> {
    if value.is_boolean() {
        return None;
    }
    value
        .as_i64()
        .or_else(|| {
            value
                .as_f64()
                .filter(|v| v.is_finite() && v.fract() == 0.0)
                .map(|v| v as i64)
        })
        .or_else(|| value.as_str().and_then(|s| s.trim().parse().ok()))
}

fn proxy_validate(raw: &str) -> std::result::Result<(), &'static str> {
    if raw.is_empty() {
        return Ok(());
    }
    if raw.chars().count() > 1024 {
        return Err("err.proxyLong");
    }
    let (scheme, rest) = raw.split_once("://").unwrap_or(("http", raw));
    if !["http", "https", "socks5", "socks5h", "socks4"]
        .contains(&scheme.trim().to_lowercase().as_str())
    {
        return Err("err.proxyScheme");
    }
    let host = rest.rsplit('@').next().unwrap_or("").trim();
    let Some((host, port)) = host.rsplit_once(':') else {
        return Err("err.proxyFormat");
    };
    if host.is_empty()
        || host.contains([':', '/', '@'])
        || host.chars().any(char::is_whitespace)
        || port.is_empty()
        || !port.chars().all(|c| c.is_ascii_digit())
    {
        return Err("err.proxyFormat");
    }
    if !port.parse::<u32>().is_ok_and(|p| (1..=65535).contains(&p)) {
        return Err("err.proxyPort");
    }
    Ok(())
}

fn normalize(key: &str, value: &Json) -> std::result::Result<Json, &'static str> {
    let range = match key {
        "api_port" | "api_listen_port" => Some((1024, 65535, "err.portRange")),
        "snail_speed_kb" => Some((1, 1000000, "err.snailRange")),
        "max_concurrent" => Some((1, 20, "err.invalidValue")),
        "max_upload_kb" => Some((0, 1_000_000, "err.invalidValue")),
        _ => None,
    };
    if let Some((min, max, error)) = range {
        return integer(value)
            .filter(|n| (min..=max).contains(n))
            .map(|n| json!(n))
            .ok_or(error);
    }
    let raw = if let Some(s) = value.as_str() {
        s.to_owned()
    } else if let Some(a) = value.as_array() {
        a.iter()
            .map(|v| {
                v.as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| v.to_string())
            })
            .collect::<Vec<_>>()
            .join(if key == "ag_konumlari" { "\n" } else { "," })
    } else if truthy(value) {
        value.to_string()
    } else {
        String::new()
    };
    match key {
        "proxy" => {
            let raw = raw.trim();
            proxy_validate(raw)?;
            Ok(json!(raw))
        }
        "clipboard_exts" => {
            let mut out = Vec::new();
            for ext in raw
                .split(|c: char| c.is_whitespace() || c == ',' || c == ';')
                .filter(|s| !s.is_empty())
            {
                if ext.contains(['*', '?', '/', '\\', ':']) {
                    return Err("err.extWildcard");
                }
                let ext = ext.to_lowercase();
                let ext = ext.trim_start_matches('.');
                if ext.is_empty()
                    || ext.len() > 24
                    || !ext.starts_with(|c: char| c.is_ascii_alphanumeric())
                    || !ext
                        .chars()
                        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || "._+-".contains(c))
                {
                    return Err("err.extInvalid");
                }
                if !out.contains(&ext.to_owned()) {
                    out.push(ext.to_owned());
                }
            }
            Ok(json!(out.join(",")))
        }
        "ag_konumlari" => {
            let mut out = Vec::new();
            let mut seen = HashSet::new();
            for line in raw.lines() {
                let line = line
                    .trim()
                    .replace('/', "\\")
                    .trim_end_matches('\\')
                    .to_owned();
                if line.is_empty() {
                    continue;
                }
                let Some(body) = line.strip_prefix("\\\\") else {
                    return Err("err.netPathFormat");
                };
                let parts: Vec<_> = body.split('\\').collect();
                if parts.len() < 2
                    || parts
                        .iter()
                        .any(|p| p.is_empty() || p.contains(['*', '?', '<', '>', '|', '"']))
                {
                    return Err("err.netPathFormat");
                }
                if seen.insert(line.to_lowercase()) {
                    out.push(line);
                }
            }
            Ok(json!(out.join("\n")))
        }
        _ => Ok(value.clone()),
    }
}

pub(super) fn update(m: &Manager, changes: &JsonMap) -> Result<Json> {
    let mut clean = JsonMap::new();
    let mut errors = Vec::new();
    for (key, value) in changes {
        match normalize(key, value) {
            Ok(v) => {
                clean.insert(key.clone(), v);
            }
            Err(e) => errors.push(json!({"alan":key,"mesaj_anahtari":e})),
        }
    }
    state(m)?.settings_errors = errors.clone();
    if !errors.is_empty() {
        return Err(invalid("settings_invalid"));
    }
    let old_snail = number(&setting(m, "snail_speed_kb", json!(100))?);
    for (key, value) in &clean {
        m.store.set(key, value.clone())?;
    }
    if let Some(speed) = clean.get("snail_speed_kb") {
        if text(&setting(m, "hiz_profili", json!("normal"))?)
            .trim()
            .eq_ignore_ascii_case("snail")
            && number(speed) != old_snail
        {
            m.store.log(
                "info",
                &format!("salyangoz hizi canli uygulandi: {} KB/s", number(speed)),
                "",
            );
        }
    }
    if clean.contains_key("download_dir") {
        let dir = current_download_dir(m)?;
        std::fs::create_dir_all(&dir)?;
        if m.rpc()
            .change_global_option(&map(json!({"dir":dir})))
            .is_err()
        {
            m.store
                .log("warn", "genel indirme klasoru uygulanamadi", "");
        }
    }
    apply(m)?;
    Ok(json!(m.store.all_settings()?))
}
