//! Synchronous aria2 JSON-RPC transport (core/rpc.py).
use afudm_types::{AfuError, Aria2, Json, JsonMap, Result};
use serde_json::json;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

const ALIVE_ERROR_LIMIT: u32 = 3;
const ALIVE_GRACE: Duration = Duration::from_secs(15);
const PROBE_TIMEOUT: Duration = Duration::from_secs(8);

#[derive(Clone, Copy, Default)]
struct ProbeHealth {
    last_success: Option<Instant>,
    consecutive_errors: u32,
}

fn alive_from_health(consecutive_errors: u32, since_success: Option<Duration>) -> bool {
    consecutive_errors < ALIVE_ERROR_LIMIT
        || since_success.is_some_and(|elapsed| elapsed < ALIVE_GRACE)
}

fn next_probe_health(current: ProbeHealth, succeeded: bool, now: Instant) -> ProbeHealth {
    if succeeded {
        ProbeHealth {
            last_success: Some(now),
            consecutive_errors: 0,
        }
    } else {
        ProbeHealth {
            consecutive_errors: current.consecutive_errors.saturating_add(1),
            ..current
        }
    }
}

// core/rpc.py STATUS_KEYS: an empty argument selects the Python defaults.
pub(crate) const STATUS_KEYS: &[&str] = &[
    "gid",
    "status",
    "totalLength",
    "completedLength",
    "uploadLength",
    "downloadSpeed",
    "uploadSpeed",
    "connections",
    "numSeeders",
    "seeder",
    "errorCode",
    "errorMessage",
    "dir",
    "files",
    "bittorrent",
    "infoHash",
    "numPieces",
    "pieceLength",
    "followedBy",
    "following",
];

pub(crate) fn status_keys<'a>(keys: &'a [&'a str]) -> &'a [&'a str] {
    if keys.is_empty() {
        STATUS_KEYS
    } else {
        keys
    }
}

pub struct Aria2Rpc {
    pub port: u16,
    url: String,
    token: String,
    ids: AtomicU64,
    probe_health: Mutex<ProbeHealth>,
}

pub(crate) fn hata_metni(body: &Json) -> String {
    let Some(error) = body.as_object().and_then(|b| b.get("error")) else {
        return String::new();
    };
    let value = if error.is_object() {
        &error["message"]
    } else {
        error
    };
    match value {
        Json::Null | Json::Bool(false) => String::new(),
        Json::String(s) => s.clone(),
        Json::Number(n) if n.as_f64() == Some(0.0) => String::new(),
        Json::Array(a) if a.is_empty() => String::new(),
        Json::Object(o) if o.is_empty() => String::new(),
        Json::Bool(true) => "True".into(),
        v => v.to_string(),
    }
}

impl Aria2Rpc {
    pub fn new(host: &str, port: u16, secret: &str) -> Self {
        Self {
            port,
            url: format!("http://{host}:{port}/jsonrpc"),
            token: format!("token:{secret}"),
            ids: AtomicU64::new(1),
            probe_health: Mutex::new(ProbeHealth::default()),
        }
    }

    fn redact(&self, text: String) -> String {
        let text = text.replace(&self.token, "[REDACTED]");
        let secret = self.token.strip_prefix("token:").unwrap_or("");
        if secret.is_empty() {
            text
        } else {
            text.replace(secret, "[REDACTED]")
        }
    }

    pub fn call_timeout(&self, method: &str, params: Vec<Json>, timeout: Duration) -> Result<Json> {
        self.call_timeout_inner(method, params, timeout, &mut false)
    }

    /// Keep the typed transport cause separate from the existing, redacted error text.
    pub(crate) fn call_with_refusal(
        &self,
        method: &str,
        params: Vec<Json>,
        timeout: Duration,
    ) -> (Result<Json>, bool) {
        let mut refused = false;
        let result = self.call_timeout_inner(method, params, timeout, &mut refused);
        (result, refused)
    }

    fn call_timeout_inner(
        &self,
        method: &str,
        params: Vec<Json>,
        timeout: Duration,
        refused: &mut bool,
    ) -> Result<Json> {
        let mut all = vec![json!(self.token)];
        all.extend(params);
        let payload = json!({"jsonrpc":"2.0", "id":self.ids.fetch_add(1, Ordering::Relaxed).to_string(), "method":method, "params":all});
        let agent: ureq::Agent = ureq::Agent::config_builder()
            .timeout_global(Some(timeout))
            .http_status_as_error(false)
            .build()
            .into();
        let mut response = agent
            .post(&self.url)
            .send_json(&payload)
            .map_err(|e| {
                *refused = matches!(&e, ureq::Error::Io(io) if io.kind() == std::io::ErrorKind::ConnectionRefused);
                AfuError::Engine(self.redact(format!("aria2 RPC erisilemedi: {e}")))
            })?;
        let status = response.status();
        let raw = response.body_mut().read_to_string().map_err(|e| {
            AfuError::Engine(self.redact(format!("aria2 RPC baglantisi koptu: {e}")))
        })?;
        let parsed = serde_json::from_str::<Json>(&raw);
        if status.is_client_error() || status.is_server_error() {
            let message = parsed.as_ref().map(hata_metni).unwrap_or_default();
            let message = if message.is_empty() {
                if raw.is_empty() {
                    status.to_string()
                } else {
                    raw
                }
            } else {
                message
            };
            return Err(AfuError::Engine(
                self.redact(format!("{method}: {message}")),
            ));
        }
        let body =
            parsed.map_err(|e| AfuError::Engine(format!("aria2 RPC baglantisi koptu: {e}")))?;
        if !body.is_object() {
            return Err(AfuError::Engine("beklenmeyen RPC yaniti".into()));
        }
        if body.get("error").is_some() {
            let message = hata_metni(&body);
            return Err(AfuError::Engine(self.redact(if message.is_empty() {
                "bilinmeyen aria2 hatasi".into()
            } else {
                message
            })));
        }
        // Do not echo response payloads: they may contain task cookies or authorization headers.
        body.get("result")
            .cloned()
            .ok_or_else(|| AfuError::Engine("RPC yanitinda sonuc yok".into()))
    }

    pub(crate) fn invoke(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        self.call(method, params)
    }

    /// Strict health check used while starting aria2; unlike `alive`, it never
    /// treats a temporarily unreachable engine as usable.
    pub(crate) fn probe(&self) -> bool {
        let ok = self
            .call_timeout("aria2.getVersion", vec![], PROBE_TIMEOUT)
            .is_ok();
        let mut health = self.probe_health.lock().unwrap_or_else(|e| e.into_inner());
        *health = next_probe_health(*health, ok, Instant::now());
        ok
    }
}

impl Aria2 for Aria2Rpc {
    fn call(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        self.call_timeout(method, params, Duration::from_secs(15))
    }
    fn alive(&self) -> bool {
        let ok = self.probe();
        if ok {
            return true;
        }
        let health = self.probe_health.lock().unwrap_or_else(|e| e.into_inner());
        let since_success = health.last_success.map(|last| last.elapsed());
        alive_from_health(health.consecutive_errors, since_success)
    }
    aria2_methods!();
}

#[cfg(test)]
mod tests {
    use super::{alive_from_health, next_probe_health, ProbeHealth, ALIVE_GRACE};
    use std::time::Duration;

    #[test]
    fn one_probe_error_keeps_engine_alive() {
        assert!(alive_from_health(1, Some(Duration::from_secs(1))));
    }

    #[test]
    fn three_errors_after_grace_mark_engine_stopped() {
        assert!(!alive_from_health(3, Some(ALIVE_GRACE)));
    }

    #[test]
    fn a_success_resets_the_error_streak() {
        let now = std::time::Instant::now();
        let health = next_probe_health(
            ProbeHealth {
                last_success: Some(now - Duration::from_secs(20)),
                consecutive_errors: 3,
            },
            true,
            now,
        );
        assert_eq!(health.consecutive_errors, 0);
        assert_eq!(health.last_success, Some(now));
        assert!(alive_from_health(
            health.consecutive_errors,
            Some(Duration::ZERO)
        ));
    }
}
