//! SAHIBI: Ekip F4a. Python app.py Api metotlarinin bu ekibe dusen kismi.
//! `dispatch` ad bu dosyaya aitse Some(yanit), degilse None doner.
//!
//! Kapsam: add_links (core/servis.py ekle), linkgrabber_*, rules_save/rules_simulate/download_rules,
//! chrome_*, eklenti_* (g2 EklentiServisi), probe, proxy_testi, port_durumu, ayar_rozetleri, defender_scan.
//! `cerez` icin app.py'de Api metodu YOK (yalniz tarayici_cerezi ayari); komut baglanmadi.

use std::collections::{BTreeSet, HashMap};
use std::io::Read;
use std::net::{TcpStream, ToSocketAddrs};
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock, PoisonError};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use afudm_core::queue;
use afudm_db::kaydet;
use afudm_extras::g1::chrome::{self, OtomatikEkleme};
use afudm_extras::g2::{kurallar, linkgrabber};
use afudm_extras::h::esleme;
use afudm_types::{AfuError, ApiCtx, Json, JsonMap};
use serde_json::json;
use tauri::Manager as _;
use tauri_plugin_dialog::DialogExt;

use crate::bridge::{self, Ek, Kabuk};
use crate::window::ANA;

type Sonuc<T> = afudm_types::Result<T>;

const ISLEM_YENIDEN_DENE: &str = "Islem tamamlanamadi. Bir kez daha dene.";
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const PROXY_TIPLERI: [&str; 5] = ["http", "https", "socks5", "socks5h", "socks4"];
const PROXY_MAX: usize = 1024;
const PROXY_PORT_MAX: u64 = 65535;
const PROXY_BAGLANTI_ZAMAN_ASIMI: Duration = Duration::from_secs(4);
const DEFENDER_ZAMAN_ASIMI: Duration = Duration::from_secs(600);
const BOOL_ANAHTARLAR: [&str; 3] = ["oto_altyazi", "altyazi_goem", "ustveri_goem"];
const METIN_ANAHTARLAR: [&str; 9] = [
    "altyazi_diller",
    "kucuk_resim",
    "bolumler",
    "sponsorblock",
    "bolum_araligi",
    "kapsayici",
    "ses_formati",
    "dosya_sablonu",
    "tarayici_cerezi",
];

/// Python core/servis.py `UYGULAMA_ZAMANI` (ayar rozetleri). Ayni sirayla kopya.
const UYGULAMA_ZAMANI: &[(&str, &str)] = &[
    ("max_speed_kb", "hemen"),
    ("max_upload_kb", "hemen"),
    ("hiz_profili", "hemen"),
    ("snail_speed_kb", "hemen"),
    ("max_concurrent", "hemen"),
    ("seed_ratio", "hemen"),
    ("clipboard_watch", "hemen"),
    ("clipboard_exts", "hemen"),
    ("language", "hemen"),
    ("notify_telegram", "hemen"),
    ("telegram_bot_token", "hemen"),
    ("telegram_chat_id", "hemen"),
    ("shutdown_when_done", "hemen"),
    ("sleep_when_done", "hemen"),
    ("sunucu_istek_limiti", "hemen"),
    ("sunucu_hatali_limit", "hemen"),
    ("sunucu_kilit_saniye", "hemen"),
    ("sunucu_istemci_kaydi", "hemen"),
    ("sunucu_proxy_guven", "hemen"),
    ("sunucu_acik", "hemen"),
    ("download_dir", "yeni_indirmelerde"),
    ("kategori_klasorleri", "yeni_indirmelerde"),
    ("video_quality", "yeni_indirmelerde"),
    ("kaydetme_penceresi", "yeni_indirmelerde"),
    ("proxy", "yeni_indirmelerde"),
    ("system_proxy", "yeni_indirmelerde"),
    ("split", "yeni_indirmelerde"),
    ("max_conn_per_server", "yeni_indirmelerde"),
    ("sunucu_port", "servis_yeniden"),
    ("sunucu_adres", "servis_yeniden"),
    ("sunucu_profil_id", "servis_yeniden"),
    ("lan_erisimi", "servis_yeniden"),
    ("api_port", "servis_yeniden"),
    ("tepsiye_kucult", "sonraki_baslatmada"),
    ("baslangicta_tepside", "sonraki_baslatmada"),
    ("auto_update_trackers", "sonraki_baslatmada"),
    ("tracker_otomatik_tara", "sonraki_baslatmada"),
];

/// LinkGrabber probe'unun iptal bayragi (Python `self._probe_iptal`).
static LG_IPTAL: Mutex<Option<Arc<AtomicBool>>> = Mutex::new(None);
/// Chrome otomatik ekleme (Python `self._chrome`) ve baslangic zamani (`self._chrome_baslangic`).
static CHROME: OnceLock<OtomatikEkleme> = OnceLock::new();
static CHROME_BASLANGIC: Mutex<f64> = Mutex::new(0.0);
/// Defender taramasi (Python `windows.scan` + `_scan_lock`).
static DEFENDER_DURUM: Mutex<Option<Json>> = Mutex::new(None);
static DEFENDER_MESGUL: AtomicBool = AtomicBool::new(false);

pub fn dispatch(k: &Kabuk, name: &str, a: &[Json]) -> Option<Json> {
    let yanit = match name {
        // --- link ekleme (core/servis.py ekle) ---
        "add_links" => ctx_yanit(k, |c| add_links(c, &nesne(a, 0))),
        "linkgrabber_ekle" => ctx_yanit(k, |c| {
            linkgrabber_ekle(c, &metin_listesi(a, 0), &nesne(a, 1))
        }),

        // --- LinkGrabber (app.py 505-610) ---
        "linkgrabber_analiz" => linkgrabber_analiz(bridge::s(a, 0), &nesne(a, 1)),
        "linkgrabber_suz" => linkgrabber_suz(&dizi(a, 0), &nesne(a, 1)),
        "linkgrabber_iptal" => {
            linkgrabber_iptal();
            json!({"ok": true})
        }
        "linkgrabber_onceki" => ek_yanit(k, |e, _| linkgrabber_onceki(e, &metin_listesi(a, 0))),
        "linkgrabber_probe" => ek_yanit(k, |e, _| {
            let es = a.get(1).and_then(Json::as_i64).unwrap_or(8);
            linkgrabber_probe(e, &metin_listesi(a, 0), es)
        }),

        // --- kurallar (g2 kurallar.rs) ---
        "rules_save" => ctx_yanit(k, |c| rules_save(c, &dizi(a, 0))),
        "rules_simulate" => ctx_yanit(k, |c| {
            let url = bridge::s(a, 0);
            let dosya = metin_ya_arg(a, 1, "");
            let boyut = a.get(2).and_then(Json::as_f64).unwrap_or(0.0);
            let protokol = metin_ya_arg(a, 3, "http");
            let kategori = metin_ya_arg(a, 4, "");
            cevap(rules_simulate(c, url, &dosya, boyut, &protokol, &kategori))
        }),
        "download_rules" => ctx_yanit(k, |c| download_rules(c, bridge::s(a, 0))),

        // --- Chrome (g1 chrome.rs) ---
        "chrome_durum" => chrome_durum(k),
        "chrome_hazirla" => {
            *kilit(&CHROME_BASLANGIC) = simdi();
            esleme::eslesme_ac(600.0);
            chrome_durum(k)
        }
        "chrome_otomatik" => ctx_yanit(k, |c| chrome_otomatik(k, c)),
        "chrome_ilerleme" => chrome_ilerleme(),
        "chrome_kopyala" => chrome_kopyala(k, bridge::s(a, 0)),
        "chrome_ac" => {
            chrome::panoya_kopyala("chrome://extensions/");
            json!({"ok": chrome::sayfayi_ac(&[]).is_some()})
        }

        // --- eklenti (g2 EklentiServisi; HTTP ile ayni ornek) ---
        "eklenti_incele" => ek_yanit(k, |e, _| eklenti_incele(k, e, bridge::s(a, 0))),
        "eklenti_kur" => ek_yanit(k, |e, _| {
            cevap(
                e.eklenti
                    .kur(bridge::s(a, 0), onay_listesi(a.get(1)).as_deref()),
            )
        }),
        "eklenti_guncelle" => ek_yanit(k, |e, _| {
            cevap(e.eklenti.guncelle(bridge::s(a, 0), bridge::s(a, 1)))
        }),
        "eklenti_kaldir" => ek_yanit(k, |e, _| cevap(e.eklenti.kaldir(bridge::s(a, 0)))),
        "eklenti_yeniden_baslat" => {
            ek_yanit(k, |e, _| cevap(e.eklenti.yeniden_baslat(bridge::s(a, 0))))
        }
        "eklenti_ayar_kaydet" => ek_yanit(k, |e, _| {
            let ayarlar = a
                .get(1)
                .filter(|v| bridge::truthy(v))
                .cloned()
                .unwrap_or(json!({}));
            cevap(e.eklenti.ayar_kaydet(bridge::s(a, 0), &ayarlar))
        }),
        "eklenti_gunluk" => ek_yanit(k, |e, _| cevap(e.eklenti.gunluk(bridge::s(a, 0)))),
        "eklenti_islem" => ek_yanit(k, |e, _| e.eklenti.islem()),
        "eklenti_islem_iptal" => ek_yanit(k, |e, _| e.eklenti.islem_iptal()),
        "eklenti_klasoru_ac" => eklenti_klasoru_ac(k),

        // --- ag / tani ---
        "probe" => ctx_yanit(k, |c| probe(c, bridge::s(a, 0))),
        "proxy_testi" => proxy_testi(bridge::s(a, 0)),
        "port_durumu" => port_durumu(k),
        "ayar_rozetleri" => ctx_yanit(k, |c| cevap(ayar_rozetleri(c))),
        "defender_scan" => ctx_yanit(k, |c| defender_scan(c, bridge::s(a, 0))),

        _ => return None,
    };
    Some(yanit)
}

// --- yardimcilar ---------------------------------------------------------------

fn kilit<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(PoisonError::into_inner)
}

fn ctx_yanit(k: &Kabuk, f: impl FnOnce(&ApiCtx) -> Json) -> Json {
    match k.ctx.get() {
        Some(c) => f(c),
        None => bridge::motor_hazir_degil(),
    }
}

fn ek_yanit(k: &Kabuk, f: impl FnOnce(&Ek, &ApiCtx) -> Json) -> Json {
    match (k.ek.get(), k.ctx.get()) {
        (Some(e), Some(c)) => f(e, c),
        _ => bridge::motor_hazir_degil(),
    }
}

fn cevap(r: Sonuc<Json>) -> Json {
    match r {
        Ok(v) => v,
        Err(e) => bridge::hata(e.to_string()),
    }
}

/// Python `str(v or "")`: bos/None/false -> "", digerleri metne cevrilir.
fn metin(v: Option<&Json>) -> String {
    match v {
        None | Some(Json::Null) => String::new(),
        Some(Json::String(s)) => s.clone(),
        Some(other) => other.to_string(),
    }
}

/// Python `v or ""`: yalniz dogru degerler metne cevrilir.
fn metin_or_bos(v: Option<&Json>) -> String {
    if v.is_some_and(bridge::truthy) {
        metin(v)
    } else {
        String::new()
    }
}

fn metin_ya(m: &JsonMap, anahtar: &str) -> String {
    metin_or_bos(m.get(anahtar))
}

fn metin_ya_arg(a: &[Json], i: usize, varsayilan: &str) -> String {
    a.get(i)
        .map_or_else(|| varsayilan.to_string(), |v| metin(Some(v)))
}

fn dogru(v: Option<&Json>) -> bool {
    v.is_some_and(bridge::truthy)
}

fn nesne(a: &[Json], i: usize) -> JsonMap {
    a.get(i)
        .and_then(Json::as_object)
        .cloned()
        .unwrap_or_default()
}

fn dizi(a: &[Json], i: usize) -> Vec<Json> {
    a.get(i)
        .and_then(Json::as_array)
        .cloned()
        .unwrap_or_default()
}

fn metin_listesi(a: &[Json], i: usize) -> Vec<String> {
    dizi(a, i).iter().map(|v| metin(Some(v))).collect()
}

fn kes(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn simdi_nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}

/// Python `_kullanici_mesaji`: girdi hatasi insan metni, digeri genel metin.
fn kullanici_mesaji(e: &AfuError) -> String {
    match e {
        AfuError::Invalid(m) | AfuError::NotFound(m) => {
            let t = kes(m.trim(), 200);
            if t.is_empty() {
                ISLEM_YENIDEN_DENE.to_string()
            } else {
                t
            }
        }
        _ => ISLEM_YENIDEN_DENE.to_string(),
    }
}

fn sadece_kumesi(filtre: &JsonMap) -> Option<BTreeSet<String>> {
    let kume: BTreeSet<String> = filtre
        .get("sadece")
        .and_then(Json::as_array)
        .map(|d| {
            d.iter()
                .map(|t| metin(Some(t)))
                .filter(|t| !t.is_empty() && t != "all")
                .collect()
        })
        .unwrap_or_default();
    if kume.is_empty() {
        None
    } else {
        Some(kume)
    }
}

/// Python `int(v)` (None/"" icin None). Hata: Err.
fn sayi_al(v: Option<&Json>) -> std::result::Result<Option<i64>, ()> {
    match v {
        None | Some(Json::Null) => Ok(None),
        Some(Json::String(s)) if s.is_empty() => Ok(None),
        Some(Json::String(s)) => s.trim().parse::<i64>().map(Some).map_err(|_| ()),
        Some(Json::Number(n)) => n
            .as_i64()
            .or_else(|| n.as_f64().map(|f| f as i64))
            .map(Some)
            .ok_or(()),
        Some(Json::Bool(b)) => Ok(Some(i64::from(*b))),
        Some(_) => Err(()),
    }
}

// --- add_links (core/servis.py ekle) -------------------------------------------

/// Python `ekle`: `urls` dizisi yoksa/bossa tek `url` (ya da `source`) kullanilir; bos satirlar atilir.
fn toplu_url_listesi(p: &JsonMap) -> Vec<String> {
    let tek = [p.get("url"), p.get("source")]
        .into_iter()
        .flatten()
        .find(|v| bridge::truthy(v))
        .map(|v| metin(Some(v)))
        .unwrap_or_default();
    let ham: Vec<String> = match p.get("urls") {
        Some(v) if bridge::truthy(v) => v
            .as_array()
            .map(|d| d.iter().map(|x| metin(Some(x))).collect())
            .unwrap_or_default(),
        _ => vec![tek],
    };
    ham.into_iter()
        .map(|u| u.trim().to_string())
        .filter(|u| !u.is_empty())
        .collect()
}

/// Python `hedef_klasor` (uzaktan dalı yok: kopru yalnız yerel arayuzden cagrilir).
fn hedef_klasor(
    c: &ApiCtx,
    secilen: &str,
    url: &str,
    kind: &str,
    kategori: &str,
) -> Sonuc<Option<String>> {
    if !secilen.is_empty() {
        return Ok(Some(secilen.to_string()));
    }
    let kl = c.store.get("kategori_klasorleri")?;
    if !kl.as_ref().is_some_and(bridge::truthy) {
        return Ok(None);
    }
    let kat = if kategori.is_empty() {
        kaydet::kategori_tahmin(url, kind, "")
    } else {
        kategori.to_string()
    };
    let ana = c.manager.current_download_dir()?;
    Ok(Some(kaydet::kategori_klasoru(&ana, &kat)))
}

/// Python `manager.add(...)` cagrisinin istek sozlugu (queue::add bu anahtarlari okur).
fn indirme_istegi(
    p: &JsonMap,
    url: &str,
    kind: &str,
    hedef: Option<String>,
    tek_ad: &str,
    tekil: bool,
    start_at: &str,
) -> JsonMap {
    let mut istek = JsonMap::new();
    istek.insert("source".into(), json!(url));
    istek.insert("kind".into(), json!(kind));
    if let Some(d) = hedef {
        istek.insert("dest_dir".into(), json!(d));
    }
    if !tek_ad.is_empty() {
        if kind == "http" {
            istek.insert("filename".into(), json!(tek_ad));
        } else if kind == "video" {
            istek.insert("title".into(), json!(tek_ad));
        }
    }
    if dogru(p.get("quality")) {
        istek.insert("quality".into(), p["quality"].clone());
    }
    istek.insert("audio_only".into(), json!(dogru(p.get("audio_only"))));
    istek.insert("playlist".into(), json!(dogru(p.get("playlist"))));
    if !start_at.is_empty() {
        istek.insert("start_at".into(), json!(start_at));
    }
    for anahtar in BOOL_ANAHTARLAR {
        istek.insert(anahtar.into(), json!(dogru(p.get(anahtar))));
    }
    for anahtar in METIN_ANAHTARLAR {
        let deger = if dogru(p.get(anahtar)) {
            p[anahtar].clone()
        } else {
            json!("")
        };
        istek.insert(anahtar.into(), deger);
    }
    if kind == "torrent" && tekil {
        istek.insert(
            "adopt_gid".into(),
            p.get("adopt_gid").cloned().unwrap_or(Json::Null),
        );
        istek.insert(
            "selected_files".into(),
            p.get("selected_files").cloned().unwrap_or(Json::Null),
        );
    }
    istek
}

/// Python `ekle` (core/servis.py): her link icin manager.add; kismi basari `failed` ile raporlanir.
fn add_links(c: &ApiCtx, p: &JsonMap) -> Json {
    let urller = toplu_url_listesi(p);
    if urller.is_empty() {
        return json!({"ok": false, "code": "BAD_REQUEST", "error": "link gerekli"});
    }
    let start_at = metin_ya(p, "start_at").trim().to_string();
    let tekil = urller.len() == 1;
    let tek_ad = if tekil {
        kaydet::guvenli_dosya_adi(&metin_ya(p, "filename"))
    } else {
        String::new()
    };
    let secilen = metin_ya(p, "dest_dir");
    let kategori = metin_ya(p, "kategori");
    let mut eklenen = 0i64;
    let mut planli = 0i64;
    let mut hatalar: Vec<String> = Vec::new();
    for url in &urller {
        let kind = queue::detect_kind(url);
        let sonuc = hedef_klasor(c, &secilen, url, kind, &kategori).and_then(|hedef| {
            let istek = indirme_istegi(p, url, kind, hedef, &tek_ad, tekil, &start_at);
            c.manager.add(&istek).map(|_| ())
        });
        match sonuc {
            Ok(()) if start_at.is_empty() => eklenen += 1,
            Ok(()) => planli += 1,
            Err(e) => {
                c.store.log(
                    "error",
                    &format!("link eklenemedi basarisiz: {}", kes(&e.to_string(), 300)),
                    "",
                );
                hatalar.push(kes(
                    &format!("{}: {}", kes(url, 48), kullanici_mesaji(&e)),
                    180,
                ));
            }
        }
    }
    if eklenen == 0 && planli == 0 {
        if let Some(ilk) = hatalar.first().cloned() {
            return json!({"ok": false, "code": "EKLENEMEDI", "error": ilk, "failed": hatalar});
        }
    }
    json!({"ok": true, "added": eklenen, "scheduled": planli, "failed": hatalar})
}

// --- LinkGrabber -----------------------------------------------------------------

fn en_az_bir_baglanti(c: &ApiCtx) -> String {
    match c
        .store
        .get("language")
        .ok()
        .flatten()
        .as_ref()
        .and_then(Json::as_str)
    {
        Some("en") => "Enter at least one link.".to_string(),
        _ => "En az bir bağlantı gir.".to_string(),
    }
}

/// Python `linkgrabber_ekle`: secimi add_links'e cevirir.
fn linkgrabber_ekle(c: &ApiCtx, urller: &[String], secim: &JsonMap) -> Json {
    let urller: Vec<String> = urller.iter().filter(|u| !u.is_empty()).cloned().collect();
    if urller.is_empty() {
        return json!({"ok": false, "error": en_az_bir_baglanti(c)});
    }
    let mut p = JsonMap::new();
    p.insert("urls".into(), json!(urller));
    p.insert("dest_dir".into(), json!(metin_ya(secim, "dest_dir")));
    p.insert("kategori".into(), json!(metin_ya(secim, "kategori")));
    p.insert(
        "quality".into(),
        secim
            .get("quality")
            .filter(|v| bridge::truthy(v))
            .cloned()
            .unwrap_or(Json::Null),
    );
    p.insert("audio_only".into(), json!(dogru(secim.get("audio_only"))));
    p.insert("playlist".into(), json!(dogru(secim.get("playlist"))));
    p.insert("start_at".into(), json!(metin_ya(secim, "start_at")));
    add_links(c, &p)
}

fn linkgrabber_analiz(metin_girdi: &str, filtre: &JsonMap) -> Json {
    let sadece = sadece_kumesi(filtre);
    let domain = metin_ya(filtre, "domain");
    let urller = linkgrabber::tekil_les(&linkgrabber::ayikla(metin_girdi));
    let urller = linkgrabber::filtrele(&urller, sadece.as_ref(), &domain);
    let ogeler: Vec<Json> = urller
        .iter()
        .map(|u| json!({"url": u, "tur": linkgrabber::tur_bul(u)}))
        .collect();
    json!({"ok": true, "toplam": ogeler.len(), "ogeler": ogeler, "filtre": filtre})
}

fn linkgrabber_suz(ogeler: &[Json], filtre: &JsonMap) -> Json {
    let sadece = sadece_kumesi(filtre);
    let (min, max) = match (
        sayi_al(filtre.get("min_boyut")),
        sayi_al(filtre.get("max_boyut")),
    ) {
        (Ok(a), Ok(b)) => (a, b),
        _ => (None, None),
    };
    let indeks = linkgrabber::ogeleri_filtrele(
        ogeler,
        &metin_ya(filtre, "ara"),
        sadece.as_ref(),
        &metin_ya(filtre, "domain"),
        min,
        max,
    );
    json!({
        "ok": true,
        "toplam": ogeler.len(),
        "gosterilen": indeks.len(),
        "indeks": indeks,
        "domainler": linkgrabber::domainler(ogeler),
    })
}

fn linkgrabber_iptal() {
    if let Some(iptal) = kilit(&LG_IPTAL).as_ref() {
        iptal.store(true, Ordering::SeqCst);
    }
}

fn linkgrabber_onceki(e: &Ek, urller: &[String]) -> Json {
    match queue::gecmis_sources(&e.core, 3000) {
        Ok(gecmis) => {
            let eslesen = linkgrabber::onceki_eslesen(urller, &gecmis);
            json!({"ok": true, "onceki": eslesen, "sayi": eslesen.len()})
        }
        Err(err) => bridge::hata(err.to_string()),
    }
}

/// Python `linkgrabber_probe` ogelerinin sekli; `sonuclar` probe_es_zamanli ciktisi.
fn probe_ogeleri(urller: &[String], sonuclar: &HashMap<String, Json>) -> Vec<Json> {
    urller
        .iter()
        .map(|url| {
            let bilgi = sonuclar
                .get(url)
                .cloned()
                .unwrap_or_else(|| json!({"ok": false}));
            let ad = bilgi
                .get("filename")
                .and_then(Json::as_str)
                .unwrap_or("")
                .to_string();
            let http = url.to_lowercase().starts_with("http://")
                || url.to_lowercase().starts_with("https://");
            let kategori = if http {
                kaydet::kategori_tahmin(url, linkgrabber::tur_bul(url), &ad)
            } else {
                String::new()
            };
            json!({
                "url": url,
                "ok": bilgi.get("ok").and_then(Json::as_bool).unwrap_or(false),
                "filename": ad,
                "size": bilgi.get("size").cloned().unwrap_or(Json::Null),
                "content_type": bilgi.get("content_type").cloned().unwrap_or(Json::Null),
                "kategori": kategori,
                "resumable": bilgi.get("resumable").and_then(Json::as_bool).unwrap_or(false),
            })
        })
        .collect()
}

fn linkgrabber_probe(e: &Ek, urller: &[String], es_zamanli: i64) -> Json {
    let iptal = Arc::new(AtomicBool::new(false));
    {
        let mut onceki = kilit(&LG_IPTAL);
        if let Some(eski) = onceki.as_ref() {
            eski.store(true, Ordering::SeqCst);
        }
        *onceki = Some(Arc::clone(&iptal));
    }
    // Python probe_url_info zaman asimi parametresi almaz; burada 3 sn kullanilir (probe_es_zamanli varsayilani).
    // ProbeFn tip takma adi 'static nesne ister: Manager Arc'ı klonlanip closure'a tasinir.
    let core = Arc::clone(&e.core);
    let probe = move |url: &str, _zaman: f64| -> Json {
        queue::probe_url_info(&core, url).unwrap_or_else(|_| json!({"ok": false}))
    };
    let sonuclar =
        linkgrabber::probe_es_zamanli(urller, es_zamanli, 3.0, Some(iptal.as_ref()), &probe);
    json!({"ok": true, "ogeler": probe_ogeleri(urller, &sonuclar)})
}

// --- kurallar --------------------------------------------------------------------

fn uuid_uret() -> String {
    use std::collections::hash_map::RandomState;
    use std::hash::{BuildHasher, Hasher};
    let mut bayt = [0u8; 16];
    for parca in bayt.chunks_mut(8) {
        let mut h = RandomState::new().build_hasher();
        h.write(&simdi_nanos().to_le_bytes());
        let deger = h.finish().to_le_bytes();
        parca.copy_from_slice(&deger[..parca.len()]);
    }
    bayt[6] = (bayt[6] & 0x0f) | 0x40;
    bayt[8] = (bayt[8] & 0x3f) | 0x80;
    let hex: String = bayt.iter().map(|b| format!("{b:02x}")).collect();
    format!(
        "{}-{}-{}-{}-{}",
        &hex[0..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..32]
    )
}

/// Python `rules_save` temizligi (kimlik yoksa uuid).
fn kural_temizle(gelen: &[Json]) -> std::result::Result<Vec<Json>, &'static str> {
    let mut temiz = Vec::with_capacity(gelen.len());
    for kural in gelen {
        let Some(nesne) = kural.as_object() else {
            return Err("kural adi gerekli");
        };
        let ad = metin_ya(nesne, "name").trim().to_string();
        if ad.is_empty() {
            return Err("kural adi gerekli");
        }
        let kimlik = match metin_ya(nesne, "id") {
            k if k.is_empty() => uuid_uret(),
            k => k,
        };
        let mt = nesne
            .get("match_type")
            .and_then(Json::as_str)
            .filter(|m| *m == "all" || *m == "any")
            .unwrap_or("all");
        temiz.push(json!({
            "id": kimlik,
            "name": kes(&ad, 100),
            "active": nesne.get("active").is_none_or(bridge::truthy),
            "match_type": mt,
            "conditions": nesne.get("conditions").filter(|v| v.is_array()).cloned().unwrap_or_else(|| json!([])),
            "actions": nesne.get("actions").filter(|v| v.is_object()).cloned().unwrap_or_else(|| json!({})),
        }));
    }
    Ok(temiz)
}

fn rules_save(c: &ApiCtx, gelen: &[Json]) -> Json {
    match kural_temizle(gelen) {
        Err(mesaj) => json!({"ok": false, "error": mesaj}),
        Ok(temiz) => match c
            .store
            .rules_save(&temiz)
            .and_then(|()| c.store.rules_list())
        {
            Ok(liste) => json!({"ok": true, "rules": liste}),
            Err(e) => bridge::hata(e.to_string()),
        },
    }
}

/// Python `rules_simulate` cekirdegi (saf): eslesen kurallar + cakisan secenekler.
fn kural_simule(
    tum: &[Json],
    varsayilan: &JsonMap,
    url: &str,
    dosya_adi: &str,
    boyut: f64,
    protokol: &str,
    kategori: &str,
) -> Sonuc<Json> {
    let baglam = kurallar::context(url, dosya_adi, boyut, protokol, kategori);
    let cikti = kurallar::evaluate(tum, varsayilan, &baglam, None)?;
    let ids = cikti["matched_rules"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let eslesen: Vec<Json> = tum
        .iter()
        .filter(|r| ids.contains(r.get("id").unwrap_or(&Json::Null)))
        .cloned()
        .collect();
    let secenekler = cikti["effective_options"]
        .as_object()
        .cloned()
        .unwrap_or_default();
    let catisma: Vec<String> = secenekler
        .keys()
        .filter(|anahtar| {
            eslesen
                .iter()
                .filter(|r| {
                    r.get("actions")
                        .and_then(Json::as_object)
                        .is_some_and(|m| m.contains_key(anahtar.as_str()))
                })
                .count()
                > 1
        })
        .cloned()
        .collect();
    Ok(json!({
        "ok": true,
        "effective_options": secenekler,
        "trace": cikti["trace"].clone(),
        "matched_rules": eslesen,
        "conflicts": catisma,
    }))
}

fn rules_simulate(
    c: &ApiCtx,
    url: &str,
    dosya_adi: &str,
    boyut: f64,
    protokol: &str,
    kategori: &str,
) -> Sonuc<Json> {
    let tum = c.store.rules_list()?;
    let mut varsayilan = JsonMap::new();
    varsayilan.insert("dest_dir".into(), json!(c.manager.current_download_dir()?));
    varsayilan.insert("proxy".into(), c.store.get("proxy")?.unwrap_or(json!("")));
    varsayilan.insert(
        "max_speed_kb".into(),
        c.store.get("max_speed_kb")?.unwrap_or(json!(0)),
    );
    varsayilan.insert(
        "split".into(),
        c.store.get("max_conn_per_server")?.unwrap_or(json!(16)),
    );
    kural_simule(&tum, &varsayilan, url, dosya_adi, boyut, protokol, kategori)
}

fn download_rules(c: &ApiCtx, gid: &str) -> Json {
    match c.store.by_gid(gid) {
        Ok(Some(satir)) => {
            let trace = satir
                .get("options")
                .and_then(|o| o.get("rules_trace"))
                .cloned()
                .unwrap_or_else(|| json!({}));
            json!({"ok": true, "trace": trace})
        }
        Ok(None) => json!({"ok": false, "error": "kayit bulunamadi"}),
        Err(e) => bridge::hata(e.to_string()),
    }
}

// --- Chrome ----------------------------------------------------------------------

fn chrome_uzanti(k: &Kabuk) -> PathBuf {
    k.app_dir.join("extension")
}

fn chrome_durum(k: &Kabuk) -> Json {
    json!({
        "ok": true,
        "chrome": chrome::chrome_yolu().is_some(),
        "klasor": chrome_uzanti(k).display().to_string(),
        "adres": "chrome://extensions/",
    })
}

fn chrome_otomatik(k: &Kabuk, c: &ApiCtx) -> Json {
    let ekleme = CHROME.get_or_init(OtomatikEkleme::new);
    {
        let mut bas = kilit(&CHROME_BASLANGIC);
        if *bas == 0.0 {
            *bas = simdi();
        }
    }
    // Python `baslat(once=...)` geri cagrisi Rust surumunde yok: eslesme penceresi kurulumdan once acilir.
    if ekleme.durum()["calisiyor"] != json!(true) {
        esleme::eslesme_ac(600.0);
    }
    let baslatildi = ekleme.baslat(c.data_dir.clone(), chrome_uzanti(k), Vec::new(), 0);
    json!({"ok": true, "baslatildi": baslatildi})
}

fn chrome_ilerleme() -> Json {
    let durum = CHROME.get_or_init(OtomatikEkleme::new).durum();
    let bas = *kilit(&CHROME_BASLANGIC);
    let baglandi = esleme::son_eslesme() >= bas && bas > 0.0;
    let mut cikti = match durum {
        Json::Object(m) => m,
        _ => JsonMap::new(),
    };
    cikti.insert("ok".into(), json!(true));
    cikti.insert("baglandi".into(), json!(baglandi));
    Json::Object(cikti)
}

fn chrome_kopyala(k: &Kabuk, ne: &str) -> Json {
    let metin_kopya = if ne == "adres" {
        "chrome://extensions/".to_string()
    } else {
        chrome_uzanti(k).display().to_string()
    };
    json!({"ok": chrome::panoya_kopyala(&metin_kopya)})
}

// --- eklenti ---------------------------------------------------------------------

/// Python `eklenti_kur` onaylanan_izinler: None/yok -> None, dizi -> liste.
fn onay_listesi(v: Option<&Json>) -> Option<Vec<String>> {
    match v {
        None | Some(Json::Null) => None,
        Some(Json::Array(d)) => Some(d.iter().map(|x| metin(Some(x))).collect()),
        Some(_) => Some(Vec::new()),
    }
}

/// Python `eklenti_incele`: yol bossa dosya secici acilir (.afup).
fn eklenti_incele(k: &Kabuk, e: &Ek, yol: &str) -> Json {
    if !yol.is_empty() {
        return cevap(e.eklenti.incele(yol));
    }
    if k.app.get_webview_window(ANA).is_none() {
        return bridge::hata("pencere hazir degil");
    }
    let secim = k
        .app
        .dialog()
        .file()
        .add_filter("AfuDM eklenti paketi (*.afup)", &["afup"])
        .add_filter("Tum dosyalar (*.*)", &["*"])
        .blocking_pick_file()
        .and_then(|p| p.into_path().ok());
    match secim {
        None => json!({"ok": true, "iptal": true}),
        Some(yol) => cevap(e.eklenti.incele(&yol.display().to_string())),
    }
}

/// Python `eklenti_klasoru_ac`: plugins klasorunu acar (os.startfile yerine explorer).
fn eklenti_klasoru_ac(k: &Kabuk) -> Json {
    let dizin = k.app_dir.join("plugins");
    if let Err(e) = std::fs::create_dir_all(&dizin) {
        return json!({"ok": false, "error": kes(&e.to_string(), 200)});
    }
    match Command::new("explorer.exe").arg(&dizin).spawn() {
        Ok(_) => json!({"ok": true}),
        Err(e) => json!({"ok": false, "error": kes(&e.to_string(), 200)}),
    }
}

// --- tani: probe, proxy, port, rozet, defender -----------------------------------

fn probe(c: &ApiCtx, url: &str) -> Json {
    match c.manager.probe_video(url) {
        Ok(info) => json!({"ok": true, "info": info}),
        Err(e) => json!({"ok": false, "error": kes(&e.to_string(), 300)}),
    }
}

fn hata_anahtari(anahtar: &str) -> Json {
    json!({"ok": false, "gecikme_ms": 0, "mesaj_anahtari": anahtar})
}

/// Python `_proxy_parcala` + `dogrula_proxy` bicim denetimi. Donus: (tip, host:port).
fn proxy_parcala(ham: &str) -> std::result::Result<(String, String), &'static str> {
    let mut giris = ham;
    let mut tip = "http".to_string();
    if let Some((sekme, geri)) = giris.split_once("://") {
        tip = sekme.trim().to_lowercase();
        giris = geri;
        if !PROXY_TIPLERI.contains(&tip.as_str()) {
            return Err("err.proxyScheme");
        }
    }
    if let Some((_, sonra)) = giris.rsplit_once('@') {
        giris = sonra;
    }
    let giris = giris.trim();
    let Some((host, port_metin)) = giris.split_once(':') else {
        return Err("err.proxyFormat");
    };
    let host_gecerli = !host.is_empty()
        && !host
            .chars()
            .any(|c| c.is_whitespace() || matches!(c, ':' | '/' | '@'));
    let port_bicimi = !port_metin.is_empty() && port_metin.chars().all(|c| c.is_ascii_digit());
    if !host_gecerli || !port_bicimi {
        return Err("err.proxyFormat");
    }
    let port = port_metin.parse::<u64>().unwrap_or(0);
    if !(1..=PROXY_PORT_MAX).contains(&port) {
        return Err("err.proxyPort");
    }
    Ok((tip, giris.to_string()))
}

/// Python `proxy_testi`: bicim denetimi + 4 sn TCP baglanti denemesi.
fn proxy_testi(girdi: &str) -> Json {
    let ham = girdi.trim();
    if ham.is_empty() {
        return hata_anahtari("err.proxyRequired");
    }
    if ham.chars().count() > PROXY_MAX {
        return hata_anahtari("err.proxyLong");
    }
    let hostport = match proxy_parcala(ham) {
        Ok((_, hp)) => hp,
        Err(anahtar) => return hata_anahtari(anahtar),
    };
    let basla = Instant::now();
    let Ok(adresler) = hostport.to_socket_addrs() else {
        return hata_anahtari("err.proxyUnreachable");
    };
    let erisildi = adresler
        .into_iter()
        .any(|a| TcpStream::connect_timeout(&a, PROXY_BAGLANTI_ZAMAN_ASIMI).is_ok());
    if erisildi {
        json!({
            "ok": true,
            "gecikme_ms": basla.elapsed().as_millis() as u64,
            "mesaj_anahtari": "",
        })
    } else {
        hata_anahtari("err.proxyUnreachable")
    }
}

/// Python `port_durumu` (LocalAPI.durum): tercih edilen ve calisan port.
fn port_durumu(k: &Kabuk) -> Json {
    let tercih = i64::from(crate::boot::port_sec());
    let calisan = k.port.get().map_or(0, |p| i64::from(*p));
    json!({
        "ok": true,
        "tercih_edilen": tercih,
        "calisan": calisan,
        "yeniden_baslatma_gerekli": calisan != 0 && calisan != tercih,
    })
}

fn uygulama_zamani(anahtar: &str) -> &'static str {
    UYGULAMA_ZAMANI
        .iter()
        .find(|(k, _)| *k == anahtar)
        .map_or("bilinmiyor", |(_, z)| z)
}

/// Python `ayar_rozetleri`: her ayarin uygulanma zamani.
fn ayar_rozetleri(c: &ApiCtx) -> Sonuc<Json> {
    let ayarlar = c.store.all_settings()?;
    let uygulama: JsonMap = ayarlar
        .keys()
        .map(|anahtar| (anahtar.clone(), json!(uygulama_zamani(anahtar))))
        .collect();
    Ok(json!({"ok": true, "uygulama": uygulama}))
}

fn defender_durum() -> Json {
    kilit(&DEFENDER_DURUM)
        .clone()
        .unwrap_or_else(|| json!({"state": "idle", "path": "", "detail": ""}))
}

/// Python `wait` ile ayni: 600 sn zaman asimi, cikis kodu, stdout/stderr.
fn bekle_cikti(
    mut child: Child,
    sure: Duration,
) -> std::result::Result<(bool, String, String), String> {
    let son = Instant::now() + sure;
    loop {
        match child.try_wait() {
            Ok(Some(durum)) => {
                let mut cikti = String::new();
                if let Some(mut s) = child.stdout.take() {
                    let _ = s.read_to_string(&mut cikti);
                }
                let mut hata_cikti = String::new();
                if let Some(mut s) = child.stderr.take() {
                    let _ = s.read_to_string(&mut hata_cikti);
                }
                return Ok((durum.success(), cikti, hata_cikti));
            }
            Ok(None) => {
                if Instant::now() >= son {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("Defender 600 sn icinde bitmedi.".to_string());
                }
                std::thread::sleep(Duration::from_millis(200));
            }
            Err(e) => return Err(e.to_string()),
        }
    }
}

/// Python `scan_file` arka plan isi: MpCmdRun -Scan -ScanType 3 -File <yol>.
fn defender_calistir(yol: &Path) -> Json {
    let yol_metin = yol.display().to_string();
    let durum = |state: &str, detay: String| json!({"state": state, "path": yol_metin, "detail": kes(&detay, 300)});
    let program = PathBuf::from(
        std::env::var("ProgramFiles").unwrap_or_else(|_| "C:/Program Files".to_string()),
    )
    .join("Windows Defender")
    .join("MpCmdRun.exe");
    if !program.exists() {
        return durum(
            "unavailable",
            "Microsoft Defender command-line tool was not found.".to_string(),
        );
    }
    let mut komut = Command::new(&program);
    komut
        .args(["-Scan", "-ScanType", "3", "-File"])
        .arg(yol)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW);
    let child = match komut.spawn() {
        Ok(c) => c,
        Err(e) => return durum("error", e.to_string()),
    };
    match bekle_cikti(child, DEFENDER_ZAMAN_ASIMI) {
        Ok((basarili, cikti, hata_cikti)) => {
            let detay = if !hata_cikti.is_empty() {
                hata_cikti
            } else if !cikti.is_empty() {
                cikti
            } else {
                "Defender returned a non-zero result.".to_string()
            };
            durum(if basarili { "clean" } else { "warning" }, detay)
        }
        Err(e) => durum("error", e),
    }
}

/// Python `scan_file`: dosya kontrolu, tek tarama kilidi, arka plan thread.
fn defender_tara(yol: PathBuf) -> Json {
    if !yol.is_file() {
        return json!({"ok": false, "error": "taranacak indirilen dosya bulunamadi"});
    }
    if DEFENDER_MESGUL
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_err()
    {
        return json!({"ok": true, "already_running": true, "scan": defender_durum()});
    }
    *kilit(&DEFENDER_DURUM) = Some(json!({
        "state": "running",
        "path": yol.display().to_string(),
        "detail": "",
    }));
    std::thread::spawn(move || {
        let sonuc = defender_calistir(&yol);
        *kilit(&DEFENDER_DURUM) = Some(sonuc);
        DEFENDER_MESGUL.store(false, Ordering::SeqCst);
    });
    json!({"ok": true, "scan": defender_durum()})
}

/// Python `defender_scan`: gid'e ait indirilen dosyayi Defender ile tarar.
fn defender_scan(c: &ApiCtx, gid: &str) -> Json {
    let snap = match c.manager.snapshot() {
        Ok(s) => s,
        Err(e) => return bridge::hata(e.to_string()),
    };
    let ogeler = snap
        .get("items")
        .and_then(Json::as_array)
        .cloned()
        .unwrap_or_default();
    for oge in &ogeler {
        if oge.get("gid").and_then(Json::as_str) != Some(gid) {
            continue;
        }
        let mut dizin = metin_or_bos(oge.get("dir"));
        if dizin.is_empty() {
            match c.manager.current_download_dir() {
                Ok(d) => dizin = d,
                Err(e) => return bridge::hata(e.to_string()),
            }
        }
        let ad = metin_or_bos(oge.get("filename"));
        return defender_tara(PathBuf::from(dizin).join(ad));
    }
    json!({"ok": false, "error": "indirme bulunamadi"})
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn toplu_liste_urls_ve_tek_url_ile_calisir() {
        let mut p = JsonMap::new();
        p.insert("urls".into(), json!(["  https://a.com/x.zip ", "", "   "]));
        assert_eq!(
            toplu_url_listesi(&p),
            vec!["https://a.com/x.zip".to_string()]
        );

        let mut tek = JsonMap::new();
        tek.insert("source".into(), json!(" https://b.com/y.bin "));
        assert_eq!(
            toplu_url_listesi(&tek),
            vec!["https://b.com/y.bin".to_string()]
        );

        assert!(toplu_url_listesi(&JsonMap::new()).is_empty());
    }

    #[test]
    fn indirme_istegi_http_ad_ve_bayraklar() {
        let mut p = JsonMap::new();
        p.insert("quality".into(), json!("720p"));
        p.insert("oto_altyazi".into(), json!(true));
        let istek = indirme_istegi(
            &p,
            "https://a.com/x.zip",
            "http",
            Some("D:/i".into()),
            "x.zip",
            true,
            "",
        );
        assert_eq!(istek["source"], json!("https://a.com/x.zip"));
        assert_eq!(istek["dest_dir"], json!("D:/i"));
        assert_eq!(istek["filename"], json!("x.zip"));
        assert!(istek.get("title").is_none());
        assert_eq!(istek["quality"], json!("720p"));
        assert_eq!(istek["oto_altyazi"], json!(true));
        assert_eq!(istek["kapsayici"], json!(""));
        assert!(istek.get("start_at").is_none());
        assert!(istek.get("adopt_gid").is_none());
    }

    #[test]
    fn indirme_istegi_torrent_ve_zamanlama() {
        let mut p = JsonMap::new();
        p.insert("adopt_gid".into(), json!("abc"));
        let istek = indirme_istegi(
            &p,
            "magnet:?xt=urn:btih:00",
            "torrent",
            None,
            "",
            true,
            "23:30",
        );
        assert_eq!(istek["adopt_gid"], json!("abc"));
        assert_eq!(istek["selected_files"], Json::Null);
        assert_eq!(istek["start_at"], json!("23:30"));
        assert!(istek.get("dest_dir").is_none());
    }

    #[test]
    fn proxy_bicim_denetimi() {
        assert_eq!(
            proxy_parcala("socks5://user:pw@10.0.0.1:1080"),
            Ok(("socks5".to_string(), "10.0.0.1:1080".to_string()))
        );
        assert_eq!(
            proxy_parcala("host:8080"),
            Ok(("http".to_string(), "host:8080".to_string()))
        );
        assert_eq!(proxy_parcala("ftp://h:1"), Err("err.proxyScheme"));
        assert_eq!(proxy_parcala("sadece-host"), Err("err.proxyFormat"));
        assert_eq!(proxy_parcala("h:0"), Err("err.proxyPort"));
        assert_eq!(proxy_parcala("h:65536"), Err("err.proxyPort"));
        assert_eq!(
            proxy_parcala("h:99999999999999999999999"),
            Err("err.proxyPort")
        );
    }

    #[test]
    fn proxy_testi_bos_ve_uzun_girdi() {
        assert_eq!(
            proxy_testi("  ")["mesaj_anahtari"],
            json!("err.proxyRequired")
        );
        let uzun = "a".repeat(PROXY_MAX + 1);
        assert_eq!(proxy_testi(&uzun)["mesaj_anahtari"], json!("err.proxyLong"));
    }

    #[test]
    fn sayi_al_python_int_gibi() {
        assert_eq!(sayi_al(None), Ok(None));
        assert_eq!(sayi_al(Some(&json!(""))), Ok(None));
        assert_eq!(sayi_al(Some(&json!(" 12 "))), Ok(Some(12)));
        assert_eq!(sayi_al(Some(&json!(7.9))), Ok(Some(7)));
        assert_eq!(sayi_al(Some(&json!("abc"))), Err(()));
    }

    #[test]
    fn uuid_biçimi_ve_surumu() {
        let u = uuid_uret();
        assert_eq!(u.len(), 36);
        assert_eq!(u.as_bytes()[14], b'4');
        assert_ne!(u, uuid_uret());
    }

    #[test]
    fn kural_temizle_python_kurallari() {
        let gelen = vec![json!({"name": "  Ad  ", "match_type": "xx", "active": 0})];
        let temiz = kural_temizle(&gelen).expect("gecerli");
        assert_eq!(temiz[0]["name"], json!("Ad"));
        assert_eq!(temiz[0]["match_type"], json!("all"));
        assert_eq!(temiz[0]["active"], json!(false));
        assert_eq!(temiz[0]["conditions"], json!([]));
        assert_eq!(temiz[0]["actions"], json!({}));
        assert!(temiz[0]["id"].as_str().is_some_and(|s| !s.is_empty()));
        assert_eq!(
            kural_temizle(&[json!({"name": "  "})]),
            Err("kural adi gerekli")
        );
    }

    #[test]
    fn uygulama_zamani_tablosu() {
        assert_eq!(uygulama_zamani("proxy"), "yeni_indirmelerde");
        assert_eq!(uygulama_zamani("max_speed_kb"), "hemen");
        assert_eq!(uygulama_zamani("max_upload_kb"), "hemen");
        assert_eq!(uygulama_zamani("bilinmeyen_ayar"), "bilinmiyor");
    }

    #[test]
    fn linkgrabber_analiz_ve_filtre() {
        let metin_girdi = "https://a.com/film.mp4 https://a.com/x.zip https://a.com/x.zip";
        let mut f = JsonMap::new();
        f.insert("sadece".into(), json!(["arsiv"]));
        let cikti = linkgrabber_analiz(metin_girdi, &f);
        assert_eq!(cikti["toplam"], json!(1));
        assert_eq!(cikti["ogeler"][0]["url"], json!("https://a.com/x.zip"));
    }

    #[test]
    fn linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar() {
        let ogeler = vec![json!({"url": "https://a.com/x.zip", "size": 100})];
        let mut f = JsonMap::new();
        f.insert("min_boyut".into(), json!("abc"));
        f.insert("max_boyut".into(), json!(50));
        let cikti = linkgrabber_suz(&ogeler, &f);
        assert_eq!(cikti["gosterilen"], json!(1));
    }

    #[test]
    fn kural_simule_eslesme_ve_catisma_yok() {
        let mut varsayilan = JsonMap::new();
        varsayilan.insert("dest_dir".into(), json!("D:/i"));
        let tum: Vec<Json> = Vec::new();
        let cikti = kural_simule(
            &tum,
            &varsayilan,
            "https://a.com/x.zip",
            "",
            0.0,
            "http",
            "",
        )
        .expect("simule");
        assert_eq!(cikti["matched_rules"], json!([]));
        assert_eq!(cikti["conflicts"], json!([]));
        assert_eq!(cikti["ok"], json!(true));
    }

    #[test]
    fn probe_ogeleri_eksik_sonuc_varsayilani() {
        let urller = vec!["https://a.com/x.zip".to_string()];
        let sonuclar: HashMap<String, Json> = HashMap::new();
        let ogeler = probe_ogeleri(&urller, &sonuclar);
        assert_eq!(ogeler[0]["ok"], json!(false));
        assert_eq!(ogeler[0]["size"], Json::Null);
        assert_eq!(ogeler[0]["resumable"], json!(false));
    }

    #[test]
    fn defender_durum_varsayilani_idle() {
        // Tarama baslatilmamissa durum "idle" olmali (Python __init__ ile ayni).
        assert_eq!(defender_durum()["state"], json!("idle"));
    }
}
