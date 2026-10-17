//! Ekipler arasi ortak sozlesme. YALNIZ Claude (orkestra) degistirir.
//! Satirlar ve yanitlar Python surumuyle birebir ayni JSON'u uretsin diye `Json` ile tasinir.
//! Her metodun Python karsiligi `C:\Users\afuuu\Desktop\afuproject\AfuDM\` altindaki dosyada,
//! doc yorumundaki satirdadir.

use std::path::{Path, PathBuf};
use std::sync::Arc;

pub type Json = serde_json::Value;
pub type JsonMap = serde_json::Map<String, Json>;

#[derive(Debug, thiserror::Error)]
pub enum AfuError {
    /// Kullanici girdisi hatali (Python: ValueError) -> HTTP 400
    #[error("{0}")]
    Invalid(String),
    /// Kayit yok (Python: KeyError / None) -> HTTP 404
    #[error("{0}")]
    NotFound(String),
    /// aria2 / yt-dlp / ffmpeg hatasi (Python: Aria2Error) -> HTTP 502
    #[error("{0}")]
    Engine(String),
    /// Motor hazir degil, uyuyor, gecici durum -> HTTP 503
    #[error("{0}")]
    Unavailable(String),
    #[error("{0}")]
    Db(String),
    #[error("{0}")]
    Io(String),
    #[error("{0}")]
    Other(String),
}

impl From<std::io::Error> for AfuError {
    fn from(e: std::io::Error) -> Self {
        AfuError::Io(e.to_string())
    }
}

impl From<serde_json::Error> for AfuError {
    fn from(e: serde_json::Error) -> Self {
        AfuError::Invalid(e.to_string())
    }
}

pub type Result<T> = std::result::Result<T, AfuError>;

/// SQLite deposu. Python: core/db.py `class Store` (satir 353).
/// Satirlar sutun adli JSON nesnesidir; `options` sutunu Python'daki gibi cozulmus nesne doner.
pub trait Store: Send + Sync {
    fn get(&self, key: &str) -> Result<Option<Json>>;
    fn set(&self, key: &str, value: Json) -> Result<()>;
    fn all_settings(&self) -> Result<JsonMap>;
    fn rules_list(&self) -> Result<Vec<Json>>;
    fn rules_save(&self, rules: &[Json]) -> Result<()>;
    #[allow(clippy::too_many_arguments)]
    fn add(&self, kind: &str, source: &str, title: Option<&str>, dest_dir: Option<&str>,
           options: Option<&JsonMap>, start_after: Option<f64>, gid: Option<&str>) -> Result<i64>;
    fn attach_gid(&self, row_id: i64, gid: &str) -> Result<()>;
    fn update_by_gid(&self, gid: &str, fields: &JsonMap) -> Result<()>;
    fn update_by_id(&self, row_id: i64, fields: &JsonMap) -> Result<()>;
    fn by_gid(&self, gid: &str) -> Result<Option<Json>>;
    fn by_id(&self, row_id: i64) -> Result<Option<Json>>;
    fn list(&self, status: Option<&str>, limit: usize) -> Result<Vec<Json>>;
    fn max_video_seq(&self) -> Result<i64>;
    fn torrent_dosya_secimlerini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<()>;
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>>;
    fn torrent_dosya_secimi_var(&self, gid: &str) -> Result<bool>;
    fn torrent_dosya_secimlerini_tasi(&self, eski_gid: &str, yeni_gid: &str) -> Result<()>;
    fn due_scheduled(&self, now: Option<f64>) -> Result<Vec<Json>>;
    fn delete(&self, row_id: i64) -> Result<()>;
    fn clear_finished(&self) -> Result<usize>;
    fn automation_enqueue(&self, gid: &str, action: &str, payload: Option<&JsonMap>) -> Result<()>;
    fn automation_jobs(&self, gid: &str, limit: usize) -> Result<Vec<Json>>;
    fn automation_claim(&self) -> Result<Option<Json>>;
    fn automation_jobs_by_id(&self, job_id: i64) -> Result<Option<Json>>;
    fn automation_update(&self, job_id: i64, fields: &JsonMap) -> Result<()>;
    fn automation_retry(&self, job_id: i64) -> Result<()>;
    fn automation_cancel(&self, job_id: i64) -> Result<()>;
    fn eklenti_listesi(&self) -> Result<Vec<Json>>;
    fn eklenti(&self, ad: &str) -> Result<Option<Json>>;
    fn eklenti_yaz(&self, kayit: &JsonMap) -> Result<()>;
    fn eklenti_alan_yaz(&self, ad: &str, alanlar: &JsonMap) -> Result<()>;
    fn eklenti_sil(&self, ad: &str) -> Result<()>;
    fn log(&self, level: &str, message: &str, gid: &str);
    fn recent_events(&self, limit: usize, gid: &str) -> Result<Vec<Json>>;
    /// Diger tablolar (mobile_devices, api_keys, api_clients, server_profiles) icin parametreli SQL.
    /// Donus: her satir sutun adli JSON nesnesi.
    fn query(&self, sql: &str, params: &[Json]) -> Result<Vec<Json>>;
    fn execute(&self, sql: &str, params: &[Json]) -> Result<usize>;
}

/// aria2 JSON-RPC istemcisi. Python: core/rpc.py `class Aria2RPC` (satir 31).
/// `keys` bos dilim = tum alanlar.
pub trait Aria2: Send + Sync {
    fn call(&self, method: &str, params: Vec<Json>) -> Result<Json>;
    fn alive(&self) -> bool;
    /// Motor uykudaysa true (Python: core/daemon.py IdleRPC.sleeping).
    fn sleeping(&self) -> bool {
        false
    }
    fn add_uri(&self, uris: &[String], options: Option<&JsonMap>) -> Result<String>;
    fn add_torrent(&self, torrent_b64: &str, options: Option<&JsonMap>) -> Result<String>;
    fn add_metalink(&self, metalink_b64: &str, options: Option<&JsonMap>) -> Result<Vec<String>>;
    fn pause(&self, gid: &str, force: bool) -> Result<String>;
    fn unpause(&self, gid: &str) -> Result<String>;
    fn remove(&self, gid: &str, force: bool) -> Result<String>;
    fn remove_result(&self, gid: &str) -> Result<String>;
    fn pause_all(&self) -> Result<String>;
    fn unpause_all(&self) -> Result<String>;
    fn tell_status(&self, gid: &str, keys: &[&str]) -> Result<Json>;
    fn tell_active(&self, keys: &[&str]) -> Result<Vec<Json>>;
    fn tell_waiting(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>>;
    fn tell_stopped(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>>;
    fn global_stat(&self) -> Result<Json>;
    fn get_peers(&self, gid: &str) -> Result<Vec<Json>>;
    fn get_files(&self, gid: &str) -> Result<Vec<Json>>;
    fn get_servers(&self, gid: &str) -> Result<Vec<Json>>;
    fn change_option(&self, gid: &str, options: &JsonMap) -> Result<String>;
    fn change_global_option(&self, options: &JsonMap) -> Result<String>;
    fn change_uri(&self, gid: &str, file_index: i64, del_uris: &[String], add_uris: &[String], position: i64) -> Result<i64>;
    fn get_global_option(&self) -> Result<JsonMap>;
    fn shutdown(&self, force: bool) -> Result<String>;
    fn save_session(&self) -> Result<String>;
}

/// Indirme yoneticisi. Python: core/manager.py `class Manager`.
/// Arguman/donus JSON sekilleri Python fonksiyonunun dict'iyle birebir aynidir.
pub trait ManagerApi: Send + Sync {
    /// manager.py:144
    fn start(&self) -> Result<()>;
    /// manager.py:169
    fn stop(&self) -> Result<()>;
    /// manager.py:219
    fn set_mode(&self, ad: &str) -> Result<Json>;
    /// manager.py:244
    fn baglanti_ayarla(&self, gid: &str, baglanti: Option<i64>, hiz_kb: Option<i64>) -> Result<Json>;
    /// manager.py:286
    fn update_settings(&self, changes: &JsonMap) -> Result<Json>;
    /// manager.py:320
    fn current_download_dir(&self) -> Result<String>;
    /// manager.py:519
    fn add_completed_file(&self, path: &Path) -> Result<Json>;
    /// manager.py:536 — `req` /add govdesi (core/models.py DownloadRequest alanlari); `source` ya da `url` zorunlu.
    fn add(&self, req: &JsonMap) -> Result<Json>;
    /// manager.py:846
    fn probe_video(&self, url: &str) -> Result<Json>;
    /// manager.py:850
    fn pause(&self, gid: &str) -> Result<bool>;
    /// manager.py:872
    fn resume(&self, gid: &str) -> Result<bool>;
    /// manager.py:886
    fn remove(&self, gid: &str, delete_files: bool) -> Result<bool>;
    /// manager.py:1048
    fn resolve_item_path(&self, gid: &str) -> Result<Option<PathBuf>>;
    /// manager.py:1283
    fn pause_all(&self) -> Result<()>;
    /// manager.py:1297
    fn resume_all(&self) -> Result<()>;
    /// manager.py:1321
    fn retry(&self, row_id: i64) -> Result<Json>;
    /// manager.py:1343
    fn renew(&self, gid: &str, yeni_url: &str, headers: Option<&JsonMap>, cookies: Option<&[Json]>, user_agent: Option<&str>) -> Result<Json>;
    /// manager.py:1510
    fn seed_bilgi(&self, gid: &str) -> Result<Json>;
    /// manager.py:1545
    fn tracker_tara(&self, gid: &str) -> Result<Json>;
    /// manager.py:1570
    fn seed_dosyalari(&self) -> Result<Json>;
    /// manager.py:1594
    fn seed_dosya_ekle(&self, yol: &str) -> Result<Json>;
    /// manager.py:1605
    fn seed_dosya_sil(&self, ad: &str) -> Result<Json>;
    /// manager.py:1623
    fn seed_tazele(&self, gid: &str) -> Result<Json>;
    /// manager.py:1695
    fn snapshot(&self) -> Result<Json>;
    /// manager.py:1879
    fn peers(&self, gid: &str) -> Result<Vec<Json>>;
    /// manager.py:1899
    fn torrent_on_ekle(&self, source: &str) -> Result<String>;
    /// manager.py:1929
    fn torrent_on_iptal(&self, gid: &str) -> Result<()>;
    /// manager.py:1977 — Python TorrentDosyaListesi: liste + hazir_degil/neden ozellikleri.
    /// Donus: {"dosyalar": [...], "hazir_degil": bool, "neden": str, "gid": str}
    fn torrent_dosyalari(&self, gid: &str) -> Result<Json>;
    /// manager.py:2036
    fn torrent_dosya_secimini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<Vec<i64>>;
    /// manager.py:2054
    fn torrent_secimi_ayarla(&self, gid: &str, indeksler: &[i64]) -> Result<Json>;
    /// manager.py:2090
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>>;
    /// manager.py:2093
    fn torrent_metrikleri(&self, gid: &str) -> Result<Json>;
    /// manager.py:2168
    fn servers(&self, gid: &str) -> Result<Vec<Json>>;
    /// manager.py:2192
    fn can_release_ui(&self) -> Result<bool>;
    /// manager.py:2447
    fn butunluk_tara(&self, gid: &str) -> Result<Json>;
    /// manager.py:2468
    fn butunluk_onar(&self, gid: &str, yeni_url: &str) -> Result<Json>;
    /// manager.py:2614
    fn butunluk_hepsini_tara(&self) -> Result<Json>;
    /// manager.py:2693
    fn notify_telegram(&self, text: &str) -> Result<bool>;
}

/// Masaustu kabuguna (Tauri) geri cagri. Ekip F uygular; testlerde `NoUi` kullanilir.
pub trait UiBridge: Send + Sync {
    /// Python: /show
    fn show_window(&self) {}
    /// Tarayicidan gelen indirmede "nereye kaydedeyim" penceresi (Python: app.py indirme penceresi).
    /// Donus: kullanicinin onayladigi (klasor/ad degismis olabilir) istek; None = iptal.
    fn ask_save_location(&self, req: &JsonMap) -> Option<JsonMap> {
        Some(req.clone())
    }
    fn notify(&self, _title: &str, _body: &str) {}
}

pub struct NoUi;
impl UiBridge for NoUi {}

/// HTTP katmanlarinin ortak baglami: Ekip E (cekirdek uclari + kimlik dogrulama), G (ekler), H (paylasim).
/// Router'lari Ekip F (app) birlestirir.
#[derive(Clone)]
pub struct ApiCtx {
    pub manager: Arc<dyn ManagerApi>,
    pub store: Arc<dyn Store>,
    /// Veri klasoru (Python: core/paths.py DATA). api_token.txt, api_endpoint.json burada.
    pub data_dir: PathBuf,
    /// Uygulama klasoru (AfuDM.exe'nin yani; engine\, ui\, extension\ burada).
    pub app_dir: PathBuf,
    pub ui: Arc<dyn UiBridge>,
}
