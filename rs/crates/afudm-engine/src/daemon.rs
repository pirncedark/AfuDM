//! Owned aria2 process, portable state and credential scrubbing.
use crate::{engines, hidden_command, Aria2Rpc};
use afudm_types::{AfuError, Aria2, Result};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use regex::Regex;
use std::{
    collections::BTreeSet,
    fs,
    net::{SocketAddr, TcpStream, UdpSocket},
    path::{Path, PathBuf},
    process::Child,
    sync::{Arc, OnceLock},
    thread,
    time::{Duration, Instant},
};

pub const RPC_PORT: u16 = 6810;
pub const RPC_PORT_SON: u16 = 6830;

pub fn load_or_create_secret(data_dir: &Path) -> Result<String> {
    fs::create_dir_all(data_dir)?;
    let file = data_dir.join("rpc_secret.txt");
    if file.exists() {
        let token = fs::read_to_string(&file)?.trim().to_owned();
        if !token.is_empty() {
            return Ok(token);
        }
    }
    let token = URL_SAFE_NO_PAD.encode(rand::random::<[u8; 24]>());
    fs::write(file, &token)?;
    Ok(token)
}

pub fn save_auth_required(data_dir: &Path, gids: &BTreeSet<String>) -> Result<()> {
    let path = data_dir.join("aria2.auth-required.json");
    if gids.is_empty() {
        match fs::remove_file(path) {
            Ok(()) => (),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => return Err(e.into()),
        }
    } else {
        fs::write(path, serde_json::to_string(gids)?)?;
    }
    Ok(())
}

pub fn sanitize_session_file(data_dir: &Path) -> Result<BTreeSet<String>> {
    let session = data_dir.join("aria2.session");
    if !session.exists() {
        return Ok(BTreeSet::new());
    }
    let text = String::from_utf8_lossy(&fs::read(&session)?).into_owned();
    let marker = data_dir.join("aria2.auth-required.json");
    let mut required: BTreeSet<String> = fs::read(&marker)
        .ok()
        .and_then(|b| serde_json::from_slice::<Vec<serde_json::Value>>(&b).ok())
        .unwrap_or_default()
        .into_iter()
        .filter(|v| !v.is_null() && v != "" && v != false && v != 0)
        .map(|v| {
            v.as_str()
                .map(str::to_owned)
                .unwrap_or_else(|| v.to_string())
        })
        .collect();
    let separator = Regex::new(r"\r?\n\s*\r?\n").map_err(|e| AfuError::Other(e.to_string()))?;
    let secret_header = Regex::new(r"(?i)^\s*header\s*=\s*(?:cookie|authorization)\s*:")
        .map_err(|e| AfuError::Other(e.to_string()))?;
    let mut records = Vec::new();
    for record in separator.split(text.trim()).filter(|r| !r.is_empty()) {
        let mut lines: Vec<String> = record.lines().map(str::to_owned).collect();
        let gid = lines
            .iter()
            .find(|l| l.trim().to_lowercase().starts_with("gid="))
            .and_then(|l| l.split_once('='))
            .map(|(_, g)| g.trim().to_owned())
            .unwrap_or_default();
        if lines.iter().any(|l| secret_header.is_match(l)) {
            if !gid.is_empty() {
                required.insert(gid);
            }
            lines.retain(|l| !secret_header.is_match(l));
            if !lines
                .iter()
                .any(|l| l.trim().eq_ignore_ascii_case("pause=true"))
            {
                lines.push(" pause=true".into());
            }
        }
        records.push(lines.join("\n"));
    }
    let mut safe = records.join("\n\n");
    if !safe.is_empty() {
        safe.push('\n');
    }
    fs::write(session, safe)?;
    fs::write(marker, serde_json::to_string(&required)?)?;
    Ok(required)
}

pub fn dinleyen_var_mi(port: u16) -> bool {
    TcpStream::connect_timeout(
        &SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(400),
    )
    .is_ok()
}

fn ipv6_usable() -> bool {
    static CACHED: OnceLock<bool> = OnceLock::new();
    *CACHED.get_or_init(|| {
        ["[2001:4860:4860::8888]:53", "[2606:4700:4700::1111]:53"].iter().any(|target| {
            let Ok(socket) = UdpSocket::bind("[::]:0") else { return false; };
            if socket.connect(target).is_err() { return false; }
            matches!(socket.local_addr(), Ok(SocketAddr::V6(addr)) if addr.ip().octets()[0] & 0xe0 == 0x20)
        })
    })
}

pub struct Aria2Daemon {
    app_dir: PathBuf,
    pub(crate) data_dir: PathBuf,
    download_dir: PathBuf,
    pub(crate) proc: Option<Child>,
    pub port: u16,
    pub(crate) rpc: Arc<Aria2Rpc>,
    pub(crate) port_range: (u16, u16),
}

impl Aria2Daemon {
    pub fn new(app_dir: &Path, data_dir: &Path, download_dir: &Path) -> Self {
        Self {
            app_dir: app_dir.into(),
            data_dir: data_dir.into(),
            download_dir: download_dir.into(),
            proc: None,
            port: RPC_PORT,
            rpc: Arc::new(Aria2Rpc::new("127.0.0.1", RPC_PORT, "")),
            port_range: (RPC_PORT, RPC_PORT_SON),
        }
    }

    pub(crate) fn arguments(&self, secret: &str, port: u16) -> Result<Vec<String>> {
        fs::create_dir_all(&self.data_dir)?;
        fs::create_dir_all(&self.download_dir)?;
        fs::create_dir_all(self.app_dir.join("plugins"))?;
        let session = self.data_dir.join("aria2.session");
        fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&session)?;
        let mut args = crate::args::arguments(secret, &self.download_dir, &self.data_dir, port);
        if !ipv6_usable() {
            args.push("--disable-ipv6=true".into());
        }
        #[cfg(test)]
        {
            // Integration tests must not share DHT state or torrent listeners with AfuDM.
            let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
            let peer_port = listener.local_addr()?.port();
            args.extend([
                "--enable-dht=false".into(),
                "--bt-enable-lpd=false".into(),
                format!("--listen-port={peer_port}"),
            ]);
        }
        Ok(args)
    }

    pub fn start(&mut self, timeout: Duration) -> Result<Arc<dyn Aria2>> {
        fs::create_dir_all(&self.download_dir)?;
        fs::create_dir_all(self.app_dir.join("plugins"))?;
        let secret = load_or_create_secret(&self.data_dir)?;
        for port in self.port_range.0..=self.port_range.1 {
            if !dinleyen_var_mi(port) {
                continue;
            }
            let candidate = Arc::new(Aria2Rpc::new("127.0.0.1", port, &secret));
            if candidate
                .call_timeout("aria2.getVersion", vec![], Duration::from_millis(1500))
                .is_ok()
            {
                self.port = port;
                self.rpc = candidate;
                return Ok(self.rpc.clone());
            }
        }
        let binary = self.app_dir.join("engine/aria2c.exe");
        if !binary.exists() {
            let system = engines::sistemde(&self.app_dir, "aria2c");
            if !system.is_empty() {
                let _ = fs::create_dir_all(self.app_dir.join("engine"));
                let _ = fs::copy(system, &binary);
            }
            if !binary.exists() {
                let _ = engines::indir(&self.app_dir, "aria2c", &|_, _| {});
            }
        }
        if !binary.exists() {
            return Err(AfuError::NotFound(format!(
                "aria2c.exe bulunamadi: {}",
                binary.display()
            )));
        }
        sanitize_session_file(&self.data_dir)?;
        let port = (self.port_range.0..=self.port_range.1)
            .find(|p| !dinleyen_var_mi(*p))
            .ok_or_else(|| {
                AfuError::Unavailable(format!(
                    "bos RPC portu yok ({}-{}): cok fazla kopya acik",
                    self.port_range.0, self.port_range.1
                ))
            })?;
        self.port = port;
        self.rpc = Arc::new(Aria2Rpc::new("127.0.0.1", port, &secret));
        self.proc = Some(
            hidden_command(&binary)
                .args(self.arguments(&secret, port)?)
                .spawn()?,
        );
        let deadline = Instant::now() + timeout;
        while Instant::now() < deadline {
            if self.rpc.alive() {
                return Ok(self.rpc.clone());
            }
            if let Some(status) = self
                .proc
                .as_mut()
                .map(|p| p.try_wait())
                .transpose()?
                .flatten()
            {
                let log = self.data_dir.join("aria2.log");
                let tail = fs::read_to_string(&log)
                    .map(|s| {
                        s.lines()
                            .rev()
                            .take(20)
                            .collect::<Vec<_>>()
                            .into_iter()
                            .rev()
                            .collect::<Vec<_>>()
                            .join("\n")
                    })
                    .unwrap_or_else(|e| format!("(log okunamadi: {e})"));
                return Err(AfuError::Engine(format!(
                    "aria2c baslatilamadi (cikis kodu {status}). Log: {}\nSon 20 satir:\n{}",
                    log.display(),
                    tail.replace(&secret, "[REDACTED]")
                )));
            }
            thread::sleep(Duration::from_millis(250));
        }
        Err(AfuError::Unavailable(format!(
            "aria2c RPC {:.0} saniyede yanit vermedi (port {})",
            timeout.as_secs_f64(),
            self.port
        )))
    }

    pub fn save_session(&self) -> Result<()> {
        let _ = self.rpc.call("aria2.purgeDownloadResult", vec![]);
        self.rpc.save_session()?;
        sanitize_session_file(&self.data_dir)?;
        Ok(())
    }

    pub(crate) fn wait_owned(&mut self, kill_after: bool) -> Result<()> {
        let deadline = Instant::now() + Duration::from_secs(8);
        if let Some(child) = self.proc.as_mut() {
            while child.try_wait()?.is_none() {
                if Instant::now() >= deadline {
                    if !kill_after {
                        return Err(AfuError::Unavailable("aria2c kapanmadi".into()));
                    }
                    child.kill()?;
                    child.wait()?;
                    break;
                }
                thread::sleep(Duration::from_millis(50));
            }
        }
        Ok(())
    }

    pub fn stop(&mut self) -> Result<()> {
        if self.proc.is_none() {
            return Ok(());
        }
        if self.rpc.alive() && self.save_session().is_ok() {
            let _ = self.rpc.shutdown(false);
        }
        self.wait_owned(true)?;
        sanitize_session_file(&self.data_dir)?;
        self.proc = None;
        Ok(())
    }
}

impl Drop for Aria2Daemon {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}
