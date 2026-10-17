# Ekip F: Tauri kabuğu (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

Amaç: AfuDM.exe. Tek exe ve tepsi simgesi; pencere yalnız kullanıcı açınca görünür. Boşta uyku hedefi: pencere ve WebView kapalıyken RAM ≤ 60 MB.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app\ altında her şey: Cargo.toml, build.rs, tauri.conf.json, src\main.rs, src\bridge.rs, src\tray.rs, src\window.rs, src\uyku.rs, icons\
- Kök Cargo.toml'a "app" üyesi eklenmesi gerekiyorsa SONUC'ta iste; ben eklerim. O zamana kadar app\Cargo.toml içine boş bir `[workspace]` bloğu koy ve `cargo build --manifest-path app\Cargo.toml` ile ayrı derle.
- Arayüz dosyaları:
  - P\ui\ klasörünü app\ui\ altına KOPYALA (P = C:\Users\afuuu\Desktop\afuproject\AfuDM).
  - Kopyada yalnız köprü için gereken en küçük değişikliği yap.
  - Asıl P\ui'ye dokunma.

## Python kaynağı
📍 P\app.py (2192), Api sınıfı (190 ve sonrası): arayüzün çağırdığı metotlar. Arayüz bunları `window.pywebview.api.<ad>(...)` ile çağırıyor.
  - Çözüm: app\ui\tauri_kopru.js yaz. `window.pywebview = {api: Proxy → window.__TAURI__.core.invoke(ad, {args})}` kur ve `pywebviewready` olayını tetikle. Böylece app.js neredeyse hiç değişmez.
  - Her Api metodu için bir Tauri komutu yaz. Manager/store çağıranları şimdi bağla.
  - G/H ekiplerinin işi olanlar (guncelleme_*, linkgrabber_*, rules_*, reliability_*, windows_integration_*) şimdilik `{"ok":false,"error":"henüz yok"}` dönsün; SONUC'ta listele.
📍 P\core\pencere.py (306) ve app.py pencere_boyutu / _calisma_alani (89–165): pencere boyutu ve konumu.
📍 P\core\baslangic.py ve P\core\servis.py (613): açılışta çalışma, tek örnek (ikinci açılış ilk örneği öne getirir), boşta uyku.
  - Süreç tasarımı tek süreç. Pencere kapanınca WebView YOK EDİLİR (gizlenmez); tepsi ve API çalışmaya devam eder.
📍 P\core\windows_integration.py (167), P\core\iliskilendir.py: magnet ve .torrent ilişkilendirme, afudm:// protokolü (protocol_link, app.py:166).
📍 Tarayıcıdan gelen indirmede "nereye kaydedeyim" penceresi:
  - Kaynak: P\ui\download.html + download.js; app.py içindeki yerelden_sor, tarayicidan_sor, bekleyen_* (656–760).
  - UiBridge::ask_save_location bu pencereyi açar. Varsayılan klasör İndirilenler; son seçilen klasör hatırlanır.
📍 Başlangıç sırası (main.rs):
  1. Veri klasörü
  2. SqliteStore (B)
  3. Aria2Daemon / IdleRpc (A)
  4. Manager (core)
  5. ApiCtx
  6. afudm_api::with_auth(router ∪ G ∪ H)
  7. serve(6811)
  8. Tepsi
  A/B/E henüz bitmemiş olabilir. Onların crate'lerini path bağımlılığıyla kullan. Eksik fonksiyon varsa SONUC'a "bekliyor" yaz; o fonksiyonu kendin YAZMA.

## Kabul
- `cargo build --release` tek AfuDM.exe üretsin. WebView2 sistemde var; exe'ye gömme.
- Exe çalışınca pencere AÇILMAZ, yalnız tepsi görünür (kullanıcı kuralı: yeni pencere yok).
- Testler headless: /ping ve /snapshot yanıtı + RAM ölçümü (Get-Process).
- Kullanıcının çalışan AfuDM'i 6811'i tutuyor. Test için başka port kullan (ortam değişkeni AFUDM_PORT, ya da Python'da varsa aynı yöntem).

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_F.md
