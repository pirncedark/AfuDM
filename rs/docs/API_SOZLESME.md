# AfuDM yerel HTTP API sözleşmesi

Kaynak: salt okunur `AfuDM/api/server.py`, `api/web.py`, `core/erisim.py`,
`core/baslangic.py` (18 Ekim 2026). Aşağıdaki JSON'lar biçim örnekleridir;
gid, kimlik, zaman, sürüm, dosya ve servis sonuçları çalışma anında değişir.
Bu belge Python davranışını tanımlar; Rust'taki bilinen farklar en alttadır.

## Başlatma ve ortak kurallar

- Varsayılan adres `127.0.0.1:6811`. Dolu portta sonraki dokuz port denenir;
  `AFUDM_UI_CHILD=1` yalnız istenen portu dener. Testler port **0** kullanır.
- Windows soketi özel sahiplenilir; DNS çözümlemesi yapılmaz.
- `api_token.txt`: 24 rastgele bayttan URL-safe, padding içermeyen token.
  Mevcut boş olmayan token korunur. `api_endpoint.json`: `{"port":6811,"token":"<gizli>"}`.
  `AFUDM_LISTENER_PORT` varsa endpoint portu onun değeridir. Sırlar loglanmaz.
- **T**: `X-AfuDM-Token: <gizli>` zorunlu. **Q**: aynı başlık veya yalnız
  `/dosya` için `?token=<gizli>` / `?k=<gizli>`. Dolu başlık sorgudan önceliklidir.
  Diğer korumalı yollarda sorgu tokenı kabul edilmez. **A**: anahtarsız.
- CORS: yalnız `chrome-extension://[a-p]{32}` ve tam biçimli HTTP/HTTPS
  loopback originleri (`localhost`, `127.0.0.1`, `[::1]`, isteğe bağlı port).
  Dış origin için Allow-Origin yazılmaz; CORS bir kimlik doğrulama mekanizması değildir.
  İzinli origin için `Vary: Origin`; izinli başlıklar `Content-Type, X-AfuDM-Token`;
  yöntemler `GET, POST, OPTIONS`. OPTIONS 204, JSON gövdesi yoktur.
- IP başına 60 saniyede 120 istek. Aşım: 429 `RATE_LIMIT`.
  Python GET `/s/*` ve GET `/_listener/*` bu sayaçtan muaftır.
- JSON POST sınırı 8 MiB. Gövde JSON nesnesi olmalıdır; boş gövde `{}` sayılır.
  Okuma zaman aşımı 15 saniye. `GOVDE_HATASI`: 400 (bozuk/eksik/negatif uzunluk),
  408 (zaman aşımı), 413 (boyut aşımı).
- Standart açık hata: `{"ok":false,"code":"GID_GEREKLI","message":"gid gerekli","error":"gid gerekli"}`.
  Hata gövdesi Python sözleşmesiyle aynıdır (afudm-api `hata_yaniti`, g1/g2/h dahil):
  `{"ok":false,"code","message","error"}`; `message` ve `error` aynı metindir.
  Eşleme (Python `core/hata.py` hata_json): Invalid -> 400 `BAD_REQUEST`;
  NotFound -> 400 `KAYIT_YOK` (Python KayitYok); Io -> 400 `IO`;
  Unavailable -> 503 `KULLANILAMIYOR`; Engine/Db/Other -> 500 `INTERNAL` ve genel metin
  `beklenmeyen bir sunucu hatasi olustu` (aria2/yt-dlp iç metni istemciye gitmez).
- Korunan genel yol: 401 `GECERSIZ_TOKEN` / `gecersiz token`.
  `/indir`, `/dosya`, `/klasorler`: 401 `ANAHTAR_GEREKLI` / `anahtar gerekli`.
  Bilinmeyen yol: 404 `BILINMEYEN_YOL` / `bilinmeyen yol`.
- Dosya yolu istemciden alınmaz. Sunucu gid'den çözer; aktif indirme kökü
  dışına çıkan yol ve symlink/junction hedefi 403 `HEDEF_DISARIDA` alır.

## E ekibi: çekirdek uçlar

| Yöntem / yol | Kimlik | İstek örneği | Başarı yanıt örneği | Özel hatalar |
|---|---|---|---|---|
| GET `/ping` | A | Gövde yok | `{"ok":true,"app":"AfuDM"}` | 429 |
| GET `/show` | A | Gövde yok | `{"ok":true}`; pencereyi gösterir | 429 |
| GET `/snapshot` | T | Gövde yok | `{"ok":true,"items":[],"mode":"normal"}`; manager snapshot alanları aynen birleşir | Manager hatası |
| GET `/probe?url=https%3A%2F%2Fexample.test%2Fa` | T | Sorgu `url` | `{"ok":true,"info":{"title":"Video"}}` | Python probe hatası 400 |
| GET `/peers?gid=g` | T | Sorgu `gid` | `{"ok":true,"peers":[]}` | Manager hatası |
| GET `/seed?gid=g` | T | Sorgu `gid` | `{"ok":true,"gid":"g"}` + seed_bilgi alanları | 400 `GID_GEREKLI` |
| GET `/torrent/dosyalar?gid=g` | T | Sorgu `gid` | `{"ok":true,"gid":"g","hazir_degil":false,"neden":"","dosyalar":[]}` | 400 `GID_GEREKLI`; Python manager hatası 400 |
| GET `/torrent/metrik?gid=g` | T | Sorgu `gid` | `{"ok":true,"gid":"g"}` + torrent_metrikleri alanları | 400 `GID_GEREKLI`; Python manager hatası 400 |
| GET `/klasorler` | T | Gövde yok | `{"ok":true,"ana":"C:\\Downloads","kategoriler":[{"anahtar":"video","ad":"Video"}],"acik":false}` | Manager/store hatası |
| GET `/capabilities` | T | Gövde yok | Store `api_capabilities` kaydı varsa o; yoksa Python varsayılanı: `{"ok":true,"app","surum","api":2,"kip":"headless","uzanti_surumu","motorlar","protokoller","turler","roller","ozellikler","sinirlar"}` | Store hatası (Store kaydı yokluğu 503 DEĞİL) |
| GET `/windows-integration` | F3 | Gövde yok | App (Ekip F3) rotayı ekler; afudm-api'de rota YOK, bu yüzden 404 `BILINMEYEN_YOL` | — |
| GET `/indir?gid=g` | T | Sorgu `gid` | 200; JSON yok, application/octet-stream dosya akışı | 400 `GID_GEREKLI`; 403 `HEDEF_DISARIDA`/`ERISIM_ENGEL`; 404 `BULUNAMADI`; 500 `AKIS_HATASI` |
| GET `/dosya?gid=g&k=<gizli>` | Q | Sorgu `gid` | 200; JSON yok, dosya türüne uygun MIME ile akış | 400 `GID_GEREKLI`; 403 `HEDEF_DISARIDA`; 404 `DOSYA_YOK` |
| POST `/add` | T | `{"url":"https://example.test/a.pdf","audio_only":false,"playlist":false}` | `{"ok":true,"id":7,"gid":"g"}` + manager.add sonucu | 400 doğrulama; 403 `HEDEF_DISARIDA` |
| POST `/add_blob?filename=a.pdf` | T | JSON yok, Content-Length ile ham dosya baytları | `{"ok":true,"id":8,"gid":"g"}` + add_completed_file sonucu | 413 `DOSYA_BUYUK`; 400 `DOSYA_ALINAMADI` |
| POST `/control` | T | `{"action":"pause","gid":"g"}` | `{"ok":true}`; ayarla eyleminde manager sonucu eklenir | 400 `BILINMEYEN_EYLEM` |
| POST `/settings` | T | `{"kategori_klasorleri":true}` | `{"ok":true,"settings":{"kategori_klasorleri":true}}` | Manager doğrulama hatası |
| POST `/renew` | T | `{"gid":"g","new_url":"https://example.test/new"}` | `{"ok":true,"gid":"g"}` + renew sonucu | 400 `BAD_REQUEST`: `gid ve url gerekli` |
| POST `/mode` | T | `{"profil":"normal"}` veya `{"mode":"turbo"}` | `{"ok":true,"profil":"normal"}` + set_mode sonucu | 400 `BAD_REQUEST`: `profil gerekli (snail\|normal\|turbo)` |
| POST `/torrent/secim` | T | `{"gid":"g","indeksler":[1,"2",3.0]}` | `{"ok":true,"gid":"g","indeksler":[1,2,3]}` + manager sonucu | 400 `GID_GEREKLI`/`GECERSIZ_SECIM` |
| POST `/seed/tazele` | T | `{"gid":"g"}` | `{"ok":true,"gid":"g"}` + seed_tazele sonucu | 400 `GID_GEREKLI` |
| POST `/tracker/tara` | T | `{"gid":"g"}`; boş gid kabul edilir | `{"ok":true,"gid":"g"}` + tracker_tara sonucu | Manager hatası |
| POST `/windows-integration` | F3 | `{"id":"...","action":"test"}` | App (Ekip F3) tarafında; afudm-api'de rota yok (404) | — |
| POST `/handoff/error` | T | `{"error":"Tarayıcı devredemedi"}` | `{"ok":true}` | Gövde hatası |
| POST `/token/rotate` | T | `{}` | `{"ok":true,"rotated":true}`; eski token derhal geçersiz | 503 `KULLANILAMIYOR` (Python callback yoksa) |
| GET `/_listener/ready` | T | Gövde yok | `{"ok":true}`; yalnız UI child | 401 veya 404 `{"ok":false}` |
| GET `/_listener/idle` | T | Gövde yok | `{"ok":true,"sleep":false}`; lifecycle callback | 401 veya 404 `{"ok":false}` |
| GET `/_listener/quit` | T | Gövde yok | Lifecycle callback sonucu; UI child kapanışı | 401 veya 404 `{"ok":false}` |

`/klasorler` tam kategori sırası: telefon → 📱 Telefona İndir, video → Video,
muzik → Müzik, belge → Belgeler, program → Programlar, arsiv → Arşiv,
resim → Resimler, torrent → Torrent, genel → Genel.

`/control` eylemleri: pause, resume, remove (`delete_files`, varsayılan false),
pause_all, resume_all, ayarla (`baglanti`, `hiz_kb`).
Boolean alanları: JSON true/false, null, metin true/1/false/0/boş/no;
sayısal 0/1 kabul edilmez. Torrent indekslerinde boolean ve kesir reddedilir;
metin tamsayı ve tam değerli float kabul edilir, sıfır/negatifler ayıklanır.

`/add` isteğinde `url` öncelikli, `source` yedektir. Diğer alanlar:
kind, dest_dir, quality, audio_only, playlist, headers, filename, cookies,
user_agent, title, start_at, proxy, checksum, altyazi_diller, oto_altyazi,
altyazi_goem, kucuk_resim, ustveri_goem, bolumler, sponsorblock, bolum_araligi,
kapsayici, ses_formati, dosya_sablonu, tarayici_cerezi.
Kategori dest_dir verilmemişse alt klasöre çevrilir. `interactive:true` ve açık
kaydetme penceresi (veya prompt_source desktop) Python'da indirmeyi başlatmaz:
`{"ok":true,"pending":true,"id":7}` döner. Bu id UI onay kuyruğunun kimliğidir.

`/add_blob`: 512 MiB üstü reddedilir, Transfer-Encoding kabul edilmez;
yalnız filename sorgusu kullanılabilir. Yol ayırıcı, kolon, NUL, `.`/`..`
reddedilir. Dosya özel oluşturulur; aynı isimde `a (1).pdf` denenir.
Yarım aktarımda yeni dosya silinir; mevcut dosyanın üstüne yazılmaz.
Dosya akışlarında RFC 5987 UTF-8 filename* kullanılır.

## E ekibi: uyuyan dinleyici

| Yöntem / yol | Kimlik | İstek | Yanıt | Hata |
|---|---|---|---|---|
| POST `/add` | T | `{"url":"https://example.test/a"}` | 202 `{"ok":true,"queued":true,"request_id":"32-hex-karakter"}` | 503 `{"ok":false,"error":"Istek alinamadi. AfuDM'i acip yeniden dene."}` |
| GET/POST `/_listener/status` | T | `{}` | `{"ok":true,"child_pid":null,"pending":0,"states":[],"error":""}` | 401 anahtar gerekli; 503 |
| POST `/_listener/notify` | T | `{"title":"AfuDM","message":"Tamamlandı"}` | `{"ok":true}` | 401; 503 |
| GET/POST `/_listener/exit` | T | `{}` | `{"ok":true}`; dinleyici kapanır | 401; 503 |

Dinleyici `data/listener_queue/<request_id>.json` yazar. Dış JSON:
`{"state":"queued","body":"dpapi:<base64>"}`; Windows'ta body mevcut kullanıcı
DPAPI ile şifrelenir. `queued` → gönderimden önce `uncertain` diske yazılır;
başarılı `{ok:true}` sonrası silinir, açık ret `rejected` olarak saklanır.
Belirsiz sonuç yeniden gönderilmez. 256 kayıt sınırı vardır. Desteklenen
http/https/ftp/sftp/magnet veya .torrent kaynakları dışındaki adresler, özellikle
file://, 202 verilmeden reddedilir. Diğer uçlar UI child'a aktarılır.

## G ekibi: yalnız belgeleme, E router'ına eklenmez

Tüm yollar **T** kimliği ister. Servis yanıtları ek bir sarmalama olmadan döner.

| Yöntem / yol | İstek örneği | Yanıt biçimi / örneği | Hatalar |
|---|---|---|---|
| GET `/eklentiler` | Gövde yok | eklentiler.liste() JSON nesnesi | Servis hatası |
| GET `/eklenti/gunluk?ad=x` | ad sorgusu | eklentiler.gunluk(ad) JSON nesnesi | Servis hatası |
| GET `/eklenti/islem` | Gövde yok | eklentiler.islem() JSON nesnesi | Servis hatası |
| POST `/eklenti` | `{"eylem":"incele","yol":"x.afup"}` | eklentiler.incele(yol) JSON nesnesi | 400 `BILINMEYEN_EYLEM` |
| POST `/linkgrabber` | `{"metin":"https://example.test/a","dosya":false}` | `{"ok":true,"pending":true}` | 400 `BAD_REQUEST`: metin gerekli; 503 `UI_YOK` |
| GET `/rules` | Gövde yok | `{"ok":true,"rules":[]}` | Store hatası |
| POST `/rules` | `{"rules":[{"name":"Kural","active":true,"conditions":[],"actions":{}}]}` | `{"ok":true,"rules":[{"id":"api-rule-1","name":"Kural","active":true,"match_type":"all","conditions":[],"actions":{}}]}` | 400 `BAD_REQUEST`: rules liste olmali / her kuralin adi olmali |
| POST `/reliability/integrity` | `{}` | reliability.integrity() JSON nesnesi | Servis hatası |
| POST `/reliability/backup` | `{}` | reliability.backup() JSON nesnesi | Servis hatası |
| POST `/reliability/diagnostics-preview` | `{}` | reliability.diagnostics_preview() JSON nesnesi | Servis hatası |
| POST `/reliability/diagnostics-export` | `{}` | reliability.diagnostics_export() JSON nesnesi | Servis hatası |

Eklenti eylemleri: incele(yol), kur(yol,onaylanan_izinler), guncelle(ad,yol),
geri_al(ad), kaldir(ad), etkinlestir(ad,acik), yeniden_baslat(ad),
ayar(ad,ayarlar), islem_iptal(). Kur/güncelle arka planda başlar;
GET /eklenti/islem ile izlenir. Dinamik eklenti ve reliability servislerinin
iç alanları kendi ekip sözleşmelerinde tamamlanmalıdır; burada uydurma alan yoktur.

## H ekibi: yalnız belgeleme, E router'ına eklenmez

| Yöntem / yol | Kimlik | İstek | Yanıt | Hata |
|---|---|---|---|---|
| GET `/pair` | A, loopback ve açık eşleşme penceresi | Gövde yok | `{"ok":true,"token":"<gizli>"}` | 403 `ESLESME_YEREL_GEREKLI` / `ESLESME_KAPALI` |
| GET `/m`, `/m/` | A | İsteğe bağlı `?k=<gizli>` | HTML mobil.html (exe'ye gömülü, rs/app/ui kaynağı); JSON yok; no-store | — (gömülü, 404 yok) |
| GET `/manifest.webmanifest` | A | Gövde yok | application/manifest+json; no-cache | 404 `SAYFA_YOK` |
| GET `/i18n.js` | A | Gövde yok | text/javascript; no-cache | 404 `SAYFA_YOK` |
| GET `/sw.js` | A | Gövde yok | text/javascript; no-cache; Service-Worker-Allowed: / | 404 `SAYFA_YOK` |
| GET `/ikon.png` | A | Gövde yok | image/png; public max-age=31536000 | 404 `SAYFA_YOK` |
| POST `/share_create` | T | `{"gid":"g"}` | `{"ok":true,"token":"<paylasim-tokeni>","filename":"a.pdf"}` | 400 `GID_GEREKLI`; 404 `HAZIR_DEGIL`/`BULUNAMADI`; 403 `HEDEF_DISARIDA` |
| GET `/s/<paylasim-tokeni>` | A, yoldaki paylaşım tokenı | İsteğe bağlı Range: bytes=0-99 | 200/206 dosya baytları; Accept-Ranges: bytes, Content-Range | 404 `SAYFA_YOK`; 416 Content-Range: bytes */boyut; 500 `AKIS_HATASI` |

`api/web.py` ayrıca ayrı LAN panelini tanımlar: rol anahtarları,
X-AfuDM-Oturum, origin/CSRF kontrolleri ve HizSinirlayici. LocalAPI'nin
dosya tokenıyla aynı kimlik mekanizması değildir. E'nin erisim modülü rol,
anahtar, istemci ve profil depolamasını sunar; H bu paneli birleştirir.

## Rust entegrasyonu ve açık sözleşme sorunları

Uygulama çekirdek/G/H router'larını birleştirir, `with_auth` katmanını **bir kez**
uygular, `serve` çağırır ve dönen gerçek portla `write_endpoint(&ctx,port)` çağırır.
Dinleyici kendi endpoint/token başlangıcını yapar. LAN bind için mevcut `serve`
imzası yalnız loopback sunar; ayrı web sunucusu H/app kapsamındadır.

`ApiCtx` sözleşmesi şu bilgileri taşımıyor; E diğer ekip dosyalarını değiştirmedi:

1. Yetenek servisi: capabilities Store `api_capabilities` kaydını okur; kayıt
   yoksa Python `servis.yetenekler()` varsayılanını üretir (503 yok). `surum` /
   `uzanti_surumu` Rust derleme sürümüdür (CARGO_PKG_VERSION), Python'da 2.9.6.
   Windows uçları afudm-api'de YOKTUR; F3 app tarafında ekler.
2. TorrentDosyaListesi metadata'sı: ManagerApi Vec<Json> döndürdüğünden
   hazir_degil/neden bilgisi taşınamıyor; şimdilik false/boş döner.
3. UI lifecycle quit/idle yan etkisi: UiBridge kapatma/uyku callback'i yok.
   `/ready`, `/idle` sorgusu var; `/quit` için uygulama callback'i gerekli.
4. Interactive: UiBridge onaylanmış isteği döndürüyor, Python bekleyen id
   döndürüyor; mevcut Rust kodu onay sonrası manager'a ekler. Birebir değildir.
5. Telefon dosyası için RPC tell_status yok; Rust Store.path yedeğini kullanır.
6. ErisimDeposu çok adımlı yazmaları aynı nesnede kilitler; Store trait'i
   transaction sağlamadığından Python'un tek transaction atomikliği yoktur.
7. HizSinirlayici canlı ayarla metodu henüz taşınmadı.
8. Python /probe, /seed, torrent hatalarının 400 davranışı ile görevdeki
   zorunlu AfuError eşlemesi farklıdır; Rust görev eşlemesini uygular.

Bu maddeler çözülmeden tam Python davranış eşitliği iddia edilmez.
