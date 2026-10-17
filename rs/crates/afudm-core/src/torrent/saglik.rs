//! SAHIBI: Ekip D. Python: core/tracker_saglik.py (352 satir).
//! Seed listesi klasorunu (trackers/) okur, her tracker'a UDP (BEP 15) ya da HTTP scrape ile sorar,
//! canli olanlari ve torrenti taniyanlari one alir.

use super::bencode::{self, Bc};
use super::trackers;
use afudm_types::{AfuError, Json, Result, Store};
use serde_json::json;
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::{self, ErrorKind};
use std::net::{ToSocketAddrs, UdpSocket};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const MAGIC: u64 = 0x0417_2710_1980;
pub const ZAMAN_ASIMI: Duration = Duration::from_secs(4);
pub const ISCI: usize = 40;
/// Python TAZELIK = 24 saat.
pub const TAZELIK_SN: f64 = 24.0 * 3600.0;
const BENI_OKU_AD: &str = "BENI_OKU.txt";
const BENI_OKU_METIN: &str = concat!(
    "Buraya istediğin kadar tracker listesi (.txt) atabilirsin.\n",
    "Her satırda bir adres olsun:\n",
    "    udp://tracker.ornek.org:1337/announce\n",
    "    http://izleyici.ornek.com/announce\n\n",
    "AfuDM bu klasördeki bütün dosyaları okur, tekrarları atar ve\n",
    "her adrese gerçekten sorar. Cevap vermeyen (ölü) tracker'lar\n",
    "kullanılmaz — ama silinmez, bir dahaki taramada yine denenir.\n\n",
    "Not: tracker eklemek seed SAYISINI artırmaz; var olan seed'leri\n",
    "daha hızlı bulmanı sağlar.\n",
);

/// Python tara() sonucu. `sayilar` = {toplam, canli, olu, tanyan}.
pub struct TaraSonucu {
    pub canli: Vec<String>,
    pub sayilar: serde_json::Map<String, Json>,
    pub zaman: f64,
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn dosya_adi(yol: &Path) -> String {
    yol.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default()
}

/// Python Path.suffix.lower().
fn uzanti_kucuk(ad: &str) -> String {
    match ad.rfind('.') {
        Some(i) if i > 0 && i < ad.len() - 1 => ad[i..].to_ascii_lowercase(),
        _ => String::new(),
    }
}

fn metin_oku(yol: &Path) -> io::Result<String> {
    Ok(String::from_utf8_lossy(&fs::read(yol)?).into_owned())
}

/// Python klasoru_hazirla: klasor + BENI_OKU.txt (hatalar yutulur).
pub fn klasoru_hazirla(klasor: &Path) {
    if fs::create_dir_all(klasor).is_err() {
        return;
    }
    let okuma = klasor.join(BENI_OKU_AD);
    if !okuma.exists() {
        let _ = fs::write(&okuma, BENI_OKU_METIN);
    }
}

/// Klasordeki .txt listeleri (BENI_OKU haric), ada gore sirali.
fn txt_dosyalari(klasor: &Path) -> Vec<PathBuf> {
    if !klasor.is_dir() {
        return Vec::new();
    }
    let Ok(girdiler) = fs::read_dir(klasor) else { return Vec::new() };
    let mut liste: Vec<PathBuf> = girdiler
        .filter_map(|g| g.ok().map(|g| g.path()))
        .filter(|p| p.is_file())
        .filter(|p| {
            let ad = dosya_adi(p);
            ad.to_ascii_lowercase().ends_with(".txt") && ad != BENI_OKU_AD
        })
        .collect();
    liste.sort_by_key(|p| dosya_adi(p));
    liste
}

/// Python klasorden_oku: butun listeler birlestirilir, tekrarsiz.
pub fn klasorden_oku(klasor: &Path) -> Vec<String> {
    let mut toplam: Vec<String> = Vec::new();
    for dosya in txt_dosyalari(klasor) {
        let Ok(metin) = metin_oku(&dosya) else { continue };
        for adres in trackers::ayikla(&metin) {
            if !toplam.contains(&adres) {
                toplam.push(adres);
            }
        }
    }
    toplam
}

/// Python dosyalar(): [{ad, sayi}] listesi.
pub fn dosyalar(klasor: &Path) -> Vec<Json> {
    klasoru_hazirla(klasor);
    let mut liste = Vec::new();
    for dosya in txt_dosyalari(klasor) {
        let Ok(metin) = metin_oku(&dosya) else { continue };
        liste.push(json!({"ad": dosya_adi(&dosya), "sayi": trackers::ayikla(&metin).len()}));
    }
    liste
}

/// Python _bos_ad: cakisan adi seed.txt -> seed-2.txt -> seed-3.txt diye kaydirir.
fn bos_ad(klasor: &Path, ad: &str) -> Result<PathBuf> {
    let hedef = klasor.join(ad);
    if !hedef.exists() {
        return Ok(hedef);
    }
    let (govde, uzanti) = match ad.rfind('.') {
        Some(i) => (&ad[..i], &ad[i + 1..]),
        None => ("", ad),
    };
    for sira in 2..1000 {
        let aday = klasor.join(format!("{govde}-{sira}.{uzanti}"));
        if !aday.exists() {
            return Ok(aday);
        }
    }
    Err(AfuError::Invalid("cok fazla ayni adli liste var".to_string()))
}

/// Python dosya_ekle: secilen .txt'yi klasore kopyalar (icerik ayiklanmis yazilir).
pub fn dosya_ekle(klasor: &Path, yol: &str) -> Result<Json> {
    let kaynak = Path::new(yol);
    let kaynak_adi = dosya_adi(kaynak);
    if uzanti_kucuk(&kaynak_adi) != ".txt" {
        return Err(AfuError::Invalid("yalniz .txt liste dosyasi eklenebilir".to_string()));
    }
    if !kaynak.is_file() {
        return Err(AfuError::Invalid("dosya bulunamadi".to_string()));
    }
    let metin = metin_oku(kaynak).map_err(|e| AfuError::Invalid(format!("dosya okunamadi: {e}")))?;
    let adresler = trackers::ayikla(&metin);
    if adresler.is_empty() {
        return Err(AfuError::Invalid("dosyada tracker adresi yok".to_string()));
    }

    klasoru_hazirla(klasor);
    let yeni: HashSet<&String> = adresler.iter().collect();
    for var_olan in txt_dosyalari(klasor) {
        let Ok(eski) = metin_oku(&var_olan) else { continue };
        let eski_kume: HashSet<String> = trackers::ayikla(&eski).into_iter().collect();
        if eski_kume.iter().collect::<HashSet<_>>() == yeni {
            return Ok(json!({"ad": dosya_adi(&var_olan), "sayi": adresler.len(), "zaten": true}));
        }
    }

    let hedef = bos_ad(klasor, &kaynak_adi)?;
    let icerik = adresler.join("\n") + "\n";
    fs::write(&hedef, icerik).map_err(|e| AfuError::Invalid(format!("dosya yazilamadi: {e}")))?;
    Ok(json!({"ad": dosya_adi(&hedef), "sayi": adresler.len(), "zaten": false}))
}

/// Python dosya_sil: yalniz klasorun icindeki .txt listeleri; yol kacisina izin yok.
pub fn dosya_sil(klasor: &Path, ad: &str) -> Result<Json> {
    let temel = ad.rsplit(['/', '\\']).next().unwrap_or(ad);
    if ad.is_empty() || temel != ad || ad.to_ascii_lowercase().ends_with(".exe") {
        return Err(AfuError::Invalid("gecersiz dosya adi".to_string()));
    }
    if !ad.to_ascii_lowercase().ends_with(".txt") {
        return Err(AfuError::Invalid("yalniz .txt liste dosyasi silinebilir".to_string()));
    }
    if ad == BENI_OKU_AD {
        return Err(AfuError::Invalid("aciklama dosyasi silinemez".to_string()));
    }
    let hedef = klasor.join(ad);
    if !hedef.is_file() {
        return Err(AfuError::Invalid("dosya bulunamadi".to_string()));
    }
    fs::remove_file(&hedef).map_err(|e| AfuError::Invalid(format!("dosya silinemedi: {e}")))?;
    Ok(json!({"ad": ad}))
}

/// Yuzde-kodlama (Python urllib.parse.quote(bytes), safe='/').
fn yuzdelik_kodla(bayt: &[u8]) -> String {
    let mut s = String::new();
    for &b in bayt {
        if b.is_ascii_alphanumeric() || b"_.-~/".contains(&b) {
            s.push(b as char);
        } else {
            s.push_str(&format!("%{b:02X}"));
        }
    }
    s
}

/// Hex metni bayta cevirir (Python bytes.fromhex, bosluksuz).
fn hex_coz(metin: &str) -> std::result::Result<Vec<u8>, ()> {
    if !metin.len().is_multiple_of(2) {
        return Err(());
    }
    (0..metin.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&metin[i..i + 2], 16).map_err(|_| ()))
        .collect()
}

/// udp://host:port/... -> (host kucuk harf, port). Port yoksa ya da 0 ise None (Python: hata).
fn host_port(adres: &str) -> Option<(String, u16)> {
    let (_, sonrasi) = adres.split_once("://")?;
    let ag = sonrasi.split(['/', '?', '#']).next()?;
    let ag = ag.rsplit('@').next()?;
    let (host, port_metin) = match ag.strip_prefix('[') {
        Some(r) => {
            let (h, k) = r.split_once(']')?;
            (h, k.strip_prefix(':')?)
        }
        None => ag.rsplit_once(':')?,
    };
    let port: u16 = port_metin.parse().ok()?;
    if host.is_empty() || port == 0 {
        return None;
    }
    Some((host.to_ascii_lowercase(), port))
}

/// Python _udp_scrape (BEP 15): connect -> scrape. Donen: (durum, seed, leech).
fn udp_sor(adres: &str, info_hash: &str) -> (&'static str, i64, i64) {
    let Some((host, port)) = host_port(adres) else { return ("hata", 0, 0) };
    match udp_dene(&host, port, info_hash) {
        Ok(sonuc) => sonuc,
        Err(e) if matches!(e.kind(), ErrorKind::TimedOut | ErrorKind::WouldBlock) => ("sessiz", 0, 0),
        Err(_) => ("hata", 0, 0),
    }
}

fn udp_dene(host: &str, port: u16, info_hash: &str) -> io::Result<(&'static str, i64, i64)> {
    let hedef = (host, port).to_socket_addrs()?.find(|a| a.is_ipv4());
    let Some(hedef) = hedef else {
        return Err(io::Error::other("IPv4 adresi yok"));
    };
    let soket = UdpSocket::bind("0.0.0.0:0")?;
    soket.set_read_timeout(Some(ZAMAN_ASIMI))?;

    let islem = rand::random::<u32>() & 0x7fff_ffff;
    let mut paket = Vec::with_capacity(16);
    paket.extend_from_slice(&MAGIC.to_be_bytes());
    paket.extend_from_slice(&0u32.to_be_bytes());
    paket.extend_from_slice(&islem.to_be_bytes());
    soket.send_to(&paket, hedef)?;

    let mut t = [0u8; 64];
    let (n, _) = soket.recv_from(&mut t)?;
    if n < 16 {
        return Ok(("hata", 0, 0));
    }
    let eylem = u32::from_be_bytes([t[0], t[1], t[2], t[3]]);
    let donen = u32::from_be_bytes([t[4], t[5], t[6], t[7]]);
    let mut baglanti_b = [0u8; 8];
    baglanti_b.copy_from_slice(&t[8..16]);
    let baglanti = u64::from_be_bytes(baglanti_b);
    if eylem != 0 || donen != islem {
        return Ok(("hata", 0, 0));
    }
    if info_hash.is_empty() {
        return Ok(("canli", 0, 0));
    }
    let Ok(hash) = hex_coz(info_hash) else { return Ok(("hata", 0, 0)) };

    let islem2 = rand::random::<u32>() & 0x7fff_ffff;
    let mut paket2 = Vec::with_capacity(36 + hash.len());
    paket2.extend_from_slice(&baglanti.to_be_bytes());
    paket2.extend_from_slice(&2u32.to_be_bytes());
    paket2.extend_from_slice(&islem2.to_be_bytes());
    paket2.extend_from_slice(&hash);
    soket.send_to(&paket2, hedef)?;

    let mut t2 = [0u8; 256];
    let (n2, _) = soket.recv_from(&mut t2)?;
    if n2 < 20 {
        return Ok(("canli", 0, 0));
    }
    let eylem2 = u32::from_be_bytes([t2[0], t2[1], t2[2], t2[3]]);
    if eylem2 != 2 {
        return Ok(("canli", 0, 0));
    }
    let seed = u32::from_be_bytes([t2[8], t2[9], t2[10], t2[11]]);
    let leech = u32::from_be_bytes([t2[16], t2[17], t2[18], t2[19]]);
    Ok(("canli", i64::from(seed), i64::from(leech)))
}

/// Python _http_scrape: /announce -> /scrape, bencode yaniti.
fn http_sor(adres: &str, info_hash: &str) -> (&'static str, i64, i64) {
    let mut hedef = adres.replace("/announce", "/scrape");
    if !info_hash.is_empty() {
        let ham = match hex_coz(info_hash) {
            Ok(bayt) => yuzdelik_kodla(&bayt),
            Err(_) => String::new(),
        };
        hedef.push_str(if hedef.contains('?') { "&" } else { "?" });
        hedef.push_str("info_hash=");
        hedef.push_str(&ham);
    }
    let Ok(govde) = trackers::indir(&hedef, "AfuDM/1.2", ZAMAN_ASIMI, 4096) else {
        return ("sessiz", 0, 0);
    };
    let Ok(cevap) = bencode::coz(&govde) else { return ("hata", 0, 0) };
    let Bc::Sozluk(sozluk) = cevap else { return ("hata", 0, 0) };
    if sozluk.contains_key(&b"failure reason"[..]) {
        return ("hata", 0, 0);
    }
    let dosyalar: BTreeMap<Vec<u8>, Bc> = match sozluk.get(&b"files"[..]) {
        None => BTreeMap::new(),
        Some(Bc::Sozluk(m)) => m.clone(),
        Some(_) => return ("hata", 0, 0),
    };
    let kayit: BTreeMap<Vec<u8>, Bc> = if info_hash.is_empty() {
        BTreeMap::new()
    } else {
        let Ok(anahtar) = hex_coz(info_hash) else { return ("hata", 0, 0) };
        match dosyalar.get(&anahtar) {
            None => BTreeMap::new(),
            Some(Bc::Sozluk(k)) => k.clone(),
            Some(_) => return ("hata", 0, 0),
        }
    };
    let tamsayi = |anahtar: &[u8]| -> std::result::Result<i64, ()> {
        match kayit.get(anahtar) {
            None => Ok(0),
            Some(Bc::Tamsayi(v)) => Ok(*v),
            Some(_) => Err(()),
        }
    };
    let (Ok(seed), Ok(leech)) = (tamsayi(b"complete"), tamsayi(b"incomplete")) else {
        return ("hata", 0, 0);
    };
    if seed.min(leech) < 0 {
        return ("hata", 0, 0);
    }
    ("canli", seed, leech)
}

/// Python sor(): tek bir tracker'a sorar -> (durum, seed, leech).
pub fn sor(adres: &str, info_hash: &str) -> (&'static str, i64, i64) {
    if adres.starts_with("udp://") {
        udp_sor(adres, info_hash)
    } else if adres.starts_with("http://") || adres.starts_with("https://") {
        http_sor(adres, info_hash)
    } else {
        ("hata", 0, 0)
    }
}

/// Python tara(): butun listeyi paralel sorar, ozetler. Torrenti taniyanlar en basa.
pub fn tara(liste: &[String], info_hash: &str, isci: usize) -> TaraSonucu {
    let n = liste.len();
    let mut sonuclar: Vec<(&'static str, i64, i64)> = vec![("hata", 0, 0); n];
    if n > 0 {
        let sira = AtomicUsize::new(0);
        let isci_say = isci.max(1).min(n);
        std::thread::scope(|s| {
            let kollar: Vec<_> = (0..isci_say)
                .map(|_| {
                    s.spawn(|| {
                        let mut yerel = Vec::new();
                        loop {
                            let k = sira.fetch_add(1, Ordering::SeqCst);
                            if k >= n {
                                break;
                            }
                            yerel.push((k, sor(&liste[k], info_hash)));
                        }
                        yerel
                    })
                })
                .collect();
            for kol in kollar {
                if let Ok(parca) = kol.join() {
                    for (k, v) in parca {
                        sonuclar[k] = v;
                    }
                }
            }
        });
    }

    let mut canli: Vec<String> = Vec::new();
    let mut olu: Vec<String> = Vec::new();
    let mut tanyan: Vec<(String, i64, i64)> = Vec::new();
    for (adres, (durum, seed, leech)) in liste.iter().zip(sonuclar) {
        if durum == "canli" {
            canli.push(adres.clone());
            if seed != 0 || leech != 0 {
                tanyan.push((adres.clone(), seed, leech));
            }
        } else {
            olu.push(adres.clone());
        }
    }
    tanyan.sort_by(|a, b| b.1.cmp(&a.1).then(b.2.cmp(&a.2)));
    let onde: Vec<String> = tanyan.iter().map(|t| t.0.clone()).collect();
    let mut sirali = onde.clone();
    sirali.extend(canli.iter().filter(|a| !onde.contains(a)).cloned());

    let mut sayilar = serde_json::Map::new();
    sayilar.insert("toplam".into(), json!(n));
    sayilar.insert("canli".into(), json!(canli.len()));
    sayilar.insert("olu".into(), json!(olu.len()));
    sayilar.insert("tanyan".into(), json!(tanyan.len()));
    TaraSonucu {
        canli: sirali,
        sayilar,
        zaman: simdi(),
    }
}

/// Python tazele(): klasoru oku, (elle eklenenlerle birlikte) tara, sonucu store'a yaz.
pub fn tazele(store: &dyn Store, klasor: &Path, info_hash: &str) -> Result<TaraSonucu> {
    klasoru_hazirla(klasor);
    let mut liste = klasorden_oku(klasor);
    let elle = match store.get("ek_trackerlar")? {
        Some(Json::String(s)) => s,
        _ => String::new(),
    };
    for adres in trackers::ayikla(&elle) {
        if !liste.contains(&adres) {
            liste.push(adres);
        }
    }
    let sonuc = tara(&liste, info_hash, ISCI);
    store.set("canli_trackerlar", Json::String(sonuc.canli.join("\n")))?;
    store.set("tracker_tarama_zamani", json!(sonuc.zaman))?;
    store.set("tracker_tarama_ozeti", Json::Object(sonuc.sayilar.clone()))?;
    let s = &sonuc.sayilar;
    store.log(
        "info",
        &format!(
            "tracker taramasi: {}/{} canli, {} tanesi torrenti taniyor",
            s["canli"], s["toplam"], s["tanyan"]
        ),
        "",
    );
    Ok(sonuc)
}

/// Python taze_mi(): son tarama 24 saatten yeni mi.
pub fn taze_mi(store: &dyn Store) -> bool {
    let zaman = match store.get("tracker_tarama_zamani") {
        Ok(None) | Ok(Some(Json::Null)) | Ok(Some(Json::Bool(false))) => 0.0,
        Ok(Some(Json::Number(n))) => n.as_f64().unwrap_or(0.0),
        Ok(Some(Json::String(s))) if s.is_empty() => 0.0,
        Ok(Some(Json::String(s))) => match s.parse::<f64>() {
            Ok(v) => v,
            Err(_) => return false,
        },
        _ => return false,
    };
    simdi() - zaman < TAZELIK_SN
}

#[cfg(test)]
mod testler {
    use super::*;

    fn gecici_klasor(ad: &str) -> PathBuf {
        let yol = std::env::temp_dir().join(format!("afudm_d_{}_{}", ad, std::process::id()));
        let _ = fs::remove_dir_all(&yol);
        fs::create_dir_all(&yol).expect("gecici klasor");
        yol
    }

    #[test]
    fn dosya_ekle_bos_listeyi_reddeder() {
        let k = gecici_klasor("bos");
        let kaynak = k.join("liste.txt");
        fs::write(&kaynak, "merhaba\n").expect("yaz");
        let hata = dosya_ekle(&k, kaynak.to_str().expect("yol")).expect_err("reddedilmeli");
        assert_eq!(hata.to_string(), "dosyada tracker adresi yok");
    }

    #[test]
    fn dosya_ekle_ayni_kumeyi_zaten_olarak_bildirir() {
        let k = gecici_klasor("zaten");
        let kaynak_klasor = gecici_klasor("zaten_kaynak");
        let kaynak = kaynak_klasor.join("liste.txt");
        fs::write(&kaynak, "udp://ok.example.org:1/a\n").expect("yaz");
        let ilk = dosya_ekle(&k, kaynak.to_str().expect("yol")).expect("ilk ekleme");
        assert_eq!(ilk["zaten"], json!(false));
        let ikinci = dosya_ekle(&k, kaynak.to_str().expect("yol")).expect("ikinci ekleme");
        assert_eq!(ikinci["zaten"], json!(true));
    }

    #[test]
    fn dosya_sil_yol_kacisini_reddeder() {
        let k = gecici_klasor("sil");
        let hata = dosya_sil(&k, "../x.txt").expect_err("reddedilmeli");
        assert_eq!(hata.to_string(), "gecersiz dosya adi");
        let hata = dosya_sil(&k, "BENI_OKU.txt").expect_err("reddedilmeli");
        assert_eq!(hata.to_string(), "aciklama dosyasi silinemez");
    }

    #[test]
    fn host_port_ayrisir() {
        assert_eq!(host_port("udp://Tracker.Example.org:1337/announce"), Some(("tracker.example.org".into(), 1337)));
        assert_eq!(host_port("udp://host/announce"), None);
    }

    #[test]
    fn tara_bos_liste_sifir_sayar() {
        let sonuc = tara(&[], "", ISCI);
        assert!(sonuc.canli.is_empty());
        assert_eq!(sonuc.sayilar["toplam"], json!(0));
    }
}
