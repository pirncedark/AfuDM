use super::*;
use afudm_types::{ManagerApi, NoUi};
use axum::body::Body;
use axum::http::Request as HttpRequest;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tower::ServiceExt;

fn fixture() -> (tempfile::TempDir, ApiCtx, Arc<FakeManager>) {
    let dir = tempfile::tempdir().unwrap();
    let manager = Arc::new(FakeManager {
        calls: Mutex::new(vec![]),
        root: dir.path().into(),
    });
    let store = Arc::new(afudm_db::SqliteStore::open_in_memory().unwrap());
    let ctx = ApiCtx {
        manager: manager.clone(),
        store,
        data_dir: dir.path().into(),
        app_dir: dir.path().into(),
        ui: Arc::new(NoUi),
    };
    security::load_token(&ctx.data_dir).unwrap();
    (dir, ctx, manager)
}
async fn request(ctx: &ApiCtx, method: &str, path: &str, data: &str, auth: bool) -> (u16, Value) {
    let mut req = HttpRequest::builder()
        .method(method)
        .uri(path)
        .header("content-length", data.len());
    if auth {
        req = req.header(
            "X-AfuDM-Token",
            security::load_token(&ctx.data_dir).unwrap(),
        );
    }
    let response = with_auth(router(ctx.clone()), ctx.clone())
        .oneshot(req.body(Body::from(data.to_owned())).unwrap())
        .await
        .unwrap();
    let status = response.status().as_u16();
    let bytes = axum::body::to_bytes(response.into_body(), 1024 * 1024)
        .await
        .unwrap();
    (status, serde_json::from_slice(&bytes).unwrap())
}
#[tokio::test]
async fn authentication_rotation_and_json_errors() {
    let (_dir, ctx, _) = fixture();
    assert_eq!(
        request(&ctx, "GET", "/ping", "", false).await.1,
        json!({"ok":true,"app":"AfuDM"})
    );
    assert_eq!(request(&ctx, "GET", "/snapshot", "", false).await.0, 401);
    assert_eq!(
        request(&ctx, "GET", "/snapshot?token=wrong", "", false)
            .await
            .0,
        401
    );
    assert_eq!(request(&ctx, "GET", "/snapshot", "", true).await.0, 200);
    assert_eq!(request(&ctx, "POST", "/add", "[]", true).await.0, 400);
    assert_eq!(request(&ctx, "POST", "/add", "{", true).await.0, 400);
    let old = security::load_token(&ctx.data_dir).unwrap();
    write_endpoint(&ctx, 12345).unwrap();
    assert_eq!(
        request(&ctx, "POST", "/token/rotate", "{}", true).await.0,
        200
    );
    assert_ne!(old, security::load_token(&ctx.data_dir).unwrap());
    let response = with_auth(router(ctx.clone()), ctx)
        .oneshot(
            HttpRequest::builder()
                .uri("/snapshot")
                .header("X-AfuDM-Token", old)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 401);
}
#[tokio::test]
async fn add_control_torrent_and_error_mapping() {
    let (_dir, ctx, manager) = fixture();
    assert_eq!(
        request(
            &ctx,
            "POST",
            "/add",
            r#"{"url":"https://example.test/a","audio_only":"false"}"#,
            true
        )
        .await
        .1["gid"],
        "test-gid"
    );
    assert_eq!(
        manager.calls.lock().unwrap()[0]["source"],
        "https://example.test/a"
    );
    assert_eq!(
        request(
            &ctx,
            "POST",
            "/control",
            r#"{"action":"remove","gid":"g","delete_files":"false"}"#,
            true
        )
        .await
        .0,
        200
    );
    assert_eq!(manager.calls.lock().unwrap()[1]["delete_files"], false);
    assert_eq!(
        request(
            &ctx,
            "POST",
            "/torrent/secim",
            r#"{"gid":"g","indeksler":["2",0,-1,3.0]}"#,
            true
        )
        .await
        .1["indeksler"],
        json!([2, 3])
    );
    assert_eq!(
        request(
            &ctx,
            "POST",
            "/torrent/secim",
            r#"{"gid":"g","indeksler":[true]}"#,
            true
        )
        .await
        .0,
        400
    );
    // Python /probe: her hata 400; motor hatasi kodu INTERNAL ve genel metin.
    let (status, body) = request(&ctx, "GET", "/probe?url=bad", "", true).await;
    assert_eq!(status, 400);
    assert_eq!(body["code"], "INTERNAL");
    assert_eq!(body["message"], body["error"]);
    for (error, status, kod) in [
        (AfuError::Invalid("x".into()), 400, "BAD_REQUEST"),
        (AfuError::NotFound("x".into()), 400, "KAYIT_YOK"),
        (AfuError::Engine("x".into()), 500, "INTERNAL"),
        (AfuError::Unavailable("x".into()), 503, "KULLANILAMIYOR"),
        (AfuError::Io("x".into()), 400, "IO"),
        (AfuError::Other("x".into()), 500, "INTERNAL"),
    ] {
        let (durum, govde) = govde_al(super::hata_yaniti(&error)).await;
        assert_eq!(durum, status, "{kod} durum kodu");
        assert_eq!(govde["ok"], false);
        assert_eq!(govde["code"], kod);
        assert_eq!(govde["message"], govde["error"]);
    }
}

async fn govde_al(yanit: Response) -> (u16, Value) {
    let durum = yanit.status().as_u16();
    let bytes = axum::body::to_bytes(yanit.into_body(), 1024 * 1024)
        .await
        .unwrap();
    (durum, serde_json::from_slice(&bytes).unwrap())
}

#[tokio::test]
async fn python_uyumlu_rotalar_ve_yetenekler() {
    let (_dir, ctx, _) = fixture();
    // GET /settings: Python gibi 404 BILINMEYEN_YOL (POST ayni kalir).
    let (status, body) = request(&ctx, "GET", "/settings", "", true).await;
    assert_eq!(status, 404);
    assert_eq!(body["code"], "BILINMEYEN_YOL");
    assert_eq!(body["message"], "bilinmeyen yol");
    assert_eq!(body["error"], "bilinmeyen yol");
    // /windows-integration afudm-api'den kaldirildi; F3 app tarafinda ekler.
    let (status, _) = request(&ctx, "GET", "/windows-integration", "", true).await;
    assert_eq!(status, 404);
    // /capabilities: Store kaydi yoksa 200 ve Python varsayilani (503 yok).
    let (status, body) = request(&ctx, "GET", "/capabilities", "", true).await;
    assert_eq!(status, 200);
    assert_eq!(body["ok"], true);
    assert_eq!(body["app"], "AfuDM");
    assert_eq!(body["api"], 2);
    assert_eq!(body["kip"], "headless");
    assert_eq!(body["roller"], json!(["yonetici", "salt_okur"]));
    assert_eq!(body["sinirlar"]["kaynak"], 8192);
    for anahtar in [
        "surum",
        "uzanti_surumu",
        "motorlar",
        "protokoller",
        "turler",
        "ozellikler",
    ] {
        assert!(body.get(anahtar).is_some(), "{anahtar} eksik");
    }
    // Hata govdesi: bos /renew -> code, message ve error birlikte.
    let (status, body) = request(&ctx, "POST", "/renew", "{}", true).await;
    assert_eq!(status, 400);
    assert_eq!(body["code"], "BAD_REQUEST");
    assert_eq!(body["message"], "gid ve url gerekli");
    assert_eq!(body["error"], "gid ve url gerekli");
}
#[tokio::test]
async fn cors_and_body_limit() {
    let (_dir, ctx, _) = fixture();
    let response = with_auth(router(ctx.clone()), ctx.clone())
        .oneshot(
            HttpRequest::builder()
                .method("OPTIONS")
                .uri("/add")
                .header("origin", "http://localhost:1234")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 204);
    assert_eq!(
        response.headers()["access-control-allow-origin"],
        "http://localhost:1234"
    );
    let response = with_auth(router(ctx.clone()), ctx.clone())
        .oneshot(
            HttpRequest::builder()
                .method("POST")
                .uri("/add")
                .header(
                    "X-AfuDM-Token",
                    security::load_token(&ctx.data_dir).unwrap(),
                )
                .header("content-length", "8388609")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 413);
    for origin in [
        "https://evil.test",
        "http://localhost.evil.test",
        "http://localhost/",
        "http://localhost:001",
        "chrome-extension://bad",
    ] {
        assert!(!security::origin_allowed(origin));
    }
    assert!(security::origin_allowed(&format!(
        "chrome-extension://{}",
        "a".repeat(32)
    )));
}
#[tokio::test]
async fn blob_streams_and_rejects_client_paths() {
    let (dir, ctx, _) = fixture();
    let (status, _) = request(
        &ctx,
        "POST",
        "/add_blob?filename=demo.pdf",
        "pdf bytes",
        true,
    )
    .await;
    assert_eq!(status, 200);
    assert_eq!(
        std::fs::read(dir.path().join("demo.pdf")).unwrap(),
        b"pdf bytes"
    );
    assert_eq!(
        request(&ctx, "POST", "/add_blob?filename=../escape", "x", true)
            .await
            .0,
        400
    );
    assert_eq!(
        request(&ctx, "POST", "/add_blob?filename=a&dest_dir=x", "x", true)
            .await
            .0,
        400
    );
    assert!(security::path_inside(
        &dir.path().join("new/file"),
        dir.path()
    ));
    assert!(!security::path_inside(
        &dir.path().join("../outside"),
        dir.path()
    ));
}
#[tokio::test]
async fn serve_and_listener_use_ephemeral_ports() {
    let (_dir, ctx, _) = fixture();
    let port = serve(router(ctx.clone()), 0).await.unwrap();
    assert_ne!(port, 6811);
    assert_ne!(port, 0);
    let owner =
        listener::Listener::new(ctx.clone(), ctx.app_dir.join("nonexistent-test-child")).unwrap();
    assert!(owner.enqueue(br#"{"url":"file:///private"}"#).is_err());
    assert_eq!(
        std::fs::read_dir(ctx.data_dir.join("listener_queue"))
            .unwrap()
            .count(),
        0
    );
    let id = owner
        .enqueue(br#"{"url":"https://example.test/a","headers":{"Cookie":"private-cookie"}}"#)
        .unwrap();
    assert_eq!(id.len(), 32);
    #[cfg(windows)]
    assert!(!std::fs::read_to_string(
        ctx.data_dir
            .join("listener_queue")
            .join(format!("{id}.json"))
    )
    .unwrap()
    .contains("private-cookie"));
    // No child process is spawned by new/router/close or by an empty delivery.
    owner.close().await.unwrap();
    let (_other_dir, other_ctx, _) = fixture();
    let other = listener::Listener::new(
        other_ctx.clone(),
        other_ctx.app_dir.join("nonexistent-test-child"),
    )
    .unwrap();
    other.deliver_once().await.unwrap();
    let response = with_auth(other.router(), other_ctx.clone())
        .oneshot(
            HttpRequest::builder()
                .method("POST")
                .uri("/add")
                .header(
                    "X-AfuDM-Token",
                    security::load_token(&other_ctx.data_dir).unwrap(),
                )
                .body(Body::from(r#"{"url":"https://example.test/a"}"#))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 202);
    let port = other.start(0).await.unwrap();
    assert_ne!(port, 6811);
    other.close().await.unwrap();
}
#[test]
fn access_keys_sessions_roles_and_limiter() {
    let (_dir, ctx, _) = fixture();
    let depot = erisim::ErisimDeposu::new(ctx.store.clone());
    let params = |v: Value| v.as_object().unwrap().clone();
    let key = depot
        .call(
            "anahtar_olustur",
            &params(json!({"ad":"test","rol":"yonetici"})),
        )
        .unwrap();
    assert_eq!(
        depot
            .call("dogrula", &params(json!({"sunulan":key["gizli"]})))
            .unwrap()["id"],
        key["id"]
    );
    let session = depot
        .call(
            "oturum_ac",
            &params(json!({"key_id":key["id"],"rol":"yonetici","ip":"127.0.0.1"})),
        )
        .unwrap();
    assert_eq!(
        depot
            .call("oturum_dokun", &params(json!({"oturum":session})))
            .unwrap()["rol"],
        "yonetici"
    );
    depot
        .call("anahtar_rotasyon", &params(json!({"key_id":key["id"]})))
        .unwrap();
    assert!(depot
        .call("dogrula", &params(json!({"sunulan":key["gizli"]})))
        .unwrap()
        .is_null());
    assert!(erisim::izinli("yonetici", "yaz"));
    assert!(!erisim::izinli("salt_okur", "yaz"));
    assert_eq!(erisim::ip_maskele("192.168.1.42"), "192.168.1.x");
    let limit = erisim::HizSinirlayici::new(1, 1, 5);
    assert_eq!(limit.call("izin_ver", "a").unwrap()[0], true);
    assert_eq!(limit.call("izin_ver", "a").unwrap()[0], false);
    limit.call("hatali", "b").unwrap();
    assert!(limit.call("kilitli_mi", "b").unwrap().as_f64().unwrap() > 0.0);
    assert_eq!(limit.call("kilitleri_temizle", "").unwrap(), 1);
}
#[derive(Default)]
struct FakeManager {
    calls: Mutex<Vec<Value>>,
    root: PathBuf,
}
impl ManagerApi for FakeManager {
    #[allow(unused_variables)]
    fn start(&self) -> Result<()> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn stop(&self) -> Result<()> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn set_mode(&self, ad: &str) -> Result<Value> {
        Ok(json!({"profil":ad}))
    }
    #[allow(unused_variables)]
    fn baglanti_ayarla(
        &self,
        gid: &str,
        baglanti: Option<i64>,
        hiz_kb: Option<i64>,
    ) -> Result<Value> {
        Ok(json!({"gid":gid,"baglanti":baglanti,"hiz_kb":hiz_kb}))
    }
    #[allow(unused_variables)]
    fn update_settings(&self, changes: &JsonMap) -> Result<Value> {
        Ok(json!(changes))
    }
    #[allow(unused_variables)]
    fn current_download_dir(&self) -> Result<String> {
        Ok(self.root.to_string_lossy().into())
    }
    #[allow(unused_variables)]
    fn add_completed_file(&self, path: &Path) -> Result<Value> {
        self.calls.lock().unwrap().push(json!(path));
        Ok(json!({"id":8,"gid":"blob"}))
    }
    #[allow(unused_variables)]
    fn add(&self, req: &JsonMap) -> Result<Value> {
        self.calls.lock().unwrap().push(json!(req));
        Ok(json!({"gid":"test-gid","id":7}))
    }
    #[allow(unused_variables)]
    fn probe_video(&self, url: &str) -> Result<Value> {
        if url == "bad" {
            Err(AfuError::Engine("motor hatasi".into()))
        } else {
            Ok(json!({"title":"video"}))
        }
    }
    #[allow(unused_variables)]
    fn pause(&self, gid: &str) -> Result<bool> {
        self.calls.lock().unwrap().push(json!(gid));
        Ok(true)
    }
    #[allow(unused_variables)]
    fn resume(&self, gid: &str) -> Result<bool> {
        Ok(true)
    }
    #[allow(unused_variables)]
    fn remove(&self, gid: &str, delete_files: bool) -> Result<bool> {
        self.calls
            .lock()
            .unwrap()
            .push(json!({"gid":gid,"delete_files":delete_files}));
        Ok(true)
    }
    #[allow(unused_variables)]
    fn resolve_item_path(&self, gid: &str) -> Result<Option<PathBuf>> {
        Ok(Some(self.root.join(gid)))
    }
    fn phone_download_path(&self, gid: &str) -> Result<Option<PathBuf>> {
        Ok(Some(self.root.join(gid)))
    }
    #[allow(unused_variables)]
    fn pause_all(&self) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn resume_all(&self) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn retry(&self, row_id: i64) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn renew(
        &self,
        gid: &str,
        yeni_url: &str,
        headers: Option<&JsonMap>,
        cookies: Option<&[Value]>,
        user_agent: Option<&str>,
    ) -> Result<Value> {
        Ok(json!({"gid":gid,"url":yeni_url}))
    }
    #[allow(unused_variables)]
    fn seed_bilgi(&self, gid: &str) -> Result<Value> {
        Ok(json!({"gid":gid}))
    }
    #[allow(unused_variables)]
    fn tracker_tara(&self, gid: &str) -> Result<Value> {
        Ok(json!({"gid":gid}))
    }
    #[allow(unused_variables)]
    fn seed_dosyalari(&self) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn seed_dosya_ekle(&self, yol: &str) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn seed_dosya_sil(&self, ad: &str) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn seed_tazele(&self, gid: &str) -> Result<Value> {
        Ok(json!({"gid":gid}))
    }
    #[allow(unused_variables)]
    fn snapshot(&self) -> Result<Value> {
        Ok(json!({"items":[],"mode":"normal"}))
    }
    #[allow(unused_variables)]
    fn peers(&self, gid: &str) -> Result<Vec<Value>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn torrent_on_ekle(&self, source: &str) -> Result<String> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn torrent_on_iptal(&self, gid: &str) -> Result<()> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn torrent_dosyalari(&self, gid: &str) -> Result<Value> {
        Ok(json!({"dosyalar": [], "hazir_degil": false, "neden": "", "gid": gid}))
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<Vec<i64>> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn torrent_secimi_ayarla(&self, gid: &str, indeksler: &[i64]) -> Result<Value> {
        self.calls.lock().unwrap().push(json!(indeksler));
        Ok(json!({"gid":gid,"indeksler":indeksler}))
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn torrent_metrikleri(&self, gid: &str) -> Result<Value> {
        Ok(json!({"gid":gid}))
    }
    #[allow(unused_variables)]
    fn servers(&self, gid: &str) -> Result<Vec<Value>> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn can_release_ui(&self) -> Result<bool> {
        Ok(true)
    }
    #[allow(unused_variables)]
    fn butunluk_tara(&self, gid: &str) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn butunluk_onar(&self, gid: &str, yeni_url: &str) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn butunluk_hepsini_tara(&self) -> Result<Value> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
    #[allow(unused_variables)]
    fn notify_telegram(&self, text: &str) -> Result<bool> {
        Err(AfuError::Unavailable("test metodu".into()))
    }
}

#[test]
fn limiter_live_settings_preserve_attempts_and_locks() {
    let mut limiter = erisim::HizSinirlayici::new(1, 2, 300);
    assert_eq!(limiter.call("izin_ver", "a").unwrap()[0], true);
    assert_eq!(limiter.call("izin_ver", "a").unwrap()[0], false);
    limiter.call("hatali", "b").unwrap();
    limiter.ayarla(Some(3), Some(1), Some(0));
    assert_eq!(limiter.call("izin_ver", "a").unwrap()[0], true);
    limiter.call("hatali", "b").unwrap();
    assert_eq!(limiter.call("izin_ver", "b").unwrap()[0], false);
    let status = limiter.call("durum", "").unwrap();
    assert_eq!(status["limit"], 3);
    assert_eq!(status["hatali_limit"], 1);
    assert_eq!(status["kilit_saniye"], 5);
    limiter.ayarla(Some(0), None, None);
    assert_eq!(limiter.call("durum", "").unwrap()["limit"], 1);
}

#[tokio::test]
async fn serve_passes_client_addr_as_connect_info() {
    async fn echo_ip(
        axum::extract::ConnectInfo(addr): axum::extract::ConnectInfo<SocketAddr>,
    ) -> String {
        addr.ip().to_string()
    }
    let app = Router::new().route("/ip", axum::routing::get(echo_ip));
    let port = serve(app, 0).await.unwrap();
    let raw = tokio::task::spawn_blocking(move || {
        use std::io::{Read, Write};
        let mut s = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
        s.write_all(b"GET /ip HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            .unwrap();
        let mut out = String::new();
        s.read_to_string(&mut out).unwrap();
        out
    })
    .await
    .unwrap();
    assert!(raw.starts_with("HTTP/1.1 200"), "{raw}");
    assert!(raw.trim_end().ends_with("127.0.0.1"), "{raw}");
}
