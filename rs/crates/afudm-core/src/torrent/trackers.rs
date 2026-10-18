//! SAHIBI: Ekip D. Python: core/trackers.py (201 satir).
//! Guncel tracker listesini indirip normalize eder ve aria2'ye uygular.

use afudm_types::{Aria2, Json, JsonMap, Result};
use std::collections::HashSet;
use std::fs;
use std::net::{IpAddr, Ipv4Addr};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const SOURCES: [&str; 2] = [
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt",
    "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_best.txt",
];
/// Python MAX_AGE = 24 saat.
const MAX_AGE_SN: f64 = 24.0 * 3600.0;
const GECERLI_SEMA: [&str; 3] = ["udp://", "http://", "https://"];
/// Python YASAK_HOST_ALT.
const YASAK_HOST_ALT: [&str; 1] = ["myporn.club"];
const YEREL_EKLER: [&str; 2] = [".local", ".localhost"];
const KAYNAK_ZAMAN_ASIMI: Duration = Duration::from_secs(15);

/// Python paths.TRACKERS_CACHE = DATA / "trackers.txt".
pub fn cache_yolu(data_dir: &Path) -> PathBuf {
    data_dir.join("trackers.txt")
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Python urlsplit(adres).hostname: kucuk harf, sondaki nokta silinmis, yoksa None.
fn host_of(adres: &str) -> Option<String> {
    let (_, sonrasi) = adres.split_once("://")?;
    let kisim = sonrasi.split(['/', '?', '#']).next().unwrap_or("");
    let ag = kisim.rsplit('@').next().unwrap_or("");
    let host = match ag.strip_prefix('[') {
        Some(r) => r.split(']').next().unwrap_or(""),
        None => ag.split(':').next().unwrap_or(""),
    };
    let host = host.to_ascii_lowercase();
    let host = host.trim_end_matches('.').to_string();
    if host.is_empty() {
        None
    } else {
        Some(host)
    }
}

/// Python ipaddress: is_private / is_reserved / loopback / link_local'in yaklasik karsiligi.
fn ipv4_ozel(ip: Ipv4Addr) -> bool {
    let o = ip.octets();
    o[0] == 0
        || o[0] == 10
        || o[0] == 127
        || o[0] >= 240
        || (o[0] == 169 && o[1] == 254)
        || (o[0] == 172 && (16..=31).contains(&o[1]))
        || (o[0] == 192 && (o[1] == 168 || (o[1] == 0 && (o[2] == 0 || o[2] == 2))))
        || (o[0] == 198 && (o[1] == 18 || o[1] == 19 || (o[1] == 51 && o[2] == 100)))
        || (o[0] == 203 && o[1] == 0 && o[2] == 113)
}

/// Python _yerel_mi.
fn yerel_mi(host: &str) -> bool {
    if matches!(host, "localhost" | "127.0.0.1" | "::1")
        || YEREL_EKLER.iter().any(|e| host.ends_with(e))
    {
        return true;
    }
    match host.parse::<IpAddr>() {
        Ok(IpAddr::V4(v4)) => ipv4_ozel(v4),
        Ok(IpAddr::V6(v6)) => {
            let ilk = v6.segments()[0];
            v6.is_loopback()
                || v6.is_unspecified()
                || (ilk & 0xfe00) == 0xfc00
                || (ilk & 0xffc0) == 0xfe80
        }
        Err(_) => false,
    }
}

/// Python _AYRAC = (?:udp|https?)://  (buyuk/kucuk harf duyarsiz, ortusmesiz).
fn ayrac_konumlari(metin: &str) -> Vec<usize> {
    let b = metin.as_bytes();
    let ayraclar: [&[u8]; 3] = [b"udp://", b"https://", b"http://"];
    let mut konum = Vec::new();
    let mut i = 0;
    while i < b.len() {
        let kalan = &b[i..];
        let uzunluk = ayraclar
            .iter()
            .find(|p| kalan.len() >= p.len() && kalan[..p.len()].eq_ignore_ascii_case(p))
            .map(|p| p.len());
        match uzunluk {
            Some(u) => {
                konum.push(i);
                i += u;
            }
            None => i += 1,
        }
    }
    konum
}

/// Python _parcala: birbirine yapismis URL'leri ayirir.
fn parcala(blok: &str) -> Vec<&str> {
    let konum = ayrac_konumlari(blok);
    (0..konum.len())
        .map(|k| {
            let bitis = konum.get(k + 1).copied().unwrap_or(blok.len());
            &blok[konum[k]..bitis]
        })
        .collect()
}

/// Python tracker_normalize: temizle -> bol -> dogrula -> tekil -> yerel/yasak ayikla.
pub fn tracker_normalize(ham: &str) -> Vec<String> {
    let mut adaylar: Vec<String> = Vec::new();
    for satir in ham.replace(',', "\n").split('\n') {
        for parca in parcala(satir) {
            let temiz = parca.trim_matches(|c: char| " \t*'\"()[]".contains(c));
            let kucuk = temiz.to_ascii_lowercase();
            if GECERLI_SEMA.iter().any(|s| kucuk.starts_with(s)) {
                adaylar.push(temiz.to_string());
            }
        }
    }
    let mut sonuc = Vec::new();
    let mut gorulen: HashSet<String> = HashSet::new();
    for adres in adaylar {
        let Some(host) = host_of(&adres) else {
            continue;
        };
        if yerel_mi(&host) || YASAK_HOST_ALT.iter().any(|y| host.contains(*y)) {
            continue;
        }
        if !gorulen.insert(adres.to_lowercase()) {
            continue;
        }
        sonuc.push(adres);
    }
    sonuc
}

/// Python ayikla: kullanicinin yapistirdigi metin icin normalize hattinin aynisi.
pub fn ayikla(metin: &str) -> Vec<String> {
    tracker_normalize(metin)
}

/// Python _fetch + bos satirlarin atilmasi. Hata varsa son hatayi doner.
pub(super) fn indir(
    url: &str,
    ua: &str,
    zaman_asimi: Duration,
    en_fazla: u64,
) -> std::result::Result<Vec<u8>, String> {
    use std::io::Read;
    let ayar = ureq::Agent::config_builder()
        .timeout_global(Some(zaman_asimi))
        .build();
    let ajan = ureq::Agent::new_with_config(ayar);
    let mut yanit = ajan
        .get(url)
        .header("User-Agent", ua)
        .call()
        .map_err(|e| e.to_string())?;
    let mut govde = Vec::new();
    let mut okuyucu = yanit.body_mut().as_reader().take(en_fazla);
    okuyucu.read_to_end(&mut govde).map_err(|e| e.to_string())?;
    Ok(govde)
}

fn kaynaklardan_cek() -> std::result::Result<Vec<String>, String> {
    let mut son_hata: Option<String> = None;
    for url in SOURCES {
        match indir(url, "AfuDM/1.0", KAYNAK_ZAMAN_ASIMI, u64::MAX) {
            Ok(govde) => {
                let metin = String::from_utf8_lossy(&govde);
                let satirlar: Vec<String> = metin
                    .lines()
                    .map(|l| l.trim().to_string())
                    .filter(|l| !l.is_empty())
                    .collect();
                if !satirlar.is_empty() {
                    return Ok(satirlar);
                }
            }
            Err(e) => son_hata = Some(e),
        }
    }
    match son_hata {
        Some(e) => Err(e),
        None => Ok(Vec::new()),
    }
}

fn satirlari_oku(yol: &Path) -> Result<Vec<String>> {
    if !yol.exists() {
        return Ok(Vec::new());
    }
    let bayt = fs::read(yol)?;
    Ok(String::from_utf8_lossy(&bayt)
        .lines()
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty())
        .collect())
}

/// Python cached().
pub fn onbellek_oku(data_dir: &Path) -> Result<Vec<String>> {
    satirlari_oku(&cache_yolu(data_dir))
}

/// Dosyanin son yazilma zamanindan bu yana gecen sure (sn). Dosya yoksa None.
/// Python cache_yasi().
pub fn cache_yasi(data_dir: &Path) -> Option<f64> {
    let mt = fs::metadata(cache_yolu(data_dir)).ok()?.modified().ok()?;
    let mt_sn = mt
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    Some(simdi() - mt_sn)
}

/// Python refresh(force): gerekiyorsa indir, normalize et, onbellege yaz; cevrimdisiysa onbellek.
pub fn yenile(data_dir: &Path, force: bool) -> Result<Vec<String>> {
    fs::create_dir_all(data_dir)?;
    let cache = cache_yolu(data_dir);
    let taze = cache_yasi(data_dir).is_some_and(|y| y < MAX_AGE_SN);
    if !force && taze {
        return onbellek_oku(data_dir);
    }
    let liste = match kaynaklardan_cek() {
        Ok(satirlar) => tracker_normalize(&satirlar.join("\n")),
        Err(_) => return onbellek_oku(data_dir),
    };
    if !liste.is_empty() {
        fs::write(&cache, liste.join("\n"))?;
    }
    Ok(liste)
}

/// Python apply_to_aria2: olculmus canli liste varsa onu, yoksa ek + guncel liste; bt-tracker'a yazar.
/// Donen: uygulanan tracker sayisi.
pub fn aria2_uygula(
    rpc: &dyn Aria2,
    data_dir: &Path,
    force: bool,
    ek: &str,
    canli: &str,
) -> Result<usize> {
    let filtreli = tracker_normalize(canli);
    let tumu: Vec<String> = if !filtreli.is_empty() {
        filtreli
    } else {
        let kendi = tracker_normalize(ek);
        let liste = yenile(data_dir, force)?;
        let mut t = kendi.clone();
        t.extend(liste.into_iter().filter(|x| !kendi.contains(x)));
        t
    };
    if tumu.is_empty() {
        return Ok(0);
    }
    let mut harita = JsonMap::new();
    harita.insert("bt-tracker".to_string(), Json::String(tumu.join(",")));
    rpc.change_global_option(&harita)?;
    Ok(tumu.len())
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn birlesik_url_ayrilir_ve_ws_elenir() {
        let liste = tracker_normalize(
            "http://a.example.org/announceudp://b.example.net:1337/announce\nws://x.example.org/y",
        );
        assert_eq!(
            liste,
            vec![
                "http://a.example.org/announce".to_string(),
                "udp://b.example.net:1337/announce".to_string()
            ]
        );
    }

    #[test]
    fn yerel_ve_yasak_adresler_cikar() {
        let liste = tracker_normalize("udp://127.0.0.1:80/a\nudp://192.168.1.5:80/a\nhttp://retracker.local/a\nhttps://myporn.club/a\nudp://ok.example.org:1/a");
        assert_eq!(liste, vec!["udp://ok.example.org:1/a".to_string()]);
    }

    #[test]
    fn tekrarlar_buyuk_kucuk_harf_duyarsiz_silinir() {
        let liste = tracker_normalize("udp://A.example.org:1/x,udp://a.example.org:1/x");
        assert_eq!(liste.len(), 1);
    }

    #[test]
    fn yildiz_ve_tirnak_temizlenir() {
        let liste = tracker_normalize("*'udp://t.example.org:1/a'*");
        assert_eq!(liste, vec!["udp://t.example.org:1/a".to_string()]);
    }
}
