# AfuDM

A portable download manager for Windows — files, video and torrents in one
folder. Nothing is written to the system, the registry or AppData: copy the
folder to a USB stick and it runs.

Engines are bundled: **aria2** (HTTP/FTP + BitTorrent), **yt-dlp** (1800+ video
sites), **ffmpeg** (optional — only needed for mp3).

*Türkçe açıklama aşağıda ↓*

---

## Start

```
AfuDM.exe          no Python needed — the desktop shortcut points here
AfuDM.bat          run from source (development)
```

`AfuDM.exe` carries its own Python, but it must sit **next to** `engine/` and
`ui/` — that is why it lives in the main folder. Don't move it on its own.

To run from source, run `kur.bat` once; it installs three Python packages
(`pywebview`, `pystray`, `pillow`). The engines are already in `engine/`.

Two packages are produced by `python paketle.py`:

| Package | Size | Contents |
|---|---|---|
| core (default) | **22 MB** | aria2 only — video engines are downloaded on demand |
| `--tam` (full) | 137 MB | everything bundled |

In the core package, Settings → Engines downloads yt-dlp and ffmpeg when you
want them. Downloads land inside the app folder, so it stays portable.

## What it does

**Fast downloads.** Splits a file into 64 pieces and opens 16 connections per
server. Measured: 16 concurrent connections, 4.9 MB/s peak.

**Pause and resume.** A paused download — even one interrupted by closing the
app — continues where it stopped. The aria2 session is written to disk every
15 seconds.

**Video.** YouTube, Instagram, TikTok and everything else yt-dlp supports.
Quality picker (up to 4K), audio only (mp3), whole playlists.

**Merging without ffmpeg.** YouTube sends audio and video as separate tracks. If
ffmpeg is not installed, AfuDM joins them with its own muxer
(`video/mp4mux.py`) — a remux, so nothing is re-encoded and quality is
untouched. Verified against ffmpeg's own output: all 46,368 frames identical,
timestamps included. This is what keeps the core package at 22 MB.

**Torrents.** Magnet links and `.torrent` files. Live seed/peer counts, uploaded
bytes, ratio. DHT, PEX and LPD are on, and the tracker list refreshes daily so
even tired torrents find peers.

**Queue and scheduling.** How many downloads at once, speed limit, "start at
23:30", notify Telegram when finished or shut the computer down.

**Download dialog.** Every link — from the extension, the clipboard or a
double-clicked `.torrent` — stops here first: file name, category, a folder tree
(shortcuts, drives, "new folder") and start now / start at a time. Nothing
reaches the engine before you confirm. Turn it off in Settings if you want links
to start instantly.

**Category folders.** With no target picked, files land in `downloads/Video`,
`downloads/Müzik`, `downloads/Belgeler`… by type. Optional.

**Seed refresh for torrents.** A **Seeds** button on every torrent row opens a
live window: seeds, connections, the torrent's tracker count, the applied list,
its age and DHT state. *Refresh now* pulls today's tracker list and re-announces
the torrent. You can paste **your own trackers** there too — they go to the front
of the list. Measured on a real 19 GB torrent: connections 6 → 11, progress kept
(aria2 cannot add trackers to a running torrent, so AfuDM removes and re-adds it
in place; the `.aria2` control file keeps every downloaded piece).

**One copy only.** Opening AfuDM again — or double-clicking a second `.torrent` —
does not start a second window; the running one comes to the front and takes the
link.

**Tray.** Minimizing hides the window from the taskbar; the tray icon brings it
back. It can also start with Windows straight into the tray (Settings), so
downloads resume without a window popping up. Windows 11 hides new tray icons
under the `^` arrow — drag it onto the taskbar once to keep it visible.

**Opens .torrent and magnet links.** Settings registers AfuDM for `.torrent`
files and `magnet:` links (your previous program's registration is backed up and
restored if you turn it off). Windows will not let a program set itself as the
default for a file type, so Settings has a button that opens the Windows screen
where you pick it.

**Clipboard watch.** Copy a downloadable link and the download dialog opens.

**Two languages.** Settings → Dil / Language: Automatic (follows Windows),
Türkçe or English. The change applies without a restart — window title and tray
menu follow too. The browser extension uses the browser's own language.

## Browser extension

**One click:** in AfuDM press **Add to Chrome** (left menu) → **Add automatically**.
AfuDM opens the extensions page, turns on Developer mode, loads the `extension`
folder and the extension connects to AfuDM by itself. Keep your hands off the
keyboard for a few seconds. If a step gets stuck, the same window shows the
manual steps with copy buttons.

By hand: `chrome://extensions` → Developer mode → **Load unpacked** (not "Pack
extension") → pick the `extension` folder. Keep AfuDM's *Add to Chrome* window
open and the extension pairs automatically.

What it does:
- takes over browser downloads (and sends session cookies, so sites that need a
  login work too — cookies are never stored in AfuDM's database)
- **video panel:** a "Download with AfuDM" button appears on playing videos, also
  inside embedded players; pick 1080p / 720p / audio only. Qualities come from the
  page's HLS/DASH playlist, or from yt-dlp on sites like YouTube
- "Download with AfuDM" in the right-click menu

When AfuDM is closed the extension stays out of the way and the browser
downloads normally. DRM-protected streams (Netflix etc.) cannot be downloaded.

## Command line

`afuadm.bat` (a thin wrapper to `afuadm.py`, needs Python) talks to the running
AfuDM through its local HTTP API — it reads the port+token from
`data/api_endpoint.json`, so nothing is ever sent unauthenticated. If AfuDM is
closed it starts it in the background (`--tepside`) and waits; `--no-start`
disables that.

```
afuadm list                                   show queue
afuadm status --json                          engine / total speed (raw JSON)
afuadm add https://site.com/file.zip
afuadm add "https://youtube.com/watch?v=..." --quality 1080p --audio-only
afuadm add URL --start-at "23:30"             schedule
afuadm mode snail|normal|turbo                live speed profile (100 KB/s / your limit / unlimited)
afuadm renew <gid> "https://new-valid-link"   swap expired URL, keep downloaded bytes
afuadm watch --json                           live NDJSON stream (poll every 0.5s)
afuadm info                                   version + service state
afuadm ayarla <gid> --baglanti 8 --hiz 500    live per-download connections/speed cap (v1.4)
afuadm ayar proxy socks5://127.0.0.1:1080     set global proxy (also: system_proxy 1)
afuadm add URL --proxy http://... --checksum sha-256:<hex>  per-download proxy + verify
```

Every subcommand accepts `--json`; `--json` and `--no-start` work on either
side of the command (`afuadm status --json` == `afuadm --json status`). In
`--json` mode stdout carries **only** the raw JSON / NDJSON; every human
message and error goes to stderr, and the API token never appears in any
output. Exit codes: `0` ok, `2` AfuDM missing/unreachable, `3` record not
found (KAYIT_YOK), `4` API error, `130` interrupted. If two `afuadm` calls
race to start AfuDM, a lock file (`data/afuadm_baslat.lock`) lets only one of
them spawn it; the other connects through `/ping` without starting anything.

`mode` (Snail/inspiration from FDM) calls `aria2.changeGlobalOption` so running
downloads are not interrupted. `renew` (inspiration from Neat DM) uses
`aria2.changeUri` — the old URI leaves the list, the new one joins it, and the
`.aria2` control file keeps every downloaded byte, so an expired Google-Drive or
signed link picks up exactly where it dropped. `renew` is HTTP(S)/FTP only and
accepts optional `--headers`, `--cookies`, `--user-agent`; torrent/video jobs
are rejected. Trackers from the seed lists are normalized (glued-URL split,
dedupe, scheme whitelist, local/blocked-host filtering) when a torrent refresh
runs — a larger list is not a faster download, a clean one is.

## Tests

```
python tests/smoke.py                  # everything (really downloads)
python tests/smoke.py --skip-torrent   # HTTP + video
python tests/smoke.py --skip-video     # HTTP + torrent

# these need no network and take seconds:
python tests/netcheck_test.py          # IPv6 detection
python tests/manager_test.py           # magnet / title rules
python tests/i18n_test.py              # language keys
python tests/seed_dosya_test.py        # seed lists in Settings
python tests/format_test.py            # video format selection
python tests/engines_test.py           # engine downloads
python tests/mux_ayristirma_test.py    # MP4 sample parsing
python tests/mux_test.py               # muxing + ffprobe + full decode
python tests/kaydet_test.py            # download dialog (categories, folder tree)
python tests/kuyruk_test.py            # duplicate detection, magnet GID re-attach
python tests/seed_test.py              # seed refresh + your own trackers
python tests/cerez_test.py             # session cookies
python tests/baslangic_test.py         # startup shortcut
python tests/iliskilendir_test.py      # .torrent / magnet registration
python tests/cli_test.py               # speed profiles, link renewal, scheduling
python tests/cli_surum_test.py         # stale endpoint, double auto-start lock, JSON purity, exit codes, token leak
python tests/trackerlar_test.py        # tracker list normalization
python tests/db_test.py                # DB migration (PRAGMA user_version, data preserved)
python tests/fake_http_test.py         # fake HTTP: range/206 resume, auth 401, 403, redirect, drop, checksum
python tests/network_core_test.py      # proxy parsing, checksum, live per-download options
```

`smoke.py` performs real downloads: multi-connection HTTP, pause/resume, magnet
seed tracking, video → mp3. Current state: **17/17**. The offline suites above
touch neither the real Startup folder nor the real registry — they redirect
themselves to a temporary location.

## Security

The local API binds to `127.0.0.1` only and requires a token on every request.
The token is generated into `data/api_token.txt` and is handed to the extension
only within 2 minutes of you pressing "Pair the extension". aria2's RPC secret
is generated randomly on every install.

## Layout

```
AfuDM/
  AfuDM.exe      single-file build (no Python needed)
  AfuDM.bat      launcher for running from source
  afuadm.py      command-line tool (afuadm.bat wrapper; needs Python)
  kur.bat        one-time package install
  paketle.py     builds the shippable package
  app.py         window + tray + clipboard watch
  core/          aria2 engine, RPC, queue, SQLite, trackers, engine downloads
                 kaydet.py (download dialog), baslangic.py (start with Windows),
                 iliskilendir.py (.torrent / magnet), pencere.py (window + tray)
  video/         yt-dlp layer + MP4 muxer
  api/           local HTTP API (127.0.0.1 + token)
  ui/            interface (HTML/CSS/JS)
  extension/     Chrome/Edge extension
  engine/        aria2c.exe, yt-dlp.exe, ffmpeg.exe
  data/          database, session, keys, log
  downloads/     default download folder
  tests/         smoke.py (real downloads) + offline suites
  docs/DURUM.md  development notes (Turkish)
```

---

# AfuDM (Türkçe)

IDM'in yerine geçen portable indirme yöneticisi. Dosya, video ve torrent indirir;
tek klasörde yaşar, sisteme hiçbir şey yazmaz.

Motorlar gömülü: **aria2** (HTTP/FTP + BitTorrent), **yt-dlp** (1800+ video
sitesi), **ffmpeg** (isteğe bağlı — yalnız mp3 için gerekli).

## Başlatma

```
AfuDM.exe          Python gerekmez — masaüstü kısayolu da buna bakar
AfuDM.bat          kaynaktan çalıştırır (geliştirme)
```

`AfuDM.exe` kendi Python'unu içinde taşır; `engine/` ve `ui/` klasörleriyle
**aynı yerde** durmalıdır — bu yüzden ana klasördedir, tek başına taşıma.

Kaynaktan çalıştıracaksan bir kez `kur.bat` — sadece üç Python paketini kurar
(`pywebview`, `pystray`, `pillow`). Motorlar `engine/` klasöründe zaten var.

`python paketle.py` iki paket üretir:

| Paket | Boyut | İçerik |
|---|---|---|
| çekirdek (varsayılan) | **22 MB** | yalnız aria2 — video motorları istenince iner |
| `--tam` | 137 MB | her şey içinde |

Çekirdek pakette Ayarlar → Motorlar'dan yt-dlp ve ffmpeg indirilir. İndirilenler
uygulama klasörüne gider, portable yapı bozulmaz.

## Ne yapar

**Hızlı indirme.** Bir dosyayı 64 parçaya böler, sunucu başına 16 bağlantı açar.
Ölçülen: 16 eşzamanlı bağlantı, 4.9 MB/s tepe hız.

**Duraklat ve devam.** Duraklattığın, hatta uygulamayı kapattığın indirme kaldığı
yerden sürer — aria2 oturumu her 15 saniyede diske yazılır.

**Video.** YouTube, Instagram, TikTok ve yt-dlp'nin desteklediği her yer.
Kalite seçimi (4K'ya kadar), sadece ses (mp3), playlist'in tamamı.

**ffmpeg'siz birleştirme.** YouTube sesi ve görüntüyü ayrı gönderir. ffmpeg
kurulu değilse AfuDM iki izi kendi birleştiricisiyle (`video/mp4mux.py`) tek mp4
yapar — remux olduğu için yeniden kodlama yok, kalite değişmez. ffmpeg'in kendi
çıktısıyla karşılaştırıldı: 46.368 karenin hepsi aynı, zaman damgaları dahil.
Çekirdek paketin 22 MB kalmasının sebebi budur.

**Torrent.** Magnet ve `.torrent`. Canlı seed/peer sayısı, gönderilen bayt, oran.
DHT, PEX ve LPD açık; tracker listesi her gün yenilenir, böylece yorgun
torrentlerde de peer bulur.

**Kuyruk ve zamanlama.** Aynı anda kaç indirme, hız sınırı, "23:30'da başlat",
hepsi bitince Telegram'a haber ver veya bilgisayarı kapat.

**Kaydetme penceresi.** Link nereden gelirse gelsin — uzantı, pano ya da çift
tıklanan bir `.torrent` — önce burada durur: dosya adı, kategori, klasör ağacı
(kısayollar, diskler, "yeni klasör") ve şimdi başlat / saatinde başlat. Sen
onaylamadan motora hiçbir şey gitmez. İstersen Ayarlar'dan kapatıp linkleri
doğrudan başlatabilirsin.

**Kategori klasörleri.** Hedef seçmezsen dosyalar türüne göre `downloads/Video`,
`downloads/Müzik`, `downloads/Belgeler`… altına iner. İsteğe bağlı.

**Torrentte seed güncelleme.** Her torrent satırında **Seed** düğmesi canlı bir
pencere açar: seed, bağlantı, torrentin tracker sayısı, uygulanan liste, listenin
yaşı ve DHT durumu. *Şimdi güncelle* günün tracker listesini çekip torrenti
yeniden duyurur. **Kendi tracker'larını** da oraya yapıştırabilirsin — listenin
başına eklenir. Gerçek bir 19 GB torrentte ölçüldü: bağlantı 6 → 11, ilerleme
korundu (aria2 çalışan torrente tracker ekleyemediği için AfuDM işi yerinde
kaldırıp yeniden ekler; `.aria2` kontrol dosyası inen her parçayı korur).

**Tek kopya.** AfuDM'i tekrar açmak — ya da ikinci bir `.torrent`e çift tıklamak —
yeni pencere açmaz; çalışan pencere öne gelir ve linki alır.

**Tepsi.** Küçültünce pencere görev çubuğundan kalkar, tepsi simgesinden geri
gelir. Bilgisayar açılınca doğrudan tepside de başlayabilir (Ayarlar), böylece
indirmeler pencere açılmadan sürer. Windows 11 yeni simgeleri `^` okunun altında
saklar — bir kez görev çubuğuna sürüklersen sabit kalır.

**.torrent ve magnet açar.** Ayarlar'dan AfuDM `.torrent` dosyaları ve `magnet:`
linkleri için kaydedilir (önceki programın kaydı yedeklenir, kapatınca geri
gelir). Windows bir programın kendini varsayılan yapmasına izin vermediği için
Ayarlar'da o ekranı açan bir düğme var.

**Pano yakalama.** İndirilebilir bir link kopyaladığında kaydetme penceresi açılır.

**İki dil.** Ayarlar → Dil / Language: Otomatik (Windows dilinden seçer), Türkçe
veya English. Değişiklik yeniden başlatmadan uygulanır; pencere başlığı ve tepsi
menüsü de döner. Tarayıcı uzantısı tarayıcının dilini kullanır.

## Tarayıcı uzantısı

**Tek tık:** AfuDM'de sol menüden **Chrome'a ekle** → **Otomatik ekle**. AfuDM
uzantılar sayfasını açar, Geliştirici modunu açar, `extension` klasörünü yükler ve
uzantı AfuDM'e kendiliğinden bağlanır. Birkaç saniye klavyeye/fareye dokunma.
Bir adımda takılırsa aynı pencerede kopyala düğmeli elle kurulum anlatımı açılır.

Elle: `chrome://extensions` → Geliştirici modu → **Paketlenmemiş öğe yükle**
("Uzantı paketle" değil) → `extension` klasörünü seç. AfuDM'deki *Chrome'a ekle*
penceresi açıkken uzantı kendiliğinden bağlanır.

Ne yapar:
- tarayıcı indirmelerini devralır (oturum çerezlerini de gönderir, giriş isteyen
  sitelerde de çalışır — çerezler AfuDM'in veritabanına yazılmaz)
- **video paneli:** oynayan videonun üstünde "AfuDM ile indir" düğmesi çıkar, gömülü
  oynatıcılarda da; 1080p / 720p / sadece ses seç. Kaliteler sayfanın HLS/DASH
  listesinden, YouTube gibi sitelerde yt-dlp'den gelir
- sağ tık menüsünde "AfuDM ile indir"

AfuDM kapalıysa uzantı hiçbir şeye karışmaz. DRM korumalı yayınlar (Netflix vb.)
indirilemez.

## Komut satırı

`afuadm.bat` (Python ister) çalışan AfuDM'e yerel HTTP API üzerinden iş verir —
port+token'i `data/api_endpoint.json`'dan okur, bu yüzden hiçbir istek
kimliksiz gitmez. AfuDM kapalıysa arka planda (`--tepside`) başlatıp bağlanmayı
bekler; `--no-start` bunu kapatır.

```
afuadm list                                   kuyruğu göster
afuadm status --json                          motor / toplam hız (ham JSON)
afuadm add https://site.com/dosya.zip
afuadm add "https://youtube.com/watch?v=..." --quality 1080p --audio-only
afuadm add URL --start-at "23:30"             zamanla
afuadm mode snail|normal|turbo                canlı hız profili (100 KB/s / limitin / sınırsız)
afuadm renew <gid> "https://yeni-gecerli-link"  ölen linki değiştir, inen baytları koru
afuadm watch --json                           canlı NDJSON akışı (0.5 sn'de bir)
afuadm info                                   sürüm + servis durumu
afuadm ayarla <gid> --baglanti 8 --hiz 500    canlı is-özel bağlantı/hız ayarı (v1.4)
afuadm ayar proxy socks5://127.0.0.1:1080     genel proxy ata (ayrıca: system_proxy 1)
afuadm add URL --proxy http://... --checksum sha-256:<hex>  is-özel proxy + doğrulama
```

Her alt komut `--json` kabul eder; `--json` ve `--no-start` komutun iki
yanında da geçerli (`afuadm status --json` = `afuadm --json status`). `--json`
modunda stdout **yalnızca** ham JSON/NDJSON taşır; tüm kullanıcı mesajı ve
hata stderr'e gider, API token'ı hiçbir çıktıda görünmez. Exit kodları: `0` tamam,
`2` AfuDM yok/erişilemez, `3` kayıt bulunamadı (KAYIT_YOK), `4` API hatası,
`130` kullanıcı durdurdu. İki `afuadm` çağrısı aynı anda AfuDM'i başlatmaya
kalkarsa `data/afuadm_baslat.lock` kilit dosyası yalnız birinin spawn etmesine
izin verir; diğeri `/ping` üzerinden başlatmadan bağlanır.

`mode` (FDM'in Snail Mode'u) `aria2.changeGlobalOption` çağırır; çalışan
indirmeler kesilmez. `renew` (Neat DM'in Renew expired link'i) `aria2.changeUri`
kullanır — eski URI listeden çıkar, yenisi girer; `.aria2` kontrol dosyası inen
her baytı korur, böylece süresi dolan Google Drive / imzalı link tam kaldığı
yerden sürer. `renew` yalnız HTTP(S)/FTP içindir ve `--headers`, `--cookies`,
`--user-agent` alır; torrent/video işleri reddedilir. Seed listelerinden gelen
tracker'lar torrent yenilenmesinde normalleştirilir (yapışık URL bölme, dedupe,
şema beyaz listesi, yerel/engelli sunucu süzme) — daha uzun liste daha hızlı
torrent demek değildir, temiz liste daha hızlıdır.

## Test

```
python tests/smoke.py                  # hepsi (gerçekten indirir)
python tests/smoke.py --skip-torrent   # HTTP + video
python tests/smoke.py --skip-video     # HTTP + torrent

# bunlar ağ gerektirmez, saniyeler sürer:
python tests/netcheck_test.py          # IPv6 tespiti
python tests/manager_test.py           # magnet / başlık kuralları
python tests/i18n_test.py              # dil anahtarları
python tests/format_test.py            # video format seçimi
python tests/engines_test.py           # motor indirme
python tests/mux_ayristirma_test.py    # MP4 örnek okuma
python tests/mux_test.py               # birleştirme + ffprobe + tam kod çözme
python tests/kaydet_test.py            # kaydetme penceresi (kategori, klasör ağacı)
python tests/kuyruk_test.py            # mükerrer iş, magnet GID yeniden bağlama
python tests/seed_test.py              # seed tazeleme + kendi tracker'ların
python tests/cerez_test.py             # oturum çerezleri
python tests/baslangic_test.py         # başlangıç kısayolu
python tests/iliskilendir_test.py      # .torrent / magnet kaydı
python tests/cli_test.py               # hız profilleri, link yenileme, zamanlama
python tests/cli_surum_test.py         # stale endpoint, çift auto-start kilidi, JSON saflığı, exit kodları, token sızması
python tests/trackerlar_test.py        # tracker listesi normalizasyonu
python tests/db_test.py                # DB migration (PRAGMA user_version, veri korunur)
python tests/fake_http_test.py         # sahte HTTP: range/206 resume, auth 401, 403, redirect, drop, checksum
python tests/network_core_test.py      # proxy ayristirma, checksum, canli ayar secenekleri
```

`smoke.py` gerçekten indirir: çok bağlantılı HTTP, duraklat/sürdür, magnet seed
takibi, video → mp3. Son durum: **17/17**. Yukarıdaki çevrimdışı testler ne
gerçek Başlangıç klasörüne ne de gerçek kayıt defterine dokunur — kendilerini
geçici bir yere yönlendirirler.

## Güvenlik

Yerel API yalnızca `127.0.0.1`'e bağlanır ve her istekte token ister. Token
`data/api_token.txt` içinde üretilir; uzantıya ancak sen "Uzantıyı bağla"
dedikten sonraki 2 dakika içinde verilir. aria2'nin RPC anahtarı da her
kurulumda rastgele üretilir.

Geliştirme notları: `docs/DURUM.md`
