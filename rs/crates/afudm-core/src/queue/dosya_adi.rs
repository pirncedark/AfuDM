//! The filename operations used by Manager.add (no network probing).
use url::Url;

pub(super) fn decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let Ok(hex) = std::str::from_utf8(&bytes[i + 1..i + 3]) {
                if let Ok(b) = u8::from_str_radix(hex, 16) {
                    out.push(b);
                    i += 3;
                    continue;
                }
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

pub(super) fn safe(name: &str) -> String {
    let s: String = name
        .chars()
        .map(|c| {
            if c < ' ' || "<>:\"/\\|?*".contains(c) {
                '_'
            } else {
                c
            }
        })
        .collect();
    let mut s = s
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim_end_matches(['.', ' '])
        .to_owned();
    let stem = s.split('.').next().unwrap_or("").trim_end().to_uppercase();
    if ["CON", "PRN", "AUX", "NUL"].contains(&stem.as_str())
        || (stem.len() == 4
            && (stem.starts_with("COM") || stem.starts_with("LPT"))
            && stem.as_bytes()[3].is_ascii_digit()
            && stem.as_bytes()[3] != b'0')
    {
        s.insert(0, '_');
    }
    if s.chars().count() > 200 {
        if let Some((base, ext)) = s.rsplit_once('.').filter(|(base, ext)| {
            !base.is_empty()
                && !ext.is_empty()
                && ext.chars().count() <= 8
                && ext.chars().all(char::is_alphanumeric)
                && !ext.chars().all(char::is_numeric)
        }) {
            s = format!(
                "{}.{}",
                base.chars()
                    .take(199 - ext.chars().count())
                    .collect::<String>()
                    .trim_end(),
                ext
            );
        } else {
            s = s
                .chars()
                .take(200)
                .collect::<String>()
                .trim_end_matches(['.', ' '])
                .to_owned();
        }
    }
    s
}

pub(super) fn guess(source: &str) -> String {
    if source.to_lowercase().starts_with("magnet:") {
        return Url::parse(source)
            .ok()
            .and_then(|u| {
                u.query_pairs()
                    .find(|(k, _)| k == "dn")
                    .map(|(_, v)| safe(&v))
            })
            .filter(|s| !s.is_empty())
            .unwrap_or("magnet baglantisi".into());
    }
    let path = Url::parse(source)
        .map(|u| u.path().to_owned())
        .unwrap_or_else(|_| source.split(['?', '#']).next().unwrap_or(source).to_owned());
    let name = safe(&decode(
        path.rsplit('/').find(|s| !s.is_empty()).unwrap_or(""),
    ));
    if name.is_empty() {
        "download".into()
    } else {
        name
    }
}

pub(super) fn magnet_hash(source: &str) -> String {
    if !source.to_lowercase().starts_with("magnet:") {
        return String::new();
    }
    Url::parse(source)
        .ok()
        .and_then(|u| {
            u.query_pairs()
                .filter(|(k, _)| k == "xt")
                .map(|(_, v)| v.into_owned())
                .find(|v| v.to_lowercase().starts_with("urn:btih:"))
        })
        .map(|v| {
            let raw = v.rsplit(':').next().unwrap_or("").trim();
            if raw.len() == 32 {
                if let Ok(bytes) = data_encoding::BASE32.decode(raw.to_uppercase().as_bytes()) {
                    return bytes.iter().map(|b| format!("{b:02x}")).collect();
                }
            }
            raw.to_lowercase()
        })
        .unwrap_or_default()
}

pub(super) fn url_key(source: &str) -> String {
    // Keep path/query/userinfo byte-for-byte, only scheme/host and fragment change.
    let Some((scheme, tail)) = source.split_once("://") else {
        return source.into();
    };
    if !["http", "https", "ftp"].contains(&scheme.to_lowercase().as_str()) {
        return source.into();
    }
    let tail = tail.split('#').next().unwrap_or(tail);
    let end = tail.find(['/', '?']).unwrap_or(tail.len());
    let authority = &tail[..end];
    let authority = if let Some((user, host)) = authority.rsplit_once('@') {
        format!("{user}@{}", host.to_lowercase())
    } else {
        authority.to_lowercase()
    };
    let rest = &tail[end..];
    format!(
        "{}://{}{}{}",
        scheme.to_lowercase(),
        authority,
        if rest.starts_with('/') { "" } else { "/" },
        rest
    )
}

pub(super) fn detect_kind(source: &str) -> &'static str {
    let lower = source.to_lowercase();
    let path = lower.split('?').next().unwrap_or(&lower);
    if lower.starts_with("magnet:") || path.ends_with(".torrent") {
        return "torrent";
    }
    if [
        ".zip", ".rar", ".7z", ".exe", ".msi", ".iso", ".pdf", ".apk", ".dmg", ".tar", ".gz",
        ".deb", ".rpm", ".img",
    ]
    .iter()
    .any(|e| path.ends_with(e))
    {
        return "http";
    }
    if [
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "tiktok.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "vimeo.com",
        "dailymotion.com",
        "twitch.tv",
        "reddit.com",
        "soundcloud.com",
        "bilibili.com",
        "odnoklassniki",
        "vk.com",
        "pinterest.com",
        "linkedin.com",
        "threads.net",
        "rumble.com",
        ".m3u8",
        ".mpd",
    ]
    .iter()
    .any(|h| path.contains(h))
    {
        "video"
    } else {
        "http"
    }
}

pub(super) fn supported(source: &str) -> bool {
    ["http://", "https://", "ftp://", "sftp://", "magnet:"]
        .iter()
        .any(|s| source.to_lowercase().starts_with(s))
        || (source.to_lowercase().ends_with(".torrent") && std::path::Path::new(source).exists())
}
