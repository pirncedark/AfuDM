//! All state stays beside the application executable (portable mode).
use afudm_types::Result;
use std::path::{Path, PathBuf};

pub fn app_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("."))
}
pub fn data_dir(app_dir: &Path) -> PathBuf {
    app_dir.join("data")
}
pub fn db_path(data: &Path) -> PathBuf {
    data.join("afudm.db")
}
pub fn token_file(data: &Path) -> PathBuf {
    data.join("api_token.txt")
}
pub fn endpoint_file(data: &Path) -> PathBuf {
    data.join("api_endpoint.json")
}
pub fn default_download_dir() -> PathBuf {
    app_dir().join("downloads")
}
pub fn user_downloads_dir() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .map(|p| PathBuf::from(p).join("Downloads"))
        .unwrap_or_else(default_download_dir)
}
pub fn ensure_dirs(base: &Path) -> Result<()> {
    for p in [data_dir(base), base.join("downloads"), base.join("plugins")] {
        std::fs::create_dir_all(p)?;
    }
    Ok(())
}
fn bundled_or_system(name: &str) -> PathBuf {
    let local = app_dir().join("engine").join(name);
    if local.exists() {
        return local;
    }
    if let Some(path) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&path) {
            let p = dir.join(if cfg!(windows) {
                name
            } else {
                name.trim_end_matches(".exe")
            });
            if p.is_file() {
                return p;
            }
        }
    }
    local
}
pub fn ytdlp_exe() -> PathBuf {
    bundled_or_system("yt-dlp.exe")
}
pub fn ffmpeg_exe() -> PathBuf {
    bundled_or_system("ffmpeg.exe")
}
pub fn ffmpeg_dir() -> PathBuf {
    ffmpeg_exe()
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_default()
}
