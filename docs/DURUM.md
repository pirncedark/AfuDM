# AfuDM — Durum & Devam Notu
Son guncelleme: 2026-09-18 (video 403 kok nedeni + seed penceresi)

## Ne yapiyoruz
IDM yerine gecen, PORTABLE (tek klasor, kopyala-calistir) Windows masaustu
indirme yoneticisi. Motor: aria2 + yt-dlp.

Konum: `C:\Users\afuuu\AfuDM\`

## DURUM: CALISIYOR — 17/17 duman testi + gorsel dogrulama tamam
Tam test (HTTP + torrent + video) TEK kosuda 17/17 gecti. Paketlenmis
`AfuDM.exe` acildi, gercek pencere ekran goruntusuyle dogrulandi, canli
indirme listesi (http + torrent + video ayni anda) arayuzde dogru akti.

## TAMAMLANAN
- [x] Motorlar `engine/` icine gomulu: aria2c 1.37.0 | yt-dlp 2026.08.19 | ffmpeg 8.1.2
- [x] `core/` : paths, rpc, daemon, db, trackers, manager, clipboard, **netcheck (YENI)**
- [x] `video/ytdlp.py`, `api/server.py`, `ui/`, `app.py`, `extension/`
- [x] `AfuDM.bat` + `kur.bat` + **`AfuDM.exe` (PyInstaller, kok klasorde)**
- [x] Masaustu kisayolu: `C:\Users\afuuu\Desktop\AfuDM.lnk` -> AfuDM.exe
- [x] README.md
- [x] Arayuz TAM TURKCE (ui + uzanti): artik "Tumu" degil **"Tümü"**, "Klasor"
      degil **"Klasör"**, "baglanti" degil **"bağlantı"**...
- [x] Testler: `tests/smoke.py` (gercek indirme), `tests/netcheck_test.py`,
      `tests/manager_test.py` (son ikisi AG GEREKTIRMEZ, saniyeler surer)

## SON TAM TEST (2026-09-16 19:10) — 17/17 GECTI
Birlestirici eklendikten SONRA kosuldu; gerileme yok.
Cevrimdisi takimlar da yesil: netcheck, manager, i18n, format, engines,
mux_ayristirma (17 kontrol), mux (16 kontrol).

## ONCEKI TAM TEST (2026-09-16 17:46) — 17/17 GECTI
Bugunun BUTUN degisikliklerinden sonra kosuldu (dil katmani, motor yonetimi,
format secimi, magnet/baslik duzeltmeleri dahil). Gerileme yok.
  HTTP 16 baglanti | duraklat->surdur bayt kaybi yok | magnet 5 seed/46 peer
  | mukerrer engelleme | .torrent devralma | video 53 format + 18.2 MB mp3

Bugun dokunulan: app.py, core/{daemon,db,engines,lang,manager,netcheck}.py,
video/{ytdlp,mp4kutu}.py, ui/{index.html,app.js,i18n.js,style.css},
extension/* (+_locales), paketle.py, tests/* (5 yeni cevrimdisi test),
README.md, docs/DURUM.md

## TEST SONUCLARI (2026-09-16 13:43, temiz durumda)
17/17 GECTI:
  - aria2 2.6 sn'de ayaga kalkti
  - HTTP: 16 es zamanli baglanti, tepe 4.9 MB/s
  - Duraklat -> surdur: 45.7 MB -> 49.0 MB, bayt kaybi yok
  - Magnet (Sintel): ustveri cozuldu ve devralindi, 9 seed / 47 peer, 2.8 MB/s
  - Mukerrer torrent engellendi, iptal sonrasi .aria2 artigi yok
  - .torrent adresinden devralma calisiyor
  - Video: 53 format okundu, indirme akti, 18.2 MB mp3 uretildi

## YOLDA COZULEN GERCEK KUSURLAR (tekrar etmesin)
1. `rpc.py` HTTPError'u yutuyordu -> aria2'nin gercek mesaji kayboluyordu.
2. Mukerrer magnet: info hash eklemeden once karsilastiriliyor.
3. Iptalde `.aria2` kontrol dosyalari kaliyordu -> `_delete_targets`.
4. aria2c dis indirici olunca yt-dlp ILERLEME BASMIYOR -> aria2c'nin `\r` ile
   bastigi satir ayristiriliyor (`VideoJob._ARIA_RE`). DOGRULANDI.
5. Video is kimlikleri her acilista sifirlanip veritabani cakismasi veriyordu.
6. **IPv6 (YENI, KOK NEDEN COZULDU):** Bu makinede genel IPv6 YOK (yalniz
   Tailscale ULA fd7a::). googlevideo AAAA dondurunce aria2c IPv6'yi deniyor,
   WSAENETUNREACH aliyor ve indirmeyi IPTAL EDIYOR — IPv4'e DUSMUYOR. (yt-dlp'nin
   kendi indiricisi duser; bu yuzden hata sadece aria2c dis indiricide cikiyordu.)
   Cozum: `core/netcheck.py` IPv6'yi CALISMA ANINDA olcer (UDP connect ile rota
   secimi; paket gitmez) ve gerekirse aria2'ye `--disable-ipv6=true` verir.
   Bayrak SABIT DEGIL: klasor IPv6'si calisan makineye kopyalanabilir.
   Kanit: bayraksiz "aria2c exited with code 1", bayrakli 10 sn'de 9.7 MB tamam.
7. **Magnet ustveri satiri:** Devralinan `[METADATA]...` kaydi listede ayri bir
   "bitti" satiri olarak goruluyordu -> `Manager.is_metadata_only` ile gizlendi
   (ustveri HENUZ cozulmediyse gizlenmez, tek geri bildirim o satir).
8. **Video basligi:** URL'den tahmin edildigi icin YouTube'da "watch" yaziyordu
   -> `VideoJob.display_title()` yt-dlp'nin urettigi dosya adini kullanir.

## TEST KAYNAK NOTLARI (zaman kaybetme)
- speed.hetzner.de -> bu makinede DNS COZULMUYOR, kullanma.
- speed.cloudflare.com ve proof.ovh.net -> Range DESTEKLEMIYOR.
- KULLAN: https://download.thinkbroadband.com/100MB.zip (206 + Accept-Ranges).
- Ubuntu .torrent -> tracker "not authorized"; seed testi icin Sintel magneti.
- Duman testi DUSERSE once "zaten kuyrukta" hatasina bak: onceki elle eklenen
  indirme `data/aria2.session` icinde kalmis olabilir. Temizligi: aria2c'yi
  durdur, `data/aria2.session` bosalt, `downloads/` icini temizle.

## PENCEREYI TEST EDERKEN (tuzaklar — bunlarla vakit kaybettik)
- `Start-Process -WindowStyle Hidden` ile baslatirsan pencere GIZLI acilir
  (Windows baslangic durumunu ilk pencereye uygular) — uygulama kusuru DEGIL.
- Pencere ikinci ekranda acilabiliyor; ekran kopyalama duvar kagidi yakalar.
  Dogru yontem: `PrintWindow(hwnd, dc, 2)` (PW_RENDERFULLCONTENT) — WebView2
  icerigini pencere onde olmasa da dogru cikarir.
- pywebview WebView2 profilini `%TEMP%\tmpXXXX\EBWebView` altinda acar.

## PAKETLEME & BOYUT (2026-09-16)
`AfuDM.exe` 30.9 MB -> **16.8 MB**. Spec: `build_out/AfuDM.spec`.
Cikarilanlar (hicbiri import EDILMIYOR, PyInstaller dolayli almisti):
cryptography 11 MB, setuptools+pkg_resources 10 MB, pygments/jinja2/mako/chardet
1.6 MB, bcrypt, PIL'in gereksiz eklentileri.

**CIKARILAMAYANLAR — denendi, uygulama COKTU:**
- `bottle`   -> webview/http.py:30 kosulsuz import eder. Hata: "No module named 'bottle'"
- `clr`, `clr_loader`, `cffi`, `proxy_tools` -> pywebview'in Windows arka ucu
  (WinForms + WebView2) bunlarla ayaga kalkiyor.

**UPX KAPALI — bilerek (upx=False).** 16.8 -> 13.0 MB indiriyor AMA uygulamayi
SESSIZCE BOZUYOR: pencere aciliyor, arayuz ciziliyor, ama rozet "baglanti yok"
diyor, `Responding=False` ve hicbir dugme calismiyor. Sebep: UPX pythonnet'in
.NET derlemelerini (System.*.dll) sikistirip JS<->Python koprusunu kopariyor.
`upx_exclude`'a 'System.*.dll' eklemek de yetmedi. 3.8 MB icin uygulamayi
islevsiz birakmaya degmez. (UPX indirilmis hali: `build_out/tools/upx.exe`)

**Exe'nin icinde ne kaldi** (24.4 MB toplanan -> 16.8 MB sikistirilmis):
python311.dll 5.5 | libcrypto+libssl 4.0 | encodings+base_library+unicodedata 3.8
| sqlite3.dll 1.4 | PIL 0.85 (tepsi simgesi) — hepsi gerekli, dip nokta budur.

**`engine/` KUCULTULDU: 217 MB -> 120 MB (ffprobe ATILDI).**
Eski: ffmpeg 97.2 + ffprobe 97.0 + yt-dlp 17.0 + aria2c 5.4 = 217 MB.
Yeni: ffmpeg 97.2 + yt-dlp 17.0 + aria2c 5.4 = 120 MB.

Neden ffprobe atildi: ffmpeg'in neredeyse AYNISI (ikisi de statik yapi, ayni
codec setini AYRI AYRI tasiyor) ve yt-dlp ona ihtiyac DUYMUYOR. Ikisi de gercek
indirmeyle test edildi, ffprobe YOKKEN:
  - mp3 cikarma        -> GECTI (18.2 MB mp3, exit 0)
  - video+ses birlestirme -> GECTI (25.5 MB mp4, exit 0, "[Merger] Merging formats")
Kodda ffprobe'a hicbir referans yoktu (sadece belgelerde geciyordu).

DENENDI, VAZGECILDI — paylasimli (shared) LGPL yapi:
BtbN ffmpeg-n8.1-win64-lgpl-shared indirildi ve olculdu. `avcodec-62.dll` TEK
BASINA 86 MB; ffplay haric toplam 157 MB tutuyor. Yani ffprobe'u atmak (120 MB)
paylasimli yapiya gecmekten (157 MB) DAHA IYI. Tekrar denemeye degmez.

Kalan buyuk parca ffmpeg 97 MB — statik LGPL yapi, tum codec'leri tasiyor.
Daha da kucultmek icin ffmpeg'i kendimiz derlemek gerekir (sadece mux + mp3),
~20 MB'a inebilir ama derleme zinciri gerekir.

## DIL DESTEGI (i18n) — BITTI, 2026-09-16
Turkce + Ingilizce. Ayar `language`: auto | tr | en (varsayilan auto).
- `ui/i18n.js`   — 113 anahtar x 2 dil, `t()` + `applyStatic()`;
                   HTML'de `data-i18n`, `data-i18n-ph`, `data-i18n-title`
- `core/lang.py` — Python tarafi (pencere basligi, tepsi menusu, bildirim);
                   `auto` -> `GetUserDefaultUILanguage()` ile Windows dilinden karar
- `extension/_locales/{tr,en}/messages.json` + manifest `__MSG_*__`;
                   Chrome tarayici diline gore KENDI secer
- `tests/i18n_test.py` — 23 kontrol, AG GEREKTIRMEZ: tr/en anahtar kumeleri esit mi,
  HTML/JS'te kullanilan her anahtar sozlukte var mi, uzanti _locales esit mi.

**Dil YENIDEN BASLATMADAN degisir.** Arayuzu app.js cevirir; pencere basligini
`Api.snapshot()` her turda esitler (`_basligi_esitle`), tepsi menusu metinleri
CAGRILABILIR verildigi icin menu her acildiginda guncel dilde gelir.
Dogrulandi: baslik `AfuDM — indirme yoneticisi` <-> `AfuDM — download manager`.

## YOUTUBE ARTIK BIRLESIK FORMAT VERMIYOR (2026-09-16 olcumu)
`yt-dlp --list-formats` ile bakildi: test videosunda 36 formatin HEPSI ya
"audio only" ya "video only". Eski progressive itag 18/22 YOK.
Sonuc: **ffmpeg'siz kurulumda YouTube'dan SESLI VIDEO INMEZ.** Sadece ses iner.
IDM'in kendi birlestiricisi olmasinin sebebi tam da budur.

Buna gore `video/ytdlp.py`:
- `ffmpeg_hazir()` — engine/ffmpeg.exe yoksa SISTEMDEKINE duser (paths._bundled_or_system)
- `format_secimi(quality, audio_only, birlestirilebilir)`
  - birlestirilebilir=True  -> `bestvideo+bestaudio` (eski davranis, mp4'e birlestirir)
  - birlestirilebilir=False -> `best[ext=mp4][acodec!=none][vcodec!=none]/...`
    yani SESI OLAN birlesik format istenir; yoksa yt-dlp acikca hata verir.
    Amac: kullanici sessiz video indirmesin.
- `build_cmd(aria2c, ffmpeg_var)` / `start(..., ffmpeg_var)` — karar disaridan verilebilir
- `tests/format_test.py` — 14 kontrol, ag gerektirmez.

DIKKAT: test makinesinde SISTEM ffmpeg'i kurulu; `ffmpeg_hazir()` bu yuzden
engine/ffmpeg.exe silinse bile True doner. ffmpeg'siz yolu test ederken
`ffmpeg_var=False` ZORLA ver, dosyayi silmek yetmez.

## MP4 BIRLESTIRICI — FIZIBILITE OLCUMU (2026-09-16 15:12)
`video/mp4kutu.py` yazildi (SADECE OKUR): MP4 kutu yapisini cikarir,
`birlestirilebilir_mi(video, ses)` ile iki izin muxlanabilirligini OLCER.

YouTube'dan itag 137 (video) + itag 140 (ses) ayri indirilip bakildi:
  ses.m4a    -> ftyp, moov, free, mdat            = NORMAL MP4 (kolay)
  video.mp4  -> ftyp, moov, sidx, moof, mdat, ...  = **PARCALANMIS MP4**
                (~250 moof/mdat cifti)

**Sonuc: birlestirici tahmin ettigimden COK daha zor.** Parcalanmis MP4'te ornek
tablolari 250 parcaya dagilmis; birlestirmek icin her `trun` kaydini okuyup tum
zaman damgalarini ve dosya konumlarini SIFIRDAN hesaplamak gerekiyor. Ilk
tahminim "birkac saat / 300-400 satir" YANLISTI; gercekci tahmin bir gunu asar
ve senkron hatasi riski yuksek (timescale, avcC, stss).

NOT: ses izinin normal gorunmesi ffmpeg sayesinde — yt-dlp `[FixupM4a]` ile
konteyneri duzeltiyor. ffmpeg YOKKEN ses de parcali gelir.

Karar kullaniciya birakildi; onerilen yol: cekirdek paket + istege bagli ffmpeg
indirme (birlestirici ayri bir is olarak sonra).

## YEREL API TESTI — 10/10 GECTI (2026-09-16 15:09)
`python tests/api_smoke.py` (onceki oturumda yazilmis, ILK KEZ kosuldu):
/ping token istemiyor, yanlis/eksik token reddediliyor, eslestirme penceresi
KAPALIYKEN anahtar verilmiyor ACIKKEN veriliyor, link ekleme/durum/duraklat/
kaldir calisiyor, bos link anlasilir hata veriyor. Uzantinin kullandigi yolun
SUNUCU tarafi tam dogrulanmis oldu; kalan tek sey uzantiyi Chrome'a yukleyip
denemek (elle yapilmali: chrome://extensions > Gelistirici modu > Paketlenmemis).

## ISTEGE BAGLI MOTOR INDIRME — HAZIR (2026-09-16 15:20)
`core/engines.py` + `tests/engines_test.py` (19 kontrol, ag gerektirmez).

Cekirdek paket mantigi:
  aria2c  5.4 MB  ZORUNLU      — onsuz uygulama calismaz
  yt-dlp   17 MB  istege bagli — video siteleri
  ffmpeg   97 MB  istege bagli — birlestirme + mp3 (indirme 164 MB zip)

`durum()` neyin kurulu oldugunu, `eksikler()` neyin eksik oldugunu, `indir(ad)`
indirip yerlestirmeyi yapar. GERCEK INDIRME ile dogrulandi: yt-dlp 17 MB,
13.8 sn, dogrulandi, atomik yerlestirildi, artik dosya birakmadi.

Iki kural kodda kilitli:
1. Dosya once GECICI klasore iner, `_dogrula()` ile CALISTIRILIR, ancak ondan
   sonra yerine tasinir. Yarim/bozuk indirme calisan kurulumu BOZMAZ (test var).
2. `_dogrula()` hem `--version` hem `-version` dener. Bunlar araclar arasinda
   AYNI DEGIL: yt-dlp/aria2c `--version`, ffmpeg `-version` ister. Ilk denemede
   sadece `-version` kullanmistim, saglam inen yt-dlp "bozuk" sayildi.

## MOTOR INDIRME ARAYUZE BAGLANDI (2026-09-16 15:30)
Ayarlar penceresine "Motorlar" bolumu eklendi:
  aria2c  -> "kurulu · 5.4 MB" (yesil)
  yt-dlp  -> "Indir (17 MB)" dugmesi
  ffmpeg  -> indirilirken "iniyor… %37" canli yuzde
Python: `Api.motor_durumu()` / `Api.motor_indir(ad)` (indirme AYRI IS PARCACIGINDA,
arayuz donmaz; ilerleme `_motor_ilerleme` uzerinden okunur).
Arayuz: `renderEngines()` Ayarlar acikken saniyede bir yeniler, pencere kapaninca
zamanlayici DURDURULUR (bosuna sorgu yok).

GORSEL DOGRULAMA YONTEMI (tekrar lazim olur):
pywebview penceresini tiklayamadigimiz icin arayuz TARAYICIDA dogrulandi:
  1. `cd ui && python -m http.server 8731` (file:// protokolu playwright'ta ENGELLI)
  2. playwright ile http://127.0.0.1:8731/index.html ac
  3. `window.pywebview = { api: {...} }` diye SAHTE kopru enjekte et
  4. `setVeil` sinifina "open" ekle, `renderEngines()` cagir, ekran goruntusu al
DIKKAT: tick() dongusu her turda `snapshot().lang` ile dili GERI YAZAR. Ingilizce
gorunusu icin sahte snapshot'in da `lang: "en"` dondurmesi gerekir — yoksa
statik metinler Turkce'ye doner (bu bir KUSUR DEGIL, canli dil takibinin kaniti).

## CEKIRDEK PAKET HAZIR — 22.3 MB (2026-09-16 15:40)
`python paketle.py` -> `build_out/paket/AfuDM/` (22.3 MB)
`python paketle.py --tam` -> her sey icinde (~137 MB)
Icerik: AfuDM.exe 16.8 + engine/aria2c.exe 5.4 + ui/ + extension/ + README.md

GERCEK CALISTIRMA ILE DOGRULANDI: paket kendi klasorunden acildi, aria2c ayaga
kalkti, `data/` PAKETIN ICINDE olustu (portable kaniti), 10 MB'lik HTTP indirme
TAMAMLANDI.

## TEST SIRASINDA CIKAN TUTARSIZLIK — DUZELTILDI
Paket icinde yt-dlp/ffmpeg YOKKEN video isi yine de calisti. Sebep:
`core/paths.py::_bundled_or_system` paket icinde bulamazsa SISTEMDEKINE duser
ve bu makinede ikisi de PATH'te kurulu:
  yt-dlp -> C:\Program Files\Python311\Scripts\yt-dlp.exe
  ffmpeg -> C:\Users\afuuu\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe

Sorun: Ayarlar "kurulu degil" derken uygulama arkadan sistemdekini calistiriyordu.
Yaniltici; ustelik PORTABLE vaadini bozuyor (baska makinede surum farkli olur
veya hic olmaz). Gizlemek yerine ACIKCA BILDIRILIYOR:
  `engines.durum()[ad]["kaynak"]` = "paket" | "sistem" | "yok"
Arayuzde yesil "kurulu · 5.4 MB" / mor "sistemden" / "—" olarak ayriliyor;
"sistemden" rozetinin ustune gelince ne demek oldugu yaziyor ve yaninda yine
"Indir" dugmesi duruyor (kendi kopyani al).

DIKKAT: Bu makinede sistem yt-dlp/ffmpeg KURULU. "Motor yokken ne oluyor"
testleri bu yuzden yaniltici sonuc verir — `ffmpeg_var=False` gibi degerleri
ZORLA vermek gerekir, dosyayi silmek YETMEZ.

## MP4 BIRLESTIRICI YAZILDI VE CALISIYOR (2026-09-16 19:00)
`video/mp4mux.py` (~590 satir) — ffmpeg OLMADAN ayri video ve ses izini tek mp4'te
toplar. Yeniden kodlama YOK: sikistirilmis ornekler oldugu gibi kopyalanir.

Okuma: hem PARCALANMIS (moof/trun, YouTube video izi) hem DUZ (stbl tablolari,
m4a) MP4. Yazma: duz MP4 — ftyp + moov(iki trak) + tek mdat, ~1 sn'lik
DONUSUMLU yiginlar (yoksa yavas diskte ses/goruntu takilir).

**KANIT — ffmpeg'in kendi ciktisiyla kare kare karsilastirildi:**
  46368 karenin (video+ses) HEPSI ayni md5, zaman damgalari dahil.
  Tam kod cozme: sifir hata.

**SENKRONU BOZAN TUZAK (elst):** B-kare kullanan videoda ilk ornegin gosterim
kaymasi (cts) sifir degildir — burada 512 tik = tam bir kare. Duzenleme listesi
(edts/elst) yazilmazsa video sese gore BIR KARE GEC baslar. ffmpeg tam olarak
bunu yapiyor (`medya_zamani=512`); biz de oyle yapiyoruz. Ilk denemede elst yoktu
ve fark SADECE kare karsilastirmasinda goruldu — gozle anlasilmazdi.

Akisa baglanti (`video/ytdlp.py`):
- ffmpeg yoksa format olarak `bv*[ext=mp4]+ba[ext=m4a]` istenir; yt-dlp
  birlestiremez, iki dosyayi birakir, `_kendi_birlestir()` devralir.
- Basarisiz olursa indirme HATAYA DUSMEZ: parcalar diskte kalir.
- Kodek bagimsiz: `stsd` oldugu gibi kopyalandigi icin h264 de AV1 de calisir
  (gercek testte yt-dlp AV1 secti, sorunsuz birlesti).

**UCTAN UCA TEST (gercek indirme, ffmpeg HIC YOKKEN):**
  yt-dlp "exe versions: none" | 2 parca indi | tek mp4 kaldi | 26 sn
  ffprobe: av1 854x480 19037 kare + aac 27331 kare | tam kod cozme hatasiz

### ffmpeg'i "yok" saymanin YOLU (test ederken sasirtti)
yt-dlp ffmpeg'i UC yerde arar ve hepsini kapatmak gerekir:
  1. `--ffmpeg-location` (biz vermiyoruz)
  2. PATH (bu makinede WinGet + Python Scripts'te kurulu)
  3. **KENDI KLASORU** — `engine/yt-dlp.exe` yanindaki `engine/ffmpeg.exe`
Sadece PATH'i temizlemek YETMEZ; `engine/ffmpeg.exe` de gecici kaldirilmali.
Bunu bilmeden yapilan iki test "birlestirici calisti" sanisi verdi; oysa dosyayi
ffmpeg uretmisti (imza: uretilen dosyada `udta` ve `free` kutusu var, bizimkinde yok).

Testler: `tests/mux_ayristirma_test.py` (ornek okuma, 17 kontrol),
`tests/mux_test.py` (birlestirme + ffprobe + tam kod cozme, 16 kontrol).
Ikisi de yerel izlerle calisir; izler yoksa ATLANIR.

## KAYDETME PENCERESI — BITTI (2026-09-18), tests/kaydet_test.py + kuyruk_test.py
IDM'in "indirme bilgisi" penceresi: link nereden gelirse gelsin (uzanti, pano)
indirme HEMEN baslamaz, once pencere acilir — dosya adi, KATEGORI, klasor agaci
ve simdi/sonra secimi. Onaylanmadan motora hicbir sey gitmez.

Parcalar:
- `core/kaydet.py` — kategori tahmini (uzanti/magnet/tur), kategori klasoru
  (downloads/Video, downloads/Muzik...), dosya adi temizligi, klasor agaci
  (kisayollar + diskler, alt klasorler ISTENDIKCE), `Bekleyenler` (onay bekleyen
  istekler; cerez/baslik bellekte, yarim saatte dusuyor).
- `api/server.py` — uzanti `interactive: true` yollar; `_Handler.on_ask` istegi
  bekletir ve `{"ok": true, "pending": true}` doner.
- `app.py` — `kaydet_bilgi`, `klasor_kisayollar/alt/yeni/gozat`,
  `bekleyen_listesi/onayla/iptal`; `core/pencere.one_getir` pencereyi one alir.
- `ui/` — `kaydetVeil` (indirme bilgisi) + `klasorVeil` (klasor agaci); "Link
  ekle" penceresindeki hedef klasor de ayni agaci kullaniyor. Ayar:
  `kaydetme_penceresi`, `kategori_klasorleri` (ikisi de varsayilan ACIK).

CANLI DOGRULAMA (2026-09-18, gercek pencere + gercek indirme):
  /add interactive -> pencere kendiliginden acildi (ad "100MB.zip", kategori
  "Arsiv", hedef downloads\Arsiv) -> klasor agacindan baska klasor secildi ->
  Indir -> 4.7 MB/s, 16 baglanti, SECILEN klasore indi. Kategori klasoru
  (downloads\Arsiv) kendiliginden olusturuldu. Arka arkaya 3 istek: pencere
  ilkini gosterdi, "Sirada 2 istek daha var" yazdi.

TUZAKLAR:
- Bekleyen sayaci yalniz pencere ACILIRKEN yazilirsa arkadan gelen istekler
  gorunmez (pencere acikken `bekleyenYokla` erken donuyordu). Artik pencere
  acikken de sayac isliyor; gosterilen istek listeden dusmedigi icin sayarken
  bir eksigi alinir.
- `klasorSec()` bir SOZ dondurur: ortulunun disina tiklamak ve ESC de sozu
  cozmeli, yoksa kaydetme penceresi bir daha yanit vermez.

## KUYRUK KIMLIGI — 2 GERCEK KUSUR DUZELTILDI (2026-09-18), tests/kuyruk_test.py
1. **"Bu torrent zaten kuyrukta" ama listede YOK.** Uygulama beklenmedik
   kapaninca (ya da aria2 oturumu silinince) veritabaninda "active" kalan kayit
   motorda olmadigi halde mukerrer sayiliyordu. `find_duplicate` artik motordaki
   GID'lerle karsilastirir; karsiligi olmayan kaydi "olu" isaretler ve yol acar.
   **Motor CEVAP VERMEZKEN hicbir kayit olu SAYILMAZ** (bos liste ile
   "bilinmiyor" ayri tutulur: `_live_statuses()` None doner) — gecici bir RPC
   hatasi calisan indirmenin kaydini bozmasin. Video isleri bellekte durdugu
   icin `video_jobs` de canli sayilir.
2. **Yeniden baslatmada magnet kaydi sahipsiz kaliyordu.** aria2 magneti
   oturumdan yeniden okurken YENI GID uretir; kayit hicbirine uymaz (bitince
   "tamamlandi" yazilmaz). `_reattach_torrent` info hash ile kaydi bulup yeni
   GID'e baglar.

## VIDEO INDIRME — IKI GERCEK KUSUR DUZELTILDI (2026-09-18)
Kullanici uzantidan video secti, liste geldi ama indirme "hata" dedi. PENCERE
ACMADAN yeniden uretildi (Manager + VideoJob dogrudan cagrilarak).

1. **aria2c dis indirici googlevideo'dan 403 aliyor** -> `ERROR: aria2c exited
   with code 22` ve is komple dusuyordu. AYNI adres yt-dlp'nin kendi
   indiricisiyle sorunsuz iniyor (matris: cerez var/yok x aria2c var/yok, dordu
   de gecti; hata KARARSIZ, CDN'e bagli). Artik aria2c dusen is bir kez daha,
   dis indirici OLMADAN denenir (`VideoJob._pump` + `build_cmd(dis_indirici=False)`).
   Yalniz ciktida "aria2c exited" gecerse tekrarlanir: "video yok/ozel" gibi
   kalici hatalarda ikinci kosu bosuna beklemedir (olculdu: 2 sn'de biter).
2. **Turkce karakter bozulmasi:** "KANALI GERI ALDIM" -> "KANALI GER? ALDIM".
   yt-dlp ciktisini Windows konsol kod sayfasiyla yaziyordu. OLCULDU:
   PYTHONIOENCODING=utf-8 ISE YARAMIYOR, `--encoding utf-8` cozuyor. Hem
   indirme hem probe komutuna eklendi; probe ciktisi da utf-8 okunuyor.
   Dogrulama: gercek indirme `KANALI GERİ ALDIM ! - YouTube.mp4` olarak bitti.

Uzanti: gercek kalite listesi varken sayfanin kendi ses efektleri
(success.mp3, open.mp3...) listeyi kirletiyordu — kalite varsa yalniz video
dosyalari ve 1 MB ustu dosyalar gosteriliyor.

## SISTEM BAGLANTILARI — BASLANGIC, TEPSI, .TORRENT/MAGNET (2026-09-18)
Kullanici istegi: "pc acildiginda acilsin, kucultunce sag alta insin, torrent
dosyalarini da AfuDM eklesin".

- `core/baslangic.py` — Windows **Baslangic klasorune** .lnk (Run anahtari
  DEGIL: kullanici Gorev Yoneticisi > Baslangic'tan kapatabilsin). Kisayol
  PowerShell + WScript.Shell ile yazilir, ek kutuphane yok. Test: 11 kontrol.
  TUZAK: PowerShell 5.1 BOM'suz betikte Turkce/em-dash'i bozar — betik ASCII
  kalir, metin PARAMETRE olarak gecilir.
- `core/iliskilendir.py` — `.torrent` + `magnet:` icin HKCU\Software\Classes
  kaydi. qBittorrent'in kaydi EZILMEZ: eski ProgId/komut `AfuDM_Onceki*`
  degerlerinde yedeklenir, `kapat()` aynen geri yazar (test bunu dogruluyor).
  OLCULEN SINIR: Windows 11'de "varsayilan uygulama" (UserChoice) kayit
  defterinden ZORLA degistirilemez (hash korumali) — kod denemez bile;
  `varsayilan_mi()` gercegi soyler, arayuz de kullaniciya "sag tik > Birlikte
  ac > Her zaman bunu kullan" diye yazar.
- `core/pencere.kucultunce_gizle` — kucultunce form gizlenir (gorev cubugundan
  da kalkar), geri donus tepsi simgesinden. Tepsideki "Pencereyi goster" artik
  `one_getir` kullaniyor (gizli VE simge durumundaki pencereyi de geri getirir).
- **Komut satiri:** `AfuDM.exe <.torrent|magnet:|http...>` -> `argvden_link` +
  `calisan_ornege_yolla`. AfuDM ZATEN ACIKSA link yerel API'ye verilir ve
  IKINCI PENCERE ACILMAZ (iki ornek ayni veritabanina/motora asilmasin);
  kapaliysa acilir ve link kaydetme penceresinde gelir.
- Ayarlar'a bes yeni secenek: kaydetme penceresi, kategori klasorleri, tepsiye
  kucult, baslangicta ac, .torrent/magnet. Windows'a dokunan ikisi ayrilan
  cagrilarla gider: biri patlasa da otekiler ve ayarlar kaydedilir.

Testler: `tests/baslangic_test.py`, `tests/iliskilendir_test.py` (ikisi de ag
ve pencere GEREKTIRMEZ; gercek Baslangic klasorune ve gercek kayit defterine
DOKUNMAZ — modul degiskeni gecici yere yonlendirilir).

DOGRULANDI (kullanici oyundayken, pencere ACMADAN): uygulama gizli baslatildi
(`-WindowStyle Hidden`), API cevap verdi; `python app.py magnet:...` ikinci
ornegi 0 saniyede cikti (link acik ornege gitti, pencere acilmadi); yeni
`AfuDM.exe` (17.7 MB) paketlendi ve gizli baslatilip ping'lendi.

BEKLEYEN GORSEL DOGRULAMA (pencere gerektirir, kullanici oyunu bitirince):
kucultunce tepsiye inme, Ayarlar'daki bes yeni kutu, .torrent cift tiklama.

## TEPSI SIMGESI — EXE'DE HIC CALISMIYORMUS (2026-09-18, KOK NEDEN)
Kullanici "kucultunce sag altta gozukmuyor" dedi. Olculdu: kaynaktan
(`python app.py`) tepsi simgesi VAR, paketlenmis `AfuDM.exe`'de YOK.

**Kok neden:** `build_out/AfuDM.spec` excludes listesinde `PIL.ImageFont`
vardi. `from PIL import ImageDraw` ImageFont'u import eder -> exe'de
ImportError -> `build_tray` sessizce `return` ediyordu. Exe konsolsuz
(runw.exe) oldugu icin hata HICBIR YERE yazilmiyordu; v1.0'dan beri boyleymis.

Duzeltme:
1. spec'ten `PIL.ImageFont` cikarildi (exe 17.7 -> 17.9 MB).
2. `build_tray` artik hatayi VERITABANINA yaziyor (events): exe'de konsol yok,
   tek teshis yolu bu. `icon.run()` de sarmalanip loglaniyor.
3. `build_tray` simgeyi DONDURUYOR; simge kurulamazsa "kucultunce tepsiye in"
   DEVREYE GIRMEZ — yoksa pencere gizlenir ve uygulamaya ulasilamazdi.
4. Tepsi simgesi pano izleyicisinden ONCE kuruluyor (pano patlarsa simge de
   kurulmadan kaliyordu); pano izleyici ayri try icinde.

**Windows 11 gercegi (degistirilemez):** yeni bir uygulamanin tepsi simgesi
varsayilan olarak "gizli simgeler" (^) altina konur ve bu disaridan
zorlanamaz. Bu yuzden ILK gizlemede bir kez bildirim gosteriliyor
("simge ^ okunun altinda, surukleyip sabitleyebilirsin" — lang: tray.hidden)
ve Ayarlar'da ayni bilgi yaziyor.

## GORSEL DOGRULAMA (2026-09-18, kullanici oyunu bitirdikten sonra)
Gercek pencerede, gercek exe ile, ekran goruntusuyle dogrulandi:
- Ayarlar'da bes yeni kutu dogru durumu okuyor (baslangic ACIK, torrent/magnet
  KAYITLI) + iki ipucu (tepsi, varsayilan uygulama) gorunuyor.
- Kucult -> pencere gorev cubugundan KALKIYOR (IsWindowVisible False), tepsi
  simgesine cift tik -> geri geliyor. Ilk gizlemede bildirim balonu cikti.
- `AfuDM.exe "<yol>.torrent"` -> 1 saniyede ACIK ORNEGE gitti, kaydetme
  penceresi "Torrent" kategorisi ve downloads\Torrent hedefiyle acildi,
  Indir -> 4.1 MB/s, 16 seed.
- Cikan kusur: ayni anda BIRDEN COK AfuDM ornegi acilabiliyor (test sirasinda
  6 surec vardi). Linksiz ikinci acilista da tek ornek kisiti YOK — siradaki is.

## TEK KOPYA + ACILISTA TEPSIDE BASLAMA (2026-09-18, Telegram istegi)
Kullanici: "1 yap. Bilgisayar acildiginda kucuk simge olarak acilsin ve orada
gozuksun, tekrar buyutebilirsin; kucultunce de simge olsun; torrent acildiginda
AfuDM calissin, qBittorrent calismasin."

1. **Tek kopya.** `main()` artik LINK OLMASA DA acik ornege sorar: yeni
   `GET /show` ucu (`_Handler.on_show` -> `pencere.one_getir`). Ikinci acilis
   0.2 saniyede doner, pencere ACMAZ. Onceden 6 kopya birikebiliyordu ve hepsi
   ayni veritabanina/motora asiliyordu.
2. **`--tepside` bayragi.** `create_window(hidden=True)`: pencere hic acilmadan
   tepside baslar. Tepsi simgesi kurulamazsa (bkz. PIL.ImageFont notu) pencere
   GOSTERILIR — yoksa uygulama erisilemez kalirdi.
3. **Baslangic kisayolu bu bayragi tasir.** `baslangic.ac("--tepside")`; ayar
   degisince kisayol YENIDEN YAZILIR (`_kisayol_argumani()` ile karsilastirilir).
   Ayar: `baslangicta_tepside` (varsayilan ACIK).
4. **Windows varsayilan uygulama ekrani dugmesi.** `.torrent` secimini yalniz
   kullanici yapabilir (UserChoice hash korumali) — Ayarlar'daki dugme
   `ms-settings:defaultapps` ekranini aciyor, ipucu da ne yapacagini yaziyor.

TUZAK (olculdu): PowerShell'de `-Command <betik> <arg>` bicimi `$args`'i
DOLDURMAZ, ikinci dizeyi ayri komut sanar; kisayolun argumani yerine yolu
donuyordu. Yol betige gomuldu. Ayrica `Write-Output` uzun satiri SARIYOR —
cikti `[Console]::Out.Write` ile aliniyor.

DOGRULANDI (gercek exe): `AfuDM.exe --tepside` -> pencere gorunmez, tepside
calisir; kisayola tekrar tiklama -> pencere acilir ve TEK pencere kalir;
Ayarlar'da iki yeni ogenin (kutu + dugme) gorseli alindi; kisayolun argumani
`--tepside` olarak okundu; `ms-settings:defaultapps` acildi.
Test: `tests/baslangic_test.py` 7. bolum (bayrak yazilir/temizlenir/geri gelir).

## VIDEO 403 — KOK NEDEN CEREZ (2026-09-18), tests/format_test.py 7. bolum
Kullanicinin iki denemesi de "hata" oldu; veritabanindaki hata metni:
`unable to download video data: HTTP Error 403: Forbidden`.

OLCULDU (ayni video, dort kosu): Referer SUCSUZ — sayfa adresi, youtube.com/
ve Referer'siz, hepsi indi. Fark, uzantinin yolladigi TARAYICI CEREZLERI:
yt-dlp ayni oturum cerezleriyle isteyince YouTube 403 veriyor ("[jsc:node]
Solving JS challenges" satiri da o kosuda cikiyor).

Cozum: `VideoJob.yedek_karari` — dusen kosudan sonra NE denenecegine karar
veren SAF fonksiyon (test edilebilir):
  - "aria2c exited" -> dis indirici olmadan tekrar
  - "403" + cerez varsa -> CEREZSIZ tekrar (cerez kaldirilmaz; giris isteyen
    sitelerde sart, yalniz bu kosuda devre disi)
  - kalici hata ("Video unavailable") -> tekrar YOK (bosuna bekleme)

Ayrica: `--encoding utf-8` (Turkce basliklar), kalite etiketinde GENISLIK —
genis ekran videoda yukseklik 606 cikiyordu ve liste "606p" diyordu; artik
standart disi yuksekliklerde "1440x606" yaziliyor.

## SEED PENCERESI (2026-09-18), tests/seed_test.py
Kullanici: "torrent icin seed guncelleme penceresi ekleyelim" + "seedlere
manuel ekleme yapabilecegimiz bir kisim olsun".

Torrent satirinda **Seed** dugmesi -> pencere: su anki seed/baglanti, torrentin
tracker sayisi, uygulanan liste, liste yasi, DHT, elle eklenen sayisi. Pencere
2 saniyede bir KENDINI TAZELER (yeniden duyurudan sonra seed'in arttigi
gorulsun). "Kendi tracker'larin" kutusu: yapistirilan adresler ayiklanip
(`trackers.ayikla`) `ek_trackerlar` ayarinda saklanir ve her uygulamada
listenin BASINA konur.

OLCULEN GERCEKLER (ayri bir aria2 ornegiyle, kullanicinin isine dokunmadan):
1. **`changeOption(gid, {"bt-tracker": ...})` "OK" der ama duyuru listesi
   DEGISMEZ** — calisan torrente tracker EKLENEMIYOR (load-cookies ile ayni
   tuzak).
2. **Kaldir + AYNI dizine yeniden ekle ISE YARIYOR ve ilerleme KORUNUR:**
   15.5 MB inmis is yeniden eklendikten sonra 26 MB'dan devam etti,
   tracker 2 -> 3 oldu. `seed_tazele` bu yolu kullanir; hicbir dosya silinmez.
3. **aria2'de tek tek PEER (IP:port) eklenemez** — API'sinde boyle bir cagri
   yok; elle eklenebilen sey tracker'dir, arayuz de bunu yaziyor.

CANLI DOGRULAMA (kullanicinin 19 GB'lik torrentinde): pencere acildi (seed 2,
baglanti 6, tracker 22), "Simdi guncelle" -> ilerleme KORUNDU (454 MB -> 476 MB
devam), **baglanti 6 -> 11**, seed 2 -> 3, liste yasi 0 saat. GID degisti,
kayit yeni GID'e baglandi.

NOT — UZANTI GUNCELLENMELI: kalite listesindeki duzeltmeler (sayfa ses
efektlerinin elenmesi, genislikli etiket) Chrome'daki uzanti YENILENMEDEN
gorunmez: chrome://extensions -> AfuDM kartindaki (yenile) simgesi.

## v1.2.0 YAYINLANDI (2026-09-18, kullanici onayiyla)
`gh release create v1.2.0` — paket `build_out/AfuDM-v1.2.0-win64.zip` (20.1 MB,
cekirdek: aria2 var, yt-dlp/ffmpeg Ayarlar'dan iniyor).
https://github.com/pirncedark/AfuDM/releases/tag/v1.2.0

Surum notu (TR+EN) bugunku her seyi anlatiyor: kaydetme penceresi, seed
guncelleme penceresi + kendi tracker'larin, tek kopya, tepsi/acilis,
.torrent-magnet baglama, 403 cerez duzeltmesi, tepsi simgesi kok nedeni,
Turkce karakter, kuyruk kimligi, uzanti kalite listesi temizligi.

TUZAK: `Path("AfuDM-v1.2.0-win64").with_suffix(".zip")` ".0-win64" kismini
UZANTI sanip "AfuDM-v1.2.zip" uretiyor — zip adini metin olarak birlestir.

## TELEFON ARAYUZU — BITTI (2026-09-18), ui/mobil.html
Kullanici Android icin "2" dedi: APK degil, PC'deki AfuDM'i telefondan yoneten
arayuz. Kurulum yok, tek dosya, mevcut LocalAPI uzerinden calisir.

- `api/server.py`: `LocalAPI(..., lan=True)` sunucuyu 0.0.0.0'a baglar
  (VARSAYILAN KAPALI), `/m` ucu `ui/mobil.html`'i servis eder, `lan_adresi()`
  telefonun yazacagi adresi uretir (UDP rota secimiyle LAN IP; paket gitmez).
- `ui/mobil.html`: tek dosya (CSS+JS gomulu), telefon olculeri, canli kuyruk
  (1.5 sn), duraklat/surdur/kaldir, altta sabit link ekleme cubugu.
- Anahtar adresten gelir (`?k=`), telefonda saklanir ve ADRES CUBUGUNDAN SILINIR
  (omuz ustu okunmasin); her API cagrisinda basliga konur.
- `app.py`: `telefon_durumu` / `telefon_ayarla` — kutu acilinca sunucu YENIDEN
  KURULUR, yeniden baslatma gerekmez. Ayar: `lan_erisimi`.

GERCEK TEST (headless Chromium, Pixel 7 profili, kullanicinin ekranina
dokunmadan): sayfa acildi, anahtar adresten silinip saklandi, "bagli" oldu,
kuyruk listelendi, TELEFONDAN link eklendi (5MB.zip listeye dustu),
duraklat isledi, ANAHTARSIZ acilista veri GELMEDI ("anahtar gerekli").
17 kontrol, hepsi gecti.

TUZAK: test kullanicinin 19 GB torrentini duraklatti — test sonunda durum
kontrol edilip SURDURULDU. Gercek isler uzerinde test yaparken kontrol
eylemlerini geri almayi unutma.

## IS SIRASI (kullanici, Telegram 2026-09-17)
1. ~~Kaydetme penceresi~~ — BITTI (2026-09-18, yukari bak).
2. ~~Telefon arayuzu~~ — BITTI (2026-09-18, yukari bak). Kullanici "2 yap" dedi.
3. SIRADA (istenirse): **gercek APK** (Kotlin) — telefonda KENDI basina indiren
   uygulama (ADM gibi cok parcali + Snaptube gibi video + torrent). Bu makinede
   JDK/Android SDK/Gradle/adb YOK: once ~8-10 GB arac kurulumu gerekiyor.

BEKLEYEN DOGRULAMA (kullanici oyundayken calistirilamaz — pencere one gelir):
`tests/port_test.py` ve `tests/extension_test.py` GORUNUR Chromium acar; kaydetme
penceresi uzantiyla ucdan uca (gercek Chrome indirmesi) HENUZ denenmedi. Yerel
API uzerinden (uzantinin yolladigi bicimin AYNISI) dogrulandi.

## SIRADAKI IS
1. **MP4 BIRLESTIRICI (karar bekliyor).** Kullanici "IDM gibi kendi birlestiricimiz
   olsun, paket 23 MB'a insin" dedi. YouTube'un iki izi de MP4 ailesinden:
   video 137/299 (avc1, mp4) + ses 140 (aac, m4a). Yani yeniden kodlama degil,
   REMUX: iki dosyanin moov/stbl tablolarini okuyup tek moov + tek mdat'a dokumak.
   Basarirsa ffmpeg (97 MB) opsiyonel olur, paket ~23 MB'a iner.
   (mp3'e cevirme yine ffmpeg ister — o isteğe bagli kalir.)
2. Cekirdek paket + istege bagli motor indirme (kullanici "1" dedi):
   gonderilen klasor aria2 + AfuDM.exe + eklenti; 4K/mp3 isteyen uygulama
   icinden motorlari indirir, engine/ icine gider (portable bozulmaz).
3. ~~Tarayici uzantisini Chrome'a yukleyip devralmayi canli dene.~~ BITTI — asagida.

## TARAYICI UZANTISI CANLI TEST — 12/12 GECTI (2026-09-16)
`python tests/extension_test.py` — uzanti GERCEK Chromium'a `--load-extension`
ile yuklenir (Playwright). ONKOSUL: AfuDM acik. AG GEREKTIRMEZ: dosyalar
127.0.0.1'deki gecici sunucudan gelir.
  service worker ayakta | acilir pencere "AfuDM çalışıyor" | eslestirme kapaliyken
  reddedildi, acikken anahtar alindi | tarayici indirmesi AfuDM'e devredildi ve
  TAMAMLANDI, tarayicidaki kopya silindi | .txt devralinmadi | AfuDM kapaliyken
  indirmeye dokunulmadi | sayfadaki .mp4 yakalandi | JS hatasi yok

Eslestirmeyi calisan uygulamanin penceresine dokunmadan sinamak icin ayni token
dosyasini kullanan IKINCI bir `LocalAPI` (6899) acilip `open_pairing()` cagriliyor.
DIKKAT: `LocalAPI.start()` `data/api_endpoint.json`'u kendi portuyla EZER —
test yedekleyip geri yaziyor.

**CANLI TESTIN BULDUGU KUSUR (duzeltildi):** acilir penceredeki 5 mesaj
`popup.js`'te SABIT ve aksansiz Turkce'ydi ("Baglandi. Artik...", sunucunun
"eslestirme kapali" metni). Ingilizce kullanici Turkce goruyordu; i18n testi
yakalayamadi cunku sadece getMessage anahtarlarini kontrol ediyor. Simdi
`msgTokenEmpty/msgNoUrl/msgSaved/msgPaired/msgPairClosed/msgNoResponse` locale'de;
403 -> msgPairClosed, baglanti yok -> notifyNotRunning. EN de canli dogrulandi.

TUZAKLAR:
- Ayarlar `<details>` icinde KATLI gelir; once `details summary` tiklanmali,
  yoksa `#port` doldurulamaz ve `inner_text("#pair")` BOS doner.
- Uzanti sayfasinda CSP `unsafe-eval` yasak: `page.wait_for_function("...")`
  CALISMAZ — Python tarafinda `inner_text` ile yokla.
- Kapali porta fetch Windows'ta ~2 sn surer; 1 sn beklemek yetmez.
- Sag tik menusu Playwright'tan tetiklenemez (yerel menu) — elle denenmeli.

## GERCEK CHROME'DA DENENDI (2026-09-17) — kullanici Telegram'dan "sen dene"
- Chrome'a ekle otomasyonu KULLANICININ Chrome'una kurdu (5 adim), uzanti 4,6 sn'de
  /pair ile baglandi. (Eslestirme sunucusu AfuDM kapatilip 6811'de ayni anahtarla
  acildi: uzanti eslesmede portu KAYDEDER, baska porta eslesirse sonra kopar.)
- Chrome'da https://download.thinkbroadband.com/5MB.zip acildi -> AfuDM devraldi,
  5 MB tamam; Chrome Indirilenler'de kopya YOK.

## SURUM 1.1.0 YAYINDA (2026-09-17)
https://github.com/pirncedark/AfuDM/releases/tag/v1.1.0 — `AfuDM-v1.1.0-win64.zip`
(19 MB), etiket 5904beb, sha256 80a21633... Kullanici Telegram'dan "1" ile onayladi.
Icerik: Chrome'a ekle, video paneli, oturum cerezleri, ozel baslik, cekirdek
duzeltmeler. Yayindan once zip gecici klasore acildi: 5 MB indirme tamam, pencere
yanit veriyor, baslik_test paketlenmis exe'de de gecti.

## SURUM 1.0.0 YAYINDA (2026-09-16)
https://github.com/pirncedark/AfuDM/releases/tag/v1.0.0 — `AfuDM-v1.0.0-win64.zip`
(19 MB, cekirdek paket), etiket f4875f1. `gh` OAuth girisiyle (keyring) — PAT YOK.
Yayindan once zip gecici klasore acilip calistirildi: 5 MB indirme tamamlandi,
data/ paketin icinde olustu. Pakette THIRD_PARTY_NOTICES.md (aria2 GPL-2.0).
Git kimligi global ayarli DEGIL: commit'ler `git -c user.name=afuuu -c
user.email=furkanu@gmail.com` ile atiliyor; `git tag -a` bu yuzden patladi,
etiketi `gh release create` olusturdu.

## OZEL BASLIK CUBUGU (2026-09-16)
Kullanici: "header pencere gibi durmasin". `core/pencere.py` + ui (.wc dugmeleri).
Secilen yol — frameless DEGIL (pywebview Windows'ta cercevesiz pencereyi kenardan
boyutlandiramiyor, JS ile takilarak surukluyor, Snap yok):
  1. WM_NCCALCSIZE alt sinifi: baslik yuksekligi istemciye katilir; sol/sag/alt
     gorunmez kenarlar, golge, yuvarlak kose, Snap, gorev cubugu adi KORUNUR.
     Buyutulmuste ust + kenar kalinligi (yoksa icerik ekran disina tasar — olculdu:
     pencere -8,-8 ama istemci 0,0).
  2. WebView2 `IsNonClientRegionSupportEnabled` — pywebview'in on_webview_ready'sinin
     BASINA yamalanir (ayar ilk gezinmeden sonra verilirse etkisiz). `.trace` ->
     `app-region: drag`: surukle/Snap/cift tik Windows'tan.
  3. Ust kenar: 4px serit -> Api.pencere_kenar -> WM_NCLBUTTONDOWN(HTTOP). Fare
     birakilmissa baslatilmaz (yapiskan pencere olmasin).
`tests/baslik_test.py` (11) FARE KULLANMADAN dogrular: Windows'un WindowFromPoint
kurali AfuDM agacinda taklit edilir.

TUZAKLAR (vakit kaybettirdi):
- WindowFromPoint ONDEKI BASKA uygulamayi dondurur (burada bir UnrealWindow vardi).
- WebView2 surukleme alani icin AYRI bir Chrome_WidgetWin_0 acar; ona dogrudan
  WM_NCHITTEST gonderince HER noktaya CAPTION der. Dogru sonuc icin z sirasi +
  HTTRANSPARENT atlama taklit edilmeli.
- `shown` olayinda `evaluate_js` -> "Main window failed to start" (sayfa yok).
  `loaded` olayina tasindi; JS de pywebviewready'de kendisi soruyor.
- **Api.window -> Api._window**: pywebview js_api ozelliklerini DOLASIYOR;
  window.native (.NET formu) sonsuz derinlige inip gunlugu "Empty.Empty..." ile
  dolduruyordu (onceden de vardi, konsol olmadigi icin gorulmemisti).

## CHROME'A EKLEME — BITTI (2026-09-17), tests/chrome_ekle_test.py
Sol menude "Chrome'a ekle" (mavi). Pencere: "Otomatik ekle" + 6 adim canli
(sayfa, gelistirici, yukle, klasor, dogrula, AfuDM'e baglandi) + takilirsa acilan
elle kurulum anlatimi (chrome://extensions ve klasor yolu icin Kopyala).
Pencere acilinca eslestirme 10 dk acilir (Api.chrome_hazirla): ELLE kurulumda da
uzanti kendiliginden baglanir.

Uctan uca test (gecici Chrome profili, kullanicinin profiline dokunmaz): 5 adim
+ uzanti KENDILIGINDEN /pair ile baglandi (5 sn). AfuDM acikken de gecti (6811
reddetti, testin sunucusu 6812).

Parcalar:
- `core/chrome_kurulum.py` — PowerShell + .NET UI Automation betigi (exe'ye ek
  kutuphane YOK), `OtomatikEkleme` (arka planda, durum() ile izlenir).
- uzanti `kendiligindenEslesme()`: onInstalled/onStartup + chrome.alarms (30 sn,
  10 dk), 6811-6820 /pair; `alarms` izni.
- `LocalAPI.son_eslesme` — anahtar en son ne zaman verildi ("baglandi" isareti).
- i18n: `data-i18n-html` (yalniz sabit <b>/<em> metinleri), i18n_test kapsiyor.

OLCULEN GERCEKLER (tekrar deneme):
- Chrome web magazasi disi uzantiyi kendiliginden kurdurmaz; 137+ `--load-extension`
  KAPALI. Tek yol kullanicinin tiklamalarini yapmak.
- **Chrome komut satirindan `chrome://` adresi ACMAZ** (Yeni Sekme acar). Cozum:
  `about:blank` ile YENI sekme -> adres cubugu ("Adres ve arama cubugu") ValuePattern
  -> Chrome ONDEYSE tek Enter (degilse tus gonderilmez, hata + elle yol).
- Gelistirici modu: Button + TogglePattern; yukle: Button + InvokePattern.
- **Klasor penceresi AYRI chrome.exe (utility) surecinde** ve UIA'da "Klasor:" kutusu
  ile "Klasor Sec" GORUNMEZ. Win32'de standart: Edit 1152 + Button 1 -> WM_SETTEXT +
  PostMessage(BM_CLICK). Pencere arama C# yardimcisiyla (PowerShell geri cagrisinin
  ciktisi kaybolur).
- Profil Preferences dosyasina bakmak YANILTIR (Chrome ~10 sn gecikmeli yazar,
  zorla kapatilinca hic yazmaz) — kanit olarak /pair kullanildi.
- Kullanicinin Chrome'u "kurulus tarafindan yonetiliyor": tek ilke
  ExtensionManifestV2Availability=2 (engel DEGIL, uzanti MV3).

## VIDEO PANELI — BITTI (2026-09-16), tests/video_panel_test.py 12/12
IDM gibi: video oynayinca ustunde "AfuDM ile indir" -> kalite listesi -> AfuDM.
- `extension/content.js`: all_frames (gomulu oynaticilar iframe'de), `play` olayi
  yakalama asamasinda, golge DOM dugme, tam ekranda fullscreenElement'e tasinir,
  240x135'ten kucuk videolar (reklam/onizleme) atlanir. Popup: "Oynayan videonun
  ustunde indirme dugmesi goster" (`videoCatch`).
- `background.js` secenek sirasi: HLS ana liste (#EXT-X-STREAM-INF) / DASH
  (Representation height) -> kaliteler + sadece ses; duz dosyalar -> "Dosya";
  hicbiri yoksa `/probe` (yt-dlp) — YouTube gibi adres vermeyen siteler.
- Indirme: kind=video + quality=yukseklik + Referer (oynatici cercevesi) + cerezler
  + title (sekme basligi; HLS'te yt-dlp "master" derdi).

UC GERCEK TUZAK (olculdu):
1. **MV3 service worker ~30 sn bosta KAPANIR** -> bellekteki mediaByTab gider.
   Yakalananlar artik `chrome.storage.session`'da (`medya:<tabId>`); test SW'yi
   CDP ile oldurup sonra secenek istiyor.
2. **Hotlink korumasi:** SW'nin fetch'i oynaticinin Referer'ini TASIMAZ -> 403,
   kalite listesi bos geliyordu (ilk test kosusu). Listeyi artik content.js
   oynatici cercevesinden okuyor (`videoPlaylists` -> fetch -> `texts`);
   okuyamazsa SW yedek.
3. yt-dlp de `Sec-Fetch-Mode` basligi yollar: istekleri tarayicidan o baslikla
   ayirmak YANILTIR. Test .ts parcalarina bakiyor (sayfa parca istemez).

Test videolari ffmpeg test deseninden uretilir (telifli icerik YOK); oynatici BASKA
porttan iframe, HLS Referer'siz 403. Kullanicinin ornek verdigi korsan film sitesi
icin test/ozel ayar YAPILMADI.

## OTURUM CEREZLERI — GIRIS GEREKTIREN SITELER (2026-09-16)
IDM'e gore en buyuk eksik buydu: uzanti yalniz link + Referer yolluyordu,
Google Drive / uyelik isteyen sitelerde AfuDM hata aliyordu.

Akis: uzanti `chrome.cookies.getAll({url})` ile tarayicinin O ADRESE gonderecegi
cerezleri (HttpOnly dahil) + `navigator.userAgent` yollar. Adres olarak
yonlendirme SONRASI `item.finalUrl` kullanilir. Popup'ta "Oturum çerezlerini
gönder" (varsayilan acik).
- HTTP  -> aria2'ye indirme basina `Cookie:` basligi + `user-agent` secenegi
- Video -> yt-dlp'ye `--cookies data/cerez/yt_N.txt` + `--user-agent`

**OLCULDU — aria2 `load-cookies` INDIRME BASINA YOK SAYILIYOR** (kabul ediyor,
hata vermiyor, ama cerez gitmiyor; yalniz global `--load-cookies` calisiyor).
Bu yuzden baslik kullaniliyor; alan adi sizintisini `finalUrl` + getAll({url})
onluyor. Yeniden denemeye degmez.

GUVENLIK: cerez VERITABANINA YAZILMAZ (`Manager._cerezler`, bellekte; is
bitince/silinince birakilir). yt-dlp dosyasi is bitince silinir, acilista
artiklar temizlenir. Satir sonu/sekme iceren cerez atilir (enjeksiyon).
Bilinen sinir: aria2 duraklatilan isin secenegini `aria2.session`'a yazar
(data/ icinde, rpc sirri ile ayni yerde). yt-dlp'nin cerez politikasi
hostOnly bayragini yok sayar: cerez AYNI sitenin alt alanlarina da gider.

Testler: `tests/cerez_test.py` (23, ag yok) + `tests/extension_test.py` artik
**19/19** (giris gerektiren dosya tamamlandi, cerez kapaliyken 403, DB taramasi).
Video cerez yolu komut + dosya duzeyinde test edildi; gercek girisli bir video
sitesiyle DENENMEDI.

## YOLDA BULUNAN 3 GERCEK KUSUR (duzeltildi)
1. **Test calisan uygulamanin motorunu olduruyordu.** `Aria2Daemon.start()` acik
   motora baglaniyor, `stop()` kendi baslatmadigi motoru da kapatiyordu. Ikinci
   AfuDM ya da api_smoke kapaninca ilkinin indirmeleri dururdu. Artik yalniz
   baslatan kapatir. `tests/daemon_test.py` (AfuDM KAPALIYKEN calisir; kusurlu
   kodda DUSTUGU dogrulandi — shutdown eszamansiz, 3 sn beklemeden gizleniyor).
2. **Ayni port iki kez aciliyordu.** HTTPServer SO_REUSEADDR acar; Windows'ta bu
   portu PAYLASMAK demek. api_smoke calisan AfuDM'in 6811'ine ortak oldu, istekler
   rastgele surece gitti. `_ExclusiveServer` (SO_EXCLUSIVEADDRUSE) -> artik 6812'ye
   geciyor. api_smoke da api_endpoint.json'u yedekleyip geri yaziyor.
3. **`rpc.call()` kopan baglantiyi Aria2Error'a cevirmiyordu** (RemoteDisconnected,
   ConnectionResetError URLError DEGIL). `except Aria2Error` bekleyen yoklama
   dongusu coker. Artik ceviriyor.

## TELEGRAM BILDIRIMI — DOGRULANDI (2026-09-16 15:04)
Gercek bot anahtariyla denendi, Turkce ve Ingilizce bildirim IKISI DE gitti
(`Manager.notify_telegram` -> True). Test sonrasi ayarlar GERI ALINDI; AfuDM'de
bot anahtari kayitli DEGIL (kullanici isterse Ayarlar'dan girecek).
Anahtar kaynagi: `antygravitiy/.env` -> MCP_TELEGRAM_TOKEN, chat 1483248658.

## CALISTIRMA
    C:\Users\afuuu\AfuDM\AfuDM.exe       (veya masaustu kisayolu)
    python app.py                        (kaynaktan)
    python tests/smoke.py                (gercek indirme, 17 test)
    python tests/netcheck_test.py        (ag gerektirmez)
    python tests/manager_test.py         (ag gerektirmez)
    python tests/extension_test.py       (AfuDM acikken; uzanti Chromium'da, 19 test)
    python tests/cerez_test.py           (ag gerektirmez)
    python tests/kaydet_test.py          (ag gerektirmez; kaydetme penceresi)
    python tests/kuyruk_test.py          (ag gerektirmez; mukerrer/GID kimligi)
    python tests/baslangic_test.py       (ag gerektirmez; Baslangic kisayolu)
    python tests/iliskilendir_test.py    (ag gerektirmez; .torrent/magnet kaydi)
    python tests/seed_test.py            (ag gerektirmez; seed/tracker tazeleme)
    python tests/daemon_test.py          (AfuDM KAPALIYKEN)
    python tests/baslik_test.py          (AfuDM acikken; fare kullanmaz)
    python tests/video_panel_test.py     (AfuDM acikken; ffmpeg+ffprobe gerekir, 12 test)
    python tests/chrome_ekle_test.py     (Chrome gerekir; gecici profil, 7 kontrol)

## ONEMLI KURALLAR
- Portable: hicbir sey sisteme yazilmaz; `data/` ve `downloads/` klasor icinde.
- `AfuDM.exe` `engine/` ve `ui/` ile AYNI klasorde durmali (kok klasor) — tasima.
- Kaynak kodu degisince exe'yi YENIDEN PAKETLE (kod exe'nin icinde); `ui/`
  diskten okundugu icin arayuz degisikligi paketleme gerektirmez.
- pywebview'de `webview.__version__` YOK.
- aria2 rpc-secret + API token `data/` icinde uretilir.
