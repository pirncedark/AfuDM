use super::*;
use afudm_types::Aria2;
use serde_json::json;
use std::{
    io::{BufRead, BufReader, Read, Write},
    net::TcpListener,
    thread,
    time::{Duration, Instant},
};

pub(crate) fn serve_bytes(
    status: u16,
    data: Vec<u8>,
) -> (u16, thread::JoinHandle<serde_json::Value>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    listener.set_nonblocking(true).unwrap();
    let handle = thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(15);
        let mut socket = loop {
            match listener.accept() {
                Ok((socket, _)) => {
                    // Windows: kabul edilen soket dinleyicinin non-blocking modunu miras alir.
                    socket.set_nonblocking(false).unwrap();
                    break socket;
                }
                Err(e)
                    if e.kind() == std::io::ErrorKind::WouldBlock && Instant::now() < deadline =>
                {
                    thread::sleep(Duration::from_millis(10))
                }
                Err(e) => panic!("test HTTP accept: {e}"),
            }
        };
        socket
            .set_read_timeout(Some(Duration::from_secs(10)))
            .unwrap();
        let mut reader = BufReader::new(socket.try_clone().unwrap());
        let mut length = 0;
        let mut chunked = false;
        loop {
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            if line == "\r\n" || line.is_empty() {
                break;
            }
            if let Some((name, value)) = line.split_once(':') {
                if name.eq_ignore_ascii_case("content-length") {
                    length = value.trim().parse().unwrap();
                }
                if name.eq_ignore_ascii_case("transfer-encoding") {
                    chunked = value.trim().eq_ignore_ascii_case("chunked");
                }
            }
        }
        let mut body = Vec::new();
        if chunked {
            loop {
                let mut size = String::new();
                reader.read_line(&mut size).unwrap();
                let size =
                    usize::from_str_radix(size.trim().split(';').next().unwrap(), 16).unwrap();
                if size == 0 {
                    break;
                }
                let mut chunk = vec![0; size + 2];
                reader.read_exact(&mut chunk).unwrap();
                body.extend_from_slice(&chunk[..size]);
            }
        } else {
            body.resize(length, 0);
            reader.read_exact(&mut body).unwrap();
        }
        write!(socket,"HTTP/1.1 {status} Test\r\nContent-Length: {}\r\nConnection: close\r\nContent-Type: application/json\r\n\r\n",data.len()).unwrap();
        socket.write_all(&data).unwrap();
        serde_json::from_slice(&body).unwrap_or(serde_json::Value::Null)
    });
    (port, handle)
}

fn rpc_response(
    body: serde_json::Value,
    status: u16,
    invoke: impl FnOnce(&Aria2Rpc),
) -> serde_json::Value {
    let (port, server) = serve_bytes(status, body.to_string().into_bytes());
    let rpc = Aria2Rpc::new("127.0.0.1", port, "test-secret");
    invoke(&rpc);
    let request = server.join().unwrap();
    assert_eq!(request["jsonrpc"], "2.0");
    assert_eq!(request["id"], "1");
    assert_eq!(request["params"][0], "token:test-secret");
    request
}

#[test]
fn rpc_all_trait_methods_send_python_methods_and_parameters() {
    macro_rules! case {
        ($method:expr, $params:expr, $result:expr, $invoke:expr) => {{
            let request = rpc_response(json!({"result":$result}),200,$invoke);
            assert_eq!(request["method"],$method);
            assert_eq!(request["params"].as_array().unwrap()[1..],$params);
        }};
    }
    let opts = serde_json::from_value(json!({"pause":"true"})).unwrap();
    case!(
        "aria2.addUri",
        [json!(["http://example.org"]), json!({})],
        "g",
        |r| assert_eq!(
            r.add_uri(&["http://example.org".into()], None).unwrap(),
            "g"
        )
    );
    case!(
        "aria2.addTorrent",
        [json!("YQ=="), json!([]), json!(opts)],
        "g",
        |r| assert_eq!(r.add_torrent("YQ==", Some(&opts)).unwrap(), "g")
    );
    case!(
        "aria2.addMetalink",
        [json!("Yg=="), json!({})],
        ["g"],
        |r| assert_eq!(r.add_metalink("Yg==", None).unwrap(), vec!["g"])
    );
    for force in [false, true] {
        case!(
            if force {
                "aria2.forcePause"
            } else {
                "aria2.pause"
            },
            [json!("g")],
            "g",
            |r| assert_eq!(r.pause("g", force).unwrap(), "g")
        );
        case!(
            if force {
                "aria2.forceRemove"
            } else {
                "aria2.remove"
            },
            [json!("g")],
            "g",
            |r| assert_eq!(r.remove("g", force).unwrap(), "g")
        );
        case!(
            if force {
                "aria2.forceShutdown"
            } else {
                "aria2.shutdown"
            },
            Vec::<serde_json::Value>::new(),
            "OK",
            |r| assert_eq!(r.shutdown(force).unwrap(), "OK")
        );
    }
    case!("aria2.unpause", [json!("g")], "g", |r| assert_eq!(
        r.unpause("g").unwrap(),
        "g"
    ));
    case!(
        "aria2.removeDownloadResult",
        [json!("g")],
        "OK",
        |r| assert_eq!(r.remove_result("g").unwrap(), "OK")
    );
    case!(
        "aria2.pauseAll",
        Vec::<serde_json::Value>::new(),
        "OK",
        |r| assert_eq!(r.pause_all().unwrap(), "OK")
    );
    case!(
        "aria2.unpauseAll",
        Vec::<serde_json::Value>::new(),
        "OK",
        |r| assert_eq!(r.unpause_all().unwrap(), "OK")
    );
    case!(
        "aria2.tellStatus",
        [json!("g"), json!(["gid"])],
        json!({"gid":"g"}),
        |r| assert_eq!(r.tell_status("g", &["gid"]).unwrap(), json!({"gid":"g"}))
    );
    case!(
        "aria2.tellActive",
        [json!(rpc::STATUS_KEYS)],
        json!([]),
        |r| assert!(r.tell_active(&[]).unwrap().is_empty())
    );
    case!(
        "aria2.tellWaiting",
        [json!(2), json!(200), json!(rpc::STATUS_KEYS)],
        json!([]),
        |r| assert!(r.tell_waiting(2, 200, &[]).unwrap().is_empty())
    );
    case!(
        "aria2.tellStopped",
        [json!(0), json!(200), json!(["gid"])],
        json!([]),
        |r| assert!(r.tell_stopped(0, 200, &["gid"]).unwrap().is_empty())
    );
    case!(
        "aria2.getGlobalStat",
        Vec::<serde_json::Value>::new(),
        json!({}),
        |r| assert_eq!(r.global_stat().unwrap(), json!({}))
    );
    case!("aria2.getPeers", [json!("g")], json!([]), |r| assert!(r
        .get_peers("g")
        .unwrap()
        .is_empty()));
    case!("aria2.getFiles", [json!("g")], json!([]), |r| assert!(r
        .get_files("g")
        .unwrap()
        .is_empty()));
    case!("aria2.getServers", [json!("g")], json!([]), |r| assert!(r
        .get_servers("g")
        .unwrap()
        .is_empty()));
    case!(
        "aria2.changeOption",
        [json!("g"), json!(opts)],
        "OK",
        |r| assert_eq!(r.change_option("g", &opts).unwrap(), "OK")
    );
    case!(
        "aria2.changeGlobalOption",
        [json!(opts)],
        "OK",
        |r| assert_eq!(r.change_global_option(&opts).unwrap(), "OK")
    );
    case!(
        "aria2.changeUri",
        [
            json!("g"),
            json!(1),
            json!(["old"]),
            json!(["new"]),
            json!(-1)
        ],
        1,
        |r| assert_eq!(
            r.change_uri("g", 1, &["old".into()], &["new".into()], -1)
                .unwrap(),
            1
        )
    );
    case!(
        "aria2.getGlobalOption",
        Vec::<serde_json::Value>::new(),
        json!({}),
        |r| assert!(r.get_global_option().unwrap().is_empty())
    );
    case!(
        "aria2.saveSession",
        Vec::<serde_json::Value>::new(),
        "OK",
        |r| assert_eq!(r.save_session().unwrap(), "OK")
    );
    rpc_response(json!({"result": {}}), 200, |r| assert!(r.alive()));
    rpc_response(json!({"result": 3}), 200, |r| {
        assert_eq!(
            r.call_timeout("custom", vec![], Duration::from_secs(1))
                .unwrap(),
            json!(3)
        )
    });
}

#[test]
fn rpc_rejects_bad_http_json_and_rpc_shapes_without_panics_or_secrets() {
    for status in [200, 400, 401, 500] {
        for body in [
            json!({"error":{"message":"Unauthorized test-secret"}}),
            json!({"error":"Unauthorized test-secret"}),
            json!({"error":null}),
            json!([]),
            json!({}),
        ] {
            rpc_response(body, status, |r| {
                let error = r.call("aria2.getVersion", vec![]).unwrap_err().to_string();
                assert!(!error.contains("test-secret"));
            });
        }
    }
    for body in [b"not JSON".to_vec(), vec![]] {
        let (port, server) = serve_bytes(200, body);
        assert!(!Aria2Rpc::new("127.0.0.1", port, "").alive());
        server.join().unwrap();
    }
    let port = TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port();
    assert!(!Aria2Rpc::new("127.0.0.1", port, "").alive());
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let server = thread::spawn(move || {
        let (stream, _) = listener.accept().unwrap();
        thread::sleep(Duration::from_millis(100));
        drop(stream);
    });
    assert!(Aria2Rpc::new("127.0.0.1", port, "")
        .call_timeout("aria2.getVersion", vec![], Duration::from_millis(25))
        .is_err());
    server.join().unwrap();
}

#[test]
fn daemon_arguments_and_listener_detection_match_python() {
    let tmp = tempfile::tempdir().unwrap();
    let d = Aria2Daemon::new(
        tmp.path(),
        &tmp.path().join("data"),
        &tmp.path().join("downloads"),
    );
    assert_eq!(d.port, 6810);
    let args = d.arguments("secret", 6817).unwrap();
    for arg in [
        "--rpc-listen-port=6817",
        "--auto-save-interval=60",
        "--save-session-interval=0",
        "--split=64",
        "--bt-max-peers=100",
        "--rpc-listen-all=false",
    ] {
        assert!(args.iter().any(|a| a == arg));
    }
    assert!(tmp.path().join("data/aria2.session").exists());
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    assert!(daemon::dinleyen_var_mi(port));
    drop(listener);
    assert!(!daemon::dinleyen_var_mi(port));
}

pub(crate) fn aria_binary() -> std::path::PathBuf {
    let path = std::env::var_os("AFUDM_ARIA2_TEST_EXE")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| {
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../engine/aria2c.exe")
        });
    assert!(
        path.is_file(),
        "real aria2 test requires a reference binary: {}",
        path.display()
    );
    path
}

#[test]
fn real_aria2_random_port_ownership_idle_and_http_download() {
    let tmp = tempfile::tempdir().unwrap();
    let app = tmp.path();
    let data = app.join("data");
    let downloads = app.join("downloads");
    std::fs::create_dir(app.join("engine")).unwrap();
    std::fs::copy(aria_binary(), app.join("engine/aria2c.exe")).unwrap();
    let port = TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port();
    assert!(!(6810..=6830).contains(&port));
    let mut owner = Aria2Daemon::new(app, &data, &downloads);
    owner.port_range = (port, port);
    let rpc = owner.start(Duration::from_secs(15)).unwrap();
    assert!(owner.proc.is_some());
    let mut guest = Aria2Daemon::new(app, &data, &downloads);
    guest.port_range = (port, port);
    guest.start(Duration::from_secs(5)).unwrap();
    assert!(guest.proc.is_none());
    guest.stop().unwrap();
    assert!(rpc.alive());
    // A different portable copy cannot adopt the owner's authenticated engine.
    // Constrain it to the occupied random port: it must fail without spawning.
    let mut foreign = Aria2Daemon::new(app, &app.join("foreign-data"), &downloads);
    foreign.port_range = (port, port);
    let err = match foreign.start(Duration::from_secs(1)) {
        Ok(_) => panic!("foreign secret adopted another engine"),
        Err(err) => err,
    };
    assert!(err.to_string().contains("bos RPC portu yok"));
    assert!(foreign.proc.is_none());
    assert!(rpc.alive());
    let (http, server) = serve_bytes(200, b"AfuDM Rust local download".to_vec());
    let options = serde_json::from_value(json!({"pause":"true", "out":"test.bin"})).unwrap();
    let gid = rpc
        .add_uri(
            &[format!("http://127.0.0.1:{http}/test.bin")],
            Some(&options),
        )
        .unwrap();
    assert_eq!(
        rpc.tell_status(&gid, &["status"]).unwrap()["status"],
        "paused"
    );
    let wakes = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let count = wakes.clone();
    let idle = IdleRpc::new(owner, move || {
        count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
    });
    assert!(!idle.sleeping());
    assert!(!idle.sleep_if_idle().unwrap());
    idle.unpause(&gid).unwrap();
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let status = idle.tell_status(&gid, &["status"]).unwrap();
        if status["status"] == "complete" {
            break;
        }
        assert!(
            Instant::now() < deadline,
            "download did not finish: {status}"
        );
        thread::sleep(Duration::from_millis(50));
    }
    server.join().unwrap();
    assert_eq!(
        std::fs::read(downloads.join("test.bin")).unwrap(),
        b"AfuDM Rust local download"
    );
    idle.save_session().unwrap();
    assert!(idle.sleep_if_idle().unwrap());
    assert!(idle.sleeping());
    assert!(idle.sleep_if_idle().unwrap());
    assert!(idle.alive());
    assert!(idle.tell_active(&[]).unwrap().is_empty());
    assert!(idle.tell_waiting(0, 1, &[]).unwrap().is_empty());
    assert!(idle.tell_stopped(0, 1, &[]).unwrap().is_empty());
    assert_eq!(idle.global_stat().unwrap()["numActive"], "0");
    assert_eq!(idle.save_session().unwrap(), "");
    assert_eq!(idle.shutdown(false).unwrap(), "");
    assert_eq!(wakes.load(std::sync::atomic::Ordering::SeqCst), 0);
    idle.get_global_option().unwrap();
    assert!(!idle.sleeping());
    assert_eq!(wakes.load(std::sync::atomic::Ordering::SeqCst), 1);
    assert!(idle.tell_active(&[]).unwrap().is_empty());
    assert!(idle.sleep_if_idle().unwrap());
    idle.call("aria2.getVersion", vec![]).unwrap();
    assert_eq!(wakes.load(std::sync::atomic::Ordering::SeqCst), 2);
    drop(idle);
    assert!(!rpc.alive());
}

#[test]
fn rpc_error_shapes_match_python() {
    assert_eq!(
        rpc::hata_metni(&json!({"error":{"message":"yanlis"}})),
        "yanlis"
    );
    assert_eq!(
        rpc::hata_metni(&json!({"error":"Unauthorized"})),
        "Unauthorized"
    );
    assert_eq!(rpc::hata_metni(&json!([])), "");
}

#[test]
fn motor_status_and_missing_are_portable() {
    let tmp = tempfile::tempdir().unwrap();
    assert_eq!(engines::eksikler(tmp.path(), false).len(), 4);
    assert_eq!(engines::eksikler(tmp.path(), true).len(), 3);
    assert!(!engines::var_mi(tmp.path(), "aria2c"));
    assert!(engines::yol(tmp.path(), "unknown").is_none());
    std::fs::create_dir(tmp.path().join("engine")).unwrap();
    std::fs::write(tmp.path().join("engine/aria2c.exe"), b"x").unwrap();
    assert!(engines::var_mi(tmp.path(), "aria2c"));
    assert_eq!(engines::sistemde(tmp.path(), "aria2c"), "");
    let status = engines::durum(tmp.path());
    assert_eq!(status["aria2c"]["kaynak"], "paket");
    assert_eq!(status["aria2c"]["zorunlu"], true);
    assert!(engines::indir(tmp.path(), "unknown", &|_, _| {}).is_err());
}

#[test]
fn secrets_and_session_credentials_survive_migration_safely() {
    let tmp = tempfile::tempdir().unwrap();
    let secret = daemon::load_or_create_secret(tmp.path()).unwrap();
    assert_eq!(secret.len(), 32);
    assert_eq!(daemon::load_or_create_secret(tmp.path()).unwrap(), secret);
    let session = tmp.path().join("aria2.session");
    std::fs::write(&session, "https://example.org/a\n gid=abc\n header=Cookie: secret\n header=X-Test: yes\n\nmagnet:?x\n gid=def\n header=AUTHORIZATION: secret\n pause=true\n").unwrap();
    let gids = daemon::sanitize_session_file(tmp.path()).unwrap();
    assert_eq!(gids.len(), 2);
    let clean = std::fs::read_to_string(&session).unwrap();
    assert!(!clean.contains("secret"));
    assert!(clean.contains("header=X-Test: yes"));
    assert_eq!(clean.matches("pause=true").count(), 2);
    daemon::save_auth_required(tmp.path(), &gids).unwrap();
    let marker: Vec<String> = serde_json::from_slice(
        &std::fs::read(tmp.path().join("aria2.auth-required.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(marker, vec!["abc", "def"]);
    assert_eq!(daemon::sanitize_session_file(tmp.path()).unwrap(), gids);
    daemon::save_auth_required(tmp.path(), &Default::default()).unwrap();
    assert!(!tmp.path().join("aria2.auth-required.json").exists());
}

#[test]
fn rpc_default_status_keys_match_python_for_each_poll() {
    for method in [
        "aria2.tellStatus",
        "aria2.tellActive",
        "aria2.tellWaiting",
        "aria2.tellStopped",
    ] {
        let result = if method == "aria2.tellStatus" {
            json!({})
        } else {
            json!([])
        };
        let request = rpc_response(json!({"result": result}), 200, |r| match method {
            "aria2.tellStatus" => {
                r.tell_status("g", &[]).unwrap();
            }
            "aria2.tellActive" => {
                r.tell_active(&[]).unwrap();
            }
            "aria2.tellWaiting" => {
                r.tell_waiting(0, 200, &[]).unwrap();
            }
            _ => {
                r.tell_stopped(0, 200, &[]).unwrap();
            }
        });
        assert_eq!(request["method"], method);
        assert_eq!(
            request["params"].as_array().unwrap().last().unwrap(),
            &json!(rpc::STATUS_KEYS)
        );
    }
    for value in [json!({}), json!([]), json!(false), json!(0), json!(null)] {
        assert_eq!(rpc::hata_metni(&json!({"error": value})), "");
        assert_eq!(rpc::hata_metni(&json!({"error": {"message": value}})), "");
    }
    assert_eq!(rpc::hata_metni(&json!({"error":true})), "True");
}

#[test]
fn omniget_corrupt_session_marker_is_quarantined() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("aria2.session"), "").unwrap();
    std::fs::write(dir.path().join("aria2.auth-required.json"), "broken").unwrap();
    assert!(crate::daemon::sanitize_session_file(dir.path())
        .unwrap()
        .is_empty());
    assert!(std::fs::read_dir(dir.path()).unwrap().any(|e| e
        .unwrap()
        .file_name()
        .to_string_lossy()
        .starts_with("aria2.auth-required.json.corrupt-")));
}
