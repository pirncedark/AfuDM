# AfuDM Kullanım Rehberi (v2.7.1)

Bu kısa rehber mevcut v2.7.1 özelliklerini ve temel kullanım adımlarını anlatır. Kontrol sırasında çalışmadığı görülen özellikler açıkça işaretlenmiştir.

| ID | Ne işe yarar | Nasıl kullanılır |
|---|---|---|
|  A1 | Taşınabilir veri klasörü (data/, downloads/ uygulama yanında) işini görür. | Zip’i açıp AfuDM.exe’yi engine/ui ile birlikte çalıştırın; data/ ve downloads/ uygulama klasöründe kalır. |
|  A2 | Tek kopya kilidi (ikinci açılış öne getirir) işini görür. | **Manuel doğrulama gerekir.** AfuDM.exe’yi yeniden açın veya .torrent başlatın; çalışan pencere öne gelir. |
|  A3 | Arayüzsüz servis `afuadm server start/status/stop` işini görür. | Komut İstemi’nde `afuadm server start`, `status`, `stop` kullanın. |
|  A4 | Açılışta JS hatası yok, arayüz yükleniyor işini görür. | AfuDM.exe’yi çalıştırın; ana indirme listesi açılır. |
|  A5 | Pencere boyutu 1600x980 + DPI (#25) işini görür. | **Manuel doğrulama gerekir.** Pencereyi başlık çubuğundan büyütün; DPI’yi Windows Görüntü’den seçin. |
|  B1 | Link ekle → indir (çoklu bağlantı) işini görür. | Sol menü `+ Ekle` ile bağlantıyı yapıştırın; pano veya uzantıdan da gönderin. |
|  B2 | Duraklat / devam işini görür. | Satırdaki Duraklat’a, sonra Devam’a basın. |
|  B3 | Uygulama kapanıp açılınca devam işini görür. | **Şu an çalışmıyor.** İndirme sürerken kapatıp açın; görev session’dan devam eder. |
|  B4 | Hız sınırı + snail/normal/turbo işini görür. | Ayarlar’da hız/profil seçin; CLI `afuadm mode snail|normal|turbo`. |
|  B5 | Süresi dolan linki yenile (renew) işini görür. | CLI `afuadm renew <gid> "<yeni bağlantı>"` yazın. |
|  B6 | Checksum doğrulama işini görür. | CLI `afuadm add URL --checksum sha-256:<hex>` kullanın. |
|  B7 | Proxy (global + indirme başına) işini görür. | Ayarlar > Proxy’yi doldurun; özel indirme için `--proxy` kullanın. |
|  B8 | İndirme başına bağlantı/hız (`ayarla`) işini görür. | Satır menüsü veya `afuadm ayarla <gid> --baglanti 8 --hiz 500`. |
|  B9 | Kategori klasörleri (Video/Müzik/Belgeler) işini görür. | Ayarlar’da kategori klasörlerini açın. |
|  B10 | İndirme diyaloğu (ad, kategori, klasör ağacı, zamanla) işini görür. | Yeni linkte ad, kategori, klasör ve zaman seçip İndir’e basın. |
|  B11 | Kuyruk: aynı anda N indirme işini görür. | Ayarlar’da aynı anda çalışacak indirme sayısını seçin. |
|  B12 | Zamanlı başlatma (23:30) işini görür. | Kaydetme penceresinde saat seçin veya `--start-at "23:30"` kullanın. |
|  B13 | Pano izleme işini görür. | **Manuel doğrulama gerekir.** Ayarlar’da Pano izleme’yi açın; linki kopyalayın. |
|  B14 | Klasör / Aç düğmeleri doğru dosyayı açıyor işini görür. | **Manuel doğrulama gerekir.** Satırdaki klasör düğmesi konumu, Aç düğmesi dosyayı açar. |
|  B15 | Toplu seçim + toplu silme + Tümünü seç işini görür. | **Şu an çalışmıyor.** Liste kutularından görevleri seçip Tümünü seç/kaldır’ı kullanın. |
|  B16 | Bitenleri temizle işini görür. | **Manuel doğrulama gerekir.** Listenin üstündeki Bitenleri temizle’ye basın. |
|  B17 | Türkçe arama (I/ı/İ/i) işini görür. | Ana listedeki arama alanına dosya adını yazın. |
|  C1 | Video analiz + kalite seçimi işini görür. | `+ Ekle` ile video bağlantısı girip kaliteyi seçin. |
|  C2 | Yalnız ses (mp3) işini görür. | Video penceresinde Yalnız ses’i işaretleyin. |
|  C3 | Oynatma listesi işini görür. | **Bu kontrolde atlandı.** `+ Ekle` alanına playlist URL’si verip onaylayın. |
|  C4 | Birleştirme sonrası doğru dosya adı/boyut (#35) işini görür. | İndirme sonrası çıktı klasöründe dosya adı/boyutunu kontrol edin. |
|  C5 | ffmpeg'siz kendi muxer işini görür. | Video indirirken ffmpeg yoksa yerleşik muxer çalışır. |
|  C6 | Tarayıcı çerezi + 403 çerezsiz yedek işini görür. | Ayarlar’daki video çerezi alanından tarayıcı seçin. |
|  C7 | Altyazı / küçük resim / bölümler / SponsorBlock seçenekleri işini görür. | Video Pro panelinde altyazı/küçük resim/bölüm/SponsorBlock seçin. |
|  C8 | Yetim "aktif" kayıt açılışta toparlanıyor (#35) işini görür. | Uygulamayı yeniden açınca eski aktif video kaydı toparlanır. |
|  C9 | Video motorlarını Ayarlar’dan indirme (çekirdek pakette) işini görür. | Ayarlar > Motorlar’da yt-dlp veya ffmpeg İndir’e basın. |
|  D1 | Magnet ekle işini görür. | **Manuel doğrulama gerekir.** `+ Ekle` alanına magnet girin; metadata gelince dosyaları seçin. |
|  D2 | .torrent dosyası + dosya seçimi işini görür. | .torrent sürükleyin/çift tıklayın; listeden dosya seçin. |
|  D3 | Seed penceresi + tracker yenile + kendi tracker işini görür. | Torrent satırında Seeds’e basıp tracker yenileyin/ekleyin. |
|  D4 | Torrent penceresi kapanınca metrik isteği duruyor işini görür. | Torrent penceresini X, Escape veya arka planla kapatın. |
|  D5 | Magnet metadata gelince dosya listesi yenileniyor işini görür. | **Manuel doğrulama gerekir.** Magnet metadata gelince dosya listesi hazır olur. |
|  D6 | 250 dosya sınırı klasör satırlarını saymıyor işini görür. | Dosya seçim penceresinde daha fazlasını gösterin. |
|  D7 | `loglar(gid)` yalnız o indirmenin olaylarını döndürüyor işini görür. | Görev ayrıntılarında Olaylar sekmesini açın. |
|  E1 | 16 panel: aç / tıkla / X / ESC / arka plan / hata / tekrar aç işini görür. | **Şu an çalışmıyor.** Sol menü panellerini açıp düğme/X/Escape/arka planı deneyin. |
|  E2 | TR + EN anahtar eşitliği, i18n dışı metin yok işini görür. | **Şu an çalışmıyor.** Ayarlar > Dil’den Türkçe veya English seçin. |
|  E3 | UI kapısı: 1280x720 / 1366x768 / 1920x1080, DPI 100/150/200 işini görür. | Pencere boyutunu ve Windows DPI oranını değiştirin. |
|  E4 | Satır hover titremesi yok (#25) işini görür. | Fareyi ana listede indirme satırlarının üzerinde gezdirin. |
|  E5 | Pencere düğmeleri sürüklenmiyor (#25) işini görür. | Başlık çubuğu küçült/büyüt/kapat düğmelerini kullanın. |
|  E6 | Ölü tıklama hedefi = 0, uncaught JS hata = 0 işini görür. | **Şu an çalışmıyor.** Panellerde görünen düğmelere basın; JS hataları izlenir. |
|  F1 | Ağda paylaş: LAN linki (http://http:// yok) işini görür. | Satır menüsünde Ağda Paylaş’ı seçin; link/QR alın. |
|  F2 | QR kod işini görür. | Paylaşım penceresindeki QR’ı telefondan okutun. |
|  F3 | SMB paylaşımı açılıyor VE silinince kaldırılıyor işini görür. | **Şu an çalışmıyor.** Paylaşım Merkezi’nde dosya seçip paylaşın, sonra Sil’e basın. |
|  F4 | Cloudflare quick tunnel yalnız /s/ açıyor işini görür. | Paylaşım Merkezi’nde İnternetten paylaş’ı seçin. |
|  F5 | Paylaşım modalı kapanıyor, çift id yok işini görür. | Paylaşım penceresini X/Escape/arka planla kapatın. |
|  F6 | Paylaşım listesinde XSS yok işini görür. | **Şu an çalışmıyor.** Paylaşım Merkezi dosya listesi ad ve bağlantı gösterir. |
|  G1 | `/m` mobil panel işini görür. | **Manuel doğrulama gerekir.** Aynı Wi-Fi’de telefonda `http://PC-adresi:port/m` açın. |
|  G2 | PWA işini görür. | Mobil panelde tarayıcı menüsünden Ana ekrana ekle’yi seçin. |
|  G3 | Telefona indir `/indir` (kök dışı yol reddi) işini görür. | **Şu an çalışmıyor.** Mobil panelde görevden Telefona indir’i seçin. |
|  G4 | LAN eşleştirme `/pair` işini görür. | **Şu an çalışmıyor.** Ayarlar’da Telefon bağlantısını açıp QR eşleştirmesi başlatın. |
|  H1 | Uzantı sürümü = core/surum.py işini görür. | Sürümü Ayarlar’da ve Chrome uzantı ayrıntılarında görün. |
|  H2 | İndirmeleri devralma + çerez gönderme işini görür. | **Manuel doğrulama gerekir.** Uzantıyı ekleyin; tarayıcı indirmesini AfuDM devralır. |
|  H3 | Video paneli (HLS/DASH kalite) işini görür. | **Manuel doğrulama gerekir.** Video üstündeki AfuDM düğmesine basıp kalite seçin. |
|  H4 | Başlık politikası (tehlikeli başlık reddi) işini görür. | Uzantı video başlıklarını filtreler; Chrome’da etkin tutun. |
|  H5 | Sağ tık menüsü işini görür. | **Manuel doğrulama gerekir.** Sayfada sağ tıklayıp AfuDM indirme menüsünü seçin. |
|  H6 | "Chrome’a ekle" otomatik kurulum işini görür. | **Manuel doğrulama gerekir.** Sol menü Chrome’a ekle > Otomatik ekle’yi seçin. |
|  I1 | list / status / add / info / watch işini görür. | Komut İstemi’nde `afuadm list/status/add/info/watch` çalıştırın. |
|  I2 | `--json` yalnız JSON, çıkış kodları 0/2/3/4/130 işini görür. | `afuadm status --json` gibi komuta `--json` ekleyin. |
|  I3 | Başlatma yarışı kilidi işini görür. | İki terminalde aynı anda `afuadm server start` yazın. |
|  J1 | Web panel erişim anahtarı (admin / salt-okur), döndürme işini görür. | Sunucu panelinde Anahtar oluştur’dan rol seçin; Döndür ile yenileyin. |
|  J2 | API token zorunlu, token loglara/URL’ye düşmüyor işini görür. | **Şu an çalışmıyor.** Sunucu panelinde anahtar oluşturup isteklerde başlıkla gönderin. |
|  J3 | `/add` hedef klasör kökü dışına çıkamıyor işini görür. | **Şu an çalışmıyor.** Yönetim API `/add` isteğine URL ve hedef klasör gönderin. |
|  J4 | CORS dar işini görür. | **Şu an çalışmıyor.** Yönetim paneline izin verilen kaynaktan başlık anahtarıyla bağlanın. |
|  K1 | Kurallar motoru (hedef klasör, hız, bölme) işini görür. | Sol menü Kurallar > Yeni kural’dan koşul/eylem seçip kaydedin. |
|  K2 | Bitince Telegram bildirimi / bilgisayarı kapat işini görür. | Ayarlar’da Telegram veya bitince kapatma seçeneklerini düzenleyin. |
|  K3 | Eklentiler (sha256 doğrulama, onay) işini görür. | Eklentiler panelinden .afup seçin; izinleri onaylayın. |
|  L1 | .torrent / magnet ilişkilendirme + eski kaydı yedekle/geri yükle işini görür. | **Manuel doğrulama gerekir.** Ayarlar’da ilişkilendirmeyi seçin; Windows varsayılan uygulamalardan AfuDM’i belirleyin. |
|  L2 | Tepsi, Windows ile başlat işini görür. | Ayarlar’da tepsi ve Windows başlangıç seçeneklerini kullanın. |
|  M1 | Yedek al / geri yükle, sonra kapalı Store kullanılmıyor işini görür. | **Şu an çalışmıyor.** Ayarlar > Yedek’ten alın/listeden geri yükleyin; uygulamayı yeniden başlatın. |
|  M2 | DB şeması 0→10 ve 3→10 geçişi (idempotent) işini görür. | **Şu an çalışmıyor.** DB geçişi açılışta otomatik yapılır. |
|  M3 | Tanılama raporu (tani.bat) işini görür. | **Manuel doğrulama gerekir.** AfuDM klasöründe `tani.bat` çalıştırın. |
|  M4 | Silme: kayıt / dosya / üst klasör, yetim temizlik işini görür. | **Şu an çalışmıyor.** Görev satırında Kaldır’a basıp kayıt/dosya/üst klasör seçimini onaylayın. |
|  N1 | Paket kendi başına çalışıyor (video/ dahil) işini görür. | Zip’i açıp AfuDM.exe veya `afuadm server start` çalıştırın. |
|  N2 | exe güncel kaynaktan derleniyor (#26) işini görür. | Derleme PyInstaller komutuyla yapılır. |
|  N3 | Açık exe varken paketleyici hiçbir şey silmiyor işini görür. | `python paketle.py` çalıştırın; açık exe kilitliyse işlem durur. |
|  N4 | Sürüm notu kuralı (İngilizce üst) işini görür. | Sürüm notunu İngilizce bölümle başlatın. |
