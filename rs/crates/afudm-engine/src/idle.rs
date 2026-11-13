//! Serialize work and idle shutdown; polling alone never wakes the engine.
use crate::Aria2Daemon;
use afudm_types::{AfuError, Aria2, Json, JsonMap, Result};
use serde_json::json;
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant};

struct State {
    daemon: Aria2Daemon,
    sleeping: bool,
    last_recovery: Option<Instant>,
    global_options: JsonMap,
}

impl State {
    fn call(&mut self, method: &str, params: Vec<Json>) -> Result<Json> {
        let (mut result, refused) = self.daemon.rpc.call_with_refusal(method, params.clone());
        if refused
            && !self
                .last_recovery
                .is_some_and(|last| last.elapsed() < Duration::from_secs(30))
            && matches!(
                self.daemon.proc.as_mut().map(|child| child.try_wait()),
                Some(Ok(Some(_)))
            )
        {
            // The mutex serializes callers; count failed attempts too to prevent a restart storm.
            self.last_recovery = Some(Instant::now());
            if self.daemon.start(Duration::from_secs(20)).is_ok()
                && (self.global_options.is_empty()
                    || self
                        .daemon
                        .rpc
                        .change_global_option(&self.global_options)
                        .is_ok())
            {
                // Restore runtime settings before replaying the refused request exactly once.
                if let Ok(value) = self.daemon.rpc.call(method, params.clone()) {
                    result = Ok(value);
                }
            }
        }
        if result.is_ok() && method == "aria2.changeGlobalOption" {
            if let Some(options) = params.first().and_then(Json::as_object) {
                self.global_options.extend(options.clone());
            }
        }
        result
    }
}

pub struct IdleRpc {
    state: Mutex<State>,
    on_wake: Box<dyn Fn() + Send + Sync>,
}

impl IdleRpc {
    pub fn new(daemon: Aria2Daemon, on_wake: impl Fn() + Send + Sync + 'static) -> Self {
        Self {
            state: Mutex::new(State {
                daemon,
                sleeping: false,
                last_recovery: None,
                global_options: JsonMap::new(),
            }),
            on_wake: Box::new(on_wake),
        }
    }

    fn lock(&self) -> Result<MutexGuard<'_, State>> {
        self.state
            .lock()
            .map_err(|_| AfuError::Unavailable("motor kilidi kullanilamiyor".into()))
    }

    pub fn sleep_if_idle(&self) -> Result<bool> {
        let mut state = self.lock()?;
        if state.sleeping {
            return Ok(true);
        }
        let daemon = &mut state.daemon;
        let Some(child) = daemon.proc.as_mut() else {
            return Ok(false);
        };
        if child.try_wait()?.is_some() {
            return Ok(false);
        }
        if !daemon.rpc.tell_active(&[])?.is_empty()
            || !daemon.rpc.tell_waiting(0, 1, &[])?.is_empty()
        {
            return Ok(false);
        }
        daemon.save_session()?;
        daemon.rpc.shutdown(false)?;
        daemon.wait_owned(false)?;
        crate::daemon::sanitize_session_file(&daemon.data_dir)?;
        daemon.proc = None;
        state.sleeping = true;
        Ok(true)
    }

    /// Python reliability.restart_engine: daemon'u durdur (oturum kaydedilir), yeniden baslat.
    /// Manager ayni IdleRpc'yi tuttugu icin rpc referansi degismez; yalniz motor surecı yenilenir.
    pub fn restart(&self) -> Result<()> {
        let mut state = self.lock()?;
        state.daemon.stop()?;
        state.daemon.start(Duration::from_secs(20))?;
        state.sleeping = false;
        Ok(())
    }

    pub(crate) fn invoke(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        let mut state = self.lock()?;
        if state.sleeping {
            match method {
                "aria2.tellActive" | "aria2.tellWaiting" | "aria2.tellStopped" => {
                    return Ok(json!([]))
                }
                "aria2.getGlobalStat" => {
                    return Ok(
                        json!({"numActive":"0", "numWaiting":"0", "numStopped":"0", "downloadSpeed":"0", "uploadSpeed":"0"}),
                    )
                }
                // The shared trait returns String, while Python returns None when asleep.
                "aria2.saveSession" | "aria2.shutdown" | "aria2.forceShutdown" => {
                    return Ok(json!(""))
                }
                _ => {
                    state.daemon.start(Duration::from_secs(20))?;
                    state.sleeping = false;
                    (self.on_wake)();
                }
            }
        }
        state.call(method, params)
    }
}

impl Aria2 for IdleRpc {
    fn call(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        // Python's generic call wakes even for otherwise read-only methods.
        let mut state = self.lock()?;
        if state.sleeping {
            state.daemon.start(Duration::from_secs(20))?;
            state.sleeping = false;
            (self.on_wake)();
        }
        state.call(method, params)
    }
    fn sleeping(&self) -> bool {
        self.state.lock().map(|s| s.sleeping).unwrap_or(false)
    }
    fn alive(&self) -> bool {
        self.state
            .lock()
            .map(|s| s.sleeping || s.daemon.rpc.alive())
            .unwrap_or(false)
    }
    aria2_methods!();
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs, net::TcpListener};

    fn engine() -> (tempfile::TempDir, IdleRpc) {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir(dir.path().join("engine")).unwrap();
        fs::copy(
            crate::tests::aria_binary(),
            dir.path().join("engine/aria2c.exe"),
        )
        .unwrap();
        let port = TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port();
        assert!(!(6810..=6830).contains(&port));
        let mut daemon = Aria2Daemon::new(
            dir.path(),
            &dir.path().join("data"),
            &dir.path().join("downloads"),
        );
        daemon.port_range = (port, port);
        daemon.start(Duration::from_secs(15)).unwrap();
        (dir, IdleRpc::new(daemon, || {}))
    }

    fn kill_owned(rpc: &IdleRpc) -> u32 {
        let mut state = rpc.lock().unwrap();
        let child = state.daemon.proc.as_mut().unwrap();
        let pid = child.id();
        child.kill().unwrap();
        child.wait().unwrap();
        // Windows reports a closed loopback port after about two seconds on some hosts.
        // A shorter probe timeout would test TimedOut instead of ConnectionRefused.
        let address = std::net::SocketAddr::from(([127, 0, 0, 1], state.daemon.port));
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Err(error) =
                std::net::TcpStream::connect_timeout(&address, Duration::from_secs(3))
            {
                if error.kind() == std::io::ErrorKind::ConnectionRefused {
                    break;
                }
            }
            assert!(
                Instant::now() < deadline,
                "killed engine listener did not close"
            );
            std::thread::sleep(Duration::from_millis(20));
        }
        pid
    }

    #[test]
    fn refused_rpc_restarts_dead_owned_engine_and_adds_download_once() {
        let (dir, rpc) = engine();
        let secret = fs::read(dir.path().join("data/rpc_secret.txt")).unwrap();
        let limits = serde_json::from_value(
            json!({"max-overall-download-limit":"102400", "max-concurrent-downloads":"2"}),
        )
        .unwrap();
        rpc.change_global_option(&limits).unwrap();
        rpc.call(
            "aria2.changeGlobalOption",
            vec![json!({"max-overall-upload-limit":"51200"})],
        )
        .unwrap();
        let pid = kill_owned(&rpc);
        let options = serde_json::from_value(json!({"pause":"true", "out":"restart.bin"})).unwrap();
        let gid = rpc
            .add_uri(&["http://127.0.0.1:1/restart.bin".into()], Some(&options))
            .expect("a dead engine must recover when adding a download");
        assert_ne!(rpc.lock().unwrap().daemon.proc.as_ref().unwrap().id(), pid);
        assert_eq!(
            fs::read(dir.path().join("data/rpc_secret.txt")).unwrap(),
            secret
        );
        let status = rpc.tell_status(&gid, &["status", "dir", "files"]).unwrap();
        assert_eq!(status["status"], "paused");
        assert!(std::path::Path::new(status["dir"].as_str().unwrap()).ends_with("downloads"));
        assert!(status["files"][0]["path"]
            .as_str()
            .unwrap()
            .ends_with("restart.bin"));
        assert_eq!(rpc.tell_waiting(0, 10, &[]).unwrap().len(), 1);
        let settings = rpc.get_global_option().unwrap();
        assert_eq!(settings["max-overall-download-limit"], "102400");
        assert_eq!(settings["max-overall-upload-limit"], "51200");
        assert_eq!(settings["max-concurrent-downloads"], "2");
        // A second crash in the same short interval must not cause a restart loop.
        let second_pid = kill_owned(&rpc);
        let error = rpc
            .add_uri(&["http://127.0.0.1:1/second.bin".into()], Some(&options))
            .unwrap_err();
        assert!(error.to_string().contains("aria2 RPC erisilemedi:"));
        assert_eq!(
            rpc.lock().unwrap().daemon.proc.as_ref().unwrap().id(),
            second_pid
        );
    }

    #[test]
    fn refused_rpc_recovers_generic_call_too() {
        let (_dir, rpc) = engine();
        kill_owned(&rpc);
        assert!(rpc.call("aria2.getVersion", vec![]).unwrap()["version"].is_string());
    }

    #[test]
    fn refused_rpc_does_not_restart_a_live_owned_process() {
        let (_dir, rpc) = engine();
        let closed = TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port();
        let mut state = rpc.lock().unwrap();
        let original = state.daemon.rpc.clone();
        let pid = state.daemon.proc.as_ref().unwrap().id();
        state.daemon.rpc = std::sync::Arc::new(crate::Aria2Rpc::new("127.0.0.1", closed, ""));
        drop(state);
        assert!(rpc.call("aria2.getVersion", vec![]).is_err());
        let mut state = rpc.lock().unwrap();
        assert_eq!(state.daemon.proc.as_ref().unwrap().id(), pid);
        assert!(state
            .daemon
            .proc
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_none());
        state.daemon.rpc = original;
    }

    #[test]
    fn refused_rpc_does_not_replace_an_unowned_engine() {
        let (dir, owner) = engine();
        let port = owner.lock().unwrap().daemon.port;
        let mut guest = Aria2Daemon::new(
            dir.path(),
            &dir.path().join("data"),
            &dir.path().join("downloads"),
        );
        guest.port_range = (port, port);
        guest.start(Duration::from_secs(5)).unwrap();
        assert!(guest.proc.is_none());
        let guest = IdleRpc::new(guest, || {});
        kill_owned(&owner);
        assert!(guest.call("aria2.getVersion", vec![]).is_err());
        assert!(guest.lock().unwrap().daemon.proc.is_none());
    }

    #[test]
    fn failed_restart_keeps_original_error_and_throttles_until_cooldown_expires() {
        let (dir, rpc) = engine();
        kill_owned(&rpc);
        let binary = dir.path().join("engine/aria2c.exe");
        fs::write(&binary, b"invalid executable").unwrap();
        let error = rpc
            .call("aria2.getVersion", vec![])
            .unwrap_err()
            .to_string();
        assert!(error.contains("aria2 RPC erisilemedi:"), "{error}");
        fs::copy(crate::tests::aria_binary(), binary).unwrap();
        assert!(rpc.call("aria2.getVersion", vec![]).is_err());
        rpc.lock().unwrap().last_recovery = Some(Instant::now() - Duration::from_secs(31));
        assert!(rpc.call("aria2.getVersion", vec![]).unwrap()["version"].is_string());
    }

    #[test]
    fn rpc_application_error_does_not_restart_dead_process() {
        let (_dir, rpc) = engine();
        let pid = kill_owned(&rpc);
        let (port, server) = crate::tests::serve_bytes(
            500,
            json!({"error":{"message":"connection refused (10061)"}})
                .to_string()
                .into_bytes(),
        );
        let original = rpc.lock().unwrap().daemon.rpc.clone();
        rpc.lock().unwrap().daemon.rpc =
            std::sync::Arc::new(crate::Aria2Rpc::new("127.0.0.1", port, ""));
        let error = rpc.call("aria2.addUri", vec![]).unwrap_err().to_string();
        assert!(error.contains("connection refused (10061)"));
        server.join().unwrap();
        let mut state = rpc.lock().unwrap();
        assert_eq!(state.daemon.proc.as_ref().unwrap().id(), pid);
        assert!(state.last_recovery.is_none());
        state.daemon.rpc = original;
    }
}
