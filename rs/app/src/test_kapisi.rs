//! T2: opt-in loopback bridge transport. Normal builds never compile this module.
use std::net::SocketAddr;
use std::sync::Arc;

use crate::bridge::{self, Kabuk};
use axum::extract::{ConnectInfo, DefaultBodyLimit, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::{routing::post, Json, Router};
use serde_json::{json, Value};

#[derive(Clone)]
struct Kapi {
    kabuk: Arc<Kabuk>,
    token: String,
}

fn yetkili(baslik: &HeaderMap, token: &str, adres: SocketAddr) -> bool {
    adres.ip().is_loopback()
        && !baslik.contains_key("origin")
        && baslik.get("x-afudm-token").and_then(|v| v.to_str().ok()) == Some(token)
}

async fn cagir(
    State(kapi): State<Kapi>,
    ConnectInfo(adres): ConnectInfo<SocketAddr>,
    baslik: HeaderMap,
    govde: axum::body::Bytes,
) -> Response {
    if !yetkili(&baslik, &kapi.token, adres) {
        return StatusCode::UNAUTHORIZED.into_response();
    }
    let v: Value = match serde_json::from_slice(&govde) {
        Ok(v) => v,
        Err(_) => return StatusCode::BAD_REQUEST.into_response(),
    };
    let (Some(name), Some(args)) = (v["name"].as_str(), v["args"].as_array()) else {
        return StatusCode::BAD_REQUEST.into_response();
    };
    if matches!(name, "reliability_health" | "reliability_restart_engine") {
        return StatusCode::FORBIDDEN.into_response();
    }
    if kapi.kabuk.port.get().is_none() {
        return StatusCode::SERVICE_UNAVAILABLE.into_response();
    }
    // Same production entry point: api_call -> spawn_blocking -> bridge::dispatch.
    Json(bridge::api_call(kapi.kabuk.app.clone(), name.to_owned(), args.clone()).await)
        .into_response()
}

pub(crate) fn baslat(kabuk: Arc<Kabuk>) -> Result<(), Box<dyn std::error::Error>> {
    let token = std::env::var("AFUDM_TEST_TOKEN")?;
    if token.len() < 32 {
        return Err("test token must contain at least 32 bytes".into());
    }
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    listener.set_nonblocking(true)?;
    let port = listener.local_addr()?.port();
    let data = kabuk.app_dir.join("data");
    std::fs::create_dir_all(&data)?;
    // Credential is deliberately absent from the discovery file and logs.
    std::fs::write(
        data.join("test_endpoint.json"),
        json!({"port": port}).to_string(),
    )?;
    let router = Router::new()
        .route("/_test/api_call", post(cagir))
        .layer(DefaultBodyLimit::max(1024 * 1024))
        .with_state(Kapi { kabuk, token });
    tauri::async_runtime::spawn(async move {
        if let Ok(listener) = tokio::net::TcpListener::from_std(listener) {
            let _ = axum::serve(
                listener,
                router.into_make_service_with_connect_info::<SocketAddr>(),
            )
            .await;
        }
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn token_origin_and_remote_clients_are_rejected() {
        let token = "a".repeat(32);
        let local = SocketAddr::from(([127, 0, 0, 1], 12345));
        let remote = SocketAddr::from(([192, 168, 1, 2], 12345));
        let mut h = HeaderMap::new();
        assert!(!yetkili(&h, &token, local));
        h.insert("x-afudm-token", "wrong".parse().unwrap());
        assert!(!yetkili(&h, &token, local));
        h.insert("x-afudm-token", token.parse().unwrap());
        assert!(yetkili(&h, &token, local));
        assert!(!yetkili(&h, &token, remote));
        h.insert("origin", "http://127.0.0.1".parse().unwrap());
        assert!(!yetkili(&h, &token, local));
    }
}

/// Open a copied legacy store without starting downloads, UI, or engine.
pub(crate) fn yalniz_goc() -> bool {
    if !std::env::args().any(|a| a == "--t2-migrate-only") {
        return false;
    }
    let sonuc = std::env::current_exe()
        .map_err(|e| e.to_string())
        .and_then(|exe| {
            let base = exe.parent().ok_or("executable parent missing")?;
            let data = base.join("data");
            let store =
                afudm_db::SqliteStore::open(&data.join("afudm.db")).map_err(|e| e.to_string())?;
            drop(store);
            std::fs::write(data.join("migration_complete.json"), "{\"ok\":true}")
                .map_err(|e| e.to_string())
        });
    if sonuc.is_err() {
        std::process::exit(2);
    }
    true
}

// Reuse the production engine arguments, changing only network isolation options.
mod engine_args {
    include!("../../crates/afudm-engine/src/args.rs");
}

/// Test-only boot avoids the production daemon's hardcoded 6810..6830 probe.
/// Manager, routers and bridge remain production implementations. IdleRpc lifecycle
/// is intentionally NOT under test: its private port range cannot be configured.
pub(crate) fn yalitilmis_boot(kabuk: Arc<Kabuk>) {
    std::thread::spawn(move || {
        if let Err(e) = test_boot(&kabuk) {
            let _ = std::fs::write(
                kabuk.app_dir.join("data/test_boot_error.json"),
                json!({"error": e.to_string()}).to_string(),
            );
            kabuk.boot_hatasi(e.to_string());
        }
    });
}

fn test_boot(k: &Arc<Kabuk>) -> Result<(), Box<dyn std::error::Error>> {
    use afudm_types::{ApiCtx, Aria2, ManagerApi, UiBridge};
    use std::time::{Duration, Instant};
    let rpc_port: u16 = std::env::var("AFUDM_TEST_RPC_PORT")?.parse()?;
    if (6810..=6830).contains(&rpc_port) || rpc_port == 0 {
        return Err("test RPC port must be outside production range".into());
    }
    let base = &k.app_dir;
    let data = base.join("data");
    let downloads = base.join("downloads");
    afudm_db::paths::ensure_dirs(base)?;
    std::fs::create_dir_all(&downloads)?;
    let session = data.join("aria2.session");
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&session)?;
    afudm_engine::daemon::sanitize_session_file(&data)?;
    let secret = afudm_engine::daemon::load_or_create_secret(&data)?;
    let mut args = engine_args::arguments(&secret, &downloads, &data, rpc_port);
    let peer_listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let peer_port = peer_listener.local_addr()?.port();
    drop(peer_listener);
    args.extend([
        "--enable-dht=false".into(),
        "--bt-enable-lpd=false".into(),
        "--disable-ipv6=true".into(),
        format!("--listen-port={peer_port}"),
    ]);
    let mut cmd = std::process::Command::new(base.join("engine/aria2c.exe"));
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }
    let mut child = cmd
        .args(args)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()?;
    let rpc = Arc::new(afudm_engine::Aria2Rpc::new("127.0.0.1", rpc_port, &secret));
    let until = Instant::now() + Duration::from_secs(20);
    while !rpc.alive() {
        if child.try_wait()?.is_some() || Instant::now() > until {
            let _ = child.kill();
            let _ = child.wait();
            return Err("isolated test engine startup failed".into());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let store = Arc::new(afudm_db::SqliteStore::open(&data.join("afudm.db"))?);
    let ui: Arc<dyn UiBridge> = k.ui.clone();
    let manager = Arc::new(afudm_core::Manager::new(
        store.clone(),
        rpc,
        ui.clone(),
        data.clone(),
        base.clone(),
    ));
    manager.start()?;
    let ctx = ApiCtx {
        manager: manager.clone(),
        store,
        data_dir: data.clone(),
        app_dir: base.clone(),
        ui,
    };
    let _ = k.ctx.set(ctx.clone());
    let automation = Arc::new(afudm_extras::g1::automation::Otomasyon::new(
        ctx.store.clone(),
        ctx.ui.clone(),
    ));
    automation.start();
    let plugins = afudm_extras::g2::servis_olustur(&ctx);
    // Never start this placeholder: health/restart operations are skipped by the harness.
    let idle = Arc::new(afudm_engine::IdleRpc::new(
        afudm_engine::Aria2Daemon::new(base, &data, &downloads),
        || {},
    ));
    let _ = k.ek.set(crate::bridge::Ek {
        eklenti: plugins.clone(),
        guncelleme: Arc::new(afudm_extras::g1::guncelleme::Guncelleme::new(
            data,
            base.clone(),
            true,
        )),
        otomasyon: automation,
        rpc: idle,
        core: manager,
    });
    let routes = afudm_api::router(ctx.clone())
        .merge(afudm_extras::g1::router(ctx.clone()))
        .merge(afudm_extras::g2::router_with(ctx.clone(), plugins))
        .merge(afudm_extras::h::router(ctx.clone()))
        .merge(crate::windows_rota::router(ctx.clone()));
    let app = afudm_api::with_auth(routes, ctx.clone());
    crate::yonetim::yonlendiriciyi_kaydet(app.clone());
    let runtime = tokio::runtime::Runtime::new()?;
    let port = runtime.block_on(afudm_api::serve(app, crate::boot::port_sec()))?;
    afudm_api::write_endpoint(&ctx, port)?;
    let _ = k.port.set(port);
    crate::izleme::baslat(k.clone());
    runtime.block_on(std::future::pending::<()>());
    Ok(())
}
