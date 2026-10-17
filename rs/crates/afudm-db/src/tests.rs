use super::*;
use afudm_types::{JsonMap, Store};
use serde_json::json;

#[test]
fn real_database_byte_copy_preserves_python_table_counts() {
    // Only filesystem copies touch the original; every SQLite connection uses tempdir.
    let source = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(4)
        .unwrap()
        .join("AfuDM/data");
    let temporary = tempfile::tempdir().unwrap();
    for name in ["afudm.db", "afudm.db-wal", "afudm.db-shm"] {
        let original = source.join(name);
        if original.exists() {
            std::fs::copy(original, temporary.path().join(name)).unwrap();
        }
    }
    let copy = temporary.path().join("afudm.db");
    assert!(copy.is_file(), "Source database was not available to copy");
    let counts = || {
        let output = std::process::Command::new("python")
            .args(["-c", r#"import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1])
assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
tables=[r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print(json.dumps({t:c.execute('select count(*) from "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}))
c.close()
"#]).arg(&copy).output().unwrap();
        assert!(output.status.success(), "Python copy verification failed");
        serde_json::from_slice::<serde_json::Value>(&output.stdout).unwrap()
    };
    let before = counts();
    let store = SqliteStore::open(&copy).unwrap();
    assert_eq!(
        store.query("PRAGMA user_version", &[]).unwrap()[0]["user_version"],
        10
    );
    drop(store);
    let after = counts();
    assert_eq!(
        before, after,
        "Opening the copy must preserve every table row count"
    );
    println!("Copied database: Python/Rust row counts match: {after}");
}

#[test]
fn store_settings_downloads_and_events() {
    let s = SqliteStore::open_in_memory().unwrap();
    assert_eq!(
        s.query("PRAGMA user_version", &[]).unwrap()[0]["user_version"],
        10
    );
    assert_eq!(s.get("max_concurrent").unwrap(), Some(json!(5)));
    s.set("custom", json!({"a": [1, true]})).unwrap();
    assert_eq!(s.all_settings().unwrap()["custom"], json!({"a": [1,true]}));
    let id = s
        .add(
            "http",
            "https://example.com/a",
            None,
            None,
            Some(&JsonMap::new()),
            None,
            None,
        )
        .unwrap();
    assert_eq!(s.by_id(id).unwrap().unwrap()["options"], json!({}));
    s.attach_gid(id, "yt:8").unwrap();
    assert_eq!(s.max_video_seq().unwrap(), 8);
    s.update_by_gid("yt:8", json!({"status":"complete"}).as_object().unwrap())
        .unwrap();
    assert_eq!(s.by_gid("yt:8").unwrap().unwrap()["status"], "complete");
    assert_eq!(s.list(Some("complete"), 10).unwrap().len(), 1);
    s.log("info", "test", "yt:8");
    assert_eq!(s.recent_events(1, "yt:8").unwrap()[0]["message"], "test");
    assert_eq!(s.clear_finished().unwrap(), 1);
    assert!(s.by_id(id).unwrap().is_none());
}

#[test]
fn settings_normalization_and_portable_paths() {
    let c = json!({"api_port":" 6812 ", "clipboard_exts":".ZIP;mp4 zip", "max_concurrent":20.0});
    let v = settings::validate(c.as_object().unwrap(), &JsonMap::new()).unwrap();
    assert_eq!(v["api_port"], 6812);
    assert_eq!(v["clipboard_exts"], "zip,mp4");
    assert!(settings::validate(
        json!({"api_port":true}).as_object().unwrap(),
        &JsonMap::new()
    )
    .is_err());
    assert_eq!(settings::default_settings()["split"], 64);
    let root = std::path::Path::new("portable");
    assert_eq!(
        paths::db_path(&paths::data_dir(root)),
        root.join("data/afudm.db")
    );
    assert_eq!(paths::token_file(root), root.join("api_token.txt"));
    assert_eq!(paths::endpoint_file(root), root.join("api_endpoint.json"));
    assert!(paths::default_download_dir().ends_with("downloads"));
}

fn obj(v: serde_json::Value) -> JsonMap {
    v.as_object().unwrap().clone()
}

#[test]
fn rules_are_ordered_and_failed_replace_rolls_back() {
    let s = SqliteStore::open_in_memory().unwrap();
    s.rules_save(&[
        json!({"id":"b","name":"B","active":false}),
        json!({"id":"a","name":"A","conditions":[1]}),
    ])
    .unwrap();
    let before = s.rules_list().unwrap();
    assert_eq!(before[0]["id"], "b");
    assert_eq!(before[0]["active"], false);
    assert_eq!(before[1]["conditions"], json!([1]));
    assert!(s.rules_save(&[json!({"id":"bad"})]).is_err());
    assert_eq!(s.rules_list().unwrap(), before);
    s.rules_save(&[]).unwrap();
    assert!(s.rules_list().unwrap().is_empty());
}

#[test]
fn scheduling_selections_queries_and_json_values() {
    let s = SqliteStore::open_in_memory().unwrap();
    let id = s
        .add(
            "torrent",
            "magnet:x",
            Some("name"),
            Some("dir"),
            Some(&obj(json!({"split":4}))),
            Some(100.0),
            Some("old"),
        )
        .unwrap();
    assert!(s.due_scheduled(Some(99.0)).unwrap().is_empty());
    assert_eq!(s.due_scheduled(Some(100.0)).unwrap().len(), 1);
    s.update_by_id(id, &obj(json!({"options":"{\"headers\":[]}"})))
        .unwrap();
    assert_eq!(
        s.list(None, 10).unwrap()[0]["options"],
        json!({"headers":[]})
    );
    s.update_by_id(id, &JsonMap::new()).unwrap();
    assert!(!s.torrent_dosya_secimi_var("old").unwrap());
    s.torrent_dosya_secimlerini_kaydet("old", &[3, 1, 3])
        .unwrap();
    assert_eq!(s.torrent_dosya_secimleri("old").unwrap(), vec![1, 3]);
    assert!(s.torrent_dosya_secimi_var("old").unwrap());
    s.torrent_dosya_secimlerini_tasi("old", "new").unwrap();
    assert!(s.torrent_dosya_secimi_var("new").unwrap());
    s.torrent_dosya_secimlerini_kaydet("new", &[]).unwrap();
    assert!(s.torrent_dosya_secimi_var("new").unwrap());
    assert!(s.torrent_dosya_secimleri("new").unwrap().is_empty());
    s.delete(id).unwrap();
    assert!(s.by_gid("old").unwrap().is_none());
    assert_eq!(
        s.query(
            "SELECT ? AS n,? AS b,? AS o,? AS s,? AS f",
            &[
                json!(null),
                json!(true),
                json!({"a":1}),
                json!("x' OR 1=1"),
                json!(1.5)
            ]
        )
        .unwrap()[0],
        json!({"n":null,"b":1,"o":"{\"a\":1}","s":"x' OR 1=1","f":1.5})
    );
    assert!(s.execute("SELECT syntax-error", &[]).is_err());
    s.execute(
        "UPDATE settings SET value='plain' WHERE key='language'",
        &[],
    )
    .unwrap();
    assert_eq!(s.get("language").unwrap(), Some(json!("plain")));
    s.execute("DELETE FROM settings WHERE key='language'", &[])
        .unwrap();
    assert_eq!(s.get("language").unwrap(), Some(json!("auto")));
    assert_eq!(s.get("missing").unwrap(), None);
    s.add("video", "x", None, None, None, None, Some("yt:bad"))
        .unwrap();
    assert_eq!(s.max_video_seq().unwrap(), 0);
    s.log("info", "no gid", "");
    assert_eq!(s.recent_events(2, "").unwrap()[0]["gid"], json!(null));
    s.execute("DROP TABLE events", &[]).unwrap();
    s.log("info", "does not throw", "");
}

#[test]
fn durable_automation_resume_retry_cancel() {
    let s = SqliteStore::open_in_memory().unwrap();
    assert!(s.automation_claim().unwrap().is_none());
    s.automation_enqueue("g", "checksum", Some(&obj(json!({"a":1}))))
        .unwrap();
    s.automation_enqueue("g", "checksum", None).unwrap();
    assert_eq!(s.automation_jobs("g", 0).unwrap().len(), 1);
    let job = s.automation_claim().unwrap().unwrap();
    let id = job["id"].as_i64().unwrap();
    assert_eq!(job["payload"], json!({"a":1}));
    assert_eq!(job["attempt"], 1);
    assert_eq!(s.automation_claim().unwrap().unwrap()["attempt"], 2);
    s.automation_update(
        id,
        &obj(json!({"status":"failed","progress":80,"error":"bad","finished_at":5})),
    )
    .unwrap();
    s.automation_retry(id).unwrap();
    let job = s.automation_jobs_by_id(id).unwrap().unwrap();
    assert_eq!(job["status"], "queued");
    assert_eq!(job["progress"], 0);
    assert!(job["error"].is_null());
    assert_eq!(job["attempt"], 2);
    s.automation_cancel(id).unwrap();
    assert_eq!(s.automation_jobs("", 1).unwrap()[0]["status"], "cancelled");
    assert!(s.automation_claim().unwrap().is_none());
    assert!(s.automation_jobs_by_id(-1).unwrap().is_none());
    s.execute("UPDATE automation_jobs SET payload='broken'", &[])
        .unwrap();
    assert_eq!(
        s.automation_jobs_by_id(id).unwrap().unwrap()["payload"],
        json!({})
    );
    s.automation_update(id, &JsonMap::new()).unwrap();
}

#[test]
fn plugins_preserve_install_time_decode_and_filter_updates() {
    let s = SqliteStore::open_in_memory().unwrap();
    s.eklenti_yaz(&obj(json!({"ad":"plug","manifest":{"a":1},"izinler":["read"],"etkin":true,"kurulum_at":123,"sha256":"abc","son_hata":"ö".repeat(600)}))).unwrap();
    let p = s.eklenti("plug").unwrap().unwrap();
    assert_eq!(p["kurulum_at"], 123.0);
    assert_eq!(p["manifest"], json!({"a":1}));
    assert_eq!(p["etkin"], true);
    assert_eq!(p["son_hata"].as_str().unwrap().chars().count(), 500);
    s.eklenti_yaz(&obj(json!({"ad":"plug","surum":"2","kurulum_at":456})))
        .unwrap();
    assert_eq!(s.eklenti("plug").unwrap().unwrap()["kurulum_at"], 123.0);
    s.eklenti_alan_yaz(
        "plug",
        &obj(
            json!({"not_column":"ignored","ayarlar":{"secret":"test"},"etkin":true,"sha256":"xyz"}),
        ),
    )
    .unwrap();
    let p = &s.eklenti_listesi().unwrap()[0];
    assert_eq!(p["ayarlar"], json!({"secret":"test"}));
    assert_eq!(p["sha256"], "xyz");
    s.eklenti_alan_yaz("plug", &obj(json!({"ignored":1})))
        .unwrap();
    s.execute(
        "UPDATE plugins SET manifest='bad',izinler='null',domainler='bad',ayarlar='null'",
        &[],
    )
    .unwrap();
    let p = s.eklenti("plug").unwrap().unwrap();
    assert_eq!(p["manifest"], json!({}));
    assert_eq!(p["izinler"], json!([]));
    assert_eq!(p["domainler"], json!([]));
    assert_eq!(p["ayarlar"], json!({}));
    s.eklenti_sil("plug").unwrap();
    assert!(s.eklenti("plug").unwrap().is_none());
    assert!(s.eklenti_yaz(&JsonMap::new()).is_err());
}

#[test]
fn migrations_zero_two_four_and_ten_preserve_records_and_reopen() {
    let dir = tempfile::tempdir().unwrap();
    for version in [0, 2, 4, 10] {
        let path = dir.path().join(format!("v{version}.db"));
        let s = SqliteStore::open(&path).unwrap();
        s.set("custom", json!("kept")).unwrap();
        s.add("http", "kept", None, None, None, None, Some("g"))
            .unwrap();
        s.log("info", "kept", "g");
        s.set("api_port", json!(6817)).unwrap();
        s.execute("PRAGMA user_version=0", &[]).unwrap();
        drop(s);
        let conn = rusqlite::Connection::open(&path).unwrap();
        if version < 3 {
            conn.execute_batch("ALTER TABLE events DROP COLUMN gid")
                .unwrap();
        }
        if version < 10 {
            conn.execute_batch("ALTER TABLE plugins DROP COLUMN sha256")
                .unwrap();
        }
        conn.pragma_update(None, "user_version", version).unwrap();
        drop(conn);
        for _ in 0..2 {
            let s = SqliteStore::open(&path).unwrap();
            assert_eq!(s.by_gid("g").unwrap().unwrap()["source"], "kept");
            assert_eq!(s.get("custom").unwrap(), Some(json!("kept")));
            assert_eq!(s.get("api_port").unwrap(), Some(json!(6817)));
            assert_eq!(s.recent_events(1, "").unwrap()[0]["message"], "kept");
            assert_eq!(
                s.query("PRAGMA user_version", &[]).unwrap()[0]["user_version"],
                10
            );
            assert_eq!(
                s.query("PRAGMA journal_mode", &[]).unwrap()[0]["journal_mode"],
                "wal"
            );
        }
    }
}

#[test]
fn legacy_v2_existing_gid_and_auto_accept_migration() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("old.db");
    let c = rusqlite::Connection::open(&path).unwrap();
    c.execute_batch("CREATE TABLE events(id INTEGER PRIMARY KEY, at REAL NOT NULL,level TEXT NOT NULL,message TEXT NOT NULL,gid TEXT); INSERT INTO events VALUES(1,1,'info','kept','gid');CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);INSERT INTO settings VALUES('kaydetme_penceresi','true');PRAGMA user_version=2;").unwrap();
    drop(c);
    let s = SqliteStore::open(&path).unwrap();
    assert_eq!(s.get("kaydetme_penceresi").unwrap(), Some(json!(false)));
    assert_eq!(s.get("auto_accept_migrated").unwrap(), Some(json!(true)));
    assert_eq!(s.recent_events(1, "gid").unwrap()[0]["message"], "kept");
    s.set("kaydetme_penceresi", json!(true)).unwrap();
    drop(s);
    let s = SqliteStore::open(&path).unwrap();
    assert_eq!(s.get("kaydetme_penceresi").unwrap(), Some(json!(true)));
}

#[test]
fn shared_store_is_send_sync_and_serializes_concurrent_writes() {
    let s = std::sync::Arc::new(SqliteStore::open_in_memory().unwrap());
    let mut threads = Vec::new();
    for n in 0..8 {
        let s = s.clone();
        threads.push(std::thread::spawn(move || {
            for i in 0..20 {
                s.add("http", &format!("{n}:{i}"), None, None, None, None, None)
                    .unwrap();
            }
        }));
    }
    for t in threads {
        t.join().unwrap();
    }
    assert_eq!(s.list(None, 1000).unwrap().len(), 160);
}

#[test]
fn settings_boundaries_normalize_and_report_all_without_secrets() {
    for (key, lo, hi, err) in [
        ("api_port", 1024, 65535, "err.portRange"),
        ("api_listen_port", 1024, 65535, "err.portRange"),
        ("snail_speed_kb", 1, 1_000_000, "err.snailRange"),
        ("max_concurrent", 1, 20, "err.invalidValue"),
    ] {
        for good in [
            json!(lo),
            json!(hi),
            json!(format!(" +{lo} ")),
            json!(lo as f64),
        ] {
            assert!(
                settings::validate(&JsonMap::from_iter([(key.into(), good)]), &JsonMap::new())
                    .is_ok()
            );
        }
        for bad in [
            json!(lo - 1),
            json!(hi + 1),
            json!(true),
            json!(1.1),
            json!(null),
            json!("abc"),
        ] {
            let e = settings::validate(&JsonMap::from_iter([(key.into(), bad)]), &JsonMap::new())
                .unwrap_err()
                .to_string();
            assert!(e.contains(err));
            assert!(e.contains(key));
        }
    }
    let changes = obj(json!({"proxy":"ftp://secret@host:7","api_port":1,"snail_speed_kb":0}));
    let err = settings::validate(&changes, &JsonMap::new())
        .unwrap_err()
        .to_string();
    assert!(!err.contains("secret"));
    let errors: serde_json::Value = serde_json::from_str(&err).unwrap();
    assert_eq!(errors.as_array().unwrap().len(), 3);
    for (value, error) in [
        ("http://h:0", "err.proxyPort"),
        ("h", "err.proxyFormat"),
        ("ftp://h:4", "err.proxyScheme"),
    ] {
        assert!(
            settings::validate(&obj(json!({"proxy":value})), &JsonMap::new())
                .unwrap_err()
                .to_string()
                .contains(error)
        );
    }
    assert!(
        settings::validate(&obj(json!({"proxy":"a".repeat(1025)})), &JsonMap::new())
            .unwrap_err()
            .to_string()
            .contains("err.proxyLong")
    );
    assert_eq!(
        settings::proxy_maskele(&json!(" socks5://user:pass@host:1080 ")),
        "socks5://host:1080"
    );
    assert_eq!(settings::proxy_maskele(&json!("invalid")), "<proxy>");
    assert_eq!(settings::proxy_maskele(&json!(null)), "");
    for bad in ["*.zip", "a/b", ".", "中文", "z".repeat(25).as_str()] {
        assert!(settings::validate(&obj(json!({"clipboard_exts":bad})), &JsonMap::new()).is_err());
    }
    let changes = obj(
        json!({"clipboard_exts":[".ZIP","mp4","zip"],"ag_konumlari":["//Nas/share/","\\\\nas\\SHARE","\\\\other\\disk"],"arbitrary":[1,2]}),
    );
    let normalized = settings::validate(&changes, &obj(json!({"existing":1}))).unwrap();
    assert_eq!(normalized["clipboard_exts"], "zip,mp4");
    assert_eq!(
        normalized["ag_konumlari"],
        "\\\\Nas\\share\n\\\\other\\disk"
    );
    assert_eq!(normalized.len(), 3);
    for bad in [
        "C:/local",
        "\\\\server",
        "\\\\server\\a?",
        "\\\\server\\\\share",
    ] {
        assert!(settings::validate(&obj(json!({"ag_konumlari":bad})), &JsonMap::new()).is_err());
    }
}

#[test]
fn categories_names_folder_tree_network_and_last_folder() {
    use kaydet::*;
    for (url, expected) in [
        ("https://a/film.mkv", "video"),
        ("https://a/a.mp3?x=1", "muzik"),
        ("https://a/a.pdf", "belge"),
        ("https://a/a.exe", "program"),
        ("https://a/a.tar.gz", "arsiv"),
        ("https://a/a.JPEG", "resim"),
        ("MAGNET:?x=1", "torrent"),
        ("https://a/indir?dosya=a.mp4", "genel"),
    ] {
        assert_eq!(kategori_tahmin(url, "", ""), expected);
    }
    assert_eq!(kategori_tahmin("https://a/watch", "video", ""), "video");
    assert_eq!(kategori_tahmin("https://a/a.mp3", "", "file.pdf"), "belge");
    assert!(kategori_klasoru("base", "video").ends_with("Video"));
    assert!(kategori_klasoru("base", "bad").ends_with("Genel"));
    assert_eq!(
        guvenli_dosya_adi("..\\..\\sistem<>:\"|?*.exe"),
        ".._.._sistem_______.exe"
    );
    assert_eq!(guvenli_dosya_adi("CON.txt"), "_CON.txt");
    assert_eq!(guvenli_dosya_adi("   "), "");
    assert_eq!(guvenli_dosya_adi("file. . "), "file");
    assert_eq!(
        guvenli_dosya_adi(&format!("{}.zip", "a".repeat(300)))
            .chars()
            .count(),
        200
    );
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_str().unwrap();
    std::fs::create_dir_all(dir.path().join("Filmler/2025")).unwrap();
    std::fs::create_dir(dir.path().join("bos")).unwrap();
    std::fs::create_dir(dir.path().join(".hidden")).unwrap();
    std::fs::write(dir.path().join("file.txt"), "x").unwrap();
    let rows = alt_klasorler(root, 500).unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0]["ad"], "bos");
    assert_eq!(rows[1]["alt"], true);
    assert_eq!(alt_klasorler(root, 1).unwrap().len(), 1);
    assert!(alt_klasorler("not-existing-team-b", 500).is_err());
    let made = klasor_olustur(root, "a/b").unwrap();
    assert!(std::path::Path::new(&made).is_dir());
    assert_eq!(klasor_olustur(root, "a/b").unwrap(), made);
    assert!(klasor_olustur(root, " ").is_err());
    let shortcuts = kisayollar(&dir.path().join("downloads").to_string_lossy(), "");
    assert_eq!(shortcuts[0]["anahtar"], "afudm");
    assert!(ag_yolu_mu("\\\\server\\share"));
    assert!(!ag_yolu_mu("C:/a"));
    assert_eq!(
        ag_konumlari("\\\\a\\b\nC:/x\n\\\\a\\b\\\n"),
        vec!["\\\\a\\b"]
    );
    assert_eq!(ag_konumu_dogrula("").unwrap_err().to_string(), "bos yol");
    assert!(ag_konumu_dogrula("C:/x").is_err());
    let s = SqliteStore::open_in_memory().unwrap();
    son_klasoru_hatirla(
        &s,
        root,
        &obj(json!({"dest_dir":made,"folder_edited":false})),
    )
    .unwrap();
    assert_eq!(son_klasor(&s, root).unwrap(), "");
    son_klasoru_hatirla(
        &s,
        root,
        &obj(json!({"dest_dir":made,"folder_edited":true})),
    )
    .unwrap();
    assert_eq!(son_klasor(&s, root).unwrap(), made);
    assert_eq!(son_klasor(&s, "other").unwrap(), "");
    son_klasoru_hatirla(&s, root, &obj(json!({"folder_reset":true}))).unwrap();
    assert_eq!(son_klasor(&s, root).unwrap(), "");
    paths::ensure_dirs(dir.path()).unwrap();
    for name in ["data", "downloads", "plugins"] {
        assert!(dir.path().join(name).is_dir());
    }
    assert!(paths::app_dir().is_absolute());
    assert!(
        paths::user_downloads_dir().ends_with("Downloads")
            || paths::user_downloads_dir().ends_with("downloads")
    );
    assert!(paths::ytdlp_exe().ends_with("yt-dlp.exe") || paths::ytdlp_exe().ends_with("yt-dlp"));
    assert_eq!(paths::ffmpeg_dir(), paths::ffmpeg_exe().parent().unwrap());
}

#[test]
fn pending_requests_persist_deduplicate_protect_secrets_and_restore() {
    let dir = tempfile::tempdir().unwrap();
    let b = kaydet::Bekleyenler::new(dir.path()).unwrap();
    let request = obj(
        json!({"url":"HTTPS://EXAMPLE.COM/a#fragment","request_id":"id1","cookies":[{"name":"sid","value":"SECRET"}],"headers":{"Authorization":"SECRET"},"user_agent":"SECRET","title":"title"}),
    );
    let id = b.ekle(&request).unwrap();
    assert_eq!(id, 1);
    assert_eq!(b.bak(id).unwrap(), Some(request.clone()));
    assert_eq!(b.ekle(&request).unwrap(), id);
    assert_eq!(
        b.ekle(&obj(json!({"url":"https://example.com/a#other"})))
            .unwrap(),
        id
    );
    assert!(b
        .ekle(&obj(json!({"url":"https://different/","request_id":"id1"})))
        .is_err());
    assert!(b.ekle(&obj(json!({"request_id":true}))).is_err());
    assert!(!b.ozet().unwrap()[0].to_string().contains("SECRET"));
    assert!(
        !std::fs::read_to_string(dir.path().join("pending_downloads.json"))
            .unwrap()
            .contains("SECRET")
    );
    let reopened = kaydet::Bekleyenler::new(dir.path()).unwrap();
    assert!(reopened.bak(id).unwrap().unwrap().get("cookies").is_none());
    let taken = b.al(id).unwrap().unwrap();
    assert!(taken.contains_key("cookies"));
    assert!(b.al(id).unwrap().is_none());
    assert!(b.bak(id).unwrap().is_none());
    b.geri_koy(id, &taken).unwrap();
    assert_eq!(b.bak(id).unwrap(), Some(taken));
    assert_eq!(b.ozet().unwrap().len(), 1);
    drop(b);
    drop(reopened);
    let b = kaydet::Bekleyenler::new(dir.path()).unwrap();
    assert_eq!(b.ekle(&obj(json!({"url":"https://new/"}))).unwrap(), 2);
}

#[test]
fn pending_expiry_corruption_and_failed_write_preserve_request() {
    let dir = tempfile::tempdir().unwrap();
    let file = dir.path().join("pending_downloads.json");
    std::fs::write(&file,json!({"version":1,"items":[{"id":5,"istek":{"url":"https://a/","cookies":["old"],"headers":{},"user_agent":"secret"},"zaman":1}]}).to_string()).unwrap();
    let b = kaydet::Bekleyenler::new(dir.path()).unwrap();
    assert_eq!(b.ozet().unwrap().len(), 1);
    assert!(b.bak(5).unwrap().unwrap().get("cookies").is_none());
    assert!(b.al(5).unwrap().is_some());
    drop(b);
    std::fs::write(&file, "bad").unwrap();
    let b = kaydet::Bekleyenler::new(dir.path()).unwrap();
    assert!(b.ozet().unwrap().is_empty());
    assert!(std::fs::read_dir(dir.path())
        .unwrap()
        .filter_map(std::result::Result::ok)
        .any(|e| e
            .file_name()
            .to_string_lossy()
            .starts_with("pending_downloads.json.corrupt-")));
    let id = b.ekle(&obj(json!({"url":"https://a/"}))).unwrap();
    std::fs::remove_file(&file).unwrap();
    std::fs::create_dir(&file).unwrap();
    assert!(b.al(id).is_err());
    assert!(b.bak(id).unwrap().is_some());
}
