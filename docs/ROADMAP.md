# AfuDM Ürün Geliştirme Planı

> Kullanıcı kararı (2026-09-19): rakip listesi artık **ürün geliştirme araştırma
> planıdır**. Amaç rakiplerden özellik kopyalamak değil; hangi problemin hangi
> projede EN İYİ çözüldüğünü bulup AfuDM mimarisine uygun olanları seçmek.

## Kimlik — 5 temel sütun

AfuDM = **Normal dosya + Torrent + Video + Browser + Remote/Mobile tek uygulamada.**
Uzun vadede fark yaratacak 5 sütun:

1. Çok iyi tarayıcı entegrasyonu
2. HTTP + Torrent + Video'nun tek yerde olması
3. LinkGrabber ve otomasyon
4. PC ↔ Telefon entegrasyonu
5. Portable + açık kaynak + hafif yapı

**Karar ilkesi:** "Hepsinde ne varsa ekleyelim" YOK. Rakip referansı ancak
fayda/efor/risk/fark puanlamasından sonra seçilir.

## Aşama yöntemi

| Aşama | İş | Çıktı |
| --- | --- | --- |
| 0 | v1.3.2'yi bitir, test et, commit et (✅ DONE) | Temiz başlangıç |
| 1 | ~30 projeyi özellik bazlı tara | Karşılaştırma matrisi |
| 2 | AfuDM'de `✓ var / ◐ kısmen / ○ yok / → planlı` işaretle | Gap analysis |
| 3 | Fayda/efor/risk/fark ile sırala | Önceliklendirme |
| 4 | v1.4–2.x roadmap'e dağıt | Geliştirme planı |
| 5 | Her sürüm için test/acceptance kriteri | Kontrollü geliştirme |

## İncelenecek proje grupları

- **Genel DM:** IDM, FDM, Neat, XDM, AB Download Manager, File Centipede, Gopeed, Varia, Persepolis, DLMan
- **Torrent:** qBittorrent, Transmission, Motrix, Gopeed, File Centipede
- **Video/medya:** yt-dlp, Stacher, Seal, Tartube, Media Downloader, Gallery-dl, N_m3u8DL-RE
- **LinkGrabber/browser:** JDownloader, DownThemAll!, Video DownloadHelper, Aria2 Explorer, FDM uzantıları, uGet Integrator
- **Remote/mobile/headless:** AB Download Manager, AriaNg, pyLoad, Transmission, Gopeed
- **Plugin/extensibility:** JDownloader, Gopeed, Motrix, pyLoad, Media Downloader
- **Alt motor/protokol:** aria2, curl/libcurl, Wget2, aria2p

## Özellik matrisi (her proje için)

HTTP, FTP/SFTP, Torrent, Magnet, Metalink, HLS, DASH, m3u8/live, YouTube/video,
Gallery/image, Resume, Multi-connection, Dynamic connections, Speed profiles,
Per-download limit, Queue, Scheduler, Checksum, Proxy, SOCKS, PAC/System proxy,
Authentication, Custom headers, User-Agent, Renew URL, Browser interception,
LinkGrabber, Clipboard monitoring, Cookie import, Torrent file selection,
Seed/peer details, Tracker management, DHT/PEX, UPnP/NAT-PMP, Subtitle,
SponsorBlock, Metadata, Chapters, Thumbnail, Archive extraction, Antivirus scan,
Post-processing, Rules, Plugin system, CLI, API, Web UI, Mobile app, PWA,
Headless, Docker, Portable, Windows, Linux, macOS, Android.

## Referans matrisi — "kim neyi en iyi yapıyor?"

| Konu | Referans proje |
| --- | --- |
| Browser interception | IDM / XDM |
| Renew URL | Neat DM |
| Modern masaüstü UX | AB Download Manager |
| Mobile companion | AB DM / Seal |
| LinkGrabber | JDownloader |
| Sayfa link filtreleme | DownThemAll! |
| Torrent UI | qBittorrent |
| Torrent motor UX | Transmission / Motrix |
| aria2 frontend | AriaNg |
| yt-dlp UI | Stacher |
| Android video | Seal |
| HLS/DASH | N_m3u8DL-RE |
| Plugin mimarisi | Gopeed / JDownloader |
| Headless | pyLoad / Transmission |
| Rules | File Centipede / AB DM |
| Post-processing | JDownloader |
| Multi-engine | Media Downloader |
| Protocol support | curl / aria2 |
| Recursive download | Wget2 |

## Öncelik modeli

Her özellik 4 puan: **Kullanıcı değeri 1–5 · Geliştirme maliyeti 1–5 ·
Teknik risk 1–5 · Fark yaratma 1–5.**

Örnek: Proxy (5/2/2/3), Checksum (4/1/1/2), LinkGrabber (5/3/2/5),
Video Pro (5/2/2/5), Torrent file selection (5/3/3/4), Android app (5/5/4/5),
Plugin system (5/5/5/5), UPnP (2/3/4/2).

## Sürüm yol haritası

### v1.3.2 — Stabilizasyon ✅ (commit c7514be, 2026-09-19)
CLI, renew, mode, scheduler, stale endpoint, JSON contract, concurrency lock,
testler. Yeni büyük özellik yok.

### v1.4 — Foundation + Network Core
Önce modeller: `DownloadRequest`, `NetworkOpts`, `IntegrityOpts`, `VideoOpts`,
`TorrentOpts`. Sonra: Proxy HTTP/SOCKS, System proxy, PAC, Basic Auth, Custom
headers, User-Agent, Checksum, Live connection/speed adjustment, Strong Renew,
API error contract (✅), DB migration (PRAGMA user_version), `/capabilities`,
fake HTTP test suite.
Referans: Neat + AB DM + IDM/XDM.

### v1.5 — LinkGrabber
Referans: JDownloader + DownThemAll! + Video DownloadHelper.
Browser DOM extraction, clipboard URLs, HTML link extraction (`a[href]`,
video/audio/source, magnet), filtre, dedupe, lazy probe, boyut tespiti,
çoklu seçim, batch add. Uzantı: "Sayfadaki tüm linkleri gönder / seçili
linkleri gönder / video linklerini gönder".

### v1.6 — Video Pro
Referans: yt-dlp + Stacher + Seal + N_m3u8DL-RE.
Subtitle, auto subtitle, embed subtitle, thumbnail, metadata, chapters,
SponsorBlock, download section, codec, container, filename template,
cookies-from-browser, playlist controls, audio options, Live/HLS/DASH.
Avantaj: **motor zaten var.**

### v1.7 — Torrent Pro
Referans: qBittorrent + Transmission + Motrix + Gopeed.
Torrent file tree, selective files, file priority, seed ratio/time, upload
limit, peer list, seed/peer count, DHT/PEX status, tracker health, tracker
pool, tracker dedupe, tracker latency. UI örneği: `Seeds: 12 / Peers: 47 /
Connected: 19 / DHT: ON / PEX: ON / Trackers: 28/34 healthy`.
**Ayrıca: "Daha Fazla Seed/Peer Bul" — Torrent Boost Bölümü aşağıda.**

### v1.8 — Automation / Post Processing
Referans: JDownloader + XDM.
`PostProcessQueue` (Manager thread'i bloke ETMEZ, idempotent): ZIP/7z/RAR
çıkar, checksum doğrula, Windows Defender taraması, taşı/yeniden adlandır,
script çalıştır, Telegram bildirimi, uyut/kapat.

### v1.9 — Smart Rules
Referans: File Centipede + AB DM. Kurallı yönlendirme:
`youtube.com → Video → subtitles tr,en` / `*.iso → ISO → SHA256` / `>10 GB →
gece kuyruğu` / `github.com → D:\Github` / `torrent → seed-ratio 1.0`.

### v2.0 — Plugin Platform
Referans: Gopeed + JDownloader + Motrix + pyLoad.
Türler: resolver, downloader, post processor, notification, metadata,
automation, site integration, theme. Manifest: name, version, minimum AfuDM,
permissions, domains, SHA256, entrypoint. İlk sürüm **trusted plugins**;
gerçek sandbox sonra.

### v2.1 — Mobile / Remote (yüksek öncelik)
- **AfuDM PWA:** QR pairing, downloads, pause/resume, add URL, torrent/magnet,
  video, snail/normal/turbo, notifications.
- **Android Companion:** "Paylaş → AfuDM → Ev PC → indirmeyi başlat",
  video → kalite seç, magnet → PC'ye gönder, torrent → dosya seç.
  **Farklılaştırıcı sütunlardan biri.** (bkz. DURUM "YOL HARITASI — EK KARARLAR")
- Güvenlik: API portu internete ASLA açılmaz; QR + kısa ömürlü cihaz token.

### v2.2 — Headless / Server
Referans: pyLoad + Transmission + AriaNg. `afuadm --headless`, REST API,
Web UI, LAN/NAS, Windows service; Docker değerlendirmesi.

### v2.3+ — Network / Protocol Expansion
UPnP, NAT-PMP, FTP/SFTP geliştirme, WebDAV, Metalink UI, recursive website
download, gallery-dl entegrasyonu. Referans: curl + Wget2 + Gallery-dl +
File Centipede.

---

## Torrent Boost — "Daha Fazla Seed/Peer Bul" (v1.7 MI, özel tasarım)

Kullanıcı dostu anlam: sıradan kullanıcı tracker'ı bilmez, düğmeye basar:
**"İndirme yavaş → Daha fazla seed bul."** Normal HTTP dosyasında seed yok;
orada çözüm mirror/link yenilemedir (renew).

UI:
```
Seeds: 2   Peers: 11      [ Daha Fazla Seed Bul ]
Durum:
✓ Tracker'lar yeniden duyuruldu
✓ 18 sağlıklı tracker denendi
✓ DHT yenilendi
✓ PEX açık
+ 7 yeni peer / + 2 yeni seed bulundu   Yeni hız: 2.4 MB/s
```
Sonuç ekranı: Önce (2 seed / 9 peer / 0.38 MB/s) → Sonra (6 / 31 / 2.7 MB/s).

**Otomatik tetikleme ("Torrent Boost" ayarı):** torrent 90+ sn boyunca < 500 KB/s
ise önce neden ara: hız limiti mi? disk darboğazı mı? seed/peer az mı? (sırasıyla).
Evetse çalıştır. Cooldown: **10 dk**, tekrar eden sorgulama kötü davranış.

**Çalışma sırası:** (1) mevcut tracker'lara reannounce, (2) havuzdan yalnızca
sağlıklı + tekrarsız seç (default max 30 ek tracker), (3) public torrent ise
en iyi 20–30 tracker'ı EKLE, (4) DHT peer discovery yenile, (5) PEX üzerinden
bağlı peer'ların bildiği peer'ları topla, (6) LAN'daki peer (local discovery)
varsa ara, (7) önce/sonra sayısını karşılaştır, (8) işe yaramayan tracker'ı
torrentten kaldır.

**Tracker hattı:** `Havuz (326) → normalize/dedupe → Geçerli (143) → health →
Sağlıklı (57) → latency/ranking → kullanılan (25)`.

### 🔒 Private torrent koruması (ZORUNLU)
`.torrent` içinde `private = 1` varsa AfuDM: **public tracker EKLEMEZ, DHT/PEX
zorlamaz, dışarıdan seed ARAMAZ.** UI: `🔒 Özel torrent — harici tracker/seed
araması devre dışı.` Gerekçe: torrent kurallarını ve kullanıcının
infohash/passkey bilgilerini dışarı yaymamak.

### Kod tasarımı
```
core/
    trackerlar.py      (mevcut: normalize)
    torrent_bilgi.py   (private tespiti, dosya ağacı → v1.7)
    torrent_boost.py   (yeni)
```
```python
class TorrentBoost:
    def boost(self, gid):
        if durum.private:
            return BoostResult(skipped=True, reason="PRIVATE_TORRENT")
        onceki = durum.peer_count
        self.reannounce(gid); self.refresh_dht(gid)
        self.add_trackers(gid, self.tracker_pool.best(limit=25))
        return BoostResult(peers_before=onceki, peers_after=durum.peer_count)
```

### Sınır (önemli)
Torrent ağında gerçekten seed yoksa AfuDM **seed üretemez**; özellik mevcut
seed/peer'ları daha iyi keşfeder. UI yanlış vaat vermemeli.