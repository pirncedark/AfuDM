# SONUC F: Tauri kabuğu (rs\app)

Durum: KISMİ. Kabuk derleniyor ve tepside çalışıyor. Motor (Manager), HTTP katmanı ve dosya/ayar uçları A/B/E/G/H bağımlılığı olduğu için henüz bağlı değil; bunlar aşağıda listelendi.

## Yapılanlar
- `app\Cargo.toml`: kendi `[workspace]` bloğuyla ayrı derleniyor (`cargo build --release --manifest-path app\Cargo.toml`). Bağımlılıklar: `afudm-types` (path), `tauri 2`, `tauri-plugin-single-instance 2`, `tauri-runtime 2` (yalnız `ResizeDirection` tipi için; `tauri` bunu dışa açmıyor), `serde_json`.
- `app\tauri.conf.json`: `windows: []` (açılışta pencere YOK), `withGlobalTauri: true`, `frontendDist: ui`, `bundle.active: false`.
- `app\src\main.rs`: tek süreç. Single-instance eklentisi (ikinci açılış yeni süreç açmaz, ilk örneğin penceresini öne getirir). Veri klasörü `exe\data` oluşturulur (Python `core/paths.py` DATA ile aynı). Son pencere kapanınca çıkılmaz (`ExitRequested` code=None engellenir).
- `app\src\tray.rs`: tepsi simgesi; sol tık ve "Aç" pencereyi açar, "Çıkış" uygulamayı kapatır.
- `app\src\window.rs`: pencere yalnız `goster()` ile açılır; kapanınca WebView yok edilir (gizlenmez). Boyut: Python `pencere_boyutu` mantığı (hedef 1600x980, min 1100x900, ekranın %92'si ile sınır). Not: Tauri'de monitör boyutu kullanılıyor, `work_area` değil (görev çubuğu farkı yok sayılıyor). Indirme penceresi (`download.html`, 520x540) ve kapanınca bekleyen isteklerin iptali burada.
- `app\src\bridge.rs`: arayüz köprü komutu `api_call(name, args)`. Pencere ve indirme metotları yerelde karşılanıyor. Kalanı "henüz yok" döner. `TauriUi` (UiBridge) `show_window` ve `ask_save_location` uygular; `ask_save_location` bekleyen isteği tutup indirme penceresini açar, yanıt/iptal gelene dek bloklar.
- `app\ui\` = `P\ui` kopyası. Eklenen: `tauri_kopru.js` (`window.pywebview.api.<ad>(...)` -> `invoke("api_call")`, `pywebviewready` olayı). `index.html` ve `download.html`'e yalnız bir `<script>` satırı eklendi. `P\ui` DOKUNULMADI (kontrol edildi: orada `tauri_kopru.js` yok).
- `app\icons\icon.ico` ve `icon.png`: `P\ui\afudm.ico` ve `icon.png` kopyası.

## Köprü komutları

Bağlanan (yerel, çalışır):
- pencere_durumu, pencere_buyut, pencere_kucult, pencere_kapat, pencere_kenar
- kapat (indirme penceresi)
- bekleyen_listesi, bekleyen_onayla, bekleyen_iptal

"henüz yok" (`{"ok":false,"error":"henüz yok"}`): Python `Api`'nin geri kalanı. Başlıca gruplar:
- Motor/Manager'a bağlı: snapshot, motor_durumu, motor_indir, api_info, surum_bilgi, peers, probe_link, kaydet_bilgi, start_pairing
- reliability_* (7 metot), security_rotate_token
- guncelleme_* (kontrol, otomatik_ayarla, son_kontrol, indir, durum, uygula)
- rules_list, rules_save, rules_simulate, download_rules
- linkgrabber_* (analiz, suz, iptal, onceki, probe, ekle)
- klasor_kisayollar, klasor_alt, klasor_yeni, klasor_gozat, ag_konumu_ekle, ag_konumu_sil
- yerelden_sor, tarayicidan_sor (Python tarafı, köprü dışı)

## A/B/E/G/H'den beklenen eksikler
- A (Aria2Daemon, IdleRpc): `Aria2` trait uygulaması yok. Manager kurulamıyor. `main.rs` boot sırasının 3-4. adımları bekliyor.
- B (`afudm-db`): `SqliteStore` ve `Store` trait uygulaması yok (crate 1 satır).
- E (`afudm-api`): HTTP router, `with_auth`, `serve(6811)`, `api_token.txt` ve `api_endpoint.json` yok (crate yalnız yorum satırı). Test portu için `AFUDM_PORT` henüz okunmuyor; `/ping` ve `/snapshot` testi bu yüzden yapılamadı.
- G/H: ek ve paylaşım router'ları yok.
- `afudm-core`: `queue.rs`, `torrent.rs`, `butunluk.rs`, `video.rs` içindeki tüm fonksiyonlar `todo!()`. Bağlanınca panik edebilir; A/B tamamlanınca doldurulmalı.
- `afudm-engine`, `afudm-extras`: boş.
- Kök `Cargo.toml`'a `app` üyesi eklenmedi (görev gereği; Claude ekleyecek). Tek sorun: `app` ayrı derleniyor.

## Kabuk içinde eksik kalanlar (Ekip F kapsamı, yazılmadı)
- Açılışta çalışma (`core/baslangic.py`) ve Windows entegrasyonu (`core/windows_integration.py`, magnet/.torrent ilişkilendirme, `afudm://` protokolü): yazılmadı.
- `klasor_gozat` için klasör seçme diyaloğu: `tauri-plugin-dialog` eklenmedi.
- `uyku.rs`: yazılmadı. Boşta uyku, WebView'in pencere kapanınca yok edilmesiyle sağlanıyor. Ayrı modüle gerek görülmedi.
- Özel başlık çubuğunda sürükleme: `decorations(false)` ile açılıyor; sürükleme alanı (`data-tauri-drag-region` ya da CSS) arayüze eklenmedi. Python `basligi_kaldir` + WM_NCCALCSIZE yaklaşımıyla birebir değil; kenar boyutlandırma test edilmedi.
- Tepsi menü metinleri ("Aç", "Çıkış") Python'un tepsi metinleriyle karşılaştırılmadı.

## Python'dan sapmalar (📍)
- `pencere_kapat`: Python X'i tepsiye gizler (`app.py:1607`). Görev gereği burada pencere yok edilir. Tepsi açık kalır.
- `bekleyen_*` istek şekli (`ogeler` içindeki alanlar): Python `_bekleyenler.ozet()` ile karşılaştırılmadı; `download.js` beklediği alanlarla doğrulanmalı.
- `bekleyen_onayla` secim birleştirme: istek ile secim birleştirilip gönderiliyor. Python'daki birebir karşılığı doğrulanmadı.

## Doğrulama
- `cargo clippy --manifest-path app\Cargo.toml -- -D warnings`: çıkış 0, uyarı yok.
- `cargo build --release --manifest-path app\Cargo.toml`: çıkış 0. Çıktı: `app\target\release\AfuDM.exe` (6,6 MB).
- `node --check app\ui\tauri_kopru.js`: OK.
- Headless tepsi testi (pencere açılmadı, port açılmadı):
  - Süreç 8 sn ayakta, panik yok. Working set 14-32 MB (hedef ≤ 60 MB).
  - Görünen tek pencere 16x16 `TOOLWINDOW` (single-instance eklentisinin gizli yardımcı penceresi). Ana pencere yok.
  - WebView2 çocuk süreci yok.
  - İkinci örnek hemen çıktı (single-instance çalışıyor).
  - Test süreci kapatıldı. Kullanıcının çalışan Python AfuDM'ine (PID 34488 ailesi, 6811) dokunulmadı.
- Pencere açma yolu test EDİLMEDİ (kullanıcı kuralı: pencere açma yok). `tauri_kopru.js`'in gerçek WebView'de çalışması da test edilmedi.

Son `cargo build` çıktısı (`--release`, `app\`):
```
   Compiling afudm-types v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-types)
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Finished `release` profile [optimized] target(s) in 4m 17s
```
(Tam release derlemesi, ilk çalıştırmada bağımlılıklarla birlikte 12m 17s sürdü; tüm çıktı derleme günlüğünde.)

## Commit
Commit yapılmadı (ekip kuralı: commit Claude'da). Değişen/eklenen dosyalar: `rs\app\` altında (src, ui, icons, Cargo.toml, Cargo.lock, build.rs, tauri.conf.json, gen\ üretilen şema). `target\` ve `gen\` `.gitignore` ile dışarıda.
