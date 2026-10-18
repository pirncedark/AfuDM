//! Synchronous aria2 JSON-RPC transport (core/rpc.py).
use afudm_types::{AfuError, Aria2, Json, JsonMap, Result};
use serde_json::json;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

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
            .map_err(|e| AfuError::Engine(self.redact(format!("aria2 RPC erisilemedi: {e}"))))?;
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
}

impl Aria2 for Aria2Rpc {
    fn call(&self, method: &str, params: Vec<Json>) -> Result<Json> {
        self.call_timeout(method, params, Duration::from_secs(15))
    }
    fn alive(&self) -> bool {
        self.call_timeout("aria2.getVersion", vec![], Duration::from_secs(3))
            .is_ok()
    }
    aria2_methods!();
}
