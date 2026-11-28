use crate::{fault, q, query, ApiCtx};
use afudm_types::Result;
use axum::{
    extract::{ConnectInfo, Request, State},
    http::{HeaderValue, Method},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    Json, Router,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use rand::RngCore;
use std::{
    collections::HashMap,
    net::SocketAddr,
    path::{Component, Path, PathBuf},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use subtle::ConstantTimeEq;

pub(crate) fn secret(bytes: usize) -> String {
    let mut raw = vec![0; bytes];
    rand::rng().fill_bytes(&mut raw);
    URL_SAFE_NO_PAD.encode(raw)
}
fn equal(a: &str, b: &str) -> bool {
    !b.is_empty() && bool::from(a.as_bytes().ct_eq(b.as_bytes()))
}

pub(crate) fn private_file(path: &Path) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        if let Ok(user) = std::env::var("USERNAME") {
            let grant = if path.is_dir() {
                format!("{user}:(OI)(CI)F")
            } else {
                format!("{user}:F")
            };
            let _ = std::process::Command::new("icacls")
                .arg(path)
                .args(["/inheritance:r", "/grant:r", &grant])
                .creation_flags(0x08000000)
                .output();
        }
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(
            path,
            std::fs::Permissions::from_mode(if path.is_dir() { 0o700 } else { 0o600 }),
        );
    }
}

pub(crate) fn load_token(dir: &Path) -> Result<String> {
    std::fs::create_dir_all(dir)?;
    let file = dir.join("api_token.txt");
    match std::fs::read_to_string(&file) {
        Ok(value) if !value.trim().is_empty() => return Ok(value.trim().into()),
        Err(e) if e.kind() != std::io::ErrorKind::NotFound => return Err(e.into()),
        _ => (),
    }
    let value = secret(24);
    std::fs::write(&file, &value)?;
    private_file(&file);
    Ok(value)
}
pub(crate) fn endpoint(dir: &Path, port: u16, token: &str) -> Result<()> {
    let port = std::env::var("AFUDM_LISTENER_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(port);
    let path = dir.join("api_endpoint.json");
    std::fs::write(
        &path,
        serde_json::to_vec_pretty(&serde_json::json!({"port":port,"token":token}))?,
    )?;
    private_file(&path);
    Ok(())
}
pub fn rotate_token(dir: &Path) -> Result<()> {
    let value = secret(24);
    let path = dir.join("api_token.txt");
    std::fs::write(&path, &value)?;
    private_file(&path);
    if let Ok(raw) = std::fs::read(dir.join("api_endpoint.json")) {
        let record: serde_json::Value = match serde_json::from_slice(&raw) {
            Ok(value) => value,
            Err(_) => {
                afudm_engine::daemon::quarantine_json(&dir.join("api_endpoint.json"));
                serde_json::Value::Null
            }
        };
        if let Some(port) = record["port"].as_u64().and_then(|p| u16::try_from(p).ok()) {
            endpoint(dir, port, &value)?;
        }
    }
    Ok(())
}

pub(crate) fn origin_allowed(origin: &str) -> bool {
    if origin.chars().any(|ch| (ch as u32) < 32) {
        return false;
    }
    if let Some(id) = origin.strip_prefix("chrome-extension://") {
        return id.len() == 32 && id.bytes().all(|b| (b'a'..=b'p').contains(&b));
    }
    // Compare original spelling, rejecting paths, userinfo, trailing slashes and padded ports.
    let Some((scheme, host)) = origin.split_once("://") else {
        return false;
    };
    if !["http", "https"].contains(&scheme) {
        return false;
    }
    ["127.0.0.1", "localhost", "[::1]"].iter().any(|local| {
        host == *local
            || host
                .strip_prefix(local)
                .and_then(|tail| tail.strip_prefix(':'))
                .is_some_and(|p| p.parse::<u16>().is_ok_and(|n| p == n.to_string()))
    })
}
fn normalized(path: &Path) -> Option<PathBuf> {
    let raw = path.to_str()?;
    if raw.is_empty() || raw.contains('\0') {
        return None;
    }
    #[cfg(windows)]
    if let Some(Component::Prefix(prefix)) = path.components().next() {
        use std::path::Prefix;
        if !matches!(
            prefix.kind(),
            Prefix::Disk(_)
                | Prefix::VerbatimDisk(_)
                | Prefix::UNC(_, _)
                | Prefix::VerbatimUNC(_, _)
        ) {
            return None;
        }
    }
    #[cfg(not(windows))]
    if raw.starts_with("\\\\") || raw.starts_with("//") {
        return None;
    }
    let full = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir().ok()?.join(path)
    };
    let mut out = PathBuf::new();
    for part in full.components() {
        match part {
            Component::ParentDir => {
                out.pop();
            }
            Component::CurDir => (),
            _ => out.push(part.as_os_str()),
        }
    }
    Some(out)
}
fn comparable(path: &Path) -> PathBuf {
    #[cfg(windows)]
    {
        let raw = path.to_string_lossy().to_lowercase();
        if let Some(unc) = raw.strip_prefix(r"\\?\unc\") {
            PathBuf::from(format!(r"\\{unc}"))
        } else {
            PathBuf::from(raw.strip_prefix(r"\\?\").unwrap_or(&raw))
        }
    }
    #[cfg(not(windows))]
    {
        path.to_path_buf()
    }
}
fn resolved_existing(path: &Path) -> Option<PathBuf> {
    let mut base = path.to_path_buf();
    let mut rest = Vec::new();
    loop {
        match std::fs::symlink_metadata(&base) {
            Ok(_) => break,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                rest.push(base.file_name()?.to_os_string());
                if !base.pop() {
                    return None;
                }
            }
            Err(_) => return None,
        }
    }
    let mut out = base.canonicalize().ok()?;
    for part in rest.into_iter().rev() {
        out.push(part)
    }
    Some(out)
}
pub(crate) fn path_inside(path: &Path, root: &Path) -> bool {
    let (Some(p), Some(r)) = (normalized(path), normalized(root)) else {
        return false;
    };
    // Compare resolved forms only: a lexical pre-check rejects the same folder
    // written as a Windows 8.3 short name (C:\Users\RUNNER~1) vs its long name.
    let (Some(p), Some(r)) = (resolved_existing(&p), resolved_existing(&r)) else {
        return false;
    };
    comparable(&p).starts_with(comparable(&r))
}
#[derive(Clone)]
struct Auth {
    ctx: ApiCtx,
    rate: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
}
pub(crate) fn with_auth(router: Router, ctx: ApiCtx) -> Router {
    router.layer(middleware::from_fn_with_state(
        Auth {
            ctx,
            rate: Arc::new(Mutex::new(HashMap::new())),
        },
        auth,
    ))
}
async fn auth(State(state): State<Auth>, req: Request, next: Next) -> Response {
    let origin = req
        .headers()
        .get("origin")
        .and_then(|h| h.to_str().ok())
        .filter(|v| origin_allowed(v))
        .map(str::to_owned);
    let mut response = if req.method() == Method::OPTIONS {
        axum::http::StatusCode::NO_CONTENT.into_response()
    } else {
        let path = req.uri().path();
        let exempt = path.starts_with("/_listener/") || path.starts_with("/s/");
        let ip = req
            .extensions()
            .get::<ConnectInfo<SocketAddr>>()
            .map(|c| c.0.ip().to_string())
            .unwrap_or_else(|| "local".into());
        let allowed = if exempt {
            true
        } else if let Ok(mut rate) = state.rate.lock() {
            let now = Instant::now();
            let hits = rate.entry(ip).or_default();
            hits.retain(|t| now.duration_since(*t) < Duration::from_secs(60));
            if hits.len() >= 120 {
                false
            } else {
                hits.push(now);
                true
            }
        } else {
            false
        };
        let public = req.method() == Method::GET
            && ([
                "/ping",
                "/show",
                "/pair",
                "/m",
                "/m/",
                "/manifest.webmanifest",
                "/i18n.js",
                "/sw.js",
                "/ikon.png",
            ]
            .contains(&path)
                || path.starts_with("/s/"));
        if !allowed {
            fault(
                429,
                "RATE_LIMIT",
                "cok fazla istek; bir dakika sonra yeniden dene",
            )
        } else if public {
            next.run(req).await
        } else {
            let supplied = req
                .headers()
                .get("x-afudm-token")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("");
            let params = query(&req);
            let supplied = if supplied.is_empty() && req.method() == Method::GET && path == "/dosya"
            {
                let token = q(&params, "token");
                if token.is_empty() {
                    q(&params, "k")
                } else {
                    token
                }
            } else {
                supplied
            };
            let token = std::fs::read_to_string(state.ctx.data_dir.join("api_token.txt"));
            if !token.as_ref().is_ok_and(|token| !token.trim().is_empty()) {
                fault(
                    503,
                    "ANAHTAR_OKUNAMADI",
                    "Erişim anahtarı okunamadı, AfuDM'i yeniden başlatın.",
                )
            } else if token.is_ok_and(|token| equal(supplied, token.trim())) {
                next.run(req).await
            } else if path.starts_with("/_listener/") {
                (
                    axum::http::StatusCode::UNAUTHORIZED,
                    Json(serde_json::json!({"ok":false})),
                )
                    .into_response()
            } else if req.method() == Method::GET
                && ["/dosya", "/indir", "/klasorler"].contains(&path)
            {
                fault(401, "ANAHTAR_GEREKLI", "anahtar gerekli")
            } else {
                fault(401, "GECERSIZ_TOKEN", "gecersiz token")
            }
        }
    };
    let headers = response.headers_mut();
    if let Some(origin) = origin.and_then(|s| HeaderValue::from_str(&s).ok()) {
        headers.insert("access-control-allow-origin", origin);
        headers.insert("vary", HeaderValue::from_static("Origin"));
    }
    headers.insert(
        "access-control-allow-headers",
        HeaderValue::from_static("Content-Type, X-AfuDM-Token"),
    );
    headers.insert(
        "access-control-allow-methods",
        HeaderValue::from_static("GET, POST, OPTIONS"),
    );
    response
}

#[cfg(all(test, windows))]
mod path_tests {
    use super::*;

    #[test]
    fn network_and_verbatim_paths_keep_their_root() {
        let ordinary = normalized(Path::new(r"\\server\share\dir")).unwrap();
        let extended = normalized(Path::new(r"\\?\UNC\server\share\dir")).unwrap();
        assert_eq!(comparable(&ordinary), comparable(&extended));
        assert!(!path_inside(&extended, Path::new(r"\\server\another")));
        assert!(normalized(Path::new(r"\\.\PhysicalDrive0")).is_none());
        let dir = tempfile::tempdir().unwrap();
        let canonical = dir.path().canonicalize().unwrap();
        assert!(path_inside(&canonical.join("file"), dir.path()));
        assert!(path_inside(&dir.path().join("file"), &canonical));
    }
}
