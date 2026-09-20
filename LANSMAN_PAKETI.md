# AfuDM v2.4.0 — Topluluk Lansman ve Tanıtım Paketi

Bu dosya; Reddit, Technopat Sosyal, DonanımHaber, AlternativeTo ve sosyal medya için hazırlanmış **doğrudan kopyala-yapıştır** formatında lansman içeriklerini barındırır.

---

## 1. Reddit Lansman Gönderisi (r/software, r/freemediaheckyeah, r/Piracy)

**Subreddit:** `r/software` veya `r/Piracy` (Sunday Showoff / Megathread / Tools)  
**Post Flair:** `Tool / Software` veya `Release`  
**Başlık:**
```
I got tired of IDM's fake serial popups and lack of torrent support, so I built AfuDM — an open-source, portable download engine for Windows (aria2 + yt-dlp + BitTorrent)
```

**İçerik:**
```markdown
Hey everyone!

Like many of you, I've used Internet Download Manager (IDM) for years. But dealing with "Fake Serial Number" popups after every Windows update, sketchy patchers, and the fact that IDM still looks like Windows 98 and **cannot download torrents** finally made me build my own solution.

Meet **AfuDM** — a zero-install, 100% portable download manager for Windows 10 & 11:

### 🔥 Why use it over IDM / other managers?

1. **100% Free & Open Source:** No fake serials, no licenses, no trials. MIT licensed.
2. **Tri-Engine Power in 22 MB:**
   - **aria2 Turbo:** Splits files into 64 chunks across 16 connections for true line-maxing speeds.
   - **BitTorrent & Magnet Swarms:** Full BitTorrent client with DHT, PEX, LPD and daily auto-refreshing tracker seed lists (revives dead swarms).
   - **Smart 4K Video Muxer:** Downloads from YouTube, TikTok, Instagram (yt-dlp powered) and merges 4K video + audio streams *without needing FFmpeg* (verified 46,368 frames identical).
3. **100% Portable:** Doesn't touch your Windows Registry or AppData. Put it on a USB flash drive and it works anywhere.
4. **Mobile Companion (New in v2.4.0):** Access your PC download queue from your phone via `http://<your-ip>:8010/m` over Wi-Fi. Pause, resume, and even hit **"Download to Phone"** to stream completed PC downloads straight into your mobile device!
5. **1-Click Chrome Integration:** One click to install the unpacked extension with full session-cookie forwarding and on-video grabber buttons.

### 📦 Download & Source
- **GitHub Releases:** https://github.com/pirncedark/AfuDM/releases
- **Source Code:** https://github.com/pirncedark/AfuDM

Check out the release notes and let me know your thoughts or feature requests in the comments!
```

---

## 2. Technopat Sosyal & DonanımHaber Forum Gönderisi

**Kategori:** `Yazılım / İndirme Yöneticileri / Açık Kaynak`  
**Başlık:**
```
[Açık Kaynak] IDM'e Yerli ve Ücretsiz Alternatif: AfuDM v2.4 (Dosya + 4K Video + Torrent + Mobil Kumanda)
```

**İçerik:**
```markdown
Merhaba arkadaşlar,

Yıllardır hepimiz IDM kullandık fakat sürekli çıkan sahte lisans (fake serial) uyarıları, virüslü crack arayışları ve IDM'in hala torrent indirememesi artık can sıkıcı bir hal almıştı. Üstelik video indirirken ses ile görüntünün ayrı kalması veya FFmpeg kurma zorunluluğu gibi dertler de cabasıydı.

Bu sorunları çözmek için açık kaynaklı ve kurulumsuz (portable) çalışan **AfuDM**'i geliştirdim.

### 🚀 Neden AfuDM?

- **3 Program Tek Pakette (Sadece 22 MB):** IDM + qBittorrent + Video Downloader çöplüğüne son.
  - **aria2 Motoru:** Dosyaları 64 parçaya bölüp 16 bağlantı açarak internet hattınızı sonuna kadar zorlar.
  - **BitTorrent / Magnet:** Günlük otomatik tracker yenileme desteğiyle ölü torrentleri bile canlandırır.
  - **FFmpeg Gerektirmeyen 4K Muxer:** YouTube, TikTok veya Reels videolarını 4K olarak sesle tek tıkla birleştirir (46.368 kare birebir doğrulandı).
- **Kayıt Defterini Kirletmez:** Sisteme hiçbir şey yüklemez, USB belleğe atıp istediğiniz bilgisayarda doğrudan çalıştırabilirsiniz.
- **v2.4 ile Mobil Kumanda Geldi:** Evde veya ofiste bilgisayarınız açıkken aynı Wi-Fi ağından telefonunuzla `http://<ip>:8010/m` adresine girip indirmeleri kontrol edebilir, biten dosyaları tek tıkla doğrudan **telefonunuza indirebilirsiniz**.
- **Tek Tıkla Chrome Eklentisi:** Tarayıcıdaki indirmeleri otomatik yakalar, izlediğiniz videoların üzerine indirme butonu ekler.

### 📥 İndirme ve İnceleme:
- **GitHub Sürüm Linki:** https://github.com/pirncedark/AfuDM/releases
- **Açık Kaynak Kodu:** https://github.com/pirncedark/AfuDM

Deneyip geri bildirimlerinizi, eksik gördüğünüz noktaları paylaşırsanız çok sevinirim!
```

---

## 3. AlternativeTo.net Listeleme Profili

**Uygulama Adı:** `AfuDM`  
**Slogan:** `Portable, open-source download manager for Windows with Torrents, 4K Video and Mobile Remote.`  
**Etiketler:** `download-manager`, `aria2`, `torrent-client`, `video-downloader`, `portable`, `open-source`, `windows`, `pwa`, `yt-dlp`  
**Alternatif Olduğu Programlar:**
- Internet Download Manager (IDM)
- Free Download Manager (FDM)
- JDownloader 2
- qBittorrent

**Açıklama (Description):**
```
AfuDM is a lightweight (22MB), 100% portable Windows download manager that combines multi-connection file acceleration, BitTorrent swarm handling, and 4K video extraction into a single zero-install package.

Key Highlights:
- High-Speed Multi-Connection: Powered by aria2, splitting files into up to 64 chunks across 16 connections.
- Built-In Torrent Client: Supports magnet links and .torrent files with daily auto-refreshing tracker lists to boost download seeds.
- Smart 4K Video Muxer: Powered by yt-dlp, joining high-res video and audio streams seamlessly without requiring FFmpeg on disk.
- Mobile Companion (PWA): Control your PC downloads over Wi-Fi from your mobile phone and download finished files directly to your phone.
- Zero-Registry Footprint: Runs entirely from its own folder or a USB stick.
```

---

## 4. Hazırlanan Tanıtım Videoları Listesi

| Video | Format | Süre | Dosya Yolu | Açıklama |
|---|---|---|---|---|
| **Lansman (EN)** | 1920x1080 (16:9) | 20s | `AfuDM/brag-output-en/brag.mp4` | Genel özellikler, Tri-engine, v2.4 Mobil kumanda |
| **Lansman (TR)** | 1920x1080 (16:9) | 20s | `AfuDM/brag-output-tr/brag.mp4` | Genel özellikler, Türkçe lansman videosu |
| **IDM Karşılaştırma (TR)** | 1080x1920 (9:16) | 19.5s | `AfuDM/brag-vs-idm-tr/brag-vs-idm.mp4` | Shorts/TikTok/Reels formatında IDM vs AfuDM |
| **IDM Comparison (EN)** | 1080x1920 (9:16) | 19.5s | `AfuDM/brag-vs-idm-en/brag-vs-idm.mp4` | Reddit/TikTok/Shorts formatında 3 Reasons to Delete IDM |
