//! Format secimi, dosya adi temizligi, birlesik cikti bulma ve arac yollari.
//! Port of video/ytdlp.py (QUALITY_FORMATS, COMBINED_FORMATS, format_secimi, guvenli_ad,
//! birlesik_dosya_bul, ffmpeg_hazir, is_video_site) ve paths.py'nin arac yolu kurali.

use regex::Regex;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::UNIX_EPOCH;

/// ffmpeg VARKEN: en iyi video + en iyi ses ayri inip mp4'e birlestirilir.
fn kalite_formati(kalite: &str) -> Option<&'static str> {
    Some(match kalite {
        "best" => "bestvideo*+bestaudio/best",
        "2160" => "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1440" => "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "1080" => "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720" => "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480" => "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio" => "bestaudio/best",
        _ => return None,
    })
}

/// ffmpeg YOKKEN: iki izi de MP4 ailesinden iste, birlestirmeyi biz yapalim.
fn kendi_mux(yukseklik: &str) -> String {
    format!(
        "bv*{h}[ext=mp4]+ba[ext=m4a]/best{h}[ext=mp4][acodec!=none][vcodec!=none]/best{h}[acodec!=none][vcodec!=none]/best{h}",
        h = yukseklik
    )
}

fn birlesik_kalite_formati(kalite: &str) -> Option<String> {
    Some(match kalite {
        "best" => kendi_mux(""),
        "2160" => kendi_mux("[height<=2160]"),
        "1440" => kendi_mux("[height<=1440]"),
        "1080" => kendi_mux("[height<=1080]"),
        "720" => kendi_mux("[height<=720]"),
        "480" => kendi_mux("[height<=480]"),
        "audio" => "bestaudio[ext=m4a]/bestaudio/best".to_string(),
        _ => return None,
    })
}

/// Python format_secimi(quality, audio_only, birlestirilebilir): yt-dlp `-f` ifadesi.
/// birlestirilebilir=false ise ayri video+ses ISTENMEZ (ffmpeg'siz kurulum).
pub(crate) fn format_secimi(kalite: &str, audio_only: bool, birlestirilebilir: bool) -> String {
    let kalite = if audio_only || kalite == "audio" {
        "audio"
    } else {
        kalite
    };
    let rakam = !kalite.is_empty() && kalite.chars().all(|c| c.is_ascii_digit());
    if rakam && kalite_formati(kalite).is_none() {
        if let Ok(yukseklik) = kalite.parse::<u64>() {
            let h = format!("[height<={yukseklik}]");
            return if birlestirilebilir {
                format!("bestvideo{h}+bestaudio/best{h}")
            } else {
                kendi_mux(&h)
            };
        }
    }
    if birlestirilebilir {
        kalite_formati(kalite)
            .unwrap_or("bestvideo*+bestaudio/best")
            .to_string()
    } else {
        birlesik_kalite_formati(kalite)
            .unwrap_or_else(|| birlesik_kalite_formati("best").unwrap_or_default())
    }
}

/// Windows dosya adinda yasak karakterleri at, sonundaki nokta/bosluğu kirp.
pub(crate) fn guvenli_ad(ad: &str) -> String {
    const SINIR: usize = 150;
    let temiz: String = ad
        .chars()
        .map(|c| {
            if "<>:\"/\\|?*".contains(c) || (c as u32) < 32 {
                '_'
            } else {
                c
            }
        })
        .collect();
    let birlesik = temiz.split_whitespace().collect::<Vec<_>>().join(" ");
    let kesik: String = birlesik.chars().take(SINIR).collect();
    let sonuc = kesik.trim_end_matches(['.', ' ']).to_string();
    if sonuc.is_empty() {
        "video".to_string()
    } else {
        sonuc
    }
}

/// `aday`, `klasor` altinda mi (cozumlenmis yollarla)?
fn klasor_icinde(klasor: &Path, aday: &Path) -> bool {
    match (klasor.canonicalize(), aday.canonicalize()) {
        (Ok(k), Ok(a)) => a.starts_with(k),
        _ => false,
    }
}

fn parca_adi_regex() -> Option<&'static Regex> {
    static RE: OnceLock<Option<Regex>> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)^(?P<stem>.+)\.f\d+(?P<ext>\.[^.]+)$").ok())
        .as_ref()
}

fn mtime_ns(yol: &Path) -> u128 {
    std::fs::metadata(yol)
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map_or(0, |d| d.as_nanos())
}

/// Python birlesik_dosya_bul(): eski yt-dlp parca adindan diskteki birlesik ciktiyi bulur.
pub(crate) fn birlesik_dosya_bul(dest_dir: &Path, dosya_adi: &str) -> Option<PathBuf> {
    if dosya_adi.is_empty() {
        return None;
    }
    let klasor = dest_dir;
    let Some(eslesme) = parca_adi_regex().and_then(|re| re.captures(dosya_adi)) else {
        let mevcut = klasor.join(dosya_adi);
        if !mevcut.is_file() || !klasor_icinde(klasor, &mevcut) {
            return None;
        }
        return Some(mevcut);
    };
    let govde = &eslesme["stem"];
    let mut adaylar: Vec<(u128, u8, PathBuf)> = Vec::new();
    for (uzanti, oncelik) in [(".mp4", 2u8), (".mkv", 1), (".webm", 0)] {
        let aday = klasor.join(format!("{govde}{uzanti}"));
        if klasor_icinde(klasor, &aday) && aday.is_file() {
            adaylar.push((mtime_ns(&aday), oncelik, aday));
        }
    }
    // En yeni mtime; esitlikte mp4 > mkv > webm (Python max key ile ayni)
    adaylar
        .into_iter()
        .max_by_key(|(zaman, oncelik, _)| (*zaman, *oncelik))
        .map(|(_, _, yol)| yol)
}

/// Sistem PATH'inde arac ara (Python bundled_or_system'in ikinci kolu).
fn path_de_bul(ad: &str) -> Option<PathBuf> {
    let yol = std::env::var_os("PATH")?;
    std::env::split_paths(&yol)
        .map(|d| d.join(ad))
        .find(|p| p.is_file())
}

/// engine\ffmpeg.exe (paketli) ya da sistemdeki ffmpeg. Yoksa None (Python ffmpeg_hazir()==False).
pub(crate) fn ffmpeg_yolu(app_dir: &Path) -> Option<PathBuf> {
    let ad = if cfg!(windows) {
        "ffmpeg.exe"
    } else {
        "ffmpeg"
    };
    let yerel = app_dir.join("engine").join(ad);
    if yerel.is_file() {
        return Some(yerel);
    }
    path_de_bul(ad)
}

/// Paketli aria2c (Python paths.ARIA2C). Yoksa None: dis indirici kullanilmaz.
pub(crate) fn aria2c_yolu(app_dir: &Path) -> Option<PathBuf> {
    let ad = if cfg!(windows) {
        "aria2c.exe"
    } else {
        "aria2c"
    };
    let yerel = app_dir.join("engine").join(ad);
    yerel.is_file().then_some(yerel)
}

/// Dosya linki mi, video sayfasi mi? (Python is_video_site)
#[allow(dead_code)] // queue.rs (C) tur tespitine baglayana kadar
pub(crate) fn is_video_site(url: &str) -> bool {
    let kucuk = url.to_lowercase();
    let lowered = kucuk.split('?').next().unwrap_or("");
    const DOSYA_UZANTILARI: &[&str] = &[
        ".zip", ".rar", ".7z", ".exe", ".msi", ".iso", ".pdf", ".apk", ".dmg", ".tar", ".gz",
        ".torrent", ".deb", ".rpm", ".img",
    ];
    if DOSYA_UZANTILARI.iter().any(|u| lowered.ends_with(u)) {
        return false;
    }
    if url.starts_with("magnet:") {
        return false;
    }
    const IPUCLARI: &[&str] = &[
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "tiktok.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "vimeo.com",
        "dailymotion.com",
        "twitch.tv",
        "reddit.com",
        "soundcloud.com",
        "bilibili.com",
        "odnoklassniki",
        "vk.com",
        "pinterest.com",
        "linkedin.com",
        "threads.net",
        "rumble.com",
    ];
    if IPUCLARI.iter().any(|h| lowered.contains(h)) {
        return true;
    }
    lowered.contains(".m3u8") || lowered.contains(".mpd")
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn birlesik_formatlar_ve_rakamli_kalite() {
        assert_eq!(
            format_secimi("best", false, true),
            "bestvideo*+bestaudio/best"
        );
        assert_eq!(
            format_secimi("720", false, true),
            "bestvideo[height<=720]+bestaudio/best[height<=720]"
        );
        assert_eq!(
            format_secimi("360", false, true),
            "bestvideo[height<=360]+bestaudio/best[height<=360]"
        );
        assert_eq!(
            format_secimi("360", false, false),
            kendi_mux("[height<=360]")
        );
        assert_eq!(
            format_secimi("1080", false, false),
            kendi_mux("[height<=1080]")
        );
        assert_eq!(format_secimi("best", false, false), kendi_mux(""));
    }

    #[test]
    fn ses_istegi_audio_formatina_gider() {
        assert_eq!(format_secimi("best", true, true), "bestaudio/best");
        assert_eq!(
            format_secimi("1080", true, false),
            "bestaudio[ext=m4a]/bestaudio/best"
        );
        assert_eq!(
            format_secimi("bilinmeyen", false, true),
            "bestvideo*+bestaudio/best"
        );
    }

    #[test]
    fn guvenli_ad_yasak_karakterleri_ve_bosluklari_temizler() {
        assert_eq!(guvenli_ad("a<b>:c  d. "), "a_b__c d");
        assert_eq!(guvenli_ad("   "), "video");
        assert_eq!(guvenli_ad(&"x".repeat(200)).chars().count(), 150);
    }

    #[test]
    fn video_sitesi_ayirimi() {
        assert!(is_video_site("https://www.youtube.com/watch?v=abc"));
        assert!(is_video_site("https://ornek.test/yayin.m3u8?x=1"));
        assert!(!is_video_site("https://ornek.test/dosya.ZIP"));
        assert!(!is_video_site("magnet:?xt=urn:btih:abc"));
        assert!(!is_video_site("https://ornek.test/sayfa"));
    }

    #[test]
    fn birlesik_cikti_parca_adindan_bulunur() {
        let d = std::env::temp_dir().join(format!("afudm-secim-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).expect("klasor");
        std::fs::write(d.join("Baslik.mp4"), b"x").expect("yaz");
        assert_eq!(
            birlesik_dosya_bul(&d, "Baslik.f137.mp4").map(|p| p.file_name().map(|n| n.to_owned())),
            Some(Some("Baslik.mp4".into()))
        );
        assert!(birlesik_dosya_bul(&d, "../disari.mp4").is_none());
        assert!(birlesik_dosya_bul(&d, "").is_none());
        assert!(birlesik_dosya_bul(&d, "Yok.f1.mp4").is_none());
    }
}
