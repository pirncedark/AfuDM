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

**Clipboard watch.** Copy a downloadable link and the add dialog opens.

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

## Tests

```
python tests/smoke.py                  # everything (really downloads)
python tests/smoke.py --skip-torrent   # HTTP + video
python tests/smoke.py --skip-video     # HTTP + torrent

# these need no network and take seconds:
python tests/netcheck_test.py          # IPv6 detection
python tests/manager_test.py           # magnet / title rules
python tests/i18n_test.py              # language keys
python tests/format_test.py            # video format selection
python tests/engines_test.py           # engine downloads
python tests/mux_ayristirma_test.py    # MP4 sample parsing
python tests/mux_test.py               # muxing + ffprobe + full decode
```

`smoke.py` performs real downloads: multi-connection HTTP, pause/resume, magnet
seed tracking, video → mp3. Current state: **17/17**.

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
  kur.bat        one-time package install
  paketle.py     builds the shippable package
  app.py         window + tray + clipboard watch
  core/          aria2 engine, RPC, queue, SQLite, trackers, engine downloads
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

**Pano yakalama.** İndirilebilir bir link kopyaladığında ekleme penceresi açılır.

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
```

`smoke.py` gerçekten indirir: çok bağlantılı HTTP, duraklat/sürdür, magnet seed
takibi, video → mp3. Son durum: **17/17**.

## Güvenlik

Yerel API yalnızca `127.0.0.1`'e bağlanır ve her istekte token ister. Token
`data/api_token.txt` içinde üretilir; uzantıya ancak sen "Uzantıyı bağla"
dedikten sonraki 2 dakika içinde verilir. aria2'nin RPC anahtarı da her
kurulumda rastgele üretilir.

Geliştirme notları: `docs/DURUM.md`
