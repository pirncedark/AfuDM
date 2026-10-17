//! Arayuz koprusu: arayuzdeki `window.pywebview.api.<ad>(...)` cagrilari tek
//! `api_call(name, args)` komutuna gelir (ui/tauri_kopru.js).
//! - Pencere ve indirme-soru penceresi metotlari yerelde karsilanir.
//! - Motor (Manager), store ve kabuk (klasor, baslangic, iliskilendirme) metotlari baglanir.
//! - Bagli olmayan her ad "henüz yok" doner (SONUC_F.md listesi).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex, MutexGuard, OnceLock, PoisonError};

use afudm_extras::g1::{guncelleme::Guncelleme, reliability};
use afudm_engine::IdleRpc;
use afudm_extras::g1::automation::Otomasyon;
use afudm_extras::g2::eklenti_servis::EklentiServisi;
use afudm_types::{Aria2, ApiCtx, Json, JsonMap, ManagerApi, UiBridge};
use serde_json::json;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

use crate::{entegrasyon, window::{self, ANA}};

type Sonuc = afudm_types::Result<Json>;

fn kilit<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(PoisonError::into_inner)
}

fn henuz_yok() -> Json {
    json!({"ok": false, "error": "henüz yok"})
}

fn hata(metin: impl Into<String>) -> Json {
    json!({"ok": false, "error": metin.into()})
}

fn motor_hazir_degil() -> Json {
    hata("motor henüz hazır değil")
}

fn cevap(r: Sonuc) -> Json {
    match r {
        Ok(v) => v,
        Err(e) => hata(e.to_string()),
    }
}

fn s(a: &[Json], i: usize) -> &str {
    a.get(i).and_then(Json::as_str).unwrap_or("")
}

fn b(a: &[Json], i: usize) -> bool {
    a.get(i).and_then(Json::as_bool).unwrap_or(false)
}

fn n(a: &[Json], i: usize) -> i64 {
    a.get(i).and_then(Json::as_i64).unwrap_or(0)
}

fn sayilar(a: &[Json], i: usize) -> Vec<i64> {
    a.get(i)
        .and_then(Json::as_array)
        .map(|v| v.iter().filter_map(Json::as_i64).collect())
        .unwrap_or_default()
}

// --- kabuk durumu --------------------------------------------------------------

struct Bekleyen {
    istek: JsonMap,
    yanit: mpsc::Sender<Option<JsonMap>>,
}

/// Indirme sorusu (Python: bekleyen_*). `ask_save_location` cagiran thread'i
/// kullanici yanitlayana dek bekletir; pencere kapanirsa None (iptal) doner.
pub struct TauriUi {
    app: AppHandle,
    sayac: Mutex<i64>,
    bekleyen: Mutex<BTreeMap<i64, Bekleyen>>,
    pub lg: Arc<LinkGrabberDurum>,
}

/// LinkGrabber teslimi (Python linkgrabber_devret + sayfa_hazir): metin, UI yuklenene dek bekler.
pub struct LinkGrabberDurum {
    bekleyen: Mutex<Option<(String, bool)>>,
    hazir: AtomicBool,
}

/// Bekleyen LinkGrabber metnini ana pencereye `window.afudmLinkgrabber(metin, dosya)` ile iletir.
fn lg_teslim_et(app: &AppHandle, lg: &LinkGrabberDurum) {
    if !lg.hazir.load(Ordering::SeqCst) {
        return;
    }
    let Some((metin, dosya)) = kilit(&lg.bekleyen).take() else {
        return;
    };
    if let Some(w) = app.get_webview_window(ANA) {
        let js = format!("window.afudmLinkgrabber({}, {})", json!(metin), dosya);
        let _ = w.eval(&js);
    }
}

impl TauriUi {
    fn new(app: AppHandle) -> Self {
        Self {
            app,
            sayac: Mutex::new(0),
            bekleyen: Mutex::new(BTreeMap::new()),
            lg: Arc::new(LinkGrabberDurum {
                bekleyen: Mutex::new(None),
                hazir: AtomicBool::new(false),
            }),
        }
    }

    /// Indirme penceresi kapandi: bekleyen tum istekler iptal.
    pub fn iptal_hepsi(&self) {
        for (_, b) in std::mem::take(&mut *kilit(&self.bekleyen)) {
            let _ = b.yanit.send(None);
        }
    }

    pub(crate) fn listele(&self) -> Vec<Json> {
        kilit(&self.bekleyen)
            .iter()
            .map(|(kimlik, b)| {
                let mut oge = b.istek.clone();
                oge.insert("kimlik".into(), json!(kimlik));
                Json::Object(oge)
            })
            .collect()
    }

    fn onayla(&self, kimlik: i64, secim: JsonMap) -> bool {
        let Some(b) = kilit(&self.bekleyen).remove(&kimlik) else {
            return false;
        };
        let mut sonuc = b.istek;
        sonuc.extend(secim);
        let _ = b.yanit.send(Some(sonuc));
        self.bos_ise_kapat();
        true
    }

    fn iptal(&self, kimlik: i64) -> bool {
        let Some(b) = kilit(&self.bekleyen).remove(&kimlik) else {
            return false;
        };
        let _ = b.yanit.send(None);
        self.bos_ise_kapat();
        true
    }

    fn bos_ise_kapat(&self) {
        if kilit(&self.bekleyen).is_empty() {
            let app = self.app.clone();
            let _ = self.app.run_on_main_thread(move || window::indirme_kapat(&app));
        }
    }
}

impl UiBridge for TauriUi {
    fn show_window(&self) {
        let app = self.app.clone();
        let _ = self.app.run_on_main_thread(move || window::goster(&app));
    }

    fn open_linkgrabber(&self, metin: &str, uyari: bool) -> bool {
        *kilit(&self.lg.bekleyen) = Some((metin.to_string(), uyari));
        let app = self.app.clone();
        let lg = self.lg.clone();
        self.app
            .run_on_main_thread(move || {
                window::goster(&app);
                lg_teslim_et(&app, &lg);
            })
            .is_ok()
    }

    fn ask_save_location(&self, req: &JsonMap) -> Option<JsonMap> {
        let (tx, rx) = mpsc::channel();
        let kimlik = {
            let mut s = kilit(&self.sayac);
            *s += 1;
            *s
        };
        kilit(&self.bekleyen).insert(
            kimlik,
            Bekleyen {
                istek: req.clone(),
                yanit: tx,
            },
        );
        let app = self.app.clone();
        let acildi = self
            .app
            .run_on_main_thread(move || {
                let _ = window::indirme_goster(&app);
            })
            .is_ok();
        if !acildi {
            kilit(&self.bekleyen).remove(&kimlik);
            return None;
        }
        rx.recv().ok().flatten()
    }
}

/// Boot'ta kurulan ek servisler; HTTP ve kopru ayni ornekleri paylasir.
pub struct Ek {
    pub eklenti: EklentiServisi,
    pub guncelleme: Arc<Guncelleme>,
    pub otomasyon: Arc<Otomasyon>,
    pub rpc: Arc<IdleRpc>,
    /// queue::probe_url_info ve guess_name somut Manager ister (ApiCtx dyn tutar).
    pub core: Arc<afudm_core::Manager>,
}

/// Python kaydet.KATEGORI_KLASORU anahtarlari.
const KATEGORILER: [&str; 9] = [
    "telefon", "video", "muzik", "belge", "program", "arsiv", "resim", "torrent", "genel",
];

/// Python app.kaydet_bilgi: indirme penceresi icin kind/kategori/klasor bilgisi.
fn kaydet_bilgi(c: &ApiCtx, url: &str, dosya_adi: &str, kind: &str) -> Sonuc {
    let url = url.trim();
    let kind = if !kind.is_empty() {
        kind.to_string()
    } else if !url.is_empty() {
        afudm_core::queue::detect_kind(url).to_string()
    } else {
        String::new()
    };
    let kategori = if url.is_empty() {
        "genel".to_string()
    } else {
        afudm_db::kaydet::kategori_tahmin(url, &kind, dosya_adi)
    };
    let ana = c.manager.current_download_dir()?;
    let ad = if !url.is_empty() && kind == "http" {
        afudm_core::queue::guess_name(url)
    } else {
        String::new()
    };
    let son_klasor = match c.store.get("son_klasor")? {
        Some(Json::Object(m)) if m.get("ana").and_then(Json::as_str) == Some(ana.as_str()) => {
            m.get("yol").and_then(Json::as_str).unwrap_or("").to_string()
        }
        _ => String::new(),
    };
    let klasor_ler = KATEGORILER
        .iter()
        .map(|k| ((*k).to_string(), json!(afudm_db::kaydet::kategori_klasoru(&ana, k))))
        .collect::<JsonMap>();
    Ok(json!({
        "ok": true,
        "kind": kind,
        "kategori": kategori,
        "video_quality": c.store.get("video_quality")?.unwrap_or(json!("best")),
        "dosya_adi": ad,
        "ana": ana,
        "son_klasor": son_klasor,
        "kategori_klasorleri": c.store.get("kategori_klasorleri")?.is_some_and(|v| truthy(&v)),
        "klasorler": klasor_ler,
    }))
}

fn truthy(v: &Json) -> bool {
    match v {
        Json::Bool(b) => *b,
        Json::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
        Json::Null => false,
    }
}

/// Python app.probe_link: HTTP(S) icin HEAD + Range GET ile ad/boyut/tur.
fn probe_link(k: &Kabuk, url: &str) -> Json {
    let url = url.trim();
    let Some(e) = k.ek.get() else {
        return motor_hazir_degil();
    };
    if !(url.to_lowercase().starts_with("http://") || url.to_lowercase().starts_with("https://")) {
        return json!({"ok": false});
    }
    match afudm_core::queue::probe_url_info(&e.core, url) {
        Ok(v) => {
            let ad = v.get("filename").and_then(Json::as_str).unwrap_or("").to_string();
            json!({
                "ok": v.get("ok").and_then(Json::as_bool).unwrap_or(false),
                "filename": ad,
                "size": v.get("size").cloned().unwrap_or(Json::Null),
                "content_type": v.get("content_type").cloned().unwrap_or(Json::Null),
                "kategori": afudm_db::kaydet::kategori_tahmin(url, "http", &ad),
                "resumable": v.get("resumable").and_then(Json::as_bool).unwrap_or(false),
            })
        }
        Err(err) => hata(err.to_string()),
    }
}

/// Tauri state: pencere, motor baglantisi ve boot durumu.
pub struct Kabuk {
    pub app_dir: PathBuf,
    pub ui: Arc<TauriUi>,
    pub ctx: OnceLock<ApiCtx>,
    pub ek: OnceLock<Ek>,
    pub port: OnceLock<u16>,
    app: AppHandle,
    boot_hata: Mutex<Option<String>>,
}

impl Kabuk {
    pub fn new(app: AppHandle, app_dir: PathBuf) -> Self {
        Self {
            app_dir,
            ui: Arc::new(TauriUi::new(app.clone())),
            ctx: OnceLock::new(),
            ek: OnceLock::new(),
            port: OnceLock::new(),
            app,
            boot_hata: Mutex::new(None),
        }
    }

    pub fn boot_hatasi(&self, hata: String) {
        *kilit(&self.boot_hata) = Some(hata);
    }

    fn boot_hata_metni(&self) -> Option<String> {
        kilit(&self.boot_hata).clone()
    }

    fn manager(&self) -> Option<&dyn ManagerApi> {
        self.ctx.get().map(|c| c.manager.as_ref())
    }

    fn ag_ayari(&self) -> String {
        self.ctx
            .get()
            .and_then(|c| c.store.get("ag_konumlari").ok().flatten())
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_default()
    }
}

fn ctx_cagri(k: &Kabuk, f: impl FnOnce(&ApiCtx) -> Sonuc) -> Json {
    match k.ctx.get() {
        Some(c) => cevap(f(c)),
        None => motor_hazir_degil(),
    }
}

fn ek_ctx_cagri(k: &Kabuk, f: impl FnOnce(&Ek, &ApiCtx) -> Sonuc) -> Json {
    match (k.ek.get(), k.ctx.get()) {
        (Some(e), Some(c)) => cevap(f(e, c)),
        _ => motor_hazir_degil(),
    }
}

/// Snapshot'ta aktif (status == "active") bir indirme var mi; guncelleme uygulamayi engeller.
pub(crate) fn aktif_var(v: &Json) -> bool {
    match v {
        Json::Object(m) => {
            m.get("status").and_then(Json::as_str) == Some("active") || m.values().any(aktif_var)
        }
        Json::Array(a) => a.iter().any(aktif_var),
        _ => false,
    }
}

fn motor_cagri(k: &Kabuk, f: impl FnOnce(&dyn ManagerApi) -> Sonuc) -> Json {
    match k.manager() {
        Some(m) => cevap(f(m)),
        None => motor_hazir_degil(),
    }
}

fn gezgin_ac(yol: &Path, sec: bool) {
    let mut komut = Command::new("explorer.exe");
    if sec {
        komut.arg(format!("/select,{}", yol.display()));
    } else {
        komut.arg(yol);
    }
    let _ = komut.spawn();
}

fn api_info(k: &Kabuk) -> Json {
    let Some(port) = k.port.get() else {
        return motor_hazir_degil();
    };
    let token = fs::read_to_string(afudm_db::paths::token_file(&afudm_db::paths::data_dir(&k.app_dir)))
        .map(|t| t.trim().to_string())
        .unwrap_or_default();
    json!({"ok": true, "port": port, "token": token})
}

fn motor_durumu(k: &Kabuk) -> Json {
    let mut motorlar = JsonMap::new();
    for ad in ["aria2c", "yt-dlp", "ffmpeg", "cloudflared"] {
        let kaynak = if afudm_engine::engines::var_mi(&k.app_dir, ad) {
            "paket"
        } else if !afudm_engine::engines::sistemde(&k.app_dir, ad).is_empty() {
            "sistem"
        } else {
            "yok"
        };
        motorlar.insert(ad.into(), json!({"kaynak": kaynak}));
    }
    json!({"ok": true, "motorlar": motorlar, "ilerleme": {}})
}

fn windows_durumu(k: &Kabuk) -> Json {
    let (torrent, magnet) = entegrasyon::iliskilendirme_durumu();
    let kayitli = |anahtar: &str| {
        k.ctx
            .get()
            .and_then(|c| c.store.get(anahtar).ok().flatten())
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
    };
    let defender = std::env::var("ProgramFiles")
        .map(|p| PathBuf::from(p).join("Windows Defender").join("MpCmdRun.exe").exists())
        .unwrap_or(false);
    json!({"ok": true, "integrations": {
        "torrent": {"registered": torrent && magnet, "scope": "current_user"},
        "startup": {"registered": entegrasyon::baslangic_acik(), "scope": "current_user"},
        "protocol": {"registered": entegrasyon::protokol_kayitli(), "scope": "current_user"},
        "notify": {"registered": kayitli("windows_notifications"), "scope": "current_user"},
        "defender": {"registered": kayitli("defender_auto_scan"), "scope": "current_user", "available": defender},
    }})
}

/// Python windows_integration_apply / remove. `ac` true ise uygular.
fn windows_uygula(k: &Kabuk, ident: &str, ac: bool) -> Json {
    let sonuc: Result<(), String> = match (ident, ac) {
        ("torrent", true) => entegrasyon::iliskilendir_ac().map_err(|e| e.to_string()),
        ("torrent", false) => {
            entegrasyon::iliskilendir_kapat();
            Ok(())
        }
        ("startup", true) => entegrasyon::baslangic_ac("--tepside").map_err(|e| e.to_string()),
        ("startup", false) => entegrasyon::baslangic_kapat().map_err(|e| e.to_string()),
        ("protocol", true) => entegrasyon::protokol_ac().map_err(|e| e.to_string()),
        ("protocol", false) => {
            entegrasyon::protokol_kapat();
            Ok(())
        }
        ("notify" | "defender", _) => {
            let anahtar = if ident == "notify" { "windows_notifications" } else { "defender_auto_scan" };
            match k.ctx.get() {
                Some(c) => c
                    .store
                    .set(anahtar, json!(ac))
                    .map_err(|e| e.to_string()),
                None => return motor_hazir_degil(),
            }
        }
        _ => return henuz_yok(),
    };
    match sonuc {
        Ok(()) => windows_durumu(k),
        Err(e) => hata(e),
    }
}

fn windows_test(ident: &str) -> Json {
    match ident {
        "torrent" => {
            let (t, m) = entegrasyon::iliskilendirme_durumu();
            json!({"ok": t && m, "registered": t && m})
        }
        "startup" => json!({"ok": entegrasyon::baslangic_acik(), "registered": entegrasyon::baslangic_acik()}),
        "protocol" => json!({"ok": entegrasyon::protokol_kayitli(), "registered": entegrasyon::protokol_kayitli()}),
        _ => henuz_yok(),
    }
}

fn kayit_bulunamadi() -> String {
    "kayıt bulunamadı".into()
}

/// Python app.settings_save / ayarlari_dogrula_kaydet (hata ayrintisi yok: update_settings
/// tek hata dondurur; Python'daki alan bazli hatalar burada uretilmez).
fn ayar_kaydet(c: &ApiCtx, payload: &JsonMap) -> Sonuc {
    match c.manager.update_settings(payload) {
        Ok(kayit) => Ok(json!({"ok": true, "hatalar": [], "ayarlar": kayit, "settings": kayit})),
        Err(_) => Ok(json!({
            "ok": false,
            "hatalar": [{"alan": "_genel", "mesaj_anahtari": "err.invalidValue"}],
            "ayarlar": c.store.all_settings()?,
        })),
    }
}

/// Python item_yolu: kayit icin kaynak adres ve diskteki tam yol.
fn item_yolu(c: &ApiCtx, gid: &str) -> Sonuc {
    let Some(row) = c.store.by_gid(gid)? else {
        return Ok(hata(kayit_bulunamadi()));
    };
    let mut klasor = row
        .get("dest_dir")
        .and_then(Json::as_str)
        .filter(|d| !d.is_empty())
        .map(String::from)
        .unwrap_or(c.manager.current_download_dir()?);
    let mut ad = row.get("filename").and_then(Json::as_str).unwrap_or("").to_string();
    if let Some(hedef) = c.manager.resolve_item_path(gid)? {
        if let (Some(p), Some(n)) = (hedef.parent(), hedef.file_name()) {
            klasor = p.display().to_string();
            ad = n.to_string_lossy().into_owned();
        }
    }
    let yol = if ad.is_empty() { klasor.clone() } else { PathBuf::from(&klasor).join(&ad).display().to_string() };
    Ok(json!({
        "ok": true,
        "url": row.get("source").and_then(Json::as_str).unwrap_or(""),
        "klasor": klasor,
        "ad": ad,
        "yol": yol,
    }))
}

/// Python dosya_ac: dosya varsa kendi programiyla, yoksa klasoru acar (Explorer).
fn dosya_ac(c: &ApiCtx, gid: &str) -> Sonuc {
    if c.store.by_gid(gid)?.is_none() {
        return Ok(hata(kayit_bulunamadi()));
    }
    let hedef = c.manager.resolve_item_path(gid)?;
    match hedef {
        Some(yol) if yol.is_file() => gezgin_ac(&yol, false),
        _ => {
            let klasor = c.manager.current_download_dir()?;
            gezgin_ac(Path::new(&klasor), false);
        }
    }
    Ok(json!({"ok": true}))
}

/// Python chrome_kurulum.panoya_kopyala: `clip` UTF-16LE girdi ile.
fn panoya_yaz(metin: &str) -> bool {
    use std::io::Write;
    let mut cocuk = match hidden_cmd("clip").stdin(std::process::Stdio::piped()).spawn() {
        Ok(c) => c,
        Err(_) => return false,
    };
    if let Some(mut girdi) = cocuk.stdin.take() {
        let bayt: Vec<u8> = metin.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let _ = girdi.write_all(&bayt);
    }
    cocuk.wait().map(|s| s.success()).unwrap_or(false)
}

/// Python clipboard.read_text: pano metni; bos pano bos metin.
fn panodan_oku() -> Json {
    let cikti = hidden_cmd("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw",
        ])
        .output();
    match cikti {
        Ok(o) if o.status.success() => json!({
            "ok": true,
            "metin": String::from_utf8_lossy(&o.stdout).trim_end_matches(['\r', '\n']),
        }),
        Ok(o) => hata(String::from_utf8_lossy(&o.stderr).trim().chars().take(200).collect::<String>()),
        Err(e) => hata(e.to_string()),
    }
}

/// Konsol penceresi acmayan surec (CREATE_NO_WINDOW).
fn hidden_cmd(program: &str) -> Command {
    let mut komut = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(0x0800_0000);
    }
    komut
}

/// Tek giris noktasi. Motor/store cagrilari `spawn_blocking` icinde calisir.
fn dispatch(k: &Kabuk, name: &str, a: &[Json]) -> Json {
    match name {
        // --- pencere ---
        "pencere_durumu" => {
            let buyuk = k
                .app
                .get_webview_window(ANA)
                .and_then(|w| w.is_maximized().ok())
                .unwrap_or(false);
            json!({"ozel": true, "buyuk": buyuk})
        }
        "pencere_buyut" => {
            if let Some(w) = k.app.get_webview_window(ANA) {
                let buyuk = w.is_maximized().unwrap_or(false);
                let _ = if buyuk { w.unmaximize() } else { w.maximize() };
            }
            json!({"ok": true})
        }
        "pencere_surukle" => {
            if let Some(w) = k.app.get_webview_window(ANA) {
                let _ = w.start_dragging();
            }
            json!({"ok": true})
        }
        "pencere_kucult" => {
            if let Some(w) = k.app.get_webview_window(ANA) {
                let _ = w.minimize();
            }
            json!({"ok": true})
        }
        "pencere_kapat" => {
            window::ana_kapat(&k.app);
            json!({"ok": true})
        }
        "pencere_kenar" => {
            if let (Some(w), Some(y)) = (k.app.get_webview_window(ANA), kenar_yonu(s(a, 0))) {
                let _ = w.as_ref().window().start_resize_dragging(y);
            }
            json!({"ok": true})
        }
        "kapat" => {
            window::indirme_kapat(&k.app);
            json!({"ok": true})
        }
        "bekleyen_listesi" => json!({"ok": true, "ogeler": k.ui.listele()}),
        "bekleyen_onayla" => {
            let secim = a.get(1).and_then(Json::as_object).cloned().unwrap_or_default();
            if k.ui.onayla(n(a, 0), secim) {
                json!({"ok": true})
            } else {
                hata("istek bulunamadi")
            }
        }
        "bekleyen_iptal" => {
            if k.ui.iptal(n(a, 0)) {
                json!({"ok": true})
            } else {
                hata("istek bulunamadi")
            }
        }

        // --- kabuk durumu ---
        "api_info" => api_info(k),
        "surum_bilgi" => json!({"ok": true, "surum": env!("CARGO_PKG_VERSION"), "uzanti": null}),
        "motor_durumu" => motor_durumu(k),
        "sistem_durumu" => {
            let (t, m) = entegrasyon::iliskilendirme_durumu();
            json!({
                "ok": true,
                "baslangic": entegrasyon::baslangic_acik(),
                "torrent": {"kayitli": t && m, "torrent": t, "magnet": m},
                "boot_hata": k.boot_hata_metni(),
            })
        }
        "baslangic_ayarla" => {
            let sonuc = if b(a, 0) {
                entegrasyon::baslangic_ac(if a.get(1).and_then(Json::as_bool).unwrap_or(true) { "--tepside" } else { "" })
                    .map_err(|e| e.to_string())
            } else {
                entegrasyon::baslangic_kapat().map_err(|e| e.to_string())
            };
            match sonuc {
                Ok(()) => json!({"ok": true, "acik": entegrasyon::baslangic_acik()}),
                Err(e) => hata(e),
            }
        }
        "varsayilan_uygulama_ekrani" => {
            let _ = Command::new("explorer.exe").arg("ms-settings:defaultapps").spawn();
            json!({"ok": true})
        }
        "torrent_iliskilendir" => {
            let sonuc = if b(a, 0) {
                entegrasyon::iliskilendir_ac().map_err(|e| e.to_string())
            } else {
                entegrasyon::iliskilendir_kapat();
                Ok(())
            };
            match sonuc {
                Ok(()) => json!({"ok": true, "durum": windows_durumu(k)["integrations"]["torrent"].clone()}),
                Err(e) => hata(e),
            }
        }
        "windows_integration_status" => windows_durumu(k),
        "windows_integration_apply" => windows_uygula(k, s(a, 0), true),
        "windows_integration_remove" => windows_uygula(k, s(a, 0), false),
        "windows_integration_test" => windows_test(s(a, 0)),

        // --- klasor ve yollar ---
        "klasor_kisayollar" => match k.ctx.get() {
            Some(c) => match c.manager.current_download_dir() {
                Ok(ana) => json!({"ok": true, "ogeler": afudm_db::kaydet::kisayollar(&ana, &k.ag_ayari())}),
                Err(e) => hata(e.to_string()),
            },
            None => motor_hazir_degil(),
        },
        "ag_konumu_ekle" => match (k.ctx.get(), afudm_db::kaydet::ag_konumu_dogrula(s(a, 0))) {
            (Some(c), Ok(temiz)) => {
                let mut mevcut = afudm_db::kaydet::ag_konumlari(&k.ag_ayari());
                if !mevcut.contains(&temiz) {
                    mevcut.push(temiz.clone());
                }
                match c.store.set("ag_konumlari", json!(mevcut.join("\n"))) {
                    Ok(()) => json!({"ok": true, "yol": temiz, "sayi": mevcut.len()}),
                    Err(e) => hata(e.to_string()),
                }
            }
            (None, _) => motor_hazir_degil(),
            (_, Err(e)) => hata(e.to_string()),
        },
        "ag_konumu_sil" => match k.ctx.get() {
            Some(c) => {
                let yol = s(a, 0).trim();
                let kalan: Vec<String> = afudm_db::kaydet::ag_konumlari(&k.ag_ayari())
                    .into_iter()
                    .filter(|y| y != yol)
                    .collect();
                match c.store.set("ag_konumlari", json!(kalan.join("\n"))) {
                    Ok(()) => json!({"ok": true, "sayi": kalan.len()}),
                    Err(e) => hata(e.to_string()),
                }
            }
            None => motor_hazir_degil(),
        },
        "klasor_alt" => match afudm_db::kaydet::alt_klasorler(s(a, 0), 500) {
            Ok(ogeler) => json!({"ok": true, "ogeler": ogeler}),
            Err(e) => hata(e.to_string()),
        },
        "klasor_yeni" => match afudm_db::kaydet::klasor_olustur(s(a, 0), s(a, 1)) {
            Ok(yol) => json!({"ok": true, "yol": yol}),
            Err(e) => hata(e.to_string()),
        },
        "klasor_gozat" => {
            let baslangic = match s(a, 0) {
                "" => k.manager().and_then(|m| m.current_download_dir().ok()).unwrap_or_default(),
                yol => yol.to_string(),
            };
            // Dialog ana thread'de calisir; bu cagri spawn_blocking worker'inda beklenir.
            let secim = k
                .app
                .dialog()
                .file()
                .set_directory(baslangic)
                .blocking_pick_folder()
                .and_then(|p| p.into_path().ok());
            json!({"ok": true, "yol": secim.map(|p| p.display().to_string()).unwrap_or_default()})
        }
        "open_download_dir" => match k.manager().map(|m| m.current_download_dir()) {
            Some(Ok(ana)) => {
                gezgin_ac(Path::new(&ana), false);
                json!({"ok": true})
            }
            Some(Err(e)) => hata(e.to_string()),
            None => motor_hazir_degil(),
        },
        "open_item_folder" => match k.manager().map(|m| m.resolve_item_path(s(a, 0))) {
            Some(Ok(Some(yol))) if yol.exists() => {
                gezgin_ac(&yol, true);
                json!({"ok": true})
            }
            Some(Ok(_)) => hata("dosya bulunamadi"),
            Some(Err(e)) => hata(e.to_string()),
            None => motor_hazir_degil(),
        },

        // --- reliability (G1) ---
        "reliability_integrity" => ctx_cagri(k, |c| reliability::integrity(&*c.store)),
        "reliability_backup" => ctx_cagri(k, |c| reliability::backup(&*c.store, &c.data_dir, "manual")),
        "reliability_backups" => match k.ctx.get() {
            Some(c) => reliability::backups(&c.data_dir),
            None => motor_hazir_degil(),
        },
        "reliability_diagnostics_preview" => {
            ctx_cagri(k, |c| reliability::diagnostics_preview(&*c.store, &c.app_dir))
        }
        "reliability_diagnostics_export" => {
            ctx_cagri(k, |c| reliability::diagnostics_export(&*c.store, &c.data_dir, &c.app_dir))
        }
        "reliability_restore" => ctx_cagri(k, |c| reliability::restore(&*c.store, &c.data_dir, s(a, 0))),
        "reliability_health" => match k.ek.get() {
            Some(e) => json!({"ok": true, "rpc_alive": e.rpc.alive(), "uyku": e.rpc.sleeping()}),
            None => motor_hazir_degil(),
        },
        "reliability_restart_engine" => match k.ek.get() {
            Some(e) => match e.rpc.restart() {
                Ok(()) => json!({"ok": e.rpc.alive(), "message": "motor yeniden baslatildi"}),
                Err(err) => hata(err.to_string()),
            },
            None => motor_hazir_degil(),
        },

        // --- guncelleme (G1) ---
        "guncelleme_kontrol" => match k.ek.get() {
            Some(e) => e.guncelleme.kontrol_ve_kaydet(),
            None => motor_hazir_degil(),
        },
        "guncelleme_durum" => match k.ek.get() {
            Some(e) => e.guncelleme.durum(),
            None => motor_hazir_degil(),
        },
        "guncelleme_otomatik_ayarla" => {
            ek_ctx_cagri(k, |e, c| e.guncelleme.otomatik_ayarla(&*c.store, b(a, 0)))
        }
        "guncelleme_son_kontrol" => ek_ctx_cagri(k, |e, c| e.guncelleme.son_kontrol(&*c.store)),
        "guncelleme_indir" => match k.ek.get() {
            Some(e) => e.guncelleme.clone().indir(a.first().cloned().unwrap_or(json!({}))),
            None => motor_hazir_degil(),
        },
        "guncelleme_uygula" => match (k.ek.get(), k.ctx.get()) {
            (Some(e), Some(c)) => {
                let bekleyen = c.manager.snapshot().map(|s| aktif_var(&s)).unwrap_or(true);
                let snap = || c.manager.snapshot();
                e.guncelleme.uygula(&*c.store, &snap, bekleyen, b(a, 0), b(a, 1))
            }
            _ => motor_hazir_degil(),
        },

        // --- otomasyon (G1) ---
        "automation_retry" => ek_ctx_cagri(k, |e, _| e.otomasyon.retry(n(a, 0))),
        "automation_cancel" => ek_ctx_cagri(k, |e, _| e.otomasyon.cancel(n(a, 0))),

        // --- eklenti (G2): HTTP ile ayni servis ornegi ---
        "eklenti_listesi" => ek_ctx_cagri(k, |e, _| e.eklenti.liste()),
        "eklenti_etkinlestir" => ek_ctx_cagri(k, |e, _| e.eklenti.etkinlestir(s(a, 0), b(a, 1))),

        // --- motor (Manager) ---
        "snapshot" => motor_cagri(k, |m| m.snapshot()),
        "peers" => motor_cagri(k, |m| m.peers(s(a, 0)).map(|v| json!({"ok": true, "peers": v}))),
        "seed_bilgi" => motor_cagri(k, |m| m.seed_bilgi(s(a, 0))),
        "seed_tazele" => motor_cagri(k, |m| m.seed_tazele(s(a, 0))),
        "seed_dosyalari" => motor_cagri(k, |m| m.seed_dosyalari()),
        "seed_dosya_ekle" => motor_cagri(k, |m| m.seed_dosya_ekle(s(a, 0))),
        "seed_dosya_sil" => motor_cagri(k, |m| m.seed_dosya_sil(s(a, 0))),
        "tracker_tara" => motor_cagri(k, |m| m.tracker_tara(s(a, 0))),
        "torrent_on_ekle" => motor_cagri(k, |m| {
            m.torrent_on_ekle(s(a, 0)).map(|gid| json!({"ok": true, "gid": gid}))
        }),
        "torrent_on_iptal" => motor_cagri(k, |m| {
            m.torrent_on_iptal(s(a, 0)).map(|_| json!({"ok": true}))
        }),
        "torrent_dosyalari" => motor_cagri(k, |m| {
            let gid = s(a, 0);
            m.torrent_dosyalari(gid).map(|v| {
                json!({
                    "ok": true,
                    "gid": v.get("gid").cloned().unwrap_or(json!(gid)),
                    "hazir_degil": v.get("hazir_degil").and_then(Json::as_bool).unwrap_or(false),
                    "neden": v.get("neden").cloned().unwrap_or(json!("")),
                    "dosyalar": v.get("dosyalar").cloned().unwrap_or(json!([])),
                })
            })
        }),
        "torrent_secimi_ayarla" => motor_cagri(k, |m| m.torrent_secimi_ayarla(s(a, 0), &sayilar(a, 1))),
        "torrent_metrikleri" => motor_cagri(k, |m| {
            let gid = s(a, 0);
            m.torrent_metrikleri(gid).map(|v| {
                let hazir_degil = v.get("hazir_degil").and_then(Json::as_bool).unwrap_or(false);
                json!({
                    "ok": true,
                    "gid": gid,
                    "hazir_degil": hazir_degil,
                    "neden": v.get("neden").cloned().unwrap_or(json!("")),
                    "metrikler": if hazir_degil { json!({}) } else { v.clone() },
                })
            })
        }),
        "control" => motor_cagri(k, |m| {
            let gid = s(a, 1);
            match s(a, 0) {
                "pause" => m.pause(gid).map(|_| json!({"ok": true})),
                "resume" => m.resume(gid).map(|_| json!({"ok": true})),
                "remove" => m.remove(gid, b(a, 2)).map(|_| json!({"ok": true})),
                _ => Ok(hata("bilinmeyen islem")),
            }
        }),
        "retry" => motor_cagri(k, |m| m.retry(n(a, 0))),

        "kaydet_bilgi" => match k.ctx.get() {
            Some(c) => cevap(kaydet_bilgi(c, s(a, 0), s(a, 1), s(a, 2))),
            None => motor_hazir_degil(),
        },
        "probe_link" => probe_link(k, s(a, 0)),
        "settings_save" => ctx_cagri(k, |c| {
            ayar_kaydet(c, &a.first().and_then(Json::as_object).cloned().unwrap_or_default())
        }),
        "clear_finished" => ctx_cagri(k, |c| {
            c.store.clear_finished().map(|n| json!({"ok": true, "removed": n}))
        }),
        "loglar" => ctx_cagri(k, |c| {
            c.store.recent_events(50, s(a, 0)).map(|e| json!({"ok": true, "events": e}))
        }),
        "link_yenile" => motor_cagri(k, |m| m.renew(s(a, 0), s(a, 1), None, None, None)),
        "automation_jobs" => ctx_cagri(k, |c| {
            c.store.automation_jobs(s(a, 0), 200).map(|j| json!({"ok": true, "jobs": j}))
        }),
        "rules_list" => ctx_cagri(k, |c| c.store.rules_list().map(|r| json!({"ok": true, "rules": r}))),
        "item_yolu" => ctx_cagri(k, |c| item_yolu(c, s(a, 0))),
        "dosya_ac" => ctx_cagri(k, |c| dosya_ac(c, s(a, 0))),
        "panoya_kopyala" => {
            let metin = s(a, 0);
            if metin.is_empty() {
                json!({"ok": false})
            } else {
                json!({"ok": panoya_yaz(metin)})
            }
        }
        "panodan_oku" => panodan_oku(),

        // Bagli degil: G/H ekleri (router'lari bos), eklenti, sunucu, telefon, paylasim.
        _ => henuz_yok(),
    }
}

fn kenar_yonu(kenar: &str) -> Option<tauri_runtime::ResizeDirection> {
    use tauri_runtime::ResizeDirection as Y;
    Some(match kenar {
        "top" => Y::North,
        "bottom" => Y::South,
        "left" => Y::West,
        "right" => Y::East,
        "topleft" => Y::NorthWest,
        "topright" => Y::NorthEast,
        "bottomleft" => Y::SouthWest,
        "bottomright" => Y::SouthEast,
        _ => return None,
    })
}

#[tauri::command]
pub async fn api_call(app: AppHandle, name: String, args: Vec<Json>) -> Json {
    let kabuk = app.state::<Arc<Kabuk>>().inner().clone();
    tauri::async_runtime::spawn_blocking(move || dispatch(&kabuk, &name, &args))
        .await
        .unwrap_or_else(|e| hata(e.to_string()))
}

/// Arayuz yuklendi (tauri_kopru.js). Yalniz ana pencere icin; LinkGrabber bekleyeni burada teslim edilir.
#[tauri::command]
pub fn sayfa_hazir(app: AppHandle, window: tauri::WebviewWindow) {
    if window.label() != ANA {
        return;
    }
    let kabuk = app.state::<Arc<Kabuk>>().inner().clone();
    kabuk.ui.lg.hazir.store(true, Ordering::SeqCst);
    lg_teslim_et(&app, &kabuk.ui.lg);
}
