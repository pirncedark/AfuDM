//! SAHIBI: Ekip A (codex). aria2c sureci + afudm_types::Aria2 JSON-RPC istemcisi + yt-dlp/ffmpeg motor yonetimi.
//! Python: core/daemon.py, core/rpc.py, core/aria2.py, core/engines.py

#[cfg(test)]
mod tests;

#[macro_use]
mod methods;
mod args;
pub mod daemon;
pub mod engines;
pub mod idle;
pub mod rpc;
pub use daemon::Aria2Daemon;
pub use idle::IdleRpc;
pub use rpc::Aria2Rpc;

pub(crate) fn hidden_command(path: &std::path::Path) -> std::process::Command {
    let mut command = std::process::Command::new(path);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    command
}
