# Ekip E: HTTP API (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md

Amaç: 127.0.0.1:6811'deki yerel API. Chrome eklentisi ve telefon arayüzü bununla konuşur; istek ve yanıt biçimi BİREBİR aynı olmalı.

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-api\Cargo.toml (axum, tokio)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-api\src\ altında her şey
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\API_SOZLESME.md (yeni dosya): her uç nokta için yöntem, yol, kimlik doğrulama, istek ve yanıt JSON örneği, hata kodları. Python'dan çıkar.

## Python kaynağı. P = C:\Users\afuuu\Desktop\afuproject\AfuDM
📍 P\api\server.py (1195 satır): _Handler sınıfı; do_GET ve do_POST rotaları 247–986. 38 uç nokta:
/ping /add /add_blob /capabilities /control /dosya /eklenti* /handoff/error /indir /klasorler /linkgrabber /m /pair /peers /probe /reliability/* /renew /rules /s/ /seed* /settings /share_create /show /snapshot /token/rotate /torrent/* /tracker/tara /mode /_listener/*
📍 Token ve güvenlik (hepsi birebir aynı kalmalı):
  - X-AfuDM-Token başlığı ve ?token= parametresi; api_token.txt; rotate_token; api_endpoint.json yazımı (port + token).
  - CORS ve Origin kuralları, chrome-extension:// izinleri, istek boyutu sınırları.
📍 P\core\erisim.py (460): API anahtarları, roller, istemci kaydı.
📍 P\api\web.py (512): mobil web arayüzünü sunma (/m).
📍 P\core\baslangic.py, UykuDinleyici (dinleyici + kuyruk):
  - Kuyruk klasörü data\listener_queue; kayıtlar DPAPI ile şifreli.
  - /add hemen 202 ve request_id döner.
  - 18 Eki: açılamayan adres (file:// gibi) kuyruğa alınmadan reddedilir.

## Sahiplik
- Senin rotaların: çekirdek (manager/store çağıranlar), kimlik doğrulama, dinleyici kuyruğu.
- Aşağıdaki rotalar G ve H ekiplerinin. Onları YAZMA; yalnız API_SOZLESME.md'de belgele.
  - G: /eklenti* /linkgrabber /rules /reliability/*
  - H: /pair /m /s/ /share_create

```rust
pub fn router(ctx: ApiCtx) -> axum::Router;                    // çekirdek rotalar
pub fn with_auth(r: axum::Router, ctx: ApiCtx) -> axum::Router; // token + CORS katmanı; app tüm router'lara uygular
pub async fn serve(r: axum::Router, port: u16) -> Result<u16>;   // port doluysa Python'daki gibi davran
pub mod listener { /* baslangic.py UykuDinleyici karşılığı */ }
```
AfuError → HTTP kodu: Invalid 400, NotFound 404, Engine 502, Unavailable 503, diğerleri 500. Hata gövdesi Python'daki `{"ok": false, "error": ...}` biçiminde.

## Test
- Sahte ManagerApi ile tokio testleri.
- Karşılık gelen Python testleri: P\tests\api_guvenlik_test.py, api_debug_duzeltme_test.py, local_api_startup_test.py, add_blob_test.py, pdf_handoff_http_test.py, bosta_uyku_listener_test.py.

SONUC: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_E.md
