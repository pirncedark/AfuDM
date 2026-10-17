//! core/cerez.py karsiligi — tarayicidan gelen oturum cerezlerini dogrulama ve iki bicime cevirme.
//!
//! - `baslik`   -> aria2 "Cookie:" basligi (satir enjekte edilemez, bkz. `temizle`).
//! - `netscape` -> yt-dlp `--cookies` dosyasi.
//!
//! GUVENLIK: cerezler veritabanina YAZILMAZ. Dosyalar `data/cerez/` altinda tutulur;
//! is bitince `sil` ile, acilista `artiklari_temizle` ile silinir.
//! Cerez degerleri log ya da hata metnine yazilmaz.

use super::py::{py_float_of, py_str, truthy};
use afudm_types::Json;
use serde_json::json;
use std::path::{Path, PathBuf};

pub const EN_COK_CEREZ: usize = 300;
pub const EN_COK_BAYT: usize = 32 * 1024;
const YASAK: [char; 4] = ['\r', '\n', '\t', '\0'];

/// Python `cerez.KLASOR`: `<data>/cerez`.
pub fn klasor(data_dir: &Path) -> PathBuf {
    data_dir.join("cerez")
}

/// Python `_temiz_metin`. Yalniz metin kabul eder; yasak karakter varsa None.
fn temiz_metin(deger: Option<&Json>, ad_mi: bool) -> Option<String> {
    let s = deger?.as_str()?;
    if s.contains(YASAK) {
        return None;
    }
    if ad_mi && (s.is_empty() || s.contains([';', '=', ' '])) {
        return None;
    }
    if !ad_mi && s.contains(';') {
        return None;
    }
    Some(s.to_string())
}

/// Guvenilmeyen girdiden gecerli cerezleri secer; bozuk olanlari sessizce atar.
/// Donus alanlari: name, value, domain, path, secure, hostOnly, expirationDate.
pub fn temizle(cerezler: &Json) -> Vec<Json> {
    let Some(liste) = cerezler.as_array() else {
        return Vec::new();
    };
    let mut sonuc = Vec::new();
    let mut toplam = 0usize;
    for ham in liste.iter().take(EN_COK_CEREZ) {
        let Some(nesne) = ham.as_object() else {
            continue;
        };
        let ad = temiz_metin(nesne.get("name"), true);
        let deger = match nesne.get("value") {
            None => Some(String::new()),
            Some(v) => temiz_metin(Some(v), false),
        };
        let alan = match nesne.get("domain") {
            None => Some(String::new()),
            Some(v) => temiz_metin(Some(v), false),
        };
        let yol = match nesne.get("path") {
            None => "/".to_string(),
            Some(v) => match temiz_metin(Some(v), false) {
                Some(s) if !s.is_empty() => s,
                _ => "/".to_string(),
            },
        };
        let (Some(ad), Some(deger), Some(alan)) = (ad, deger, alan) else {
            continue;
        };
        if alan.is_empty() || alan.contains(' ') {
            continue;
        }
        toplam += ad.chars().count() + deger.chars().count();
        if toplam > EN_COK_BAYT {
            break;
        }
        let bitis = nesne
            .get("expirationDate")
            .filter(|v| truthy(v))
            .map(|v| py_float_of(v).unwrap_or(f64::NAN))
            .unwrap_or(0.0);
        let bitis: i64 = if bitis.is_finite() {
            bitis.trunc().max(0.0) as i64
        } else {
            0
        };
        let host_only = match nesne.get("hostOnly") {
            Some(v) => truthy(v),
            None => !alan.starts_with('.'),
        };
        sonuc.push(json!({
            "name": ad,
            "value": deger,
            "domain": alan.clone(),
            "path": if yol.starts_with('/') { yol } else { "/".to_string() },
            "secure": nesne.get("secure").is_some_and(truthy),
            "hostOnly": host_only,
            "expirationDate": bitis,
        }));
    }
    sonuc
}

fn cerez_adi(c: &Json) -> &str {
    c.get("name").and_then(Json::as_str).unwrap_or("")
}

/// aria2 icin tek satir Cookie degeri: `ad=deger; ad2=deger2`.
pub fn baslik(cerezler: &[Json]) -> String {
    cerezler
        .iter()
        .map(|c| {
            let deger = c.get("value").map(py_str).unwrap_or_default();
            format!("{}={}", cerez_adi(c), deger)
        })
        .collect::<Vec<_>>()
        .join("; ")
}

/// yt-dlp / curl'un okudugu Netscape cookies.txt bicimi.
pub fn netscape(cerezler: &[Json]) -> String {
    let mut satirlar = vec![
        "# Netscape HTTP Cookie File".to_string(),
        "# AfuDM tarafindan uretildi — is bitince silinir".to_string(),
    ];
    for c in cerezler {
        let ham_alan = c.get("domain").and_then(Json::as_str).unwrap_or("");
        let host_only = c.get("hostOnly").is_some_and(truthy);
        let (alan_adi, alt) = if host_only {
            (ham_alan.trim_start_matches('.').to_string(), "FALSE")
        } else if ham_alan.starts_with('.') {
            (ham_alan.to_string(), "TRUE")
        } else {
            (format!(".{ham_alan}"), "TRUE")
        };
        let secure = if c.get("secure").is_some_and(truthy) {
            "TRUE"
        } else {
            "FALSE"
        };
        let yol = c.get("path").and_then(Json::as_str).unwrap_or("/");
        let bitis = c.get("expirationDate").map(py_str).unwrap_or_default();
        let deger = c.get("value").map(py_str).unwrap_or_default();
        satirlar.push(
            [
                alan_adi.as_str(),
                alt,
                yol,
                secure,
                bitis.as_str(),
                cerez_adi(c),
                deger.as_str(),
            ]
            .join("\t"),
        );
    }
    format!("{}\n", satirlar.join("\n"))
}

/// Anahtardan guvenli dosya adi: harf/rakam disindakiler `_` olur.
fn dosya_adi(anahtar: &str) -> String {
    let guvenli: String = anahtar
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { '_' })
        .collect();
    format!("{guvenli}.txt")
}

/// Netscape dosyasini `<klasor>/<anahtar>.txt` olarak yazar.
pub fn dosya_yaz(klasor: &Path, anahtar: &str, cerezler: &[Json]) -> std::io::Result<PathBuf> {
    std::fs::create_dir_all(klasor)?;
    let hedef = klasor.join(dosya_adi(anahtar));
    std::fs::write(&hedef, netscape(cerezler))?;
    Ok(hedef)
}

/// Anahtarin cerez dosyasini siler; yoksa ya da hata olursa sessizce gecer.
pub fn sil(klasor: &Path, anahtar: &str) {
    let _ = std::fs::remove_file(klasor.join(dosya_adi(anahtar)));
}

/// Onceki calismadan kalan `*.txt` cerez dosyalarini siler; silinen sayisini doner.
pub fn artiklari_temizle(klasor: &Path) -> usize {
    let Ok(girdiler) = std::fs::read_dir(klasor) else {
        return 0;
    };
    let mut sayi = 0;
    for girdi in girdiler.flatten() {
        let yol = girdi.path();
        if yol.extension().is_some_and(|e| e == "txt") && std::fs::remove_file(&yol).is_ok() {
            sayi += 1;
        }
    }
    sayi
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(ad: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        std::env::temp_dir().join(format!("afudm-g2-{ad}-{}-{nanos}", std::process::id()))
    }

    #[test]
    fn bozuk_cerez_atilir() {
        let g = json!([
            {"name": "sid", "value": "a", "domain": ".ornek.com"},
            {"name": "bad name", "value": "x", "domain": "ornek.com"},
            {"name": "k", "value": "a\nb", "domain": "ornek.com"},
            {"name": "tercih", "value": "tr", "domain": "ornek.com"},
            {"name": "x", "value": "a;b", "domain": "ornek.com"},
        ]);
        let t = temizle(&g);
        let adlar: Vec<&str> = t.iter().map(|c| c["name"].as_str().unwrap_or("")).collect();
        assert_eq!(adlar, vec!["sid", "tercih"]);
        assert!(temizle(&json!({"name": "a"})).is_empty());
        assert!(temizle(&Json::Null).is_empty());
    }

    #[test]
    fn boyut_siniri_uygulanir() {
        let uzun = "a".repeat(20_000);
        let g = json!([
            {"name": "bir", "value": uzun, "domain": "x.com"},
            {"name": "iki", "value": "b".repeat(20_000), "domain": "x.com"},
        ]);
        assert_eq!(temizle(&g).len(), 1);
    }

    #[test]
    fn cookie_basligi_ve_netscape() {
        let g = json!([
            {"name": "sid", "value": "GIZLI", "domain": "drive.example.com", "hostOnly": true, "secure": true, "expirationDate": 1700000000},
            {"name": "tercih", "value": "tr", "domain": ".example.com"},
        ]);
        let t = temizle(&g);
        assert_eq!(baslik(&t), "sid=GIZLI; tercih=tr");
        let n = netscape(&t);
        assert!(n.contains("drive.example.com\tFALSE\t/\tTRUE\t1700000000\tsid\tGIZLI"));
        assert!(n.contains(".example.com\tTRUE\t/\tFALSE\t0\ttercih\ttr"));
        assert!(n.starts_with("# Netscape HTTP Cookie File\n"));
    }

    #[test]
    fn dosya_yaz_sil_ve_artik_temizligi() {
        let k = tmp("cerez");
        let t = temizle(&json!([{"name": "sid", "value": "GIZLI", "domain": "x.com"}]));
        let yol = dosya_yaz(&k, "is/1:2", &t).expect("yazilmali");
        assert!(yol.is_file());
        assert!(std::fs::read_to_string(&yol)
            .unwrap_or_default()
            .contains("GIZLI"));
        sil(&k, "is/1:2");
        assert!(!yol.exists());
        dosya_yaz(&k, "eski", &t).expect("yazilmali");
        assert_eq!(artiklari_temizle(&k), 1);
        assert_eq!(artiklari_temizle(&k), 0);
        let _ = std::fs::remove_dir_all(&k);
    }
}
