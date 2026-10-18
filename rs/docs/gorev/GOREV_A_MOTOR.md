# Ekip A: Motor (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

Amaç: aria2c sürecini yönetmek, afudm_types::Aria2 JSON-RPC istemcisini yazmak, yt-dlp / ffmpeg / cloudflared motorlarını yönetmek.

## ÇALIŞACAĞIN DOSYALAR (yalnız bunlar)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-engine\Cargo.toml
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-engine\src\ altında her şey (lib.rs, daemon.rs, rpc.rs, engines.rs, idle.rs ...)

## Python kaynağı (oku, birebir taşı). P = C:\Users\afuuu\Desktop\afuproject\AfuDM
📍 P\core\rpc.py (179 satır): class Aria2RPC → `pub struct Aria2Rpc` + `impl afudm_types::Aria2`. _hata_metni (satır 15) aynı kalsın. HTTP için ureq (senkron).
📍 P\core\daemon.py (329 satır):
  - _args (satır 100): aria2c argümanları BİREBİR aynı olsun. `--auto-save-interval=60` (satır 153) dahil; bu 17 Eki düzeltmesi, kaybolmamalı.
  - Taşınacaklar: load_or_create_secret (73), sanitize_session_file (31), save_auth_required (65), _dinleyen_var_mi (84).
  - Aria2Daemon (175): start, save_session, stop.
  - IdleRPC (276): motor uyurken ilk çağrıda uyanan sarmalayıcı; `sleeping()` true döner.
  - Süreç penceresiz başlasın (CREATE_NO_WINDOW). Kapanışta önce save_session, sonra shutdown.
📍 P\core\aria2.py ve P\core\engines.py (238): Motor tanımları, durum(), eksikler(), indir() (SHA256 doğrulamalı), var_mi, sistemde.
📍 P\core\paths.py (79): yalnız motor yollarıyla ilgili kısım.

## Dışa açacağın API (diğer ekipler kullanacak; adları değiştirme)
```rust
pub struct Aria2Daemon;
impl Aria2Daemon {
    pub fn new(app_dir: &Path, data_dir: &Path, download_dir: &Path) -> Self;
    pub fn start(&mut self, timeout: Duration) -> Result<Arc<dyn Aria2>>;
    pub fn save_session(&self) -> Result<()>;
    pub fn stop(&mut self) -> Result<()>;
}
pub struct IdleRpc; // impl Aria2, sleeping()
pub mod engines {
    pub fn durum(app_dir: &Path) -> Json;
    pub fn eksikler(app_dir: &Path, sadece_istege_bagli: bool) -> Vec<String>;
    pub fn indir(app_dir: &Path, ad: &str, ilerleme: &dyn Fn(u64, u64)) -> Result<Json>;
    pub fn yol(app_dir: &Path, ad: &str) -> Option<PathBuf>;
}
```

## Test
- Sahte HTTP sunucusuyla RPC birim testleri. Karşılık gelen Python testleri: P\tests\fake_http_test.py, daemon_test.py, daemon_port_test.py.
- Gerçek aria2c ile entegrasyon testi:
  1. P\engine\aria2c.exe dosyasını geçici klasöre KOPYALA.
  2. Rastgele portta başlat.
  3. add_uri, tell_status, shutdown sırasıyla çalıştır.
  - Kullanıcının çalışan AfuDM'ine DOKUNMA (portlar 6810, 6811 ve aria2c PID'leri).

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_A.md
