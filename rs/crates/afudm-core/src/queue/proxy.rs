//! Proxy katmanlari ve aria2 secenekleri: Python core/proxy.py + manager._proksi.
//!
//! Katman sirasi: is-acik proxy → Windows sistem proxy (system_proxy aciksa) → genel proxy.
//! Sistem proxy PAC (AutoConfigURL) bilerek desteklenmez (Python ile ayni karar).

use super::*;
use std::collections::HashMap;

/// Windows HKCU anahtari: ProxyEnable / ProxyServer.
const SISTEM_ANAHTAR: &str = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings";
const TIP_SINIRI: usize = 1024;

/// Python parcala() ciktisi: {'tip', 'adres', 'kullanici', 'sifre'}.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Proxy {
    pub tip: String,
    pub adres: String,
    pub kullanici: String,
    pub sifre: String,
}

/// Python _HOST_PORT: `^[^:\s/]+:\d+$`.
fn host_port_gecerli(giris: &str) -> bool {
    let Some((host, port)) = giris.split_once(':') else {
        return false;
    };
    !host.is_empty()
        && !host.chars().any(|c| c == '/' || c.is_whitespace())
        && !port.is_empty()
        && port.chars().all(|c| c.is_ascii_digit())
}

/// 'socks5://user:pass@host:port', 'http://host:port', 'host:port' → Proxy (Python parcala).
pub fn parcala(uri: &str) -> Result<Proxy> {
    let ham = uri.trim();
    if ham.is_empty() {
        return Err(invalid("proxy adresi bos"));
    }
    let mut tip = "http".to_string();
    let mut giris = ham;
    if let Some((sekme, geri)) = giris.split_once("://") {
        tip = sekme.trim().to_lowercase();
        giris = geri;
        if tip == "https" {
            tip = "http".to_string();
        } else if tip == "socks5h" {
            tip = "socks5".to_string();
        }
        if !matches!(tip.as_str(), "http" | "socks5" | "socks4") {
            return Err(invalid("desteklenen proxy: http, socks5, socks4"));
        }
    }
    let mut kullanici = String::new();
    let mut sifre = String::new();
    if let Some(pos) = giris.rfind('@') {
        let kimlik = &giris[..pos];
        giris = &giris[pos + 1..];
        match kimlik.split_once(':') {
            Some((k, s)) => {
                kullanici = k.to_string();
                sifre = s.to_string();
            }
            None => kullanici = kimlik.to_string(),
        }
    }
    let giris = giris.trim();
    if !host_port_gecerli(giris) {
        return Err(invalid(
            "proxy 'host:port' biciminde olmali (orn. 127.0.0.1:1080)",
        ));
    }
    if ham.chars().count() > TIP_SINIRI {
        return Err(invalid(format!("proxy adresi cok uzun (max {TIP_SINIRI})")));
    }
    Ok(Proxy {
        tip,
        adres: giris.to_string(),
        kullanici,
        sifre,
    })
}

/// Python aria2_secenekleri: all-proxy / all-proxy-type (+ kimlik varsa user/passwd).
pub fn aria2_secenekleri(p: &Proxy) -> JsonMap {
    let mut sec = JsonMap::new();
    sec.insert("all-proxy".into(), json!(p.adres));
    sec.insert("all-proxy-type".into(), json!(p.tip));
    if !p.kullanici.is_empty() {
        sec.insert("all-proxy-user".into(), json!(p.kullanici));
    }
    if !p.sifre.is_empty() {
        sec.insert("all-proxy-passwd".into(), json!(p.sifre));
    }
    sec
}

/// Python url(): yt-dlp --proxy girdisi 'tip://kullanici:sifre@adres'.
pub fn url(p: &Proxy) -> String {
    let kimlik = if p.kullanici.is_empty() {
        String::new()
    } else {
        format!("{}:{}@", p.kullanici, p.sifre)
    };
    format!("{}://{}{}", p.tip, kimlik, p.adres)
}

/// Python sistem_proxysi (yalniz Windows; diger platformda None).
#[cfg(windows)]
pub fn sistem_proxysi() -> Option<String> {
    use winreg::{enums::HKEY_CURRENT_USER, RegKey};
    let anahtar = RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey(SISTEM_ANAHTAR)
        .ok()?;
    let aktif: u32 = anahtar.get_value("ProxyEnable").ok()?;
    let sunucu: String = anahtar.get_value("ProxyServer").ok()?;
    sistem_adresi(aktif != 0, &sunucu)
}

#[cfg(not(windows))]
pub fn sistem_proxysi() -> Option<String> {
    None
}

/// ProxyServer metninden http adresini secer ('http=h:1;https=h:2' bicimi dahil).
fn sistem_adresi(aktif: bool, sunucu: &str) -> Option<String> {
    let sunucu = sunucu.trim();
    if !aktif || sunucu.is_empty() {
        return None;
    }
    let mut bolumler: HashMap<String, String> = HashMap::new();
    for parca in sunucu.split(';') {
        if let Some((anahtar, deger)) = parca.split_once('=') {
            bolumler.insert(anahtar.trim().to_lowercase(), deger.trim().to_string());
        }
    }
    let dolu = |k: &str| bolumler.get(k).filter(|v| !v.is_empty()).cloned();
    let adres = dolu("http")
        .or_else(|| dolu("https"))
        .unwrap_or_else(|| sunucu.to_string());
    let mut adres = adres.trim().to_string();
    if adres.is_empty() {
        return None;
    }
    if let Some((_, geri)) = adres.split_once("://") {
        adres = geri.to_string();
    }
    Some(adres)
}

/// Python Manager._proksi: is-acik → sistem (system_proxy aciksa) → genel. Yoksa None.
pub fn proksi_bul(m: &Manager, options: &JsonMap) -> Result<Option<Proxy>> {
    let adres = options
        .get("proxy")
        .filter(|v| truthy(v))
        .map(|v| text(v).trim())
        .unwrap_or("");
    if !adres.is_empty() {
        return parcala(adres).map(Some);
    }
    if m.store.get("system_proxy")?.as_ref().is_some_and(truthy) {
        if let Some(sistem) = sistem_proxysi() {
            return parcala(&sistem).map(Some);
        }
    }
    let genel = setting(m, "proxy", json!(""))?;
    let genel = text(&genel).trim();
    if !genel.is_empty() {
        return parcala(genel).map(Some);
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parcala_http_ve_socks_sekmeleri() {
        let p = parcala("127.0.0.1:8123").unwrap();
        assert_eq!(
            (p.tip.as_str(), p.adres.as_str()),
            ("http", "127.0.0.1:8123")
        );
        let p = parcala("https://h:443").unwrap();
        assert_eq!(p.tip, "http");
        let p = parcala("socks5h://h:1080").unwrap();
        assert_eq!(p.tip, "socks5");
    }

    #[test]
    fn parcala_kimlik_ve_hatalar() {
        let p = parcala("socks5://ali:s3:cr@h:1080").unwrap();
        assert_eq!((p.kullanici.as_str(), p.sifre.as_str()), ("ali", "s3:cr"));
        assert!(parcala("ftp://h:1").is_err());
        assert!(parcala("sadece-host").is_err());
        assert!(parcala("   ").is_err());
        let uzun = format!("h{}:1", "a".repeat(2000));
        assert!(parcala(&uzun).is_err());
    }

    #[test]
    fn aria2_secenekleri_ve_url() {
        let p = parcala("socks5://u:p@h:1080").unwrap();
        let sec = aria2_secenekleri(&p);
        assert_eq!(sec["all-proxy"], "h:1080");
        assert_eq!(sec["all-proxy-type"], "socks5");
        assert_eq!(sec["all-proxy-user"], "u");
        assert_eq!(sec["all-proxy-passwd"], "p");
        assert_eq!(url(&p), "socks5://u:p@h:1080");
        let basit = parcala("h:1").unwrap();
        assert!(!aria2_secenekleri(&basit).contains_key("all-proxy-user"));
    }

    #[test]
    fn sistem_adresi_http_girdisini_secer() {
        assert_eq!(
            sistem_adresi(true, "http=10.0.0.1:8123;https=10.0.0.1:8124").as_deref(),
            Some("10.0.0.1:8123")
        );
        assert_eq!(sistem_adresi(true, "h:9").as_deref(), Some("h:9"));
        assert_eq!(sistem_adresi(false, "h:9"), None);
        assert_eq!(sistem_adresi(true, ""), None);
    }
}
