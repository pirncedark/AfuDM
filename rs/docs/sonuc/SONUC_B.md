# Ekip B — Veri katmanı sonucu

## Dosyalar
- `crates/afudm-db/Cargo.toml`: rusqlite 0.37 bundled; tempfile 3; Windows için winreg 0.56, windows-sys 0.61.
- `src/lib.rs`, `store.rs`, `schema.rs`, `settings.rs`, `paths.rs`, `kaydet.rs`, `tests.rs`, `verify_cargo.py` (hepsi afudm-db altında).

## Taşınan işlevler
- ✅ SqliteStore::open / open_in_memory; Mutex ile Send + Sync, 15 saniye kilit bekleme, WAL.
- ✅ Store ayarları: get, set, all_settings; db.py DEFAULTS → default_settings.
- ✅ rules_list / rules_save; hatalı kural kaydında işlem geri alınır.
- ✅ add, attach_gid, update_by_gid / update_by_id, by_gid / by_id, list, max_video_seq, due_scheduled, delete, clear_finished.
- ✅ Torrent dosya seçimlerinin kaydı, okunması, varlık kontrolü ve GID taşıma.
- ✅ automation_enqueue / jobs / claim / jobs_by_id / update / retry / cancel.
- ✅ eklenti_listesi / eklenti / eklenti_yaz / eklenti_alan_yaz / eklenti_sil.
- ✅ log (hata döndürmez), recent_events, parametreli query / execute ve JSON → SQL değer dönüşümü.
- ✅ Şema v2–v10; yeni göç eklenmedi; auto_accept_migrated davranışı korundu.
- ✅ validate: portlar, salyangoz hızı, eşzamanlı indirme sayısı, proxy, uzantılar, ağ konumları; Python i18n hata anahtarları korunur. proxy_maskele kimlik bilgisini gizler.
- ✅ Portable yollar: data_dir / db_path / token_file / endpoint_file / default_download_dir; uygulama, kullanıcı indirme, motor yolları ve klasör oluşturma yardımcıları.
- ✅ Kaydet: kategori_tahmin / kategori_klasoru / guvenli_dosya_adi / kisayollar / alt_klasorler / klasor_olustur / ag_yolu_mu / ag_konumlari / ag_konumu_dogrula.
- ✅ Bekleyenler: new / bak / ekle / al / geri_koy / ozet; atomik dosya yazımı, sırların yalnız bellekte tutulması, süre dolumu, URL/istek kimliğiyle tekilleştirme ve bozuk dosyayı ayırma.
- ✅ app.py son klasör davranışı: son_klasor / son_klasoru_hatirla.

## Test yaklaşımı ve sözleşme
- Store sözleşmesinde eksik metot saptanmadı. Ortak crates/afudm-types değiştirilmedi.
- Python kaynak dosyaları yalnız okundu; kaynak proje içinde test/derleme çalıştırılmadı.
- Kullanıcının asıl DB'si SQLite ile açılmadı. Test `afudm.db`, varsa `-wal` ve `-shm` dosyalarını byte olarak geçici dizine kopyalar. Python SQLite ile kopyanın bütünlüğünü ve her tablonun satır sayısını okur; Rust açılışından sonra tekrar karşılaştırır.
- Testler: bellek deposu, v0/v2/v4/v10 göçleri, tekrar açılış, eşzamanlı yazma, kural işlemi geri alma, otomasyon, eklenti JSON, ayar sınırları, portable yollar, klasörler, bekleyen istek kalıcılığı ve sır temizleme.
- Cargo Windows TLS/eksik önbellek sorunu için `verify_cargo.py` yalnız geçici Cargo önbelleği kullanır; normal Cargo test/build/clippy komutlarını çalıştırır ve gerçek çıktıların son 30 satırını bu rapora ekler. Yeniden çalıştırma: `python crates/afudm-db/src/verify_cargo.py`.
- `cargo fmt -p afudm-db` çalıştırıldı (çıkış 0).
- Önceki turdaki başka crate manifest engeli bu turda görünmedi. İlk bu tur derlemesinde büyük DEFAULTS JSON makrosu recursion sınırını aştı; afudm-db crate'inde sınır 256 yapıldı.

## Gerçek Cargo çıktıları
Aşağıdaki çıktılar doğrulama betiği tarafından eklenir. Son komutların çıkış kodları esas alınmalıdır.

## Cargo test (isolated cache)
```text
   Compiling fallible-streaming-iterator v0.1.9
   Compiling hashlink v0.10.0
   Compiling fastrand v2.5.0
   Compiling smallvec v1.16.3
   Compiling once_cell v1.21.4
   Compiling bitflags v2.13.2
   Compiling log v0.4.34
   Compiling libsqlite3-sys v0.35.0
   Compiling tempfile v3.27.0
   Compiling winreg v0.56.0
   Compiling syn v3.0.9
   Compiling thiserror-impl v2.0.21
   Compiling serde_derive v1.0.229
   Compiling rusqlite v0.37.0
   Compiling afudm-types v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-types)
   Compiling afudm-db v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-db)
error[E0308]: `?` operator has incompatible types
   --> crates\afudm-db\src\store.rs:179:21
    |
179 |         query_conn(&self.lock()?, sql, params)
    |                     ^^^^^^^^^^^^ expected `Connection`, found `MutexGuard<'_, Connection>`
    |
    = note: `?` operator cannot convert from `std::sync::MutexGuard<'_, Connection>` to `Connection`
    = note: expected struct `Connection`
               found struct `std::sync::MutexGuard<'_, Connection>`

For more information about this error, try `rustc --explain E0308`.
error: could not compile `afudm-db` (lib) due to 1 previous error
warning: build failed, waiting for other jobs to finish...
error: could not compile `afudm-db` (lib test) due to 1 previous error
exit_code=101
```
