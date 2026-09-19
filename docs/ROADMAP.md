# AfuDM Ürün Yol Haritası

> Kullanıcı kararı (2026-09-19): rakip listesi artık **ürün geliştirme araştırma
> planıdır**. Amaç rakiplerden özellik kopyalamak değil; hangi problemin hangi
> projede EN İYİ çözüldüğünü bulup AfuDM mimarisine uygun olanları seçmek.
>
> Aynı tarihli ikinci karar: AfuDM **Windows merkezli** üründür. Linux/macOS
> masaüstü hedefleri roadmap'ten tamamen çıkarıldı; cross-platform masaüstü
> hedefi YOKTUR. Uzaktan kullanım Browser + PWA/Android Remote + Headless API
> üzerinden geliştirilir.

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

## Yön — Windows merkezli

```
                    Windows ana uygulama
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
            CLI       Browser        Mobile/PWA
          (afuadm)   Extension        Remote
                            │
                            ▼
                      Headless API
                    (afuadm server)
```

- **Ana platform: Windows** (portable, tek klasör, kopyala-çalıştır).
- **Uzaktan kullanım:** Browser Extension zaten var; mobil tarafta PWA →
  Android Companion; sunucu tarafında Headless API.
- Linux/macOS masaüstü uygulaması yapılmayacak; Docker ana hedef değildir (P3).

## Aşama yöntemi

| Aşama | İş | Çıktı |
| --- | --- | --- |
| 0 | v1.3.2'yi bitir, test et, commit et (✅ DONE) | Temiz başlangıç |
| 1 | ~30 projeyi özellik bazlı tara | Karşılaştırma matrisi |
| 2 | AfuDM'de `✓ var / ◐ kısmen / ○ yok / → planlı` işaretle | Gap analysis |
| 3 | Fayda/efor/risk/fark ile sırala | Önceliklendirme |
| 4 | v1.4–v2.3 roadmap'e dağıt | Geliştirme planı |
| 5 | Her sürüm için test/acceptance kriteri | Kontrollü geliştirme |

## Araştırma — iki dalga

Dalga 1 (P0/P1 — hemen etki): LinkGrabber, Video, Torrent, Mobile/PWA.
Dalga 2 (P2 — sonra): Rules, Plugin, Headless, Windows Integration.

İncelenecek proje grupları:

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
Headless, Docker, Portable, Windows, Android.

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

P0 = hemen, P1 = yakın, P2 = sonra. (Proxy 5/2/2/3, Checksum 4/1/1/2,
LinkGrabber 5/3/2/5, Video Pro 5/2/2/5, Torrent file selection 5/3/3/4,
Android app 5/5/4/5, Plugin system 5/5/5/5, UPnP 2/3/4/2.)

## Sürüm yol haritası

| Sürüm  | Ana hedef                    | Öncelik |
| ---    | ---                          | ---     |
| v1.4.0 | Foundation + Network Core ✅ | —       |
| v1.5.0 | LinkGrabber — YAYINLANDI (tag v1.5.0, 2026-09-19) | **P0** |
| v1.6.0 | Video Pro — YAYINLANDI (tag v1.6.0, 2026-09-19 10:17 UTC) | P1 |
| v1.7   | Torrent Pro — dilim 1-2 tamam | P1      |
| v1.7.5 | Mobile Remote / PWA          | P1      |
| v1.8   | Automation & Post-processing | P1      |
| v1.9   | Rules Engine                 | P2      |
| v2.0   | Plugin API + Marketplace     | P2      |
| v2.1   | Headless / NAS / Remote      | P2      |
| v2.2   | Windows Integration          | P1/P2   |
| v2.3   | Security / Reliability / UX  | P2      |

### v1.4.0 — Foundation + Network Core ✅ TAMAMLANDI (commit 7dd7bdd, 2026-09-19)
Tek ekleme noktası (`DownloadRequest.from_mapping`), DB migration (PRAGMA
user_version), `/capabilities`, proxy HTTP/SOCKS (+ sistem proxy), checksum,
canlı bağlantı/hız ayarı, strong renew, API error contract, fake HTTP test
harness. **PAC bilinçli olarak kapsam dışı** (bkz. DURUM — JS çalıştırıp ağ
davranışını değiştirmek yerine net adres).

### v1.5.0 — LinkGrabber — YAYINLANDI (tag v1.5.0, 2026-09-19)
Referans: JDownloader + DownThemAll! + Video DownloadHelper.

Akış:

```text
Clipboard / Browser / Manuel URL
        ↓
URL çıkarma (Extract)
        ↓
normalize
        ↓
duplicate temizleme (Dedupe)
        ↓
tür/domain filtreleme (Filter)
        ↓
lazy probe
        ↓
LinkGrabber Panel
        ↓
toplu indirme (Batch Add)
```

Ekler:
- Dosya türü filtresi
- Boyut filtresi
- Domain filtresi
- "Sadece video"
- "Sadece arşiv"
- "Sadece torrent/magnet"
- Seçilenleri topluca indirme
- Aynı URL'nin tekrar eklenmesini engelleme
- Probe concurrency limiti

Not: masaüstü LinkGrabber paneli ana iştir; uzantı tarafında "seçili/sayfa
linklerini indir" zaten var (v1.3.2), masaüstü karşılığı eksiktir.

### v1.6.0 — Video Pro — YAYINLANDI (tag v1.6.0, 2026-09-19 10:17 UTC)
Referans: yt-dlp + Stacher + Seal + N_m3u8DL-RE.
Subtitle, auto subtitle, subtitle embed, thumbnail, metadata, chapters,
SponsorBlock, video section download, codec seçimi, container seçimi, audio
format seçimi, filename template, cookies-from-browser UI, playlist gelişmiş
seçenekleri. Avantaj: **motor zaten var** (yt-dlp + ffmpeg).

### v1.7 — Torrent Pro (P1, `v1.7-torrent` ayrı worktree)
Referans: qBittorrent + Transmission + Motrix + Gopeed.

Beş dilimli teslim planı:

- [x] Dilim 1 (`77d6499`): `aria2.getFiles`, `torrent_dosyalari()` ve DB
  migration ile seçim kalıcılığı.
- [x] Dilim 2 (`d4f93c8`): canlı `select-file` için `torrent_secimi_ayarla()`;
  seçim magnet çocuk GID'ine ve `seed_tazele` sonrasına taşınır.
- [ ] Dilim 3: dosya ağacı UI.
- [ ] Dilim 4: metrikler.
- [ ] Dilim 5: `.torrent` ön-ekleme.

```text
Torrent
├─ Dosya ağacı
├─ Seçili dosyaları indir
├─ Priority
├─ Seed / Peer / Connected
├─ Upload speed
├─ Ratio
├─ Seed time
└─ Tracker health
```

Tracker sistemi:

```text
ham tracker listesi
        ↓
normalize (var)
        ↓
dedupe
        ↓
health scan (var — tracker_saglik.py)
        ↓
en iyi trackerlar
```

UPnP/NAT-PMP burada şart değil; sonraya bırakılabilir.
**Ayrıca: "Daha Fazla Seed/Peer Bul" — Torrent Boost Bölümü aşağıda.**

### v1.7.5 — Mobile Remote / PWA (P1)
Referans: AB Download Manager / Seal.

```text
Telefon
   ↓
QR ile eşleştir
   ↓
Windows PC
   ↓
AfuDM
```

Telefon üzerinden: link gönder, magnet gönder, video URL gönder, pause/resume,
Snail/Normal/Turbo, indirme durumunu gör, seed/peer gör, tamamlanınca bildirim al.

Sonra: **PWA → Android Companion** (native Android, masaüstü uygulamasının
yerine geçmez — uzaktan kumandasıdır).
Güvenlik: API portu internete ASLA açılmaz; QR + kısa ömürlü cihaz token.

### v1.8 — Automation & Post-processing (P1)
Referans: JDownloader + XDM.
İndirme bittikten sonra:

```text
Checksum
 ↓
Defender scan
 ↓
ZIP/RAR/7z extract
 ↓
Move
 ↓
Rename
 ↓
Script
 ↓
Notification
 ↓
Sleep / Shutdown
```

Ayrı worker queue kullanılmalı (manager thread'ini bloke etmez, idempotent).

### v1.9 — Rules Engine (P2)
Referans: File Centipede + AB DM. Kurallı yönlendirme:

```text
youtube.com   → D:\Video   → yt-dlp   → Chrome cookies
*.iso         → D:\ISO     → 16 connections
>20 GB        → gece kuyruğu
torrent       → ratio 1.0
github.com    → D:\GitHub
```

Rules: domain / extension / filename / size / protocol / category.
Actions: folder / proxy / speed / connection / schedule / headers / post-process.

### v2.0 — Plugin API + Marketplace (P2)
Referans: Gopeed + JDownloader + Motrix + pyLoad.

```text
resolve(url)
before_download(job)
after_download(job)
on_error(job)
```

Plugin türleri: Site Resolver / Post Processor / Integration / Automation / Theme.
İlk aşamada **trusted plugin** modeli; gerçek sandbox daha sonra.
Manifest: name, version, minimum AfuDM, permissions, domains, SHA256, entrypoint.

### v2.1 — Headless / NAS / Remote Server (P2)
Referans: pyLoad + Transmission + AriaNg.
Native Linux masaüstü uygulaması YAPILMAZ; AfuDM core `afuadm server` ile
UI olmadan çalışır: Windows sunucu / ev sunucusu / NAS'a bağlı Windows makine /
uzaktan kullanılan AfuDM instance. Docker ana hedef değil (P3).

### v2.2 — Windows Integration (P1/P2)
- Windows startup
- Windows Service / background mode
- Explorer sağ tık menüsü
- `afudm://` protocol handler
- Windows notifications
- "AfuDM ile indir" / "Linki AfuDM'ye gönder"
- Defender entegrasyonu
- Windows proxy entegrasyonunu geliştirme
- Default download-handler seçenekleri

### v2.3 — Security / Reliability / UX polish (P2)
- API rate limiting
- device token rotation
- secure pairing
- plugin permission audit
- DB recovery
- crash recovery
- interrupted download recovery
- corrupted `.aria2` recovery
- backup/restore settings
- diagnostics export
- structured logs
- sensitive-data redaction
- automatic engine health check

---

## Nihai ürün yönü

```text
WINDOWS DESKTOP
      │
      ├── HTTP / Files
      ├── Torrent
      ├── Video
      ├── LinkGrabber
      ├── Automation
      ├── Rules
      └── Plugins
             │
             ▼
         AfuDM Core
             │
     ┌───────┼────────┐
     ▼       ▼        ▼
   CLI    Browser   Mobile
                   Remote/PWA
```

> **Windows ana uygulama + Browser + PWA/Android Remote + Headless API.**
> Linux/macOS masaüstü hedefleri roadmap'ten çıkarılmıştır; cross-platform
> masaüstü hedefi yoktur.

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

---

## ✅ v1.5 — LinkGrabber: KAPANDI (2026-09-19)

P0 hedefine ulaşıldı. Akış **uçtan uca çalışıyor**:

```text
Clipboard / Browser (uzantı) / Manuel URL
        ↓
URL çıkarma (ayikla) → normalize → tekil_les
        ↓
tür/domain/arama/boyut filtresi (ogeleri_filtrele)
        ↓
"daha önce indirildi" işareti (onceki_eslesen, geçmiş DB'den)
        ↓
lazy probe (cache'li, iptal edilebilir, eszamanlılık sınırlı)
        ↓
LinkGrabber Panel (filtre çubuğu + durum satırı + rozetler)
        ↓
toplu indirme (Batch Add)
```

### Tamamlanan parçalar
- **Core** (`core/linkgrabber.py`): ayıkla → normalize → tekil_les → tur_bul →
  filtrele → ogeleri_filtrele (wildcard/arama/tür/domain/boyut) →
  onceki_eslesen (magnet infohash dahil) → probe_es_zamanli
  (ThreadPoolExecutor, hard limit 16, RAM cache TTL/cap, iptal event'i).
- **App köprüsü** (`app.py`): `linkgrabber_analiz / _suz / _onceki / _probe /
  _ekle / _iptal`. `_iptal` panel kapanınca çalışan probe'ları durdurur.
- **UI** (`ui/`): panel, filtre çubuğu (160 ms debounce), "önceden indirildi"
  rozeti, durum satırı (klik → önceden eklenenleri bırak), TR+EN i18n.
- **Browser handoff**: uzantıya "Sayfadaki/Seçili bağlantıları AfuDM
  LinkGrabber'a gönder" context menüsü; `/linkgrabber` Local API ucu; panel
  sayfa yüklenmeden gelen isteği de yerine ulaştırır.
- **Testler** (`tests/linkgrabber_test.py`): 100 kontrol, tamamı çevrimdışı
  (fake_http). API smoke: handoff ucu (501→503/UI_YOK→aktarım→400).

### Kabul kriterleri (hepsi geçti)
- 1000 URL → 3 sn altında toplu analiz; aynı URL ×100 → tek sonuç
- `File.zip` / `file.zip` → **farklı** kayıt (path case korunur)
- http / https aynı yol → **farklı** kayıt; aynı dosya adı farklı URL → ayrı
- magnet infohash büyük/küçük harf → tek kayıt
- redirect → son adresin bilgisi okunur; timeout → **diğer adresleri durdurmaz**
- cancel probe → istek atılmaz; batch add → kayıtlar sırayla girer

## 🚂 AfuDM Release Train — CI/release altyapısı (sıradaki teknik iş)

Yeni özellik yerine **önce süreç**: her sürüm el ile paketlenip sınamak yerine
tek komutla, doğrulanabilir biçimde yayınlanacak. Amaç: v1.6+ hızlanan
yayınların (Video Pro, Torrent Pro) kalite kapısını otomasyona bağlamak.

### Pipeline
```text
push → CI (test + build) → release tag vX.Y.Z
        ↓                          ↓
   unit testler       tag == origin/main HEAD? core/surum.py == tag?
                          ↓ hayır  ↓
                     BUILD FAIL (gate) — elle sürüm kazası engellenir
```

### GitHub Actions (`.github/workflows/`)
| Dosya | İş |
|---|---|
| `ci.yml` | her push: `scripts/test.ps1` (tüm çevrimdışı testler) + build (paketle) |
| `release.yml` | `v*` tag'inde: gate kontrolü → `build_release.ps1` → `verify_release.ps1` → `make_checksums.ps1` → artifact `AfuDM-vX.Y.Z-win64.zip(.sha256)` |
| `security.yml` | token/parola sızar mı (ör. `secrets/gitleaks` benzeri tarama) |

### Betikler (`scripts/`)
`test.ps1` (tüm testler, çevrimdışı) · `surum_oku.py` (sürümü tek yerden okur —
inline regex yok) · `build_exe.ps1` (AfuDM.spec → PyInstaller → dist → kök) ·
`build_release.ps1` (exe gerekirse üretir → temp klasör → paket) ·
`verify_release.ps1` (zip gerekli dosyaları içeriyor mu, attığında çalışıyor mu) ·
`smoke_test.ps1` (paketlenen exe'yi gerçekten koşturur) · `make_checksums.ps1`.

### GitHub Actions klasörü
Kökteki `AfuDM.spec` (PyInstaller spec) CI'da exe üretimini sağlar;
`build_out/AfuDM.spec` yalnızca yerel tarihsel bir kopyadır (gitignore'da).

### Kurallar
1. **main koruması:** `main`'e doğrudan veya force-push **YOK**; PR + CI zorunlu.
2. **Release gate:** tag `vX.Y.Z` yalnız `origin/main HEAD` ile aynıysa ve
   `core/surum.py == X.Y.Z` ise BUILD. Yanlış tag → FAIL (otomatik yakalanır).
3. **DB migrasyonları** yol haritası: her versiyon kendi migration'ını taşır
   (`core/db.py` user_version), geriye dönük uyum bundan geçecek.
4. **API uyumu:** `/capabilities` her sürümde büyür; mevcut alanlar kırılmaz,
   yeni özellik önce orada duyurulur (uzantı/mobil buna göre davranır).
5. **Kapanış prosedürü** her sürüm için sabittir (bkz. sürüm çıkış sırası):
   testleri koştur → sürümü artır (`core/surum.py`) → dokümanları kapat →
   tag → release workflow → kullanıcıya rapor.
