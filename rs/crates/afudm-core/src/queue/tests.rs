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
    asleep: Mutex<bool>,
    status_reads: Mutex<usize>,
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
fn torrent_existing_root_integrity_for_local_adopted_and_refreshed_jobs() {
    let f = Fixture::new();
    f.m.store
        .set(
            "canli_trackerlar",
            json!("udp://tracker.example.org:1337/announce"),
        )
        .unwrap();
    std::fs::create_dir(f.root.join("Game")).unwrap();
    let torrent = f.root.join("game.torrent");
    std::fs::write(&torrent, b"d4:infod4:name4:Gameee").unwrap();
    crate::torrent::torrent_ekle_ic(
        &f.m,
        json!({"source": torrent, "dest_dir": f.root})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    {
        let calls = f.rpc.calls.lock().unwrap();
        let (_, params) = calls
            .iter()
            .rev()
            .find(|(m, _)| m == "add_torrent")
            .unwrap();
        assert_eq!(params[1]["check-integrity"], "true");
    }
    f.rpc.statuses.lock().unwrap().insert(
        "preview".into(),
        json!({"gid":"preview", "followedBy":["child"]}),
    );
    f.rpc.statuses.lock().unwrap().insert("child".into(), json!({"gid":"child", "bittorrent":{"info":{"name":"Game"}}, "infoHash":"abc", "dir":f.root}));
    crate::torrent::torrent_ekle_ic(
        &f.m,
        json!({"source":"magnet:?xt=urn:btih:abc", "adopt_gid":"preview", "dest_dir": f.root})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    {
        let calls = f.rpc.calls.lock().unwrap();
        let (_, params) = calls
            .iter()
            .rev()
            .find(|(m, _)| m == "change_option")
            .unwrap();
        assert_eq!(params[0], "child");
        assert_eq!(params[1]["check-integrity"], "true");
    }
    assert_eq!(
        crate::torrent::seed_tazele(&f.m, "child").unwrap()["ok"],
        true
    );
    {
        let calls = f.rpc.calls.lock().unwrap();
        let (_, params) = calls.iter().rev().find(|(m, _)| m == "add_uri").unwrap();
        assert_eq!(params[1]["check-integrity"], "true");
    }
    std::fs::write(&torrent, b"d4:infod4:name7:Missingee").unwrap();
    crate::torrent::torrent_ekle_ic(
        &f.m,
        json!({"source": torrent, "dest_dir": f.root})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    let calls = f.rpc.calls.lock().unwrap();
    let (_, params) = calls
        .iter()
        .rev()
        .find(|(m, _)| m == "add_torrent")
        .unwrap();
    assert!(params[1].get("check-integrity").is_none());
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
fn readded_torrent_db_row_survives_stale_hash_when_engine_is_offline() {
    let f = Fixture::new();
    let hash = "0123456789012345678901234567890123456789";
    state(&f.m).unwrap().removed_hashes.insert(hash.into());
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
    f.m.store
        .update_by_id(id, &map(json!({"status":"paused"})))
        .unwrap();
    *f.rpc.offline.lock().unwrap() = true;
    let snap = snapshot(&f.m).unwrap();
    assert_eq!(snap["items"].as_array().unwrap().len(), 1);
    assert_eq!(snap["items"][0]["id"], id);
}

#[test]
fn intentional_magnet_readd_clears_removed_hash() {
    let f = Fixture::new();
    let hash = "0123456789012345678901234567890123456789";
    state(&f.m).unwrap().removed_hashes.insert(hash.into());
    add(
        &f.m,
        &map(json!({"source":format!("magnet:?xt=urn:btih:{hash}")})),
    )
    .unwrap();
    assert!(!state(&f.m).unwrap().removed_hashes.contains(hash));
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
        if method == "aria2.purgeDownloadResult" {
            self.statuses
                .lock()
                .unwrap()
                .retain(|_, s| !["complete", "error", "removed"].contains(&text(&s["status"])));
        }
        Ok(json!("OK"))
    }
    fn sleeping(&self) -> bool {
        *self.asleep.lock().unwrap()
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
        *self.status_reads.lock().unwrap() += 1;
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
        self.call("add_torrent", vec![json!(torrent_b64), json!(options)])?;
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
        self.call("change_option", vec![json!(gid), json!(options)])?;
        Ok("OK".into())
    }
    #[allow(unused_variables)]
    fn change_global_option(&self, options: &JsonMap) -> Result<String> {
        self.call("change_global_option", vec![json!(options)])?;
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

/// Tamamlanma kancasi: her cagrida {"title","size","gid"} yukunu kaydeder.
fn kanca_kaydi(m: &Manager) -> Arc<Mutex<Vec<Json>>> {
    let kayit = Arc::new(Mutex::new(Vec::new()));
    let hedef = Arc::clone(&kayit);
    m.tamamlandi_kancasi_ekle(Box::new(move |yuk: &Json| {
        hedef.lock().unwrap().push(yuk.clone());
    }));
    kayit
}

#[test]
fn tamamlandi_kancalari_dogru_yukle_calisir() {
    let f = Fixture::new();
    let kayit = kanca_kaydi(&f.m);
    tamamlandi(&f.m, "Ornek", 2048, "gid-x");
    let kayit = kayit.lock().unwrap();
    assert_eq!(kayit.len(), 1);
    assert_eq!(kayit[0], json!({"title":"Ornek","size":2048,"gid":"gid-x"}));
}

#[test]
fn snapshot_does_not_process_completion() {
    let f = Fixture::new();
    let gid = f.add("tamam")["gid"].as_str().unwrap().to_string();
    f.rpc.statuses.lock().unwrap().get_mut(&gid).unwrap()["status"] = json!("complete");
    let kayit = kanca_kaydi(&f.m);
    snapshot(&f.m).unwrap();
    assert!(
        kayit.lock().unwrap().is_empty(),
        "snapshot must only read completion"
    );
    assert_ne!(
        f.m.store.by_gid(&gid).unwrap().unwrap()["status"],
        "complete"
    );
}

#[test]
fn video_completion_waits_for_sync_not_snapshot() {
    let f = Fixture::new();
    let kayit = kanca_kaydi(&f.m);
    crate::video::test_tamamlandi_ekle(&f.m, "Klip", 4096, "yt:9");
    snapshot(&f.m).unwrap();
    assert!(kayit.lock().unwrap().is_empty());
}

#[test]
fn video_duraklat_ve_kaldir_kayitlari_gunceller() {
    let f = Fixture::new();
    let dir = f.root.to_string_lossy().to_string();
    f.m.store
        .add(
            "video",
            "https://ornek.test/v",
            None,
            Some(&dir),
            None,
            None,
            Some("yt:1"),
        )
        .unwrap();
    crate::video::test_is_ekle(&f.m, "yt:1", &dir, "klip.mp4", "active");
    assert!(pause(&f.m, "yt:1").unwrap());
    assert_eq!(
        f.m.store.by_gid("yt:1").unwrap().unwrap()["status"],
        "paused"
    );
    assert_eq!(crate::video::video_satirlari(&f.m)[0]["status"], "paused");
    assert!(remove(&f.m, "yt:1", false).unwrap());
    assert!(crate::video::video_satirlari(&f.m).is_empty());
}

#[test]
fn video_tumunu_durdur_yalniz_bitmemis_isleri_durdurur() {
    let f = Fixture::new();
    let dir = f.root.to_string_lossy().to_string();
    for (gid, durum) in [
        ("yt:1", "active"),
        ("yt:2", "waiting"),
        ("yt:3", "complete"),
    ] {
        f.m.store
            .add(
                "video",
                "https://ornek.test/v",
                None,
                Some(&dir),
                None,
                None,
                Some(gid),
            )
            .unwrap();
        crate::video::test_is_ekle(&f.m, gid, &dir, "a.mp4", durum);
    }
    pause_all(&f.m).unwrap();
    let durum_of = |gid: &str| {
        crate::video::video_satirlari(&f.m)
            .into_iter()
            .find(|s| s["gid"].as_str() == Some(gid))
            .unwrap()["status"]
            .clone()
    };
    assert_eq!(durum_of("yt:1"), "paused");
    assert_eq!(durum_of("yt:2"), "paused");
    assert_eq!(durum_of("yt:3"), "complete");
}

#[test]
fn video_yetim_kayitlari_acilista_duraklatilir() {
    let f = Fixture::new();
    let dir = f.root.to_string_lossy().to_string();
    f.m.store
        .add(
            "video",
            "https://ornek.test/v",
            None,
            Some(&dir),
            None,
            None,
            Some("yt:7"),
        )
        .unwrap();
    f.m.store
        .update_by_gid("yt:7", &map(json!({"status":"active"})))
        .unwrap();
    start(&f.m).unwrap();
    assert_eq!(
        f.m.store.by_gid("yt:7").unwrap().unwrap()["status"],
        "paused"
    );
}

#[test]
fn video_kapanista_kayit_durumu_korunur() {
    let f = Fixture::new();
    let dir = f.root.to_string_lossy().to_string();
    crate::video::test_is_ekle(&f.m, "yt:5", &dir, "b.mp4", "active");
    stop(&f.m).unwrap();
    assert_eq!(crate::video::video_satirlari(&f.m)[0]["status"], "active");
}

#[test]
fn video_isi_yinelenen_kontrolunde_canli_sayilir() {
    let f = Fixture::new();
    let dir = f.root.to_string_lossy().to_string();
    f.m.store
        .add(
            "video",
            "https://ornek.test/v",
            None,
            Some(&dir),
            None,
            None,
            Some("yt:4"),
        )
        .unwrap();
    f.m.store
        .update_by_gid("yt:4", &map(json!({"status":"active"})))
        .unwrap();
    crate::video::test_is_ekle(&f.m, "yt:4", &dir, "d.mp4", "active");
    let bulunan = find_duplicate(&f.m, "https://ornek.test/v").unwrap();
    assert_eq!(bulunan.unwrap()["gid"], "yt:4");
}

#[test]
fn dosya_adi_cozumlemesi_python_ile_ayni_sonuc_verir() {
    use super::probe::{clean_title, guess_name, resolve_filename};
    assert_eq!(
        resolve_filename("https://x.test/a%20b.zip", None, None),
        "a b.zip"
    );
    assert_eq!(
        resolve_filename(
            "https://x.test/a",
            Some("attachment; filename=\"ham.txt\"; filename*=UTF-8''%C5%9Fi%20k.pdf"),
            None
        ),
        "şi k.pdf"
    );
    assert_eq!(
        resolve_filename(
            "https://x.test/indir",
            None,
            Some("application/zip; charset=binary")
        ),
        "indir.zip"
    );
    assert_eq!(
        resolve_filename("https://x.test/app-v1.12.0", None, None),
        "app-v1.12.0"
    );
    assert_eq!(resolve_filename("https://x.test/CON", None, None), "_CON");
    assert_eq!(resolve_filename("https://x.test/", None, None), "download");
    assert_eq!(
        resolve_filename("magnet:?xt=urn:btih:abc&dn=Film%2F2026", None, None),
        "Film_2026"
    );
    assert_eq!(guess_name("https://x.test/a%20b.zip"), "a b.zip");
    assert_eq!(clean_title("[METADATA]Ornek"), "Ornek");
    assert_eq!(clean_title("Ornek"), "Ornek");
}

#[test]
fn probe_url_info_yerel_sunucudan_basliklari_okur() {
    use std::io::{Read, Write};
    let dinleyici = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = dinleyici.local_addr().unwrap().port();
    let sunucu = std::thread::spawn(move || {
        let (mut akis, _) = dinleyici.accept().unwrap();
        let mut istek = Vec::new();
        let mut parca = [0u8; 1024];
        while !istek.windows(4).any(|w| w == b"\r\n\r\n") {
            let n = akis.read(&mut parca).unwrap();
            if n == 0 {
                break;
            }
            istek.extend_from_slice(&parca[..n]);
        }
        akis.write_all(
            b"HTTP/1.1 200 OK\r\nContent-Disposition: attachment; filename*=UTF-8''ornek%20dosya.zip\r\nContent-Length: 12\r\nAccept-Ranges: bytes\r\nConnection: close\r\n\r\n",
        )
        .unwrap();
    });
    let f = Fixture::new();
    let url = format!("http://127.0.0.1:{port}/indir");
    let sonuc = probe_url_info(&f.m, &url).unwrap();
    sunucu.join().unwrap();
    assert_eq!(sonuc["ok"], true);
    assert_eq!(sonuc["filename"], "ornek dosya.zip");
    assert_eq!(sonuc["size"], 12);
    assert_eq!(sonuc["resumable"], true);
    assert_eq!(sonuc["final_url"], url.as_str());
}

#[test]
fn probe_url_info_erisilemeyen_ve_http_disi_kaynaklar() {
    let f = Fixture::new();
    let kapali = probe_url_info(&f.m, "http://127.0.0.1:1/dosya.zip").unwrap();
    assert_eq!(kapali["ok"], false);
    assert_eq!(kapali["filename"], "dosya.zip");
    let ftp = probe_url_info(&f.m, "ftp://x.test/a.zip").unwrap();
    assert_eq!(ftp["ok"], false);
    assert_eq!(ftp["filename"], "a.zip");
    assert!(ftp["size"].is_null());
}

#[test]
fn hiz_limiti_ve_gecmis_kaynaklar_ayarlara_gore_doner() {
    let f = Fixture::new();
    f.m.store.set("max_speed_kb", json!(500)).unwrap();
    assert_eq!(hiz_limiti_kb(&f.m, None).unwrap(), 500);
    f.m.store.set("hiz_profili", json!("snail")).unwrap();
    f.m.store.set("snail_speed_kb", json!(100)).unwrap();
    assert_eq!(hiz_limiti_kb(&f.m, None).unwrap(), 100);
    f.m.store.set("hiz_profili", json!("turbo")).unwrap();
    assert_eq!(hiz_limiti_kb(&f.m, None).unwrap(), 0);
    let _ = f.add("gecmis");
    let kaynaklar = gecmis_sources(&f.m, 10).unwrap();
    assert!(kaynaklar.iter().any(|s| s == "https://example.test/gecmis"));
}

#[test]
fn phone_path_uses_engine_before_db_without_filename_guessing() {
    let f = Fixture::new();
    let gid = f.add("phone.bin")["gid"].as_str().unwrap().to_string();
    let engine = f.root.join("engine.bin");
    let fallback = f.root.join("db.bin");
    std::fs::write(&engine, "engine").unwrap();
    std::fs::write(&fallback, "db").unwrap();
    f.m.store
        .update_by_gid(&gid, &map(json!({"path":fallback})))
        .unwrap();
    f.rpc.statuses.lock().unwrap().get_mut(&gid).unwrap()["files"] =
        json!([{"path":""},{"path":engine}]);
    assert_eq!(phone_download_path(&f.m, &gid).unwrap(), Some(engine));
    f.rpc.statuses.lock().unwrap().clear();
    assert_eq!(phone_download_path(&f.m, &gid).unwrap(), Some(fallback));
    f.m.store
        .update_by_gid(&gid, &map(json!({"path":null,"filename":"db.bin"})))
        .unwrap();
    assert_eq!(phone_download_path(&f.m, &gid).unwrap(), None);
}

#[test]
fn folder_resolves_saved_path_outside_default_and_keeps_missing_target() {
    let f = Fixture::new();
    let gid = f.add("app.exe")["gid"].as_str().unwrap().to_string();
    let actual = f.root.join("chosen folder").join("Antigravity IDE.exe");
    std::fs::create_dir_all(actual.parent().unwrap()).unwrap();
    std::fs::write(&actual, "program").unwrap();
    f.m.store.update_by_gid(&gid, &map(json!({"dest_dir":actual.parent(),"filename":"Antigravity IDE.exe","status":"complete"}))).unwrap();
    f.rpc.statuses.lock().unwrap().clear();
    assert_eq!(resolve_item_path(&f.m, &gid).unwrap(), Some(actual.clone()));
    std::fs::remove_file(&actual).unwrap();
    assert_eq!(resolve_item_path(&f.m, &gid).unwrap(), Some(actual));
}

#[test]
fn completed_timestamp_does_not_advance_with_every_sync() {
    let f = Fixture::new();
    let gid = f.add("done.zip")["gid"].as_str().unwrap().to_string();
    f.rpc.statuses.lock().unwrap().get_mut(&gid).unwrap()["status"] = json!("complete");
    sync_aria2(&f.m).unwrap();
    f.m.store
        .update_by_gid(&gid, &map(json!({"finished_at":10.0})))
        .unwrap();
    sync_aria2(&f.m).unwrap();
    assert_eq!(
        f.m.store.by_gid(&gid).unwrap().unwrap()["finished_at"],
        json!(10.0)
    );
}

#[test]
fn sync_persists_completion_once_before_purge_and_snapshot_reads_db() {
    let f = Fixture::new();
    let gid = f.add("done.bin")["gid"].as_str().unwrap().to_string();
    let other = f.add("other.bin")["gid"].as_str().unwrap().to_string();
    f.rpc.statuses.lock().unwrap().get_mut(&gid).unwrap().as_object_mut().unwrap().extend(map(json!({"status":"complete","totalLength":"123","completedLength":"123","files":[{"path":f.root.join("done.bin")}]})));
    let kayit = kanca_kaydi(&f.m);
    // remove/save_session must synchronize before purging even without a poll tick.
    remove(&f.m, &other, false).unwrap();
    sync_aria2(&f.m).unwrap();
    sync_aria2(&f.m).unwrap();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    assert_eq!(row["status"], "complete");
    assert_eq!(row["total_bytes"], 123);
    assert_eq!(row["done_bytes"], 123);
    assert_eq!(row["filename"], "done.bin");
    assert!(row["finished_at"].as_f64().unwrap() > 0.0);
    assert!(f.rpc.statuses.lock().unwrap().get(&gid).is_none());
    assert_eq!(kayit.lock().unwrap().len(), 1);
    let items = snapshot(&f.m).unwrap()["items"].as_array().unwrap().clone();
    let item = items.iter().find(|r| r["gid"] == gid).unwrap();
    assert!(item.get("start_after").is_some());
    assert_eq!(item["status"], "complete");
}

#[test]
fn acilis_kurtarmasi_aria2da_olmayan_bitmemis_kaydi_yeniden_ekler() {
    let f = Fixture::new();
    let gid = f.add("kesik.bin")["gid"].as_str().unwrap().to_string();
    // Motor cokmesi: aria2 oturumu bos kaldi, gid artik motorda yok.
    f.rpc.statuses.lock().unwrap().remove(&gid);
    sync_aria2(&f.m).unwrap();
    let adet_add_uri = f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .filter(|(ad, _)| ad.as_str() == "add_uri")
        .count();
    assert_eq!(adet_add_uri, 2, "ilk ekleme + acilis kurtarmasi");
    let satir = f.m.store.list(None, 10).unwrap();
    assert_eq!(satir.len(), 1);
    let yeni = text(&satir[0]["gid"]).to_string();
    assert!(f.rpc.statuses.lock().unwrap().contains_key(&yeni));
    assert!(state(&f.m).unwrap().kurtarma_bitti);
}

#[test]
fn sync_persists_errors_and_does_not_wake_sleeping_engine() {
    let f = Fixture::new();
    let gid = f.add("error.bin")["gid"].as_str().unwrap().to_string();
    let kayit = kanca_kaydi(&f.m);
    f.rpc
        .statuses
        .lock()
        .unwrap()
        .get_mut(&gid)
        .unwrap()
        .as_object_mut()
        .unwrap()
        .extend(map(
            json!({"status":"error","errorMessage":"failure","completedLength":"12"}),
        ));
    *f.rpc.asleep.lock().unwrap() = true;
    *f.rpc.offline.lock().unwrap() = true;
    sync_aria2(&f.m).unwrap();
    assert_ne!(f.m.store.by_gid(&gid).unwrap().unwrap()["status"], "error");
    *f.rpc.asleep.lock().unwrap() = false;
    *f.rpc.offline.lock().unwrap() = false;
    sync_aria2(&f.m).unwrap();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    assert_eq!(row["error"], "failure");
    assert_eq!(row["done_bytes"], 12);
    assert!(row["finished_at"].as_f64().unwrap() > 0.0);
    assert!(kayit.lock().unwrap().is_empty());
}

#[test]
fn sync_dispatches_video_completion_once() {
    let f = Fixture::new();
    let kayit = kanca_kaydi(&f.m);
    crate::video::test_tamamlandi_ekle(&f.m, "Klip", 4096, "yt:9");
    sync_aria2(&f.m).unwrap();
    sync_aria2(&f.m).unwrap();
    assert_eq!(
        *kayit.lock().unwrap(),
        vec![json!({"title":"Klip","size":4096,"gid":"yt:9"})]
    );
}

#[test]
fn sleeping_video_completion_does_not_query_or_wake_aria2() {
    let f = Fixture::new();
    f.m.store
        .add(
            "video",
            "https://example.test/video",
            Some("Klip"),
            f.root.to_str(),
            None,
            None,
            Some("yt:9"),
        )
        .unwrap();
    let kayit = kanca_kaydi(&f.m);
    *f.rpc.asleep.lock().unwrap() = true;
    crate::video::test_tamamlandi_ekle(&f.m, "Klip", 4096, "yt:9");
    sync_aria2(&f.m).unwrap();
    assert_eq!(kayit.lock().unwrap().len(), 1);
    assert_eq!(
        *f.rpc.status_reads.lock().unwrap(),
        0,
        "completion integrity checks must not wake aria2"
    );
}

#[test]
fn fix8_filename_motor_kokunden_cikamaz() {
    for ad in [
        r"..\..\Startup\x.exe",
        "../../x",
        "C:x.exe",
        "a\0b",
        ".",
        "..",
    ] {
        let f = Fixture::new();
        let sonuc = add(
            &f.m,
            json!({"source":"https://example.test/f", "filename":ad})
                .as_object()
                .unwrap(),
        );
        if sonuc.is_ok() {
            for (ad, params) in f.rpc.calls.lock().unwrap().iter() {
                if ad == "add_uri" {
                    if let Some(out) = params[1]["out"].as_str() {
                        assert!(
                            !out.contains(['/', '\\', ':', '\0']) && out != "." && out != "..",
                            "{out:?}"
                        );
                    }
                }
            }
        }
    }
}

#[test]
fn omniget_403_retries_once_with_preserved_request() {
    let f = Fixture::new();
    let r = add(&f.m, json!({"source":"https://example.test/file.zip","filename":"saved.zip","headers":{"Authorization":"Bearer keep","Referer":"https://example.test/"},"cookies":[{"name":"sid","value":"keep","domain":"example.test"}]}).as_object().unwrap()).unwrap();
    let gid = text(&r["gid"]).to_owned();
    f.rpc.statuses.lock().unwrap().get_mut(&gid).unwrap().as_object_mut().unwrap().extend(map(json!({"status":"error","errorCode":"22","errorMessage":"The response status is not successful. status=403","dir":f.root,"files":[{"path":f.root.join("saved.zip")}]})));
    sync_aria2(&f.m).unwrap();
    let row = f.m.store.by_id(number(&r["id"])).unwrap().unwrap();
    let new_gid = text(&row["gid"]).to_owned();
    assert_ne!(new_gid, gid);
    let calls = f.rpc.calls.lock().unwrap();
    let (_, args) = calls.iter().rev().find(|(n, _)| n == "add_uri").unwrap();
    assert_eq!(args[1]["dir"], json!(f.root));
    assert_eq!(args[1]["out"], "saved.zip");
    let headers = args[1]["header"].as_array().unwrap();
    for value in [
        "Authorization: Bearer keep",
        "Referer: https://example.test/",
        "Cookie: sid=keep",
        "Range: bytes=0-",
        "Sec-Fetch-Mode: navigate",
        "Sec-Fetch-Dest: document",
    ] {
        assert!(headers.contains(&json!(value)), "missing {value}");
    }
    drop(calls);
    f.rpc
        .statuses
        .lock()
        .unwrap()
        .get_mut(&new_gid)
        .unwrap()
        .as_object_mut()
        .unwrap()
        .extend(map(
            json!({"status":"error","errorCode":"22","errorMessage":"status=403"}),
        ));
    sync_aria2(&f.m).unwrap();
    assert_eq!(
        f.m.store.by_id(number(&r["id"])).unwrap().unwrap()["status"],
        "error"
    );
    assert_eq!(
        f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .filter(|(n, _)| n == "add_uri")
            .count(),
        2
    );
}

#[test]
fn omniget_only_real_http_403_is_retried() {
    for (code, message) in [
        ("22", "status=404"),
        ("3", "status=403"),
        ("22", "status=1403"),
    ] {
        let f = Fixture::new();
        let r = f.add("x.zip");
        let gid = text(&r["gid"]);
        f.rpc
            .statuses
            .lock()
            .unwrap()
            .get_mut(gid)
            .unwrap()
            .as_object_mut()
            .unwrap()
            .extend(map(
                json!({"status":"error","errorCode":code,"errorMessage":message}),
            ));
        sync_aria2(&f.m).unwrap();
        assert_eq!(
            f.m.store.by_id(number(&r["id"])).unwrap().unwrap()["gid"],
            gid
        );
    }
}

#[test]
fn omniget_html_error_blocks_completion_and_preserves_file() {
    for (name, headers, body, error) in [
        (
            "x.zip",
            json!({}),
            "\u{feff} \r\n<!DOCTYPE HTML><title>denied</title>",
            true,
        ),
        ("x.zip", json!({}), " \u{feff}<html>denied", true),
        ("x.zip", json!({}), "<HEAD>denied", true),
        ("x.HTML", json!({}), "<html>page", false),
        ("x.htm", json!({}), "<html>page", false),
        (
            "x.zip",
            json!({"Content-Type":"text/html; charset=utf-8"}),
            "<html>page",
            false,
        ),
        ("x.zip", json!({}), "PK binary", false),
    ] {
        let f = Fixture::new();
        let r = add(
            &f.m,
            json!({"source":format!("https://example.test/{name}"),"headers":headers})
                .as_object()
                .unwrap(),
        )
        .unwrap();
        let gid = text(&r["gid"]);
        let path = f.root.join(name);
        std::fs::write(&path, body).unwrap();
        f.rpc.statuses.lock().unwrap().get_mut(gid).unwrap().as_object_mut().unwrap().extend(map(json!({"status":"complete","files":[{"path":path}],"totalLength":body.len().to_string(),"completedLength":body.len().to_string()})));
        let hooks = Arc::new(Mutex::new(0));
        let count = hooks.clone();
        f.m.tamamlandi_kancasi_ekle(Box::new(move |_| *count.lock().unwrap() += 1));
        sync_aria2(&f.m).unwrap();
        sync_aria2(&f.m).unwrap();
        let row = f.m.store.by_gid(gid).unwrap().unwrap();
        assert_eq!(
            row["status"],
            if error { "error" } else { "complete" },
            "{name}: {body}"
        );
        assert_eq!(
            *hooks.lock().unwrap(),
            if error { 0 } else { 1 },
            "{name}: {body}"
        );
        assert_eq!(
            snapshot(&f.m).unwrap()["items"][0]["status"],
            if error { "error" } else { "complete" }
        );
        assert_eq!(std::fs::read_to_string(&path).unwrap(), body);
    }
}

#[test]
fn omniget_corrupt_auth_marker_is_quarantined() {
    let f = Fixture::new();
    let path = f.root.join("aria2.auth-required.json");
    std::fs::write(&path, b"{broken").unwrap();
    start(&f.m).unwrap();
    assert!(!path.exists());
    assert!(std::fs::read_dir(&f.root)
        .unwrap()
        .filter_map(|e| e.ok())
        .any(|e| e
            .file_name()
            .to_string_lossy()
            .starts_with("aria2.auth-required.json.corrupt-")));
}

#[test]
fn omniget_html_content_type_does_not_skip_binary_integrity() {
    let f = Fixture::new();
    let r = add(
        &f.m,
        json!({"source":"https://example.test/x.zip","headers":{"Content-Type":"text/html"}})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    let gid = text(&r["gid"]);
    let path = f.root.join("x.zip");
    std::fs::write(&path, "broken binary").unwrap();
    f.rpc.statuses.lock().unwrap().get_mut(gid).unwrap().as_object_mut().unwrap().extend(map(json!({"status":"complete","files":[{"path":path}],"totalLength":"13","completedLength":"13"})));
    let hooks = Arc::new(Mutex::new(0));
    let count = hooks.clone();
    f.m.tamamlandi_kancasi_ekle(Box::new(move |_| *count.lock().unwrap() += 1));
    sync_aria2(&f.m).unwrap();
    assert_eq!(*hooks.lock().unwrap(), 0);
}

#[test]
fn upload_global_default_and_live_changes() {
    let f = Fixture::new();
    apply_settings(&f.m).unwrap();
    let last_options = || {
        f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .rev()
            .find(|(name, _)| name == "change_global_option")
            .unwrap()
            .1[0]
            .clone()
    };
    assert_eq!(last_options()["max-overall-upload-limit"], "100K");
    for (kb, expected) in [(250, "250K"), (0, "0")] {
        update_settings(&f.m, json!({"max_upload_kb": kb}).as_object().unwrap()).unwrap();
        assert_eq!(last_options()["max-overall-upload-limit"], expected);
    }
    for invalid in [json!(-1), json!(true), json!(1.5), json!("bad")] {
        assert!(
            update_settings(&f.m, json!({"max_upload_kb": invalid}).as_object().unwrap()).is_err()
        );
    }
}
