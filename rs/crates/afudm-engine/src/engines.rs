//! Portable engine discovery and verified installation (core/engines.py).
use afudm_types::{AfuError, Json, Result};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
    process::Stdio,
    thread,
    time::{Duration, Instant},
};

struct Motor {
    ad: &'static str,
    dosya: &'static str,
    adres: &'static str,
    zip_icinde: Option<&'static str>,
    indirme_boyutu_mb: u64,
    zorunlu: bool,
    ne_icin: &'static str,
    sha256: Option<&'static str>,
}

const MOTORLAR: &[Motor] = &[
    Motor { ad:"aria2c", dosya:"aria2c.exe", adres:"https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip", zip_icinde:Some("aria2c.exe"), indirme_boyutu_mb:3, zorunlu:true, ne_icin:"indirme motoru", sha256:None },
    Motor { ad:"yt-dlp", dosya:"yt-dlp.exe", adres:"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe", zip_icinde:None, indirme_boyutu_mb:17, zorunlu:false, ne_icin:"video sitelerinden indirme (YouTube, Instagram, TikTok...)", sha256:None },
    Motor { ad:"ffmpeg", dosya:"ffmpeg.exe", adres:"https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-lgpl-8.1.zip", zip_icinde:Some("bin/ffmpeg.exe"), indirme_boyutu_mb:164, zorunlu:false, ne_icin:"ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", sha256:None },
    Motor { ad:"cloudflared", dosya:"cloudflared.exe", adres:"https://github.com/cloudflare/cloudflared/releases/download/2026.9.1/cloudflared-windows-amd64.exe", zip_icinde:None, indirme_boyutu_mb:21, zorunlu:false, ne_icin:"farkli aglardan guvenli dosya paylasimi", sha256:Some("2837888cc0f5d58f15b6dc478376de90b4d3ba5241c7947455d1e0a0df429712") },
];

pub const EKSIK_NE_YAPAMAZ: &[(&str, &str)] = &[
    ("yt-dlp", "video sitelerinden indirme"),
    (
        "ffmpeg",
        "1080p ve ustu video (ses ayri geliyor) ve mp3'e cevirme",
    ),
];

fn motor(ad: &str) -> Option<&'static Motor> {
    MOTORLAR.iter().find(|m| m.ad == ad)
}
fn hedef(app_dir: &Path, motor: &Motor) -> PathBuf {
    app_dir.join("engine").join(motor.dosya)
}

pub fn var_mi(app_dir: &Path, ad: &str) -> bool {
    motor(ad).is_some_and(|m| hedef(app_dir, m).exists())
}

pub fn sistemde(app_dir: &Path, ad: &str) -> String {
    let Some(motor) = motor(ad) else {
        return String::new();
    };
    if hedef(app_dir, motor).exists() {
        return String::new();
    }
    find_system(motor)
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default()
}

fn find_system(motor: &Motor) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let exe = dir.join(motor.dosya);
        if exe.is_file() {
            return Some(exe);
        }
        #[cfg(not(windows))]
        {
            let exe = dir.join(motor.ad);
            use std::os::unix::fs::PermissionsExt;
            if exe
                .metadata()
                .is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
            {
                return Some(exe);
            }
        }
    }
    None
}

/// Prefer bundled engines; None means no bundled or system executable exists.
pub fn yol(app_dir: &Path, ad: &str) -> Option<PathBuf> {
    let motor = motor(ad)?;
    let local = hedef(app_dir, motor);
    if local.exists() {
        Some(local)
    } else {
        find_system(motor)
    }
}

fn boyut(path: &Path) -> f64 {
    path.metadata()
        .map(|m| (m.len() as f64 / 1_048_576.0 * 10.0).round_ties_even() / 10.0)
        .unwrap_or(0.0)
}

pub fn durum(app_dir: &Path) -> Json {
    let mut result = serde_json::Map::new();
    for m in MOTORLAR {
        let target = hedef(app_dir, m);
        let system = sistemde(app_dir, m.ad);
        let source = if target.exists() {
            "paket"
        } else if !system.is_empty() {
            "sistem"
        } else {
            "yok"
        };
        result.insert(m.ad.into(), json!({"var": target.exists(), "kaynak":source, "sistem_yolu":system, "kullanilabilir":source != "yok", "boyut_mb":boyut(&target), "zorunlu":m.zorunlu, "ne_icin":m.ne_icin, "indirme_boyutu_mb":m.indirme_boyutu_mb}));
    }
    Json::Object(result)
}

pub fn eksikler(app_dir: &Path, sadece_istege_bagli: bool) -> Vec<String> {
    MOTORLAR
        .iter()
        .filter(|m| !hedef(app_dir, m).exists() && (!sadece_istege_bagli || !m.zorunlu))
        .map(|m| m.ad.to_owned())
        .collect()
}

fn dogrula(path: &Path) -> bool {
    for flag in ["--version", "-version"] {
        let Ok(output) = tempfile::tempfile() else {
            return false;
        };
        let Ok(writer) = output.try_clone() else {
            return false;
        };
        let mut command = crate::hidden_command(path);
        let Ok(mut child) = command.arg(flag).stdout(Stdio::from(writer)).spawn() else {
            return false;
        };
        let deadline = Instant::now() + Duration::from_secs(30);
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    if status.success() {
                        use std::io::{Seek, SeekFrom};
                        let mut output = output;
                        let mut bytes = Vec::new();
                        if output.seek(SeekFrom::Start(0)).is_ok()
                            && output.read_to_end(&mut bytes).is_ok()
                            && bytes.iter().any(|b| !b.is_ascii_whitespace())
                        {
                            return true;
                        }
                    }
                    break;
                }
                Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(50)),
                _ => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return false;
                }
            }
        }
    }
    false
}

pub fn indir(app_dir: &Path, ad: &str, ilerleme: &dyn Fn(u64, u64)) -> Result<Json> {
    let motor = motor(ad).ok_or_else(|| AfuError::Invalid(format!("bilinmeyen motor: {ad}")))?;
    install(app_dir, motor, motor.adres, ilerleme)
}

fn install(
    app_dir: &Path,
    motor: &Motor,
    address: &str,
    progress: &dyn Fn(u64, u64),
) -> Result<Json> {
    fs::create_dir_all(app_dir.join("engine"))?;
    let target = hedef(app_dir, motor);
    let temp = tempfile::Builder::new().prefix("afudm_motor_").tempdir()?;
    let mut downloaded = temp.path().join(if motor.zip_icinde.is_some() {
        "paket.zip"
    } else {
        motor.dosya
    });
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(60)))
        .build()
        .into();
    let mut response = agent
        .get(address)
        .header("User-Agent", "AfuDM/1.0")
        .call()
        .map_err(|_| AfuError::Engine(format!("{} indirilemedi", motor.dosya)))?;
    let total = response
        .headers()
        .get("Content-Length")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);
    {
        let mut reader = response.body_mut().as_reader();
        let mut file = File::create(&downloaded)?;
        let mut buffer = vec![0; 256 * 1024];
        let mut read = 0;
        loop {
            let n = reader.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            file.write_all(&buffer[..n])?;
            read += n as u64;
            progress(read, total);
        }
    }
    if let Some(suffix) = motor.zip_icinde {
        let mut archive = zip::ZipArchive::new(File::open(&downloaded)?)
            .map_err(|e| AfuError::Engine(e.to_string()))?;
        let index = (0..archive.len())
            .find(|i| {
                archive
                    .by_index(*i)
                    .is_ok_and(|f| f.name().replace('\\', "/").ends_with(suffix))
            })
            .ok_or_else(|| AfuError::Engine(format!("zip icinde {suffix} bulunamadi")))?;
        downloaded = temp.path().join(motor.dosya);
        let mut entry = archive
            .by_index(index)
            .map_err(|e| AfuError::Engine(e.to_string()))?;
        std::io::copy(&mut entry, &mut File::create(&downloaded)?)?;
    }
    if let Some(expected) = motor.sha256 {
        let mut digest = Sha256::new();
        let mut file = File::open(&downloaded)?;
        let mut buffer = vec![0; 1024 * 1024];
        loop {
            let n = file.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            digest.update(&buffer[..n]);
        }
        if !format!("{:x}", digest.finalize()).eq_ignore_ascii_case(expected) {
            return Err(AfuError::Engine(format!(
                "{} SHA-256 dogrulamasi basarisiz",
                motor.dosya
            )));
        }
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&downloaded, fs::Permissions::from_mode(0o755))?;
    }
    if !dogrula(&downloaded) {
        return Err(AfuError::Engine(format!(
            "{} indi ama calismadi (bozuk indirme?)",
            motor.dosya
        )));
    }
    let backup = target.with_extension("exe.eski");
    if target.exists() {
        if backup.exists() {
            fs::remove_file(&backup)?;
        }
        fs::rename(&target, &backup)?;
    }
    // shutil.move also supports temporary directories on a different volume.
    if fs::rename(&downloaded, &target).is_err() {
        fs::copy(&downloaded, &target)?;
    }
    if backup.exists() {
        let _ = fs::remove_file(backup);
    }
    Ok(json!({"ad":motor.ad, "dosya":target.to_string_lossy(), "boyut_mb":boyut(&target)}))
}

#[cfg(test)]
mod tests;
