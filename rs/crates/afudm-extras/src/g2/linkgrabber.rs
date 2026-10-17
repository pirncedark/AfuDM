//! core/linkgrabber.py karsiligi — metinden indirilebilir baglanti cikarma, tekillestirme,
//! tur/domain/panel filtreleri ve sinirli eszamanlilikla lazy probe.
//! Akis: ayikla -> normalize -> tekil_les -> tur_bul -> filtrele -> probe_es_zamanli.
//!
//! Probe'un kendisi (HEAD/Range istegi) Python'da core/dosya_adi.probe_url_info'dur ve Rust
//! tarafinda henuz yoktur; `probe_es_zamanli` bunu bir kapanis (closure) olarak alir.

use super::py::{py_float_of, py_str, truthy};
use super::url_parca::{birlestir, hostname, urlsplit};
use afudm_types::Json;
use regex::Regex;
use serde_json::json;
use std::collections::{BTreeSet, HashMap, HashSet};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

pub const PROBE_MAKS_WORKER: i64 = 16;
pub const PROBE_CACHE_TTL: Duration = Duration::from_secs(300);
pub const PROBE_CACHE_CAP: usize = 2000;

const ARSIV_UZANTILARI: [&str; 10] = [
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".tgz", ".iso",
];
const VIDEO_UZANTILARI: [&str; 9] = [
    ".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".ts", ".m3u8", ".mpd",
];
const SES_UZANTILARI: [&str; 6] = [".mp3", ".m4a", ".aac", ".flac", ".ogg", ".wav"];
const VIDEO_SITELERI: [&str; 20] = [
    "youtube.com",
    "youtu.be",
    "www.youtube.com",
    "vimeo.com",
    "player.vimeo.com",
    "dailymotion.com",
    "www.dailymotion.com",
    "twitch.tv",
    "www.twitch.tv",
    "clips.twitch.tv",
    "tiktok.com",
    "www.tiktok.com",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "www.twitter.com",
    "kick.com",
    "www.kick.com",
];

fn url_desen() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(r#"(?i)(?:https?://|ftp://)[\w\-._~:/?#\[\]@!$&'()*+,;=%]+|magnet:\?[^\s<>"']+"#)
            .expect("sabit URL deseni gecerli")
    })
}

fn yol(url: &str) -> String {
    urlsplit(url).path.to_lowercase()
}

fn host(url: &str) -> String {
    hostname(&urlsplit(url).netloc)
}

/// Metinden URL adaylarini cikarir (http/https/ftp/magnet). Python: ayikla.
pub fn ayikla(metin: &str) -> Vec<String> {
    if metin.is_empty() {
        return Vec::new();
    }
    url_desen()
        .find_iter(metin)
        .map(|m| m.as_str().to_string())
        .collect()
}

/// Python: normalize. Trim + cevreleyen noktalama; http/https/ftp'de host kucuk harf,
/// fragment atilir; path/query korunur; diger semalar aynen doner.
pub fn normalize(url: &str) -> String {
    let t = url.trim().trim_matches(|c: char| ".,;:!?\"'".contains(c));
    let p = urlsplit(t);
    if p.scheme.is_empty() || p.netloc.is_empty() {
        return t.to_string();
    }
    if matches!(p.scheme.as_str(), "http" | "https" | "ftp") {
        let netloc = match p.netloc.rfind('@') {
            Some(i) => format!("{}@{}", &p.netloc[..i], p.netloc[i + 1..].to_lowercase()),
            None => p.netloc.to_lowercase(),
        };
        let mut q = p;
        q.netloc = netloc;
        q.fragment = String::new();
        return birlestir(&q);
    }
    t.to_string()
}

/// Python `unquote_plus` (yuzde kodu + '+' -> bosluk).
fn unquote_plus(s: &str) -> String {
    let s = s.replace('+', " ");
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            let onaltilik = std::str::from_utf8(&b[i + 1..i + 3])
                .ok()
                .and_then(|h| u8::from_str_radix(h, 16).ok());
            if let Some(v) = onaltilik {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// Tekillesme anahtari: normalize URL; magnet icin btih infohash (kucuk harf).
fn anahtar(url: &str) -> String {
    let u = normalize(url);
    if u.to_lowercase().starts_with("magnet:") {
        let sorgu = urlsplit(&u).query;
        let mut xt = String::new();
        for cift in sorgu.split('&') {
            let (k, v) = cift.split_once('=').unwrap_or((cift, ""));
            if unquote_plus(k) == "xt" && !v.is_empty() {
                xt = unquote_plus(v);
                break;
            }
        }
        if let Some(i) = xt.find("urn:btih:") {
            return format!("btih:{}", xt[i + "urn:btih:".len()..].to_lowercase());
        }
        return u.to_lowercase();
    }
    u
}

/// Ayni URL'yi (ve magnet'te ayni infohash'i) bir kez birakir; sira korunur.
pub fn tekil_les(urller: &[String]) -> Vec<String> {
    let mut gorulen = HashSet::new();
    let mut sonuc = Vec::new();
    for url in urller {
        if gorulen.insert(anahtar(url)) {
            sonuc.push(normalize(url));
        }
    }
    sonuc
}

/// Adreslerden gecmiste kayitli olanlar (uyari icin; indirmeyi engellemez).
pub fn onceki_eslesen(adresler: &[String], gecmis: &[String]) -> Vec<String> {
    let bilinen: HashSet<String> = gecmis
        .iter()
        .map(|e| anahtar(e))
        .filter(|a| !a.is_empty())
        .collect();
    let mut gorulen = HashSet::new();
    let mut sonuc = Vec::new();
    for adres in adresler {
        let a = anahtar(adres);
        if bilinen.contains(&a) && gorulen.insert(a) {
            sonuc.push(adres.clone());
        }
    }
    sonuc
}

/// Host, verilen alan adina ait mi (esit ya da alt alan adi). `evilgithub.com` eslesmez.
pub fn domain_eslesir(host: &str, domain: &str) -> bool {
    let mut d = domain.trim().to_lowercase();
    if let Some(r) = d.strip_prefix("www.") {
        d = r.to_string();
    }
    let h = host.strip_prefix("www.").unwrap_or(host);
    !d.is_empty() && (h == d || h.ends_with(&format!(".{d}")))
}

/// Hafif tur tahmini: "torrent" | "video" | "arsiv" | "http".
pub fn tur_bul(url: &str) -> &'static str {
    let u = normalize(url);
    let alt = u.to_lowercase();
    if alt.starts_with("magnet:") || yol(&alt).ends_with(".torrent") {
        return "torrent";
    }
    let y = yol(&alt);
    if ARSIV_UZANTILARI.iter().any(|e| y.ends_with(e)) {
        return "arsiv";
    }
    if VIDEO_UZANTILARI
        .iter()
        .chain(SES_UZANTILARI.iter())
        .any(|e| y.ends_with(e))
    {
        return "video";
    }
    let h = host(&u);
    if VIDEO_SITELERI.iter().any(|s| domain_eslesir(&h, s)) {
        return "video";
    }
    "http"
}

/// Tur (bos = hepsi) ve alan adi (bos = hepsi) filtresi.
pub fn filtrele(urller: &[String], sadece: Option<&BTreeSet<String>>, domain: &str) -> Vec<String> {
    let dom = domain.trim().to_lowercase();
    let mut sonuc = Vec::new();
    for url in urller {
        if let Some(s) = sadece.filter(|s| !s.is_empty()) {
            if !s.contains(tur_bul(url)) {
                continue;
            }
        }
        if !dom.is_empty() && !domain_eslesir(&host(url), &dom) {
            continue;
        }
        sonuc.push(url.clone());
    }
    sonuc
}

/// Python `_joker_esles`: `*` ve `?` joker; yoksa parca aramasi. Buyuk/kucuk harf duyarsiz.
pub fn joker_esles(metin: &str, desen: &str) -> bool {
    let metin = metin.to_lowercase();
    let desen = desen.trim().to_lowercase();
    if desen.is_empty() {
        return true;
    }
    if desen.contains('*') || desen.contains('?') {
        let mut rx = String::new();
        for c in desen.chars() {
            match c {
                '*' => rx.push_str(".*"),
                '?' => rx.push('.'),
                _ => rx.push_str(&regex::escape(&c.to_string())),
            }
        }
        return Regex::new(&rx).map(|r| r.is_match(&metin)).unwrap_or(false);
    }
    metin.contains(&desen)
}

/// Panelin TEK filtre mantigi. Donus: eslesen ogelerin orijinal indeksleri.
/// Boyut filtresi aktifken boyutu bilinmeyen (size yok/null) oge elenir.
pub fn ogeleri_filtrele(
    ogeler: &[Json],
    ara: &str,
    sadece: Option<&BTreeSet<String>>,
    domain: &str,
    min_boyut: Option<i64>,
    max_boyut: Option<i64>,
) -> Vec<usize> {
    let mut eslesen = Vec::new();
    for (i, o) in ogeler.iter().enumerate() {
        let Some(obj) = o.as_object() else { continue };
        let url = obj.get("url").map(py_str).unwrap_or_default();
        let url = url.trim();
        if url.is_empty() {
            continue;
        }
        if let Some(s) = sadece.filter(|s| !s.is_empty()) {
            let tur = match obj.get("tur") {
                Some(t) if truthy(t) => py_str(t),
                _ => tur_bul(url).to_string(),
            };
            if !s.contains(&tur) {
                continue;
            }
        }
        if !domain.is_empty() && !domain_eslesir(&host(url), domain) {
            continue;
        }
        if min_boyut.is_some() || max_boyut.is_some() {
            let Some(boyut) = obj
                .get("size")
                .filter(|v| !v.is_null())
                .and_then(py_float_of)
            else {
                continue;
            };
            if min_boyut.is_some_and(|m| boyut < m as f64)
                || max_boyut.is_some_and(|m| boyut > m as f64)
            {
                continue;
            }
        }
        if !ara.trim().is_empty() {
            let dosya = obj
                .get("filename")
                .filter(|v| truthy(v))
                .map(py_str)
                .unwrap_or_default();
            if !joker_esles(&format!("{dosya} {url}"), ara) {
                continue;
            }
        }
        eslesen.push(i);
    }
    eslesen
}

/// Panelin domain acilir kutusu icin benzersiz, sirali host listesi.
pub fn domainler(ogeler: &[Json]) -> Vec<String> {
    let mut tum = BTreeSet::new();
    for o in ogeler {
        let Some(url) = o.get("url").filter(|v| truthy(v)).map(py_str) else {
            continue;
        };
        let h = host(url.trim());
        if !h.is_empty() {
            tum.insert(h);
        }
    }
    tum.into_iter().collect()
}

// --- Probe onbellegi (yalniz ok=true sonuclar, TTL + kapasite siniri) -----------------
type Onbellek = Mutex<HashMap<String, (Instant, Json)>>;

fn onbellek() -> &'static Onbellek {
    static O: OnceLock<Onbellek> = OnceLock::new();
    O.get_or_init(|| Mutex::new(HashMap::new()))
}

fn onbellege_yaz(url: &str, sonuc: &Json) {
    if !sonuc.get("ok").is_some_and(truthy) {
        return;
    }
    let mut o = onbellek().lock().unwrap_or_else(|e| e.into_inner());
    o.insert(url.to_string(), (Instant::now(), sonuc.clone()));
    if o.len() > PROBE_CACHE_CAP {
        let mut anahtarlar: Vec<(Instant, String)> =
            o.iter().map(|(k, v)| (v.0, k.clone())).collect();
        anahtarlar.sort();
        for (_, k) in anahtarlar.iter().take(PROBE_CACHE_CAP / 2) {
            o.remove(k);
        }
    }
}

fn onbellekten_oku(url: &str) -> Option<Json> {
    let mut o = onbellek().lock().unwrap_or_else(|e| e.into_inner());
    let (zaman, sonuc) = o.get(url)?.clone();
    if zaman.elapsed() > PROBE_CACHE_TTL {
        o.remove(url);
        return None;
    }
    Some(sonuc)
}

fn probe_tek(url: &str, timeout: f64, iptal: Option<&AtomicBool>, probe: &ProbeFn) -> Json {
    if let Some(c) = onbellekten_oku(url) {
        return c;
    }
    if iptal.is_some_and(|i| i.load(Ordering::SeqCst)) {
        return json!({"ok": false, "iptal": true});
    }
    // Beklenmedik hata paneli kilitlemesin (Python: except Exception).
    let sonuc = catch_unwind(AssertUnwindSafe(|| probe(url, timeout)))
        .unwrap_or_else(|_| json!({"ok": false, "error": "probe beklenmeyen hata verdi"}));
    onbellege_yaz(url, &sonuc);
    sonuc
}

/// Lazy probe imzasi: (url, zaman asimi saniye) -> {"ok", "filename", "size", ...}.
pub type ProbeFn = dyn Fn(&str, f64) -> Json + Sync;

/// Toplu probe, eszamanlilik `1..=16` ile sinirli. Donus: {url: probe sonucu}.
/// `iptal` set edilirse yeni probe baslatilmaz (calisanlar bitirir).
pub fn probe_es_zamanli(
    urller: &[String],
    es_zamanli: i64,
    timeout: f64,
    iptal: Option<&AtomicBool>,
    probe: &ProbeFn,
) -> HashMap<String, Json> {
    let cap = es_zamanli.clamp(1, PROBE_MAKS_WORKER) as usize;
    let mut benzersiz: Vec<&String> = Vec::new();
    let mut gorulen = HashSet::new();
    for u in urller {
        if gorulen.insert(u) {
            benzersiz.push(u);
        }
    }
    let sonuclar = Mutex::new(HashMap::new());
    let sira = AtomicUsize::new(0);
    std::thread::scope(|s| {
        for _ in 0..cap.min(benzersiz.len()) {
            s.spawn(|| loop {
                let i = sira.fetch_add(1, Ordering::SeqCst);
                let Some(url) = benzersiz.get(i) else { break };
                let sonuc = if iptal.is_some_and(|f| f.load(Ordering::SeqCst)) {
                    json!({"ok": false, "iptal": true})
                } else {
                    probe_tek(url, timeout, iptal, probe)
                };
                sonuclar
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .insert(url.to_string(), sonuc);
            });
        }
    });
    sonuclar.into_inner().unwrap_or_else(|e| e.into_inner())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(v: &[&str]) -> Vec<String> {
        v.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn ayiklar_http_ftp_magnet() {
        let c = ayikla("Bugun su dosyayi indir: https://ornek.com/dosya.iso lutfen. magnet:?xt=urn:btih:abc123 ve ftp://ftp.ornek.com/video.mp4");
        assert!(c.contains(&"https://ornek.com/dosya.iso".to_string()));
        assert!(c.contains(&"ftp://ftp.ornek.com/video.mp4".to_string()));
        assert!(c.contains(&"magnet:?xt=urn:btih:abc123".to_string()));
        assert!(c.iter().all(|u| !u.ends_with(".") && !u.ends_with(",")));
    }

    #[test]
    fn normalize_python_ile_ayni() {
        assert_eq!(normalize("https://x.com/a.zip."), "https://x.com/a.zip");
        assert_eq!(normalize("\"https://x.com/a\""), "https://x.com/a");
        assert_eq!(normalize("HTTPS://X.com/a.zip"), "https://x.com/a.zip");
        assert_eq!(
            normalize("https://GIThub.COM/Rapo/File.exe"),
            "https://github.com/Rapo/File.exe"
        );
        assert_eq!(
            normalize("https://x.com/a?TOKEN=AbC&b=1"),
            "https://x.com/a?TOKEN=AbC&b=1"
        );
        assert_eq!(
            normalize("https://x.com/a.zip#kaydir"),
            "https://x.com/a.zip"
        );
        assert_eq!(normalize("HTTP://X.com:8080/a"), "http://x.com:8080/a");
        assert_eq!(
            normalize("https://KULLANICI:sifre@X.com/a"),
            "https://KULLANICI:sifre@x.com/a"
        );
        assert_eq!(
            normalize("MAGNET:?xt=urn:btih:ABC"),
            "MAGNET:?xt=urn:btih:ABC"
        );
    }

    #[test]
    fn tekil_les_kurallari() {
        assert_eq!(
            tekil_les(&s(&["https://x.com/a.zip", "https://x.com/a.zip"])),
            s(&["https://x.com/a.zip"])
        );
        assert_eq!(
            tekil_les(&s(&["https://X.COM/a.zip", "https://x.com/a.zip"])),
            s(&["https://x.com/a.zip"])
        );
        assert_eq!(
            tekil_les(&s(&["https://x.com/File.zip", "https://x.com/file.zip"])).len(),
            2
        );
        assert_eq!(
            tekil_les(&s(&[
                "magnet:?xt=urn:btih:ABC",
                "magnet:?xt=urn:btih:abc&dn=x"
            ]))
            .len(),
            1
        );
        assert_eq!(
            tekil_les(&s(&[
                "https://b.com/1",
                "https://a.com/2",
                "https://b.com/1"
            ])),
            s(&["https://b.com/1", "https://a.com/2"])
        );
    }

    #[test]
    fn tur_tahmini() {
        assert_eq!(tur_bul("magnet:?xt=urn:btih:abc"), "torrent");
        assert_eq!(tur_bul("https://x.com/a.torrent"), "torrent");
        assert_eq!(tur_bul("https://x.com/a.tar.gz"), "arsiv");
        assert_eq!(tur_bul("https://x.com/sarki.mp3"), "video");
        assert_eq!(tur_bul("https://m.youtube.com/watch?v=abc"), "video");
        assert_eq!(tur_bul("https://evilyoutube.com/x"), "http");
        assert_eq!(tur_bul("https://youtube.com.evil.com/x"), "http");
        assert_eq!(tur_bul("https://x.com/sayfa"), "http");
    }

    #[test]
    fn domain_taklit_engellenir() {
        assert!(domain_eslesir("api.github.com", "github.com"));
        assert!(domain_eslesir("www.example.com", "www.example.com"));
        assert!(!domain_eslesir("evilgithub.com", "github.com"));
        assert!(!domain_eslesir("github.com.evil.com", "github.com"));
        assert!(!domain_eslesir("wwexample.com", "www.example.com"));
    }

    #[test]
    fn panel_filtresi_wildcard_ve_boyut() {
        let o = vec![
            json!({"url":"https://x.com/file1.zip","filename":"file1.zip","size":2_000_000_000u64,"tur":"arsiv"}),
            json!({"url":"https://x.com/file2.zip","filename":"file2.zip","size":null,"tur":"arsiv"}),
            json!({"url":"https://y.com/image.png","filename":"image.png","size":100,"tur":"http"}),
        ];
        assert_eq!(
            ogeleri_filtrele(&o, "*.zip", None, "", None, None),
            vec![0, 1]
        );
        assert_eq!(
            ogeleri_filtrele(&o, "*IMAGE*", None, "", None, None),
            vec![2]
        );
        assert_eq!(
            ogeleri_filtrele(&o, "file?.zip", None, "", None, None),
            vec![0, 1]
        );
        assert_eq!(
            ogeleri_filtrele(&o, "", None, "", Some(1 << 30), None),
            vec![0]
        );
        assert_eq!(
            ogeleri_filtrele(&o, "", None, "", None, Some(1 << 30)),
            vec![2]
        );
        assert!(ogeleri_filtrele(&[], "x", None, "", None, None).is_empty());
    }

    #[test]
    fn onceki_ve_domainler() {
        let gecmis = s(&["https://X.com/a.zip", "magnet:?xt=urn:btih:ABC"]);
        let adresler = s(&[
            "https://x.com/a.zip",
            "magnet:?xt=urn:btih:abc",
            "https://y.com/b",
        ]);
        assert_eq!(onceki_eslesen(&adresler, &gecmis).len(), 2);
        assert!(onceki_eslesen(&adresler, &[]).is_empty());
        let o = vec![
            json!({"url":"https://github.com/a"}),
            json!({"url":"https://api.github.com/b"}),
        ];
        assert_eq!(domainler(&o), s(&["api.github.com", "github.com"]));
    }

    #[test]
    fn probe_eszamanli_ve_onbellek() {
        use std::sync::atomic::AtomicUsize;
        static CAGRI: AtomicUsize = AtomicUsize::new(0);
        let probe = |url: &str, _t: f64| {
            CAGRI.fetch_add(1, Ordering::SeqCst);
            json!({"ok": true, "filename": url.rsplit('/').next().unwrap_or(""), "size": 5})
        };
        let urller: Vec<String> = (0..6)
            .map(|i| format!("https://probe-test.invalid/g2-{i}.mp4"))
            .collect();
        let sonuc = probe_es_zamanli(&urller, 9999, 3.0, None, &probe);
        assert_eq!(sonuc.len(), 6);
        assert!(sonuc.values().all(|v| v["ok"] == json!(true)));
        let ilk = CAGRI.load(Ordering::SeqCst);
        let tekrar = probe_es_zamanli(&urller[..1], 0, 3.0, None, &probe);
        assert_eq!(tekrar[&urller[0]]["ok"], json!(true));
        assert_eq!(
            CAGRI.load(Ordering::SeqCst),
            ilk,
            "onbellek ag cagrisini engellemeli"
        );
    }

    #[test]
    fn iptal_yeni_probe_baslatmaz() {
        let iptal = AtomicBool::new(true);
        let probe = |_u: &str, _t: f64| json!({"ok": true});
        let urller = s(&["https://iptal-test.invalid/x.zip"]);
        let sonuc = probe_es_zamanli(&urller, 2, 3.0, Some(&iptal), &probe);
        assert_eq!(sonuc[&urller[0]]["iptal"], json!(true));
    }
}
