//! Serialize work and idle shutdown; polling alone never wakes the engine.
use crate::Aria2Daemon;
use afudm_types::{AfuError, Aria2, Json, JsonMap, Result};
use serde_json::json;
use std::sync::{Mutex, MutexGuard};
use std::time::Duration;

struct State {
    daemon: Aria2Daemon,
    sleeping: bool,
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
        state.daemon.rpc.call(method, params)
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
        state.daemon.rpc.call(method, params)
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
