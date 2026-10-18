//! SAHIBI: Ekip D (claude kod ajani). Python: core/manager.py torrent bolumu (add torrent dali,
//! seed, torrent dosyalari, metrik, peers, on-ekleme/iptal) + core/trackers.py + core/tracker_saglik.py.
//! Imzalar afudm-types::ManagerApi ile sabit; degistirilmez.

mod bencode;
pub mod saglik;
pub mod trackers;

use crate::queue::proxy;
use crate::Manager;
use afudm_types::{AfuError, Aria2, Json, JsonMap, ManagerApi, Result, Store};
use base64::Engine;
use serde_json::json;
use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::{Arc, MutexGuard};

/// Ekip D calisma durumu (Manager::torrent_state). preview/removed gid'leri tek kaynak olarak
/// queue::State'te tutulur (bkz. queue_kilidi); burada ikinci kopya yoktur.
#[derive(Default)]
pub struct State {}

// ---------------------------------------------------------------- yardimcilar

/// Python int(x or 0): aria2 sayilari genelde metin olarak gelir.
fn sayi_of(v: Option<&Json>) -> i64 {
    match v {
        Some(Json::Number(n)) => n
            .as_i64()
            .or_else(|| n.as_f64().map(|f| f as i64))
            .unwrap_or(0),
        Some(Json::String(s)) => s.trim().parse::<i64>().unwrap_or(0),
        Some(Json::Bool(b)) => i64::from(*b),
        _ => 0,
    }
}

/// Python truthiness.
fn truthy(v: Option<&Json>) -> bool {
    match v {
        None | Some(Json::Null) => false,
        Some(Json::Bool(b)) => *b,
        Some(Json::Number(n)) => n.as_f64().is_some_and(|f| f != 0.0),
        Some(Json::String(s)) => !s.is_empty(),
        Some(Json::Array(a)) => !a.is_empty(),
        Some(Json::Object(o)) => !o.is_empty(),
    }
}

/// Python str(x): metin ise kendisi, yoksa bos.
fn str_of(v: Option<&Json>) -> String {
    match v {
        Some(Json::String(s)) => s.clone(),
        Some(Json::Null) | None => String::new(),
        Some(other) => other.to_string(),
    }
}

/// Bos olmayan metin ise Some.
fn dolu_str(v: Option<&Json>) -> Option<String> {
    let s = str_of(v);
    if s.is_empty() {
        None
    } else {
        Some(s)
    }
}

/// Python round(x, n).
fn yuvarla(x: f64, n: i32) -> f64 {
    let c = 10f64.powi(n);
    (x * c).round() / c
}

/// Python str(exc)[:200] biciminde kisaltma (karakter bazli).
fn kes(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// Python: except Aria2Error/ValueError -> {"ok": False, "error": str(exc)[:200]}.
fn hata_json(e: &AfuError) -> Json {
    json!({"ok": false, "error": kes(crate::queue::kullanici_hatasi(&e.to_string()), 200)})
}

/// Only enable hash verification when metadata names an existing root inside the destination.
/// Malformed or unreadable metadata is left to aria2 to report.
pub(crate) fn yeniden_kullan(source: &str, dest: &str, name: &str, options: &mut JsonMap) {
    let local_name = || -> Option<String> {
        let path = Path::new(source);
        if !path.extension()?.eq_ignore_ascii_case("torrent") {
            return None;
        }
        let bencode::Bc::Sozluk(root) = bencode::coz(&std::fs::read(path).ok()?).ok()? else {
            return None;
        };
        let bencode::Bc::Sozluk(info) = root.get(&b"info"[..])? else {
            return None;
        };
        let bencode::Bc::Metin(name) = info
            .get(&b"name.utf-8"[..])
            .or_else(|| info.get(&b"name"[..]))?
        else {
            return None;
        };
        String::from_utf8(name.clone()).ok()
    };
    let name = if name.is_empty() {
        local_name().unwrap_or_default()
    } else {
        name.to_owned()
    };
    if name.is_empty()
        || [".", ".."].contains(&name.as_str())
        || name.contains(['/', '\\', ':', '\0'])
    {
        return;
    }
    // Canonical paths also prevent a symlink/junction from escaping the destination.
    if let (Ok(root), Ok(target)) = (
        Path::new(dest).canonicalize(),
        Path::new(dest).join(name).canonicalize(),
    ) {
        if target != root && target.starts_with(root) {
            options.insert("check-integrity".into(), json!("true"));
        }
    }
}

/// aria2 select-file degeri: 1-tabanli indeksler, virgullu liste.
pub(crate) fn select_degeri(indeksler: &[i64]) -> String {
    indeksler
        .iter()
        .map(|i| i.to_string())
        .collect::<Vec<_>>()
        .join(",")
}

/// Python human_size.
fn human_size(num: f64) -> String {
    let mut n = num;
    for birim in ["B", "KB", "MB", "GB", "TB"] {
        if n.abs() < 1024.0 {
            return if birim != "B" {
                format!("{:.1} {}", n, birim)
            } else {
                format!("{} B", n as i64)
            };
        }
        n /= 1024.0;
    }
    format!("{:.1} PB", n)
}

/// Python Path.suffix.lower().
fn uzanti_kucuk(ad: &str) -> String {
    match ad.rfind('.') {
        Some(i) if i > 0 && i < ad.len() - 1 => ad[i..].to_ascii_lowercase(),
        _ => String::new(),
    }
}

/// Python _torrent_dosya_turu.
fn torrent_dosya_turu(uzanti: &str) -> &'static str {
    let turler: [(&str, &[&str]); 5] = [
        ("video", &[".mp4", ".mkv", ".avi", ".webm", ".ts"]),
        ("ses", &[".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav"]),
        ("arsiv", &[".zip", ".rar", ".7z", ".tar", ".gz", ".iso"]),
        (
            "belge",
            &[".pdf", ".txt", ".epub", ".mobi", ".doc", ".docx"],
        ),
        ("resim", &[".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]),
    ];
    for (ad, uzantilar) in turler {
        if uzantilar.contains(&uzanti) {
            return ad;
        }
    }
    "diger"
}

/// Python _torrent_yol_parcalari: yolu parcalara boler; torrent adindan itibaren kirpar.
fn torrent_yol_parcalari(yol: &str, torrent_adi: &str) -> Vec<String> {
    let mut parcalar: Vec<String> = yol
        .replace('\\', "/")
        .split('/')
        .filter(|p| !p.is_empty())
        .map(String::from)
        .collect();
    if parcalar.first().is_some_and(|p| p.ends_with(':')) {
        parcalar.remove(0);
    }
    if !torrent_adi.is_empty() {
        let kucuk_ad = torrent_adi.to_lowercase();
        if let Some(sira) = parcalar.iter().position(|p| p.to_lowercase() == kucuk_ad) {
            return parcalar[sira..].to_vec();
        }
    }
    parcalar
}

/// preview/removed gid'leri icin tek kaynak: queue::State (Python ortak _preview_gids/_removed_gids).
fn queue_kilidi(m: &Manager) -> Result<MutexGuard<'_, crate::queue::State>> {
    m.queue_state
        .lock()
        .map_err(|_| AfuError::Other("kuyruk kilidi kullanilamiyor".into()))
}

fn ana_kilit(m: &Manager) -> Result<MutexGuard<'_, ()>> {
    m.kilit.lock().map_err(|e| AfuError::Other(e.to_string()))
}

/// Python: ilk followedBy gid'i (yoksa None).
fn ilk_followed(durum: &Json) -> Option<String> {
    durum
        .get("followedBy")
        .and_then(|a| a.as_array())
        .and_then(|a| a.first())
        .and_then(|v| v.as_str())
        .map(String::from)
}

// ---------------------------------------------------------- tracker islemleri

/// Python _seed_taramasini_bayatlat + _tracker_saglik_tara: arka planda yeniden tarar.
fn arka_planda_tara(store: Arc<dyn Store>, rpc: Arc<dyn Aria2>, data: PathBuf, app: PathBuf) {
    std::thread::spawn(move || {
        let gid = rpc
            .tell_active(&["gid"])
            .ok()
            .and_then(|aktif| aktif.first().map(|s| str_of(s.get("gid"))))
            .unwrap_or_default();
        let sonuc = tracker_tara_ic(&*store, &*rpc, &data, &app, &gid);
        let basarili = sonuc
            .as_ref()
            .ok()
            .and_then(|s| s.get("ok"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !basarili {
            let hata = sonuc
                .ok()
                .and_then(|s| s.get("error").and_then(|e| e.as_str()).map(String::from))
                .unwrap_or_default();
            store.log(
                "warn",
                &kes(&format!("tracker taramasi basarisiz: {hata}"), 150),
                &gid,
            );
        }
    });
}

/// Python tracker_tara: GID verilirse info hash ile tarar, sonucu aria2'ye uygular.
fn tracker_tara_ic(
    store: &dyn Store,
    rpc: &dyn Aria2,
    data: &Path,
    app: &Path,
    gid: &str,
) -> Result<Json> {
    let mut infohash = String::new();
    if !gid.is_empty() {
        match rpc.tell_status(gid, &["infoHash"]) {
            Ok(durum) => infohash = str_of(durum.get("infoHash")).to_lowercase(),
            Err(e) => return Ok(hata_json(&e)),
        }
    }
    let sonuc = match saglik::tazele(store, &app.join("trackers"), &infohash) {
        Ok(s) => s,
        Err(e) => return Ok(hata_json(&e)),
    };
    let ek = str_of(store.get("ek_trackerlar")?.as_ref());
    let canli = str_of(store.get("canli_trackerlar")?.as_ref());
    let uygulanan = match trackers::aria2_uygula(rpc, data, false, &ek, &canli) {
        Ok(n) => n,
        Err(e) => return Ok(hata_json(&e)),
    };
    let mut cikti = json!({"ok": true});
    for (anahtar, deger) in sonuc.sayilar.iter() {
        cikti[anahtar.as_str()] = deger.clone();
    }
    cikti["uygulanan"] = json!(uygulanan);
    Ok(cikti)
}

/// Python seed_bilgi: seed penceresi icin ozet.
pub fn seed_bilgi(m: &Manager, gid: &str) -> Result<Json> {
    let rpc = m.rpc();
    let status = match rpc.tell_status(
        gid,
        &[
            "gid",
            "status",
            "infoHash",
            "numSeeders",
            "connections",
            "bittorrent",
            "dir",
            "completedLength",
            "totalLength",
        ],
    ) {
        Ok(s) => s,
        Err(e) => return Ok(hata_json(&e)),
    };
    let bittorrent = status.get("bittorrent").cloned().unwrap_or(Json::Null);
    let duyuru = bittorrent
        .get("announceList")
        .and_then(|a| a.as_array())
        .cloned()
        .unwrap_or_default();
    let global_ayar: JsonMap = rpc.get_global_option().unwrap_or_default();
    let havuz_sayisi = str_of(global_ayar.get("bt-tracker"))
        .split(',')
        .filter(|t| !t.is_empty())
        .count();
    let yas = trackers::cache_yasi(&m.data_dir);
    let ek = str_of(m.store.get("ek_trackerlar")?.as_ref());
    let canli = str_of(m.store.get("canli_trackerlar")?.as_ref());
    let baslik = m
        .store
        .by_gid(gid)?
        .and_then(|r| dolu_str(r.get("title")))
        .unwrap_or_else(|| gid.to_string());
    let tarama = match m.store.get("tracker_tarama_ozeti")? {
        Some(v) if truthy(Some(&v)) => v,
        _ => json!({}),
    };
    let done = sayi_of(status.get("completedLength"));
    let total = sayi_of(status.get("totalLength"));
    Ok(json!({
        "ok": true,
        "baslik": baslik,
        "seed": sayi_of(status.get("numSeeders")),
        "baglanti": sayi_of(status.get("connections")),
        "tracker": duyuru.iter().map(|g| g.as_array().map_or(0, |a| a.len())).sum::<usize>(),
        "havuz": havuz_sayisi,
        "liste_yasi_saat": yas.map(|y| yuvarla(y / 3600.0, 1)),
        "dht": str_of(global_ayar.get("enable-dht")) == "true",
        "ek_trackerlar": str_of(m.store.get("ek_trackerlar")?.as_ref()),
        "ek_sayisi": trackers::ayikla(&ek).len(),
        "canli_sayisi": trackers::ayikla(&canli).len(),
        "tarama": tarama,
        "durum": str_of(status.get("status")),
        "ilerleme": yuvarla(done as f64 * 100.0 / (total.max(1) as f64), 1),
    }))
}

/// Python tracker_tara(gid).
pub fn tracker_tara(m: &Manager, gid: &str) -> Result<Json> {
    let rpc = m.rpc();
    tracker_tara_ic(&*m.store, &*rpc, &m.data_dir, &m.app_dir, gid)
}

/// Python seed_dosyalari: Ayarlar > Seed listeleri icin ozet.
pub fn seed_dosyalari(m: &Manager) -> Result<Json> {
    let klasor = m.app_dir.join("trackers");
    saglik::klasoru_hazirla(&klasor);
    let dosyalar = saglik::dosyalar(&klasor);
    let adres = saglik::klasorden_oku(&klasor).len();
    let zaman = match m.store.get("tracker_tarama_zamani")? {
        Some(Json::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(Json::String(s)) => s.parse::<f64>().unwrap_or(0.0),
        _ => 0.0,
    };
    let yas = {
        let simdi = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        simdi - zaman
    };
    let canli = str_of(m.store.get("canli_trackerlar")?.as_ref());
    let tarama = match m.store.get("tracker_tarama_ozeti")? {
        Some(v) if truthy(Some(&v)) => v,
        _ => json!({}),
    };
    Ok(json!({
        "ok": true,
        "dosyalar": dosyalar,
        "klasor": klasor.display().to_string(),
        "adres": adres,
        "canli": trackers::ayikla(&canli).len(),
        "tarama": tarama,
        "tarama_yasi_saat": if yas == 0.0 || yas > 1e9 { Json::Null } else { json!(yuvarla(yas / 3600.0, 1)) },
        "taze": saglik::taze_mi(&*m.store),
        "otomatik": truthy(m.store.get("tracker_otomatik_tara")?.as_ref()),
    }))
}

/// Python seed_dosya_ekle.
pub fn seed_dosya_ekle(m: &Manager, yol: &str) -> Result<Json> {
    let klasor = m.app_dir.join("trackers");
    let sonuc = match saglik::dosya_ekle(&klasor, yol) {
        Ok(s) => s,
        Err(e) => return Ok(hata_json(&e)),
    };
    if !truthy(sonuc.get("zaten")) {
        seed_taramasini_bayatlat(m)?;
    }
    let mut cikti = json!({"ok": true});
    for (anahtar, deger) in sonuc.as_object().into_iter().flatten() {
        cikti[anahtar.as_str()] = deger.clone();
    }
    Ok(cikti)
}

/// Python seed_dosya_sil.
pub fn seed_dosya_sil(m: &Manager, ad: &str) -> Result<Json> {
    let klasor = m.app_dir.join("trackers");
    let sonuc = match saglik::dosya_sil(&klasor, ad) {
        Ok(s) => s,
        Err(e) => return Ok(hata_json(&e)),
    };
    seed_taramasini_bayatlat(m)?;
    let mut cikti = json!({"ok": true});
    for (anahtar, deger) in sonuc.as_object().into_iter().flatten() {
        cikti[anahtar.as_str()] = deger.clone();
    }
    Ok(cikti)
}

fn seed_taramasini_bayatlat(m: &Manager) -> Result<()> {
    m.store.set("tracker_tarama_zamani", json!(0))?;
    arka_planda_tara(
        m.store.clone(),
        m.rpc(),
        m.data_dir.clone(),
        m.app_dir.clone(),
    );
    Ok(())
}

/// Python seed_tazele: torrenti tracker listesiyle yeniden duyurur (ilerleme .aria2 ile korunur).
pub fn seed_tazele(m: &Manager, gid: &str) -> Result<Json> {
    let rpc = m.rpc();
    let row = m.store.by_gid(gid)?;
    let status = match rpc.tell_status(gid, &["infoHash", "dir", "bittorrent", "status"]) {
        Ok(s) => s,
        Err(e) => return Ok(hata_json(&e)),
    };
    let infohash = str_of(status.get("infoHash")).to_lowercase();
    if infohash.is_empty() {
        return Ok(json!({"ok": false, "error": "bu is bir torrent degil"}));
    }
    let row_dir = row.as_ref().and_then(|r| dolu_str(r.get("dest_dir")));
    let hedef = match dolu_str(status.get("dir")).or(row_dir) {
        Some(h) => h,
        None => m.current_download_dir()?,
    };

    let ek = str_of(m.store.get("ek_trackerlar")?.as_ref());
    let canli = str_of(m.store.get("canli_trackerlar")?.as_ref());
    let sayi = trackers::aria2_uygula(&*rpc, &m.data_dir, true, &ek, &canli)?;

    let mut kaynak = row
        .as_ref()
        .map(|r| str_of(r.get("source")))
        .unwrap_or_default();
    if kaynak.to_lowercase().ends_with(".torrent") && !Path::new(&kaynak).exists() {
        kaynak.clear();
    }
    if !kaynak.starts_with("magnet:") && !kaynak.starts_with("http") && kaynak.is_empty() {
        kaynak = format!("magnet:?xt=urn:btih:{infohash}");
    }
    let mut secenekler = JsonMap::new();
    secenekler.insert("dir".to_string(), json!(hedef));
    secenekler.insert("bt-save-metadata".to_string(), json!("false"));
    yeniden_kullan(
        &kaynak,
        &hedef,
        &str_of(status.pointer("/bittorrent/info/name")),
        &mut secenekler,
    );
    if m.store.torrent_dosya_secimi_var(gid)? {
        let secim = m.store.torrent_dosya_secimleri(gid)?;
        secenekler.insert("select-file".to_string(), json!(select_degeri(&secim)));
    }
    let _ = rpc.pause(gid, false);
    let _ = rpc.remove(gid, true);
    let _ = rpc.remove_result(gid);

    let yeni = if kaynak.to_lowercase().ends_with(".torrent") && Path::new(&kaynak).exists() {
        let bayt = std::fs::read(&kaynak)?;
        rpc.add_torrent(
            &base64::engine::general_purpose::STANDARD.encode(bayt),
            Some(&secenekler),
        )
    } else {
        rpc.add_uri(std::slice::from_ref(&kaynak), Some(&secenekler))
    };
    let yeni_gid = match yeni {
        Ok(g) => g,
        Err(e) => {
            m.store
                .log("warn", &format!("seed tazeleme basarisiz: {e}"), gid);
            if crate::queue::disk_dolu(&e.to_string()) {
                if let Some(row) = row.as_ref() {
                    m.store.update_by_id(
                        sayi_of(row.get("id")),
                        &serde_json::from_value(json!({
                            "status":"error",
                            "error":crate::queue::kullanici_hatasi(&e.to_string())
                        }))?,
                    )?;
                }
            }
            return Ok(hata_json(&e));
        }
    };
    if let Some(r) = row.as_ref() {
        let mut alanlar = JsonMap::new();
        alanlar.insert("gid".to_string(), json!(yeni_gid));
        alanlar.insert("status".to_string(), json!("active"));
        alanlar.insert("error".to_string(), Json::Null);
        m.store.update_by_id(sayi_of(r.get("id")), &alanlar)?;
        m.store.torrent_dosya_secimlerini_tasi(gid, &yeni_gid)?;
    }
    m.store.log(
        "info",
        &format!("seed tazelendi: {sayi} tracker ile yeniden duyuruldu"),
        &yeni_gid,
    );
    Ok(json!({"ok": true, "tracker": sayi, "gid": yeni_gid}))
}

// -------------------------------------------------------- peer / on-ekleme

/// Python peers: canli peer listesi (yt:/row: icin bos).
pub fn peers(m: &Manager, gid: &str) -> Result<Vec<Json>> {
    if gid.starts_with("yt:") || gid.starts_with("row:") {
        return Ok(Vec::new());
    }
    let raw = match m.rpc().get_peers(gid) {
        Ok(r) => r,
        Err(_) => return Ok(Vec::new()),
    };
    Ok(raw
        .iter()
        .map(|p| {
            json!({
                "ip": p.get("ip").cloned().unwrap_or(Json::Null),
                "port": p.get("port").cloned().unwrap_or(Json::Null),
                "seeder": str_of(p.get("seeder")) == "true",
                "downloadSpeed": sayi_of(p.get("downloadSpeed")),
                "uploadSpeed": sayi_of(p.get("uploadSpeed")),
                "client": kes(&str_of(p.get("peerId")), 24),
            })
        })
        .collect())
}

/// Python torrent_on_ekle: dosya secimi yapilabilsin diye torrenti duraklatilmis ekler (DB'ye yazmaz).
pub fn torrent_on_ekle(m: &Manager, source: &str) -> Result<String> {
    let dir = m.current_download_dir()?;
    let mut secenekler = JsonMap::new();
    secenekler.insert("dir".to_string(), json!(dir));
    secenekler.insert("bt-save-metadata".to_string(), json!("false"));
    secenekler.insert("pause".to_string(), json!("true"));
    secenekler.insert("pause-metadata".to_string(), json!("false"));
    if let Some(p) = proxy::proksi_bul(m, &JsonMap::new())? {
        secenekler.extend(proxy::aria2_secenekleri(&p));
    }

    let rpc = m.rpc();
    let _kilit = ana_kilit(m)?;
    let yerel = Path::new(source);
    let sonuc = if yerel.exists() && uzanti_kucuk(&dosya_adi_of(yerel)) == ".torrent" {
        let bayt = std::fs::read(yerel)?;
        rpc.add_torrent(
            &base64::engine::general_purpose::STANDARD.encode(bayt),
            Some(&secenekler),
        )
    } else {
        rpc.add_uri(&[source.to_string()], Some(&secenekler))
    };
    match sonuc {
        Ok(gid) => {
            queue_kilidi(m)?.preview_gids.insert(gid.clone());
            Ok(gid)
        }
        Err(e) => {
            if e.to_string().to_lowercase().contains("already registered") {
                return Err(AfuError::Invalid("bu torrent zaten kuyrukta".to_string()));
            }
            Err(e)
        }
    }
}

fn dosya_adi_of(yol: &Path) -> String {
    yol.file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default()
}

/// Python torrent_on_iptal: on-eklenmis torrenti (ve varsa ortaya cikan child'i) aria2'den siler.
pub fn torrent_on_iptal(m: &Manager, gid: &str) -> Result<()> {
    let rpc = m.rpc();
    let child = rpc
        .tell_status(gid, &["followedBy"])
        .ok()
        .and_then(|d| ilk_followed(&d));
    {
        let mut durum = queue_kilidi(m)?;
        durum.removed_gids.insert(gid.to_string());
        if let Some(c) = child.as_ref() {
            durum.removed_gids.insert(c.clone());
        }
    }
    let hedefler = [Some(gid.to_string()), child];
    for tekil in hedefler.into_iter().flatten() {
        if tekil.is_empty() {
            continue;
        }
        let _ = rpc.remove(&tekil, true);
        let _ = rpc.remove_result(&tekil);
    }
    Ok(())
}

// --------------------------------------------------------------- dosyalar

const HAZIR_DEGIL_NEDEN: &str = "Magnet ustverisi henuz gelmedi; dosya listesi hazir degil.";

/// Python TorrentDosyaListesi'nin JSON karsiligi: hazir degilse liste bos, neden dolu.
fn hazir_degil_sonuc(gid: &str) -> Json {
    json!({"dosyalar": [], "hazir_degil": true, "neden": HAZIR_DEGIL_NEDEN, "gid": gid})
}

/// Python torrent_dosyalari. Donus: {"dosyalar", "hazir_degil", "neden", "gid"} (sozlesme: afudm-types).
pub fn torrent_dosyalari(m: &Manager, gid: &str) -> Result<Json> {
    let rpc = m.rpc();
    let row = m.store.by_gid(gid)?;
    const ALANLAR: [&str; 4] = ["gid", "infoHash", "bittorrent", "followedBy"];
    let mut aktif_gid = gid.to_string();
    let mut durum = rpc.tell_status(&aktif_gid, &ALANLAR).map_err(|e| {
        AfuError::Invalid(format!(
            "torrent durumu okunamadi: {}",
            kes(&e.to_string(), 160)
        ))
    })?;
    if let Some(child) = ilk_followed(&durum) {
        aktif_gid = child;
        durum = rpc.tell_status(&aktif_gid, &ALANLAR).map_err(|e| {
            AfuError::Invalid(format!(
                "torrent durumu okunamadi: {}",
                kes(&e.to_string(), 160)
            ))
        })?;
    }
    let bittorrent = durum.get("bittorrent").cloned().unwrap_or(Json::Null);
    let torrent_mu = row
        .as_ref()
        .is_some_and(|r| str_of(r.get("kind")) == "torrent")
        || truthy(Some(&bittorrent))
        || truthy(durum.get("infoHash"));
    if !torrent_mu {
        return Err(AfuError::Invalid(
            "dosya listesi yalnizca torrent GID icin kullanilir".to_string(),
        ));
    }
    if !truthy(Some(&bittorrent)) && !truthy(durum.get("infoHash")) {
        return Ok(hazir_degil_sonuc(&aktif_gid));
    }
    let ham_dosyalar = rpc.get_files(&aktif_gid).map_err(|e| {
        AfuError::Invalid(format!(
            "torrent dosya listesi okunamadi: {}",
            kes(&e.to_string(), 160)
        ))
    })?;
    if ham_dosyalar.is_empty() && !truthy(Some(&bittorrent)) {
        return Ok(hazir_degil_sonuc(&aktif_gid));
    }
    let torrent_adi = str_of(bittorrent.get("info").and_then(|i| i.get("name")));
    let tercih_var = m.store.torrent_dosya_secimi_var(&aktif_gid)?;
    let secilenler: HashSet<i64> = if tercih_var {
        m.store
            .torrent_dosya_secimleri(&aktif_gid)?
            .into_iter()
            .collect()
    } else {
        HashSet::new()
    };

    let mut sonuc = Vec::with_capacity(ham_dosyalar.len());
    for ham in &ham_dosyalar {
        let indeks = sayi_of(ham.get("index"));
        let yol = str_of(ham.get("path"));
        let parcalar = torrent_yol_parcalari(&yol, &torrent_adi);
        let ad = match parcalar.last() {
            Some(son) => son.clone(),
            None => yol
                .replace('\\', "/")
                .rsplit('/')
                .next()
                .unwrap_or("")
                .to_string(),
        };
        let uzanti = uzanti_kucuk(&ad);
        let boyut = sayi_of(ham.get("length"));
        let tamamlanan = sayi_of(ham.get("completedLength"));
        let secili = if tercih_var {
            secilenler.contains(&indeks)
        } else {
            ham.get("selected").and_then(|v| v.as_str()) == Some("true")
        };
        let uris = if truthy(ham.get("uris")) {
            ham["uris"].clone()
        } else {
            json!([])
        };
        let parent_yol = if parcalar.len() > 1 {
            parcalar[..parcalar.len() - 1].join("/")
        } else {
            String::new()
        };
        sonuc.push(json!({
            "indeks": indeks,
            "ad": ad,
            "yol": yol,
            "boyut": boyut,
            "boyut_insan": human_size(boyut as f64),
            "tamamlanan": tamamlanan,
            "yuzde": if boyut != 0 { yuvarla(tamamlanan as f64 * 100.0 / boyut as f64, 1) } else { 0.0 },
            "secili": secili,
            "uzanti": uzanti,
            "tur": torrent_dosya_turu(&uzanti),
            "yol_parcalari": parcalar,
            "parent_yol": parent_yol,
            "uris": uris,
        }));
    }
    Ok(json!({"dosyalar": sonuc, "hazir_degil": false, "neden": "", "gid": aktif_gid}))
}

/// Python torrent_dosya_secimini_kaydet: UI secimini sonraki baslatmaya kadar DB'de saklar.
pub fn torrent_dosya_secimini_kaydet(
    m: &Manager,
    gid: &str,
    indeksler: &[i64],
) -> Result<Vec<i64>> {
    let torrent = m
        .store
        .by_gid(gid)?
        .is_some_and(|r| str_of(r.get("kind")) == "torrent");
    if !torrent {
        return Err(AfuError::Invalid(
            "dosya secimi yalnizca torrent GID icin kaydedilir".to_string(),
        ));
    }
    let mut temiz: Vec<i64> = indeksler.iter().copied().filter(|&i| i > 0).collect();
    temiz.sort_unstable();
    temiz.dedup();
    m.store.torrent_dosya_secimlerini_kaydet(gid, &temiz)?;
    Ok(temiz)
}

/// Python torrent_secimi_ayarla: secimi calisan torrente aria2 uzerinden uygular ve kalici saklar.
pub fn torrent_secimi_ayarla(m: &Manager, gid: &str, indeksler: &[i64]) -> Result<Json> {
    let torrent = m
        .store
        .by_gid(gid)?
        .is_some_and(|r| str_of(r.get("kind")) == "torrent");
    if !torrent {
        return Err(AfuError::Invalid(
            "dosya secimi yalnizca torrent GID icin ayarlanir".to_string(),
        ));
    }
    let mut temiz: Vec<i64> = indeksler.to_vec();
    temiz.sort_unstable();
    temiz.dedup();
    if temiz.iter().any(|&i| i < 1) {
        return Err(AfuError::Invalid(
            "gecersiz dosya indeksi: 1-tabanli pozitif tam sayi olmali".to_string(),
        ));
    }
    let rpc = m.rpc();
    let dosyalar = rpc.get_files(gid).map_err(|e| {
        AfuError::Invalid(format!(
            "torrent dosya listesi okunamadi: {}",
            kes(&e.to_string(), 160)
        ))
    })?;
    let gecerli: HashSet<i64> = dosyalar.iter().map(|d| sayi_of(d.get("index"))).collect();
    if gecerli.is_empty() {
        return Err(AfuError::Invalid(
            "torrent dosya listesi henuz hazir degil".to_string(),
        ));
    }
    let gecersiz: Vec<String> = temiz
        .iter()
        .filter(|i| !gecerli.contains(i))
        .map(|i| i.to_string())
        .collect();
    if !gecersiz.is_empty() {
        return Err(AfuError::Invalid(format!(
            "gecersiz dosya indeksi: {}",
            gecersiz.join(",")
        )));
    }
    let mut degisiklik = JsonMap::new();
    degisiklik.insert("select-file".to_string(), json!(select_degeri(&temiz)));
    rpc.change_option(gid, &degisiklik).map_err(|e| {
        AfuError::Invalid(format!(
            "dosya secimi canli degistirilemedi: {}",
            kes(&e.to_string(), 160)
        ))
    })?;
    m.store.torrent_dosya_secimlerini_kaydet(gid, &temiz)?;
    m.store.log(
        "info",
        &format!("dosya secimi guncellendi ({} dosya)", temiz.len()),
        gid,
    );
    Ok(json!({"ok": true, "gid": gid, "indeksler": temiz}))
}

/// Python torrent_dosya_secimleri.
pub fn torrent_dosya_secimleri(m: &Manager, gid: &str) -> Result<Vec<i64>> {
    m.store.torrent_dosya_secimleri(gid)
}

/// Python torrent_metrikleri: seed, oran, hiz, tracker ve peer ozeti.
pub fn torrent_metrikleri(m: &Manager, gid: &str) -> Result<Json> {
    let rpc = m.rpc();
    let row = m.store.by_gid(gid)?;
    const ALANLAR: [&str; 13] = [
        "gid",
        "status",
        "infoHash",
        "numSeeders",
        "connections",
        "bittorrent",
        "dir",
        "completedLength",
        "totalLength",
        "uploadLength",
        "downloadSpeed",
        "uploadSpeed",
        "seeder",
    ];
    let status = rpc.tell_status(gid, &ALANLAR).map_err(|e| {
        AfuError::Invalid(format!(
            "torrent durumu okunamadi: {}",
            kes(&e.to_string(), 160)
        ))
    })?;
    let bittorrent = status.get("bittorrent").cloned().unwrap_or(Json::Null);
    let torrent_mu = row
        .as_ref()
        .is_some_and(|r| str_of(r.get("kind")) == "torrent")
        || truthy(Some(&bittorrent))
        || truthy(status.get("infoHash"));
    if !torrent_mu {
        return Err(AfuError::Invalid(
            "torrent metrikleri yalnizca torrent GID icin kullanilir".to_string(),
        ));
    }
    if !truthy(Some(&bittorrent)) && !truthy(status.get("infoHash")) {
        return Ok(json!({
            "hazir_degil": true,
            "neden": "Magnet ustverisi henuz gelmedi; metrikler hazir degil.",
        }));
    }
    let duyuru = bittorrent
        .get("announceList")
        .and_then(|a| a.as_array())
        .cloned()
        .unwrap_or_default();
    let tracker_sayisi: usize = duyuru
        .iter()
        .map(|g| g.as_array().map_or(0, |a| a.len()))
        .sum();
    let global_ayar: JsonMap = rpc.get_global_option().unwrap_or_default();
    let havuz_sayisi = str_of(global_ayar.get("bt-tracker"))
        .split(',')
        .filter(|t| !t.is_empty())
        .count();

    let done = sayi_of(status.get("completedLength"));
    let total = sayi_of(status.get("totalLength"));
    let uploaded = sayi_of(status.get("uploadLength"));
    let ratio = if done > 0 {
        yuvarla(uploaded as f64 / done as f64, 3)
    } else {
        0.0
    };
    let canli_peers = peers(m, gid)?;
    let seeder_peers = canli_peers
        .iter()
        .filter(|p| truthy(p.get("seeder")))
        .count();
    let ek = str_of(m.store.get("canli_trackerlar")?.as_ref());

    Ok(json!({
        "hazir_degil": false,
        "gid": gid,
        "durum": str_of(status.get("status")),
        "seeder": str_of(status.get("seeder")) == "true",
        "num_seeders": sayi_of(status.get("numSeeders")),
        "connections": sayi_of(status.get("connections")),
        "download_speed": sayi_of(status.get("downloadSpeed")),
        "upload_speed": sayi_of(status.get("uploadSpeed")),
        "completed_length": done,
        "total_length": total,
        "upload_length": uploaded,
        "ratio": ratio,
        "progress": if total != 0 { yuvarla(done as f64 * 100.0 / total as f64, 1) } else { 0.0 },
        "tracker_sayisi": tracker_sayisi,
        "havuz_sayisi": havuz_sayisi,
        "canli_tracker": trackers::ayikla(&ek).len(),
        "peers_toplam": canli_peers.len(),
        "peers_seeders": seeder_peers,
        "peers_leechers": canli_peers.len() - seeder_peers,
    }))
}

// ------------------------------------------------- sozlesme fonksiyonlari (C ekibi)

/// Python manager.py add() icindeki torrent dali (_launch_torrent): adopt / .torrent / magnet.
/// `req` alanlari: source, dest_dir, adopt_gid, selected_files (dizi). Donen: {"gid": ...}.
#[allow(dead_code)] // C ekibi cagirana kadar stub
pub(crate) fn torrent_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json> {
    let rpc = m.rpc();
    let source = str_of(req.get("source"));
    let dest_dir = match dolu_str(req.get("dest_dir")) {
        Some(d) => d,
        None => m.current_download_dir()?,
    };
    let mut adopt_gid = dolu_str(req.get("adopt_gid"));
    let secili: Vec<i64> = req
        .get("selected_files")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|x| sayi_of(Some(x))).collect())
        .unwrap_or_default();

    if adopt_gid.is_none() {
        let mut infohash = magnet_infohash(&source);
        let yerel = Path::new(&source);
        if infohash.is_empty() && yerel.exists() && uzanti_kucuk(&dosya_adi_of(yerel)) == ".torrent"
        {
            infohash = bencode::torrent_info_hash(&std::fs::read(yerel)?);
        }
        if !infohash.is_empty() {
            let bekleyen = rpc.tell_waiting(0, 200, &[]).unwrap_or_default();
            for durum in bekleyen {
                let gid = str_of(durum.get("gid"));
                if str_of(durum.get("status")) == "paused"
                    && str_of(durum.get("infoHash")).to_lowercase() == infohash.to_lowercase()
                    && m.store.by_gid(&gid)?.is_none()
                {
                    adopt_gid = Some(gid);
                    break;
                }
            }
        }
    }

    if let Some(adopt) = adopt_gid {
        let mut gid = adopt;
        let mut metadata = Json::Null;
        if let Ok(durum) = rpc.tell_status(&gid, &["followedBy", "bittorrent"]) {
            if let Some(child) = ilk_followed(&durum) {
                gid = child;
                metadata = rpc.tell_status(&gid, &["bittorrent"]).unwrap_or(Json::Null);
            } else {
                metadata = durum;
            }
        }
        let mut dizin = JsonMap::new();
        dizin.insert("dir".to_string(), json!(dest_dir));
        dizin.insert("bt-save-metadata".to_string(), json!("false"));
        yeniden_kullan(
            &source,
            &dest_dir,
            &str_of(metadata.pointer("/bittorrent/info/name")),
            &mut dizin,
        );
        if let Err(e) = rpc.change_option(&gid, &dizin) {
            m.store
                .log("error", &format!("kayit dizini degistirilemedi: {e}"), &gid);
            if crate::queue::disk_dolu(&e.to_string()) {
                return Err(e);
            }
            return Err(AfuError::Invalid(
                "Secilen klasore kaydedilemiyor, baska bir klasor secin.".to_string(),
            ));
        }
        if !secili.is_empty() {
            let mut secim = JsonMap::new();
            secim.insert("select-file".to_string(), json!(select_degeri(&secili)));
            match rpc.change_option(&gid, &secim) {
                Ok(_) => m.store.torrent_dosya_secimlerini_kaydet(&gid, &secili)?,
                Err(e) => m
                    .store
                    .log("error", &format!("dosya secimi uygulanamadi: {e}"), &gid),
            }
        }
        rpc.unpause(&gid)?;
        return Ok(json!({"gid": gid}));
    }

    let mut secenekler = JsonMap::new();
    secenekler.insert("dir".to_string(), json!(dest_dir));
    secenekler.insert("bt-save-metadata".to_string(), json!("false"));
    yeniden_kullan(&source, &dest_dir, "", &mut secenekler);
    if let Some(p) = proxy::proksi_bul(m, req)? {
        secenekler.extend(proxy::aria2_secenekleri(&p));
    }
    let yerel = Path::new(&source);
    let sonuc = if yerel.exists() && uzanti_kucuk(&dosya_adi_of(yerel)) == ".torrent" {
        let bayt = std::fs::read(yerel)?;
        rpc.add_torrent(
            &base64::engine::general_purpose::STANDARD.encode(bayt),
            Some(&secenekler),
        )
    } else {
        rpc.add_uri(std::slice::from_ref(&source), Some(&secenekler))
    };
    match sonuc {
        Ok(gid) => Ok(json!({"gid": gid})),
        Err(e) => {
            if e.to_string().to_lowercase().contains("already registered") {
                return Err(AfuError::Invalid("bu torrent zaten kuyrukta".to_string()));
            }
            Err(e)
        }
    }
}

/// Python snapshot satirindaki torrent alanlari (seed, peers, metrik). Torrent degilse bos harita.
#[allow(dead_code)] // C ekibi cagirana kadar stub
pub(crate) fn snapshot_alanlari(m: &Manager, status: &Json) -> JsonMap {
    let _ = m;
    let bittorrent = status.get("bittorrent");
    let torrent = truthy(bittorrent) || truthy(status.get("infoHash"));
    let mut harita = JsonMap::new();
    if !torrent {
        return harita;
    }
    let done = sayi_of(status.get("completedLength"));
    let uploaded = sayi_of(status.get("uploadLength"));
    harita.insert(
        "numSeeders".to_string(),
        json!(sayi_of(status.get("numSeeders"))),
    );
    harita.insert(
        "seeder".to_string(),
        json!(str_of(status.get("seeder")) == "true"),
    );
    harita.insert(
        "connections".to_string(),
        json!(sayi_of(status.get("connections"))),
    );
    harita.insert(
        "uploadSpeed".to_string(),
        json!(sayi_of(status.get("uploadSpeed"))),
    );
    harita.insert("uploadLength".to_string(), json!(uploaded));
    harita.insert(
        "ratio".to_string(),
        json!(if done > 0 {
            yuvarla(uploaded as f64 / done as f64, 3)
        } else {
            0.0
        }),
    );
    harita.insert(
        "infoHash".to_string(),
        json!(str_of(status.get("infoHash"))),
    );
    harita.insert(
        "numPieces".to_string(),
        json!(sayi_of(status.get("numPieces"))),
    );
    harita
}

/// Python magnet_infohash: magnet linkinden hex info hash (kucuk harf); yoksa bos.
pub(crate) fn magnet_infohash(source: &str) -> String {
    let kucuk = source.to_ascii_lowercase();
    if !kucuk.starts_with("magnet:") {
        return String::new();
    }
    let sorgu = source.split_once('?').map(|(_, q)| q).unwrap_or("");
    for parca in sorgu.split('&') {
        let Some((anahtar, deger)) = parca.split_once('=') else {
            continue;
        };
        if anahtar != "xt" || !deger.to_ascii_lowercase().starts_with("urn:btih:") {
            continue;
        }
        let ham = deger.rsplit(':').next().unwrap_or("").trim();
        if ham.len() == 40 {
            return ham.to_ascii_lowercase();
        }
        if ham.len() == 32 {
            if let Some(hex) = base32_hex(ham) {
                return hex;
            }
        }
        return ham.to_ascii_lowercase();
    }
    String::new()
}

/// Python base64.b32decode(raw).hex() icin RFC 4648 kodlama cozucu (32 karakter -> 20 bayt).
fn base32_hex(metin: &str) -> Option<String> {
    let alfabe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    let mut bit_tamponu: u32 = 0;
    let mut bit_say: u32 = 0;
    let mut cikti = String::new();
    for c in metin.to_ascii_uppercase().bytes() {
        let deger = alfabe.iter().position(|&a| a == c)? as u32;
        bit_tamponu = (bit_tamponu << 5) | deger;
        bit_say += 5;
        if bit_say >= 8 {
            bit_say -= 8;
            let bayt = ((bit_tamponu >> bit_say) & 0xff) as u8;
            cikti.push_str(&format!("{bayt:02x}"));
        }
    }
    Some(cikti)
}
