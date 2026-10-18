//! Ekip G1. Python: core/reliability.py — tutarlilik, yedek (zip), geri yukleme dogrulamasi,
//! tani (maskeli) ve kurtarma onizlemesi. Tum islemler orijinali korur; hicbir sey silinmez.
//! Eksik (Python'da var, burada yok): health, restart_engine (ManagerApi'de motor/daemon durumu yok) ve
//! tani.engines (core/engines.py sozlesmede yok). Bkz. docs/sonuc/SONUC_G1.md.

use afudm_types::{AfuError, Json, Result, Store};
use regex::{Captures, Regex};
use serde_json::{json, Value};
use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const PROXY_ANAHTARLARI: [&str; 5] = [
    "proxy",
    "proxy_url",
    "http_proxy",
    "https_proxy",
    "socks_proxy",
];
const PROXY_TIPLERI: [&str; 5] = ["http", "https", "socks5", "socks5h", "socks4"];
/// Python: restore sirasinda yedekten cikan veritabani bu adla saklanir; baslangicta uygulanir.
pub const BEKLEYEN_GERI_YUKLEME: &str = "restore_bekleyen.db";

fn io_hata(e: impl std::fmt::Display) -> AfuError {
    AfuError::Io(e.to_string())
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn zaman_damgasi() -> String {
    chrono::Local::now().format("%Y%m%d-%H%M%S").to_string()
}

/// Python: Reliability.integrity — PRAGMA integrity_check.
pub fn integrity(store: &dyn Store) -> Result<Json> {
    let satirlar = store.query("PRAGMA integrity_check", &[])?;
    let mesajlar: Vec<String> = satirlar
        .iter()
        .map(|r| {
            let v = r
                .as_object()
                .and_then(|o| o.values().next())
                .cloned()
                .unwrap_or(Value::Null);
            v.as_str()
                .map(str::to_string)
                .unwrap_or_else(|| v.to_string())
        })
        .collect();
    let ok = mesajlar == ["ok"];
    Ok(json!({
        "ok": ok,
        "status": if ok { "ok" } else { "corrupt" },
        "details": mesajlar,
        "action": if ok { "none" } else { "restore_backup" },
        "checked_at": simdi(),
    }))
}

/// Python: Reliability.backup. Tutarli anlik goruntu (VACUUM INTO) + manifest iceren zip yazar.
pub fn backup(store: &dyn Store, data: &Path, neden: &str) -> Result<Json> {
    let klasor = data.join("backups");
    fs::create_dir_all(&klasor)?;
    let zaman = zaman_damgasi();
    let hedef = klasor.join(format!("afudm-{zaman}-{neden}.zip"));
    let gecici = klasor.join(format!("afudm-{zaman}-{neden}.db"));
    let _ = fs::remove_file(&gecici);
    store.execute("VACUUM INTO ?", &[json!(gecici.to_string_lossy())])?;
    {
        let mut zip = zip::ZipWriter::new(fs::File::create(&hedef)?);
        let secenek = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated);
        zip.start_file("afudm.db", secenek).map_err(io_hata)?;
        io::copy(&mut fs::File::open(&gecici)?, &mut zip)?;
        zip.start_file("manifest.json", secenek).map_err(io_hata)?;
        let manifest = json!({
            "created_at": simdi(),
            "reason": neden,
            "contents": ["settings", "download_history"],
        });
        zip.write_all(manifest.to_string().as_bytes())?;
        zip.finish().map_err(io_hata)?;
    }
    let _ = fs::remove_file(&gecici);
    Ok(json!({"ok": true, "path": hedef.to_string_lossy(), "created_at": simdi()}))
}

/// Python: Reliability.backups. `afudm-*.zip` dosyalari, yeniden eskiye.
pub fn backups(data: &Path) -> Json {
    let klasor = data.join("backups");
    let mut dosyalar: Vec<PathBuf> = fs::read_dir(&klasor)
        .map(|rd| {
            rd.filter_map(|g| g.ok().map(|g| g.path()))
                .filter(|p| {
                    let ad = p.file_name().and_then(|s| s.to_str()).unwrap_or("");
                    ad.starts_with("afudm-") && ad.ends_with(".zip")
                })
                .collect()
        })
        .unwrap_or_default();
    dosyalar.sort();
    dosyalar.reverse();
    let items: Vec<Json> = dosyalar
        .iter()
        .filter_map(|p| {
            let meta = fs::metadata(p).ok()?;
            let modified = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0);
            Some(json!({
                "path": p.to_string_lossy(),
                "name": p.file_name().and_then(|s| s.to_str()).unwrap_or(""),
                "size": meta.len(),
                "modified": modified,
            }))
        })
        .collect();
    json!({"ok": true, "items": items})
}

/// Python: Reliability.restore. Yedegi dogrular ve `restore_bekleyen.db` olarak hazirlar.
///
/// SAPMA (bkz. SONUC_G1): Python canli veritabanini kapatip degistirirdi. Store sozlesmesinde
/// baglanti kapatma/yeniden acma yok; bu yuzden yedek hazirlanir ve uygulama bir sonraki
/// acilista bu dosyayi uygulamalidir (`restart_required: true`).
pub fn restore(store: &dyn Store, data: &Path, arsiv: &str) -> Result<Json> {
    let yol = PathBuf::from(arsiv)
        .canonicalize()
        .map_err(|_| AfuError::Invalid("yalniz AfuDM yedekleri geri yuklenebilir".into()))?;
    let kok = data
        .join("backups")
        .canonicalize()
        .map_err(|_| AfuError::Invalid("yalniz AfuDM yedekleri geri yuklenebilir".into()))?;
    if !yol.is_file() || !yol.starts_with(&kok) {
        return Err(AfuError::Invalid(
            "yalniz AfuDM yedekleri geri yuklenebilir".into(),
        ));
    }
    let once = backup(store, data, "before-restore")?;
    let mut zip = zip::ZipArchive::new(fs::File::open(&yol)?).map_err(io_hata)?;
    if zip.by_name("afudm.db").is_err() {
        return Err(AfuError::Invalid("yedekte veritabani yok".into()));
    }
    let gecici = data.join("restore.tmp.db");
    let dogrulama = (|| -> Result<()> {
        const EN_FAZLA_DB: u64 = 2 * 1024 * 1024 * 1024;
        let girdi = zip.by_name("afudm.db").map_err(io_hata)?;
        let boyut = girdi.size();
        if boyut > EN_FAZLA_DB {
            return Err(AfuError::Invalid(
                "yedek veritabani boyutu siniri asiyor".into(),
            ));
        }
        let mut cikti = fs::File::create(&gecici)?;
        let yazilan = io::copy(&mut girdi.take(EN_FAZLA_DB + 1), &mut cikti)?;
        if yazilan > EN_FAZLA_DB || yazilan != boyut {
            return Err(AfuError::Invalid(
                "yedek veritabani boyutu uygun degil".into(),
            ));
        }
        drop(cikti);
        let c = rusqlite::Connection::open(&gecici).map_err(io_hata)?;
        let saglik: String = c
            .query_row("PRAGMA integrity_check", [], |r| r.get(0))
            .map_err(|_| AfuError::Invalid("yedek butun degil".into()))?;
        if saglik != "ok" {
            return Err(AfuError::Invalid("yedek butun degil".into()));
        }
        let surum: i64 = c
            .query_row("PRAGMA user_version", [], |r| r.get(0))
            .map_err(io_hata)?;
        // Migration siniri db crate'inde ozel; yeni bellek DB'si ayni siniri verir.
        let desteklenen = afudm_db::SqliteStore::open_in_memory()?;
        let en_yeni = desteklenen.query("PRAGMA user_version", &[])?;
        let en_yeni = en_yeni
            .first()
            .and_then(|r| r["user_version"].as_i64())
            .ok_or_else(|| AfuError::Invalid("sema surumu okunamadi".into()))?;
        if surum > en_yeni {
            return Err(AfuError::Invalid("yedek daha yeni bir surumden".into()));
        }
        Ok(())
    })();
    if let Err(e) = dogrulama {
        let _ = fs::remove_file(&gecici);
        return Err(e);
    }
    let hedef = data.join(BEKLEYEN_GERI_YUKLEME);
    fs::rename(&gecici, &hedef)?;
    let _ = store; // canli baglanti bu adimda degismez
    Ok(json!({
        "ok": true,
        "pre_restore_backup": once["path"],
        "restart_required": true,
        "staged": hedef.to_string_lossy(),
    }))
}

/// Python: Reliability.diagnostics_preview — tum veri maskelenmis halde.
pub fn diagnostics_preview(store: &dyn Store, app_dir: &Path) -> Result<Json> {
    let veri = json!({
        "generated_at": simdi(),
        "integrity": integrity(store)?,
        "engines": afudm_engine::engines::durum(app_dir),
        "settings": store.all_settings()?,
        "events": store.recent_events(150, "")?,
    });
    Ok(json!({"ok": true, "preview": maskele(&veri), "masked": true}))
}

/// Python: Reliability.diagnostics_export — maskeli tanilamayi diske yazar.
pub fn diagnostics_export(store: &dyn Store, data: &Path, app_dir: &Path) -> Result<Json> {
    let onizleme = diagnostics_preview(store, app_dir)?["preview"].clone();
    let klasor = data.join("diagnostics");
    fs::create_dir_all(&klasor)?;
    let hedef = klasor.join(format!("afudm-diagnostics-{}.json", zaman_damgasi()));
    fs::write(
        &hedef,
        serde_json::to_string_pretty(&onizleme).map_err(io_hata)?,
    )?;
    Ok(json!({"ok": true, "path": hedef.to_string_lossy(), "masked": true}))
}

/// Python: Reliability.recovery_preview. Yerel dosya + sunucu HEAD bilgisi; dogrulanan bayt tahmini.
pub fn recovery_preview(store: &dyn Store, varsayilan_klasor: &str, row_id: i64) -> Result<Json> {
    let row = store
        .by_id(row_id)?
        .ok_or_else(|| AfuError::Invalid("indirme bulunamadi".into()))?;
    let klasor = row["dest_dir"]
        .as_str()
        .filter(|s| !s.is_empty())
        .unwrap_or(varsayilan_klasor);
    let ad = row["filename"]
        .as_str()
        .filter(|s| !s.is_empty())
        .or(row["title"].as_str())
        .unwrap_or("");
    let hedef = PathBuf::from(klasor).join(ad);
    let kontrol = PathBuf::from(format!("{}.aria2", hedef.to_string_lossy()));
    let yerel = if hedef.is_file() {
        fs::metadata(&hedef)?.len()
    } else {
        0
    };
    let uzak = match uzak_bilgi(row["source"].as_str().unwrap_or("")) {
        Ok((etag, uzunluk, aralik)) => json!({"etag": etag, "length": uzunluk, "range": aralik}),
        Err(tur) => json!({"etag": null, "length": null, "range": false, "error": tur}),
    };
    let etag_var = uzak["etag"].as_str().is_some_and(|s| !s.is_empty());
    let dogrulanan = if uzak["range"] == true && etag_var {
        yerel
    } else {
        0
    };
    Ok(json!({
        "ok": true,
        "original_preserved": true,
        "control_file": kontrol.exists(),
        "local_bytes": yerel,
        "remote": uzak,
        "hash_verified_bytes": 0,
        "source_verified_bytes": dogrulanan,
        "unverified_bytes": yerel.saturating_sub(dogrulanan),
        "can_attempt": kontrol.exists() && uzak["range"] == true,
        "warning": "Dosya boyutu parcalarin saglamligini kanitlamaz; yalniz listelenen dogrulamalar gecerlidir.",
    }))
}

/// HEAD ile (etag, uzunluk, aralik) — hata turu Python'daki exception adina benzer doner.
fn uzak_bilgi(url: &str) -> std::result::Result<(Option<String>, u64, bool), &'static str> {
    if url.is_empty() {
        return Err("ValueError");
    }
    let yapi = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(8)))
        .build();
    let ajan = ureq::Agent::new_with_config(yapi);
    let yanit = ajan.head(url).call().map_err(|e| match e {
        ureq::Error::StatusCode(_) => "HTTPError",
        _ => "URLError",
    })?;
    let etag = yanit
        .headers()
        .get("etag")
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);
    let uzunluk = yanit
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(0);
    let aralik = yanit
        .headers()
        .get("accept-ranges")
        .and_then(|v| v.to_str().ok())
        .is_some_and(|s| s.to_ascii_lowercase().contains("bytes"));
    Ok((etag, uzunluk, aralik))
}

fn url_sir_re() -> Option<&'static Regex> {
    static R: OnceLock<Option<Regex>> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(r"(?i)([?&](?:token|key|sig|signature|password|auth)=[^&#\s]+)").ok()
    })
    .as_ref()
}

fn metin_sir_re() -> Option<&'static Regex> {
    static R: OnceLock<Option<Regex>> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(r#"(?i)(token|passwd|password|cookie|authorization|api[_-]?key)\s*([:=])\s*([^\s,&"]+)"#).ok()
    })
    .as_ref()
}

fn anahtar_sir_re() -> Option<&'static Regex> {
    static R: OnceLock<Option<Regex>> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(
            r"(?i)(token|password|passwd|secret|cookie|authorization|api[_-]?key|key|sifre|parola)",
        )
        .ok()
    })
    .as_ref()
}

/// Python: mask() — metindeki kimlik bilgilerini siler. Regex yuklenemezse hepsini gizler (kapali taraf).
pub fn mask(deger: &str) -> String {
    let (Some(url), Some(metin)) = (url_sir_re(), metin_sir_re()) else {
        return "***".to_string();
    };
    let url_temiz = url.replace_all(deger, |c: &Captures| {
        format!("{}=***", c[1].split('=').next().unwrap_or(""))
    });
    metin
        .replace_all(&url_temiz, |c: &Captures| format!("{}{}***", &c[1], &c[2]))
        .into_owned()
}

/// Python: proxy_maskele — kimlik bolumu tamamen atilir; bozuk girdi "<proxy>" olur.
pub fn proxy_maskele(proxy: &str) -> String {
    let ham = proxy.trim();
    if ham.is_empty() {
        return String::new();
    }
    match proxy_parcala(ham) {
        Some((tip, giris)) => format!("{tip}://{giris}"),
        None => "<proxy>".to_string(),
    }
}

fn proxy_parcala(ham: &str) -> Option<(String, String)> {
    let mut giris = ham;
    let mut tip = "http".to_string();
    if let Some((sekme, geri)) = giris.split_once("://") {
        tip = sekme.trim().to_lowercase();
        giris = geri;
        if !PROXY_TIPLERI.contains(&tip.as_str()) {
            return None;
        }
    }
    if let Some((_, son)) = giris.rsplit_once('@') {
        giris = son;
    }
    let giris = giris.trim();
    // Python: ^[^:\s/@]+:\d+$
    let (host, port) = giris.split_once(':')?;
    let host_gecerli = !host.is_empty()
        && !host.contains(|c: char| c.is_whitespace() || c == '/' || c == '@' || c == ':');
    let port_gecerli = !port.is_empty() && port.bytes().all(|b| b.is_ascii_digit());
    if !host_gecerli || !port_gecerli || port.contains(':') {
        return None;
    }
    let numara: u32 = port.parse().ok()?;
    if !(1..=65535).contains(&numara) {
        return None;
    }
    Some((tip, giris.to_string()))
}

fn sir_anahtari_mi(anahtar: &str) -> bool {
    anahtar_sir_re().is_none_or(|r| r.is_match(anahtar))
}

fn sir_maskele(deger: &Json, anahtar: &str) -> Json {
    if !anahtar.is_empty() && sir_anahtari_mi(anahtar) {
        return json!("***");
    }
    match deger {
        Value::Object(m) => Value::Object(
            m.iter()
                .map(|(k, v)| (k.clone(), sir_maskele(v, k)))
                .collect(),
        ),
        Value::Array(a) => Value::Array(a.iter().map(|v| sir_maskele(v, anahtar)).collect()),
        Value::String(s) => {
            if PROXY_ANAHTARLARI.contains(&anahtar) && !s.trim().is_empty() {
                json!(proxy_maskele(s))
            } else {
                json!(mask(s))
            }
        }
        diger => diger.clone(),
    }
}

/// Python: maskele — ayar/olay verisini disari cikmadan once maskeler.
pub fn maskele(veri: &Json) -> Json {
    sir_maskele(veri, "")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::g1::test_sunucu;
    use std::path::PathBuf;

    #[test]
    fn fix8_yeni_sema_reddedilir() {
        let d = gecici("fix8-sema");
        let store = bellek_db();
        store.execute("PRAGMA user_version=999", &[]).unwrap();
        let y = backup(&store, &d, "future").unwrap();
        let r = restore(&store, &d, y["path"].as_str().unwrap());
        assert!(r.is_err(), "yeni sema kabul edildi");
        assert!(r.unwrap_err().to_string().contains("daha yeni"));
        assert!(!d.join(BEKLEYEN_GERI_YUKLEME).exists());
        assert!(!d.join("restore.tmp.db").exists());
    }

    #[test]
    fn fix8_buyuk_zip_girdisi_reddedilir() {
        let d = gecici("fix8-buyuk");
        let store = bellek_db();
        let y = backup(&store, &d, "large").unwrap();
        let yol = PathBuf::from(y["path"].as_str().unwrap());
        let mut bytes = fs::read(&yol).unwrap();
        let pos = bytes.windows(4).position(|b| b == b"PK\x01\x02").unwrap();
        bytes[pos + 24..pos + 28].copy_from_slice(&(2_147_483_649u32).to_le_bytes());
        fs::write(&yol, bytes).unwrap();
        let r = restore(&store, &d, yol.to_str().unwrap());
        assert!(r.is_err(), "buyuk girdi kabul edildi");
        assert!(r.unwrap_err().to_string().contains("boyutu"));
        assert!(!d.join(BEKLEYEN_GERI_YUKLEME).exists());
    }

    fn gecici(ad: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("afudm-g1-rel-{ad}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).expect("klasor");
        d
    }

    fn bellek_db() -> afudm_db::SqliteStore {
        afudm_db::SqliteStore::open_in_memory().expect("db")
    }

    #[test]
    fn mask_url_ve_metin_sirlarini_siler() {
        assert_eq!(
            mask("https://x/y?token=abc&k=1"),
            "https://x/y?token=***&k=1"
        );
        assert_eq!(mask("password: hunter2 ok"), "password:*** ok");
        assert_eq!(mask("normal metin"), "normal metin");
    }

    #[test]
    fn proxy_kimligi_atilir() {
        assert_eq!(
            proxy_maskele("socks5://kullanici:parola@10.0.0.1:1080"),
            "socks5://10.0.0.1:1080"
        );
        assert_eq!(proxy_maskele("http://h:8080"), "http://h:8080");
        assert_eq!(proxy_maskele("bozuk girdi"), "<proxy>");
        assert_eq!(proxy_maskele("ftp://h:21"), "<proxy>");
        assert_eq!(proxy_maskele("h:70000"), "<proxy>");
    }

    #[test]
    fn maskele_anahtar_adina_gore_gizler() {
        let veri = json!({
            "api_token": "gizli",
            "ayarlar": {"proxy": "http://u:p@host:8080", "dil": "tr"},
            "liste": ["sifre", {"password": "x"}],
        });
        let m = maskele(&veri);
        assert_eq!(m["api_token"], "***");
        assert_eq!(m["ayarlar"]["proxy"], "http://host:8080");
        assert_eq!(m["ayarlar"]["dil"], "tr");
        assert_eq!(m["liste"][1]["password"], "***");
    }

    #[test]
    fn saglik_temiz_veritabaninda_ok() {
        let store = bellek_db();
        let s = integrity(&store).expect("integrity");
        assert_eq!(s["ok"], true, "{s}");
        assert_eq!(s["action"], "none");
    }

    #[test]
    fn yedek_olusur_listelenir_ve_geri_yuklenir() {
        let d = gecici("yedek");
        let store = bellek_db();
        let y = backup(&store, &d, "manual").expect("yedek");
        let yol = PathBuf::from(y["path"].as_str().expect("yol"));
        assert!(yol.is_file());
        let liste = backups(&d);
        assert_eq!(liste["items"].as_array().map(Vec::len), Some(1));
        let r = restore(&store, &d, yol.to_str().expect("utf8")).expect("geri yukle");
        assert_eq!(r["restart_required"], true);
        assert!(d.join(BEKLEYEN_GERI_YUKLEME).is_file());
        // Yedek klasoru disindaki dosya reddedilir.
        let dis = d.join("dis.zip");
        fs::write(&dis, b"x").expect("yaz");
        assert!(restore(&store, &d, dis.to_str().expect("utf8")).is_err());
    }

    #[test]
    fn tani_maskeli_disa_aktarilir() {
        let d = gecici("tani");
        let store = bellek_db();
        store.set("api_token", json!("cok-gizli")).expect("set");
        let onizleme = diagnostics_preview(&store, &d).expect("onizleme");
        assert_eq!(onizleme["masked"], true);
        assert_eq!(onizleme["preview"]["settings"]["api_token"], "***");
        assert!(
            onizleme["preview"]["engines"].is_object(),
            "engines anahtari Python diagnostics ile ayni olmali"
        );
        let disa = diagnostics_export(&store, &d, &d).expect("disa");
        let metin = fs::read_to_string(disa["path"].as_str().expect("yol")).expect("oku");
        assert!(!metin.contains("cok-gizli"));
    }

    #[test]
    fn kurtarma_onizlemesi_sunucudan_dogrular() {
        let d = gecici("kurtarma");
        let store = bellek_db();
        let base = test_sunucu::baslat_basliklarla(vec![(
            "/dosya.bin",
            "Accept-Ranges: bytes\r\nETag: \"abc\"\r\n",
            b"ABCD".to_vec(),
        )]);
        let yol = d.join("dosya.bin");
        fs::write(&yol, b"AB").expect("yaz");
        fs::write(d.join("dosya.bin.aria2"), b"x").expect("yaz");
        let id = store
            .add(
                "http",
                &format!("{base}/dosya.bin"),
                Some("dosya.bin"),
                Some(d.to_str().expect("utf8")),
                None,
                None,
                Some("kurt"),
            )
            .expect("ekle");
        let s = recovery_preview(&store, d.to_str().expect("utf8"), id).expect("onizle");
        assert_eq!(s["local_bytes"], 2);
        assert_eq!(s["remote"]["range"], true);
        assert_eq!(s["control_file"], true);
        assert_eq!(s["can_attempt"], true);
        assert_eq!(s["unverified_bytes"], 0);
    }

    #[test]
    fn kurtarma_olmayan_satir_hata_verir() {
        let store = bellek_db();
        let hata = recovery_preview(&store, "C:/", 999).expect_err("satir yok");
        assert!(matches!(hata, AfuError::Invalid(_)));
    }
}
