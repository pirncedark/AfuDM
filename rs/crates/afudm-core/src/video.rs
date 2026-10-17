//! SAHIBI: Ekip D (claude kod ajani). Python: core/manager.py (video dali, probe_video) + video/ytdlp.py (probe).
//! Imzalar afudm-types::ManagerApi ile sabit; degistirilmez.
//! DURUM: probe_video tasindi. video_ekle_ic (VideoJob surec yoneticisi, video/ytdlp.py 275-831,
//! video/mp4mux.py, video/mp4kutu.py) henuz tasinmadi; bkz. docs/sonuc/SONUC_D.md.

use crate::Manager;
use afudm_types::{AfuError, Json, JsonMap, Result};
use serde_json::json;
use std::io::Read;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// Ekip D (claude kod ajani) kendi calisma durumunu buraya koyar (Manager::video_state).
#[derive(Default)]
pub struct State {}

/// Python ytdlp.probe varsayilan zaman asimi (sn).
const PROBE_ZAMAN_ASIMI: Duration = Duration::from_secs(90);

/// Python paths._bundled_or_system("yt-dlp.exe"): once uygulama klasorundeki engine\yt-dlp.exe,
/// yoksa sistemdeki yt-dlp. (Varsayim: Python BASE = Manager::app_dir.)
fn ytdlp_yolu(app_dir: &Path) -> String {
    let yerel = app_dir.join("engine").join("yt-dlp.exe");
    if yerel.exists() {
        yerel.display().to_string()
    } else {
        "yt-dlp".to_string()
    }
}

/// Python: `x.get(k)` ile ayni; yoksa null.
fn al(v: &Json, anahtar: &str) -> Json {
    v.get(anahtar).cloned().unwrap_or(Json::Null)
}

/// Python truthiness (null/false/0/""/bos dizi-nesne falsy).
fn dogru_mu(v: &Json) -> bool {
    match v {
        Json::Null => false,
        Json::Bool(b) => *b,
        Json::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
    }
}

/// Python ytdlp.probe'un JSON'u isleyen kismi: yt-dlp -J ciktisini Afu sekline cevirir.
pub(crate) fn probe_sonucu(url: &str, data: &Json) -> Json {
    let formats: Vec<Json> = data
        .get("formats")
        .and_then(|f| f.as_array())
        .map(|dizi| {
            dizi.iter()
                .map(|fmt| {
                    let filesize = al(fmt, "filesize");
                    let filesize = if dogru_mu(&filesize) { filesize } else { al(fmt, "filesize_approx") };
                    json!({
                        "id": al(fmt, "format_id"),
                        "ext": al(fmt, "ext"),
                        "height": al(fmt, "height"),
                        "width": al(fmt, "width"),
                        "fps": al(fmt, "fps"),
                        "vcodec": al(fmt, "vcodec"),
                        "acodec": al(fmt, "acodec"),
                        "filesize": filesize,
                        "note": al(fmt, "format_note"),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    let title = al(data, "title");
    let entries = match data.get("entries") {
        Some(e) if dogru_mu(e) => e.as_array().map_or(0, |a| a.len()),
        _ => 0,
    };
    json!({
        "title": if dogru_mu(&title) { title } else { json!(url) },
        "duration": al(data, "duration"),
        "thumbnail": al(data, "thumbnail"),
        "uploader": al(data, "uploader"),
        "is_playlist": data.get("_type").and_then(|t| t.as_str()) == Some("playlist"),
        "entries": entries,
        "formats": formats,
    })
}

/// Surec calistirir; zaman asiminda oldurur. Donen: (cikis kodu, stdout, stderr).
fn surec_calistir(yol: &str, args: &[&str], zaman_asimi: Duration) -> Result<(Option<i32>, Vec<u8>, Vec<u8>)> {
    let mut komut = Command::new(yol);
    komut.args(args).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(0x0800_0000); // CREATE_NO_WINDOW (Python ytdlp.CREATE_NO_WINDOW)
    }
    let mut cocuk = komut.spawn()?;
    let mut out_pipe = cocuk.stdout.take();
    let mut err_pipe = cocuk.stderr.take();
    let out_is = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(p) = out_pipe.as_mut() {
            let _ = p.read_to_end(&mut b);
        }
        b
    });
    let err_is = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(p) = err_pipe.as_mut() {
            let _ = p.read_to_end(&mut b);
        }
        b
    });
    let baslangic = Instant::now();
    let kod = loop {
        if let Some(durum) = cocuk.try_wait()? {
            break durum.code();
        }
        if baslangic.elapsed() >= zaman_asimi {
            let _ = cocuk.kill();
            let _ = cocuk.wait();
            return Err(AfuError::Engine(format!(
                "yt-dlp {} sn icinde yanit vermedi",
                zaman_asimi.as_secs()
            )));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let stdout = out_is.join().unwrap_or_default();
    let stderr = err_is.join().unwrap_or_default();
    Ok((kod, stdout, stderr))
}

/// Python probe_video -> ytdlp.probe(url): video bilgisi ve format listesi (indirmeden once).
pub fn probe_video(m: &Manager, url: &str) -> Result<Json> {
    let yol = ytdlp_yolu(&m.app_dir);
    let args = [
        "-J",
        "--no-warnings",
        "--no-playlist",
        // --encoding OLMADAN Turkce harfler '?' olur (Python notu); utf-8 zorunlu.
        "--encoding",
        "utf-8",
        "--flat-playlist",
        url,
    ];
    let (kod, stdout, stderr) = surec_calistir(&yol, &args, PROBE_ZAMAN_ASIMI)?;
    if kod != Some(0) {
        let metin = String::from_utf8_lossy(&stderr);
        let kirpik = metin.trim();
        let mesaj = if kirpik.is_empty() { "yt-dlp bilgi alamadi" } else { kirpik };
        return Err(AfuError::Engine(mesaj.chars().take(500).collect()));
    }
    let data: Json = serde_json::from_str(&String::from_utf8_lossy(&stdout))?;
    Ok(probe_sonucu(url, &data))
}

/// Python manager.py add() icindeki video dali (_launch_video + VideoJob).
/// TODO(Ekip D): VideoJob surec yoneticisi (video/ytdlp.py 275-831) henuz tasinmadi.
#[allow(dead_code)] // C ekibi cagirana kadar stub
pub(crate) fn video_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json> {
    let _ = (m, req);
    todo!("video_ekle_ic")
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn probe_formatlari_ve_varsayilanlari_cikarir() {
        let data = json!({
            "title": null,
            "duration": 12,
            "_type": "playlist",
            "entries": [1, 2, 3],
            "formats": [
                {"format_id": "137", "ext": "mp4", "height": 1080, "width": 1920,
                 "fps": 30, "vcodec": "avc1", "acodec": "none",
                 "filesize": 0, "filesize_approx": 5000, "format_note": "1080p"}
            ]
        });
        let s = probe_sonucu("https://ornek.test/v", &data);
        assert_eq!(s["title"], json!("https://ornek.test/v"));
        assert_eq!(s["is_playlist"], json!(true));
        assert_eq!(s["entries"], json!(3));
        assert_eq!(s["formats"][0]["filesize"], json!(5000));
        assert_eq!(s["formats"][0]["id"], json!("137"));
    }

    #[test]
    fn entries_yoksa_sifir_ve_playlist_degil() {
        let s = probe_sonucu("u", &json!({"title": "Baslik"}));
        assert_eq!(s["entries"], json!(0));
        assert_eq!(s["is_playlist"], json!(false));
        assert_eq!(s["formats"], json!([]));
        assert_eq!(s["title"], json!("Baslik"));
    }
}
