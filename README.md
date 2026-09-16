# AfuDM

IDM'in yerine geçen portable indirme yöneticisi. Dosya, video ve torrent indirir;
tek klasörde yaşar, sisteme hiçbir şey yazmaz.

Motorlar hazır gömülü: **aria2** (HTTP/FTP + BitTorrent), **yt-dlp** (1800+ video sitesi),
**ffmpeg** (birleştirme ve mp3).

## Başlatma

```
AfuDM.exe          Python gerekmez — masaüstü kısayolu da buna bakar
AfuDM.bat          kaynaktan çalıştırır (geliştirme)
```

`AfuDM.exe` kendi Python'unu içinde taşır; `engine/` ve `ui/` klasörleriyle
**aynı yerde** durmalıdır — bu yüzden ana klasördedir, taşıma.

Kaynaktan çalıştıracaksan bir kez `kur.bat` — sadece üç Python paketini kurar
(`pywebview`, `pystray`, `pillow`). Motorlar `engine/` klasöründe zaten var.

Portable kullanım: `AfuDM` klasörünü USB'ye ya da başka bir makineye kopyala,
`AfuDM.bat` ile çalıştır. Ayarlar `data/`, indirmeler `downloads/` içinde kalır.

## Ne yapar

**Hızlı indirme.** Bir dosyayı 64 parçaya böler, sunucu başına 16 bağlantı açar.
Ölçülen: 16 eşzamanlı bağlantı, 3.6 MB/s tepe hız.

**Duraklat ve devam.** Duraklattığın, hatta uygulamayı kapattığın indirme kaldığı
yerden sürer — aria2 oturumu her 15 saniyede diske yazılır.

**Video.** YouTube, Instagram, TikTok ve yt-dlp'nin desteklediği her yer.
Kalite seçimi (4K'ya kadar), sadece ses (mp3), playlist'in tamamı.

**Torrent.** Magnet ve `.torrent`. Canlı seed/peer sayısı, gönderilen bayt, oran.
DHT, PEX ve LPD açık; tracker listesi her gün otomatik yenilenir, böylece
yorgun torrentlerde de peer bulur.

**Kuyruk ve zamanlama.** Aynı anda kaç indirme, hız sınırı, "23:30'da başlat",
hepsi bitince Telegram'a haber ver veya bilgisayarı kapat.

**Pano yakalama.** İndirilebilir bir link kopyaladığında ekleme penceresi açılır.

**İki dil.** Türkçe ve İngilizce. Ayarlar → Dil / Language: Otomatik (Windows
dilinden seçer), Türkçe veya English. Değişiklik yeniden başlatmadan uygulanır;
pencere başlığı ve tepsi menüsü de döner. Tarayıcı uzantısı tarayıcının dilini
kullanır.

## Tarayıcı uzantısı

1. Chrome/Edge → `chrome://extensions` → Geliştirici modu açık
2. "Paketlenmemiş öğe yükle" → bu klasördeki `extension` klasörünü seç
3. AfuDM'de **Ayarlar → Uzantıyı bağla**'ya bas (2 dakikalık pencere açılır)
4. Uzantı simgesine tıkla → **Otomatik bağlan**

Bundan sonra tarayıcıdaki indirmeleri AfuDM devralır, sayfadaki videoları algılar,
sağ tık menüsüne "AfuDM ile indir" ekler. AfuDM kapalıysa uzantı hiçbir şeye
karışmaz, tarayıcı kendi işini yapar.

## Klasör düzeni

```
AfuDM/
  AfuDM.exe      tek dosya paket (Python gerekmez)
  AfuDM.bat      kaynaktan başlatıcı
  kur.bat        tek seferlik paket kurulumu
  app.py         pencere + tepsi + pano izleme
  core/          aria2 motoru, RPC, kuyruk, SQLite, tracker güncelleme
  video/         yt-dlp katmanı
  api/           yerel HTTP API (127.0.0.1 + token)
  ui/            arayüz (HTML/CSS/JS)
  extension/     Chrome/Edge uzantısı
  engine/        aria2c.exe, yt-dlp.exe, ffmpeg.exe
  data/          veritabanı, oturum, anahtarlar, log
  downloads/     varsayılan indirme klasörü
  tests/         smoke.py (gerçek indirme) + netcheck_test.py
  build_out/     PyInstaller çalışma alanı (kopyalarken atlayabilirsin)
  docs/DURUM.md  geliştirme notları
```

## Test

```
python tests/smoke.py                  # hepsi (gerçekten indirir)
python tests/smoke.py --skip-torrent   # HTTP + video
python tests/smoke.py --skip-video     # HTTP + torrent
python tests/netcheck_test.py          # IPv6 bayrağı (ağ gerektirmez)
python tests/manager_test.py           # magnet/başlık kuralları (ağ gerektirmez)
python tests/i18n_test.py              # dil anahtarları (ağ gerektirmez)
python tests/format_test.py            # video format seçimi (ağ gerektirmez)
```

Gerçekten indirir: çok bağlantılı HTTP, duraklat/sürdür, magnet seed takibi,
video → mp3. Son durum: HTTP+torrent 14/14, HTTP+video 11/11.

## Güvenlik

Yerel API yalnızca `127.0.0.1`'e bağlanır ve her istekte token ister. Token
`data/api_token.txt` içinde üretilir; uzantıya ancak sen "Uzantıyı bağla"
dedikten sonraki 2 dakika içinde verilir. aria2'nin RPC anahtarı da her
kurulumda rastgele üretilir.
