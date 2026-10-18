//! Durable tray inbox compatible with core/baslangic.py UykuDinleyici.
use crate::{error, fault, merged, security, ApiCtx};
use afudm_types::{AfuError, Json, Result};
use axum::{
    body::Body,
    extract::{Request, State},
    http::{Method, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
#[cfg(windows)]
use base64::{engine::general_purpose::STANDARD, Engine};
use serde_json::json;
use std::{
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Duration,
};
use tokio::{
    io::{AsyncBufReadExt, AsyncRead, AsyncReadExt, BufReader},
    process::{Child, Command},
    sync::{Mutex as AsyncMutex, Notify},
};

#[derive(Clone)]
pub struct Listener {
    inner: Arc<Inner>,
}
struct Inner {
    ctx: ApiCtx,
    queue: PathBuf,
    queue_lock: Mutex<()>,
    child: AsyncMutex<ChildState>,
    wake: Notify,
    closed: std::sync::atomic::AtomicBool,
    last_error: Mutex<String>,
    command: PathBuf,
    http: reqwest::Client,
}
struct ChildState {
    child: Option<Child>,
    port: u16,
    listener_port: u16,
    stopping: bool,
}
impl Listener {
    /// Construct without starting HTTP, child processes or workers.
    pub fn new(ctx: ApiCtx, command: PathBuf) -> Result<Self> {
        std::fs::create_dir_all(&ctx.data_dir)?;
        let queue = ctx.data_dir.join("listener_queue");
        std::fs::create_dir_all(&queue)?;
        security::private_file(&queue);
        security::load_token(&ctx.data_dir)?;
        Ok(Self {
            inner: Arc::new(Inner {
                ctx,
                queue,
                queue_lock: Mutex::new(()),
                child: AsyncMutex::new(ChildState {
                    child: None,
                    port: 0,
                    listener_port: 0,
                    stopping: false,
                }),
                wake: Notify::new(),
                closed: false.into(),
                last_error: Mutex::new(String::new()),
                http: reqwest::Client::builder()
                    .no_proxy()
                    .redirect(reqwest::redirect::Policy::none())
                    .build()
                    .map_err(|_| AfuError::Other("Istemci baslatilamadi".into()))?,
                command,
            }),
        })
    }
    /// Validate before acknowledging; unsupported URLs must not cancel browser downloads.
    pub fn enqueue(&self, body: &[u8]) -> Result<String> {
        let payload: Json = serde_json::from_slice(body)?;
        let Some(url) = payload
            .get("url")
            .and_then(Json::as_str)
            .map(str::trim)
            .filter(|v| !v.is_empty())
        else {
            return Err(AfuError::Invalid(
                "Indirme baglantisi eksik. Baglantiyi yeniden gonder.".into(),
            ));
        };
        let source = url.to_lowercase();
        if !["http://", "https://", "ftp://", "sftp://", "magnet:"]
            .iter()
            .any(|s| source.starts_with(s))
            && !source.ends_with(".torrent")
        {
            return Err(AfuError::Invalid(
                "Bu adres AfuDM ile indirilemez. Tarayicidan indir.".into(),
            ));
        }
        let _guard = self
            .inner
            .queue_lock
            .lock()
            .map_err(|_| AfuError::Other("Kuyruk kilidi acilamadi".into()))?;
        if records(&self.inner.queue)?.len() >= 256 {
            return Err(AfuError::Invalid(
                "Bekleyen istekler dolu. AfuDM'i acip tekrar dene.".into(),
            ));
        }
        let id = uuid::Uuid::new_v4().simple().to_string();
        let body = std::str::from_utf8(body)
            .map_err(|_| AfuError::Invalid("Istek okunamadi. Yeniden dene.".into()))?;
        write_record(
            &self.inner.queue.join(format!("{id}.json")),
            &json!({"state":"queued","body":body}),
        )?;
        self.inner.wake.notify_one();
        Ok(id)
    }
    /// Return the listener router. `start` installs authentication on this router.
    pub fn router(&self) -> Router {
        Router::new()
            .route(
                "/ping",
                get(|| async { axum::Json(json!({"ok":true,"app":"AfuDM"})) }),
            )
            .route("/add", post(enqueue_http))
            .route("/_listener/status", get(status_http).post(status_http))
            .route("/_listener/notify", post(notify_http))
            .route("/_listener/exit", get(exit_http).post(exit_http))
            .fallback(forward_http)
            .with_state(self.clone())
    }
    /// Bind a separate port and start the worker. Tests must pass zero, never 6811.
    pub async fn start(&self, port: u16) -> Result<u16> {
        let listener = crate::bind(port).await?;
        let port = listener.local_addr()?.port();
        self.inner.child.lock().await.listener_port = port;
        let token = security::load_token(&self.inner.ctx.data_dir)?;
        security::endpoint(&self.inner.ctx.data_dir, port, &token)?;
        let router = crate::with_auth(self.router(), self.inner.ctx.clone());
        let owner = self.clone();
        tokio::spawn(async move {
            let stop = owner.clone();
            let service = router.into_make_service_with_connect_info::<std::net::SocketAddr>();
            let _ = axum::serve(listener, service)
                .with_graceful_shutdown(async move {
                    while !stop.closed() {
                        stop.inner.wake.notified().await;
                    }
                })
                .await;
        });
        let owner = self.clone();
        tokio::spawn(async move {
            owner.work().await;
        });
        Ok(port)
    }
    /// Try queued records once; ambiguous outcomes stay uncertain and are never replayed.
    pub async fn deliver_once(&self) -> Result<()> {
        let mut state = self.inner.child.lock().await;
        for path in records(&self.inner.queue)? {
            let mut record = read_record(&path)?;
            if record["state"] != "queued" {
                continue;
            }
            if self.ensure_child(&mut state).await.is_err() {
                self.last_error("AfuDM acilamadi; indirme istegi saklandi. Tepsiden Ac'a bas.");
                return Ok(());
            }
            let body = record["body"].as_str().unwrap_or("").to_owned();
            record["state"] = json!("uncertain");
            write_record(&path, &record)?;
            let response = self
                .child_request(&state, Method::POST, "/add")
                .body(body)
                .header("content-type", "application/json")
                .send()
                .await;
            match response {
                Ok(response) => {
                    let success = response.status().is_success();
                    match response.json::<Json>().await {
                    Ok(value) if success && value["ok"]==true=>{std::fs::remove_file(path)?;self.last_error("");},
                    Ok(_)=>{record["state"]=json!("rejected");write_record(&path,&record)?;self.last_error("Indirme eklenemedi; istek saklandi. AfuDM'i acip baglantiyi kontrol et.");},
                    Err(_)=>self.last_error("Indirme yaniti alinamadi; istek saklandi. AfuDM'de kuyrugu kontrol et.")
                }
                }
                Err(_) => self.last_error(
                    "Indirme yaniti alinamadi; istek saklandi. AfuDM'de kuyrugu kontrol et.",
                ),
            }
        }
        Ok(())
    }
    /// Shutdown only the child created by this listener; never search for user processes.
    pub async fn close(&self) -> Result<()> {
        self.inner
            .closed
            .store(true, std::sync::atomic::Ordering::Release);
        self.inner.wake.notify_waiters();
        let mut state = self.inner.child.lock().await;
        if state.child.is_some() {
            let _ = self
                .child_request(&state, Method::GET, "/_listener/quit")
                .send()
                .await;
        }
        if let Some(child) = state.child.as_mut() {
            if tokio::time::timeout(Duration::from_secs(20), child.wait())
                .await
                .is_err()
            {
                child.kill().await?;
            }
        }
        state.child = None;
        Ok(())
    }
    fn closed(&self) -> bool {
        self.inner.closed.load(std::sync::atomic::Ordering::Acquire)
    }
    fn last_error(&self, message: &str) {
        if let Ok(mut value) = self.inner.last_error.lock() {
            *value = message.into()
        }
    }
    fn child_request(
        &self,
        state: &ChildState,
        method: Method,
        path: &str,
    ) -> reqwest::RequestBuilder {
        let token = std::fs::read_to_string(self.inner.ctx.data_dir.join("api_token.txt"))
            .unwrap_or_default();
        self.inner
            .http
            .request(method, format!("http://127.0.0.1:{}{path}", state.port))
            .header("X-AfuDM-Token", token.trim())
            .timeout(Duration::from_secs(30))
    }
    async fn ensure_child(&self, state: &mut ChildState) -> Result<()> {
        if self.closed() {
            return Err(AfuError::Unavailable("Dinleyici kapaniyor".into()));
        }
        if state.stopping {
            if let Some(child) = state.child.as_mut() {
                tokio::time::timeout(Duration::from_secs(30), child.wait())
                    .await
                    .map_err(|_| AfuError::Unavailable("AfuDM kapaniyor".into()))??;
            }
            state.child = None;
            state.stopping = false;
        }
        let running = match state.child.as_mut() {
            Some(child) => child.try_wait()?.is_none(),
            None => false,
        };
        if !running {
            state.port = 0;
            let log = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(self.inner.ctx.data_dir.join("listener_child.log"))?;
            let mut command = Command::new(&self.inner.command);
            command
                .arg("--tepside")
                .env("AFUDM_UI_CHILD", "1")
                .env("AFUDM_CHILD_PORT", "0")
                .env("AFUDM_LISTENER_PORT", state.listener_port.to_string())
                .env("AFUDM_LISTENER_TRAY", "0")
                .stdout(std::process::Stdio::piped())
                .stderr(log);
            #[cfg(windows)]
            command.creation_flags(0x08000000);
            let mut child = command.spawn()?;
            let output = child
                .stdout
                .take()
                .ok_or_else(|| AfuError::Unavailable("AfuDM acilamadi".into()))?;
            let mut output = BufReader::new(output);
            let port = tokio::time::timeout(Duration::from_secs(45), child_port(&mut output)).await;
            match port {
                Ok(Ok(port)) => state.port = port,
                _ => {
                    let _ = child.kill().await;
                    return Err(AfuError::Unavailable(
                        "AfuDM acilamadi. Tepsiden Ac'a basip tekrar dene.".into(),
                    ));
                }
            }
            // Boru dolup cocugu durdurmasin; stderr mevcut gunlukte kalir.
            tokio::spawn(async move {
                let _ = tokio::io::copy(&mut output, &mut tokio::io::sink()).await;
            });
            state.child = Some(child);
        }
        let deadline = tokio::time::Instant::now() + Duration::from_secs(45);
        while tokio::time::Instant::now() < deadline && !self.closed() {
            if let Some(child) = state.child.as_mut() {
                if child.try_wait()?.is_some() {
                    break;
                }
            }
            if let Ok(response) = self
                .child_request(state, Method::GET, "/_listener/ready")
                .send()
                .await
            {
                if response.status() == 200
                    && response.json::<Json>().await.is_ok_and(|v| v["ok"] == true)
                {
                    return Ok(());
                }
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
        Err(AfuError::Unavailable(
            "AfuDM acilamadi. Tepsiden Ac'a basip tekrar dene.".into(),
        ))
    }
    async fn work(&self) {
        while !self.closed() {
            tokio::select! {_=self.inner.wake.notified()=>(),_=tokio::time::sleep(Duration::from_secs(5))=>()}
            if self.closed() {
                break;
            }
            if self.deliver_once().await.is_err() {
                self.last_error("AfuDM yanit vermiyor. Tepsiden Ac'a bas.");
            }
            let mut state = self.inner.child.lock().await;
            if state.child.is_some() && !state.stopping {
                if let Ok(response) = self
                    .child_request(&state, Method::GET, "/_listener/idle")
                    .send()
                    .await
                {
                    if response.status() == 200
                        && response
                            .json::<Json>()
                            .await
                            .is_ok_and(|v| v["sleep"] == true)
                    {
                        state.stopping = true;
                    }
                }
            }
        }
    }
}
// Kaynak yalniz spawn edilen cocugun stdout borusudur; agdan port kabul edilmez.
async fn child_port(output: &mut (impl AsyncRead + Unpin)) -> Result<u16> {
    let mut limited = BufReader::new(output.take(4096));
    let mut line = String::new();
    while limited.read_line(&mut line).await? > 0 {
        // Sinira takilan veya yarim kalan port sayisi baska bir port sanilmasin.
        if !line.ends_with('\n') {
            break;
        }
        if let Some(value) = line.trim().strip_prefix("AFUDM_CHILD_BOUND:") {
            return value
                .parse::<u16>()
                .ok()
                .filter(|p| *p != 0)
                .ok_or_else(|| AfuError::Unavailable("AfuDM acilamadi".into()));
        }
        line.clear();
    }
    Err(AfuError::Unavailable("AfuDM acilamadi".into()))
}

fn records(root: &Path) -> Result<Vec<PathBuf>> {
    let mut paths = std::fs::read_dir(root)?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|e| e == "json"))
        .collect::<Vec<_>>();
    paths.sort();
    Ok(paths)
}
fn write_record(path: &Path, record: &Json) -> Result<()> {
    use std::io::Write;
    let mut record = record.clone();
    if let Some(body) = record["body"].as_str() {
        record["body"] = json!(crypt(body, false)?);
    }
    let temporary = path.with_extension("tmp");
    let mut file = std::fs::File::create(&temporary)?;
    security::private_file(&temporary);
    file.write_all(&serde_json::to_vec(&record)?)?;
    file.sync_all()?;
    drop(file);
    // Windows rename cannot replace existing targets. MoveFileExW is atomic.
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        let from = temporary
            .as_os_str()
            .encode_wide()
            .chain(Some(0))
            .collect::<Vec<_>>();
        let to = path
            .as_os_str()
            .encode_wide()
            .chain(Some(0))
            .collect::<Vec<_>>();
        if unsafe {
            windows_sys::Win32::Storage::FileSystem::MoveFileExW(
                from.as_ptr(),
                to.as_ptr(),
                windows_sys::Win32::Storage::FileSystem::MOVEFILE_REPLACE_EXISTING
                    | windows_sys::Win32::Storage::FileSystem::MOVEFILE_WRITE_THROUGH,
            )
        } == 0
        {
            return Err(std::io::Error::last_os_error().into());
        }
    }
    #[cfg(not(windows))]
    std::fs::rename(temporary, path)?;
    Ok(())
}
fn read_record(path: &Path) -> Result<Json> {
    let mut record: Json = match serde_json::from_slice(&std::fs::read(path)?) {
        Ok(record) => record,
        Err(_) => {
            afudm_engine::daemon::quarantine_json(path);
            return Ok(Json::Null);
        }
    };
    if let Some(body) = record["body"].as_str() {
        record["body"] = json!(crypt(body, true)?);
    }
    Ok(record)
}
fn crypt(body: &str, decrypt: bool) -> Result<String> {
    #[cfg(not(windows))]
    {
        let _ = decrypt;
        Ok(body.into())
    }
    #[cfg(windows)]
    {
        use windows_sys::Win32::{
            Foundation::LocalFree,
            Security::Cryptography::{
                CryptProtectData, CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN, CRYPT_INTEGER_BLOB,
            },
        };
        let mut bytes = if decrypt {
            STANDARD
                .decode(
                    body.strip_prefix("dpapi:")
                        .ok_or_else(|| AfuError::Invalid("Kuyruk kaydi sifreli degil".into()))?,
                )
                .map_err(|_| AfuError::Invalid("Kuyruk kaydi okunamadi".into()))?
        } else {
            body.as_bytes().to_vec()
        };
        let source = CRYPT_INTEGER_BLOB {
            cbData: bytes.len() as u32,
            pbData: bytes.as_mut_ptr(),
        };
        let mut target = CRYPT_INTEGER_BLOB {
            cbData: 0,
            pbData: std::ptr::null_mut(),
        };
        let success = unsafe {
            if decrypt {
                CryptUnprotectData(
                    &source,
                    std::ptr::null_mut(),
                    std::ptr::null(),
                    std::ptr::null(),
                    std::ptr::null(),
                    CRYPTPROTECT_UI_FORBIDDEN,
                    &mut target,
                )
            } else {
                CryptProtectData(
                    &source,
                    std::ptr::null(),
                    std::ptr::null(),
                    std::ptr::null(),
                    std::ptr::null(),
                    CRYPTPROTECT_UI_FORBIDDEN,
                    &mut target,
                )
            }
        };
        if success == 0 {
            return Err(AfuError::Io("Kuyruk sifrelemesi basarisiz".into()));
        }
        let raw =
            unsafe { std::slice::from_raw_parts(target.pbData, target.cbData as usize) }.to_vec();
        unsafe {
            LocalFree(target.pbData.cast());
        }
        if decrypt {
            String::from_utf8(raw).map_err(|_| AfuError::Invalid("Kuyruk kaydi okunamadi".into()))
        } else {
            Ok(format!("dpapi:{}", STANDARD.encode(raw)))
        }
    }
}
async fn enqueue_http(State(owner): State<Listener>, req: Request) -> Response {
    let data = match crate::body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    let raw = match serde_json::to_vec(&data) {
        Ok(v) => v,
        Err(e) => return error(e.into()),
    };
    match owner.enqueue(&raw) {
        Ok(id) => (
            StatusCode::ACCEPTED,
            axum::Json(json!({"ok":true,"queued":true,"request_id":id})),
        )
            .into_response(),
        Err(_) => fault(
            503,
            "KULLANILAMIYOR",
            "Istek alinamadi. AfuDM'i acip yeniden dene.",
        ),
    }
}
async fn status_http(State(owner): State<Listener>) -> Response {
    let paths = match records(&owner.inner.queue) {
        Ok(v) => v,
        Err(e) => return error(e),
    };
    let mut states = Vec::new();
    for path in &paths {
        match read_record(path) {
            Ok(v) => states.push(v["state"].clone()),
            Err(e) => return error(e),
        }
    }
    let mut child = owner.inner.child.lock().await;
    let pid = child.child.as_mut().and_then(|c| {
        if c.try_wait().ok().flatten().is_none() {
            c.id()
        } else {
            None
        }
    });
    let error = owner
        .inner
        .last_error
        .lock()
        .map(|v| v.clone())
        .unwrap_or_default();
    merged(json!({"child_pid":pid,"pending":paths.len(),"states":states,"error":error}))
}
async fn notify_http(State(owner): State<Listener>, req: Request) -> Response {
    let data = match crate::body(req).await {
        Ok(v) => v,
        Err(r) => return r,
    };
    owner.inner.ctx.ui.notify(
        &crate::text(&data, "title")
            .chars()
            .take(100)
            .collect::<String>(),
        &crate::text(&data, "message")
            .chars()
            .take(500)
            .collect::<String>(),
    );
    merged(json!({}))
}
async fn exit_http(State(owner): State<Listener>) -> Response {
    tokio::spawn(async move {
        let _ = owner.close().await;
    });
    merged(json!({}))
}
async fn forward_http(State(owner): State<Listener>, req: Request) -> Response {
    let mut state = owner.inner.child.lock().await;
    if let Err(e) = owner.ensure_child(&mut state).await {
        return error(e);
    }
    let path = req
        .uri()
        .path_and_query()
        .map(|v| v.as_str())
        .unwrap_or("/");
    let mut builder = owner.child_request(&state, req.method().clone(), path);
    for (name, value) in req.headers() {
        if !["host", "connection", "transfer-encoding", "x-afudm-token"].contains(&name.as_str()) {
            builder = builder.header(name, value);
        }
    }
    let response = match builder
        .body(reqwest::Body::wrap_stream(
            req.into_body().into_data_stream(),
        ))
        .send()
        .await
    {
        Ok(v) => v,
        Err(_) => {
            return fault(
                503,
                "KULLANILAMIYOR",
                "Istek alinamadi. AfuDM'i acip yeniden dene.",
            )
        }
    };
    let status = response.status();
    let headers = response.headers().clone();
    let mut output = Body::from_stream(response.bytes_stream()).into_response();
    *output.status_mut() = status;
    for (name, value) in &headers {
        if !["connection", "transfer-encoding", "server", "date"].contains(&name.as_str()) {
            output.headers_mut().insert(name.clone(), value.clone());
        }
    }
    output
}

#[cfg(test)]
mod record_tests {
    use super::*;

    #[test]
    fn corrupt_record_is_quarantined_without_replay_or_backup_loss() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("request.json");
        let malformed = b"{\"state\":\"queued\",\"body\":";

        for expected_backups in 1..=2 {
            std::fs::write(&path, malformed).unwrap();
            let record = read_record(&path).unwrap();
            assert_eq!(record, Json::Null);
            assert_ne!(record["state"], "queued");
            assert!(!path.exists());
            assert!(records(dir.path()).unwrap().is_empty());

            let backups = std::fs::read_dir(dir.path())
                .unwrap()
                .map(|entry| entry.unwrap().path())
                .collect::<Vec<_>>();
            assert_eq!(backups.len(), expected_backups);
            for backup in backups {
                let name = backup.file_name().unwrap().to_str().unwrap();
                let stamp = name.strip_prefix("request.json.corrupt-").unwrap();
                assert_eq!(stamp.len(), 15);
                chrono::NaiveDateTime::parse_from_str(stamp, "%Y%m%d-%H%M%S").unwrap();
                assert_eq!(std::fs::read(backup).unwrap(), malformed);
            }
        }
    }

    #[test]
    fn valid_record_round_trips_and_missing_record_remains_an_io_error() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("request.json");
        assert!(read_record(&path).is_err());
        let record = json!({"state": "queued", "body": "{\"url\":\"https://example.com/file\"}"});
        write_record(&path, &record).unwrap();
        assert_eq!(read_record(&path).unwrap(), record);
        assert_eq!(records(dir.path()).unwrap(), vec![path]);
    }
}

#[cfg(test)]
mod port_tests {
    use super::*;

    #[tokio::test]
    async fn pipe_child_fixture() {
        if std::env::var("AFUDM_301A_PIPE_FIXTURE").as_deref() != Ok("1") {
            return;
        }
        // Talep edilen port dolu bile olsa cocuk kendi bos portuna baglanir.
        let router = Router::new().route("/ping", get(|| async { "child-ready" }));
        crate::serve(router, 1).await.unwrap();
        tokio::time::sleep(Duration::from_secs(30)).await;
    }

    #[tokio::test]
    async fn gercek_cocuk_borusu_yeni_portu_bildirir() {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "listener::port_tests::pipe_child_fixture",
                "--exact",
                "--nocapture",
            ])
            .env("AFUDM_301A_PIPE_FIXTURE", "1")
            .env("AFUDM_UI_CHILD", "1")
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true);
        #[cfg(windows)]
        command.creation_flags(0x08000000);
        let mut child = command.spawn().unwrap();
        let mut output = child.stdout.take().unwrap();
        let port = tokio::time::timeout(Duration::from_secs(10), child_port(&mut output))
            .await
            .unwrap()
            .unwrap();
        assert_ne!(port, 1);
        let response = reqwest::Client::builder()
            .no_proxy()
            .build()
            .unwrap()
            .get(format!("http://127.0.0.1:{port}/ping"))
            .send()
            .await
            .unwrap();
        let text = response.text().await.unwrap();
        child.kill().await.unwrap();
        child.wait().await.unwrap();
        assert_eq!(text, "child-ready");
    }

    #[tokio::test]
    async fn cocuk_portu_yalniz_borudan_ve_baglandiktan_sonra_ogrenilir() {
        let socket = crate::bind(0).await.unwrap();
        let port = socket.local_addr().unwrap().port();
        let mesaj = format!("baslatiliyor\nAFUDM_CHILD_BOUND:{port}\n");
        let bildirilen = child_port(&mut mesaj.as_bytes()).await.unwrap();
        assert_eq!(bildirilen, port);
        // OS portu halen cocugun dinleyicisine aittir; baska surec alamaz.
        assert!(
            tokio::net::TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, port))
                .await
                .is_err()
        );
    }

    #[tokio::test]
    async fn eksik_sahte_ve_gecersiz_port_bildirimi_reddedilir() {
        for mesaj in [
            "",
            "{\"ok\":true}",
            "AFUDM_CHILD_BOUND:0\n",
            "AFUDM_CHILD_BOUND:65536\n",
            "AFUDM_CHILD_BOUND:abc\n",
            "AFUDM_CHILD_BOUND:43210",
        ] {
            assert!(child_port(&mut mesaj.as_bytes()).await.is_err());
        }
        assert!(child_port(&mut vec![b'x'; 5000].as_slice()).await.is_err());
    }

    #[tokio::test]
    async fn boru_bildirimi_gelmeden_http_baslamaz() {
        use tokio::io::AsyncWriteExt;
        let (mut yaz, mut oku) = tokio::io::duplex(64);
        let bekle = child_port(&mut oku);
        tokio::pin!(bekle);
        assert!(tokio::time::timeout(Duration::from_millis(20), &mut bekle)
            .await
            .is_err());
        yaz.write_all(b"AFUDM_CHILD_BOUND:43210\n").await.unwrap();
        assert_eq!(bekle.await.unwrap(), 43210);
    }
}
