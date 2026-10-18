//! yt-dlp / aria2c cikti ayristirma. Port of video/ytdlp.py (_DEST_RE, _ARIA_RE, _UNITS,
//! _eta_seconds, _parse_aria, _parse_progress, _num, yedek_karari).

use regex::Regex;
use std::sync::OnceLock;

/// yt-dlp --progress-template ile gelen satirin oneki (Python PROGRESS_TAG).
pub(crate) const PROGRESS_TAG: &str = "AFUDM";
pub(crate) const PROGRESS_TEMPLATE: &str = "AFUDM|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s";

fn dest_regex() -> Option<&'static Regex> {
    static RE: OnceLock<Option<Regex>> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r#"\[(?P<tag>download|Merger|VideoRemuxer|VideoConvertor|ExtractAudio|Fixup[^\]]*)\](?:.*(?:(?:Destination:|\bto\b|\binto\b)\s*(?P<target>.+)|\bof\s+(?P<quoted>"[^"]+"))|(?P<already>.+?)\s+has already been downloaded)$"#,
        )
        .ok()
    })
    .as_ref()
}

fn aria_regex() -> Option<&'static Regex> {
    static RE: OnceLock<Option<Regex>> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"\[#\w+\s+(?P<done>[\d.]+)(?P<du>[KMGT]?i?B)/(?P<total>[\d.]+)(?P<tu>[KMGT]?i?B)\((?P<pct>\d+)%\)(?:\s+CN:(?P<cn>\d+))?(?:\s+DL:(?P<dl>[\d.]+)(?P<su>[KMGT]?i?B))?(?:\s+ETA:(?P<eta>\S+?))?\]",
        )
        .ok()
    })
    .as_ref()
}

fn eta_regex() -> Option<&'static Regex> {
    static RE: OnceLock<Option<Regex>> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(\d+)([hms])").ok()).as_ref()
}

/// Python _UNITS: birim -> bayt carpani. Bilinmeyen birim 1 kabul edilir.
fn birim_carpani(birim: &str) -> f64 {
    match birim {
        "KiB" => 1024.0,
        "MiB" => 1024.0 * 1024.0,
        "GiB" => 1024.0 * 1024.0 * 1024.0,
        "TiB" => 1024.0_f64.powi(4),
        "KB" => 1000.0,
        "MB" => 1_000_000.0,
        "GB" => 1_000_000_000.0,
        "TB" => 1_000_000_000_000.0,
        _ => 1.0,
    }
}

/// Python VideoJob._bytes(): sayi+birim -> bayt; bozuk sayi 0.
pub(crate) fn bayt(miktar: &str, birim: &str) -> u64 {
    match miktar.parse::<f64>() {
        Ok(v) => (v * birim_carpani(birim)) as u64,
        Err(_) => 0,
    }
}

/// Python _eta_seconds: "2s", "1m30s", "1h2m" -> saniye.
pub(crate) fn eta_saniye(metin: &str) -> u64 {
    let Some(re) = eta_regex() else {
        return 0;
    };
    re.captures_iter(metin)
        .map(|c| {
            let sayi: u64 = c[1].parse().unwrap_or(0);
            sayi * match &c[2] {
                "h" => 3600,
                "m" => 60,
                _ => 1,
            }
        })
        .sum()
}

/// aria2c ozet satiri: `[#da19cb 2.8MiB/9.7MiB(29%) CN:10 DL:3.3MiB ETA:2s]`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct AriaIlerleme {
    pub indirilen: u64,
    /// 0 ise bilinmiyor (eski toplam korunur).
    pub toplam: u64,
    /// Yalniz DL: alani varsa.
    pub hiz: Option<u64>,
    pub eta: u64,
}

pub(crate) fn aria_satiri(satir: &str) -> Option<AriaIlerleme> {
    let c = aria_regex()?.captures(satir)?;
    Some(AriaIlerleme {
        indirilen: bayt(&c["done"], &c["du"]),
        toplam: bayt(&c["total"], &c["tu"]),
        hiz: c
            .name("dl")
            .map(|dl| bayt(dl.as_str(), c.name("su").map_or("", |s| s.as_str()))),
        eta: eta_saniye(c.name("eta").map_or("", |e| e.as_str())),
    })
}

/// `AFUDM|done|total|total_est|speed|eta` satiri (Python _parse_progress).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ProgressSatiri {
    pub indirilen: u64,
    pub toplam: u64,
    pub toplam_tahmini: u64,
    pub hiz: u64,
    pub eta: u64,
}

/// Python _num: NA/None/bos ya da bozuk -> 0.
fn sayi(deger: &str) -> u64 {
    if matches!(deger, "NA" | "None" | "") {
        return 0;
    }
    deger
        .parse::<f64>()
        .map_or(0, |f| if f > 0.0 { f as u64 } else { 0 })
}

pub(crate) fn progress_satiri(satir: &str) -> Option<ProgressSatiri> {
    let parcalar: Vec<&str> = satir.split('|').collect();
    if parcalar.len() < 6 {
        return None;
    }
    Some(ProgressSatiri {
        indirilen: sayi(parcalar[1]),
        toplam: sayi(parcalar[2]),
        toplam_tahmini: sayi(parcalar[3]),
        hiz: sayi(parcalar[4]),
        eta: sayi(parcalar[5]),
    })
}

/// yt-dlp hedef satiri: etiket ("download" | "Merger" ...) ve hedef dosya adi.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct HedefSatiri {
    pub etiket: String,
    pub hedef: String,
}

pub(crate) fn hedef_satiri(satir: &str) -> Option<HedefSatiri> {
    let c = dest_regex()?.captures(satir)?;
    let mut hedef = c
        .name("target")
        .or_else(|| c.name("quoted"))
        .or_else(|| c.name("already"))
        .map_or("", |m| m.as_str())
        .trim()
        .to_string();
    if hedef.len() >= 2 && hedef.starts_with('"') && hedef.ends_with('"') {
        hedef = hedef[1..hedef.len() - 1].to_string();
    }
    if hedef.is_empty() {
        return None;
    }
    Some(HedefSatiri {
        etiket: c["tag"].to_string(),
        hedef,
    })
}

/// Python yedek_karari(): dusen kosudan sonra NE denenecek: "aria2c" | "cerezsiz" | "" (pes).
pub(crate) fn yedek_karari(
    metin: &str,
    aria2c_var: bool,
    cerez_var: bool,
    aria_denendi: bool,
    cerezsiz_denendi: bool,
) -> &'static str {
    if aria2c_var && !aria_denendi && metin.contains("aria2c exited") {
        return "aria2c";
    }
    if cerez_var && !cerezsiz_denendi && metin.contains("403") {
        return "cerezsiz";
    }
    ""
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn aria_ozet_satiri_okunur() {
        let s = aria_satiri("[#da19cb 2.8MiB/9.7MiB(29%) CN:10 DL:3.3MiB ETA:1m30s]")
            .expect("eslesmeli");
        assert_eq!(s.indirilen, (2.8 * 1024.0 * 1024.0) as u64);
        assert_eq!(s.toplam, (9.7 * 1024.0 * 1024.0) as u64);
        assert_eq!(s.hiz, Some((3.3 * 1024.0 * 1024.0) as u64));
        assert_eq!(s.eta, 90);
        assert!(aria_satiri("duz metin").is_none());
    }

    #[test]
    fn eta_bicimleri() {
        assert_eq!(eta_saniye("2s"), 2);
        assert_eq!(eta_saniye("1h2m"), 3720);
        assert_eq!(eta_saniye(""), 0);
    }

    #[test]
    fn ilerleme_satiri_na_ve_bozuk_degerleri_sifirlar() {
        let s = progress_satiri("AFUDM|100|NA|250.5|NA|7").expect("6 parca");
        assert_eq!(s.indirilen, 100);
        assert_eq!(s.toplam, 0);
        assert_eq!(s.toplam_tahmini, 250);
        assert_eq!(s.hiz, 0);
        assert_eq!(s.eta, 7);
        assert!(progress_satiri("AFUDM|1|2").is_none());
    }

    #[test]
    fn hedef_satirlari_ayristirilir() {
        let s =
            hedef_satiri("[download] Destination: C:\\indir\\Baslik.f137.mp4").expect("indirme");
        assert_eq!(s.etiket, "download");
        assert_eq!(s.hedef, "C:\\indir\\Baslik.f137.mp4");
        let m = hedef_satiri("[Merger] Merging formats into \"C:\\indir\\Baslik.mp4\"")
            .expect("birlestirme");
        assert_eq!(m.etiket, "Merger");
        assert_eq!(m.hedef, "C:\\indir\\Baslik.mp4"); // dis tirnaklar soyulur
        let v =
            hedef_satiri("[download] Baslik.mp4 has already been downloaded").expect("var olan");
        assert_eq!(v.hedef, "Baslik.mp4");
    }

    #[test]
    fn yedek_karari_yalniz_belli_hatalarda_tekrarlar() {
        assert_eq!(
            yedek_karari("aria2c exited with code 22", true, false, false, false),
            "aria2c"
        );
        assert_eq!(
            yedek_karari("aria2c exited with code 22", true, false, true, false),
            ""
        );
        assert_eq!(
            yedek_karari("HTTP Error 403: Forbidden", false, true, false, false),
            "cerezsiz"
        );
        assert_eq!(
            yedek_karari("Video unavailable", true, true, false, false),
            ""
        );
    }
}
