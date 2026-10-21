//! Core local HTTP API. Mount G/H routers before applying `with_auth` once.
pub mod erisim;
pub mod listener;
mod request;
pub mod security;
mod transfer;

pub use afudm_types::ApiCtx;
use afudm_types::{AfuError, Json as Value, JsonMap, Result};
use axum::{
    extract::{Request, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde_json::json;
use std::{
    collections::HashMap,
    net::{Ipv4Addr, SocketAddr},
};

/// Core routes only; G/H endpoints must be merged by the application.
pub fn router(ctx: ApiCtx) -> Router {
    Router::new()
        .route(
            "/ping",
            get(|| async { Json(json!({"ok":true,"app":"AfuDM"})) }),
        )
        .route("/show", get(show))
        .route("/snapshot", get(snapshot))
        .route("/probe", get(probe))
        .route("/peers", get(peers))
        .route("/seed", get(seed))
        .route("/klasorler", get(folders))
        .route("/torrent/dosyalar", get(torrent_files))
        .route("/torrent/metrik", get(torrent_metrics))
        .route("/capabilities", get(capabilities))
        .route("/indir", get(transfer::download))
        .route("/dosya", get(transfer::phone_download))
        .route("/add_blob", post(transfer::add_blob))
        .route("/add", post(add))
        .route("/control", post(control))
        .route("/settings", post(settings).get(bilinmeyen_yol))
        .route("/renew", post(renew))
        .route("/mode", post(mode))
        .route("/torrent/secim", post(torrent_select))
        .route("/seed/tazele", post(seed_refresh))
        .route("/tracker/tara", post(tracker))
        .route("/handoff/error", post(handoff_error))
        .route("/token/rotate", post(rotate))
        .route("/_listener/{action}", get(child_lifecycle))
        .fallback(bilinmeyen_yol)
        .with_state(ctx)
}

/// Apply to the combined router, including G/H. Token is read on every request.
pub fn with_auth(r: Router, ctx: ApiCtx) -> Router {
    security::with_auth(r, ctx)
}

/// Publish the port returned by `serve` and initialize the private local token.
/// The app must call this after binding; listener startup calls it internally.
pub fn write_endpoint(ctx: &ApiCtx, port: u16) -> Result<()> {
    let token = security::load_token(&ctx.data_dir)?;
    security::endpoint(&ctx.data_dir, port, &token)
}

/// Start in the background on loopback; try the requested port and the next nine.
/// A UI child binds an OS-selected port and reports it through its stdout pipe.
pub async fn serve(r: Router, port: u16) -> Result<u16> {
    let child = std::env::var("AFUDM_UI_CHILD").as_deref() == Ok("1");
    let listener = bind(if child { 0 } else { port }).await?;
    let actual = listener.local_addr()?.port();
    if child {
        use std::io::Write;
        // Port ancak socket baglandiktan sonra, yalniz ebeveynin borusuna yazilir.
        let mut output = std::io::stdout().lock();
        writeln!(output, "AFUDM_CHILD_BOUND:{actual}")?;
        output.flush()?;
    }
    tokio::spawn(async move {
        if axum::serve(
            listener,
            r.into_make_service_with_connect_info::<SocketAddr>(),
        )
        .await
        .is_err()
        {
            log::error!("API sunucusu durdu");
        }
    });
    Ok(actual)
}

async fn bind(port: u16) -> Result<tokio::net::TcpListener> {
    let count = if std::env::var("AFUDM_UI_CHILD").as_deref() == Ok("1") || port == 0 {
        1
    } else {
        10
    };
    for offset in 0..count {
        let Some(candidate) = port.checked_add(offset) else {
            break;
        };
        // Never share a listening port with another AfuDM process.
        let socket = socket2::Socket::new(
            socket2::Domain::IPV4,
            socket2::Type::STREAM,
            Some(socket2::Protocol::TCP),
        )?;
        #[cfg(windows)]
        {
            use std::os::windows::io::AsRawSocket;
            use windows_sys::Win32::Networking::WinSock::{
                setsockopt, WSAGetLastError, SOCKET_ERROR, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
            };
            let enabled: i32 = 1;
            // The value lives until setsockopt returns; the handle is owned by socket.
            if unsafe {
                setsockopt(
                    socket.as_raw_socket() as _,
                    SOL_SOCKET,
                    SO_EXCLUSIVEADDRUSE,
                    (&enabled as *const i32).cast(),
                    std::mem::size_of_val(&enabled) as i32,
                )
            } == SOCKET_ERROR
            {
                return Err(std::io::Error::from_raw_os_error(unsafe { WSAGetLastError() }).into());
            }
        }
        if socket
            .bind(&SocketAddr::from((Ipv4Addr::LOCALHOST, candidate)).into())
            .is_ok()
            && socket.listen(128).is_ok()
        {
            socket.set_nonblocking(true)?;
            return Ok(tokio::net::TcpListener::from_std(socket.into())?);
        }
    }
    Err(AfuError::Unavailable("API portu acilamadi".into()))
}

fn fault(status: u16, code: &str, message: &str) -> Response {
    (
        StatusCode::from_u16(status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
        Json(json!({"ok":false,"code":code,"message":message,"error":message})),
    )
        .into_response()
}
/// Python `GET` icin tanimsiz yol: 404 `BILINMEYEN_YOL` (Python do_GET/do_POST else dali).
pub async fn bilinmeyen_yol() -> Response {
    fault(404, "BILINMEYEN_YOL", "bilinmeyen yol")
}
/// Python `api/server.py` ve `core/hata.py` `hata_json` ile ayni hata govdesi:
/// {"ok":false,"code","message","error"} (`message` ve `error` ayni metin).
/// Durum ve metin Python eslemesini izler: kayit yok 400 KAYIT_YOK; motor (aria2/yt-dlp),
/// veritabani ve beklenmeyen hatalar 500 INTERNAL ile genel metin doner (ic metin sizdirilmaz).
pub fn hata_yaniti(e: &AfuError) -> Response {
    let (durum, kod, mesaj) = match e {
        AfuError::Invalid(m) => (StatusCode::BAD_REQUEST, "BAD_REQUEST", m.clone()),
        AfuError::NotFound(m) => (StatusCode::BAD_REQUEST, "KAYIT_YOK", m.clone()),
        AfuError::Unavailable(m) => (StatusCode::SERVICE_UNAVAILABLE, "KULLANILAMIYOR", m.clone()),
        AfuError::Io(_) => (
            StatusCode::BAD_REQUEST,
            "IO",
            "dosya islemi basarisiz".to_string(),
        ),
        AfuError::Engine(_) | AfuError::Db(_) | AfuError::Other(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL",
            "beklenmeyen bir sunucu hatasi olustu".to_string(),
        ),
    };
    (
        durum,
        Json(json!({"ok":false,"code":kod,"message":mesaj,"error":mesaj})),
    )
        .into_response()
}
fn error(e: AfuError) -> Response {
    hata_yaniti(&e)
}
fn merged(value: Value) -> Response {
    let mut obj = JsonMap::from_iter([("ok".into(), Value::Bool(true))]);
    if let Some(map) = value.as_object() {
        obj.extend(map.clone());
    }
    Json(Value::Object(obj)).into_response()
}
fn result(value: Result<Value>) -> Response {
    match value {
        Ok(v) => merged(v),
        Err(e) => error(e),
    }
}
fn text<'a>(data: &'a JsonMap, key: &str) -> &'a str {
    data.get(key).and_then(Value::as_str).unwrap_or("")
}
fn query(req: &Request) -> HashMap<String, String> {
    let mut out = HashMap::new();
    for (key, value) in url::form_urlencoded::parse(req.uri().query().unwrap_or("").as_bytes()) {
        if !value.is_empty() {
            out.entry(key.into_owned())
                .or_insert_with(|| value.into_owned());
        }
    }
    out
}
fn q<'a>(data: &'a HashMap<String, String>, key: &str) -> &'a str {
    data.get(key).map(String::as_str).unwrap_or("")
}
// Hata tarafi axum Response'u: framework tipi, kutulamak tum cagri zincirini degistirir.
#[allow(clippy::result_large_err)]
async fn body(req: Request) -> std::result::Result<JsonMap, Response> {
    if let Some(length) = req.headers().get("content-length") {
        match length.to_str().ok().and_then(|s| s.parse::<i64>().ok()) {
            Some(n) if (0..=8 * 1024 * 1024).contains(&n) => (),
            Some(n) => {
                return Err(fault(
                    if n < 0 { 400 } else { 413 },
                    "GOVDE_HATASI",
                    "Istek boyutu uygun degil. Daha kucuk bir istek gonder.",
                ))
            }
            None => return Err(fault(400, "GOVDE_HATASI", "Istek okunamadi. Yeniden dene.")),
        }
    }
    let bytes = match tokio::time::timeout(
        std::time::Duration::from_secs(15),
        axum::body::to_bytes(req.into_body(), 8 * 1024 * 1024),
    )
    .await
    {
        Err(_) => {
            return Err(fault(
                408,
                "GOVDE_HATASI",
                "Istek tamamlanamadi. Yeniden dene.",
            ))
        }
        Ok(Err(_)) => {
            return Err(fault(
                413,
                "GOVDE_HATASI",
                "Istek boyutu uygun degil. Daha kucuk bir istek gonder.",
            ))
        }
        Ok(Ok(bytes)) => bytes,
    };
    if bytes.is_empty() {
        return Ok(JsonMap::new());
    }
    match serde_json::from_slice::<Value>(&bytes) {
        Ok(Value::Object(map)) => Ok(map),
        Ok(_) => Err(fault(
            400,
            "GOVDE_HATASI",
            "Istek bicimi uygun degil. Yeniden dene.",
        )),
        Err(_) => Err(fault(400, "GOVDE_HATASI", "Istek okunamadi. Yeniden dene.")),
    }
}
async fn show(State(ctx): State<ApiCtx>) -> Response {
    ctx.ui.show_window();
    merged(json!({}))
}
async fn snapshot(State(ctx): State<ApiCtx>) -> Response {
    result(ctx.manager.snapshot())
}
async fn probe(State(ctx): State<ApiCtx>, req: Request) -> Response {
    // Python GET /probe: her hata (bos url dahil) 400 ile doner; kod hata_json eslemesinden gelir.
    match ctx.manager.probe_video(q(&query(&req), "url")) {
        Ok(v) => merged(json!({"info":v})),
        Err(e) => {
            let mut yanit = hata_yaniti(&e);
            *yanit.status_mut() = StatusCode::BAD_REQUEST;
            yanit
        }
    }
}
async fn peers(State(ctx): State<ApiCtx>, req: Request) -> Response {
    result(
        ctx.manager
            .peers(q(&query(&req), "gid"))
            .map(|v| json!({"peers":v})),
    )
}
async fn seed(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let params = query(&req);
    let gid = q(&params, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    }
    result(ctx.manager.seed_bilgi(gid))
}
async fn torrent_metrics(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let params = query(&req);
    let gid = q(&params, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    }
    result(ctx.manager.torrent_metrikleri(gid))
}
async fn torrent_files(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let params = query(&req);
    let gid = q(&params, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    }
    result(ctx.manager.torrent_dosyalari(gid))
}
const CATEGORIES: &[(&str, &str)] = &[
    ("telefon", "📱 Telefona İndir"),
    ("video", "Video"),
    ("muzik", "Müzik"),
    ("belge", "Belgeler"),
    ("program", "Programlar"),
    ("arsiv", "Arşiv"),
    ("resim", "Resimler"),
    ("torrent", "Torrent"),
    ("genel", "Genel"),
];
async fn folders(State(ctx): State<ApiCtx>) -> Response {
    result((|| {
        Ok(
            json!({"ana":ctx.manager.current_download_dir()?,"kategoriler":CATEGORIES.iter().map(|(key,name)|json!({"anahtar":key,"ad":name})).collect::<Vec<_>>(),"acik":ctx.store.get("kategori_klasorleri")?.as_ref().is_some_and(request::truthy)}),
        )
    })())
}
const YETENEK_OZELLIKLER: &[&str] = &[
    "scheduler",
    "hiz_profilleri",
    "renew",
    "ozel_basliklar",
    "cerez",
    "zamanlama",
    "cli",
    "api",
    "kategori_klasorleri",
    "proxy",
    "sistem_proxy",
    "checksum",
    "canli_ayar",
    "headless",
    "servis_katmani",
    "web_panel",
    "roller",
    "erisim_anahtarlari",
    "anahtar_rotasyonu",
    "aktif_istemciler",
    "hiz_sinirlama",
    "origin_denetimi",
    "sunucu_profilleri",
    "tek_ornek_kilidi",
];
/// Python `servis.yetenekler()` varsayilani (Store kaydi yoksa).
fn yetenek_varsayilani(ctx: &ApiCtx) -> Value {
    let surum = env!("CARGO_PKG_VERSION");
    json!({
        "ok": true,
        "app": "AfuDM",
        "surum": surum,
        "api": 2,
        "kip": "headless",
        "uzanti_surumu": surum,
        "motorlar": afudm_engine::engines::durum(&ctx.app_dir),
        "protokoller": ["http", "https", "ftp", "sftp", "magnet", "torrent"],
        "turler": ["http", "video", "torrent"],
        "roller": ["yonetici", "salt_okur"],
        "ozellikler": YETENEK_OZELLIKLER,
        "sinirlar": {
            "kaynak": 8192,
            "baslik": 200,
            "user_agent": 512,
            "ozel_baslik": 40,
            "proxy": 1024
        }
    })
}
async fn capabilities(State(ctx): State<ApiCtx>) -> Response {
    // Store'da uygulamanin yayinladigi kayit varsa o doner; yoksa Python varsayilani. 503 yok.
    match ctx.store.get("api_capabilities") {
        Ok(Some(v)) => Json(v).into_response(),
        Ok(None) => Json(yetenek_varsayilani(&ctx)).into_response(),
        Err(e) => error(e),
    }
}
async fn add(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let mut data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    if !text(&data, "dest_dir").is_empty() {
        let root = match ctx.manager.current_download_dir() {
            Ok(v) => v,
            Err(e) => return error(e),
        };
        if !security::path_inside(
            std::path::Path::new(text(&data, "dest_dir")),
            std::path::Path::new(&root),
        ) {
            return fault(
                403,
                "HEDEF_DISARIDA",
                "hedef klasor indirme kokunun disinda",
            );
        }
    }
    let interactive = match request::boolean(&data, "interactive") {
        Ok(v) => v,
        Err(e) => return error(e),
    };
    if interactive
        && !text(&data, "url").trim().is_empty()
        && (text(&data, "prompt_source") == "desktop"
            || ctx
                .store
                .get("kaydetme_penceresi")
                .ok()
                .flatten()
                .as_ref()
                .is_some_and(request::truthy))
    {
        if let Some(queued) = ctx.ui.queue_save_location(&data) {
            return Json(queued).into_response();
        }
        return match ctx.ui.ask_save_location(&data) {
            Some(accepted) => result(ctx.manager.add(&accepted)),
            None => error(AfuError::Invalid(
                "indirme onay penceresi istegi kabul etmedi".into(),
            )),
        };
    }
    if text(&data, "dest_dir").is_empty() && !text(&data, "kategori").is_empty() {
        let root = match ctx.manager.current_download_dir() {
            Ok(v) => v,
            Err(e) => return error(e),
        };
        let name = CATEGORIES
            .iter()
            .find(|(k, _)| *k == text(&data, "kategori"))
            .map(|(_, v)| *v)
            .unwrap_or("Genel");
        data.insert(
            "dest_dir".into(),
            json!(std::path::Path::new(&root).join(name)),
        );
    }
    result(request::normalize(data).and_then(|data| ctx.manager.add(&data)))
}
async fn control(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let gid = text(&data, "gid");
    let output = match text(&data, "action") {
        "pause" => ctx.manager.pause(gid).map(|_| json!({})),
        "resume" => ctx.manager.resume(gid).map(|_| json!({})),
        "remove" => request::boolean(&data, "delete_files")
            .and_then(|delete| ctx.manager.remove(gid, delete))
            .map(|_| json!({})),
        "pause_all" => ctx.manager.pause_all().map(|_| json!({})),
        "resume_all" => ctx.manager.resume_all().map(|_| json!({})),
        "ayarla" => ctx.manager.baglanti_ayarla(
            gid,
            data.get("baglanti").and_then(Value::as_i64),
            data.get("hiz_kb").and_then(Value::as_i64),
        ),
        _ => return fault(400, "BILINMEYEN_EYLEM", "bilinmeyen eylem"),
    };
    result(output)
}
async fn settings(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    result(
        ctx.manager
            .update_settings(&data)
            .map(|v| json!({"settings":v})),
    )
}
async fn renew(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let gid = text(&data, "gid");
    let url = if text(&data, "url").is_empty() {
        text(&data, "new_url")
    } else {
        text(&data, "url")
    };
    if gid.is_empty() || url.is_empty() {
        return fault(400, "BAD_REQUEST", "gid ve url gerekli");
    }
    result(
        ctx.manager.renew(
            gid,
            url,
            data.get("headers").and_then(Value::as_object),
            data.get("cookies")
                .and_then(Value::as_array)
                .map(Vec::as_slice),
            data.get("user_agent").and_then(Value::as_str),
        ),
    )
}
async fn mode(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let name = if text(&data, "profil").is_empty() {
        text(&data, "mode")
    } else {
        text(&data, "profil")
    };
    if name.is_empty() {
        return fault(400, "BAD_REQUEST", "profil gerekli (snail|normal|turbo)");
    }
    result(ctx.manager.set_mode(name))
}
async fn torrent_select(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let gid = text(&data, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    }
    let Some(indices) = data.get("indeksler").and_then(Value::as_array) else {
        return fault(400, "GECERSIZ_SECIM", "indeksler liste olmali");
    };
    let mut clean = Vec::new();
    for v in indices {
        let n = match v {
            Value::String(s) => s.trim().parse::<i64>().ok(),
            Value::Number(n) => n.as_i64().or_else(|| {
                n.as_f64()
                    .filter(|n| n.fract() == 0.0 && *n >= i64::MIN as f64 && *n < i64::MAX as f64)
                    .map(|n| n as i64)
            }),
            _ => None,
        };
        let Some(n) = n else {
            return fault(400, "GECERSIZ_SECIM", "indeksler tam sayi olmali");
        };
        if n > 0 {
            clean.push(n)
        }
    }
    result(ctx.manager.torrent_secimi_ayarla(gid, &clean))
}
async fn seed_refresh(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let gid = text(&data, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    };
    result(ctx.manager.seed_tazele(gid))
}
async fn tracker(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    result(ctx.manager.tracker_tara(text(&data, "gid")))
}
async fn handoff_error(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let _data = match body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    // Browser-supplied errors may contain credentials; never persist that text.
    ctx.store.log("error", "Tarayici devretme hatasi", "");
    merged(json!({}))
}
async fn rotate(State(ctx): State<ApiCtx>, req: Request) -> Response {
    if let Err(r) = body(req).await {
        return r;
    };
    result(security::rotate_token(&ctx.data_dir).map(|_| json!({"rotated":true})))
}
async fn child_lifecycle(State(ctx): State<ApiCtx>, req: Request) -> Response {
    if std::env::var("AFUDM_UI_CHILD").as_deref() != Ok("1") {
        return (StatusCode::NOT_FOUND, Json(json!({"ok":false}))).into_response();
    }
    match req.uri().path() {
        "/_listener/ready" => merged(json!({})),
        "/_listener/idle" => result(ctx.manager.can_release_ui().map(|v| json!({"sleep":v}))),
        _ => (StatusCode::NOT_FOUND, Json(json!({"ok":false}))).into_response(),
    }
}

#[cfg(test)]
mod tests;
