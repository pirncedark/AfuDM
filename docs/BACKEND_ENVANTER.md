# AfuDM Backend Envanteri (v1.5.0)

Bu belge `app.py`, `core/`, `api/` ve `video/` modüllerindeki tüm backend özelliklerini, yapılandırma anahtarlarını, RPC ve HTTP uç noktalarını ve çalışma zamanı davranışlarını DOSYA:SATIR kanıtlarıyla listeler.

---

## 1. Tüm Ayar Anahtarları (Config / Settings / Varsayılan Değerler)

Tüm varsayılan ayarlar `core/db.py:51-101` (`DEFAULTS`) sözlüğünde tanımlanır ve SQLite `settings` tablosuna JSON formatında saklanır (`core/db.py:38-41`, `core/db.py:156-160`).

| Özellik / Ayar | Anahtar adı | Tip / Varsayılan | Ne yapar | DOSYA:SATIR |
|---|---|---|---|---|
| Arayüz Dili | `language` | `str` / `"auto"` | Uygulama dilini belirler (`"auto"`, `"tr"`, `"en"`). `"auto"` seçeneğinde Windows UI diline (`GetUserDefaultUILanguage`) bakar. | `core/db.py:53`<br>`core/lang.py:70-97`<br>`core/manager.py:1052` |
| İndirme Klasörü | `download_dir` | `str` / `""` | Genel indirme hedef dizini. Boş ise taşınabilir varsayılan `downloads/` klasörüdür. Değişince aria2'ye anında `dir` global seçeneği uygulanır. | `core/db.py:54`<br>`core/manager.py:65-66`<br>`core/manager.py:206-212`<br>`core/paths.py:63-65` |
| Eşzamanlı İndirme Limiti | `max_concurrent` | `int` / `5` | Aynı anda aktif olarak indirilebilecek maksimum indirme sayısı. aria2 `max-concurrent-downloads` seçeneğine yazılır. | `core/db.py:55`<br>`core/manager.py:125`<br>`core/daemon.py:68` |
| Bağlantı Parçalama Sayısı | `split` | `int` / `64` | Bir dosya indirilirken açılabilecek maksimum parça sayısı. aria2 `split` seçeneğine yazılır. | `core/db.py:56`<br>`core/manager.py:126`<br>`core/daemon.py:66` |
| Sunucu Başına Bağlantı Limiti | `max_conn_per_server` | `int` / `16` | Tek bir sunucuya açılabilecek azami TCP bağlantı sayısı. aria2 `max-connection-per-server` seçeneğine yazılır. | `core/db.py:57`<br>`core/manager.py:127`<br>`core/daemon.py:65` |
| Azami Hız Limiti (Normal) | `max_speed_kb` | `int` / `0` | Normal profil etkinken toplam azami indirme hızı (KB/s). `0` sınırsız demektir. aria2 `max-overall-download-limit` seçeneğine aktarılır. | `core/db.py:58`<br>`core/manager.py:119`<br>`core/manager.py:128` |
| Hız Profili Modu | `hiz_profili` | `str` / `"normal"` | Aktif hız profili (`"normal"`, `"turbo"`, `"snail"`). `turbo` sınırı 0 yapar; `snail` ise `snail_speed_kb` değerini uygular. | `core/db.py:62`<br>`core/manager.py:39`<br>`core/manager.py:114-119`<br>`core/manager.py:136-160` |
| Salyangoz Hızı Limiti | `snail_speed_kb` | `int` / `100` | Snail (arka plan/oyun) profilindeki azami indirme hızı (KB/s). | `core/db.py:63`<br>`core/manager.py:117-118` |
| Pano İzleyici Açık/Kapalı | `clipboard_watch` | `bool` / `True` | Windows panosunu izleyip indirilebilir bağlantı tespit edildiğinde yakalama penceresini tetikler. | `core/db.py:64`<br>`app.py:1042-1048`<br>`core/clipboard.py:61-94` |
| Pano Takip Uzantıları | `clipboard_exts` | `str` / `"zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent"` | Panoda algılanacak dosya uzantılarının virgülle ayrılmış listesi. | `core/db.py:65`<br>`app.py:1047`<br>`core/clipboard.py:50-53` |
| Telegram Bildirimi | `notify_telegram` | `bool` / `False` | İndirme tamamlandığında Telegram botu üzerinden bildirim mesajı gönderilmesini sağlar. | `core/db.py:66`<br>`core/manager.py:1526-1534` |
| Telegram Bot Tokeni | `telegram_bot_token` | `str` / `""` | Telegram bildirimleri için kullanılan Bot API tokeni. Boşsa `TELEGRAM_BOT_TOKEN` ortam değişkenine bakar. | `core/db.py:67`<br>`core/manager.py:1566-1568` |
| Telegram Sohbet Kimliği | `telegram_chat_id` | `str` / `""` | Telegram bildirimlerinin gönderileceği `chat_id`. | `core/db.py:68`<br>`core/manager.py:1569-1570` |
| İndirmeler Bitince Kapat | `shutdown_when_done` | `bool` / `False` | Tüm aktif/bekleyen indirmeler tamamlandığında bilgisayarı 60 saniye geri sayımla kapatır (`shutdown /s /t 60`). | `core/db.py:69`<br>`core/manager.py:1535-1540` |
| İndirmeler Bitince Uyut | `sleep_when_done` | `bool` / `False` | Tüm indirmeler bitince bilgisayarı 20 saniye sonra uyku (S3) moduna geçirir. Windows şifresi gerektirmeden uyanabilir. | `core/db.py:71`<br>`core/manager.py:1541-1556`<br>`core/guc.py:24-35` |
| Seed Oranı (Ratio) | `seed_ratio` | `float` / `1.0` | Torrent tamamlandıktan sonra aria2'nin gönderme (upload) oran hedefi. aria2 `seed-ratio` seçeneğine yazılır. | `core/db.py:72`<br>`core/manager.py:129`<br>`core/daemon.py:92` |
| Otomatik Tracker Güncelleme | `auto_update_trackers` | `bool` / `True` | Başlangıçta ve 24 saatte bir uzak depolardan güncel genel tracker listesini indirip aria2 havuzuna ekler. | `core/db.py:73`<br>`core/manager.py:86-87`<br>`core/manager.py:1495-1502` |
| Varsayılan Video Kalitesi | `video_quality` | `str` / `"best"` | Video indirmeleri için varsayılan yt-dlp kalite seçimi (`"best"`, `"1080p"`, `"720p"`, `"480p"`, `"360p"`). | `core/db.py:74`<br>`core/manager.py:366`<br>`video/ytdlp.py:29-38` |
| Yerel API Portu | `api_port` | `int` / `6811` | Yerel HTTP API'nin (`LocalAPI`) son açıldığı TCP port numarası. | `core/db.py:75`<br>`app.py:25`<br>`app.py:939-943` |
| Kaydetme Penceresi | `kaydetme_penceresi` | `bool` / `True` | Tarayıcı uzantısından veya CLI'dan gelen `interactive` indirme isteklerinde doğrudan indirmek yerine onay penceresini açar. | `core/db.py:77`<br>`api/server.py:243-247`<br>`app.py:324-333` |
| Kategori Klasörleri | `kategori_klasorleri` | `bool` / `True` | Dosyaları türlerine göre `downloads/Video`, `downloads/Muzik`, `downloads/Programlar`, `downloads/Belgeler`, `downloads/Arsivler`, `downloads/Genel` alt klasörlerine yönlendirir. | `core/db.py:79`<br>`core/kaydet.py:30-41`<br>`core/kaydet.py:66-67`<br>`app.py:136-143` |
| Tepsiye Küçült | `tepsiye_kucult` | `bool` / `True` | Pencere kapatma (X) düğmesine basıldığında veya Alt+F4 yapıldığında uygulamayı kapatmayıp sistem tepsisine gizler. | `core/db.py:81`<br>`app.py:734-746`<br>`app.py:1006-1010`<br>`core/pencere.py:169-199` |
| Başlangıçta Tepside Başla | `baslangicta_tepside` | `bool` / `True` | Windows başlangıç klasörüne eklenen kısayolun `--tepside` argümanıyla gizli başlamasını kontrol eder. | `core/db.py:83`<br>`app.py:381-386`<br>`core/baslangic.py:77-92` |
| Ek Tracker Listesi | `ek_trackerlar` | `str` / `""` | Kullanıcının Ayarlar panelinden elle yapıştırdığı ek BitTorrent tracker adresleri (satır satır). | `core/db.py:85`<br>`app.py:513-518`<br>`core/trackers.py:179-201` |
| Canlı Tracker Listesi | `canli_trackerlar` | `str` / `""` | Otomatik sağlık taraması sonucu canlı olduğu teyit edilen tracker adresleri. | `core/db.py:87`<br>`core/tracker_saglik.py:288-304`<br>`core/manager.py:842` |
| Tracker Tarama Zamanı | `tracker_tarama_zamani` | `float` / `0` | En son yapılan tracker sağlık taramasının epoch zaman damgası. | `core/db.py:88`<br>`core/tracker_saglik.py:300`<br>`core/tracker_saglik.py:307-311` |
| Tracker Tarama Özeti | `tracker_tarama_ozeti` | `dict` / `{}` | Son tracker taramasına ait istatistik özeti (canlı, sessiz, hatalı, süre, yanıt süreleri). | `core/db.py:89`<br>`core/tracker_saglik.py:301`<br>`core/manager.py:844` |
| Tracker Otomatik Tara | `tracker_otomatik_tara` | `bool` / `True` | Günde bir kez `trackers/` klasöründeki tracker'ları otomatik olarak UDP/HTTP scrape ile test eder. | `core/db.py:91`<br>`core/manager.py:1504-1508` |
| LAN Erişimi (Telefon Bağlantısı) | `lan_erisimi` | `bool` / `False` | Yerel API'nin `0.0.0.0` IP'sine bağlanarak yerel ağdaki telefon arayüzüne (`/m`) izin vermesini sağlar. | `core/db.py:93`<br>`app.py:521-531`<br>`app.py:555-570`<br>`api/server.py:370-375` |
| Ağ Konumları (NAS / UNC) | `ag_konumlari` | `str` / `""` | Kaydetme menüsünde gösterilen doğrulanmış UNC ağ paylaşımları (`\\sunucu\paylasim`, her satırda bir yol). | `core/db.py:95`<br>`app.py:287-303`<br>`core/kaydet.py:159-193` |
| Genel Proxy | `proxy` | `str` / `""` | Tüm indirmeler için kullanılacak varsayılan HTTP/SOCKS proxy adresi (`tip://kullanici:sifre@host:port`). | `core/db.py:99`<br>`core/manager.py:429-432`<br>`core/proxy.py:73-116` |
| Sistem Proxy Kullan | `system_proxy` | `bool` / `False` | Windows Internet Settings (`HKCU\Software\...\Internet Settings`) üzerindeki sistem proxy'sinin otomatik kullanılması. | `core/db.py:100`<br>`core/manager.py:425-428`<br>`core/proxy.py:31-70` |
| Tepsi Bildirimi Yapıldı | `tepsi_bildirimi_yapildi` | `bool` / Yok (Dinamik) | Windows 11'de simge ilk kez tepsiye indiğinde kullanıcının bilgilendirildiğini işaretleyen tek seferlik bayrak. | `app.py:986-988` |

---

## 2. Tüm RPC / Arayüz API Uç Noktaları (`app.py` `Api` Sınıfı)

Bu metotlar PyWebView köprüsü üzerinden UI (`window.pywebview.api.*`) tarafından doğrudan çağrılır ve JSON uyumlu sözlük döner (`app.py:52-798`).

| Özellik / Ayar | Fonksiyon / Metot Adı | Parametreler | Ne Yapar | DOSYA:SATIR |
|---|---|---|---|---|
| Durum Anlık Görüntüsü | `snapshot()` | — | Aktif, duraklatılmış ve geçmiş indirmeleri, küresel hız istatistiklerini, motor durumunu ve çözülmüş dili döndürür. Pencere başlığını dile göre senkronize eder. | `app.py:74-77` |
| Motor Durumları | `motor_durumu()` | — | `aria2c`, `yt-dlp` ve `ffmpeg` motorlarının kurulu/eksik olup olmadığını ve arka planda devam eden motor indirme ilerlemelerini döndürür. | `app.py:93-99` |
| Motor İndir | `motor_indir(ad)` | `ad: str` | İsteğe bağlı motoru (`yt-dlp` veya `ffmpeg`) arka plan iş parçacığında indirir, zip ise açar ve `engine/` içine yerleştirir. | `app.py:101-121` |
| Yerel API Bilgisi | `api_info()` | — | Yerel API'nin aktif portunu ve kimlik doğrulama tokenini döndürür. | `app.py:123-124` |
| Eş Listesi (Torrent) | `peers(gid)` | `gid: str` | Belirtilen torrent indirmesi için aria2'den canlı peer/seed IP, port, hız ve istemci bilgilerini döndürür. | `app.py:126-127` |
| Eşleştirme Aç | `start_pairing(seconds=120)` | `seconds: int = 120` | Tarayıcı uzantısının tokeni otomatik çekebilmesi için `/pair` uç noktasını belirtilen süre boyunca açar. | `app.py:129-133` |
| Kaydetme Bilgisi Getir | `kaydet_bilgi(url)` | `url: str` | Link türü, tahmini dosya adı, kategori, varsayılan indirme klasörü ve kategori klasör eşlemelerini döndürür. | `app.py:144-157` |
| Bağlantı Bilgisi Sondajla | `probe_link(url)` | `url: str` | HTTP HEAD ve Range 0-0 GET isteğiyle dosya adı (`Content-Disposition`), MIME türü, boyut ve devam edebilirlik (`resumable`) bilgilerini çeker. | `app.py:159-175` |
| LinkGrabber Metin Analizi | `linkgrabber_analiz(metin, filtre=None)` | `metin: str`, `filtre: dict \| None = None` | Ham metindeki tüm URL'leri ayıklar, normalleştirir, tekilleştirir, tür/domain filtrelerini uygular. | `app.py:177-191` |
| LinkGrabber Canlı Süzme | `linkgrabber_suz(ogeler, filtre=None)` | `ogeler: list[dict]`, `filtre: dict \| None = None` | Panel üzerinde arama (wildcard), tür, domain, min/max boyut kriterlerine uyan öğelerin indekslerini ve mevcut domainleri döndürür. | `app.py:193-220` |
| LinkGrabber İptal | `linkgrabber_iptal()` | — | Devam eden toplu lazy probe (sondaj) iş parçacıklarını durdurur. | `app.py:222-226` |
| LinkGrabber Önceki Kayıtlar | `linkgrabber_onceki(urller)` | `urller: list[str]` | Verilen linklerden daha önce indirilmiş veya kuyrukta olanları tespit edip arayüzde uyarı gösterilmesini sağlar. | `app.py:228-236` |
| LinkGrabber Toplu Sondaj | `linkgrabber_probe(urller, es_zamanli=8)` | `urller: list[str]`, `es_zamanli: int = 8` | Seçili URL'lerin dosya adı, boyutu ve MIME türünü eşzamanlı iş parçacıklarıyla arka planda sorgular. | `app.py:238-264` |
| LinkGrabber Toplu Ekle | `linkgrabber_ekle(urller, secim=None)` | `urller: list[str]`, `secim: dict \| None = None` | LinkGrabber panelinden seçilen bağlantıları topluca indirme yöneticisine ekler. | `app.py:266-280` |
| Klasör Kısayolları | `klasor_kisayollar()` | — | İndirme klasörü, Masaüstü, Belgeler, Videolar, Müzik ve kayıtlı ağ konumlarını listeler. | `app.py:282-285` |
| Ağ Konumu Ekle | `ag_konumu_ekle(yol)` | `yol: str` | Modem/NAS SMB/UNC yolunu (`\\sunucu\paylasim`) erişimini doğrulayarak ayarlar listesine ekler. | `app.py:287-297` |
| Ağ Konumu Sil | `ag_konumu_sil(yol)` | `yol: str` | Kayıtlı UNC ağ konumunu listeden kaldırır. | `app.py:299-303` |
| Alt Klasörleri Listele | `klasor_alt(yol)` | `yol: str` | Belirtilen klasörün altındaki dizinleri ağaç görünümü için listeler. | `app.py:305-309` |
| Yeni Klasör Oluştur | `klasor_yeni(ust, ad)` | `ust: str`, `ad: str` | Belirtilen dizin altında güvenli ad kurallarına uyarak yeni bir klasör açar. | `app.py:311-315` |
| Klasör Gözat İletişim Kutusu | `klasor_gozat(baslangic="")` | `baslangic: str = ""` | Yerel Windows klasör seçme iletişim kutusunu (`FOLDER_DIALOG`) açar ve seçilen yolu döndürür. | `app.py:317-322` |
| Tarayıcıdan İstek Beklet | `tarayicidan_sor(istek)` | `istek: dict` | Uzantıdan gelen etkileşimli indirme isteğini bekleyenler listesine ekler, ana pencereyi öne getirir. | `app.py:324-333` |
| Bekleyen İstekler Listesi | `bekleyen_listesi()` | — | Kullanıcı onayı bekleyen tarayıcı indirme isteklerini listeler. | `app.py:335-336` |
| Bekleyen İsteği İptal Et | `bekleyen_iptal(kimlik)` | `kimlik: int` | Bekleyen isteği kuyruktan siler ve indirmeyi reddeder. | `app.py:338-340` |
| Bekleyen İsteği Onayla | `bekleyen_onayla(kimlik, secim)` | `kimlik: int`, `secim: dict` | Bekleyen isteği kullanıcının seçtiği klasör, dosya adı, kalite ve zamanlamayla indirmeye başlatır. | `app.py:342-366` |
| Sistem Başlangıç ve Torrent Durumu | `sistem_durumu()` | — | Windows Başlangıç klasöründe kısayolun olup olmadığını ve `.torrent`/`magnet:` kayıt defteri ilişkilerini sorgular. | `app.py:371-379` |
| Başlangıç Kısayolu Ayarla | `baslangic_ayarla(acik, tepside=True)` | `acik: bool`, `tepside: bool = True` | Windows Başlangıç klasörüne `--tepside` argümanlı kısayol ekler veya kaldırır. | `app.py:381-390` |
| Varsayılan Uygulamalar Ekranı | `varsayilan_uygulama_ekrani()` | — | Windows `ms-settings:defaultapps` ayar sayfasını açar. | `app.py:392-402` |
| Torrent/Magnet İlişkilendir | `torrent_iliskilendir(acik)` | `acik: bool` | `HKCU\Software\Classes` altında `.torrent` ve `magnet:` protokolünü AfuDM ile eşler ya da kaldırır. | `app.py:404-409` |
| Seed Bilgisi | `seed_bilgi(gid)` | `gid: str` | Torrent için seed/peer sayıları, tracker havuzu, liste yaşı ve DHT durumunu döndürür. | `app.py:412-413` |
| Seed Yeniden Duyur / Tazele | `seed_tazele(gid)` | `gid: str` | Güncel tracker'ları aria2'ye uygulayıp torrenti kaldığı yerden aynı dizine yeniden duyurarak ekler. | `app.py:415-416` |
| Torrent Ön Ekle | `torrent_on_ekle(source)` | `source: str` | Dosya seçimi yapabilmek için torrenti aria2'ye duraklatılmış olarak ön-ekler (`pause=true`, `pause-metadata=false`). | `app.py:417-423` |
| Torrent Ön İptal | `torrent_on_iptal(gid)` | `gid: str` | Ön-eklenmiş ancak vazgeçilmiş torrenti ve meta verisini aria2'den temizler. | `app.py:425-431` |
| Torrent Dosya Ağacı | `torrent_dosyalari(gid)` | `gid: str` | Torrentin içindeki dosyaları, boyutlarını, tamamlanma yüzdelerini ve kullanıcı seçim durumlarını listeler. | `app.py:433-447` |
| Torrent Dosya Seçimi Ayarla | `torrent_secimi_ayarla(gid, indeksler)` | `gid: str`, `indeksler: list[int]` | Torrent içindeki seçilen dosyaları aria2 `select-file` seçeneğiyle canlı uygular ve veritabanına kaydeder. | `app.py:449-454` |
| Torrent Canlı Metrikleri | `torrent_metrikleri(gid)` | `gid: str` | Torrent için yükleme/indirme hızları, tamamlanan miktar, upload miktarı, ratio ve tracker sayılarını döndürür. | `app.py:455-469` |
| Olay Günlükleri | `loglar(gid="")` | `gid: str = ""` | Veritabanındaki `events` tablosundan son olay ve hata kayıtlarını döndürür. | `app.py:471-477` |
| Tracker Sağlık Taraması Yap | `tracker_tara(gid="")` | `gid: str = ""` | trackers/ klasöründeki tracker'ları UDP/HTTP scrape ile test eder ve canlı olanları aria2'ye anında uygular. | `app.py:481-483` |
| Tracker Klasörünü Aç | `tracker_klasoru_ac()` | — | `trackers/` klasörünü Windows Gezgini'nde açar. | `app.py:485-491` |
| Seed Dosyaları Listesi | `seed_dosyalari()` | — | `trackers/` altındaki `.txt` dosyalarını, tracker sayılarını ve son tarama durumunu listeler. | `app.py:493-495` |
| Seed Dosyası Ekle | `seed_dosya_ekle(yol="")` | `yol: str = ""` | Kullanıcının seçtiği `.txt` tracker dosyasını `trackers/` dizinine kopyalar ve taramayı tetikler. | `app.py:497-508` |
| Seed Dosyası Sil | `seed_dosya_sil(ad)` | `ad: str` | `trackers/` klasöründeki bir `.txt` dosyasını siler ve taramayı yeniler. | `app.py:510-511` |
| Elle Eklenen Tracker'ları Kaydet | `seed_tracker_kaydet(metin)` | `metin: str` | Kullanıcının girdiği tracker metnini ayıklar, doğrular ve `ek_trackerlar` ayarına yazar. | `app.py:513-518` |
| Mobil Arayüz Durumu | `telefon_durumu()` | — | Yerel ağ erişiminin açık olup olmadığını, mobil IP adresini, QR kodunu (data URI) ve API portunu döndürür. | `app.py:521-531` |
| Mobil Arayüz Ayarla | `telefon_ayarla(acik)` | `acik: bool` | `lan_erisimi` ayarını değiştirir ve HTTP sunucusunu `127.0.0.1` ya da `0.0.0.0` ile yeniden başlatır. | `app.py:555-570` |
| Güç Durumu | `guc_durumu()` | — | Aktif ağ kartı adı, MAC adresi, Wake-on-LAN desteği ve uyandırmaya hazır olup olmadığını döndürür. | `app.py:572-577` |
| Şimdi Uyut | `simdi_uyu()` | — | Bilgisayarı test amacıyla anında S3 uyku moduna geçirir (`PowrProf.SetSuspendState`). | `app.py:579-581` |
| Link Ekle | `add_links(payload)` | `payload: dict` | Birden çok URL'yi (HTTP, Video, Torrent) hedef klasör, dosya adı, kalite ve zamanlama seçenekleriyle kuyruğa ekler. | `app.py:583-613` |
| İndirme Kontrolü | `control(action, gid, delete_files=False)` | `action: str`, `gid: str`, `delete_files: bool = False` | İndirmeyi duraklatır (`pause`), sürdürür (`resume`), siler (`remove`), tümünü duraklatır/sürdürür (`pause_all`, `resume_all`). | `app.py:616-632` |
| Tekrar Dene | `retry(row_id)` | `row_id: int` | Hata almış veya durmuş bir indirmeyi sıfırlayıp yeniden başlatır. | `app.py:634-638` |
| Tamamlananları Temizle | `clear_finished()` | — | Durumu `complete`, `removed` veya `error` olan indirme kayıtlarını veritabanından temizler. | `app.py:640-641` |
| Ayarları Kaydet | `settings_save(payload)` | `payload: dict` | Değiştirilen ayarları veritabanına yazar ve aria2'ye anında uygular. | `app.py:644-649` |
| İndirme Klasörünü Aç | `open_download_dir()` | — | Genel indirme klasörünü Windows Gezgini'nde açar. | `app.py:652-654` |
| İndirilen Öğenin Klasörünü Aç | `open_item_folder(gid)` | `gid: str` | İndirilen dosyanın bulunduğu klasörü Windows Gezgini'nde dosyayı seçili olarak açar (`explorer /select,`). | `app.py:656-663` |
| İndirilen Dosyayı Aç | `dosya_ac(gid)` | `gid: str` | İndirilen dosyayı Windows varsayılan uygulamasıyla çalıştırır/açar (`os.startfile`). | `app.py:665-681` |
| İndirilen Öğenin Yolu | `item_yolu(gid)` | `gid: str` | Sağ tık menüsü için satırın kaynak URL'si, hedef klasörü, dosya adı ve tam disk yolunu verir. | `app.py:683-692` |
| Panoya Kopyala | `panoya_kopyala(metin="")` | `metin: str = ""` | Verilen metni Windows panosuna (`clip` komutu aracılığıyla güvenle) yazar. | `app.py:694-703` |
| Panodan Oku | `panodan_oku()` | — | Windows panosundaki geçerli metni ctypes (`user32.GetClipboardData`) ile okur. | `app.py:705-714` |
| Pencere Küçült | `pencere_kucult()` | — | Ana uygulama penceresini simge durumuna küçültür. | `app.py:717-720` |
| Pencere Büyüt/Geri Yükle | `pencere_buyut()` | — | Pencereyi ekranı kapla (maximize) veya normal boyuta geri getir (restore) durumları arasında değiştirir. | `app.py:722-728` |
| Pencere Kapat | `pencere_kapat()` | — | `tepsiye_kucult` etkinse pencereyi gizler ve tepsi bildirimi verir; değilse uygulamayı tamamen kapatır. | `app.py:730-746` |
| Pencere Durumu | `pencere_durumu()` | — | Çerçevesiz özel başlık çubuğunun aktifliğini ve pencerenin tam ekran olup olmadığını döndürür. | `app.py:748-753` |
| Pencere Kenarından Boyutlandırma | `pencere_kenar(kenar)` | `kenar: str` | Çerçevesiz pencerede üst/sol/sağ kenarlardan yerel Windows boyutlandırma döngüsünü başlatır. | `app.py:755-756` |
| Chrome Uzantı Durumu | `chrome_durum()` | — | Chrome'un kurulu olup olmadığını, uzantı klasör yolunu ve `chrome://extensions/` adresini döndürür. | `app.py:759-765` |
| Chrome Kurulumunu Hazırla | `chrome_hazirla()` | — | Eşleştirme penceresini 10 dakika boyunca açar ve Chrome durumunu döndürür. | `app.py:767-772` |
| Chrome Otomatik Kurulum | `chrome_otomatik()` | — | UI Automation betiğiyle Chrome'u açıp geliştirici modunu etkinleştirerek uzantıyı otomatik yüklemeyi dener. | `app.py:774-778` |
| Chrome Kurulum İlerlemesi | `chrome_ilerleme()` | — | Otomatik uzantı ekleme sürecinin adımını ve uzantının bağlanıp bağlanmadığını izler. | `app.py:780-783` |
| Chrome Kurulum Bilgisi Kopyala | `chrome_kopyala(ne)` | `ne: str` | `chrome://extensions/` adresini veya uzantı klasörünün disk yolunu panoya kopyalar. | `app.py:785-787` |
| Chrome'u Aç | `chrome_ac()` | — | Chrome'u `about:blank` sekmesiyle başlatır ve adresi panoya kopyalar. | `app.py:789-792` |
| Video Bilgisi Sondajla | `probe(url)` | `url: str` | `yt-dlp` üzerinden video başlığı, süresi, küçük resmi ve format listesini çeker. | `app.py:794-798` |

---

## 3. Tüm Yerel HTTP API Uç Noktaları (`api/server.py` `LocalAPI` / `_Handler`)

Yerel HTTP API (`127.0.0.1:6811` veya `0.0.0.0:6811`), tarayıcı uzantısı, CLI (`afuadm`), mobil arayüz ve diğer betikler için REST/JSON arayüzü sunar (`api/server.py:67-345`).

| Özellik / Ayar | HTTP Metodu & Yol | Parametreler (Body / Query) | Ne Yapar | DOSYA:SATIR |
|---|---|---|---|---|
| Kimlik / Sağlık Kontrolü | `GET /ping` | — *(Token Gerekmez)* | Uygulama kimliğini (`{"ok": true, "app": "AfuDM"}`) döndürür. CLI ve uzantı portun AfuDM'e ait olduğunu buradan doğrular. | `api/server.py:148-152` |
| Mobil Kategori Listesi | `GET /klasorler` | `?token=...` veya `X-AfuDM-Token` | Mobil arayüz için ana indirme klasörünü ve kategori klasör listesini döndürür. | `api/server.py:153-166` |
| Mobil Arayüz Sayfası | `GET /m` veya `/m/` | — *(Token Gerekmez)* | Telefon web arayüzünü (`ui/mobil.html`) tek dosya HTML olarak döndürür. | `api/server.py:167-172` |
| Pencereyi Öne Getir | `GET /show` | `X-AfuDM-Token` | Çalışan AfuDM penceresini simge durumundan çıkarır ve öne getirir. İkinci bir kopya açıldığında kullanılır. | `api/server.py:173-178` |
| Uzantı Eşleştirme | `GET /pair` | — *(Eşleştirme Penceresi Açıkken)* | `pair_until` süresi dolmamışsa API tokenini uzantıya teslim eder. Süre dolduysa 403 `ESLESME_KAPALI` döner. | `api/server.py:179-190` |
| Durum Anlık Görüntüsü | `GET /snapshot` | `X-AfuDM-Token` | Tüm aktif/bekleyen/tamamlanan indirmeleri, hızları ve ayarları döndürür. | `api/server.py:194-195` |
| Video Bilgisi Sorgula | `GET /probe` | `?url=...` & `X-AfuDM-Token` | Video URL'sinin format ve meta verilerini yt-dlp ile sorgular. | `api/server.py:196-202` |
| Eşleri Listele | `GET /peers` | `?gid=...` & `X-AfuDM-Token` | Torrent indirmesinin canlı peer/seed bağlantılarını döndürür. | `api/server.py:203-205` |
| Sistem Yetenekleri | `GET /capabilities` | `X-AfuDM-Token` | Sürüm, uzantı sürümü, motor durumları, desteklenen protokoller, özellik listesi ve girdi sınırlarını döndürür. | `api/server.py:206-229` |
| Yeni İndirme Ekle | `POST /add` | JSON: `url`/`source`, `kind`, `dest_dir`, `kategori`, `quality`, `audio_only`, `playlist`, `headers`, `filename`, `cookies`, `user_agent`, `title`, `start_at`, `proxy`, `checksum`, `interactive` | Yeni bir indirme başlatır veya zamanlar. `interactive: true` ve ayar açıksa indirmeyi bekletip arayüzde onay penceresi açar. | `api/server.py:241-270` |
| İndirme Kontrolü | `POST /control` | JSON: `action` (`pause`, `resume`, `remove`, `pause_all`, `resume_all`, `ayarla`), `gid`, `delete_files`, `baglanti`, `hiz_kb` | İndirmeleri duraklatır, sürdürür, siler veya çalışan HTTP indirmesinin bağlantı/hız limitlerini canlı değiştirir. | `api/server.py:271-295` |
| Ayarları Güncelle | `POST /settings` | JSON: `{key: value, ...}` | Backend ayarlarını günceller, veritabanına yazar ve çalışan motorlara anında yansıtır. | `api/server.py:296-297` |
| Süresi Dolan Linki Yenile | `POST /renew` | JSON: `gid`, `url`/`new_url`, opsiyonel `headers`, `cookies`, `user_agent` | Google Drive / dosya barındırma sitelerinde indirme sıfırlanmadan inen baytları koruyarak yeni URL ve başlıklarla indirmeye devam eder. | `api/server.py:298-316` |
| Hız Profili Değiştir | `POST /mode` | JSON: `profil` veya `mode` (`"snail"`, `"normal"`, `"turbo"`) | Hız profilini çalışan indirmeleri kesmeden anında değiştirir. | `api/server.py:317-323` |
| LinkGrabber'a Aktar | `POST /linkgrabber` | JSON: `metin`, `dosya` | Tarayıcı uzantısından gelen ham sayfa metnini LinkGrabber paneline aktarır ve pencereyi öne getirir. | `api/server.py:324-338` |

---

## 4. Kullanıcıyı İlgilendiren Davranışlar ve Kontrol Mekanizmaları

| Kullanıcı Davranışı | Kontrol Eden Değer / Ayar | Varsayılan Değer | Çalışma Mantığı ve Etkisi | DOSYA:SATIR |
|---|---|---|---|---|
| Eşzamanlı İndirme Sayısı | `max_concurrent` | `5` | aria2'ye `--max-concurrent-downloads` olarak verilir ve `apply_settings` ile anında güncellenir. Kuyruktaki işlerin kaç tanesinin aynı anda aktifleşeceğini sınırlar. | `core/db.py:55`<br>`core/manager.py:125`<br>`core/daemon.py:68` |
| Genel Hız Sınırı | `max_speed_kb`, `hiz_profili`, `snail_speed_kb` | `0` (Sınırsız), `"normal"`, `100` KB/s | Hız profiline göre hesaplanır: `turbo` = 0 (sınırsız), `snail` = `snail_speed_kb`, `normal` = `max_speed_kb`. aria2'ye `max-overall-download-limit` ile kesintisiz aktarılır. | `core/db.py:58-63`<br>`core/manager.py:111-135`<br>`core/manager.py:136-160` |
| Tekil İndirmede Canlı Hız ve Bağlantı Ayarı | `control(action='ayarla', gid=..., baglanti=..., hiz_kb=...)` | İşe özel | Çalışan HTTP indirmesini KESMEDEN `max-connection-per-server` (1-64) ve `max-download-limit` değerlerini değiştirir; ayarları DB'ye işleyip yeniden başlatmada korur. | `core/manager.py:161-201`<br>`api/server.py:285-291` |
| Çok Parçalı İndirme ve Parça Boyutu | `split`, `max_conn_per_server` | `split: 64`, `max_conn_per_server: 16` | aria2 başlatılırken `--split=64`, `--min-split-size=1M`, `--max-connection-per-server=16` olarak ayarlanır. Çok parçalı hızlanmayı sağlar. | `core/daemon.py:65-67`<br>`core/manager.py:126-127` |
| Otomatik Yeniden Deneme ve Zaman Aşımları | Sabit aria2 Argümanları | Deneme: `10`, Bekleme: `3s`, Zaman aşımı: `30s`, Bağlantı: `15s` | aria2c başlatılırken `--max-tries=10`, `--retry-wait=3`, `--timeout=30`, `--connect-timeout=15`, `--continue=true`, `--always-resume=true` argümanları verilir. | `core/daemon.py:72-77` |
| İndirme Tamamlanma Eylemi: Kapatma | `shutdown_when_done` | `False` | Tüm aktif/bekleyen indirmeler bittiğinde (`_all_idle()`) Windows'ta 60 saniyelik geri sayımla kapatma başlatır (`shutdown /s /t 60`). | `core/db.py:69`<br>`core/manager.py:1535-1540` |
| İndirme Tamamlanma Eylemi: Uyutma | `sleep_when_done` | `False` | Tüm indirmeler bittiğinde 20 saniye bekler (kullanıcı iptal edebilsin diye), ardından makineyi S3 uykusuna alır (`guc.uyut()`). Uyanışta şifre istemez. | `core/db.py:71`<br>`core/manager.py:1541-1556`<br>`core/guc.py:24-35` |
| İndirme Tamamlanma Eylemi: Telegram | `notify_telegram`, `telegram_bot_token`, `telegram_chat_id` | `False`, `""`, `""` | İndirme bittiğinde başlık ve insan-okur boyut bilgisini içeren Telegram mesajını HTTPS üzerinden Telegram Bot API'sine asenkron postalar. | `core/db.py:66-68`<br>`core/manager.py:1526-1534`<br>`core/manager.py:1565-1580` |
| Oturum Çerezleri (Cookies) | `DownloadRequest.cookies`, `_cerezler` | Oturum bazlı bellek sözlüğü | Hassas oturum çerezleri güvenlik gereği SQLite DB'ye yazılmaz; RAM'de tutulur. aria2 için `Cookie:` başlığı, yt-dlp için Netscape `cookies.txt` dosyası üretilir. İş bitince temizlenir. | `core/manager.py:77-79`<br>`core/manager.py:386-388`<br>`core/manager.py:525-526`<br>`core/cerez.py:41-129` |
| Proxy Önceliği ve Katmanları | `DownloadRequest.proxy`, `system_proxy`, `proxy` | Sırayla değerlendirilir | Öncelik: 1) İsteğe özel `proxy`, 2) Açık ise Windows `system_proxy` (`Internet Settings`), 3) Ayarlardaki genel `proxy`. `parcala` ile normalize edilip aria2/yt-dlp'ye verilir. | `core/manager.py:416-432`<br>`core/proxy.py:3-15`<br>`core/proxy.py:73-137` |
| BitTorrent Seed Oranı (Ratio) | `seed_ratio` | `1.0` | aria2'ye `--seed-ratio=1.0` argümanı ve `changeGlobalOption` ile aktarılır. Dosya boyutu kadar upload yapıldıktan sonra seed sonlandırılır. | `core/db.py:72`<br>`core/manager.py:129`<br>`core/daemon.py:92` |
| BitTorrent Dosya Seçimi | `torrent_file_selections` tablosu & `select-file` | Tümü seçili | Torrent indirilmeden önce veya indirilirken dosyalar seçilebilir. Canlı torrentte `changeOption(select-file)` ile duraklatma olmadan uygulanır; GID değişse bile korunur. | `core/db.py:117-124`<br>`core/db.py:299-337`<br>`core/manager.py:1270-1314` |
| BitTorrent Tracker Havuzu ve Canlılık | `auto_update_trackers`, `tracker_otomatik_tara`, `ek_trackerlar`, `canli_trackerlar` | Otomatik: `True`, Otomatik Tara: `True` | Uzak depolardan tracker çeker; `trackers/` klasöründeki `.txt` listelerini UDP/HTTP scrape ile paralel test edip ölüleri eler; canlıları aria2 `bt-tracker` havuzuna yazar. | `core/trackers.py:179-201`<br>`core/tracker_saglik.py:252-305`<br>`core/manager.py:1494-1522` |
| BitTorrent Seed Yeniden Duyurma | `manager.seed_tazele(gid)` | — | aria2 çalışan torrente yeni tracker ekleyemediği için torrenti durdurup kaldırır, dosyaları silmeden yeni tracker havuzuyla aynı dizine yeniden ekler; ilerleme korunur. | `core/manager.py:928-998` |
| Süresi Dolan Bağlantıyı Yenileme (Renew) | `manager.renew(gid, yeni_url, ...)` | — | İmzalı bağlantısı (Google Drive, dosya sunucusu) düşen indirmelerde aria2 `changeUri` çağrısıyla inen baytları sıfırlamadan yeni linkle indirmeye devam ettirir. | `core/manager.py:704-812` |
| Zamanlanmış İndirme | `start_at` / `start_after` | `None` | `HH:MM` veya `YYYY-MM-DD HH:MM` biçiminde verilen saat geldiğinde `_poll_loop` arka plan döngüsü tarafından otomatik kuyruğa alınıp başlatılır. | `core/models.py:36-67`<br>`core/db.py:339-347`<br>`core/manager.py:1486-1493` |
| Otomatik Kategoriye Ayrıştırma | `kategori_klasorleri` | `True` | Dosya uzantısına göre `Video`, `Muzik`, `Programlar`, `Belgeler`, `Arsivler`, `Genel` klasörleri altına kaydeder. | `core/kaydet.py:30-67`<br>`app.py:136-143` |
| Pano İzleme ve Otomatik Yakalama | `clipboard_watch`, `clipboard_exts` | `True`, 13 uzantı | Windows panosu her saniye ctypes ile kontrol edilir. Desteklenen uzantı veya video sitesi kopyalandığında yakalama arayüzü tetiklenir. | `core/clipboard.py:41-94`<br>`app.py:1042-1048` |
| Sistem Tepsisine Küçültme (Tray) | `tepsiye_kucult` | `True` | Pencere kapatıldığında arka planda `pystray` simgesinde çalışmaya devam eder; çift tıklama veya menüden geri getirilebilir. | `app.py:730-746`<br>`app.py:845-913`<br>`core/pencere.py:169-199` |
| Windows Başlangıcında Çalışma | `baslangicta_tepside` | `True` | Windows Startup klasörüne `AfuDM.lnk` kısayolu ekler; `--tepside` argümanıyla arka planda gizli başlar. | `core/baslangic.py:77-156`<br>`app.py:381-390`<br>`app.py:920` |
| Çift Tıklanan .torrent ve magnet: İlişkilendirmesi | `iliskilendir.ac()` | Kayıt defteri | `HKCU\Software\Classes` altına yazılarak gezginde `.torrent` dosyasına tıklandığında veya tarayıcıda magnet linkine basıldığında AfuDM'in açılmasını sağlar. | `core/iliskilendir.py:113-187`<br>`app.py:802-812`<br>`app.py:918-922` |
| Tek Kopya (Single Instance) Koruması | `calisan_ornege_yolla(link)` | — | İkinci bir AfuDM örneği başlatıldığında link varsa açık olan örneğe `POST /add` ile aktarır; link yoksa `GET /show` ile pencereyi öne getirir ve kendisini kapatır. | `app.py:815-842`<br>`app.py:921-922` |
| IPv6 Otomatik İzolasyonu | `netcheck.ipv6_usable()` | Çalışma anında tespit | Gerçek genel IPv6 rotası yoksa aria2'nin WSAENETUNREACH hatasıyla indirmeyi iptal etmesini önlemek için `--disable-ipv6=true` argümanını otomatik ekler. | `core/netcheck.py:1-64`<br>`core/daemon.py:106-109` |
| Video FFmpeg Remux / MP4 Dönüştürme | `ytdlp.py` & `mp4mux.py` | ffmpeg varsa ffmpeg, yoksa dahili remux | ffmpeg kurulu değilse YouTube'dan ayrı inen video ve ses akışlarını saf Python `mp4mux` motoruyla kayıpsız birleştirir; sessiz video kalmasını önler. | `video/ytdlp.py:40-56`<br>`video/mp4mux.py:1-18` |
| Dosya İndirme Sağlama Kontrolü (Checksum) | `DownloadRequest.checksum` | `md5`, `sha-1`, `sha-224`, `sha-256`, `sha-384`, `sha-512` | İndirme eklenirken verilen hash bilgisini aria2 `checksum` seçeneğine (`TYPE=HEX`) dönüştürür; indirme sonunda bütünlüğü otomatik doğrular. | `core/models.py:20-34`<br>`core/models.py:69-88`<br>`core/manager.py:467-468` |
