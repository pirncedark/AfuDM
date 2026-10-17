# SONUC T1: Python ↔ Rust kara kutu uyum testi

Durum: TAMAM (koşu bitti), AMA sonuç NEGATİF. 90 adım koştu; **57 kritik, 34 orta, 0 kozmetik** fark var. Çıkış kodu 1 (kritik var). "Çalışıyor" iddiası için bu test bugün geçmiyor.

## Ne koştu

- Komut: `python rs\tests_parity\uyum_testi.py` (son koşu: `python -u tests_parity/uyum_testi.py`).
- Python: `C:\Users\afuuu\Desktop\afuproject\AfuDM` kaynağından, headless benzeri. Veri `AFUDM_DATA_ROOT` ile geçici klasöre, aria2 RPC portu `AFUDM_RPC_PORT` ile ayrı.
- Rust: `rs\app\target\release\AfuDM.exe` geçici klasöre kopyalandı (kopya saati ~02:36; exe'nin kaynak derlemesi 02:25'ti, koşu sırasında 02:39'da başka ajan yeniden derledi, kopya etkilenmedi). `AFUDM_PORT` ile çalıştı, aria2c kopyalandı.
- Kullanıcının 6811 AfuDM'i (PID 29328) ve 6810 aria2'si (PID 5932) koşu boyunca ve sonrasında yanıt verdi/yerinde. `P\data` imzası koşu öncesi-sonrası aynı (`P\data degismedi: True`).
- Test süreçleri ve geçici klasör temizlendi.
- Ham sonuç: `rs\tests_parity\rapor\sonuc_son.json`. Harness: `rs\tests_parity\uyum_testi.py`. Adımlar: `rs\tests_parity\senaryolar\temel.json`. Açıklama: `rs\tests_parity\README.md`.

Not: Koşu sırasında harness'ın bir kez takıldığı sanıldı; gerçekte `bekle` (indirme bekleme) döngüsünü bekliyordu. Önceki bir koşu benim tarafımdan erken öldürüldü, geçici `faulthandler` tanılaması eklendi ve kaldırıldı. Son koşunun sonuçları yukarıdaki sayılar.

## Senaryo başına GEÇTİ / FARK

| Grup | Adım | Fark'sız (GEÇTİ) | Kritik içeren | Not |
|---|---|---|---|---|
| 1 Çekirdek | 6 | 5 | 1 | `/capabilities` Rust 503 |
| 2 Ayarlar | 4 | 3 | 1 | `GET /settings` 404 vs 405 |
| 3 Ekleme | 11 | 8 | 3 | hata gövdesinde `code`/`message` eksik |
| 4 Kontrol | 11 | 8 | 3 | gid yok 400 vs 404; resume 500 vs 502 |
| 5 İndirme sonu | 8 | 8 | 0 | **GEÇİYOR AMA ANLAMSIZ**: iki taraf da satır/indirme bulamadı (aşağıda) |
| 6 Torrent | 10 | 9 | 1 | secim geçerli: iki tarafta 400 (metadata hazır değil) |
| 7 Yardımcı | 8 | 5 | 3 | probe url yok 400 vs 502 |
| 8 Kurallar/eklenti | 15 | 12 | 3 | reliability 200 vs 405; windows 200 vs 503 |
| 9 Paylaşım/statik | 11 | 6 | 5 | Rust `/m`, manifest, i18n, sw, ikon 404 |
| 10 Blob/handoff/token | 6 | 6 | 0 | GEÇTİ (token rotate sonrası eski token 401 dahil) |

Toplam: 90 adım, 57 kritik fark, 34 orta fark, 0 kozmetik.

## Farklar (📍 Rust tahmini, Python karşılığı)

1. **Kritik, `/capabilities` 1.2**: Rust 503, Python 200 ve tam JSON.
   📍 `rs\crates\afudm-api\src\lib.rs:297` (`capabilities`): `api_capabilities` Store kaydı yoksa 503. API_SOZLESME madde 1 ile aynı bilinen boşluk. Python: `{ok,app,surum,api,kip,...}`.
2. **Kritik, `GET /settings` 2.1**: Python 404, Rust 405.
   📍 `lib.rs:48` yalnız `.route("/settings", post(settings))`. Python GET'e 404 döner. Düşük etki, durum kodu eşleşmeli.
3. **Kritik (sözleşme), hata gövdesi 3.2, 3.3, 3.4, 4.3, 6.4, 7.3, 7.7, 4.2**: Python `{ok,code,message,error}`; Rust yalnız `{ok,error}`.
   📍 `lib.rs` `fn error(...)` (≈satır 138-145) manager hatalarında `code`/`message` üretmiyor. `fault()` (lib.rs:130-137) üretiyor, ama her hata yolunda kullanılmıyor. API_SOZLESME "Rust ortak sözleşmesi `{ok,error}`" diyor. Yani bu, bilinen sözleşme farkı; ama Python istemcileri `code`'a güveniyorsa kırılır. **Karar gerekli**: sözleşmeyi mi değiştirelim, Rust'ı mı Python'a mı uyduralım.
4. **Kritik, `/control` gid yok 4.5**: Python 400 `GID_GEREKLI`, Rust 404.
   📍 `lib.rs:364` (`control`): `gid = text(&data,"gid")` boş kontrolü yok; `manager.pause("")` NotFound→404. Düzeltme: boş gid için `fault(400,"GID_GEREKLI","gid gerekli")`.
5. **Orta, `/control` resume 4.2**: Python 500 "beklenmeyen bir sunucu hatasi olustu", Rust 502 aria2 mesajı. Contract'a göre Engine→502 Rust doğru; Python 500 veriyor. Mesaj metni de farklı (orta).
6. **Kritik, `/probe` url yok 7.2**: Python 400, Rust 502 (`ERROR: [generic] '' is not a valid URL`).
   📍 `lib.rs:238-244` (`probe`): `q(&query(&req),"url")` boş kontrolü yok, boş url yt-dlp'ye gidiyor. Düzeltme: boş url → 400 (API_SOZLESME: "Python /probe hatası 400").
7. **Kritik, `/reliability/integrity` 8.10 ve `/diagnostics-preview` 8.11**: Python 200 JSON, Rust 405.
   📍 `crates\afudm-api` içinde `/reliability` rotası bulunamadı (grep boş). 405 "yol var, yöntem yok" anlamına gelir; rota H/G ekibinde (`afudm-extras`) olabilir. Doğrulanmadı; kaynağı bul.
8. **Kritik (kapsam), `/windows-integration` 8.12**: Python 200 `{ok,integrations,scan,service}`, Rust 503.
   📍 `lib.rs:294` (`windows_unavailable`). API_SOZLESME'de 503 Rust için beklenen. Yani bilinen eksik, Windows entegrasyonu bağlanmadı.
9. **Kritik, H statik dosyaları 9.6-9.10** (`/m`, `/manifest.webmanifest`, `/i18n.js`, `/sw.js`, `/ikon.png`): Python 200, Rust 404.
   📍 Rotalar `rs\crates\afudm-extras\src\h\mod.rs:24-29` içinde tanımlı ve `boot.rs` (≈118-122) H router'ı birleştiriyor. Koşudaki exe 02:25 derlemesi. 404 kaynak ile çelişiyor: **kaynak-exe uyuşmazlığı olabilir**. Derleme sonrası yeniden koş; hâlâ 404 ise `with_auth`/merge sırasını incele. Python'da ayrıca `cache-control` ve `service-worker-allowed` başlıkları var.
10. **Orta, `/add` kopya 3.2 ve geçersiz URL 3.3, file:// 3.4**: durum kodları eşleşiyor (400), fark yalnız gövde alanları (madde 3).
11. **Orta, `/settings` POST, `/add` 401/403 ve CORS 3.5-3.11**: fark yok. CORS `Access-Control-Allow-Origin` davranışı Python ile aynı.

## Açık kapsam boşlukları (sonuç "geçti" görünse de kanıt değil)

- **5.1-5.7 indirme sonu**: iki tarafta da `/snapshot` içinde `gid_a` satırı bulunamadı (5.1 `satir_yok`, 90 sn bekleme). Sonuç: `/indir` ve `/dosya` her iki tarafta 404. Bu yüzden indirme dosya akışının byte/hash eşitliği **kanıtlanmadı**. Harness'ta (veya snapshot'ta) satır eşleme sorunu var; ayrı bir tur gerek.
- **6.4 torrent secim geçerli**: iki tarafta 400 (metadata hazır değil). Torrent detay uçları kısmen koştu, eşitlik ancak metadata gelince kanıtlanır.
- **9.1-9.4 paylaşım `/s/`**: `/share_create` her iki tarafta 404 (gid_a yok). Paylaşım akışı test edilmedi.
- **`/show`, `/linkgrabber` UI yolu, `/_listener/quit|exit|notify`, `POST /windows-integration`**: bilerek atlandı (pencere açma ve yıkıcı etki riski). README'de belirtildi.

## Sonuç ve önerilen sıra

1. Kritik (Rust, hızlı): `/control` gid boş kontrolü (📍 lib.rs:364), `/probe` boş url (📍 lib.rs:238), `/settings` GET davranışı (📍 lib.rs:48).
2. Karar: hata gövdesi `code`/`message` sözleşmesi (📍 lib.rs `error`). Python paritesi mi, API_SOZLESME mi?
3. Derle ve H statik / reliability rota durumunu doğrula (9.6-9.10, 8.10-8.11).
4. Harness'ta indirme satır eşlemesini düzelt (5.x), sonra yeniden koş.
5. Bilinen eksikler (capabilities 503, windows 503) ayrı ekip kararı.

Komut sonucu: `OZET: adim=90 kritik=57 orta=34 kozmetik=0`, `P\data degismedi: True`.
