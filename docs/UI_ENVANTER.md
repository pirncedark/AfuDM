# AfuDM — UI Kontrol ve Bileşen Envanteri

Bu doküman, AfuDM (`v1.7`) arayüzünün kaynak kodları (`ui/index.html`, `ui/app.js`, `ui/style.css`, `ui/i18n.js`, `core/db.py`) incelenerek hazırlanmış eksiksiz arayüz envanteridir. Her madde ve kontrol için dosya ve satır kanıtı (`DOSYA:SATIR`) belirtilmiştir.

---

## 1. Sayfalar, Sekmeler, Paneller ve Modallar

AfuDM tek pencereli bir masaüstü uygulamasıdır (`pywebview`). Arayüz katmanları; sabit üst bant izi/pencere başlığı, sol kenar çubuğu (rail), ana indirme listesi, detay çekmecesi (drawer) ve modal pencerelerden (veil) oluşur.

| Bileşen / Panel Adı | ID veya Seçici | Türü | Açıklama | Görünürlük / Tetiklenme | DOSYA:SATIR |
|---|---|---|---|---|---|
| Bant İzi & Başlık Çubuğu | `.trace` | Üst Sabit Panel | Canlı indirme hızı grafiği (canvas), hız metrikleri ve motor durumu | Her zaman görünür (özel başlıkta sürükleme alanı) | `ui/index.html:11`, `ui/style.css:48` |
| Pencere Kontrolleri | `#winControls` / `.wc` | Başlık Buton Grubu | Windows çerçevesiz pencere için küçült, büyüt/eski boyut, kapat butonları | Özel başlık aktifken (`.ozel-baslik .wc`) | `ui/index.html:25`, `ui/style.css:98` |
| Pencere Kenar Tutamaçları | `.wc-edge` | Boyutlandırma Kenarları | Pencere üst ve köşe boyutlandırma bölgeleri (`top`, `topleft`, `topright`) | Özel başlık aktifken | `ui/index.html:34-36`, `ui/app.js:2134-2138` |
| Sol Kenar Çubuğu | `aside.rail` | Sol Sabit Panel | Logo, sürüm rozeti, filtre sekme butonları, indirme klasörü/ayarlar/Chrome butonları | Her zaman görünür | `ui/index.html:40`, `ui/style.css:127` |
| Filtreler Menüsü | `nav.filters#filters` | Navigasyon Menüsü | Tümü, İndiriliyor, Duraklatıldı, Video, Torrent, Bitti, Hata filtre butonları | Her zaman görünür | `ui/index.html:44`, `ui/style.css:144` |
| Kenar Çubuğu Alt Butonları | `.rail-foot` | Alt Buton Grubu | Klasör açma, Chrome uzantı ekleme, ayarlar butonu ve portable yol ipucu | Her zaman görünür | `ui/index.html:53`, `ui/style.css:170` |
| Ana Üst Çubuk | `.main > .bar` | Eylem Çubuğu | Link ekle, Link yakala, Tümünü duraklat/sürdür, Arama kutusu, Bitenleri temizle | Her zaman görünür | `ui/index.html:62`, `ui/style.css:186` |
| İndirme Listesi | `.list#list` | Ana Liste Alanı | Aktif/kuyruktaki/biten indirme satırları (`.row`) veya boş durumu | Her zaman görünür | `ui/index.html:72`, `ui/style.css:218` |
| Detay Çekmecesi | `section.drawer#drawer` | Alt Açılır Çekmece | Seçili indirmeye ait sekmeli detay paneli | Bir indirme satırına tıklandığında açılır (`.open`) | `ui/index.html:74`, `ui/style.css:339`, `ui/app.js:372` |
| Çekmece Sekme Butonları | `#detailTabs` | Sekme Çubuğu | Genel bakış, Dosyalar, Trackerlar, Kurallar, Otomasyon, Günlükler sekmeleri | Detay çekmecesi açıkken | `ui/index.html:78`, `ui/app.js:394-399` |
| Çekmece: Genel Bakış | `#dPanelOverview` | Çekmece Paneli | Durum, boyut, indirilen, hız, eta, eş/seed, oran, hash, klasör bilgileri | Sekme `overview` seçiliyken (`.active`) | `ui/index.html:91`, `ui/app.js:256-261` |
| Çekmece: Dosyalar | `#dPanelFiles` | Çekmece Paneli | İndirilen dosyaların listesi ve torrent ise dosya seçim kutuları | Sekme `files` seçiliyken (`.active`) | `ui/index.html:95`, `ui/app.js:262-343` |
| Çekmece: Trackerlar | `#dPanelTrackers` | Çekmece Paneli | Torrent tracker listesi ve bağlı peer tablosu | Sekme `trackers` seçiliyken (`.active`) | `ui/index.html:99`, `ui/app.js:345-369` |
| Çekmece: Kurallar | `#dPanelRules` | Çekmece Paneli | v1.9 Rules Engine kural durum paneli (placeholder) | Sekme `rules` seçiliyken (`.active`) | `ui/index.html:104`, `ui/app.js:239-242` |
| Çekmece: Otomasyon | `#dPanelAutomation` | Çekmece Paneli | v1.8 Automation tetikleyici paneli (placeholder) | Sekme `automation` seçiliyken (`.active`) | `ui/index.html:108`, `ui/app.js:243-246` |
| Çekmece: Günlükler | `#dPanelLogs` | Çekmece Paneli | İndirmeye özel log ve olay listesi | Sekme `logs` seçiliyken (`.active`) | `ui/index.html:112`, `ui/app.js:247-250` |
| Modal: Link Ekle | `.veil#addVeil` | Modal İletişim Kutusu | Manuel URL/magnet/video linki ekleme, kalite ve zamanlama formu | `#addBtn` tıklandığında açılır | `ui/index.html:120`, `ui/app.js:569` |
| Modal: Ayarlar | `.veil#setVeil` | Modal İletişim Kutusu | Dil, indirme motorları, klasör, bağlantı limitleri, Telegram, sistem entegrasyonu | `#openSettings` tıklandığında açılır | `ui/index.html:164`, `ui/app.js:1502` |
| Modal: Chrome'a Ekle | `.veil#chromeVeil` | Modal İletişim Kutusu | Chrome tarayıcı uzantısını otomatik/manuel kurma rehberi | `#openChrome` tıklandığında açılır | `ui/index.html:298`, `ui/app.js:1473` |
| Modal: İndirme Bilgisi | `.veil#kaydetVeil` | Modal İletişim Kutusu | Tarayıcıdan/panodan gelen indirmeyi onaylama, ad/kategori/hedef/saat seçme | Tarayıcı/pano indirme isteğinde açılır | `ui/index.html:338`, `ui/app.js:1920` |
| Modal: Klasör Seçici | `.veil#klasorVeil` | Modal İletişim Kutusu | Ağaç yapısında klasör seçimi, yeni klasör oluşturma, ağ konumu ekleme | Hedef klasör "Değiştir/Seç" butonlarıyla açılır | `ui/index.html:413`, `ui/app.js:1824` |
| Modal: Seed Güncelleme | `.veil#seedVeil` | Modal İletişim Kutusu | Torrent için tracker havuzu yenileme, elle tracker ekleme ve canlı tarama | Satırdaki "Seed" butonundan açılır | `ui/index.html:434`, `ui/app.js:847` |
| Modal: Link Yakalayıcı | `.veil#lgVeil` | Modal İletişim Kutusu | Metinden toplu link çıkarma (LinkGrabber), tür/alan adı/boyut filtresi | `#lgBtn` veya harici uzantı handoff'u ile açılır | `ui/index.html:466`, `ui/app.js:792, 803` |
| Modal: Torrent Dosyaları | `.veil#torrentVeil` | Modal İletişim Kutusu | Torrent içindeki dosyaları ağaç yapısında seçme/bırakma ve metrik paneli | Çekmeceden veya dosya listesinden açılır | `ui/index.html:530`, `ui/app.js:1169` |
| Sağ Tık İçerik Menüsü | `.ctx#ctx` | Bağlam Menüsü | İndirme satırı veya metin kutuları için özel sağ tık eylem menüsü | Sağ tıklandığında açılır | `ui/index.html:573`, `ui/app.js:2182` |
| Bildirim Kutusu | `.toast#toast` | Geçici Bildirim | Eylem ve hata bildirimlerini gösteren toast kutusu | `toast()` çağrıldığında görünür | `ui/index.html:575`, `ui/app.js:50-57` |

---

## 2. Kullanıcı Kontrolleri Envanteri

Aşağıdaki tablo arayüzde yer alan her bir kullanıcı kontrolünü (buton, checkbox/toggle, metin kutusu, seçim listesi, radio butonu, bağlantı ve dinamik bileşenler) listelemektedir.

| Panel | Kontrol | i18n anahtari | Ne yapar | DOSYA:SATIR |
|---|---|---|---|---|
| Bant İzi & Başlık | `#wcMin` (button) | `win.min` | Pencereyi görev çubuğuna küçültür (`pencere_kucult`) | `ui/index.html:26`, `ui/app.js:2131` |
| Bant İzi & Başlık | `#wcMax` (button) | `win.max` / `win.restore` | Pencereyi ekranı kaplayacak şekilde büyütür veya önceki boyutuna döndürür (`pencere_buyut`) | `ui/index.html:28`, `ui/app.js:2132` |
| Bant İzi & Başlık | `#wcClose` (button) | `win.close` | Pencereyi kapatır veya ayara göre sistem tepsisine gizler (`pencere_kapat`) | `ui/index.html:31`, `ui/app.js:2133` |
| Bant İzi & Başlık | `.wc-edge` (div) | — | Pencere kenarlarından sürükleyerek yeniden boyutlandırmayı tetikler (`pencere_kenar`) | `ui/index.html:34-36`, `ui/app.js:2135` |
| Sol Kenar Çubuğu | `button.filter[data-f="all"]` | `filter.all` | İndirme listesinde tüm indirmeleri listeler | `ui/index.html:45`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="active"]` | `filter.active` | Yalnızca aktif inenleri listeler | `ui/index.html:46`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="paused"]` | `filter.paused` | Yalnızca duraklatılan indirmeleri listeler | `ui/index.html:47`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="video"]` | `filter.video` | Yalnızca video indirmelerini listeler | `ui/index.html:48`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="torrent"]` | `filter.torrent` | Yalnızca torrent indirmelerini listeler | `ui/index.html:49`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="complete"]` | `filter.complete` | Yalnızca tamamlanan indirmeleri listeler | `ui/index.html:50`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `button.filter[data-f="error"]` | `filter.error` | Yalnızca hatalı indirmeleri listeler | `ui/index.html:51`, `ui/app.js:513-518` |
| Sol Kenar Çubuğu | `#openFolder` (button) | `rail.openFolder` | İndirme klasörünü Windows Dosya Gezgini'nde açar (`open_download_dir`) | `ui/index.html:54`, `ui/app.js:530` |
| Sol Kenar Çubuğu | `#openChrome` (button) | `rail.chrome` | Chrome uzantı ekleme modalini (`#chromeVeil`) açar ve hazırlık yapar (`chrome_hazirla`) | `ui/index.html:55`, `ui/app.js:1473-1486` |
| Sol Kenar Çubuğu | `#openSettings` (button) | `rail.settings` | Ayarlar modalini (`#setVeil`) açar, ayarları ve motor durumlarını yükler | `ui/index.html:56`, `ui/app.js:1502-1539` |
| Ana Üst Çubuk | `#addBtn` (button) | `bar.add` | Link ekleme modalini (`#addVeil`) açar | `ui/index.html:63`, `ui/app.js:569-574` |
| Ana Üst Çubuk | `#lgBtn` (button) | `bar.lg` | Link yakalama modalini (`#lgVeil`) açar | `ui/index.html:64`, `ui/app.js:803` |
| Ana Üst Çubuk | `#pauseAll` (button) | `bar.pauseAll` | Tüm aktif indirmeleri topluca duraklatır (`control -> pause_all`) | `ui/index.html:65`, `ui/app.js:522` |
| Ana Üst Çubuk | `#resumeAll` (button) | `bar.resumeAll` | Tüm duraklatılmış indirmeleri topluca sürdürür (`control -> resume_all`) | `ui/index.html:66`, `ui/app.js:523` |
| Ana Üst Çubuk | `#search` (input text) | `bar.search` | Listelenen indirmeler arasında anlık arama/süzme yapar | `ui/index.html:68`, `ui/app.js:520` |
| Ana Üst Çubuk | `#clearDone` (button) | `bar.clearDone` | Tamamlanan indirmeleri listeden ve veritabanından temizler (`clear_finished`) | `ui/index.html:69`, `ui/app.js:524-529` |
| İndirme Listesi | `.row` (div / satır) | — | Satıra tıklandığında seçili yapar ve detay çekmecesini (`#drawer`) açar/kapatır | `ui/app.js:148`, `ui/app.js:498-508` |
| İndirme Listesi | `button[data-act="pause"]` | `row.pause` | Satırdaki indirmeyi duraklatır (`control -> pause`) | `ui/app.js:190`, `ui/app.js:488` |
| İndirme Listesi | `button[data-act="resume"]` | `row.resume` | Satırdaki indirmeyi sürdürür (`control -> resume`) | `ui/app.js:191`, `ui/app.js:488` |
| İndirme Listesi | `button[data-act="retry"]` | `row.retry` | Hatalı indirmeyi baştan başlatır (`control -> retry`) | `ui/app.js:192`, `ui/app.js:488` |
| İndirme Listesi | `button[data-act="folder"]` | `row.folder` | İndirilen dosyanın bulunduğu klasörü açar (`open_dir`) | `ui/app.js:193`, `ui/app.js:488` |
| İndirme Listesi | `button[data-act="remove"]` | `row.remove` | İndirmeyi listeden kaldırır (dosyayı silmez) (`control -> remove`) | `ui/app.js:194`, `ui/app.js:488` |
| İndirme Listesi | `button[data-act="seed"]` | `row.seed` | Torrent indirmesi için Seed/Tracker güncelleme modalini (`#seedVeil`) açar | `ui/app.js:196`, `ui/app.js:488, 847` |
| Detay Çekmecesi | `#dTabOverview` (button) | `dtab.overview` | Genel bakış panelini (`#dPanelOverview`) gösterir | `ui/index.html:79`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTabFiles` (button) | `dtab.files` | Dosyalar panelini (`#dPanelFiles`) gösterir | `ui/index.html:80`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTabTrackers` (button) | `dtab.trackers` | Trackerlar ve peerlar panelini (`#dPanelTrackers`) gösterir | `ui/index.html:81`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTabRules` (button) | `dtab.rules` | Kurallar panelini (`#dPanelRules`) gösterir | `ui/index.html:82`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTabAutomation` (button) | `dtab.automation` | Otomasyon panelini (`#dPanelAutomation`) gösterir | `ui/index.html:83`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTabLogs` (button) | `dtab.logs` | Günlükler panelini (`#dPanelLogs`) gösterir | `ui/index.html:84`, `ui/app.js:231, 398` |
| Detay Çekmecesi | `#dTorFiles` (button) | `tor.btnFiles` | Torrent indirmelerinde torrent dosya seçim penceresini (`#torrentVeil`) açar | `ui/index.html:86`, `ui/app.js:390-391` |
| Detay Çekmecesi | `#dClose` (button) | `drawer.close` | Detay çekmecesini kapatır ve satır seçimini sıfırlar | `ui/index.html:87`, `ui/app.js:510` |
| Çekmece Dosyalar | `#dOpenTorVeil` (button) | `tor.files` | Dosyalar sekmesinden Torrent dosyaları modalini açar | `ui/app.js:265, 287` |
| Çekmece Dosyalar | `input[type=checkbox][data-idx]` | — | Torrent içindeki dosyanın indirilip indirilmeyeceğini seçer (`torrent_secimi_ayarla`) | `ui/app.js:296, 311-329` |
| Modal: Link Ekle | `#urls` (textarea) | `add.urls` | Eklenecek indirme adreslerini (HTTP/magnet/video) satır satır alır | `ui/index.html:126` |
| Modal: Link Ekle | `#quality` (select) | `add.quality` | İndirilecek video kalitesini belirler (`best`, `2160`, `1080`, `720`, `480`, `audio`) | `ui/index.html:130-137` |
| Modal: Link Ekle | `#startAt` (input text) | `add.startAt` | İndirmenin başlayacağı zamanı ayarlar (ör: `23:30`) | `ui/index.html:141` |
| Modal: Link Ekle | `#playlist` (input checkbox) | `add.playlist` | Video linki playlist ise tamamının indirilmesini seçer | `ui/index.html:145` |
| Modal: Link Ekle | `#audioOnly` (input checkbox) | `add.audioOnly` | Videonun yalnızca sesini mp3 olarak çıkarmayı seçer | `ui/index.html:146` |
| Modal: Link Ekle | `#dest` (input text) | `add.dest` | İndirmenin yapılacağı hedef klasör yolunu belirler | `ui/index.html:150` |
| Modal: Link Ekle | `#destPick` (button) | `add.pick` | Hedef klasörü seçmek için `#klasorVeil` modalini açar | `ui/index.html:151`, `ui/app.js:1893-1896` |
| Modal: Link Ekle | `button[data-close="addVeil"]` | `add.cancel` | Link ekleme penceresini kapatır / iptal eder | `ui/index.html:157`, `ui/app.js:560` |
| Modal: Link Ekle | `#addGo` (button) | `add.go` | Girilen bağlantıları indirme motoruna ekler (`add_uris`) | `ui/index.html:158`, `ui/app.js:575-606` |
| Modal: Ayarlar | `#sLang` (select) | `set.lang` | Arayüz dilini seçer (`auto`, `tr`, `en`) | `ui/index.html:170-174`, `ui/app.js:1504, 1710` |
| Modal: Ayarlar | `button[data-motor]` (button) | `eng.download` | Eksik veya sistemden kullanılan motoru (`aria2c`, `yt-dlp`, `ffmpeg`) indirir (`motor_indir`) | `ui/app.js:1664-1678, 1689-1698` |
| Modal: Ayarlar | `#sDir` (input text) | `set.dir` | Varsayılan indirme klasörü yolunu belirler | `ui/index.html:183`, `ui/app.js:1505, 1711` |
| Modal: Ayarlar | `#sSplit` (input number) | `set.split` | Dosya başına indirme parça sayısını belirler (1-128) | `ui/index.html:189`, `ui/app.js:1506, 1712` |
| Modal: Ayarlar | `#sConn` (input number) | `set.conn` | Sunucu başına maksimum bağlantı sayısını belirler (1-16) | `ui/index.html:193`, `ui/app.js:1507, 1713` |
| Modal: Ayarlar | `#sConc` (input number) | `set.conc` | Aynı anda paralel indirilecek görev sayısını belirler (1-20) | `ui/index.html:197`, `ui/app.js:1508, 1714` |
| Modal: Ayarlar | `#sSpeed` (input number) | `set.speed` | Maksimum indirme hız sınırını KB/s cinsinden belirler (0 = sınırsız) | `ui/index.html:201`, `ui/app.js:1509, 1715` |
| Modal: Ayarlar | `#sMode` (select) | `set.mode` | Hız profilini belirler (`turbo`, `normal`, `snail`) | `ui/index.html:205-209`, `ui/app.js:1510, 1716` |
| Modal: Ayarlar | `#sRatio` (input number) | `set.ratio` | Torrent seed paylaşım oran sınırını belirler | `ui/index.html:213`, `ui/app.js:1511, 1717` |
| Modal: Ayarlar | `#sChat` (input text) | `set.chat` | Telegram bildirimleri için hedef sohbet kimliğini (chat_id) alır | `ui/index.html:217`, `ui/app.js:1512, 1718` |
| Modal: Ayarlar | `#sToken` (input text) | `set.token` | Telegram bildirimleri için bot erişim anahtarını (token) alır | `ui/index.html:222`, `ui/app.js:1513, 1719` |
| Modal: Ayarlar | `#sClip` (input checkbox) | `set.clip` | Panoya kopyalanan URL'lerin otomatik yakalanmasını açar/kapatır | `ui/index.html:225`, `ui/app.js:1514, 1720` |
| Modal: Ayarlar | `#sTrackers` (input checkbox) | `set.trackers` | Torrent tracker listelerinin günlük güncellenmesini açar/kapatır | `ui/index.html:226`, `ui/app.js:1515, 1721` |
| Modal: Ayarlar | `#sNotify` (input checkbox) | `set.notify` | İndirme bitince Telegram'a haber verme bildirimini açar/kapatır | `ui/index.html:227`, `ui/app.js:1516, 1722` |
| Modal: Ayarlar | `#sShutdown` (input checkbox) | `set.shutdown` | Tüm indirmeler bitince bilgisayarı otomatik kapatmayı açar/kapatır | `ui/index.html:228`, `ui/app.js:1517, 1723` |
| Modal: Ayarlar | `#sSleep` (input checkbox) | `set.sleep` | Tüm indirmeler bitince bilgisayarı uyutmayı açar/kapatır | `ui/index.html:229`, `ui/app.js:1518, 1724` |
| Modal: Ayarlar | `#sKaydet` (input checkbox) | `set.kaydet` | İndirme başlamadan önce bilgi/kaydetme penceresini göstermeyi ayarlar | `ui/index.html:230`, `ui/app.js:1520, 1725` |
| Modal: Ayarlar | `#sKategori` (input checkbox) | `set.kategori` | İndirmeleri dosya türüne göre kategori alt klasörlerine ayırmayı ayarlar | `ui/index.html:231`, `ui/app.js:1521, 1726` |
| Modal: Ayarlar | `#sTepsi` (input checkbox) | `set.tepsi` | Pencere kapatılınca (`X`) sistem tepsisine simge durumuna küçülmeyi ayarlar | `ui/index.html:232`, `ui/app.js:1522, 1727` |
| Modal: Ayarlar | `#sBaslangic` (input checkbox) | `set.baslangic` | Windows başlangıcında AfuDM'in otomatik çalıştırılmasını ayarlar | `ui/index.html:233`, `ui/app.js:1546, 1561` |
| Modal: Ayarlar | `#sTorrent` (input checkbox) | `set.torrent` | .torrent dosyaları ve magnet linkleri için AfuDM'i Windows'ta varsayılan yapar | `ui/index.html:234`, `ui/app.js:1549, 1564` |
| Modal: Ayarlar | `#sBasTepside` (input checkbox) | `set.basTepside` | Bilgisayar açılışında pencere açılmadan sistem tepsisinde başlatmayı ayarlar | `ui/index.html:235`, `ui/app.js:1523, 1728` |
| Modal: Ayarlar | `#sTelefon` (input checkbox) | `set.telefon` | Yerel ağdaki telefondan erişim için mobil web arayüzünü açar/kapatır | `ui/index.html:236`, `ui/app.js:1584, 1592-1600` |
| Modal: Ayarlar | `#sSeedEkle` (button) | `set.seedEkle` | Dosya seçici ile yeni bir tracker `.txt` dosyası ekler (`seed_dosya_ekle`) | `ui/index.html:246`, `ui/app.js:1408-1416` |
| Modal: Ayarlar | `#sSeedKlasor` (button) | `set.seedKlasor` | Tracker listelerinin tutulduğu `trackers/` klasörünü açar (`tracker_klasoru_ac`) | `ui/index.html:247`, `ui/app.js:1418-1420` |
| Modal: Ayarlar | `#sSeedTara` (button) | `set.seedTara` | Yüklü tüm tracker adreslerini canlılık için hemen tarar (`seed_tara`) | `ui/index.html:248`, `ui/app.js:1422-1433` |
| Modal: Ayarlar | `button.seed-sil` (button) | `set.seedSil` | İlgili seed listesi dosyasını siler (`seed_dosya_sil`) | `ui/app.js:1388-1396` |
| Modal: Ayarlar | `#sSeedEk` (textarea) | `set.seedEk` | Kullanıcının elle girdiği ek tracker adreslerini tutar | `ui/index.html:254`, `ui/app.js:1528, 2334` |
| Modal: Ayarlar | `#sSeedEkYapistir` (button) | `set.seedEkYapistir` | Panodaki metni ek tracker textarea kutusuna yapıştırır (`panodanOku`) | `ui/index.html:256`, `ui/app.js:2323-2329` |
| Modal: Ayarlar | `#sSeedEkKaydet` (button) | `set.seedEkKaydet` | Elle girilen ek tracker'ları kaydeder ve temizler (`seed_tracker_kaydet`) | `ui/index.html:257`, `ui/app.js:2331-2339` |
| Modal: Ayarlar | `#sSeedOto` (input checkbox) | `set.seedOto` | Seed listelerini her gün otomatik tarayıp ölüleri elemeyi açar/kapatır | `ui/index.html:260`, `ui/app.js:1403, 1729` |
| Modal: Ayarlar | `#sMac` (input text) | `set.wol` | Bilgisayarın Wake-on-LAN için kullanılan fiziksel MAC adresini gösterir (readonly) | `ui/index.html:266`, `ui/app.js:1621` |
| Modal: Ayarlar | `#sMacKopya` (button) | `set.kopyala` | MAC adresini panoya kopyalar | `ui/index.html:267`, `ui/app.js:1630-1635` |
| Modal: Ayarlar | `#sTelefonAdres` (input text) | `set.telefonAdres` | Telefon tarayıcısı için yerel ağ adresini gösterir (readonly) | `ui/index.html:275`, `ui/app.js:1586` |
| Modal: Ayarlar | `#sTelefonKopya` (button) | `set.kopyala` | Telefon erişim bağlantısını panoya kopyalar (`panoyaYaz`) | `ui/index.html:276`, `ui/app.js:1602-1608` |
| Modal: Ayarlar | `#sVarsayilan` (button) | `set.varsayilan` | Windows Varsayılan Uygulamalar ayar ekranını açar (`varsayilan_uygulama_ekrani`) | `ui/index.html:282`, `ui/app.js:1571-1575` |
| Modal: Ayarlar | `#pairBtn` (button) | `set.pair` | Chrome uzantısıyla otomatik eşleşme için 120 saniyelik port dinleme başlatır (`start_pairing`) | `ui/index.html:288`, `ui/app.js:1701-1705` |
| Modal: Ayarlar | `button[data-close="setVeil"]` | `set.cancel` | Ayarlar penceresini değişiklikleri kaydetmeden kapatır | `ui/index.html:290`, `ui/app.js:560` |
| Modal: Ayarlar | `#setGo` (button) | `set.save` | Tüm ayarları veritabanına ve Windows sistemine kaydeder (`settings_save`) | `ui/index.html:291`, `ui/app.js:1708-1743` |
| Modal: Chrome | `#chrAuto` (button) | `chr.auto` | Chrome uzantısını otomatik olarak tarayıcıya eklemeyi başlatır (`chrome_otomatik`) | `ui/index.html:304`, `ui/app.js:1488-1492` |
| Modal: Chrome | `button[data-kopya="adres"]` | `chr.copy` | `chrome://extensions/` adresini panoya kopyalar (`chrome_kopyala -> adres`) | `ui/index.html:320`, `ui/app.js:1493-1499` |
| Modal: Chrome | `button[data-kopya="klasor"]` | `chr.copy` | AfuDM uzantı klasör yolunu panoya kopyalar (`chrome_kopyala -> klasor`) | `ui/index.html:325`, `ui/app.js:1493-1499` |
| Modal: Chrome | `#chrElle` (details/summary) | `chr.manual` | Uzantının elle kurulum adımlarını açar/kapatır | `ui/index.html:316` |
| Modal: Chrome | `button[data-close="chromeVeil"]` | `chr.close` | Chrome ekleme penceresini kapatır | `ui/index.html:332`, `ui/app.js:560` |
| Modal: İndirme Bilgisi | `#kayName` (input text) | `kay.name` | İndirilecek dosyanın adını düzenler | `ui/index.html:348`, `ui/app.js:2044` |
| Modal: İndirme Bilgisi | `#kayCat` (select) | `kay.cat` | İndirme kategorisini seçer; hedef klasörü kategoriye göre günceller | `ui/index.html:353`, `ui/app.js:1903-1918, 1991` |
| Modal: İndirme Bilgisi | `#kayQuality` (select) | `kay.quality` | Video indirmesi için kalite seçimi yapar | `ui/index.html:357-364`, `ui/app.js:2052` |
| Modal: İndirme Bilgisi | `#kayDest` (input text) | `kay.dest` | Dosyanın kaydedileceği hedef klasör yolunu belirler | `ui/index.html:369`, `ui/app.js:2045` |
| Modal: İndirme Bilgisi | `#kayPick` (button) | `kay.pick` | Hedef klasörü seçmek için `#klasorVeil` modalini açar | `ui/index.html:370`, `ui/app.js:1992-1995` |
| Modal: İndirme Bilgisi | `#kayNow` (input radio) | `kay.now` | İndirmenin hemen şimdi başlatılmasını seçer | `ui/index.html:375`, `ui/app.js:2047` |
| Modal: İndirme Bilgisi | `#kayLater` (input radio) | `kay.later` | İndirmenin belirtilen saatte zamanlanarak başlatılmasını seçer | `ui/index.html:376`, `ui/app.js:2047` |
| Modal: İndirme Bilgisi | `#kayAt` (input text) | `add.startAt` | Zamanlanmış başlangıç saatini alır (ör: `23:30`) | `ui/index.html:380`, `ui/app.js:2048` |
| Modal: İndirme Bilgisi | `#kayTorAra` (input text) | `tor.filterPh` | Torrent içindeki dosya/klasör adlarında arama yapar | `ui/index.html:389`, `ui/app.js:1291` |
| Modal: İndirme Bilgisi | `#kayTorSecHepsi` (button) | `tor.selectAll` | Torrent içindeki tüm dosyaları seçili yapar | `ui/index.html:391`, `ui/app.js:1299-1302` |
| Modal: İndirme Bilgisi | `#kayTorSecHicbiri` (button) | `tor.selectNone` | Torrent içindeki tüm dosya seçimlerini temizler | `ui/index.html:392`, `ui/app.js:1303-1306` |
| Modal: İndirme Bilgisi | `#kayTorSecTers` (button) | `tor.invert` | Torrent içindeki dosya seçimlerini tersine çevirir | `ui/index.html:393`, `ui/app.js:1307-1311` |
| Modal: İndirme Bilgisi | `#kayTorLimitHepsi` (button) | `tor.showAll` | Çok dosyalı torrentlerde limit sınırını kaldırıp tüm dosyaları gösterir | `ui/index.html:398`, `ui/app.js:1295-1298` |
| Modal: İndirme Bilgisi | `#kayCancel` (button) | `kay.cancel` | İndirme isteğini reddeder ve pencereyi kapatır (`kaydet_reddet`) | `ui/index.html:406`, `ui/app.js:2016, 2040` |
| Modal: İndirme Bilgisi | `#kayGo` (button) | `kay.go` | İndirmeyi onaylar ve indirme motoruna gönderir (`kaydet_onayla`) | `ui/index.html:407`, `ui/app.js:2042-2070` |
| Modal: Klasör Seçici | `#agac .dugum` (div) | — | Tıklanan klasörü seçer ve yolunu `#klasYol` kutusuna yazar | `ui/app.js:1747, 1795-1803` |
| Modal: Klasör Seçici | `#agac .ok` (span) | — | Klasörü genişletir / alt klasörleri açıp kapatır | `ui/app.js:1754, 1771-1793` |
| Modal: Klasör Seçici | `#klasYol` (input text) | — | Seçilen klasörün tam yolunu gösterir veya elle girilmesini sağlar | `ui/index.html:419`, `ui/app.js:1768, 1841` |
| Modal: Klasör Seçici | `#klasYeni` (button) | `klas.new` | Seçili klasör altında yeni bir klasör oluşturur (`prompt` + `klasor_yeni`) | `ui/index.html:420`, `ui/app.js:1845-1855` |
| Modal: Klasör Seçici | `#klasAg` (button) | `klas.ag` | Ağ konumu / NAS paylaşımı ekler (`prompt` + `klasor_ag_ekle`) | `ui/index.html:421`, `ui/app.js:1874-1883` |
| Modal: Klasör Seçici | `#klasSistem` (button) | `klas.system` | Windows'un yerel klasör seçme iletişim kutusunu açar (`klasor_gozat`) | `ui/index.html:422`, `ui/app.js:1856-1863` |
| Modal: Klasör Seçici | `#klasCancel` (button) | `klas.cancel` | Klasör seçimini iptal eder ve modalı kapatır | `ui/index.html:427`, `ui/app.js:1839` |
| Modal: Klasör Seçici | `#klasOk` (button) | `klas.ok` | Seçilen klasör yolunu onaylayıp çağıran forma aktarır | `ui/index.html:428`, `ui/app.js:1840-1844` |
| Modal: Seed Güncelle | `#seedEk` (textarea) | `seed.ek` | Seçili torrente özel eklenecek tracker adreslerini alır | `ui/index.html:442`, `ui/app.js:875` |
| Modal: Seed Güncelle | `#seedKlasor` (button) | `seed.klasorAc` | Tracker `.txt` dosyalarının bulunduğu klasörü açar (`tracker_klasoru_ac`) | `ui/index.html:447`, `ui/app.js:903-905` |
| Modal: Seed Güncelle | `#seedTara` (button) | `seed.tara` | Torrente ait tracker listesini canlılık için tarar (`seed_tara_torrent`) | `ui/index.html:448`, `ui/app.js:888-901` |
| Modal: Seed Güncelle | `button[data-close="seedVeil"]` | `seed.close` | Seed güncelleme modalini kapatır | `ui/index.html:456`, `ui/app.js:560` |
| Modal: Seed Güncelle | `#seedKaydet` (button) | `seed.kaydet` | Elle girilen ek tracker'ları kaydeder (`seed_tracker_kaydet`) | `ui/index.html:458`, `ui/app.js:876-885` |
| Modal: Seed Güncelle | `#seedGo` (button) | `seed.go` | Güncel tracker listesini indirip torrenti yeniden duyurur (`seed_tazele`) | `ui/index.html:459`, `ui/app.js:861-873` |
| Modal: LinkGrabber | `#lgMetin` (textarea) | `lg.metin` | İçinden link ayıklanacak serbest metni alır | `ui/index.html:472`, `ui/app.js:722` |
| Modal: LinkGrabber | `#lgAra` (input text) | `lg.araLabel` | Bulunan bağlantılar arasında ada göre jokerli (*, ?) filtreleme yapar | `ui/index.html:477`, `ui/app.js:810` |
| Modal: LinkGrabber | `#lgSadece` (select) | `lg.turLabel` | Dosya türü filtresi uygular (`all`, `video`, `arsiv`, `torrent`, `http`) | `ui/index.html:482-488`, `ui/app.js:624, 807` |
| Modal: LinkGrabber | `#lgDomain` (select) | `lg.domainLabel` | Alan adı (domain) filtresi uygular | `ui/index.html:492`, `ui/app.js:627, 808` |
| Modal: LinkGrabber | `#lgBoyut` (select) | `lg.boyutLabel` | Dosya boyutu filtresi uygular (`>1GB`, `>100MB`, `>10MB`, `<10MB`, `<100MB`) | `ui/index.html:498-506`, `ui/app.js:628, 809` |
| Modal: LinkGrabber | `#lgDest` (input text) | `lg.dest` | Yakalanan linklerin indirileceği hedef klasörü belirler | `ui/index.html:510`, `ui/app.js:774` |
| Modal: LinkGrabber | `#lgAnaliz` (button) | `lg.analiz` | Metni analiz ederek URL'leri ayrıştırır (`linkgrabber_analiz`) | `ui/index.html:514`, `ui/app.js:721-744, 804` |
| Modal: LinkGrabber | `#lgProbe` (button) | `lg.probe` | Seçili bağlantıların dosya boyutlarını HTTP HEAD ile sorgular (`linkgrabber_probe`) | `ui/index.html:515`, `ui/app.js:746-765, 805` |
| Modal: LinkGrabber | `#lgDurum` (span/button) | `lg.oncekiKaldir` | Önceden indirilmiş linkler varsa tıklanınca onların seçimini kaldırır | `ui/index.html:516`, `ui/app.js:710-714` |
| Modal: LinkGrabber | `input[type=checkbox][data-i]` | — | Yakalanan listedeki tekil linkin indirilme seçimini açar/kapatır | `ui/app.js:690, 701-705` |
| Modal: LinkGrabber | `button[data-close="lgVeil"]` | `lg.cancel` | LinkGrabber penceresini kapatır | `ui/index.html:524`, `ui/app.js:560` |
| Modal: LinkGrabber | `#lgGo` (button) | `lg.go` | Seçilen linkleri topluca indirme kuyruğuna ekler (`linkgrabber_ekle`) | `ui/index.html:526`, `ui/app.js:768-789, 806` |
| Modal: Torrent Dosya | `#torAra` (input text) | `tor.filterPh` | Torrent dosyaları ve klasörleri içinde filtreleme yapar | `ui/index.html:549`, `ui/app.js:1291` |
| Modal: Torrent Dosya | `#torSecHepsi` (button) | `tor.selectAll` | Torrentteki tüm dosyaları seçer | `ui/index.html:552`, `ui/app.js:1299-1302` |
| Modal: Torrent Dosya | `#torSecHicbiri` (button) | `tor.selectNone` | Torrentteki tüm dosya seçimlerini kaldırır | `ui/index.html:553`, `ui/app.js:1303-1306` |
| Modal: Torrent Dosya | `#torSecTers` (button) | `tor.invert` | Torrentteki mevcut seçimleri tersine çevirir | `ui/index.html:554`, `ui/app.js:1307-1311` |
| Modal: Torrent Dosya | `span.tor-katla[data-act="katla"]` | — | Torrent ağacındaki klasörü genişletir veya daraltır | `ui/app.js:1074, 1262-1268` |
| Modal: Torrent Dosya | `input[type=checkbox][data-yol]` | — | Klasör seviyesindeki tüm alt dosyaları topluca seçer/bırakır | `ui/app.js:1076, 1269-1279` |
| Modal: Torrent Dosya | `input[type=checkbox][data-idx]` | — | Tekil torrent dosyasını seçer/bırakır | `ui/app.js:1102, 1280-1288` |
| Modal: Torrent Dosya | `#torLimitHepsi` (button) | `tor.showAll` | Çok dosyalı torrentlerde limit uyarısını kaldırıp tüm dosyaları listeler | `ui/index.html:562`, `ui/app.js:1295-1298` |
| Modal: Torrent Dosya | `button[data-close="torrentVeil"]` | `tor.close` | Torrent dosyaları penceresini kapatır | `ui/index.html:565`, `ui/app.js:560` |
| Modal: Torrent Dosya | `#torUygula` (button) | `tor.apply` | Seçili dosya indekslerini aria2'ye uygular (`torrent_secimi_ayarla`) | `ui/index.html:567`, `ui/app.js:1320-1355` |
| Sağ Tık Menüsü | Satır Sağ Tık: Bağlantıyı kopyala | `ctx.copyLink` | İndirme URL adresini panoya kopyalar (`panoyaYaz`) | `ui/app.js:2252` |
| Sağ Tık Menüsü | Satır Sağ Tık: Dosya adını kopyala | `ctx.copyName` | Dosya adını panoya kopyalar (`panoyaYaz`) | `ui/app.js:2253` |
| Sağ Tık Menüsü | Satır Sağ Tık: Dosya yolunu kopyala | `ctx.copyPath` | İndirilen dosyanın tam disk yolunu panoya kopyalar (`panoyaYaz`) | `ui/app.js:2254` |
| Sağ Tık Menüsü | Satır Sağ Tık: Dosyayı aç | `ctx.openFile` | İndirilen dosyayı varsayılan programla açar (`open_file`) | `ui/app.js:2256` |
| Sağ Tık Menüsü | Satır Sağ Tık: Klasörü aç | `ctx.openFolder` | Dosyanın bulunduğu klasörü açar (`open_dir`) | `ui/app.js:2257` |
| Sağ Tık Menüsü | Satır Sağ Tık: Yeniden indir | `ctx.again` | İndirmeyi baştan yeni bir görev olarak ekler (`add_uris`) | `ui/app.js:2259` |
| Sağ Tık Menüsü | Satır Sağ Tık: Duraklat | `row.pause` | İndirmeyi duraklatır (`control -> pause`) | `ui/app.js:2264` |
| Sağ Tık Menüsü | Satır Sağ Tık: Sürdür | `row.resume` | İndirmeyi sürdürür (`control -> resume`) | `ui/app.js:2266` |
| Sağ Tık Menüsü | Satır Sağ Tık: Kaldır | `row.remove` | İndirmeyi listeden kaldırır (`control -> remove`, disk dosyası kalır) | `ui/app.js:2270` |
| Sağ Tık Menüsü | Satır Sağ Tık: Sil | `row.delete` | İndirmeyi ve indirilen dosyayı diskten kalıcı olarak siler (`control -> remove`, diskten sil) | `ui/app.js:2272` |
| Sağ Tık Menüsü | Metin Kutusu: Kes | `ctx.cut` | Seçili metni kesip panoya kopyalar | `ui/app.js:2226` |
| Sağ Tık Menüsü | Metin Kutusu: Kopyala | `ctx.copy` | Seçili metni panoya kopyalar | `ui/app.js:2229` |
| Sağ Tık Menüsü | Metin Kutusu: Yapıştır | `ctx.paste` | Panodaki metni imleç yerine yapıştırır (`panodanOku`) | `ui/app.js:2232` |
| Sağ Tık Menüsü | Metin Kutusu: Tümünü seç | `ctx.selectAll` | Metin alanındaki metnin tamamını seçer | `ui/app.js:2235` |
| Sağ Tık Menüsü | Ağ Konumu Sağ Tık: Kaldır | `klas.agSil` | Klasör ağacındaki UNC ağ kısayolunu onay alarak listeden siler (`klasor_ag_sil`) | `ui/app.js:1805-1815` |

---

## 3. Ayarlar Ekranında Bulunan Tüm Ayarlar Listesi

Ayarlar modalinde (`#setVeil`) kullanıcı tarafından yapılandırılabilen tüm alanların veritabanı ayar anahtarı, türü, varsayılan değeri ve dosya kanıtları şöyledir:

| Ayar Adı / Etiketi | UI Kontrolü | i18n Anahtarı | Veritabanı / Backend Anahtarı | Tip | Varsayılan Değer | Ne Yapar | DOSYA:SATIR |
|---|---|---|---|---|---|---|---|
| Dil / Language | `#sLang` (select) | `set.lang` | `language` | string | `"auto"` | Uygulama dilini belirler (`auto`, `tr`, `en`). `auto` seçildiğinde Windows dili kullanılır. | `ui/index.html:170`, `ui/app.js:1504, 1710`, `core/db.py:53` |
| Motorlar (aria2c, yt-dlp, ffmpeg) | `#engines` (butonlar) | `set.engines`, `eng.download` | `motor_durumu`, `motor_indir` | action | — | Gerekli video ve indirme motorlarını indirir, durum ve boyutlarını gösterir. | `ui/index.html:178`, `ui/app.js:1643-1698` |
| İndirme klasörü | `#sDir` (input text) | `set.dir` | `download_dir` | string | `""` (boş = portable `downloads/`) | İndirmelerin kaydedileceği varsayılan ana klasör yolu. | `ui/index.html:183`, `ui/app.js:1505, 1711`, `core/db.py:54` |
| Dosya başına parça (split) | `#sSplit` (input number) | `set.split` | `split` | integer | `64` (min 1, max 128) | aria2'nin tek bir dosyayı böleceği maksimum parça sayısı. | `ui/index.html:189`, `ui/app.js:1506, 1712`, `core/db.py:56` |
| Sunucu başına bağlantı | `#sConn` (input number) | `set.conn` | `max_conn_per_server` | integer | `16` (min 1, max 16) | Bir sunucuya açılacak eşzamanlı maksimum bağlantı sayısı. | `ui/index.html:193`, `ui/app.js:1507, 1713`, `core/db.py:57` |
| Aynı anda indirme | `#sConc` (input number) | `set.conc` | `max_concurrent` | integer | `5` (min 1, max 20) | Aynı anda aktif indirilecek maksimum görev/kuyruk sayısı. | `ui/index.html:197`, `ui/app.js:1508, 1714`, `core/db.py:55` |
| Hız sınırı (KB/s) | `#sSpeed` (input number) | `set.speed` | `max_speed_kb` | integer | `0` (0 = sınırsız) | Global indirme hızı üst sınırı (KB/s). | `ui/index.html:201`, `ui/app.js:1509, 1715`, `core/db.py:58` |
| Hız profili | `#sMode` (select) | `set.mode` | `hiz_profili` | string | `"normal"` | Hız profili modu (`turbo` = sınırsız, `normal` = hız sınırına uy, `snail` = salyangoz 100 KB/s). | `ui/index.html:205`, `ui/app.js:1510, 1716`, `core/db.py:62` |
| Seed oranı (torrent) | `#sRatio` (input number) | `set.ratio` | `seed_ratio` | float | `1.0` (step 0.1) | Torrent indikten sonra erişildiğinde seed paylaşımını durduracak oran. | `ui/index.html:213`, `ui/app.js:1511, 1717`, `core/db.py:72` |
| Telegram sohbet kimliği | `#sChat` (input text) | `set.chat` | `telegram_chat_id` | string | `""` | Telegram bildirimlerinin gönderileceği chat/kanal ID. | `ui/index.html:217`, `ui/app.js:1512, 1718`, `core/db.py:69` |
| Telegram bot anahtarı | `#sToken` (input text) | `set.token` | `telegram_bot_token` | string | `""` | Bildirim gönderimi için Telegram bot token'ı. | `ui/index.html:222`, `ui/app.js:1513, 1719`, `core/db.py:68` |
| Panoya kopyalanan linki yakala | `#sClip` (checkbox) | `set.clip` | `clipboard_watch` | boolean | `true` | Panoya kopyalanan desteklenen dosya URL'lerini otomatik yakalar. | `ui/index.html:225`, `ui/app.js:1514, 1720`, `core/db.py:65` |
| Tracker listesini günlük güncelle | `#sTrackers` (checkbox) | `set.trackers` | `auto_update_trackers` | boolean | `true` | Torrentler için tracker listelerinin otomatik güncellenmesini sağlar. | `ui/index.html:226`, `ui/app.js:1515, 1721`, `core/db.py:73` |
| Bitince Telegram'a haber ver | `#sNotify` (checkbox) | `set.notify` | `notify_telegram` | boolean | `false` | İndirmeler tamamlandığında Telegram botu üzerinden bildirim gönderir. | `ui/index.html:227`, `ui/app.js:1516, 1722`, `core/db.py:67` |
| Hepsi bitince bilgisayarı kapat | `#sShutdown` (checkbox) | `set.shutdown` | `shutdown_when_done` | boolean | `false` | Kuyruktaki tüm indirmeler bitince Windows'u kapatır (`shutdown`). | `ui/index.html:228`, `ui/app.js:1517, 1723`, `core/db.py:70` |
| Hepsi bitince bilgisayarı uyut | `#sSleep` (checkbox) | `set.sleep` | `sleep_when_done` | boolean | `false` | Kuyruktaki tüm indirmeler bitince bilgisayarı uyku moduna alır. | `ui/index.html:229`, `ui/app.js:1518, 1724`, `core/db.py:71` |
| İndirmeden önce kaydetme penceresi | `#sKaydet` (checkbox) | `set.kaydet` | `kaydetme_penceresi` | boolean | `true` | Tarayıcı/panodan gelen indirmelerde kaydetme penceresini (`#kaydetVeil`) açar. | `ui/index.html:230`, `ui/app.js:1520, 1725`, `core/db.py:77` |
| Dosyaları kategori klasörlerine ayır | `#sKategori` (checkbox) | `set.kategori` | `kategori_klasorleri` | boolean | `true` | Dosyaları uzantılarına göre Video, Müzik, Arşiv vb. klasörlerine yönlendirir. | `ui/index.html:231`, `ui/app.js:1521, 1726`, `core/db.py:79` |
| X ile kapatınca sistem tepsisine git | `#sTepsi` (checkbox) | `set.tepsi` | `tepsiye_kucult` | boolean | `true` | Kapatma butonuna basıldığında uygulamayı kapatmak yerine tepsiye gizler. | `ui/index.html:232`, `ui/app.js:1522, 1727`, `core/db.py:81` |
| Bilgisayar açılınca AfuDM'i başlat | `#sBaslangic` (checkbox) | `set.baslangic` | Windows Başlangıç Kısayolu | boolean | `false` | Windows Başlangıç (Startup) klasörüne kısayol ekler/kaldırır (`baslangic_ayarla`). | `ui/index.html:233`, `ui/app.js:1546, 1561` |
| .torrent ve magnet linklerini AfuDM açsın | `#sTorrent` (checkbox) | `set.torrent` | Windows Registry İlişkilendirmesi | boolean | `false` | Windows kayıt defterinde `.torrent` ve `magnet:` protokolünü AfuDM'e bağlar. | `ui/index.html:234`, `ui/app.js:1549, 1564` |
| Açılışta pencere açılmasın, tepside başlasın | `#sBasTepside` (checkbox) | `set.basTepside` | `baslangicta_tepside` | boolean | `true` | Başlangıç kısayoluna `--tepside` argümanı ekleyerek penceresiz başlatır. | `ui/index.html:235`, `ui/app.js:1523, 1561, 1728`, `core/db.py:83` |
| Telefondan bağlan (aynı Wi-Fi) | `#sTelefon` (checkbox) | `set.telefon` | `lan_erisimi` | boolean | `false` | Yerel API'yi `0.0.0.0` dinlemeye açar, QR kod ve mobil erişim URL'i üretir (`telefon_ayarla`). | `ui/index.html:236`, `ui/app.js:1584, 1592-1600`, `core/db.py:92` |
| Seed Listesi Dosya Yönetimi | `#sSeedEkle`, `#sSeedKlasor`, `#sSeedTara` | `set.seedListe`, vb. | `seed_dosyalari` | action | — | `trackers/` klasörüne dosya ekler, klasörü açar ve tracker canlılık taraması yapar. | `ui/index.html:246-248`, `ui/app.js:1358-1433` |
| Kendi tracker'ların (elle yapıştır) | `#sSeedEk` (textarea) | `set.seedEk` | `ek_trackerlar` | string | `""` | Kullanıcının girdiği özel tracker adresleri listesi. | `ui/index.html:254`, `ui/app.js:1528, 2334`, `core/db.py:85` |
| Seed listelerini günlük tara | `#sSeedOto` (checkbox) | `set.seedOto` | `tracker_otomatik_tara` | boolean | `true` | Tracker listelerini günlük olarak canlılık testine tabi tutup ölüleri eler. | `ui/index.html:260`, `ui/app.js:1403, 1729`, `core/db.py:90` |
| Telefondan uyandırma (Wake-on-LAN) | `#sMac`, `#sMacKopya` | `set.wol`, `set.kopyala` | `guc_durumu` | readonly / action | — | Ağ kartı fiziksel MAC adresini gösterir ve kopyalanmasını sağlar. | `ui/index.html:266-267`, `ui/app.js:1618-1635` |
| Telefon Bağlantı Bilgisi & QR | `#sTelefonAdres`, `#sTelefonKopya`, `#sTelefonQr` | `set.telefonAdres`, `set.telefonQr` | `telefon_durumu` | readonly / action | — | Yerel IP adresini ve telefondan okutulacak QR kod görselini gösterir. | `ui/index.html:275-278`, `ui/app.js:1586-1608` |
| Windows varsayılan uygulama ekranı | `#sVarsayilan` (button) | `set.varsayilan` | `varsayilan_uygulama_ekrani` | action | — | Windows Ayarları Varsayılan Uygulamalar sayfasını açar (`ms-settings:defaultapps`). | `ui/index.html:282`, `ui/app.js:1571-1575` |
| Uzantıyı bağla | `#pairBtn` (button) | `set.pair` | `start_pairing` | action | — | Chrome uzantısı için 120 saniyelik geçici eşleşme modunu aktif eder. | `ui/index.html:288`, `ui/app.js:1701-1705` |

---

## 4. Klavye Kısayolları ve Pencere Olayları

| Kısayol / Olay | Tetiklenen Eylem | DOSYA:SATIR |
|---|---|---|
| `Escape` | Açık olan tüm modal pencereleri (`.veil.open`), klasör seçim sözünü ve sağ tık içerik menüsünü (`#ctx`) kapatır. | `ui/app.js:565-567`, `ui/app.js:1868-1870`, `ui/app.js:2215` |
| `F5`, `Ctrl+R`, `Ctrl+P` | Engellenmiştir (`preventDefault`). Sayfanın kaza ile yeniden yüklenmesini ve yazdırma diyaloğunu engeller. | `ui/app.js:2283-2287` |
| Pencere Dışı Tıklama (`veil.click`) | Modalın karartma alanına (veil) tıklandığında ilgili modal penceresini kapatır. | `ui/app.js:562-564`, `ui/app.js:1865-1867` |
| Pencere Yeniden Boyutlandırma (`resize`) | Bant izi canvas grafiğini yeniden çizer ve açık olan sağ tık menüsünü kapatır. | `ui/app.js:110`, `ui/app.js:2141-2144`, `ui/app.js:2214` |
| `pywebviewready` Olayı | Pywebview köprüsünün hazır olduğunu işaretler, sürüm bilgisini ve bekleyen indirmeleri yükler. | `ui/app.js:2146-2158` |
