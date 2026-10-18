//! Independently implemented download response checks (no third-party source).
use super::*;
use std::io::Read;

pub(super) const HTML_ERROR: &str =
    "Sunucu dosya yerine bir hata sayfası gönderdi. Bağlantıyı tarayıcıda açıp yeniden dene.";

pub(super) fn browser_headers(aria: &mut JsonMap, headers: &mut Vec<String>) {
    if !aria.contains_key("user-agent")
        && !headers
            .iter()
            .any(|h| h.to_ascii_lowercase().starts_with("user-agent:"))
    {
        aria.insert("user-agent".into(), json!("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"));
    }
    for (name, value) in [
        (
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        ),
        ("Range", "bytes=0-"),
        ("Sec-Fetch-Mode", "navigate"),
        ("Sec-Fetch-Dest", "document"),
    ] {
        if !headers.iter().any(|h| {
            h.split_once(':')
                .is_some_and(|(k, _)| k.eq_ignore_ascii_case(name))
        }) {
            headers.push(format!("{name}: {value}"));
        }
    }
}

pub(super) fn retry_403(m: &Manager, row: &Json, status: &Json) -> Result<bool> {
    let gid = text(&status["gid"]);
    let mut opts = options(row);
    if row["kind"] != "http"
        || !text(&row["source"]).starts_with("http")
        || text(&status["errorCode"]) != "22"
        || !text(&status["errorMessage"])
            .split(|c: char| !c.is_ascii_digit())
            .any(|s| s == "403")
        || opts.get("browser_retry") == Some(&json!(true))
        || state(m)?.auth_required_gids.contains(gid)
    {
        return Ok(false);
    }
    opts.insert("browser_retry".into(), json!(true));
    let path = status["files"]
        .as_array()
        .and_then(|f| f.first())
        .map(|f| Path::new(text(&f["path"])));
    if let Some(name) = path.and_then(Path::file_name) {
        opts.insert("filename".into(), json!(name.to_string_lossy()));
    }
    let dir = status
        .get("dir")
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .unwrap_or(text(&row["dest_dir"]));
    m.store
        .update_by_id(row_id(row), &map(json!({"options":opts,"dest_dir":dir})))?;
    let retry_row = m
        .store
        .by_id(row_id(row))?
        .ok_or_else(|| invalid("kayit bulunamadi"))?;
    m.store.log(
        "info",
        "HTTP 403: tarayıcı başlıklarıyla bir kez yeniden deneniyor.",
        gid,
    );
    match launch(m, &retry_row) {
        Ok(_) => {
            state(m)?.removed_gids.insert(gid.into());
            let _ = m.rpc().remove_result(gid);
            m.store
                .update_by_id(row_id(row), &map(json!({"error":"","finished_at":null})))?;
            Ok(true)
        }
        Err(_) => Ok(false),
    }
}

pub(super) fn html_error(row: &Json, status: &Json) -> bool {
    if row["kind"] != "http" || !text(&row["source"]).starts_with("http") {
        return false;
    }
    let opts = options(row);
    if html_requested(&opts) {
        return false;
    }
    let Some(path) = status["files"]
        .as_array()
        .and_then(|f| f.first())
        .map(|f| Path::new(text(&f["path"])))
    else {
        return false;
    };
    if path
        .extension()
        .and_then(|e| e.to_str())
        .is_some_and(|e| e.eq_ignore_ascii_case("html") || e.eq_ignore_ascii_case("htm"))
    {
        return false;
    }
    is_html_file(path)
}

pub(super) fn is_html_file(path: &Path) -> bool {
    let Ok(file) = std::fs::File::open(path) else {
        return false;
    };
    let mut bytes = Vec::new();
    if file.take(512).read_to_end(&mut bytes).is_err() {
        return false;
    }
    let prefix = String::from_utf8_lossy(&bytes);
    let prefix = prefix
        .trim_start_matches(|c: char| c.is_whitespace() || c == '\u{feff}')
        .to_ascii_lowercase();
    ["<!doctype html", "<html", "<head"]
        .iter()
        .any(|s| prefix.starts_with(s))
}

pub(super) fn html_requested(opts: &JsonMap) -> bool {
    opts.get("headers")
        .and_then(Json::as_object)
        .is_some_and(|h| {
            h.iter().any(|(k, v)| {
                k.eq_ignore_ascii_case("content-type")
                    && text(v)
                        .split(';')
                        .next()
                        .is_some_and(|t| t.trim().eq_ignore_ascii_case("text/html"))
            })
        })
}
