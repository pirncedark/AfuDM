//! Cekirdek yonetici. Bu dosya YALNIZ Claude (orkestra) tarafindan degistirilir.
//! Govdeler ekip dosyalarinda: queue.rs (C), torrent.rs + video.rs (D), butunluk.rs (G).
//! Ekipler arasi cagri: modul fonksiyonlarini dogrudan cagir (ornek: queue::add icinden torrent::torrent_ekle_ic).
//! Ekip ici yardimci fonksiyonlar `pub(crate)` olur ve kendi dosyasinda durur.

pub mod butunluk;
pub mod queue;
pub mod torrent;
pub mod video;

use afudm_types::{Aria2, Json, JsonMap, ManagerApi, Result, Store, UiBridge};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, RwLock};

pub struct Manager {
    pub store: Arc<dyn Store>,
    /// Motor yeniden baslatilinca degisir (Python: self.rpc atamasi).
    pub rpc: RwLock<Arc<dyn Aria2>>,
    pub ui: Arc<dyn UiBridge>,
    pub data_dir: PathBuf,
    pub app_dir: PathBuf,
    /// Python: manager.py self._kilit() — ekleme/silme yarisini onler.
    pub kilit: Mutex<()>,
    pub queue_state: Mutex<queue::State>,
    pub torrent_state: Mutex<torrent::State>,
    pub video_state: Mutex<video::State>,
    pub butunluk_state: Mutex<butunluk::State>,
    /// Indirme bitince cagrilir (Python manager._on_complete sonundaki otomasyon adimi).
    /// Arguman: {"title","size","gid"}. Kabuk (app) otomasyon kuyrugunu buraya baglar.
    pub tamamlandi_kancalari: Mutex<Vec<TamamlandiKancasi>>,
}

pub type TamamlandiKancasi = Box<dyn Fn(&Json) + Send + Sync>;

impl Manager {
    pub fn new(
        store: Arc<dyn Store>,
        rpc: Arc<dyn Aria2>,
        ui: Arc<dyn UiBridge>,
        data_dir: PathBuf,
        app_dir: PathBuf,
    ) -> Self {
        Manager {
            store,
            rpc: RwLock::new(rpc),
            ui,
            data_dir,
            app_dir,
            kilit: Mutex::new(()),
            queue_state: Mutex::new(Default::default()),
            torrent_state: Mutex::new(Default::default()),
            video_state: Mutex::new(Default::default()),
            butunluk_state: Mutex::new(Default::default()),
            tamamlandi_kancalari: Mutex::new(Vec::new()),
        }
    }

    pub fn tamamlandi_kancasi_ekle(&self, kanca: TamamlandiKancasi) {
        if let Ok(mut k) = self.tamamlandi_kancalari.lock() {
            k.push(kanca);
        }
    }

    pub fn rpc(&self) -> Arc<dyn Aria2> {
        self.rpc.read().expect("rpc kilidi").clone()
    }
}

#[allow(unused_imports)]
use afudm_types::AfuError;

impl ManagerApi for Manager {
    fn start(&self) -> Result<()> {
        queue::start(self)
    }
    fn stop(&self) -> Result<()> {
        queue::stop(self)
    }
    fn set_mode(&self, ad: &str) -> Result<Json> {
        queue::set_mode(self, ad)
    }
    fn baglanti_ayarla(
        &self,
        gid: &str,
        baglanti: Option<i64>,
        hiz_kb: Option<i64>,
    ) -> Result<Json> {
        queue::baglanti_ayarla(self, gid, baglanti, hiz_kb)
    }
    fn update_settings(&self, changes: &JsonMap) -> Result<Json> {
        queue::update_settings(self, changes)
    }
    fn current_download_dir(&self) -> Result<String> {
        queue::current_download_dir(self)
    }
    fn add_completed_file(&self, path: &Path) -> Result<Json> {
        queue::add_completed_file(self, path)
    }
    fn add(&self, req: &JsonMap) -> Result<Json> {
        queue::add(self, req)
    }
    fn probe_video(&self, url: &str) -> Result<Json> {
        video::probe_video(self, url)
    }
    fn pause(&self, gid: &str) -> Result<bool> {
        queue::pause(self, gid)
    }
    fn resume(&self, gid: &str) -> Result<bool> {
        queue::resume(self, gid)
    }
    fn remove(&self, gid: &str, delete_files: bool) -> Result<bool> {
        queue::remove(self, gid, delete_files)
    }
    fn phone_download_path(&self, gid: &str) -> Result<Option<PathBuf>> {
        queue::phone_download_path(self, gid)
    }

    fn resolve_item_path(&self, gid: &str) -> Result<Option<PathBuf>> {
        queue::resolve_item_path(self, gid)
    }
    fn pause_all(&self) -> Result<()> {
        queue::pause_all(self)
    }
    fn resume_all(&self) -> Result<()> {
        queue::resume_all(self)
    }
    fn retry(&self, row_id: i64) -> Result<Json> {
        queue::retry(self, row_id)
    }
    fn renew(
        &self,
        gid: &str,
        yeni_url: &str,
        headers: Option<&JsonMap>,
        cookies: Option<&[Json]>,
        user_agent: Option<&str>,
    ) -> Result<Json> {
        queue::renew(self, gid, yeni_url, headers, cookies, user_agent)
    }
    fn seed_bilgi(&self, gid: &str) -> Result<Json> {
        torrent::seed_bilgi(self, gid)
    }
    fn tracker_tara(&self, gid: &str) -> Result<Json> {
        torrent::tracker_tara(self, gid)
    }
    fn seed_dosyalari(&self) -> Result<Json> {
        torrent::seed_dosyalari(self)
    }
    fn seed_dosya_ekle(&self, yol: &str) -> Result<Json> {
        torrent::seed_dosya_ekle(self, yol)
    }
    fn seed_dosya_sil(&self, ad: &str) -> Result<Json> {
        torrent::seed_dosya_sil(self, ad)
    }
    fn seed_tazele(&self, gid: &str) -> Result<Json> {
        torrent::seed_tazele(self, gid)
    }
    fn snapshot(&self) -> Result<Json> {
        queue::snapshot(self)
    }
    fn peers(&self, gid: &str) -> Result<Vec<Json>> {
        torrent::peers(self, gid)
    }
    fn torrent_on_ekle(&self, source: &str) -> Result<String> {
        torrent::torrent_on_ekle(self, source)
    }
    fn torrent_on_iptal(&self, gid: &str) -> Result<()> {
        torrent::torrent_on_iptal(self, gid)
    }
    fn torrent_dosyalari(&self, gid: &str) -> Result<Json> {
        torrent::torrent_dosyalari(self, gid)
    }
    fn torrent_dosya_secimini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<Vec<i64>> {
        torrent::torrent_dosya_secimini_kaydet(self, gid, indeksler)
    }
    fn torrent_secimi_ayarla(&self, gid: &str, indeksler: &[i64]) -> Result<Json> {
        torrent::torrent_secimi_ayarla(self, gid, indeksler)
    }
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>> {
        torrent::torrent_dosya_secimleri(self, gid)
    }
    fn torrent_metrikleri(&self, gid: &str) -> Result<Json> {
        torrent::torrent_metrikleri(self, gid)
    }
    fn servers(&self, gid: &str) -> Result<Vec<Json>> {
        queue::servers(self, gid)
    }
    fn can_release_ui(&self) -> Result<bool> {
        queue::can_release_ui(self)
    }
    fn butunluk_tara(&self, gid: &str) -> Result<Json> {
        butunluk::butunluk_tara(self, gid)
    }
    fn butunluk_onar(&self, gid: &str, yeni_url: &str) -> Result<Json> {
        butunluk::butunluk_onar(self, gid, yeni_url)
    }
    fn butunluk_hepsini_tara(&self) -> Result<Json> {
        butunluk::butunluk_hepsini_tara(self)
    }
    fn notify_telegram(&self, text: &str) -> Result<bool> {
        queue::notify_telegram(self, text)
    }
}
