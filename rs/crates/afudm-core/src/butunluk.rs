//! SAHIBI: Ekip G1 (butunluk). Python karsiligi: core/butunluk.py (tarama, aria2 kontrol dosyasi,
//! blok indirme) + core/manager.py butunluk_tara / butunluk_onar / _repair_thread / butunluk_hepsini_tara.
//! Imzalar afudm-types::ManagerApi ile sabit.

use crate::{queue, Manager};
use afudm_types::{AfuError, Json, JsonMap, ManagerApi, Result, Store};
use serde_json::{json, Value};
use std::fs;
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

/// Python: butunluk.BLOCK_SIZE
pub const BLOCK_SIZE: u64 = 4 * 1024 * 1024;
const HTML_IZINLI_UZANTILAR: [&str; 4] = [".html", ".htm", ".xml", ".json"];

/// Ekip G1 kendi calisma durumunu buraya koyar (Manager::butunluk_state).
#[derive(Default)]
pub struct State {}

pub fn butunluk_tara(m: &Manager, gid: &str) -> Result<Json> {
    let Some(row) = m.store.by_gid(gid)? else {
        return Ok(json!({"ok": false, "durum": "bulunamadi", "neden": "Kayıt bulunamadı."}));
    };
    let yol = indirme_yolu(m, gid, &row)?;
    if !yol.exists() {
        return Ok(
            json!({"ok": false, "durum": "bulunamadi", "neden": "Dosya diskte bulunamadı."}),
        );
    }
    let sonuc = tara(&yol, row.get("size"));
    if sonuc["durum"] != "saglam" {
        if let Some(id) = row["id"].as_i64() {
            m.store
                .update_by_id(id, &alan(&[("error", sonuc["neden"].clone())]))?;
        }
    }
    let mut cikti = JsonMap::new();
    cikti.insert("ok".into(), json!(true));
    if let Some(o) = sonuc.as_object() {
        for (k, v) in o {
            cikti.insert(k.clone(), v.clone());
        }
    }
    Ok(Value::Object(cikti))
}

pub fn butunluk_onar(m: &Manager, gid: &str, yeni_url: &str) -> Result<Json> {
    let Some(row) = m.store.by_gid(gid)? else {
        return Ok(json!({"ok": false, "neden": "Kayıt bulunamadı."}));
    };
    let yol = match queue::resolve_item_path(m, gid) {
        Ok(Some(p)) if p.exists() => p,
        _ => return Ok(json!({"ok": false, "neden": "Dosya bulunamadı."})),
    };
    let yerel = fs::metadata(&yol)?.len();
    let mut opts = opts_oku(&row);
    if let Err(neden) = head_kontrol(yeni_url, &basliklar_oku(&opts), yerel) {
        return Ok(json!({"ok": false, "neden": neden}));
    }

    // Kayitli onarim varsa kaldigi yerden; yoksa yeni tarama.
    let mevcut = opts
        .get("repair_state")
        .cloned()
        .unwrap_or_else(|| json!({}));
    let devam = mevcut["yeni_url"].as_str() == Some(yeni_url)
        && mevcut["bozuk_bloklar"]
            .as_array()
            .is_some_and(|a| !a.is_empty());
    let rep = if devam {
        mevcut
    } else {
        let tarama = tara(&yol, Some(&json!(yerel)));
        if tarama["durum"] != "bozuk" {
            return Ok(json!({"ok": false, "neden": "Dosya sağlam, onarıma gerek yok."}));
        }
        json!({
            "bozuk_bloklar": tarama.get("bozuk_bloklar").cloned().unwrap_or_else(|| json!([])),
            "toplam_blok": tarama.get("toplam_blok").cloned().unwrap_or_else(|| json!(0)),
            "duzeltilen": 0,
            "yeni_url": yeni_url,
            "hata": "",
        })
    };
    opts["repair_state"] = rep;
    m.store.update_by_gid(
        gid,
        &alan(&[
            ("options", json!(opts.to_string())),
            ("status", json!("repairing")),
        ]),
    )?;

    let store = Arc::clone(&m.store);
    let gid_s = gid.to_string();
    std::thread::spawn(move || onarim_iscisi(store, &gid_s, &yol));
    Ok(json!({"ok": true, "durum": "Onarım başlatıldı."}))
}

pub fn butunluk_hepsini_tara(m: &Manager) -> Result<Json> {
    let satirlar = m.store.list(None, i64::MAX as usize)?;
    let mut sonuclar = JsonMap::new();
    let mut taranan = 0u64;
    for row in &satirlar {
        if row["status"] != "complete"
            || !matches!(row["kind"].as_str(), Some("http") | Some("ftp"))
        {
            continue;
        }
        taranan += 1;
        if let Some(gid) = row["gid"].as_str().filter(|g| !g.is_empty()) {
            let sonuc = butunluk_tara(m, gid)
                .unwrap_or_else(|e| json!({"ok": false, "neden": e.to_string()}));
            sonuclar.insert(gid.to_string(), sonuc);
        }
    }
    Ok(json!({"ok": true, "sonuclar": sonuclar, "taranan": taranan}))
}

/// Python: butunluk.tara. Donus: {durum: saglam|eksik|bozuk|bulunamadi, neden, ...}.
pub fn tara(yol: &Path, beklenen_boyut: Option<&Json>) -> Json {
    if !yol.exists() {
        return json!({"durum": "bulunamadi", "neden": "Dosya diskte bulunamadı."});
    }
    let aria2 = aria2_yolu(yol);
    let aria2_var = aria2.exists() && !aria2_kontrol_tam_mi(&aria2);

    let gercek = match fs::metadata(yol) {
        Ok(m) => m.len(),
        Err(e) => return json!({"durum": "eksik", "neden": format!("Dosya okunamadı: {e}")}),
    };
    if let Some(b) = beklenen_boyut.and_then(tamsayi_al) {
        if b > 0 && gercek as i64 != b {
            return json!({"durum": "eksik", "neden": format!("Boyut uyuşmuyor (Beklenen: {b}, Gerçek: {gercek}).")});
        }
    }
    let uzanti = yol
        .extension()
        .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
        .unwrap_or_default();
    if gercek == 0 {
        return json!({"durum": "eksik", "neden": "Dosya boyutu 0 bayt."});
    }

    let toplam_blok = gercek.div_ceil(BLOCK_SIZE);
    let mut file = match fs::File::open(yol) {
        Ok(f) => f,
        Err(e) => return json!({"durum": "eksik", "neden": format!("Dosya okunamadı: {e}")}),
    };
    let bozuk = match bloklari_tara(&mut file, &uzanti, toplam_blok) {
        Ok(b) => b,
        Err(e) => return json!({"durum": "eksik", "neden": format!("Dosya okunamadı: {e}")}),
    };
    if !bozuk.is_empty() {
        let html = bozuk.iter().any(|b| b.sebep == "HTML");
        let imza = bozuk.iter().any(|b| b.sebep == "imza yok");
        let ek = if html {
            " (HTML içeriyor)"
        } else if imza {
            " (imza yok)"
        } else {
            ""
        };
        let liste: Vec<Json> = bozuk
            .iter()
            .map(|b| json!({"offset": b.offset, "boyut": b.boyut, "index": b.index, "sebep": b.sebep}))
            .collect();
        return json!({
            "durum": "bozuk",
            "neden": format!("{} blok bozuk bulundu.{ek}", bozuk.len()),
            "bozuk_bloklar": liste,
            "toplam_blok": toplam_blok,
            "bozuk_sayisi": bozuk.len(),
        });
    }
    if aria2_var {
        return json!({"durum": "eksik", "neden": "İndirme tamamlanmamış (.aria2 dosyası duruyor)."});
    }
    json!({"durum": "saglam", "neden": "Dosya sağlam görünüyor."})
}

struct Bozuk {
    offset: u64,
    boyut: usize,
    index: u64,
    sebep: &'static str,
}

fn bloklari_tara(f: &mut fs::File, uzanti: &str, toplam: u64) -> std::io::Result<Vec<Bozuk>> {
    let mut bozuk = Vec::new();
    let mut buf = vec![0u8; BLOCK_SIZE as usize];
    for i in 0..toplam {
        let offset = i * BLOCK_SIZE;
        f.seek(SeekFrom::Start(offset))?;
        let mut n = 0;
        while n < buf.len() {
            let k = f.read(&mut buf[n..])?;
            if k == 0 {
                break;
            }
            n += k;
        }
        if n == 0 {
            break;
        }
        if let Some(sebep) = blok_sebebi(&buf[..n], i, uzanti) {
            bozuk.push(Bozuk {
                offset,
                boyut: n,
                index: i,
                sebep,
            });
        }
    }
    Ok(bozuk)
}

/// Python'daki if/elif zincirinin birebir karsiligi: imza kontrolunun sebebini
/// HTML/JSON kontrolu ezebilir (Python'da da ayni sira).
fn blok_sebebi(block: &[u8], i: u64, uzanti: &str) -> Option<&'static str> {
    if block.iter().all(|&b| b == 0) {
        return Some("sıfır");
    }
    let mut sebep = None;
    if i == 0 {
        if let Some(beklenen) = sihirli_bayt(uzanti) {
            if !block.starts_with(beklenen) {
                sebep = Some("imza yok");
            }
        }
    }
    if !HTML_IZINLI_UZANTILAR.contains(&uzanti) && metin_gibi(block) {
        let bas = String::from_utf8_lossy(&block[..block.len().min(4096)]);
        let s = bas.trim();
        let kucuk = s.to_lowercase();
        if kucuk.starts_with("<!doctype") || kucuk.starts_with("<html") || s.starts_with("<?xml") {
            sebep = Some("HTML");
        } else if s.starts_with('{') && s.ends_with('}') && s.len() < 4096 {
            if serde_json::from_str::<Value>(s).is_ok() {
                sebep = Some("JSON");
            }
        } else if s.starts_with('{') && s.contains('"') && s.contains(':') {
            sebep = Some("JSON");
        }
    }
    sebep
}

fn sihirli_bayt(uzanti: &str) -> Option<&'static [u8]> {
    match uzanti {
        ".rar" => Some(b"Rar!"),
        ".zip" => Some(b"PK"),
        ".7z" => Some(&[0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C]),
        ".pdf" => Some(b"%PDF"),
        ".exe" => Some(b"MZ"),
        _ => None,
    }
}

/// Python: butunluk._metin_gibi — bloğun ilk 4096 baytının %85'i okunur metin mi?
fn metin_gibi(bas: &[u8]) -> bool {
    let bas = &bas[..bas.len().min(4096)];
    if bas.is_empty() {
        return false;
    }
    let okunur = bas
        .iter()
        .filter(|&&b| matches!(b, 9 | 10 | 13) || (32..127).contains(&b))
        .count();
    okunur as f64 / bas.len() as f64 >= 0.85
}

/// Python: butunluk.aria2_kontrol_tam_mi — aria2 kontrol dosyasinda tum parcalar var mi?
/// Okunamayan ya da bozuk dosya icin false (indirme yarim sayilir).
pub fn aria2_kontrol_tam_mi(yol: &Path) -> bool {
    match fs::read(yol) {
        Ok(d) => ayristir_aria2(&d).unwrap_or(false),
        Err(_) => false,
    }
}

fn ayristir_aria2(d: &[u8]) -> Option<bool> {
    let mut o = 6usize;
    let kimlik = be_u32(d, o)? as usize;
    o = o.checked_add(4 + kimlik)?;
    let parca = be_u32(d, o)? as u128;
    let toplam = be_u64(d, o + 4)? as u128;
    o += 20; // parca(4) + toplam(8) + yuklenen(8)
    let bit_uzunlugu = be_u32(d, o)? as usize;
    o += 4;
    let bit = d.get(o..o.checked_add(bit_uzunlugu)?)?;
    if parca == 0 || toplam == 0 {
        return Some(false);
    }
    let parca_sayisi = toplam.div_ceil(parca);
    if (bit_uzunlugu as u128) * 8 < parca_sayisi {
        return Some(false);
    }
    let dolu: u128 = bit.iter().map(|b| b.count_ones() as u128).sum();
    Some(dolu >= parca_sayisi)
}

fn be_u32(d: &[u8], o: usize) -> Option<u32> {
    Some(u32::from_be_bytes(
        d.get(o..o.checked_add(4)?)?.try_into().ok()?,
    ))
}

fn be_u64(d: &[u8], o: usize) -> Option<u64> {
    Some(u64::from_be_bytes(
        d.get(o..o.checked_add(8)?)?.try_into().ok()?,
    ))
}

/// Python: butunluk.artik_kontrol_dosyasini_sil — indirme TAM gorunuyorsa .aria2 dosyasini siler.
pub fn artik_kontrol_dosyasini_sil(yol: &Path) -> bool {
    let aria2 = aria2_yolu(yol);
    if aria2.exists() && aria2_kontrol_tam_mi(&aria2) {
        return fs::remove_file(&aria2).is_ok();
    }
    false
}

/// Yeni linkten YALNIZ [offset, offset+boyut) araligini indirir (Python: butunluk.blok_indir).
/// Sunucu 206 donmezse, HTML ya da eksik veri gelirse hata doner; dosyaya hicbir sey yazilmaz.
pub fn blok_indir(
    url: &str,
    basliklar: &[(String, String)],
    offset: u64,
    boyut: u64,
) -> Result<Vec<u8>> {
    if boyut == 0 {
        return Err(AfuError::Other("Geçersiz blok boyutu".into()));
    }
    let mut istek = ureq::get(url);
    let mut ua_var = false;
    for (k, v) in basliklar {
        ua_var |= k.eq_ignore_ascii_case("user-agent");
        istek = istek.header(k.as_str(), v.as_str());
    }
    if !ua_var {
        istek = istek.header("User-Agent", "AfuDM");
    }
    let son = offset + boyut - 1;
    let mut yanit = istek
        .header("Range", format!("bytes={offset}-{son}"))
        .call()
        .map_err(|e| AfuError::Other(e.to_string()))?;
    if yanit.status().as_u16() != 206 {
        return Err(AfuError::Other(
            "Link kaldığı yerden indirmeyi desteklemiyor.".into(),
        ));
    }
    let mut veri = Vec::new();
    yanit
        .body_mut()
        .as_reader()
        .take(boyut + 1)
        .read_to_end(&mut veri)
        .map_err(|e| AfuError::Other(e.to_string()))?;
    if icerik_html_mi(&veri) {
        return Err(AfuError::Other(
            "Link geçersiz (hata sayfası döndü), yeni link ver.".into(),
        ));
    }
    if veri.len() as u64 != boyut {
        return Err(AfuError::Other(
            "Sunucu eksik veri verdi, tekrar denenecek.".into(),
        ));
    }
    Ok(veri)
}

fn icerik_html_mi(data: &[u8]) -> bool {
    let bas = String::from_utf8_lossy(&data[..data.len().min(4096)])
        .trim_start()
        .to_lowercase();
    bas.starts_with("<!doctype") || bas.starts_with("<html") || bas.starts_with("<?xml")
}

/// Python: manager._repair_thread. Arka planda, bozuk bloklari yeniden indirip yazar.
fn onarim_iscisi(store: Arc<dyn Store>, gid: &str, yol: &Path) {
    let Ok(Some(row)) = store.by_gid(gid) else {
        return;
    };
    let mut opts = opts_oku(&row);
    let mut rep = opts["repair_state"].clone();
    if rep.as_object().is_none_or(|o| o.is_empty()) || !yol.exists() {
        return;
    }
    let yeni_url = rep["yeni_url"].as_str().unwrap_or("").to_string();
    let basliklar = basliklar_oku(&opts);
    if let Err(hata) = onarim_isi(&store, gid, yol, &mut opts, &mut rep, &yeni_url, &basliklar) {
        if let Ok(Some(g)) = store.by_gid(gid) {
            if durum(&g) == "repairing" {
                rep["hata"] = json!(hata);
                opts["repair_state"] = rep;
                let _ = store.update_by_gid(
                    gid,
                    &alan(&[
                        ("options", json!(opts.to_string())),
                        ("status", json!("error")),
                        ("error", json!(format!("Onarım hatası: {hata}"))),
                    ]),
                );
            }
        }
    }
}

fn onarim_isi(
    store: &Arc<dyn Store>,
    gid: &str,
    yol: &Path,
    opts: &mut Json,
    rep: &mut Json,
    yeni_url: &str,
    basliklar: &[(String, String)],
) -> std::result::Result<(), String> {
    let hata = |e: &dyn std::fmt::Display| e.to_string();
    let mut bozuk: Vec<Json> = rep["bozuk_bloklar"].as_array().cloned().unwrap_or_default();
    {
        let mut dosya = fs::OpenOptions::new()
            .read(true)
            .write(true)
            .open(yol)
            .map_err(|e| hata(&e))?;
        while !bozuk.is_empty() {
            let guncel = store.by_gid(gid).map_err(|e| hata(&e))?;
            if guncel.as_ref().is_none_or(|g| durum(g) != "repairing") {
                break;
            }
            let blok = bozuk[0].clone();
            let start = blok["offset"].as_u64().unwrap_or(0);
            let boyut = blok["boyut"].as_u64().unwrap_or(0);
            let veri = blok_indir(yeni_url, basliklar, start, boyut).map_err(|e| hata(&e))?;
            dosya.seek(SeekFrom::Start(start)).map_err(|e| hata(&e))?;
            dosya.write_all(&veri).map_err(|e| hata(&e))?;
            bozuk.remove(0);
            rep["duzeltilen"] = json!(rep["duzeltilen"].as_u64().unwrap_or(0) + 1);
            rep["bozuk_bloklar"] = json!(bozuk);
            opts["repair_state"] = rep.clone();
            store
                .update_by_gid(gid, &alan(&[("options", json!(opts.to_string()))]))
                .map_err(|e| hata(&e))?;
        }
    }
    let guncel = store.by_gid(gid).map_err(|e| hata(&e))?;
    if guncel.as_ref().is_some_and(|g| durum(g) == "repairing") && bozuk.is_empty() {
        let boyut = fs::metadata(yol).map_err(|e| hata(&e))?.len();
        if tara(yol, Some(&json!(boyut)))["durum"] != "saglam" {
            return Err("Onarım sonrası tarama başarısız. Hala bozuk blok var.".into());
        }
        if let Some(o) = opts.as_object_mut() {
            o.remove("repair_state");
        }
        store
            .update_by_gid(
                gid,
                &alan(&[
                    ("options", json!(opts.to_string())),
                    ("status", json!("complete")),
                    ("error", Json::Null),
                ]),
            )
            .map_err(|e| hata(&e))?;
        let aria2 = aria2_yolu(yol);
        if aria2.exists() {
            let _ = fs::remove_file(&aria2);
        }
        let baslik = guncel
            .as_ref()
            .and_then(|g| g["title"].as_str())
            .unwrap_or("");
        store.log("info", &format!("Onarım tamamlandı: {baslik}"), gid);
    }
    Ok(())
}

/// Python: HEAD ile link kontrolu. Hatalar Python'daki metinlerle doner.
fn head_kontrol(
    url: &str,
    basliklar: &[(String, String)],
    yerel: u64,
) -> std::result::Result<(), String> {
    let mut istek = ureq::head(url);
    let mut ua_var = false;
    for (k, v) in basliklar {
        ua_var |= k.eq_ignore_ascii_case("user-agent");
        istek = istek.header(k.as_str(), v.as_str());
    }
    if !ua_var {
        istek = istek.header("User-Agent", "AfuDM");
    }
    let yanit = istek
        .call()
        .map_err(|e| format!("Link doğrulanamadı: {e}"))?;
    let tip = yanit
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .split(';')
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    if tip == "text/html" {
        return Err("Link geçersiz (HTML döndü), yeni link ver.".into());
    }
    if let Some(cl) = yanit
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
    {
        if !cl.is_empty() {
            let n: u64 = cl
                .trim()
                .parse()
                .map_err(|_| format!("Link doğrulanamadı: geçersiz Content-Length: {cl}"))?;
            if n != yerel {
                return Err(format!(
                    "Boyut uyuşmuyor. Beklenen: {yerel}, Linkteki: {cl}"
                ));
            }
        }
    }
    Ok(())
}

/// Indirme dosya yolu: once aria2/kayit (queue::resolve_item_path), yoksa dest_dir + title.
fn indirme_yolu(m: &Manager, gid: &str, row: &Json) -> Result<PathBuf> {
    if let Ok(Some(p)) = queue::resolve_item_path(m, gid) {
        return Ok(p);
    }
    let klasor = match row["dest_dir"].as_str().filter(|s| !s.is_empty()) {
        Some(k) => PathBuf::from(k),
        None => PathBuf::from(m.current_download_dir()?),
    };
    Ok(klasor.join(row["title"].as_str().unwrap_or("")))
}

fn aria2_yolu(yol: &Path) -> PathBuf {
    let mut s = yol.as_os_str().to_owned();
    s.push(".aria2");
    PathBuf::from(s)
}

fn alan(pairs: &[(&str, Json)]) -> JsonMap {
    pairs
        .iter()
        .map(|(k, v)| (k.to_string(), v.clone()))
        .collect()
}

fn durum(row: &Json) -> &str {
    row["status"].as_str().unwrap_or("")
}

/// Satirin `options` alani: Store nesne olarak doner; metin gelirse ayristirilir.
fn opts_oku(row: &Json) -> Json {
    match &row["options"] {
        v @ Value::Object(_) => v.clone(),
        Value::String(s) => match serde_json::from_str::<Value>(s) {
            Ok(v @ Value::Object(_)) => v,
            _ => json!({}),
        },
        _ => json!({}),
    }
}

/// Python: opts["header"] — "Ad: deger" bicimindeki basliklar.
fn basliklar_oku(opts: &Json) -> Vec<(String, String)> {
    opts["header"]
        .as_array()
        .map(|liste| {
            liste
                .iter()
                .filter_map(Value::as_str)
                .filter_map(|h| h.split_once(':'))
                .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn tamsayi_al(v: &Json) -> Option<i64> {
    match v {
        Value::Number(n) => n
            .as_i64()
            .or_else(|| n.as_f64().filter(|f| f.is_finite()).map(|f| f as i64)),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use afudm_types::{Aria2, NoUi};

    use std::net::TcpListener;
    use std::sync::Arc;

    /// Testte rpc gerekmez: her cagri hata doner (aria2 cevrimdisi gibi davranir).
    struct CevrimdisiRpc;
    impl Aria2 for CevrimdisiRpc {
        fn call(&self, _: &str, _: Vec<Json>) -> Result<Json> {
            Err(AfuError::Engine("test".into()))
        }
        fn alive(&self) -> bool {
            false
        }
        fn add_uri(&self, _: &[String], _: Option<&JsonMap>) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn add_torrent(&self, _: &str, _: Option<&JsonMap>) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn add_metalink(&self, _: &str, _: Option<&JsonMap>) -> Result<Vec<String>> {
            Err(AfuError::Engine("test".into()))
        }
        fn pause(&self, _: &str, _: bool) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn unpause(&self, _: &str) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn remove(&self, _: &str, _: bool) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn remove_result(&self, _: &str) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn pause_all(&self) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn unpause_all(&self) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn tell_status(&self, _: &str, _: &[&str]) -> Result<Json> {
            Err(AfuError::Engine("test".into()))
        }
        fn tell_active(&self, _: &[&str]) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn tell_waiting(&self, _: i64, _: i64, _: &[&str]) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn tell_stopped(&self, _: i64, _: i64, _: &[&str]) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn global_stat(&self) -> Result<Json> {
            Err(AfuError::Engine("test".into()))
        }
        fn get_peers(&self, _: &str) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn get_files(&self, _: &str) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn get_servers(&self, _: &str) -> Result<Vec<Json>> {
            Err(AfuError::Engine("test".into()))
        }
        fn change_option(&self, _: &str, _: &JsonMap) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn change_global_option(&self, _: &JsonMap) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn change_uri(&self, _: &str, _: i64, _: &[String], _: &[String], _: i64) -> Result<i64> {
            Err(AfuError::Engine("test".into()))
        }
        fn get_global_option(&self) -> Result<JsonMap> {
            Err(AfuError::Engine("test".into()))
        }
        fn shutdown(&self, _: bool) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
        fn save_session(&self) -> Result<String> {
            Err(AfuError::Engine("test".into()))
        }
    }

    fn gecici_klasor(ad: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("afudm-g1-butunluk-{ad}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).expect("klasor");
        d
    }

    fn yonetici(klasor: &Path) -> (Manager, Arc<afudm_db::SqliteStore>) {
        let store = Arc::new(afudm_db::SqliteStore::open_in_memory().expect("db"));
        let m = Manager::new(
            store.clone(),
            Arc::new(CevrimdisiRpc),
            Arc::new(NoUi),
            klasor.to_path_buf(),
            klasor.to_path_buf(),
        );
        (m, store)
    }

    /// Sahte .aria2 dosyasi: parca/toplam ve bit dizisi verilir.
    fn aria2_dosyasi(parca: u32, toplam: u64, bitler: &[u8]) -> Vec<u8> {
        let mut d = b"aria2\0".to_vec();
        d.extend_from_slice(&0u32.to_be_bytes()); // kimlik uzunlugu
        d.extend_from_slice(&parca.to_be_bytes());
        d.extend_from_slice(&toplam.to_be_bytes());
        d.extend_from_slice(&0u64.to_be_bytes()); // yuklenen
        d.extend_from_slice(&(bitler.len() as u32).to_be_bytes());
        d.extend_from_slice(bitler);
        d
    }

    /// Tek istek alan yerel HTTP sunucusu; verilen ham yanitı döner.
    fn sahte_sunucu(yanit: Vec<u8>) -> String {
        let dinleyici = TcpListener::bind("127.0.0.1:0").expect("bind");
        let adres = dinleyici.local_addr().expect("adres");
        std::thread::spawn(move || {
            if let Ok((mut akis, _)) = dinleyici.accept() {
                let mut tampon = [0u8; 4096];
                let _ = akis.read(&mut tampon);
                let _ = akis.write_all(&yanit);
            }
        });
        format!("http://{adres}/dosya")
    }

    #[test]
    fn tara_saglam_zip_gecer() {
        let d = gecici_klasor("saglam");
        let yol = d.join("a.zip");
        let mut veri = b"PK\x03\x04".to_vec();
        veri.extend((0..2000u32).map(|i| (i * 37 % 200 + 128) as u8));
        fs::write(&yol, &veri).expect("yaz");
        let s = tara(&yol, Some(&json!(veri.len())));
        assert_eq!(s["durum"], "saglam", "{s}");
    }

    #[test]
    fn tara_html_hata_sayfasi_bozuk_sayilir() {
        let d = gecici_klasor("html");
        let yol = d.join("veri.dat");
        fs::write(&yol, b"<!doctype html><html><body>Hata</body></html>").expect("yaz");
        let s = tara(&yol, None);
        assert_eq!(s["durum"], "bozuk", "{s}");
        assert_eq!(s["bozuk_sayisi"], 1);
        assert!(s["neden"]
            .as_str()
            .unwrap_or("")
            .contains("(HTML içeriyor)"));
    }

    #[test]
    fn tara_boyut_uyusmazligi_eksik() {
        let d = gecici_klasor("boyut");
        let yol = d.join("x.bin");
        fs::write(&yol, vec![1u8; 10]).expect("yaz");
        let s = tara(&yol, Some(&json!(99)));
        assert_eq!(s["durum"], "eksik");
        assert_eq!(s["neden"], "Boyut uyuşmuyor (Beklenen: 99, Gerçek: 10).");
    }

    #[test]
    fn aria2_tam_ve_yarim() {
        let d = gecici_klasor("aria2");
        let tam = d.join("tam.aria2");
        fs::write(&tam, aria2_dosyasi(10, 30, &[0b0000_0111])).expect("yaz");
        assert!(aria2_kontrol_tam_mi(&tam));
        let yarim = d.join("yarim.aria2");
        fs::write(&yarim, aria2_dosyasi(10, 30, &[0b0000_0011])).expect("yaz");
        assert!(!aria2_kontrol_tam_mi(&yarim));
        assert!(!aria2_kontrol_tam_mi(&d.join("yok.aria2")));
    }

    #[test]
    fn artik_aria2_tam_iken_silinir() {
        let d = gecici_klasor("artik");
        let dosya = d.join("indi.bin");
        fs::write(&dosya, b"veri").expect("yaz");
        fs::write(aria2_yolu(&dosya), aria2_dosyasi(4, 4, &[0b0000_0001])).expect("yaz");
        assert!(artik_kontrol_dosyasini_sil(&dosya));
        assert!(!aria2_yolu(&dosya).exists());
    }

    #[test]
    fn butunluk_tara_kayit_yoksa_bulunamadi() {
        let d = gecici_klasor("kayityok");
        let (m, _) = yonetici(&d);
        let s = butunluk_tara(&m, "yok-gid").expect("tara");
        assert_eq!(s["ok"], false);
        assert_eq!(s["durum"], "bulunamadi");
    }

    #[test]
    fn butunluk_tara_bozuk_kaydi_hataya_yazar() {
        let d = gecici_klasor("kayit");
        let (m, store) = yonetici(&d);
        let yol = d.join("hedef.dat");
        fs::write(&yol, vec![0u8; 16]).expect("yaz");
        store
            .add(
                "http",
                "https://x/y",
                Some("hedef.dat"),
                Some(d.to_str().expect("utf8")),
                None,
                None,
                Some("g1"),
            )
            .expect("ekle");
        let s = butunluk_tara(&m, "g1").expect("tara");
        assert_eq!(s["ok"], true);
        assert_eq!(s["durum"], "bozuk");
        let satir = store.by_gid("g1").expect("sorgu").expect("satir");
        assert!(satir["error"].as_str().unwrap_or("").contains("bozuk"));
    }

    #[test]
    fn butunluk_hepsini_tara_yalniz_tamamlananlari_sayar() {
        let d = gecici_klasor("hepsi");
        let (m, store) = yonetici(&d);
        store
            .add(
                "http",
                "https://x/a",
                Some("a.bin"),
                Some(d.to_str().expect("utf8")),
                None,
                None,
                Some("a"),
            )
            .expect("ekle");
        let s = butunluk_hepsini_tara(&m).expect("hepsi");
        assert_eq!(s["ok"], true);
        assert_eq!(s["taranan"], 0);
        assert!(s["sonuclar"].as_object().is_some_and(|o| o.is_empty()));
    }

    #[test]
    fn butunluk_onar_kayit_yoksa_neden_doner() {
        let d = gecici_klasor("onar");
        let (m, _) = yonetici(&d);
        let s = butunluk_onar(&m, "yok", "http://127.0.0.1:1/x").expect("onar");
        assert_eq!(s, json!({"ok": false, "neden": "Kayıt bulunamadı."}));
    }

    #[test]
    fn blok_indir_206_ve_dogru_veri() {
        let govde = b"ABCDEFGH";
        let mut yanit = format!(
            "HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            govde.len()
        )
        .into_bytes();
        yanit.extend_from_slice(govde);
        let url = sahte_sunucu(yanit);
        let veri = blok_indir(&url, &[], 0, 8).expect("blok");
        assert_eq!(veri, govde);
    }

    #[test]
    fn blok_indir_206_yoksa_reddeder() {
        let govde = b"ABCDEFGH";
        let mut yanit = format!(
            "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            govde.len()
        )
        .into_bytes();
        yanit.extend_from_slice(govde);
        let url = sahte_sunucu(yanit);
        let hata = blok_indir(&url, &[], 0, 8).expect_err("200 reddedilmeli");
        assert!(hata.to_string().contains("desteklemiyor"));
    }

    /// Python testi: tests/butunluk_test.py (13 Eki duzeltmesi dahil) — ayni senaryolar.
    fn dosya_yaz(d: &Path, ad: &str, veri: &[u8]) -> PathBuf {
        let yol = d.join(ad);
        fs::write(&yol, veri).expect("yaz");
        yol
    }

    /// Deterministik sozde-rastgele bayt (Python: random.Random(7) yerine).
    fn sozde_rastgele(n: usize, mut tohum: u64) -> Vec<u8> {
        (0..n)
            .map(|_| {
                tohum ^= tohum << 13;
                tohum ^= tohum >> 7;
                tohum ^= tohum << 17;
                (tohum & 0xFF) as u8
            })
            .collect()
    }

    #[test]
    fn rastgele_veri_json_gibi_baslasa_bozuk_sayilmaz() {
        let d = gecici_klasor("rastgele");
        let mut govde = vec![0x7B];
        govde.extend(sozde_rastgele(5000, 7));
        let mut veri = b"Rar!\x1A\x07\x01\x00".to_vec();
        veri.extend(govde);
        let yol = dosya_yaz(&d, "a.rar", &veri);
        assert_eq!(tara(&yol, None)["durum"], "saglam");
    }

    #[test]
    fn gercek_json_hata_sayfasi_bozuk() {
        let d = gecici_klasor("jsonhata");
        let yol = dosya_yaz(&d, "a.rar", br#"{"error": "link expired", "code": 403}"#);
        assert_eq!(tara(&yol, None)["durum"], "bozuk");
    }

    #[test]
    fn html_iceren_sahte_rar_bozuk_ve_html_uzantisi_saglam() {
        let d = gecici_klasor("htmlrar");
        let bozuk = dosya_yaz(
            &d,
            "a.rar",
            b"<!DOCTYPE html>\n<html><body>Error</body></html>",
        );
        let s = tara(&bozuk, None);
        assert_eq!(s["durum"], "bozuk");
        assert!(s["neden"].as_str().unwrap_or("").contains("HTML"));
        let saglam = dosya_yaz(
            &d,
            "a.html",
            b"<!DOCTYPE html>\n<html><body>Hello</body></html>",
        );
        assert_eq!(tara(&saglam, None)["durum"], "saglam");
    }

    #[test]
    fn yanlis_imza_bozuk() {
        let d = gecici_klasor("imza");
        let yol = dosya_yaz(&d, "a.zip", b"Not a zip file at all");
        let s = tara(&yol, None);
        assert_eq!(s["durum"], "bozuk");
        assert!(s["neden"]
            .as_str()
            .unwrap_or("")
            .to_lowercase()
            .contains("imza yok"));
    }

    #[test]
    fn aria2_var_ve_bos_dosya_eksik() {
        let d = gecici_klasor("aria2var");
        let yol = dosya_yaz(&d, "a.rar", b"Rar!\x1A\x07\x00");
        fs::write(aria2_yolu(&yol), b"fake aria2 data").expect("yaz");
        let s = tara(&yol, None);
        assert_eq!(s["durum"], "eksik");
        assert!(s["neden"].as_str().unwrap_or("").contains(".aria2"));
        let bos = dosya_yaz(&d, "bos.txt", b"");
        assert!(tara(&bos, None)["neden"]
            .as_str()
            .unwrap_or("")
            .contains("0 bayt"));
    }

    #[test]
    fn aria2_ve_html_blok_bozuk_bloklari_verir() {
        let d = gecici_klasor("blokbozuk");
        let mut veri = b"<!DOCTYPE html><html>x</html>".to_vec();
        veri.resize(BLOCK_SIZE as usize, b' ');
        veri.extend(vec![0u8; BLOCK_SIZE as usize]);
        veri.extend(b"Rar!\x1A\x07\x00");
        veri.extend(sozde_rastgele(1000, 3));
        let yol = dosya_yaz(&d, "a.rar", &veri);
        fs::write(aria2_yolu(&yol), b"x").expect("yaz");
        let s = tara(&yol, None);
        assert_eq!(s["durum"], "bozuk", "{s}");
        let indeksler: Vec<u64> = s["bozuk_bloklar"]
            .as_array()
            .map(|a| a.iter().filter_map(|b| b["index"].as_u64()).collect())
            .unwrap_or_default();
        assert_eq!(indeksler, vec![0, 1]);
    }

    #[test]
    fn html_yanit_206_olsa_da_reddedilir() {
        let govde = b"<!DOCTYPE html><html>expired</html>";
        let mut yanit = format!(
            "HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            govde.len()
        )
        .into_bytes();
        yanit.extend_from_slice(govde);
        let url = sahte_sunucu(yanit);
        let hata = blok_indir(&url, &[], 0, 100).expect_err("html reddedilmeli");
        assert!(hata.to_string().contains("hata sayfası"), "{hata}");
    }
}
