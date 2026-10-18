//! core/eklenti.py (manifest, paket, ayar) karsiligi.
//!
//! DURUSTLUK: bu bir sandbox DEGILDIR. Manifestteki izin ve domain listeleri beyandir;
//! teknik olarak zorlanmaz. "Izole calisir" iddiasi kullanilmaz.

use super::py::{kes, py_esit, py_float_of, py_metin_veya_bos, py_str, truthy};
use afudm_types::{Json, JsonMap};
use regex::Regex;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub const MANIFEST_ADI: &str = "eklenti.json";
pub const PAKET_UZANTISI: &str = ".afup";
/// Uygulama surumu (Python `core/surum.py` SURUM karsiligi); workspace surumunden gelir.
pub const SURUM: &str = env!("CARGO_PKG_VERSION");
pub const BILINEN_IZINLER: [&str; 9] = [
    "indirme_oku",
    "indirme_ekle",
    "indirme_yonet",
    "ayar_oku",
    "ayar_yaz",
    "ag",
    "dosya_oku",
    "dosya_yaz",
    "bildirim",
];
pub const UYGULAMA_ZAMANLARI: [&str; 4] = [
    "hemen",
    "yeni_indirmeler",
    "sonraki_baslatma",
    "servis_yeniden",
];
const AYAR_TURLERI: [&str; 4] = ["metin", "sayi", "anahtar", "secim"];
const BELLEK_BAYT_MB: u64 = 1024 * 1024;

/// Kullaniciya gosterilebilir eklenti hatasi (kod anahtari + mesaj). Python: EklentiHatasi.
#[derive(Debug, Clone, PartialEq)]
pub struct EklentiHatasi {
    pub kod: String,
    pub mesaj: String,
}

impl EklentiHatasi {
    pub fn new(kod: &str, mesaj: impl Into<String>) -> Self {
        Self {
            kod: kod.to_string(),
            mesaj: mesaj.into(),
        }
    }
}

impl std::fmt::Display for EklentiHatasi {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.mesaj)
    }
}

impl std::error::Error for EklentiHatasi {}

/// Python `{"ok": False, "code": kod, "error": mesaj}`.
pub fn hata_yaniti(kod: &str, mesaj: &str) -> Json {
    json!({"ok": false, "code": kod, "error": mesaj})
}

fn ad_desen() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^[a-z0-9][a-z0-9_-]{1,39}$").expect("sabit desen"))
}
fn surum_desen() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^\d+(\.\d+){0,3}$").expect("sabit desen"))
}
fn giris_desen() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^[A-Za-z0-9_./-]+\.py$").expect("sabit desen"))
}
fn domain_desen() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(r"^(\*\.)?[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$").expect("sabit desen")
    })
}

/// Python `surum_dizisi`: en fazla 4 parca, eksikler 0.
fn surum_dizisi(metin: &str) -> [i64; 4] {
    let metin = if metin.is_empty() { "0" } else { metin };
    let mut d = [0i64; 4];
    for (i, parca) in metin.split('.').take(4).enumerate() {
        d[i] = parca.parse().unwrap_or(0);
    }
    d
}

/// Python `surum_uyumlu`. `mevcut` None ise uygulama surumu (SURUM).
pub fn surum_uyumlu(min_surum: &str, max_surum: &str, mevcut: Option<&str>) -> bool {
    let m = surum_dizisi(mevcut.unwrap_or(SURUM));
    if !min_surum.is_empty() && m < surum_dizisi(min_surum) {
        return false;
    }
    if !max_surum.is_empty() && m > surum_dizisi(max_surum) {
        return false;
    }
    true
}

/// Python `_metin`: None -> "", metin/sayi/bool kabul, digerleri hata.
fn metin(
    nesne: &JsonMap,
    anahtar: &str,
    zorunlu: bool,
    sinir: usize,
) -> Result<String, EklentiHatasi> {
    let s = match nesne.get(anahtar) {
        None | Some(Json::Null) => String::new(),
        Some(v @ (Json::String(_) | Json::Number(_) | Json::Bool(_))) => py_str(v),
        Some(_) => {
            return Err(EklentiHatasi::new(
                "MANIFEST_ALAN",
                format!("{anahtar} metin olmali"),
            ))
        }
    };
    let s = s.trim().to_string();
    if zorunlu && s.is_empty() {
        return Err(EklentiHatasi::new(
            "MANIFEST_EKSIK",
            format!("{anahtar} zorunlu"),
        ));
    }
    Ok(kes(&s, sinir))
}

/// Python `x or varsayilan` + str(): falsy ise varsayilan.
fn str_veya(v: Option<&Json>, varsayilan: &str) -> String {
    match v {
        Some(x) if truthy(x) => py_str(x),
        _ => varsayilan.to_string(),
    }
}

/// Python: `ham.get(k) or []` + liste olmali. Yanlis tip `hata` ile reddedilir.
fn liste_al<'a>(v: Option<&'a Json>, hata: &str) -> Result<Vec<&'a Json>, EklentiHatasi> {
    match v {
        None => Ok(Vec::new()),
        Some(x) if !truthy(x) => Ok(Vec::new()),
        Some(Json::Array(a)) => Ok(a.iter().collect()),
        Some(_) => Err(EklentiHatasi::new("MANIFEST_ALAN", hata)),
    }
}

fn ayar_semasi_dogrula(ham: Option<&Json>) -> Result<Vec<Json>, EklentiHatasi> {
    let liste = match ham {
        None | Some(Json::Null) => return Ok(Vec::new()),
        Some(Json::String(s)) if s.is_empty() => return Ok(Vec::new()),
        Some(Json::Array(a)) => a,
        Some(_) => {
            return Err(EklentiHatasi::new(
                "MANIFEST_ALAN",
                "ayar_semasi liste olmali",
            ))
        }
    };
    let mut cikti = Vec::new();
    let mut gorulen = HashSet::new();
    for alan in liste.iter().take(40) {
        let Some(nesne) = alan.as_object() else {
            return Err(EklentiHatasi::new(
                "MANIFEST_ALAN",
                "ayar_semasi ogesi nesne olmali",
            ));
        };
        let anahtar = py_metin_veya_bos(nesne.get("anahtar"));
        if anahtar.is_empty() || anahtar.chars().count() > 60 || gorulen.contains(&anahtar) {
            return Err(EklentiHatasi::new(
                "MANIFEST_ALAN",
                format!("ayar anahtari gecersiz: {}", kes(&anahtar, 40)),
            ));
        }
        gorulen.insert(anahtar.clone());
        let tur = str_veya(nesne.get("tur"), "metin").trim().to_string();
        if !AYAR_TURLERI.contains(&tur.as_str()) {
            return Err(EklentiHatasi::new(
                "MANIFEST_ALAN",
                format!("bilinmeyen ayar turu: {}", kes(&tur, 20)),
            ));
        }
        let mut uygulama = str_veya(nesne.get("uygulama"), "hemen").trim().to_string();
        if !UYGULAMA_ZAMANLARI.contains(&uygulama.as_str()) {
            uygulama = "hemen".into();
        }
        let secenekler: Vec<Json> = if tur == "secim" {
            let ham_secenek = liste_al(nesne.get("secenekler"), "secenekler liste olmali")?;
            if ham_secenek.is_empty() {
                return Err(EklentiHatasi::new(
                    "MANIFEST_ALAN",
                    format!("{anahtar}: secim icin secenekler gerekli"),
                ));
            }
            ham_secenek
                .iter()
                .take(50)
                .map(|s| json!(kes(&py_str(s), 80)))
                .collect()
        } else {
            Vec::new()
        };
        let varsayilan = match nesne.get("varsayilan") {
            Some(v) => v.clone(),
            None => match tur.as_str() {
                "metin" => json!(""),
                "sayi" => json!(0),
                "anahtar" => json!(false),
                _ => secenekler.first().cloned().unwrap_or(Json::Null),
            },
        };
        let mut girdi = json!({
            "anahtar": anahtar,
            "tur": tur,
            "etiket": kes(&str_veya(nesne.get("etiket"), &anahtar), 120),
            "aciklama": kes(&str_veya(nesne.get("aciklama"), ""), 300),
            "varsayilan": varsayilan,
            "secenekler": secenekler,
            "uygulama": uygulama,
        });
        if tur == "sayi" {
            for sinir_ad in ["en_az", "en_cok"] {
                if let Some(ham_sinir) = nesne.get(sinir_ad) {
                    let Some(f) = py_float_of(ham_sinir) else {
                        return Err(EklentiHatasi::new(
                            "MANIFEST_ALAN",
                            format!("{anahtar}: {sinir_ad} sayi olmali"),
                        ));
                    };
                    girdi[sinir_ad] = json!(f);
                }
            }
        }
        cikti.push(girdi);
    }
    Ok(cikti)
}

/// Ham manifesti dogrular ve NORMALLESTIRILMIS nesne doner. Gecersizse hicbir sey kurulmaz.
/// Python: manifest_dogrula. Alan siralamasi Python'daki dogrulama sirasini izler.
pub fn manifest_dogrula(ham: &Json) -> Result<Json, EklentiHatasi> {
    let Some(nesne) = ham.as_object() else {
        return Err(EklentiHatasi::new(
            "MANIFEST_BOZUK",
            "manifest bir JSON nesnesi olmali",
        ));
    };
    let ad = metin(nesne, "ad", true, 40)?.to_lowercase();
    if !ad_desen().is_match(&ad) {
        return Err(EklentiHatasi::new(
            "MANIFEST_AD",
            "ad yalniz kucuk harf, rakam, - ve _ icerebilir",
        ));
    }
    let eklenti_surum = metin(nesne, "surum", true, 20)?;
    if !surum_desen().is_match(&eklenti_surum) {
        return Err(EklentiHatasi::new(
            "MANIFEST_SURUM",
            "surum 1.2.3 biciminde olmali",
        ));
    }
    let giris = metin(nesne, "giris", true, 120)?.replace('\\', "/");
    if !giris_desen().is_match(&giris)
        || giris.starts_with('/')
        || giris.split('/').any(|p| p == "..")
    {
        return Err(EklentiHatasi::new(
            "MANIFEST_GIRIS",
            "giris paket icinde bir .py dosyasi olmali",
        ));
    }
    let afudm_min = metin(nesne, "afudm_min", false, 20)?;
    let afudm_max = metin(nesne, "afudm_max", false, 20)?;
    for (etiket, deger) in [("afudm_min", &afudm_min), ("afudm_max", &afudm_max)] {
        if !deger.is_empty() && !surum_desen().is_match(deger) {
            return Err(EklentiHatasi::new(
                "MANIFEST_SURUM",
                format!("{etiket} 1.2.3 biciminde olmali"),
            ));
        }
    }

    let mut izinler: Vec<String> = Vec::new();
    for izin in liste_al(nesne.get("izinler"), "izinler liste olmali")?
        .into_iter()
        .take(30)
    {
        let m = kes(py_str(izin).trim(), 40);
        if !m.is_empty() && !izinler.contains(&m) {
            izinler.push(m);
        }
    }

    let mut domainler: Vec<String> = Vec::new();
    for domain in liste_al(nesne.get("domainler"), "domainler liste olmali")?
        .into_iter()
        .take(60)
    {
        let m = kes(&py_str(domain).trim().to_lowercase(), 120);
        if m.is_empty() {
            continue;
        }
        if m != "*" && !domain_desen().is_match(&m) {
            return Err(EklentiHatasi::new(
                "MANIFEST_DOMAIN",
                format!("gecersiz domain: {}", kes(&m, 40)),
            ));
        }
        if !domainler.contains(&m) {
            domainler.push(m);
        }
    }

    let baslik = metin(nesne, "baslik", false, 120)?;
    let aciklama = metin(nesne, "aciklama", false, 500)?;
    let yazar = metin(nesne, "yazar", false, 120)?;
    let sha256 = metin(nesne, "sha256", false, 64)?.to_lowercase();
    let ayar_semasi = ayar_semasi_dogrula(nesne.get("ayar_semasi"))?;

    Ok(json!({
        "ad": ad,
        "baslik": if baslik.is_empty() { ad.clone() } else { baslik },
        "surum": eklenti_surum,
        "aciklama": aciklama,
        "yazar": yazar,
        "giris": giris,
        "afudm_min": afudm_min,
        "afudm_max": afudm_max,
        "sha256": sha256,
        "izinler": izinler,
        "domainler": domainler,
        "ayar_semasi": ayar_semasi,
    }))
}

/// Bir zip uyesinin kurulum icin gerekli bilgileri.
pub(super) struct Uye {
    pub ad: String,
    pub boyut: u64,
    pub dizin: bool,
}

fn bozuk_zip(_: impl std::fmt::Display) -> EklentiHatasi {
    EklentiHatasi::new("PAKET_BOZUK", "paket okunamadi (zip bozuk)")
}

/// Zip Slip + zip bomb korumasi. Python: _zip_guvenli_uyeler.
pub(super) fn zip_guvenli_uyeler(
    arsiv: &mut zip::ZipArchive<File>,
    max_boyut: u64,
    max_oran: f64,
) -> Result<Vec<Uye>, EklentiHatasi> {
    let mut uyeler = Vec::new();
    let mut toplam = 0u64;
    let mut toplam_sikisik = 0u64;
    for i in 0..arsiv.len() {
        let f = arsiv.by_index_raw(i).map_err(bozuk_zip)?;
        let ad = f.name().replace('\\', "/");
        let ilk = ad.split('/').next().unwrap_or("");
        if ad.starts_with('/')
            || ad.split('/').any(|p| p == "..")
            || ilk.chars().nth(1) == Some(':')
        {
            return Err(EklentiHatasi::new(
                "PAKET_GUVENSIZ",
                format!("paket disina yazmaya calisiyor: {}", kes(&ad, 60)),
            ));
        }
        let boyut = f.size();
        if boyut > max_boyut {
            return Err(EklentiHatasi::new(
                "PAKET_COK_BUYUK",
                format!("dosya cok buyuk: {} ({boyut} bayt)", kes(&ad, 60)),
            ));
        }
        toplam += boyut;
        toplam_sikisik += f.compressed_size();
        uyeler.push(Uye {
            dizin: f.is_dir(),
            boyut,
            ad,
        });
    }
    if toplam > max_boyut {
        return Err(EklentiHatasi::new(
            "PAKET_COK_BUYUK",
            format!("toplam boyut cok buyuk: {toplam} bayt"),
        ));
    }
    if toplam_sikisik > 0 && (toplam as f64 / toplam_sikisik as f64) > max_oran {
        return Err(EklentiHatasi::new(
            "PAKET_COK_BUYUK",
            "asiri sikistirma orani (zip bomb suphesi)",
        ));
    }
    Ok(uyeler)
}

fn json_oku(ham: &[u8]) -> Result<Json, EklentiHatasi> {
    let govde = ham.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(ham);
    serde_json::from_slice(govde).map_err(|_| {
        EklentiHatasi::new(
            "MANIFEST_BOZUK",
            format!("{MANIFEST_ADI} gecerli JSON degil"),
        )
    })
}

fn io_hatasi(e: impl std::fmt::Display) -> EklentiHatasi {
    EklentiHatasi::new("PAKET_OKUNAMADI", kes(&e.to_string(), 200))
}

/// Klasor icinde (rglob) tum girdi sayisi ve dosya boyutu toplami.
fn dizin_istatistik(kok: &Path) -> std::io::Result<(u64, u64)> {
    let (mut sayi, mut boyut) = (0u64, 0u64);
    let mut yigin = vec![kok.to_path_buf()];
    while let Some(dizin) = yigin.pop() {
        for girdi in std::fs::read_dir(&dizin)? {
            let girdi = girdi?;
            sayi += 1;
            let yol = girdi.path();
            if yol.is_dir() {
                yigin.push(yol);
            } else {
                boyut += girdi.metadata()?.len();
            }
        }
    }
    Ok((sayi, boyut))
}

/// Kurmadan once manifesti okur. `.afup` (zip) veya acik klasor kabul eder. Python: paket_incele.
pub fn paket_incele(yol: &str, max_boyut_mb: i64, max_oran: f64) -> Result<Json, EklentiHatasi> {
    let kaynak = PathBuf::from(yol.trim().trim_matches('"'));
    if !kaynak.exists() {
        return Err(EklentiHatasi::new("PAKET_YOK", "paket bulunamadi"));
    }
    let (ham, dosya_sayisi, boyut) = if kaynak.is_dir() {
        let mf = kaynak.join(MANIFEST_ADI);
        if !mf.is_file() {
            return Err(EklentiHatasi::new(
                "MANIFEST_YOK",
                format!("{MANIFEST_ADI} bulunamadi"),
            ));
        }
        let ham = json_oku(&std::fs::read(&mf).map_err(io_hatasi)?)?;
        let (sayi, boyut) = dizin_istatistik(&kaynak).map_err(io_hatasi)?;
        (ham, sayi, boyut)
    } else {
        let uzanti = kaynak
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()));
        if uzanti.as_deref() != Some(PAKET_UZANTISI) {
            return Err(EklentiHatasi::new(
                "PAKET_TUR",
                format!("yalniz {PAKET_UZANTISI} paketi veya klasor"),
            ));
        }
        let file = File::open(&kaynak).map_err(io_hatasi)?;
        let mut arsiv = zip::ZipArchive::new(file).map_err(|_| bozuk_zip(""))?;
        let max_bayt = (max_boyut_mb.max(0) as u64).saturating_mul(BELLEK_BAYT_MB);
        let uyeler = zip_guvenli_uyeler(&mut arsiv, max_bayt, max_oran)?;
        if !uyeler.iter().any(|u| u.ad == MANIFEST_ADI) {
            return Err(EklentiHatasi::new(
                "MANIFEST_YOK",
                format!("pakette {MANIFEST_ADI} yok (kokte olmali)"),
            ));
        }
        let mut icerik = Vec::new();
        arsiv
            .by_name(MANIFEST_ADI)
            .map_err(bozuk_zip)?
            .read_to_end(&mut icerik)
            .map_err(bozuk_zip)?;
        let ham = json_oku(&icerik)?;
        let dosya_sayisi = uyeler.iter().filter(|u| !u.dizin).count() as u64;
        let boyut = uyeler.iter().map(|u| u.boyut).sum();
        (ham, dosya_sayisi, boyut)
    };

    let mut manifest = manifest_dogrula(&ham)?;
    let (min, max) = (
        manifest["afudm_min"].as_str().unwrap_or("").to_string(),
        manifest["afudm_max"].as_str().unwrap_or("").to_string(),
    );
    let obj = manifest
        .as_object_mut()
        .expect("manifest_dogrula nesne doner");
    obj.insert("uyumlu".into(), json!(surum_uyumlu(&min, &max, None)));
    obj.insert("afudm_surum".into(), json!(SURUM));
    obj.insert("kaynak".into(), json!(kaynak.display().to_string()));
    obj.insert("dosya_sayisi".into(), json!(dosya_sayisi));
    obj.insert("boyut".into(), json!(boyut));
    // UI bunu kurulum onayinda AYNEN gosterir: teknik kisitlama YOKTUR.
    obj.insert("guven_modeli".into(), json!("guvenilen_eklenti"));
    Ok(manifest)
}

pub(super) fn kopyala_dizin(kaynak: &Path, hedef: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(hedef)?;
    for girdi in std::fs::read_dir(kaynak)? {
        let girdi = girdi?;
        let yol = girdi.path();
        let dest = hedef.join(girdi.file_name());
        if yol.is_dir() {
            kopyala_dizin(&yol, &dest)?;
        } else {
            std::fs::copy(&yol, &dest)?;
        }
    }
    Ok(())
}

/// Paketi `hedef` altina acar (klasor kopyalanir; zip guvenli sekilde cikarilir).
pub(super) fn paket_ac(
    kaynak: &Path,
    hedef: &Path,
    max_boyut_mb: i64,
    max_oran: f64,
) -> Result<(), EklentiHatasi> {
    let acilamadi = |e: std::io::Error| {
        EklentiHatasi::new("PAKET_ACILMADI", kes(&format!("paket acilamadi: {e}"), 300))
    };
    std::fs::create_dir_all(hedef).map_err(acilamadi)?;
    if kaynak.is_dir() {
        return kopyala_dizin(kaynak, hedef).map_err(acilamadi);
    }
    let file = File::open(kaynak).map_err(acilamadi)?;
    let mut arsiv = zip::ZipArchive::new(file).map_err(|e| {
        EklentiHatasi::new("PAKET_ACILMADI", kes(&format!("paket acilamadi: {e}"), 300))
    })?;
    let max_bayt = (max_boyut_mb.max(0) as u64).saturating_mul(BELLEK_BAYT_MB);
    zip_guvenli_uyeler(&mut arsiv, max_bayt, max_oran)?;
    for i in 0..arsiv.len() {
        let mut f = arsiv.by_index(i).map_err(|e| {
            EklentiHatasi::new("PAKET_ACILMADI", kes(&format!("paket acilamadi: {e}"), 300))
        })?;
        let ad = f.name().replace('\\', "/");
        let yol = hedef.join(&ad);
        if ad.ends_with('/') {
            std::fs::create_dir_all(&yol).map_err(acilamadi)?;
            continue;
        }
        if let Some(ust) = yol.parent() {
            std::fs::create_dir_all(ust).map_err(acilamadi)?;
        }
        let mut cikti = File::create(&yol).map_err(acilamadi)?;
        std::io::copy(&mut f, &mut cikti).map_err(acilamadi)?;
    }
    Ok(())
}

/// Dosyalarin SHA256 ozeti: ada gore sirali, manifest haric (Python: paket_sha256 kalibi).
pub(super) fn paket_sha256(kaynak: &Path) -> Result<String, EklentiHatasi> {
    let file = File::open(kaynak).map_err(io_hatasi)?;
    let mut arsiv = zip::ZipArchive::new(file).map_err(bozuk_zip)?;
    let mut dosyalar: Vec<String> = Vec::new();
    for i in 0..arsiv.len() {
        let f = arsiv.by_index_raw(i).map_err(bozuk_zip)?;
        if !f.is_dir() && f.name() != MANIFEST_ADI {
            dosyalar.push(f.name().to_string());
        }
    }
    dosyalar.sort();
    let mut h = Sha256::new();
    let mut tampon = vec![0u8; 65536];
    for dosya in dosyalar {
        let mut f = arsiv.by_name(&dosya).map_err(bozuk_zip)?;
        loop {
            let n = f.read(&mut tampon).map_err(bozuk_zip)?;
            if n == 0 {
                break;
            }
            h.update(&tampon[..n]);
        }
    }
    Ok(h.finalize().iter().map(|b| format!("{b:02x}")).collect())
}

/// Manifestteki `sha256` ile gercek ozeti karsilastirir (Python: _kur_isle / _guncelle_isle).
/// Donus: gercek ozet (dosya yoksa bos). Imzasiz ve izin kapaliysa hata.
pub(super) fn ozet_dogrula(
    kaynak: &Path,
    manifest: &Json,
    imzasiz_izin: bool,
) -> Result<String, EklentiHatasi> {
    if !kaynak.is_file() {
        return Ok(String::new());
    }
    let gercek = paket_sha256(kaynak)?;
    let beklenen = manifest["sha256"].as_str().unwrap_or("").to_lowercase();
    if beklenen.is_empty() {
        if !imzasiz_izin {
            return Err(EklentiHatasi::new(
                "IMZASIZ_REDDEDILDI",
                "imzasiz (sha256 yok) eklentiye izin verilmiyor",
            ));
        }
    } else if beklenen != gercek {
        return Err(EklentiHatasi::new(
            "OZET_UYUSMUYOR",
            format!("sha256 uyusmuyor! beklenen: {beklenen}, gercek: {gercek}"),
        ));
    }
    Ok(gercek)
}

pub(super) fn sil(klasor: &Path) {
    let _ = std::fs::remove_dir_all(klasor);
}

/// Python `_varsayilan_ayarlar`: her alanin varsayilani.
pub(super) fn varsayilan_ayarlar(manifest: &Json) -> JsonMap {
    manifest["ayar_semasi"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|a| Some((a["anahtar"].as_str()?.to_string(), a["varsayilan"].clone())))
        .collect()
}

/// Guncellemede kullanici ayarlari korunur; yeni alanlar varsayilanla gelir.
pub(super) fn ayarlari_tasi(eski: &JsonMap, manifest: &Json) -> JsonMap {
    let mut yeni = varsayilan_ayarlar(manifest);
    for (anahtar, deger) in eski {
        if let Some(hedef) = yeni.get_mut(anahtar) {
            *hedef = deger.clone();
        }
    }
    yeni
}

/// Python `_ayarlari_dogrula`: gecersiz tek alan HICBIR alani yazmaz (atomik).
pub fn ayarlari_dogrula(
    sema: &[Json],
    gelen: &JsonMap,
    mevcut: &JsonMap,
) -> Result<JsonMap, EklentiHatasi> {
    let mut cikti = mevcut.clone();
    for alan in sema {
        let anahtar = alan["anahtar"].as_str().unwrap_or("").to_string();
        let etiket = str_veya(alan.get("etiket"), &anahtar);
        let Some(deger) = gelen.get(&anahtar) else {
            if !cikti.contains_key(&anahtar) {
                cikti.insert(anahtar, alan["varsayilan"].clone());
            }
            continue;
        };
        match alan["tur"].as_str().unwrap_or("metin") {
            "anahtar" => {
                let b = match deger {
                    Json::String(s) => {
                        matches!(s.trim().to_lowercase().as_str(), "1" | "true" | "evet")
                    }
                    _ => truthy(deger),
                };
                cikti.insert(anahtar, json!(b));
            }
            "sayi" => {
                let sayi = py_float_of(deger).ok_or_else(|| {
                    EklentiHatasi::new("AYAR_TUR", format!("{etiket}: sayi bekleniyor"))
                })?;
                if let Some(en_az) = alan.get("en_az").and_then(Json::as_f64) {
                    if sayi < en_az {
                        return Err(EklentiHatasi::new(
                            "AYAR_ARALIK",
                            format!("{etiket}: en az {}", py_str(&alan["en_az"])),
                        ));
                    }
                }
                if let Some(en_cok) = alan.get("en_cok").and_then(Json::as_f64) {
                    if sayi > en_cok {
                        return Err(EklentiHatasi::new(
                            "AYAR_ARALIK",
                            format!("{etiket}: en cok {}", py_str(&alan["en_cok"])),
                        ));
                    }
                }
                let deger = if sayi.is_finite() && sayi.fract() == 0.0 {
                    json!(sayi as i64)
                } else {
                    json!(sayi)
                };
                cikti.insert(anahtar, deger);
            }
            "secim" => {
                let metin = py_str(deger);
                let secenekler = alan["secenekler"].as_array().cloned().unwrap_or_default();
                if !secenekler.iter().any(|s| py_esit(s, &json!(metin))) {
                    return Err(EklentiHatasi::new(
                        "AYAR_SECIM",
                        format!("{etiket}: gecersiz secenek"),
                    ));
                }
                cikti.insert(anahtar, json!(metin));
            }
            _ => {
                let metin = py_str(deger);
                if metin.chars().count() > 2000 {
                    return Err(EklentiHatasi::new(
                        "AYAR_UZUN",
                        format!("{etiket}: en cok 2000 karakter"),
                    ));
                }
                cikti.insert(anahtar, json!(metin));
            }
        }
    }
    Ok(cikti)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn gecerli() -> Json {
        json!({"ad": "Test-Eklenti", "surum": "1.0.0", "giris": "main.py",
               "izinler": ["dosya_oku", "dosya_oku"], "domainler": ["*.ornek.com", "ORNEK.com"],
               "ayar_semasi": [{"anahtar": "boyut", "tur": "sayi", "varsayilan": 3, "en_az": 1, "en_cok": 9}]})
    }

    #[test]
    fn manifest_normallestirir() {
        let m = manifest_dogrula(&gecerli()).expect("gecerli");
        assert_eq!(m["ad"], "test-eklenti");
        assert_eq!(m["baslik"], "test-eklenti");
        assert_eq!(m["izinler"], json!(["dosya_oku"]));
        assert_eq!(m["domainler"], json!(["*.ornek.com", "ornek.com"]));
        assert_eq!(m["ayar_semasi"][0]["uygulama"], "hemen");
    }

    #[test]
    fn manifest_hatalari() {
        assert_eq!(
            manifest_dogrula(&json!({"surum": "1", "giris": "a.py"}))
                .unwrap_err()
                .kod,
            "MANIFEST_EKSIK"
        );
        let mut k = gecerli();
        k["giris"] = json!("../x.py");
        assert_eq!(manifest_dogrula(&k).unwrap_err().kod, "MANIFEST_GIRIS");
        let mut k = gecerli();
        k["domainler"] = json!(["bad domain!"]);
        assert_eq!(manifest_dogrula(&k).unwrap_err().kod, "MANIFEST_DOMAIN");
        let mut k = gecerli();
        k["ayar_semasi"] = json!([{"anahtar": "x", "tur": "secim", "secenekler": []}]);
        assert_eq!(manifest_dogrula(&k).unwrap_err().kod, "MANIFEST_ALAN");
    }

    #[test]
    fn surum_karsilastirma() {
        assert!(surum_uyumlu("1.0.0", "", Some("1.2")));
        assert!(!surum_uyumlu("3.0", "", Some("2.9.6")));
        assert!(!surum_uyumlu("", "2.0", Some("2.9.6")));
        assert!(surum_uyumlu("", "", None));
    }

    #[test]
    fn ayar_dogrulama_atomik() {
        let sema = manifest_dogrula(&gecerli()).unwrap()["ayar_semasi"]
            .as_array()
            .unwrap()
            .clone();
        let mevcut = JsonMap::new();
        let ok = ayarlari_dogrula(
            &sema,
            &json!({"boyut": "5"}).as_object().unwrap().clone(),
            &mevcut,
        )
        .unwrap();
        assert_eq!(ok["boyut"], json!(5));
        let hata = ayarlari_dogrula(
            &sema,
            &json!({"boyut": 99}).as_object().unwrap().clone(),
            &mevcut,
        )
        .unwrap_err();
        assert_eq!(hata.kod, "AYAR_ARALIK");
        assert_eq!(hata.mesaj, "boyut: en cok 9.0");
    }

    fn zip_yaz(yol: &Path, uyeler: &[(&str, &[u8])]) {
        let file = File::create(yol).expect("zip olusmali");
        let mut w = zip::ZipWriter::new(file);
        for (ad, icerik) in uyeler {
            w.start_file(*ad, zip::write::SimpleFileOptions::default())
                .unwrap();
            w.write_all(icerik).unwrap();
        }
        w.finish().unwrap();
    }

    fn tmp(ad: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let d = std::env::temp_dir().join(format!("afudm-g2-{ad}-{}-{nanos}", std::process::id()));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn paket_incele_ve_ozet() {
        let d = tmp("eklenti-incele");
        let yol = d.join("p.afup");
        let manifest = br#"{"ad":"test-vaka1","surum":"1.0.0","giris":"main.py","afudm_min":"1.0.0","izinler":["dosya_oku"],"domainler":["*.ornek.com"]}"#;
        zip_yaz(
            &yol,
            &[("eklenti.json", manifest), ("main.py", b"print('ok')")],
        );
        let m = paket_incele(yol.to_str().unwrap(), 200, 100.0).expect("incelenmeli");
        assert_eq!(m["ad"], "test-vaka1");
        assert_eq!(m["dosya_sayisi"], 2);
        assert_eq!(m["guven_modeli"], "guvenilen_eklenti");
        let ozet = paket_sha256(&yol).unwrap();
        assert_eq!(ozet.len(), 64);
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn zip_slip_reddedilir() {
        let d = tmp("eklenti-slip");
        let yol = d.join("p.afup");
        zip_yaz(&yol, &[("eklenti.json", b"{}"), ("../disari.txt", b"x")]);
        let hata = paket_incele(yol.to_str().unwrap(), 200, 100.0).unwrap_err();
        assert_eq!(hata.kod, "PAKET_GUVENSIZ");
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn uzanti_ve_manifest_yok() {
        let d = tmp("eklenti-uzanti");
        let yol = d.join("p.zip");
        zip_yaz(&yol, &[("eklenti.json", b"{}")]);
        assert_eq!(
            paket_incele(yol.to_str().unwrap(), 200, 100.0)
                .unwrap_err()
                .kod,
            "PAKET_TUR"
        );
        let _ = std::fs::remove_dir_all(&d);
    }
}
