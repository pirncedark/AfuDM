use super::*;
use afudm_types::{Aria2, NoUi, Store};
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct MemoryStore {
    rows: Mutex<BTreeMap<i64, Json>>,
    settings: Mutex<JsonMap>,
}

#[derive(Default)]
struct MemoryRpc {
    statuses: Mutex<BTreeMap<String, Json>>,
    calls: Mutex<Vec<(String, Vec<Json>)>>,
    offline: Mutex<bool>,
}

fn manager() -> Manager {
    Manager::new(
        Arc::new(MemoryStore::default()),
        Arc::new(MemoryRpc::default()),
        Arc::new(NoUi),
        std::env::temp_dir(),
        std::env::temp_dir(),
    )
}

struct Fixture {
    m: Manager,
    rpc: Arc<MemoryRpc>,
    root: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "afudm-queue-{}-{}",
            std::process::id(),
            rand::random::<u64>()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let rpc = Arc::new(MemoryRpc::default());
        let m = Manager::new(
            Arc::new(MemoryStore::default()),
            rpc.clone(),
            Arc::new(NoUi),
            root.clone(),
            root.clone(),
        );
        m.store.set("download_dir", json!(root)).unwrap();
        Self { m, rpc, root }
    }
    fn add(&self, name: &str) -> Json {
        add(
            &self.m,
            json!({"source":format!("https://example.test/{name}")})
                .as_object()
                .unwrap(),
        )
        .unwrap()
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        // Every fixture owns exactly this fresh temporary directory.
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

#[test]
fn http_add_duplicate_controls_and_retry() {
    let f = Fixture::new();
    let result = f.add("test.zip");
    let gid = result["gid"].as_str().unwrap();
    assert!(add(
        &f.m,
        json!({"url":"https://example.test/test.zip"})
            .as_object()
            .unwrap()
    )
    .is_err());
    assert!(pause(&f.m, gid).unwrap());
    assert_eq!(f.m.store.by_gid(gid).unwrap().unwrap()["status"], "paused");
    assert!(resume(&f.m, gid).unwrap());
    baglanti_ayarla(&f.m, gid, Some(4), Some(128)).unwrap();
    assert_eq!(
        options(&f.m.store.by_gid(gid).unwrap().unwrap())["baglanti"],
        4
    );
    assert!(baglanti_ayarla(&f.m, gid, Some(65), None).is_err());
    assert!(baglanti_ayarla(&f.m, gid, None, Some(-1)).is_err());
    let retried = retry(&f.m, result["id"].as_i64().unwrap()).unwrap();
    assert_ne!(retried["gid"], result["gid"]);
    assert!(state(&f.m).unwrap().removed_gids.contains(gid));
}

#[test]
fn scheduled_add_persists_without_launch_or_cookies_in_options() {
    let f = Fixture::new();
    let req = json!({"source":"https://example.test/f.zip", "start_after":2000000000.0,"cookies":[{"name":"sid","value":"secret","domain":"example.test"}]});
    let result = add(&f.m, req.as_object().unwrap()).unwrap();
    assert_eq!(result["scheduled_for"], 2000000000.0);
    let row =
        f.m.store
            .by_id(result["id"].as_i64().unwrap())
            .unwrap()
            .unwrap();
    assert_eq!(row["status"], "scheduled");
    assert!(!options(&row).contains_key("cookies"));
    assert_eq!(state(&f.m).unwrap().cookies[&row_id(&row)].len(), 1);
    assert!(!f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(n, _)| n == "add_uri"));
    assert_eq!(
        snapshot(&f.m).unwrap()["items"][0]["gid"],
        format!("row:{}", row_id(&row))
    );
    remove(&f.m, &format!("row:{}", row_id(&row)), false).unwrap();
    assert_eq!(
        f.m.store.by_id(row_id(&row)).unwrap().unwrap()["status"],
        "removed"
    );
}

#[test]
fn completed_file_registration_and_resolve() {
    let f = Fixture::new();
    let path = f.root.join("page.html");
    std::fs::write(&path, "page").unwrap();
    let result = add_completed_file(&f.m, &path).unwrap();
    let gid = result["gid"].as_str().unwrap();
    assert!(gid.starts_with("local:"));
    assert_eq!(
        resolve_item_path(&f.m, gid).unwrap().unwrap(),
        path.canonicalize().unwrap()
    );
    assert_eq!(f.m.store.by_gid(gid).unwrap().unwrap()["done_bytes"], 4);
    assert!(f.rpc.calls.lock().unwrap().is_empty());
    remove(&f.m, gid, true).unwrap();
    assert!(!path.exists());
    assert!(f.root.exists());
}

#[test]
fn parent_child_remove_hides_orphans_and_allows_hash_readd() {
    let f = Fixture::new();
    let hash = "0123456789012345678901234567890123456789";
    let id =
        f.m.store
            .add(
                "torrent",
                &format!("magnet:?xt=urn:btih:{hash}"),
                Some("bundle"),
                f.root.to_str(),
                None,
                None,
                Some("parent"),
            )
            .unwrap();
    let file = f.root.join("bundle.bin");
    std::fs::write(&file, "body").unwrap();
    let part = f.root.join("bundle.bin.aria2");
    std::fs::write(&part, "control").unwrap();
    f.rpc.statuses.lock().unwrap().extend([
        ("parent".into(), json!({"gid":"parent","infoHash":hash,"followedBy":["child"]})),
        ("child".into(), json!({"gid":"child","status":"active","infoHash":hash,"following":"parent","files":[{"path":file}]})),
    ]);
    remove(&f.m, "parent", true).unwrap();
    assert!(!file.exists());
    assert!(!part.exists());
    assert!(f.root.exists());
    assert_eq!(f.m.store.by_id(id).unwrap().unwrap()["status"], "removed");
    assert!(state(&f.m).unwrap().removed_hashes.contains(hash));
    assert!(state(&f.m).unwrap().removed_gids.contains("child"));
    assert!(snapshot(&f.m).unwrap()["items"]
        .as_array()
        .unwrap()
        .is_empty());
    // A replacement DB row must remain visible even if an old removed hash survives.
    let id =
        f.m.store
            .add(
                "torrent",
                &format!("magnet:?xt=urn:btih:{hash}"),
                Some("again"),
                f.root.to_str(),
                None,
                None,
                Some("new"),
            )
            .unwrap();
    f.rpc.statuses.lock().unwrap().insert(
        "new".into(),
        json!({"gid":"new","status":"active","infoHash":hash,"files":[]}),
    );
    let snap = snapshot(&f.m).unwrap();
    assert_eq!(snap["items"].as_array().unwrap().len(), 1);
    assert_eq!(snap["items"][0]["id"], id);
}

#[test]
fn remove_rejects_outside_files_and_root_directory() {
    let f = Fixture::new();
    let sibling = Fixture::new();
    let outside = sibling.root.join("keep.bin");
    std::fs::write(&outside, "keep").unwrap();
    let result = f.add("x.zip");
    let gid = result["gid"].as_str().unwrap();
    f.rpc.statuses.lock().unwrap().get_mut(gid).unwrap()["files"] =
        json!([{"path":outside},{"path":f.root}]);
    remove(&f.m, gid, true).unwrap();
    assert!(outside.exists());
    assert!(f.root.exists());
}

#[test]
fn renew_updates_url_and_clears_auth_requirement() {
    let f = Fixture::new();
    let result = f.add("old.zip");
    let gid = result["gid"].as_str().unwrap();
    state(&f.m).unwrap().auth_required_gids.insert(gid.into());
    assert!(resume(&f.m, gid).is_err());
    assert!(retry(&f.m, result["id"].as_i64().unwrap()).is_err());
    let result = renew(
        &f.m,
        gid,
        "https://example.test/new.zip",
        None,
        None,
        Some("Agent"),
    )
    .unwrap();
    assert_eq!(result["degisen"], 1);
    assert_eq!(
        f.m.store.by_gid(gid).unwrap().unwrap()["source"],
        "https://example.test/new.zip"
    );
    assert!(!state(&f.m).unwrap().auth_required_gids.contains(gid));
    assert_eq!(
        serde_json::from_slice::<Json>(
            &std::fs::read(f.root.join("aria2.auth-required.json")).unwrap()
        )
        .unwrap(),
        json!([])
    );
}

#[test]
fn request_and_filename_contracts() {
    assert_eq!(
        dosya_adi::guess("https://example.test/a%20b.zip"),
        "a b.zip"
    );
    assert_eq!(dosya_adi::safe("CON.txt"), "_CON.txt");
    assert_eq!(
        dosya_adi::url_key("HTTPS://Example.Test/a?q=1#part"),
        "https://example.test/a?q=1"
    );
    assert_eq!(
        dosya_adi::detect_kind("https://example.test/file.torrent?q=1"),
        "torrent"
    );
    assert_eq!(
        dosya_adi::detect_kind("https://youtube.com/watch?v=1"),
        "video"
    );
    let n = models::normalize(
        json!({"url":" https://example.test/f ","checksum":"SHA256:AbCd"})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    assert_eq!(n["checksum"], "sha-256=abcd");
    assert!(models::normalize(
        json!({"url":"https://e.test","headers":[]})
            .as_object()
            .unwrap()
    )
    .is_err());
    assert!(models::normalize(
        json!({"url":"https://e.test","kapsayici":"bad"})
            .as_object()
            .unwrap()
    )
    .is_err());
    assert!(models::parse_time(&json!("bad")).is_err());
    assert_eq!(
        models::parse_time(&json!("2000000000")).unwrap(),
        Some(2000000000.0)
    );
}

#[test]
fn profiles_restore_normal_limit() {
    let m = manager();
    m.store.set("max_speed_kb", json!(750)).unwrap();
    assert_eq!(set_mode(&m, "turbo").unwrap()["limit_kb"], 0);
    assert_eq!(set_mode(&m, " NORMAL ").unwrap()["limit_kb"], 750);
    assert!(set_mode(&m, "bad").is_err());
}

#[test]
fn missing_pause_resume_and_connection_fail_without_writes() {
    let m = manager();
    assert!(pause(&m, "absent").is_err());
    assert!(resume(&m, "absent").is_err());
    assert!(baglanti_ayarla(&m, "absent", Some(4), None).is_err());
    assert!(m.store.list(None, 100).unwrap().is_empty());
}

#[test]
fn special_servers_and_orphan_remove() {
    let m = manager();
    assert!(servers(&m, "yt:1").unwrap().is_empty());
    assert!(servers(&m, "row:1").unwrap().is_empty());
    assert!(remove(&m, "absent", false).unwrap());
    assert!(remove(&m, "absent", false).unwrap());
}

#[test]
fn settings_validation_is_all_or_nothing() {
    let m = manager();
    let changes = json!({"max_concurrent": 0, "download_dir": "never-created"});
    assert!(update_settings(&m, changes.as_object().unwrap()).is_err());
    assert!(m.store.all_settings().unwrap().is_empty());
}

#[test]
fn lifecycle_and_telegram_without_configuration() {
    let m = manager();
    start(&m).unwrap();
    assert!(!can_release_ui(&m).unwrap());
    assert!(!notify_telegram(&m, "test").unwrap());
    pause_all(&m).unwrap();
    resume_all(&m).unwrap();
    stop(&m).unwrap();
}

#[test]
fn invalid_add_retry_renew_and_local_file() {
    let m = manager();
    assert!(add(&m, json!({"url":"plain text"}).as_object().unwrap()).is_err());
    assert!(retry(&m, 999).is_err());
    assert!(renew(&m, "missing", "bad", None, None, None).is_err());
    assert!(add_completed_file(&m, Path::new("missing-file")).is_err());
    assert!(resolve_item_path(&m, "missing").unwrap().is_none());
}

#[test]
fn empty_snapshot_has_python_envelope() {
    let m = manager();
    let s = snapshot(&m).unwrap();
    assert_eq!(s["items"], json!([]));
    assert_eq!(
        s["stat"],
        json!({"downloadSpeed":0,"uploadSpeed":0,"numActive":0,"numWaiting":0,"numStopped":0})
    );
    for key in [
        "settings",
        "engine_ok",
        "download_dir",
        "lang",
        "last_error",
        "automation",
    ] {
        assert!(s.get(key).is_some(), "{key}");
    }
}

impl Store for MemoryStore {
    fn get(&self, key: &str) -> Result<Option<Json>> {
        Ok(self.settings.lock().unwrap().get(key).cloned())
    }
    fn set(&self, key: &str, value: Json) -> Result<()> {
        self.settings.lock().unwrap().insert(key.into(), value);
        Ok(())
    }
    fn all_settings(&self) -> Result<JsonMap> {
        Ok(self.settings.lock().unwrap().clone())
    }
    fn by_id(&self, id: i64) -> Result<Option<Json>> {
        Ok(self.rows.lock().unwrap().get(&id).cloned())
    }
    fn by_gid(&self, gid: &str) -> Result<Option<Json>> {
        Ok(self
            .rows
            .lock()
            .unwrap()
            .values()
            .find(|r| r["gid"] == gid)
            .cloned())
    }
    fn list(&self, status: Option<&str>, limit: usize) -> Result<Vec<Json>> {
        Ok(self
            .rows
            .lock()
            .unwrap()
            .values()
            .rev()
            .filter(|r| status.is_none_or(|s| r["status"] == s))
            .take(limit)
            .cloned()
            .collect())
    }
    #[allow(clippy::too_many_arguments)]
    fn add(
        &self,
        kind: &str,
        source: &str,
        title: Option<&str>,
        dest_dir: Option<&str>,
        options: Option<&JsonMap>,
        start_after: Option<f64>,
        gid: Option<&str>,
    ) -> Result<i64> {
        let mut rows = self.rows.lock().unwrap();
        let id = rows.keys().next_back().copied().unwrap_or(0) + 1;
        rows.insert(id,json!({"id":id,"kind":kind,"source":source,"title":title,"dest_dir":dest_dir,"options":options.cloned().unwrap_or_default(),"gid":gid,"start_after":start_after,"status":if start_after.is_some(){"scheduled"}else{"queued"},"filename":null,"total_bytes":0,"done_bytes":0}));
        Ok(id)
    }
    fn update_by_id(&self, id: i64, fields: &JsonMap) -> Result<()> {
        if let Some(r) = self.rows.lock().unwrap().get_mut(&id) {
            r.as_object_mut().unwrap().extend(fields.clone());
        }
        Ok(())
    }
    fn update_by_gid(&self, gid: &str, fields: &JsonMap) -> Result<()> {
        if let Some(r) = self.by_gid(gid)? {
            self.update_by_id(r["id"].as_i64().unwrap(), fields)?;
        }
        Ok(())
    }
    fn attach_gid(&self, id: i64, gid: &str) -> Result<()> {
        self.update_by_id(
            id,
            json!({"gid":gid,"status":"active"}).as_object().unwrap(),
        )
    }
    #[allow(unused_variables)]
    fn rules_list(&self) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn rules_save(&self, rules: &[Json]) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn max_video_seq(&self) -> Result<i64> {
        Ok(0)
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimlerini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimi_var(&self, gid: &str) -> Result<bool> {
        Ok(false)
    }
    #[allow(unused_variables)]
    fn torrent_dosya_secimlerini_tasi(&self, eski_gid: &str, yeni_gid: &str) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn due_scheduled(&self, now: Option<f64>) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn delete(&self, row_id: i64) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn clear_finished(&self) -> Result<usize> {
        Ok(0)
    }
    #[allow(unused_variables)]
    fn automation_enqueue(&self, gid: &str, action: &str, payload: Option<&JsonMap>) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn automation_jobs(&self, gid: &str, limit: usize) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn automation_claim(&self) -> Result<Option<Json>> {
        Ok(None)
    }
    #[allow(unused_variables)]
    fn automation_jobs_by_id(&self, job_id: i64) -> Result<Option<Json>> {
        Ok(None)
    }
    #[allow(unused_variables)]
    fn automation_update(&self, job_id: i64, fields: &JsonMap) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn automation_retry(&self, job_id: i64) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn automation_cancel(&self, job_id: i64) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn eklenti_listesi(&self) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn eklenti(&self, ad: &str) -> Result<Option<Json>> {
        Ok(None)
    }
    #[allow(unused_variables)]
    fn eklenti_yaz(&self, kayit: &JsonMap) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn eklenti_alan_yaz(&self, ad: &str, alanlar: &JsonMap) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn eklenti_sil(&self, ad: &str) -> Result<()> {
        Ok(())
    }
    #[allow(unused_variables)]
    fn log(&self, level: &str, message: &str, gid: &str) {}
    #[allow(unused_variables)]
    fn recent_events(&self, limit: usize, gid: &str) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn query(&self, sql: &str, params: &[Json]) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn execute(&self, sql: &str, params: &[Json]) -> Result<usize> {
        Ok(0)
    }
}

impl Aria2 for MemoryRpc {
    fn call(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        if *self.offline.lock().unwrap() {
            return Err(AfuError::Engine("offline".into()));
        }
        self.calls.lock().unwrap().push((method.into(), params));
        Ok(json!("OK"))
    }
    fn alive(&self) -> bool {
        !*self.offline.lock().unwrap()
    }
    fn add_uri(&self, uris: &[String], options: Option<&JsonMap>) -> Result<String> {
        self.call("add_uri", vec![json!(uris), json!(options)])?;
        let mut s = self.statuses.lock().unwrap();
        let gid = format!("g{}", s.len() + 1);
        s.insert(
            gid.clone(),
            json!({"gid":gid,"status":"active","files":[],"dir":options.and_then(|o|o.get("dir"))}),
        );
        Ok(gid)
    }
    fn tell_status(&self, gid: &str, _keys: &[&str]) -> Result<Json> {
        if *self.offline.lock().unwrap() {
            return Err(AfuError::Engine("offline".into()));
        }
        self.statuses
            .lock()
            .unwrap()
            .get(gid)
            .cloned()
            .ok_or_else(|| AfuError::NotFound(gid.into()))
    }
    fn tell_active(&self, _keys: &[&str]) -> Result<Vec<Json>> {
        if *self.offline.lock().unwrap() {
            return Err(AfuError::Engine("offline".into()));
        }
        Ok(self.statuses.lock().unwrap().values().cloned().collect())
    }
    fn global_stat(&self) -> Result<Json> {
        Ok(json!({}))
    }
    fn get_global_option(&self) -> Result<JsonMap> {
        Ok(JsonMap::new())
    }
    #[allow(unused_variables)]
    fn add_torrent(&self, torrent_b64: &str, options: Option<&JsonMap>) -> Result<String> {
        self.call("add_torrent", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn add_metalink(&self, metalink_b64: &str, options: Option<&JsonMap>) -> Result<Vec<String>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn pause(&self, gid: &str, force: bool) -> Result<String> {
        self.call("pause", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn unpause(&self, gid: &str) -> Result<String> {
        self.call("unpause", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn remove(&self, gid: &str, force: bool) -> Result<String> {
        self.call("remove", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn remove_result(&self, gid: &str) -> Result<String> {
        self.call("remove_result", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn pause_all(&self) -> Result<String> {
        self.call("pause_all", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn unpause_all(&self) -> Result<String> {
        self.call("unpause_all", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn tell_waiting(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn tell_stopped(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn get_peers(&self, gid: &str) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn get_files(&self, gid: &str) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn get_servers(&self, gid: &str) -> Result<Vec<Json>> {
        Ok(vec![])
    }
    #[allow(unused_variables)]
    fn change_option(&self, gid: &str, options: &JsonMap) -> Result<String> {
        self.call("change_option", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn change_global_option(&self, options: &JsonMap) -> Result<String> {
        self.call("change_global_option", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn change_uri(
        &self,
        gid: &str,
        file_index: i64,
        del_uris: &[String],
        add_uris: &[String],
        position: i64,
    ) -> Result<i64> {
        Ok(1)
    }
    #[allow(unused_variables)]
    fn shutdown(&self, force: bool) -> Result<String> {
        self.call("shutdown", vec![])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn save_session(&self) -> Result<String> {
        self.call("save_session", vec![])?;
        Ok("OK".into())
    }
}
