//! Tarayicidan gelen oturum cerezleri -> yt-dlp `--cookies` dosyasi (Netscape bicimi).
//! Port of core/cerez.py (temizle, netscape, dosya_yaz, sil, artiklari_temizle).
//! GUVENLIK: satir sonu/sekme iceren ya da ';' tasiyan cerez atilir (satir enjeksiyonu yok).

use super::dogru_mu;
use afudm_types::{AfuError, Json, Result};
use std::path::{Path, PathBuf};

const EN_COK_CEREZ: usize = 300;
const EN_COK_BAYT: usize = 32 * 1024;
const YASAK: [char; 4] = ['\r', '\n', '\t', '\0'];

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Cerez {
    pub name: String,
    pub value: String,
    pub domain: String,
    pub path: String,
    pub secure: bool,
    pub host_only: bool,
    pub expiration: i64,
}

/// Python _temiz_metin: metin degilse ya da yasak karakter/format bozuksa None.
fn temiz_metin(deger: &Json, ad_mi: bool) -> Option<String> {
    let metin = deger.as_str()?;
    if metin.contains(YASAK) {
        return None;
    }
    if ad_mi && (metin.is_empty() || metin.contains([';', '=', ' '])) {
        return None;
    }
    if !ad_mi && metin.contains(';') {
        return None;
    }
    Some(metin.to_string())
}

/// Python: `ham.get(k, varsayilan)` — anahtar yoksa varsayilan, varsa degeri.
fn al_veya<'a>(ham: &'a Json, anahtar: &str, varsayilan: &'a Json) -> &'a Json {
    ham.get(anahtar).unwrap_or(varsayilan)
}

fn sure_sayisi(deger: &Json) -> i64 {
    let f = match deger {
        Json::Number(n) => n.as_f64(),
        Json::String(s) => s.trim().parse::<f64>().ok(),
        Json::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    };
    f.map_or(0, |v| if v.is_finite() { v.max(0.0) as i64 } else { 0 })
}

/// Guvenilmeyen girdiden gecerli cerezleri sec; bozuk olani sessizce at.
pub(crate) fn temizle(cerezler: &Json) -> Vec<Cerez> {
    let Some(dizi) = cerezler.as_array() else {
        return Vec::new();
    };
    let bos = Json::String(String::new());
    let yol_varsayilan = Json::String("/".into());
    let mut sonuc = Vec::new();
    let mut toplam = 0usize;
    for ham in dizi.iter().take(EN_COK_CEREZ) {
        if !ham.is_object() {
            continue;
        }
        let ad = temiz_metin(al_veya(ham, "name", &bos), true);
        let deger = temiz_metin(al_veya(ham, "value", &bos), false);
        let alan = temiz_metin(al_veya(ham, "domain", &bos), false);
        let yol = temiz_metin(al_veya(ham, "path", &yol_varsayilan), false)
            .filter(|y| !y.is_empty())
            .unwrap_or_else(|| "/".into());
        let (Some(ad), Some(deger), Some(alan)) = (ad, deger, alan) else {
            continue;
        };
        if alan.is_empty() || alan.contains(' ') {
            continue;
        }
        toplam += ad.len() + deger.len();
        if toplam > EN_COK_BAYT {
            break;
        }
        let host_only_varsayilan = !alan.starts_with('.');
        let host_only = match ham.get("hostOnly") {
            Some(v) => dogru_mu(v),
            None => host_only_varsayilan,
        };
        sonuc.push(Cerez {
            name: ad,
            value: deger,
            secure: ham.get("secure").is_some_and(dogru_mu),
            host_only,
            expiration: sure_sayisi(al_veya(ham, "expirationDate", &Json::Null)),
            path: if yol.starts_with('/') {
                yol
            } else {
                "/".into()
            },
            domain: alan,
        });
    }
    sonuc
}

/// yt-dlp / curl'un okudugu Netscape cookies.txt bicimi.
pub(crate) fn netscape(cerezler: &[Cerez]) -> String {
    let mut satirlar = vec![
        "# Netscape HTTP Cookie File".to_string(),
        "# AfuDM tarafindan uretildi — is bitince silinir".to_string(),
    ];
    for c in cerezler {
        let (alan, alt) = if c.host_only {
            (c.domain.trim_start_matches('.').to_string(), "FALSE")
        } else if c.domain.starts_with('.') {
            (c.domain.clone(), "TRUE")
        } else {
            (format!(".{}", c.domain), "TRUE")
        };
        satirlar.push(
            [
                alan.as_str(),
                alt,
                c.path.as_str(),
                if c.secure { "TRUE" } else { "FALSE" },
                &c.expiration.to_string(),
                c.name.as_str(),
                c.value.as_str(),
            ]
            .join("\t"),
        );
    }
    format!("{}\n", satirlar.join("\n"))
}

fn klasor(data_dir: &Path) -> PathBuf {
    data_dir.join("cerez")
}

fn dosya_adi(data_dir: &Path, anahtar: &str) -> PathBuf {
    let guvenli: String = anahtar
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { '_' })
        .collect();
    klasor(data_dir).join(format!("{guvenli}.txt"))
}

/// Python dosya_yaz(): cerezleri `data/cerez/<anahtar>.txt` olarak yazar.
pub(crate) fn dosya_yaz(data_dir: &Path, anahtar: &str, cerezler: &[Cerez]) -> Result<PathBuf> {
    std::fs::create_dir_all(klasor(data_dir))?;
    let hedef = dosya_adi(data_dir, anahtar);
    std::fs::write(&hedef, netscape(cerezler))
        .map_err(|e| AfuError::Io(format!("cerez dosyasi yazilamadi: {e}")))?;
    Ok(hedef)
}

/// Python sil(): is bitince cerez dosyasini siler; hata sessizdir.
pub(crate) fn sil(data_dir: &Path, anahtar: &str) {
    let _ = std::fs::remove_file(dosya_adi(data_dir, anahtar));
}

/// Python artiklari_temizle(): onceki calismadan kalan cerez dosyalarini siler.
#[allow(dead_code)] // acilista cagirilana kadar
pub(crate) fn artiklari_temizle(data_dir: &Path) -> usize {
    let Ok(girdiler) = std::fs::read_dir(klasor(data_dir)) else {
        return 0;
    };
    girdiler
        .filter_map(|g| g.ok().map(|g| g.path()))
        .filter(|p| p.extension().is_some_and(|e| e == "txt"))
        .filter(|p| std::fs::remove_file(p).is_ok())
        .count()
}

#[cfg(test)]
mod testler {
    use super::*;
    use serde_json::json;

    #[test]
    fn bozuk_ve_yasak_cerezler_atilir() {
        let girdi = json!([
            {"name": "oturum", "value": "abc", "domain": ".ornek.test", "path": "/x", "secure": true, "expirationDate": 1700000000.7},
            {"name": "kotu;ad", "value": "x", "domain": ".ornek.test"},
            {"name": "satir", "value": "a\nb", "domain": ".ornek.test"},
            {"name": "bosalan", "value": "x", "domain": ""},
            "duz metin"
        ]);
        let c = temizle(&girdi);
        assert_eq!(c.len(), 1);
        assert_eq!(c[0].name, "oturum");
        assert!(c[0].secure);
        assert!(!c[0].host_only);
        assert_eq!(c[0].expiration, 1_700_000_000);
    }

    #[test]
    fn netscape_bicimi() {
        let c = vec![
            Cerez {
                name: "a".into(),
                value: "1".into(),
                domain: ".ornek.test".into(),
                path: "/".into(),
                secure: false,
                host_only: false,
                expiration: 0,
            },
            Cerez {
                name: "b".into(),
                value: "2".into(),
                domain: "tek.test".into(),
                path: "/p".into(),
                secure: true,
                host_only: true,
                expiration: 5,
            },
        ];
        let metin = netscape(&c);
        assert!(metin.starts_with("# Netscape HTTP Cookie File\n"));
        assert!(metin.contains(".ornek.test\tTRUE\t/\tFALSE\t0\ta\t1"));
        assert!(metin.contains("tek.test\tFALSE\t/p\tTRUE\t5\tb\t2"));
        assert!(metin.ends_with('\n'));
    }

    #[test]
    fn dosya_yaz_sil_ve_artik_temizligi() {
        let d = std::env::temp_dir().join(format!("afudm-cerez-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        let c = temizle(&json!([{"name": "a", "value": "1", "domain": ".t.test"}]));
        let yol = dosya_yaz(&d, "yt:1", &c).expect("yazilmali");
        assert!(yol.is_file());
        assert_eq!(artiklari_temizle(&d), 1);
        assert!(!yol.exists());
        sil(&d, "yok");
    }
}
