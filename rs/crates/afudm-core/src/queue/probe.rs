//! Python core/dosya_adi.py: Content-Disposition (RFC 6266/5987), MIME uzantisi, guvenli dosya adi,
//! probe_url_info (HEAD + 1 baytlik Range GET) ve Manager.guess_name / clean_title.
use super::dosya_adi::decode;
use afudm_types::{Json, Result};
use serde_json::json;
use std::time::Duration;
use ureq::ResponseExt;

const VARSAYILAN_AD: &str = "download";
const EN_FAZLA_KARAKTER: usize = 200;
const TARAYICI_UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36";
const DOS_AYGIT_ADLARI: [&str; 22] = [
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
    "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

/// Python MIME_UZANTILARI (yaygin turlerin guvenli uzanti karsiliklari).
const MIME_UZANTILARI: &[(&str, &str)] = &[
    ("application/zip", "zip"),
    ("application/x-zip-compressed", "zip"),
    ("application/gzip", "gz"),
    ("application/x-gzip", "gz"),
    ("application/x-tar", "tar"),
    ("application/x-7z-compressed", "7z"),
    ("application/vnd.rar", "rar"),
    ("application/x-rar-compressed", "rar"),
    ("application/x-bzip2", "bz2"),
    ("application/x-xz", "xz"),
    ("application/zstd", "zst"),
    ("application/x-msdownload", "exe"),
    ("application/x-msdos-program", "exe"),
    ("application/vnd.microsoft.portable-executable", "exe"),
    ("application/x-msi", "msi"),
    ("application/x-ms-installer", "msi"),
    ("application/x-apple-diskimage", "dmg"),
    ("application/vnd.debian.binary-package", "deb"),
    ("application/x-deb", "deb"),
    ("application/x-rpm", "rpm"),
    ("application/x-redhat-package-manager", "rpm"),
    ("application/vnd.android.package-archive", "apk"),
    ("application/x-iso9660-image", "iso"),
    ("application/pdf", "pdf"),
    ("application/epub+zip", "epub"),
    ("application/rtf", "rtf"),
    ("application/msword", "doc"),
    (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    ("application/vnd.ms-excel", "xls"),
    (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    ("application/vnd.ms-powerpoint", "ppt"),
    (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
    ),
    ("text/plain", "txt"),
    ("text/html", "html"),
    ("text/css", "css"),
    ("text/csv", "csv"),
    ("text/markdown", "md"),
    ("application/json", "json"),
    ("application/xml", "xml"),
    ("text/xml", "xml"),
    ("application/javascript", "js"),
    ("text/javascript", "js"),
    ("image/png", "png"),
    ("image/jpeg", "jpg"),
    ("image/gif", "gif"),
    ("image/webp", "webp"),
    ("image/avif", "avif"),
    ("image/svg+xml", "svg"),
    ("image/x-icon", "ico"),
    ("image/vnd.microsoft.icon", "ico"),
    ("video/mp4", "mp4"),
    ("video/webm", "webm"),
    ("video/x-matroska", "mkv"),
    ("video/quicktime", "mov"),
    ("video/x-msvideo", "avi"),
    ("audio/mpeg", "mp3"),
    ("audio/mp4", "m4a"),
    ("audio/x-m4a", "m4a"),
    ("audio/ogg", "ogg"),
    ("application/ogg", "ogg"),
    ("audio/flac", "flac"),
    ("audio/x-flac", "flac"),
    ("audio/wav", "wav"),
    ("audio/x-wav", "wav"),
];

/// Python _unquote: cift tirnagi kaldirir, ters slash kacislarini cozer.
fn unquote(deger: &str) -> String {
    let d = deger.trim();
    if d.len() >= 2 && d.starts_with('"') && d.ends_with('"') {
        let mut cikti = String::new();
        let mut kacis = false;
        for ch in d[1..d.len() - 1].chars() {
            if kacis {
                cikti.push(ch);
                kacis = false;
            } else if ch == '\\' {
                kacis = true;
            } else {
                cikti.push(ch);
            }
        }
        return cikti;
    }
    d.to_string()
}

/// Python _parametreleri_bol: tirnak icindeki noktali virgulleri bolmeden ayirir.
fn parametreleri_bol(baslik: &str) -> Vec<String> {
    let mut parcalar = Vec::new();
    let mut baslangic = 0;
    let mut tirnakta = false;
    let mut kacis = false;
    for (i, ch) in baslik.char_indices() {
        if kacis {
            kacis = false;
            continue;
        }
        match ch {
            '\\' if tirnakta => kacis = true,
            '"' => tirnakta = !tirnakta,
            ';' if !tirnakta => {
                parcalar.push(&baslik[baslangic..i]);
                baslangic = i + 1;
            }
            _ => {}
        }
    }
    parcalar.push(&baslik[baslangic..]);
    parcalar
        .into_iter()
        .map(str::trim)
        .filter(|p| !p.is_empty())
        .map(str::to_string)
        .collect()
}

/// Python _decode_rfc5987: charset'language'pct-encoded bicimi.
fn decode_rfc5987(deger: &str) -> Option<String> {
    let d = unquote(deger);
    let parcalar: Vec<&str> = d.splitn(3, '\'').collect();
    if parcalar.len() != 3 {
        return None;
    }
    let charset = parcalar[0].trim().to_lowercase();
    if !["utf-8", "us-ascii", "iso-8859-1"].contains(&charset.as_str()) {
        return None;
    }
    Some(decode(parcalar[2]))
}

/// Python filename_from_content_disposition: filename* (RFC 5987) varsa oncelikli.
fn filename_from_content_disposition(baslik: &str) -> Option<String> {
    if baslik.is_empty() {
        return None;
    }
    let mut plain: Option<String> = None;
    let mut extended: Option<String> = None;
    for param in parametreleri_bol(baslik) {
        let Some((anahtar, deger)) = param.split_once('=') else {
            continue;
        };
        let anahtar = anahtar.trim().to_lowercase();
        let deger = deger.trim();
        if anahtar == "filename" && plain.is_none() {
            plain = Some(unquote(deger));
        } else if anahtar == "filename*" && extended.is_none() {
            extended = decode_rfc5987(deger);
        }
    }
    let secilen = match extended {
        Some(e) if !e.is_empty() => Some(e),
        _ => plain,
    }?;
    let temiz = secilen.trim();
    (!temiz.is_empty()).then(|| temiz.to_string())
}

/// Python is_plausible_extension: 1-8 karakter, alfanumerik, tamami rakam degil.
fn is_plausible_extension(uzanti: &str) -> bool {
    !uzanti.is_empty()
        && uzanti.chars().count() <= 8
        && uzanti.chars().all(char::is_alphanumeric)
        && !uzanti.chars().all(char::is_numeric)
}

/// Python split_stem_ext: "app-v1.12.0" icin uzanti yok sayilir.
fn split_stem_ext(ad: &str) -> (String, Option<String>) {
    if let Some(nokta) = ad.rfind('.') {
        if nokta > 0 {
            let olasi = &ad[nokta + 1..];
            if is_plausible_extension(olasi) {
                return (ad[..nokta].to_string(), Some(olasi.to_string()));
            }
        }
    }
    (ad.to_string(), None)
}

/// Python ensure_extension: uzanti yoksa MIME turunden uzanti ekler.
fn ensure_extension(ad: &str, content_type: Option<&str>) -> String {
    if ad.is_empty() {
        return VARSAYILAN_AD.to_string();
    }
    if split_stem_ext(ad).1.is_some() {
        return ad.to_string();
    }
    let Some(ct) = content_type.filter(|c| !c.is_empty()) else {
        return ad.to_string();
    };
    let mime = ct.split(';').next().unwrap_or("").trim().to_lowercase();
    match MIME_UZANTILARI.iter().find(|(m, _)| *m == mime) {
        Some((_, uzanti)) => format!("{}.{uzanti}", ad.trim_end_matches(['.', ' '])),
        None => ad.to_string(),
    }
}

/// Python guvenli_dosya_adi: tek guvenli dosya bileseni (yasak karakter, DOS aygit adi, 200 karakter).
pub(crate) fn guvenli_dosya_adi(ad: &str) -> String {
    if ad.is_empty() {
        return String::new();
    }
    let karakterler: String = ad
        .chars()
        .map(|ch| {
            if "<>:\"/\\|?*".contains(ch) || (ch as u32) < 32 {
                '_'
            } else {
                ch
            }
        })
        .collect();
    let bosluksuz = karakterler.split_whitespace().collect::<Vec<_>>().join(" ");
    let mut temiz = bosluksuz.trim_end_matches(['.', ' ']).to_string();
    if temiz.is_empty() {
        return String::new();
    }
    let on = temiz
        .split('.')
        .next()
        .unwrap_or("")
        .trim_end()
        .to_uppercase();
    if DOS_AYGIT_ADLARI.contains(&on.as_str()) {
        temiz.insert(0, '_');
    }
    if temiz.chars().count() > EN_FAZLA_KARAKTER {
        let (kok, uzanti) = split_stem_ext(&temiz);
        temiz = match uzanti {
            Some(u) => {
                let kalan = EN_FAZLA_KARAKTER
                    .saturating_sub(u.chars().count() + 1)
                    .max(1);
                let kok: String = kok.chars().take(kalan).collect();
                format!("{}.{u}", kok.trim_end())
            }
            None => temiz
                .chars()
                .take(EN_FAZLA_KARAKTER)
                .collect::<String>()
                .trim_end_matches(['.', ' '])
                .to_string(),
        };
    }
    temiz
}

/// Python filename_from_url: URL yolunun son gecerli bileseni.
fn filename_from_url(url: &str) -> Option<String> {
    let yol = match url::Url::parse(url) {
        Ok(u) => u.path().to_string(),
        Err(_) => url.split(['?', '#']).next().unwrap_or("").to_string(),
    };
    let son = yol.split('/').rfind(|s| !s.is_empty())?;
    let guvenli = guvenli_dosya_adi(&decode(son));
    (!guvenli.is_empty()).then_some(guvenli)
}

/// Python resolve_filename: magnet dn, Content-Disposition, URL, MIME; sonuc guvenli ad.
pub(crate) fn resolve_filename(
    url: &str,
    content_disposition: Option<&str>,
    content_type: Option<&str>,
) -> String {
    if url.to_lowercase().starts_with("magnet:") {
        let dn = url::Url::parse(url).ok().and_then(|u| {
            u.query_pairs()
                .find(|(k, _)| k == "dn")
                .map(|(_, v)| v.into_owned())
        });
        return match dn.filter(|d| !d.is_empty()) {
            Some(dn) => {
                let guvenli = guvenli_dosya_adi(&dn);
                if guvenli.is_empty() {
                    "magnet baglantisi".to_string()
                } else {
                    guvenli
                }
            }
            None => "magnet baglantisi".to_string(),
        };
    }
    let mut ad = content_disposition
        .filter(|c| !c.is_empty())
        .and_then(filename_from_content_disposition)
        .map(|a| guvenli_dosya_adi(&a))
        .filter(|a| !a.is_empty());
    if ad.is_none() {
        ad = filename_from_url(url);
    }
    let ad = ensure_extension(
        &ad.unwrap_or_else(|| VARSAYILAN_AD.to_string()),
        content_type,
    );
    let guvenli = guvenli_dosya_adi(&ad);
    if guvenli.is_empty() {
        VARSAYILAN_AD.to_string()
    } else {
        guvenli
    }
}

/// Python guess_name(source) = resolve_filename(source).
pub(crate) fn guess_name(source: &str) -> String {
    resolve_filename(source, None, None)
}

/// Python clean_title: "[METADATA]" on ekini kaldirir.
pub(crate) fn clean_title(title: &str) -> String {
    title
        .strip_prefix("[METADATA]")
        .unwrap_or(title)
        .to_string()
}

fn baslik(yanit: &ureq::http::Response<ureq::Body>, ad: &str) -> Option<String> {
    yanit
        .headers()
        .get(ad)
        .and_then(|v| v.to_str().ok())
        .filter(|v| !v.is_empty())
        .map(str::to_string)
}

fn rakam_mi(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

/// Python probe_url_info: HEAD, sonra Content-Disposition/boyut yoksa Range 0-0 GET.
/// 3 sn zaman asimi (Python varsayilani). Iki istek de basarisizsa ok=false.
pub(crate) fn probe_url_info(url: &str) -> Result<Json> {
    let url = url.trim();
    let http = url.to_lowercase();
    if url.is_empty() || !(http.starts_with("http://") || http.starts_with("https://")) {
        return Ok(json!({
            "ok": false,
            "filename": resolve_filename(url, None, None),
            "size": null,
            "content_type": null,
            "resumable": false,
        }));
    }
    let ajan: ureq::Agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(3)))
        .build()
        .into();
    let mut erisildi = false;
    let mut son_url = url.to_string();
    let mut cd: Option<String> = None;
    let mut ct: Option<String> = None;
    let mut boyut: Option<u64> = None;
    let mut resumable = false;

    if let Ok(yanit) = ajan
        .head(url)
        .header("User-Agent", TARAYICI_UA)
        .header("Accept", "*/*")
        .call()
    {
        son_url = yanit.get_uri().to_string();
        cd = baslik(&yanit, "content-disposition");
        ct = baslik(&yanit, "content-type");
        boyut = baslik(&yanit, "content-length")
            .filter(|c| rakam_mi(c))
            .and_then(|c| c.parse().ok());
        if baslik(&yanit, "accept-ranges").is_some_and(|a| a.to_lowercase().contains("bytes")) {
            resumable = true;
        }
        erisildi = true;
    }

    if cd.is_none() || boyut.is_none() {
        if let Ok(yanit) = ajan
            .get(&son_url)
            .header("User-Agent", TARAYICI_UA)
            .header("Accept", "*/*")
            .header("Range", "bytes 0-0")
            .call()
        {
            if cd.is_none() {
                cd = baslik(&yanit, "content-disposition");
            }
            if ct.is_none() {
                ct = baslik(&yanit, "content-type");
            }
            if let Some(cr) = baslik(&yanit, "content-range") {
                if let Some((_, toplam)) = cr.rsplit_once('/') {
                    let toplam = toplam.trim();
                    if rakam_mi(toplam) {
                        boyut = toplam.parse().ok();
                        resumable = true;
                    }
                }
            }
            if boyut.is_none() {
                boyut = baslik(&yanit, "content-length")
                    .filter(|c| rakam_mi(c))
                    .and_then(|c| c.parse::<u64>().ok())
                    .filter(|n| *n > 1);
            }
            erisildi = true;
        }
    }

    let ad = resolve_filename(&son_url, cd.as_deref(), ct.as_deref());
    Ok(json!({
        "ok": erisildi,
        "filename": ad,
        "size": boyut,
        "content_type": ct,
        "resumable": resumable,
        "final_url": son_url,
    }))
}
