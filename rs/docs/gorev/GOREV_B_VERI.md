# Ekip B: Veri (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

Amaç: afudm_types::Store'un rusqlite uygulaması, ayarlar ve doğrulama, yollar, kayıt yeri.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db\Cargo.toml (rusqlite, bundled özelliğiyle)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db\src\ altında her şey (lib.rs, store.rs, schema.rs, settings.rs, paths.rs, kaydet.rs)

## Python kaynağı. P = C:\Users\afuuu\Desktop\afuproject\AfuDM
📍 P\core\db.py (745 satır):
  - Store (353) sınıfının bütün metotları.
  - Şema göçleri _v2…_v10 (179–339) ve _guncelle_sema (339). 2.9.x veritabanı açılınca hiçbir veri kaybolmamalı. Yeni göç EKLEME.
  - `options` sütunu JSON metni olarak saklanır, nesne olarak döner. log() hata fırlatmaz.
  - query / execute (sözleşmedeki ek metotlar): parametreli SQL, Json → rusqlite değeri dönüşümü.
📍 P\core\settings_validation.py (278): `pub fn validate(changes, current) -> Result<JsonMap>`. Hata metinleri aynı olsun.
📍 P\core\paths.py (79): DATA, varsayılan indirme klasörü, api_token.txt, api_endpoint.json yolları. Taşınabilir mod mantığı aynı kalsın.
📍 P\core\kaydet.py (316): kayıt yeri seçimi ve son klasörü hatırlama.
📍 Varsayılan ayarlar: P\core\manager.py ve P\core\db.py içindeki DEFAULT / varsayılan sözlükleri bul. `pub fn default_settings() -> JsonMap` olarak taşı.

## Dışa açacağın API
```rust
pub struct SqliteStore;
impl SqliteStore {
    pub fn open(path: &Path) -> Result<Self>;
    pub fn open_in_memory() -> Result<Self>;
}
impl afudm_types::Store for SqliteStore {}
pub mod settings {
    pub fn default_settings() -> JsonMap;
    pub fn validate(changes: &JsonMap, current: &JsonMap) -> Result<JsonMap>;
}
pub mod paths {
    pub fn data_dir(app_dir: &Path) -> PathBuf;
    pub fn db_path(data: &Path) -> PathBuf;
    pub fn token_file(data: &Path) -> PathBuf;
    pub fn endpoint_file(data: &Path) -> PathBuf;
    pub fn default_download_dir() -> PathBuf;
}
pub mod kaydet { /* kaydet.py'deki public fonksiyonlar */ }
```
SqliteStore birden çok iş parçacığından kullanılır (Mutex<Connection> ya da havuz). WAL modu Python'daki gibi açık olsun.

## Test
- Karşılık gelen Python testleri: P\tests\db_test.py, db_gecis_test.py, restore_store_test.py, kaydet_test.py, son_klasor_test.py, v175_ayar_test.py.
- Gerçek veritabanının KOPYASIYLA test et:
  1. P\data\afudm.db, -wal ve -shm dosyalarını geçici klasöre kopyala.
  2. Kopyayı Rust ile aç.
  3. Tablo satır sayılarını Python ile karşılaştır.
  - Asıl dosyayı ASLA açma ya da yazma.

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_B.md
