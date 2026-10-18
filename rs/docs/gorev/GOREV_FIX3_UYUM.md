# Entegrasyon-3: Uyum testi farklarını kapat (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Test raporu: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_T1.md
Ham sonuç: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_parity\rapor\sonuc_son.json
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- crates\afudm-api\ (her şey)
- crates\afudm-extras\src\g1\mod.rs, g2\mod.rs, h\mod.rs (yalnız rota ve hata gövdesi)
- docs\API_SOZLESME.md
- docs\sonuc\SONUC_FIX3.md
DOKUNMA: app\ (Ekip F3 çalışıyor), tests_parity\ (T1 çalışıyor), afudm-types, afudm-core.

## KARAR (Claude): Python paritesi esas alınır.
Hata gövdesi her yerde Python'la aynı: `{"ok": false, "code": "...", "message": "...", "error": "..."}`. Python api/server.py'deki `_hata` ve `hata_json` kodlarına bak. AfuError → kod eşlemesi Python'daki gibi olsun (ValueError → 400 + code, vb.). API_SOZLESME.md'deki "{ok,error}" ifadesini düzelt.

## Yapılacaklar (SONUC_T1 sırasıyla)
1. Hata gövdesi: afudm-api `error()` dahil bütün hata yollarında code ve message alanları olsun. g1, g2 ve h router'ları da aynı biçimi kullansın (ortak yardımcı afudm-api'de olsun, extras onu çağırsın; döngüsel bağımlılık çıkarsa yardımcıyı extras'ta kopyala ve SONUC'ta not düş).
2. /capabilities: Python'daki gibi 200 ve tam JSON (P\api\server.py'de "/capabilities" ara). Store kaydı yoksa Python'un ürettiği varsayılanı üret; 503 dönme.
3. GET /settings: Python 404 dönüyor; aynısını yap.
4. /control: boş gid → 400 GID_GEREKLI (📍 crates\afudm-api\src\lib.rs:364). Diğer eylemlerin doğrulamasını Python sırasıyla karşılaştır.
5. /probe: boş url → 400 (📍 lib.rs:238). Python'daki doğrulama metniyle.
6. /control resume aria2 hatası: Python 500 "beklenmeyen bir sunucu hatasi olustu" dönüyor. Python davranışını taklit et (durum + metin).
7. /reliability/integrity ve /reliability/diagnostics-preview Rust'ta 405 veriyor. g1 router'ında yöntem (GET/POST) Python ile uyuşmuyor olabilir; Python'daki yöntemlerle eşle.
8. H statik dosyaları (/m, /manifest.webmanifest, /i18n.js, /sw.js, /ikon.png) 404 veriyor. Rota h\mod.rs:24-29'da var. ui klasörünün yolu ApiCtx.app_dir\ui mi? Exe'nin yanında ui klasörü yoksa (Tauri ui'yi exe'ye gömüyor) dosyalar bulunamaz. Çözüm: ui dosyalarını derleme anında crate'e göm (include_bytes / rust-embed). Kaynak dosyalar: P\ui\ (mobil.html, panel.html, manifest.webmanifest, i18n.js, sw.js, icon.png). Python'daki cache-control ve service-worker-allowed başlıklarını da ekle.
9. /windows-integration: Bu rotayı Ekip F3 app tarafında ekleyecek, çünkü işlevler orada. afudm-api'deki 503 dönen `windows_unavailable` rotasını (📍 lib.rs:294) KALDIR; yoksa F3'ün rotasıyla çakışır. API_SOZLESME'de belirt.

## Kontrol
- `cargo test -p afudm-api -p afudm-extras` ve `cargo clippy -p afudm-api -p afudm-extras --all-targets -- -D warnings` yeşil.
- Her madde için birim testi ekle (durum kodu + gövde anahtarları).
- Uyum testini (tests_parity) sen KOŞMA; F3 bitip exe yeniden derlenince ben koşturacağım.
SONUC: docs\sonuc\SONUC_FIX3.md. Soru sorup durma.
