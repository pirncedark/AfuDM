use super::*;
use afudm_types::{Aria2, NoUi, Store};
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;

#[derive(Default)]
struct MemoryStore {
    rows: Mutex<BTreeMap<i64, Json>>,
    settings: Mutex<JsonMap>,
}

#[derive(Default)]
struct MemoryRpc {
    statuses: Mutex<BTreeMap<String, Json>>,
    waiting: Mutex<Vec<Json>>,
    calls: Mutex<Vec<(String, Vec<Json>)>>,
    offline: Mutex<bool>,
    asleep: Mutex<bool>,
    status_reads: Mutex<usize>,
    alive_override: Mutex<Option<bool>>,
    generation: Mutex<u64>,
    blocked: Mutex<bool>,
    unblock: Condvar,
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
        m.store.set("torrent_dir", json!(root)).unwrap();
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

fn wait_removed(m: &Manager, gid: &str) {
    for _ in 0..200 {
        if m.store
            .by_gid(gid)
            .ok()
            .flatten()
            .is_some_and(|row| row["status"] == "removed")
        {
            return;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

fn wait_removed_id(m: &Manager, id: i64) {
    for _ in 0..200 {
        if m.store
            .by_id(id)
            .ok()
            .flatten()
            .is_some_and(|row| row["status"] == "removed")
        {
            return;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[test]
fn local_torrent_selection_survives_missing_preview() {
    let f = Fixture::new();
    let source = f.root.join("nested.torrent");
    std::fs::write(&source, b"d4:infod4:name4:Packee").unwrap();
    add(
        &f.m,
        &map(json!({"source": source, "dest_dir": f.root,
        "adopt_gid": "missing-gid", "selected_files": [2]})),
    )
    .unwrap();
    let calls = f.rpc.calls.lock().unwrap();
    let (_, params) = calls
        .iter()
        .find(|(method, _)| method == "add_torrent")
        .unwrap();
    assert_eq!(params[1]["select-file"], "2");
}

#[test]
fn torrent_directory_error_reaches_live_and_saved_rows() {
    let f = Fixture::new();
    let gid = "nested-error";
    f.m.store
        .add("torrent", "file.torrent", None, None, None, None, Some(gid))
        .unwrap();
    let status = json!({"gid":gid, "status":"error", "infoHash":"abc", "errorCode":"18",
        "errorMessage":"Failed to make the directory ..."});
    f.rpc
        .statuses
        .lock()
        .unwrap()
        .insert(gid.into(), status.clone());
    sync::collect(&f.m).unwrap();
    let expected = "Windows Denetimli klasör erişimi bu klasöre yazmayı engelledi; AfuDM'i izinli uygulamalara ekleyin.";
    assert_eq!(
        shaping::aria(&f.m, &status).unwrap()["errorMessage"],
        expected
    );
    assert_eq!(f.m.store.by_gid(gid).unwrap().unwrap()["error"], expected);
}

#[test]
fn torrent_local_info_name_is_saved_before_metadata_and_used_in_snapshot() {
    let f = Fixture::new();
    let torrent = f.root.join("unrelated.TORRENT");
    std::fs::write(&torrent, b"d4:infod4:name4:Gameee").unwrap();
    let result = add(
        &f.m,
        json!({"source":torrent, "title":"wrong path", "start_after":4102444800.0})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    let row =
        f.m.store
            .by_id(result["id"].as_i64().unwrap())
            .unwrap()
            .unwrap();
    assert_eq!(row["title"], "Game");
    let gid = "torrent-job";
    f.m.store
        .update_by_id(row_id(&row), &map(json!({"gid":gid})))
        .unwrap();
    let mut status = json!({"gid":gid,"infoHash":"abc","files":[{"path":"/downloads/a-part.bin"}]});
    assert_eq!(shaping::aria(&f.m, &status).unwrap()["title"], "Game");
    status["bittorrent"] = json!({"info":{"name":"Metadata name"}});
    assert_eq!(
        shaping::aria(&f.m, &status).unwrap()["title"],
        "Metadata name"
    );
}

#[test]
fn torrent_directory_setting_applies_to_preview_queue_and_direct_add() {
    let f = Fixture::new();
    let dest = f.root.join("torrents");
    update_settings(&f.m, &map(json!({"torrent_dir":dest}))).unwrap();
    let torrent = f.root.join("game.torrent");
    std::fs::write(&torrent, b"d4:infod4:name4:Gameee").unwrap();
    crate::torrent::torrent_on_ekle(&f.m, torrent.to_str().unwrap()).unwrap();
    crate::torrent::torrent_ekle_ic(&f.m, &map(json!({"source":torrent}))).unwrap();
    let result = add(&f.m, &map(json!({"source":torrent}))).unwrap();
    let row =
        f.m.store
            .by_id(result["id"].as_i64().unwrap())
            .unwrap()
            .unwrap();
    assert_eq!(row["dest_dir"], json!(dest));
    let calls = f.rpc.calls.lock().unwrap();
    let torrent_calls: Vec<_> = calls
        .iter()
        .filter(|(method, _)| method == "add_torrent")
        .collect();
    assert_eq!(torrent_calls.len(), 3);
    for (_, params) in torrent_calls {
        assert_eq!(params[1]["dir"], json!(dest));
    }
    drop(calls);
    assert_eq!(f.add("normal.zip")["kind"], "http");
    let rows = f.m.store.list(None, 20).unwrap();
    assert_eq!(
        rows.iter().find(|r| r["kind"] == "http").unwrap()["dest_dir"],
        json!(f.root)
    );
}

#[test]
fn torrent_explicit_directory_wins_and_adoption_uses_torrent_default() {
    let f = Fixture::new();
    let dest = f.root.join("torrents");
    f.m.store.set("torrent_dir", json!(dest)).unwrap();
    f.rpc
        .statuses
        .lock()
        .unwrap()
        .insert("preview".into(), json!({"gid":"preview"}));
    crate::torrent::torrent_ekle_ic(
        &f.m,
        &map(json!({"source":"magnet:?xt=urn:btih:abc", "adopt_gid":"preview"})),
    )
    .unwrap();
    let calls = f.rpc.calls.lock().unwrap();
    let (_, params) = calls
        .iter()
        .find(|(method, _)| method == "change_option")
        .unwrap();
    assert_eq!(params[1]["dir"], json!(dest));
    drop(calls);
    let chosen = f.root.join("chosen");
    let result = add(
        &f.m,
        &map(json!({"source":"magnet:?xt=urn:btih:def", "dest_dir":chosen})),
    )
    .unwrap();
    let row =
        f.m.store
            .by_id(result["id"].as_i64().unwrap())
            .unwrap()
            .unwrap();
    assert_eq!(row["dest_dir"], json!(chosen));
}

#[test]
fn torrent_restart_without_saved_directory_uses_torrent_setting() {
    let f = Fixture::new();
    let dest = f.root.join("torrents");
    f.m.store.set("torrent_dir", json!(dest)).unwrap();
    let id =
        f.m.store
            .add(
                "torrent",
                "magnet:?xt=urn:btih:abc",
                Some("Game"),
                None,
                None,
                None,
                None,
            )
            .unwrap();
    let row = f.m.store.by_id(id).unwrap().unwrap();
    launch(&f.m, &row).unwrap();
    let calls = f.rpc.calls.lock().unwrap();
    let (_, params) = calls
        .iter()
        .find(|(method, _)| method == "add_uri")
        .unwrap();
    assert_eq!(params[1]["dir"], json!(dest));
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
    wait_removed_id(&f.m, row_id(&row));
    assert_eq!(
        f.m.store.by_id(row_id(&row)).unwrap().unwrap()["status"],
        "removed"
    );
    assert!(!f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(method, _)| method == "remove" || method == "remove_result"));
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
    for _ in 0..200 {
        if !path.exists() {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
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
    wait_removed(&f.m, "parent");
    for _ in 0..200 {
        if !file.exists() && !part.exists() {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(!file.exists());
    assert!(!part.exists());
    assert!(f.root.exists());
    assert_eq!(f.m.store.by_id(id).unwrap().unwrap()["status"], "removed");
    assert!(state(&f.m).unwrap().removed_hashes.contains(hash));
    assert!(!f.rpc.statuses.lock().unwrap().contains_key("child"));
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
fn active_db_row_stays_visible_when_engine_is_offline() {
    let f = Fixture::new();
    let result = f.add("active.bin");
    let gid = result["gid"].as_str().unwrap();
    assert_eq!(f.m.store.by_gid(gid).unwrap().unwrap()["status"], "active");
    *f.rpc.offline.lock().unwrap() = true;
    let snap = snapshot(&f.m).unwrap();
    let items = snap["items"].as_array().unwrap();
    assert!(
        items.iter().any(|item| item["gid"] == gid),
        "active DB row {gid} vanished from snapshot: {items:?}"
    );
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
        let mut blocked = self.blocked.lock().unwrap();
        while *blocked {
            let (next, timed_out) = self
                .unblock
                .wait_timeout(blocked, Duration::from_secs(30))
                .unwrap();
            blocked = next;
            if timed_out.timed_out() && *blocked {
                return Err(AfuError::Engine(
                    "fake RPC timed out after 30 seconds".into(),
                ));
            }
        }
        drop(blocked);
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
    fn generation(&self) -> u64 {
        *self.generation.lock().unwrap()
    }
    fn alive(&self) -> bool {
        self.alive_override
            .lock()
            .unwrap()
            .unwrap_or(!*self.offline.lock().unwrap())
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
            .ok_or_else(|| AfuError::Engine(format!("aria2.tellStatus: GID {gid} is not found")))
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
        if gid.starts_with("row:") || gid.starts_with("local:") {
            return Err(AfuError::Engine(format!("aria2.remove: unknown GID {gid}")));
        }
        self.call("remove", vec![json!(gid)])?;
        self.statuses.lock().unwrap().remove(gid);
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
        if *self.offline.lock().unwrap() {
            return Err(AfuError::Engine("offline".into()));
        }
        Ok(self.waiting.lock().unwrap().clone())
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

fn rpc_block(rpc: &MemoryRpc, block: bool) {
    *rpc.blocked.lock().unwrap() = block;
    if !block {
        rpc.unblock.notify_all();
    }
}

#[test]
fn pause_intent_returns_before_blocked_rpc_and_is_applied_when_rpc_recovers() {
    let f = Fixture::new();
    let gid = f.add("pause-fast.bin")["gid"].as_str().unwrap().to_owned();
    rpc_block(&f.rpc, true);
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::scope(|scope| {
        scope.spawn(|| tx.send(pause(&f.m, &gid)).unwrap());
        let fast_result = rx.recv_timeout(Duration::from_millis(100));
        let returned_fast = fast_result.is_ok();
        let intent_saved = f.m.store.by_gid(&gid).unwrap().unwrap()["status"] == "paused";
        rpc_block(&f.rpc, false);
        let result =
            fast_result.unwrap_or_else(|_| rx.recv_timeout(Duration::from_secs(2)).unwrap());
        assert!(result.unwrap());
        assert!(intent_saved, "pause intent was not saved before the RPC");
        assert!(returned_fast, "pause waited for the blocked RPC");
    });
    for _ in 0..100 {
        if f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .any(|(method, _)| method == "pause")
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(method, _)| method == "pause"));
}

#[test]
fn resume_intent_returns_before_blocked_rpc_and_is_applied_when_rpc_recovers() {
    let f = Fixture::new();
    let gid = f.add("resume-fast.bin")["gid"].as_str().unwrap().to_owned();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    f.m.store
        .update_by_id(row_id(&row), &map(json!({"status":"paused"})))
        .unwrap();
    rpc_block(&f.rpc, true);
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::scope(|scope| {
        scope.spawn(|| tx.send(resume(&f.m, &gid)).unwrap());
        let fast_result = rx.recv_timeout(Duration::from_millis(100));
        let returned_fast = fast_result.is_ok();
        let intent_saved = f.m.store.by_gid(&gid).unwrap().unwrap()["status"] == "active";
        rpc_block(&f.rpc, false);
        let result =
            fast_result.unwrap_or_else(|_| rx.recv_timeout(Duration::from_secs(2)).unwrap());
        assert!(result.unwrap());
        assert!(intent_saved, "resume intent was not saved before the RPC");
        assert!(returned_fast, "resume waited for the blocked RPC");
    });
    for _ in 0..100 {
        if f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .any(|(method, _)| method == "unpause")
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(method, _)| method == "unpause"));
}

#[test]
fn remove_intent_returns_before_blocked_rpc_and_finishes_after_rpc_recovers() {
    let f = Fixture::new();
    let gid = f.add("remove-fast.bin")["gid"].as_str().unwrap().to_owned();
    let path = f.root.join("remove-fast.bin");
    std::fs::write(&path, "kept until motor releases it").unwrap();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    f.m.store
        .update_by_id(row_id(&row), &map(json!({"filename":"remove-fast.bin"})))
        .unwrap();
    rpc_block(&f.rpc, true);
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::scope(|scope| {
        scope.spawn(|| tx.send(remove(&f.m, &gid, true)).unwrap());
        let fast_result = rx.recv_timeout(Duration::from_millis(100));
        let returned_fast = fast_result.is_ok();
        let row = f.m.store.by_gid(&gid).unwrap().unwrap();
        let intent_saved = row["status"] == "removing" || row["status"] == "removed";
        rpc_block(&f.rpc, false);
        let result =
            fast_result.unwrap_or_else(|_| rx.recv_timeout(Duration::from_secs(2)).unwrap());
        assert!(result.unwrap());
        assert!(intent_saved, "remove intent was not saved before the RPC");
        assert!(returned_fast, "remove waited for the blocked RPC");
        for _ in 0..100 {
            if f.m.store.by_gid(&gid).unwrap().unwrap()["status"] == "removed" {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(
            f.m.store.by_gid(&gid).unwrap().unwrap()["status"],
            "removed"
        );
    });
    assert!(
        !path.exists(),
        "delete-files must finish after aria2 releases the file"
    );
    for _ in 0..100 {
        if f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .any(|(method, _)| method == "remove")
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(method, _)| method == "remove"));
}

#[test]
fn delete_retry_keeps_row_pending_while_aria2_sidecar_exists() {
    let f = Fixture::new();
    let target = f.root.join("sidecar-only.bin");
    let sidecar = std::path::PathBuf::from(format!("{}.aria2", target.display()));
    let partial = f.root.join("sidecar-only.bin.part");
    std::fs::write(&sidecar, "aria2 sidecar").unwrap();
    std::fs::write(&partial, "partial file").unwrap();
    assert!(files::delete_targets_pending(
        &f.m,
        &f.root,
        std::slice::from_ref(&target),
        "sidecar-test"
    ));
    std::fs::remove_file(&sidecar).unwrap();
    assert!(files::delete_targets_pending(
        &f.m,
        &f.root,
        std::slice::from_ref(&target),
        "sidecar-test"
    ));
    std::fs::remove_file(&partial).unwrap();
    assert!(!files::delete_targets_pending(
        &f.m,
        &f.root,
        std::slice::from_ref(&target),
        "sidecar-test"
    ));
}

#[test]
fn startup_recovery_never_readds_pending_or_removed_downloads() {
    let f = Fixture::new();
    let pending = f.add("pending-remove.bin");
    let removed = f.add("removed.bin");
    f.m.store
        .update_by_id(number(&pending["id"]), &map(json!({"status":"removing"})))
        .unwrap();
    f.m.store
        .update_by_id(number(&removed["id"]), &map(json!({"status":"removed"})))
        .unwrap();
    f.rpc.statuses.lock().unwrap().clear();
    *f.rpc.generation.lock().unwrap() += 1;
    let adds_before = f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .filter(|(method, _)| method == "add_uri")
        .count();
    sync_aria2(&f.m).unwrap();
    let adds_after = f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .filter(|(method, _)| method == "add_uri")
        .count();
    assert_eq!(
        adds_after, adds_before,
        "pending removals and tombstones must not be recovered"
    );
    for _ in 0..100 {
        if f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .any(|(method, _)| method == "remove")
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(
        f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .any(|(method, _)| method == "remove"),
        "pending removal was not resumed after startup"
    );
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
    assert_eq!(
        guess_name("https://downloader.disk.yandex.ru/disk/opaque?filename=MUGEN%20LEGACY%201.1%20(ACTUALIZADO%202018%20)-FP.rar&disposition=attachment"),
        "MUGEN LEGACY 1.1 (ACTUALIZADO 2018 )-FP.rar"
    );
    assert_eq!(
        guess_name("https://x.test/opaque?response-content-disposition=attachment%3B%20filename%3D%22game%20file.zip%22"),
        "game file.zip"
    );
    assert_eq!(clean_title("[METADATA]Ornek"), "Ornek");
    assert_eq!(clean_title("Ornek"), "Ornek");
}

#[test]
fn retry_torrent_with_missing_adopt_gid_readds_source_and_updates_gid() {
    let f = Fixture::new();
    let id =
        f.m.store
            .add(
                "torrent",
                "magnet:?xt=urn:btih:abc",
                Some("Game"),
                Some(f.root.to_str().unwrap()),
                Some(&map(json!({"adopt_gid":"missing-gid"}))),
                None,
                Some("missing-gid"),
            )
            .unwrap();

    let result = retry(&f.m, id).unwrap();
    let row = f.m.store.by_id(id).unwrap().unwrap();

    assert_eq!(row["gid"], result["gid"]);
    assert_ne!(row["gid"], "missing-gid");
    assert!(f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(method, _)| method == "add_uri"));
}

#[test]
fn unknown_download_size_has_no_remaining_bytes_value() {
    let f = Fixture::new();
    let added = f.add("unknown.zip");
    let gid = added["gid"].as_str().unwrap();
    f.rpc.statuses.lock().unwrap().insert(
        gid.to_string(),
        json!({"gid":gid,"status":"active","totalLength":"0","completedLength":"0","files":[]}),
    );

    let item = snapshot(&f.m).unwrap()["items"][0].clone();
    assert!(item["remaining"].is_null());
}

#[test]
fn active_status_keeps_engine_indicator_alive_after_quick_probe_fails() {
    let f = Fixture::new();
    let added = f.add("busy.zip");
    let gid = added["gid"].as_str().unwrap();
    f.rpc.alive_override.lock().unwrap().replace(false);
    f.rpc.statuses.lock().unwrap().insert(
        gid.to_string(),
        json!({"gid":gid,"status":"active","totalLength":"10","completedLength":"1","files":[]}),
    );

    let snap = snapshot(&f.m).unwrap();
    assert_eq!(snap["engine_ok"], true);
}

#[test]
fn mega_403_uses_saved_page_source_and_has_single_retry_message() {
    use super::safety::{mega_page_source, MEGA_EXPIRED_ERROR};

    let row = json!({"source":"https://userstorage.mega.co.nz/temporary","options":{"headers":{"Referer":"https://mega.nz/file/abc"}}});
    assert_eq!(
        mega_page_source(&row).as_deref(),
        Some("https://mega.nz/file/abc")
    );
    assert_eq!(
        mega_page_source(&json!({"source":"https://userstorage.mega.co.nz/temp","options":{}})),
        None
    );
    let f = Fixture::new();
    let result = add(
        &f.m,
        &map(json!({"source":"https://userstorage.mega.co.nz/temp"})),
    )
    .unwrap();
    let gid = result["gid"].as_str().unwrap();
    f.rpc.statuses.lock().unwrap().insert(
        gid.to_owned(),
        json!({"gid":gid,"status":"error","errorCode":"22","errorMessage":"status=403","totalLength":"0","completedLength":"0","files":[]}),
    );

    sync_aria2(&f.m).unwrap();
    let row =
        f.m.store
            .by_id(result["id"].as_i64().unwrap())
            .unwrap()
            .unwrap();
    assert_eq!(row["error"], MEGA_EXPIRED_ERROR);
    assert_eq!(row["status"], "error");
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
    // Removing one GID must not purge unrelated completed results before the next sync.
    remove(&f.m, &other, false).unwrap();
    wait_removed(&f.m, &other);
    sync_aria2(&f.m).unwrap();
    sync_aria2(&f.m).unwrap();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    assert_eq!(row["status"], "complete");
    assert_eq!(row["total_bytes"], 123);
    assert_eq!(row["done_bytes"], 123);
    assert_eq!(row["filename"], "done.bin");
    assert!(row["finished_at"].as_f64().unwrap() > 0.0);
    assert!(f.rpc.statuses.lock().unwrap().contains_key(&gid));
    assert_eq!(kayit.lock().unwrap().len(), 1);
    let items = snapshot(&f.m).unwrap()["items"].as_array().unwrap().clone();
    let item = items.iter().find(|r| r["gid"] == gid).unwrap();
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
fn motor_yeniden_baslayinca_kaybolan_indirmeler_her_seferinde_geri_eklenir() {
    let f = Fixture::new();
    let gid = f.add("kesik.bin")["gid"].as_str().unwrap().to_string();
    sync_aria2(&f.m).unwrap();
    let add_uri = |f: &Fixture| {
        f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .filter(|(ad, _)| ad.as_str() == "add_uri")
            .count()
    };
    assert_eq!(add_uri(&f), 1, "motorda olan indirme yeniden eklenmez");
    // Motor yeniden basladi (cokme/uyanma), oturum bos: indirme motorda yok.
    f.rpc.statuses.lock().unwrap().clear();
    *f.rpc.generation.lock().unwrap() += 1;
    sync_aria2(&f.m).unwrap();
    assert_eq!(add_uri(&f), 2, "yeniden baslatmadan sonra geri eklendi");
    assert!(f
        .rpc
        .statuses
        .lock()
        .unwrap()
        .contains_key(text(&f.m.store.list(None, 10).unwrap()[0]["gid"])));
    let _ = gid;
    // Ikinci yeniden baslatma da kapsanir.
    f.rpc.statuses.lock().unwrap().clear();
    *f.rpc.generation.lock().unwrap() += 1;
    sync_aria2(&f.m).unwrap();
    assert_eq!(add_uri(&f), 3);
    // Ayni nesilde tekrar senkron gereksiz ekleme yapmaz.
    sync_aria2(&f.m).unwrap();
    assert_eq!(add_uri(&f), 3);
}

#[test]
fn motor_mesgulken_eklenemeyen_indirme_bir_dakika_sonra_yeniden_denenir() {
    let f = Fixture::new();
    f.add("mesgul.bin");
    sync_aria2(&f.m).unwrap();
    let add_uri = |f: &Fixture| {
        f.rpc
            .calls
            .lock()
            .unwrap()
            .iter()
            .filter(|(ad, _)| ad.as_str() == "add_uri")
            .count()
    };
    // Motor yeniden basladi ama mesgul (buyuk dosya ayirirken RPC yanit vermiyor).
    f.rpc.statuses.lock().unwrap().clear();
    *f.rpc.generation.lock().unwrap() += 1;
    *f.rpc.offline.lock().unwrap() = true;
    let _ = sync_aria2(&f.m);
    assert!(state(&f.m).unwrap().kurtarma_son_deneme.is_some());
    *f.rpc.offline.lock().unwrap() = false;
    // Bekleme suresi dolmadan tekrar denenmez.
    sync_aria2(&f.m).unwrap();
    assert_eq!(add_uri(&f), 1);
    // Bir dakika gecince yeniden eklenir ve kurtarma bu nesil icin tamamlanir.
    state(&f.m).unwrap().kurtarma_son_deneme =
        std::time::Instant::now().checked_sub(std::time::Duration::from_secs(61));
    sync_aria2(&f.m).unwrap();
    assert_eq!(add_uri(&f), 2);
    assert!(state(&f.m).unwrap().kurtarma_son_deneme.is_none());
}

#[test]
fn motor_hatasiyla_baslatilamayan_indirme_motor_donunce_geri_eklenir() {
    let f = Fixture::new();
    let gid = f.add("hata.bin")["gid"].as_str().unwrap().to_string();
    let id = f.m.store.by_gid(&gid).unwrap().unwrap()["id"]
        .as_i64()
        .unwrap();
    f.m.store
        .update_by_id(
            id,
            &map(json!({"status":"error","error":"indirme baslatilamadi"})),
        )
        .unwrap();
    f.rpc.statuses.lock().unwrap().clear();
    *f.rpc.generation.lock().unwrap() += 1;
    sync_aria2(&f.m).unwrap();
    let row = f.m.store.by_id(id).unwrap().unwrap();
    assert_eq!(row["status"], "active");
    assert!(row["error"].is_null());
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
    assert_eq!(args[1]["dir"], json!(f.root.join("saved")));
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
fn http_auth_warning_does_not_mislabel_zip_download_as_image() {
    let f = Fixture::new();
    let m = Manager::new(
        Arc::new(afudm_db::SqliteStore::open_in_memory().unwrap()),
        f.rpc.clone(),
        Arc::new(NoUi),
        f.root.clone(),
        f.root.clone(),
    );
    m.store.set("download_dir", json!(f.root)).unwrap();
    let result = add(
        &m,
        json!({"source":"https://example.test/archive.zip"})
            .as_object()
            .unwrap(),
    )
    .unwrap();
    let gid = text(&result["gid"]);
    f.rpc
        .statuses
        .lock()
        .unwrap()
        .get_mut(gid)
        .unwrap()
        .as_object_mut()
        .unwrap()
        .extend(map(
            json!({"status":"error", "errorCode":"22", "errorMessage":"status=401"}),
        ));
    sync_aria2(&m).unwrap();
    sync_aria2(&m).unwrap();
    let events = m.store.recent_events(20, gid).unwrap();
    let warnings: Vec<_> = events.iter().filter(|e| e["level"] == "warn").collect();
    assert_eq!(warnings.len(), 1, "{events:?}");
    let message = warnings[0]["message"].as_str().unwrap();
    assert!(
        !message.contains("Görsel"),
        "a ZIP is not an image: {message}"
    );
    assert!(message.contains("tarayıcıdan"));
    assert_eq!(m.store.by_gid(gid).unwrap().unwrap()["status"], "error");
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

#[test]
fn stopped_metadata_cannot_reclaim_payload_gid_or_progress() {
    let f = Fixture::new();
    let id =
        f.m.store
            .add(
                "torrent",
                "magnet:?xt=urn:btih:abc",
                None,
                None,
                None,
                None,
                Some("old"),
            )
            .unwrap();
    f.m.store
        .update_by_id(id, &map(json!({"status":"active"})))
        .unwrap();
    f.rpc.statuses.lock().unwrap().extend([
        ("a-child".into(),json!({"gid":"a-child","following":"old","infoHash":"abc","status":"active","completedLength":"42"})),
        ("old".into(),json!({"gid":"old","followedBy":["a-child"],"infoHash":"abc","status":"complete","completedLength":"1"}))
    ]);
    for _ in 0..2 {
        sync::collect(&f.m).unwrap();
    }
    let row = f.m.store.by_id(id).unwrap().unwrap();
    assert_eq!(row["gid"], "a-child");
    assert_eq!(row["done_bytes"], 42);
    assert_eq!(row["status"], "active");
}

#[test]
fn sync_clears_previous_error_when_job_recovers() {
    let f = Fixture::new();
    let item = f.add("recovered.bin");
    let gid = text(&item["gid"]);
    f.m.store
        .update_by_gid(
            gid,
            &map(json!({"error":"previous failure","status":"error"})),
        )
        .unwrap();
    // Live active status hides stale DB error immediately before sync runs.
    let live_active = f.rpc.statuses.lock().unwrap().get(gid).unwrap().clone();
    assert_eq!(
        shaping::aria(&f.m, &live_active).unwrap()["errorMessage"],
        ""
    );
    sync::collect(&f.m).unwrap();
    assert!(f.m.store.by_gid(gid).unwrap().unwrap()["error"].is_null());

    // Waiting jobs also clear previous error on sync and in live snapshot shaping.
    let waiting_item = f.add("waiting.bin");
    // Add before any status removal so the fake engine cannot reuse a gid.
    let paused_item = f.add("paused.bin");
    let waiting_gid = text(&waiting_item["gid"]);
    f.rpc.statuses.lock().unwrap().remove(waiting_gid);
    f.m.store
        .update_by_gid(
            waiting_gid,
            &map(json!({"error":"stale waiting error","status":"error"})),
        )
        .unwrap();
    let waiting_status = json!({"gid":waiting_gid,"status":"waiting","files":[]});
    assert_eq!(
        shaping::aria(&f.m, &waiting_status).unwrap()["errorMessage"],
        ""
    );
    f.rpc.waiting.lock().unwrap().push(waiting_status);
    sync::collect(&f.m).unwrap();
    let waiting_row = f.m.store.by_gid(waiting_gid).unwrap().unwrap();
    assert_eq!(waiting_row["status"], "waiting");
    assert!(waiting_row["error"].is_null());

    // Paused jobs retain recorded error until resumed to waiting/active.
    let paused_gid = text(&paused_item["gid"]);
    f.rpc.statuses.lock().unwrap().remove(paused_gid);
    f.m.store
        .update_by_gid(
            paused_gid,
            &map(json!({"error":"kept error","status":"error"})),
        )
        .unwrap();
    f.rpc
        .waiting
        .lock()
        .unwrap()
        .push(json!({"gid":paused_gid,"status":"paused","files":[]}));
    sync::collect(&f.m).unwrap();
    assert_eq!(
        f.m.store.by_gid(paused_gid).unwrap().unwrap()["error"],
        "kept error"
    );
}

#[test]
fn removing_supersedes_an_inflight_pause() {
    let f = Fixture::new();
    let gid = f.add("race.bin")["gid"].as_str().unwrap().to_string();
    rpc_block(&f.rpc, true);
    pause(&f.m, &gid).unwrap();
    remove(&f.m, &gid, false).unwrap();
    let row = f.m.store.by_gid(&gid).unwrap().unwrap();
    assert!(control_action(&row).is_none());
    assert!(pause(&f.m, &gid).is_err());
    rpc_block(&f.rpc, false);
    wait_removed(&f.m, &gid);
    assert_eq!(
        f.m.store.by_gid(&gid).unwrap().unwrap()["status"],
        "removed"
    );
}

#[test]
fn permanent_rpc_errors_release_control_and_removal_intents() {
    let f = Fixture::new();
    let first = f.add("pause.bin")["gid"].as_str().unwrap().to_string();
    let second = f.add("remove.bin")["gid"].as_str().unwrap().to_string();
    *f.rpc.offline.lock().unwrap() = true;
    pause(&f.m, &first).unwrap();
    remove(&f.m, &second, false).unwrap();
    for _ in 0..400 {
        if [&first, &second]
            .iter()
            .all(|gid| f.m.store.by_gid(gid).unwrap().unwrap()["status"] == "error")
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    for gid in [&first, &second] {
        let row = f.m.store.by_gid(gid).unwrap().unwrap();
        assert_eq!(row["status"], "error");
        assert!(!text(&row["error"]).is_empty());
        assert!(control_action(&row).is_none());
        assert!(!state(&f.m).unwrap().removed_gids.contains(gid));
    }
    *f.rpc.offline.lock().unwrap() = false;
    sync::collect(&f.m).unwrap();
    let snap = snapshot(&f.m).unwrap();
    let failed = snap["items"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["gid"] == second)
        .unwrap();
    assert_eq!(failed["status"], "error");
    assert!(!text(&failed["errorMessage"]).is_empty());
}

#[test]
fn retry_releases_video_worker_before_relaunch() {
    let f = Fixture::new();
    let old = "yt:7";
    // Offline replacement avoids launching an external downloader in this fixture.
    let id =
        f.m.store
            .add(
                "http",
                "https://example.test/a",
                None,
                Some(f.root.to_str().unwrap()),
                None,
                None,
                Some(old),
            )
            .unwrap();
    crate::video::test_is_ekle(&f.m, old, f.root.to_str().unwrap(), "test.mp4", "paused");
    retry(&f.m, id).unwrap();
    assert!(!crate::video::gidler(&f.m).contains(old));
    assert!(!f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(c, _)| c == "remove_result"));
}

#[test]
fn resolve_prefers_existing_output_when_merged_candidate_is_missing() {
    let f = Fixture::new();
    let id =
        f.m.store
            .add(
                "video",
                "video",
                None,
                Some(f.root.to_str().unwrap()),
                None,
                None,
                Some("yt:1"),
            )
            .unwrap();
    let name = "clip.f123.mp4";
    f.m.store
        .update_by_id(id, &map(json!({"filename":name})))
        .unwrap();
    let target = f.root.join(name);
    std::fs::write(&target, "test").unwrap();
    assert_eq!(files::resolve(&f.m, "yt:1").unwrap().unwrap(), target);
}

#[test]
fn failed_final_sync_still_shuts_down_and_clears_state() {
    let f = Fixture::new();
    state(&f.m).unwrap().started = true;
    let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _guard = f.m.kilit.lock().unwrap();
        panic!("simulate poisoned synchronization lock");
    }));
    assert!(stop(&f.m).is_err());
    assert!(!state(&f.m).unwrap().started);
    assert!(f
        .rpc
        .calls
        .lock()
        .unwrap()
        .iter()
        .any(|(c, _)| c == "shutdown"));
}

#[test]
fn torrent_partial_selection_saves_gid_sets_allocation_and_cleans_unselected() {
    let root = std::env::temp_dir().join(format!(
        "afudm-tselect-{}-{}",
        std::process::id(),
        rand::random::<u64>()
    ));
    std::fs::create_dir_all(&root).unwrap();
    let torrent_bytes = b"d4:infod5:filesld6:lengthi10e4:pathl7:sub.dir5:a.bineed6:lengthi10e4:pathl5:b.bineee4:name4:Packee";
    let source = root.join("pack.torrent");
    std::fs::write(&source, torrent_bytes).unwrap();

    // 1) Partial selection: select-file + file-allocation=none + saved on new gid + cleans unselected.
    let rpc = Arc::new(MemoryRpc::default());
    let store = Arc::new(afudm_db::SqliteStore::open_in_memory().unwrap());
    let m = Manager::new(
        store.clone(),
        rpc.clone(),
        Arc::new(NoUi),
        root.clone(),
        root.clone(),
    );
    m.store.set("download_dir", json!(root)).unwrap();
    m.store.set("torrent_dir", json!(root)).unwrap();

    let added = add(
        &m,
        &map(json!({"source": source, "dest_dir": root, "selected_files": [2]})),
    )
    .unwrap();
    let gid = text(&added["gid"]).to_owned();
    assert_eq!(store.torrent_dosya_secimleri(&gid).unwrap(), vec![2]);
    {
        let calls = rpc.calls.lock().unwrap();
        let (_, params) = calls.iter().find(|(n, _)| n == "add_torrent").unwrap();
        assert_eq!(params[1]["select-file"], "2");
        assert_eq!(params[1]["file-allocation"], "none");
    }

    let pack_dir = root.join("Pack");
    let sub_dir = pack_dir.join("sub.dir");
    std::fs::create_dir_all(&sub_dir).unwrap();
    let unselected_file = sub_dir.join("a.bin");
    let selected_file = pack_dir.join("b.bin");
    let outside_file = root
        .parent()
        .unwrap()
        .join(format!("afudm-outside-{}.bin", rand::random::<u64>()));
    std::fs::write(&unselected_file, b"pad").unwrap();
    std::fs::write(&selected_file, b"keep").unwrap();
    std::fs::write(&outside_file, b"outside").unwrap();

    // Forward slashes test canonical path handling on Windows too.
    let fwd_unselected = unselected_file.to_string_lossy().replace('\\', "/");
    rpc.statuses.lock().unwrap().insert(
        gid.clone(),
        json!({
            "gid": gid,
            "status": "complete",
            "infoHash": "0123456789abcdef0123456789abcdef01234567",
            "dir": root,
            "totalLength": "10",
            "completedLength": "10",
            "files": [
                {"index": "1", "path": fwd_unselected, "selected": "false"},
                {"index": "2", "path": selected_file, "selected": "true"},
                {"index": "3", "path": outside_file, "selected": "false"}
            ]
        }),
    );
    sync::collect(&m).unwrap();
    assert!(!unselected_file.exists());
    assert!(!sub_dir.exists());
    assert!(selected_file.exists());
    assert!(outside_file.exists());
    let _ = std::fs::remove_file(&outside_file);

    // 2) Full selection: select-file set, file-allocation NOT forced to none.
    let rpc_full = Arc::new(MemoryRpc::default());
    let store_full = Arc::new(afudm_db::SqliteStore::open_in_memory().unwrap());
    let m_full = Manager::new(
        store_full,
        rpc_full.clone(),
        Arc::new(NoUi),
        root.clone(),
        root.clone(),
    );
    m_full.store.set("download_dir", json!(root)).unwrap();
    m_full.store.set("torrent_dir", json!(root)).unwrap();
    add(
        &m_full,
        &map(json!({"source": source, "dest_dir": root, "selected_files": [1, 2]})),
    )
    .unwrap();
    let calls = rpc_full.calls.lock().unwrap();
    let (_, params) = calls.iter().find(|(n, _)| n == "add_torrent").unwrap();
    assert_eq!(params[1]["select-file"], "1,2");
    assert!(params[1].get("file-allocation").is_none());

    let _ = std::fs::remove_dir_all(&root);
}
