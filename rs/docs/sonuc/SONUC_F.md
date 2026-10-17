# SONUC F: Tauri kabuğu (rs\app), 2. tur

Durum: KISMİ ama uçtan uca çalışıyor. Exe açılıyor, motor (aria2 + store + Manager + HTTP API) kalkıyor, gerçek indirme tamamlanıp doğrulanıyor. Pencere açma yolu, arayüz köprüsünün gerçek WebView'deki davranışı ve bazı Python-paritesi noktaları test edilmedi (aşağıda).

## Yapılanlar (2. tur)
- `main.rs` / `boot.rs`: açılış sırası. Bekleyen geri yükleme (`restore_bekleyen.db` -> `afudm.db`, store açılmadan), çerez artığı temizliği (`g2::cerez::artiklari_temizle`), `SqliteStore` -> `Aria2Daemon` -> `IdleRpc` (boşta kapatan döngü, 30 sn) -> `Manager` (+ `start`, `tamamlandi_kancasi_ekle` ile otomasyon) -> `ApiCtx` -> `with_auth(api::router U g1::router U g2::router_with(ctx, servis) U h::router)` -> `serve(port)` -> `write_endpoint`. Port `AFUDM_PORT` (varsayılan 6811). Eklenti servisi tek örnek (`g2::servis_olustur`), HTTP ve köprü paylaşır.
- `entegrasyon.rs` (yeni): başlangıç kısayolu (Baslangic klasöründe `AfuDM.lnk`, PowerShell + WScript.Shell, `CREATE_NO_WINDOW`), torrent + magnet ilişkilendirme (HKCU\Software\Classes; ilk değişimde eski değer yedeklenir), `afudm://` protokolü. Hepsi kullanıcı düzeyi.
- `bridge.rs`: `api_call` artık async; motor çağrıları `spawn_blocking` içinde. Bağlanan komutlar:
  - Pencere/yerel: pencere_durumu, pencere_buyut, pencere_kucult, pencere_kapat, pencere_kenar, pencere_surukle, kapat, bekleyen_listesi/onayla/iptal
  - Kabuk: api_info, surum_bilgi (3.0.0), motor_durumu, sistem_durumu, baslangic_ayarla, varsayilan_uygulama_ekrani, torrent_iliskilendir, windows_integration_status/apply/remove/test (torrent, startup, protocol, notify, defender)
  - Klasör: klasor_kisayollar, ag_konumu_ekle/sil, klasor_alt, klasor_yeni, klasor_gozat (native klasör diyaloğu, `tauri-plugin-dialog`), open_download_dir, open_item_folder
  - Motor: snapshot, peers, seed_bilgi/tazele/dosyalari/dosya_ekle/dosya_sil, tracker_tara, torrent_on_ekle/on_iptal/dosyalari/secimi_ayarla/metrikleri, control (pause/resume/remove), retry
  - Reliability (G1): integrity, backup, backups, diagnostics_preview, diagnostics_export, restore, health (rpc_alive, uyku)
  - Güncelleme (G1): kontrol, durum, otomatik_ayarla, son_kontrol, indir, uygula (bekleyen = snapshot'ta status "active" var mı)
  - Otomasyon (G1): automation_retry, automation_cancel
  - Eklenti (G2): eklenti_listesi, eklenti_etkinlestir (HTTP ile aynı servis)
- LinkGrabber: `UiBridge::open_linkgrabber` pencereyi açar, `afudm-linkgrabber` olayı yayar; `tauri_kopru.js` bunu DOM olayına çevirir.
- Kabuk eksikleri: açılışta çalışma, magnet/.torrent ve afudm:// kaydı, klasör diyaloğu, özel başlık sürükleme (`tauri_kopru.js` mousedown/dblclick ile `pencere_surukle`/`pencere_buyut`; WebView2 CSS app-region desteklemediği için).
- `tauri_kopru.js` ve `index.html`/`download.html` değişiklikleri yalnız `app\ui` kopyasında. `P\ui` dokunulmadı.

## Köprü komutları: bağlı değil ("henüz yok")
- `reliability_restart_engine`: IdleRpc içindeki daemon'a erişim/yeniden başlatma API'si yok (A ekibi gerekli).
- `kaydet_bilgi`, `probe_link`: Python `manager.detect_kind` / `guess_name` / `probe_url_info`; afudm-core'da `pub(super)`, dışarı açılmadı.
- G2 `linkgrabber_*`, `rules_*`, `cerez`; G1 `guncelleme` dışı kalan otomasyon listeleri (`automation_jobs`); G1 `chrome_*`; eklenti dışındaki eklenti uçları (kur, incele, ayar, günlük); sunucu/anahtar/profil uçları (`sunucu_*`, `sunucu_anahtar_*`); H `start_pairing`, paylaşım (`share_*`, `dosya_sec_ve_paylas`, `agda_paylas`), telefon (`telefon_*`); `add_links`, `link_yenile`, `clear_finished`, `settings_save`, `proxy_testi`, `port_durumu`, `ayar_rozetleri`, `loglar`, `defender_scan`, `dosya_ac`, `item_yolu`, `panoya_*`, `probe`.
- Kapsam dışı bırakılanlar koordinatöre açık: bu uçların her biri Python'daki ilgili Api metodu okunup eşlenmeli.

## A/B/E/G/H'den beklenen eksikler / riskler
- A: IdleRpc'den daemon'a yeniden başlatma API'si (reliability_restart_engine).
- E: HTTP tarafı çalışıyor; `write_endpoint` çağrıldı.
- G1: Güncelleme otomatik kontrol zamanlaması (Python'daki periyot) bulunamadı; kurulmadı. `Guncelleme::new(.., paketli=true)` sabit.
- G2/H: LinkGrabber paneli arayüz tarafında (app.js) dinlenmiyor; olay DOM'a düşüyor, panel yok. Pencere açılmadan önce yayılan olay kaybolabilir.
- Bağımlılık: `afudm-extras` ve `afudm-core` derleme uyarıları (video.rs, is.rs) başka ekiplerde; bu crate'lere yazılmadı.

## Python'dan sapmalar (📍)
- `pencere_kapat`: Python X'i tepsiye gizler; burada pencere yok edilir (görev gereği). Tepsi açık kalır.
- Başlangıç kısayolu: Python `baslangic.ac` ile aynı yol ve argüman (`--tepside`); exe yolu `current_exe`.
- Protokol kaydı (`afudm://`): Python kurulum öncesi değeri yedekleyip geri yükler; burada yedek alınmıyor, kaldırmada anahtar siliniyor. Torrent/magnet yedeklemesi Python ile aynı.
- `torrent_dosyalari` / `torrent_metrikleri`: Python'daki `hazir_degil`/`neden` nesne öznitelikleri Rust Vec'te yok; `hazir_degil=false` varsayıldı (metrik için JSON'dan okunur).
- `sistem_durumu.torrent`: Python `iliskilendir.durum()` alanları bire bir değil; `{kayitli, torrent, magnet}` döner.
- `motor_durumu`: Python `engines.durum()` ayrıntısı yok; yalnız `kaynak` (paket/sistem/yok).
- `bekleyen_listesi` istek alanları ve `bekleyen_onayla` birleştirme: Python `_bekleyenler` ile doğrulanmadı.
- `api_info`: Python `local_api.port/token` yerine dosyadan (`api_token.txt`) ve `boot` portundan okunur.
- `reliability_health`: Python'daki ayrıntılı sağlık alanları yerine rpc_alive ve uyku.

## Doğrulama
- `cargo clippy --manifest-path app\Cargo.toml -- -D warnings`: çıkış 0 (2. tur kodu dahil).
- `cargo build --release --manifest-path app\Cargo.toml`: çıkış 0. Çıktı kuyruğu:
```
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
   Compiling afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
    Finished `release` profile [optimized] target(s) in 4m 14s
```
  (Bir kez rustc `STATUS_DLL_INIT_FAILED` ile çöktü; yeniden çalıştırmada geçti.)
- `node --check app\ui\tauri_kopru.js`: OK.
- Headless uçtan uca test (gerçek aria2c 1.37, geçici klasör `scratchpad\hedef`, port 6851, yerel dosya sunucusu 6852; pencere açılmadı):
  - `/ping` -> `{"app":"AfuDM","ok":true}`. Boot 20 sn içinde.
  - `/snapshot` (token `X-AfuDM-Token`) -> `ok:true`, `engine_ok:true`, ayarlar dolu.
  - `/add` -> `{"gid":"3027f6d7b4a262bc","kind":"http","ok":true}`.
  - İndirme: `test.bin` 8388608 bayt. SHA-256 kaynak ve indirilen dosyada eşit: `3AFCB9D9EB68B2359B2E3FF520C90A5D7DDD0EAEDF0332943DB97D5E6E4E3DDA`.
  - Otomasyon kancası: indirme bitince `automation` kuyruğunda `notify` işi oluştu (status complete).
  - RAM (indirme sırasında): AfuDM.exe 29.1 MB (working set), aria2c 18.0 MB.
  - Temizlik: test süreçleri kapatıldı, `alive_after=0`. Kullanıcının Python AfuDM'ine ve aria2'sine (6810, PID ailesi) dokunulmadı.
- Test edilmedi: pencere açma, WebView'de `tauri_kopru.js` davranışı, klasör diyaloğu, LinkGrabber paneli, başlangıç kısayolu/protokol kaydının gerçek Windows'ta yazılması (kayıt defteri/Startup'a yazan çağrılar derlendi, çalıştırılmadı), restore_bekleyen geri yüklemesi, güncelleme uçları.

## Commit
Commit yapılmadı (ekip kuralı: commit Claude'da). Değişen dosyalar: `rs\app\` altı (src: main, boot, bridge, window, tray, entegrasyon; ui: tauri_kopru.js + iki HTML'de tek script satırı; Cargo.toml, tauri.conf.json, build.rs, icons). `target\` ve `gen\` `.gitignore` ile dışarıda.
