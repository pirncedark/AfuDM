# AfuDM — Durum & Devam Notu
Son guncelleme: 2026-09-16 13:45

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
3. Tarayici uzantisini Chrome'a yukleyip devralmayi canli dene.

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

## ONEMLI KURALLAR
- Portable: hicbir sey sisteme yazilmaz; `data/` ve `downloads/` klasor icinde.
- `AfuDM.exe` `engine/` ve `ui/` ile AYNI klasorde durmali (kok klasor) — tasima.
- Kaynak kodu degisince exe'yi YENIDEN PAKETLE (kod exe'nin icinde); `ui/`
  diskten okundugu icin arayuz degisikligi paketleme gerektirmez.
- pywebview'de `webview.__version__` YOK.
- aria2 rpc-secret + API token `data/` icinde uretilir.
