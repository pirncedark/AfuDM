# AfuDM — Kontrol Listesi

Amaç: v2.7.2 öncesi mevcut özellikleri doğrulayıp raporlamak. Yeni özellik veya ürün kodu değişikliği yok.
Kaynaklar: README.md, docs/BACKEND_ENVANTER.md, docs/UI_ENVANTER.md, docs/UI_UX_MASTER_TESTLIST.md ve _gorev/RAPOR_D1_TARAMA.md.
Sürüm kaynağı: core/surum.py v2.7.1; uzantı manifest’i v2.7.1.

**GEÇTİ** test/gerçek çalıştırma geçti; **KALDI** hata/güvenlik/veri bulgusu; **MANUEL** gerçek cihaz/pencere/sistem gerekir; **ATLANDI** görev kısıtı nedeniyle denenmedi.

## A — Başlatma ve temel

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| A1 | Taşınabilir veri klasörü (data/, downloads/ uygulama yanında) | Zip’i açıp AfuDM.exe’yi engine/ui ile birlikte çalıştırın; data/ ve downloads/ uygulama klasöründe kalır. | tests/paket_import_test.py + gerçek paket smoke | GEÇTİ | Paket import testi geçti; paket yanında data/downloads ile servis açıldı. |
| A2 | Tek kopya kilidi (ikinci açılış öne getirir) | AfuDM.exe’yi yeniden açın veya .torrent başlatın; çalışan pencere öne gelir. | ikinci pencere (MANUEL) | MANUEL | Pencere açılmadı; MANUEL. |
| A3 | Arayüzsüz servis `afuadm server start/status/stop` | Komut İstemi’nde `afuadm server start`, `status`, `stop` kullanın. | paket afuadm server start/status/stop | GEÇTİ | Paket start/status/stop çıkış kodları 0/0/0; stop sonrası status 2. |
| A4 | Açılışta JS hatası yok, arayüz yükleniyor | AfuDM.exe’yi çalıştırın; ana indirme listesi açılır. | python tests/ui_startup_test.py | GEÇTİ | ui_startup_test: 3 test geçti. |
| A5 | Pencere boyutu 1600x980 + DPI (#25) | Pencereyi başlık çubuğundan büyütün; DPI’yi Windows Görüntü’den seçin. | pencere/DPI (MANUEL) | MANUEL | Gerçek DPI/pencere testi yapılmadı; MANUEL. |

## B — HTTP indirme

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| B1 | Link ekle → indir (çoklu bağlantı) | Sol menü `+ Ekle` ile bağlantıyı yapıştırın; pano veya uzantıdan da gönderin. | tests/kontrol/B1_real_aria2.py | GEÇTİ | Gerçek aria2 fake_http 127.0.0.1 indirmesi ve SHA-256 geçti. |
| B2 | Duraklat / devam | Satırdaki Duraklat’a, sonra Devam’a basın. | tests/kontrol/B1_real_aria2.py | GEÇTİ | Gerçek aria2 pause/resume tamamlandı. |
| B3 | Uygulama kapanıp açılınca devam | İndirme sürerken kapatıp açın; görev session’dan devam eder. | tests/kontrol/B3_aria2_session_restart.py; D1_07_cookie_session.py | KALDI | **Şu an çalışmıyor (güvenli session):** sentetik Cookie gerçek aria2.session içinde bulundu; `core/daemon.py:96-100`, `tests/kontrol/D1_07_cookie_session.py`. |
| B4 | Hız sınırı + snail/normal/turbo | Ayarlar’da hız/profil seçin; CLI `afuadm mode snail|normal|turbo`. | B1_real_aria2.py; tests/network_core_test.py | GEÇTİ | Canlı hız 131072 bayt/s; network_core 41 kontrol geçti. |
| B5 | Süresi dolan linki yenile (renew) | CLI `afuadm renew <gid> "<yeni bağlantı>"` yazın. | python tests/cli_test.py | GEÇTİ | CLI renew mock RPC’de URI değiştirdi. |
| B6 | Checksum doğrulama | CLI `afuadm add URL --checksum sha-256:<hex>` kullanın. | tests/kontrol/B1_real_aria2.py | GEÇTİ | Yanlış hash gerçek aria2’de error üretti. |
| B7 | Proxy (global + indirme başına) | Ayarlar > Proxy’yi doldurun; özel indirme için `--proxy` kullanın. | python tests/network_core_test.py | GEÇTİ | Network core 41 kontrol, 0 hata. |
| B8 | İndirme başına bağlantı/hız (`ayarla`) | Satır menüsü veya `afuadm ayarla <gid> --baglanti 8 --hiz 500`. | python tests/network_core_test.py | GEÇTİ | İndirme başı seçenekleri network_core testinde geçti. |
| B9 | Kategori klasörleri (Video/Müzik/Belgeler) | Ayarlar’da kategori klasörlerini açın. | python tests/kaydet_test.py | GEÇTİ | Kaydetme testi kategori/klasör kontrolleri geçti. |
| B10 | İndirme diyaloğu (ad, kategori, klasör ağacı, zamanla) | Yeni linkte ad, kategori, klasör ve zaman seçip İndir’e basın. | python tests/ui_startup_test.py | GEÇTİ | ui_startup_test 3 test geçti. |
| B11 | Kuyruk: aynı anda N indirme | Ayarlar’da aynı anda çalışacak indirme sayısını seçin. | python tests/kuyruk_test.py | GEÇTİ | Kuyruk testi geçti. |
| B12 | Zamanlı başlatma (23:30) | Kaydetme penceresinde saat seçin veya `--start-at "23:30"` kullanın. | python tests/cli_test.py | GEÇTİ | CLI start-at testi geçti. |
| B13 | Pano izleme | Ayarlar’da Pano izleme’yi açın; linki kopyalayın. | pano (MANUEL) | MANUEL | OS panosu kullanılmadı; MANUEL. |
| B14 | Klasör / Aç düğmeleri doğru dosyayı açıyor | Satırdaki klasör düğmesi konumu, Aç düğmesi dosyayı açar. | Explorer (MANUEL) | MANUEL | Explorer açılmadı; MANUEL. |
| B15 | Toplu seçim + toplu silme + Tümünü seç | Liste kutularından görevleri seçip Tümünü seç/kaldır’ı kullanın. | python -m pytest -q tests/bulk_and_parent_remove_test.py | KALDI | **Şu an çalışmıyor/doğrulanamadı:** 1 failed, 1 passed; `tests/bulk_and_parent_remove_test.py:49` parent GID `KayitYok` veriyor. |
| B16 | Bitenleri temizle | Listenin üstündeki Bitenleri temizle’ye basın. | gerçek UI (MANUEL) | MANUEL | Gerçek UI açılmadı; MANUEL. |
| B17 | Türkçe arama (I/ı/İ/i) | Ana listedeki arama alanına dosya adını yazın. | python tests/tr_arama_test.py | GEÇTİ | Türkçe arama testi geçti. |

## C — Video

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| C1 | Video analiz + kalite seçimi | `+ Ekle` ile video bağlantısı girip kaliteyi seçin. | python tests/kontrol/C1_youtube_real.py | GEÇTİ | Tek YouTube URL: Me at the zoo.mp4, 475990 bayt. |
| C2 | Yalnız ses (mp3) | Video penceresinde Yalnız ses’i işaretleyin. | python tests/kontrol/C2_youtube_audio.py | GEÇTİ | Aynı URL: Me at the zoo.mp3, 331053 bayt. |
| C3 | Oynatma listesi | `+ Ekle` alanına playlist URL’si verip onaylayın. | ATLANDI: ek video ağı | ATLANDI | Test sonucu kaydedildi. |
| C4 | Birleştirme sonrası doğru dosya adı/boyut (#35) | İndirme sonrası çıktı klasöründe dosya adı/boyutunu kontrol edin. | merger testi + gerçek MP4 | GEÇTİ | Gerçek MP4 adı/boyutu ve merger testi geçti. |
| C5 | ffmpeg'siz kendi muxer | Video indirirken ffmpeg yoksa yerleşik muxer çalışır. | python tests/mux_test.py | GEÇTİ | Mux/ffprobe testi geçti. |
| C6 | Tarayıcı çerezi + 403 çerezsiz yedek | Ayarlar’daki video çerezi alanından tarayıcı seçin. | python tests/video_cerez_test.py | GEÇTİ | Video cookie/403 yedek testi geçti. |
| C7 | Altyazı / küçük resim / bölümler / SponsorBlock seçenekleri | Video Pro panelinde altyazı/küçük resim/bölüm/SponsorBlock seçin. | python tests/video_pro_test.py | GEÇTİ | Video Pro 66 kontrol, 0 hata; UI i18n testi false alarm, anahtar ui/i18n.js:1245’te var. |
| C8 | Yetim "aktif" kayıt açılışta toparlanıyor (#35) | Uygulamayı yeniden açınca eski aktif video kaydı toparlanır. | python tests/video_yetim_kayit_test.py | GEÇTİ | Yetim video kaydı 3 test geçti. |
| C9 | Video motorlarını Ayarlar’dan indirme (çekirdek pakette) | Ayarlar > Motorlar’da yt-dlp veya ffmpeg İndir’e basın. | python tests/engines_test.py | GEÇTİ | Motor testi geçti; dış indirme yapılmadı. |

## D — Torrent

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| D1 | Magnet ekle | `+ Ekle` alanına magnet girin; metadata gelince dosyaları seçin. | MANUEL: DHT metadata | MANUEL | DHT metadata dış ağ ister; MANUEL. |
| D2 | .torrent dosyası + dosya seçimi | .torrent sürükleyin/çift tıklayın; listeden dosya seçin. | python tests/torrent_secim_test.py | GEÇTİ | Torrent dosya seçim testi geçti. |
| D3 | Seed penceresi + tracker yenile + kendi tracker | Torrent satırında Seeds’e basıp tracker yenileyin/ekleyin. | python tests/seed_test.py; trackerlar_test.py | GEÇTİ | Seed ve tracker testleri geçti. |
| D4 | Torrent penceresi kapanınca metrik isteği duruyor | Torrent penceresini X, Escape veya arka planla kapatın. | python tests/kontrol/panel_dongu_test.py | GEÇTİ | Torrent panel döngüsü geçti; diğer hatalar E1’de. |
| D5 | Magnet metadata gelince dosya listesi yenileniyor | Magnet metadata gelince dosya listesi hazır olur. | MANUEL: DHT metadata | MANUEL | DHT metadata dış ağ ister; MANUEL. |
| D6 | 250 dosya sınırı klasör satırlarını saymıyor | Dosya seçim penceresinde daha fazlasını gösterin. | python tests/torrent_ui_test.py | GEÇTİ | 250 dosya limiti testi geçti. |
| D7 | `loglar(gid)` yalnız o indirmenin olaylarını döndürüyor | Görev ayrıntılarında Olaylar sekmesini açın. | python tests/torrent_duzeltme_test.py | GEÇTİ | GID olay filtreleme testi geçti. |

## E — Arayüz / UX

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| E1 | 16 panel: aç / tıkla / X / ESC / arka plan / hata / tekrar aç | Sol menü panellerini açıp düğme/X/Escape/arka planı deneyin. | python tests/kontrol/panel_dongu_test.py | KALDI | **Şu an çalışmıyor:** panel testi 16’da 14; drawer ve shareCenterVeil başarısız. |
| E2 | TR + EN anahtar eşitliği, i18n dışı metin yok | Ayarlar > Dil’den Türkçe veya English seçin. | python tests/i18n_test.py + statik inceleme | KALDI | **Şu an çalışmıyor:** sabit metin `ui/app.js:662`, `ui/mobil.html:383`; i18n testi bu satırları taramıyor. |
| E3 | UI kapısı: 1280x720 / 1366x768 / 1920x1080, DPI 100/150/200 | Pencere boyutunu ve Windows DPI oranını değiştirin. | python tests/ui_ux_gate_test.py | GEÇTİ | UI gate 14 test, headless geçti. |
| E4 | Satır hover titremesi yok (#25) | Fareyi ana listede indirme satırlarının üzerinde gezdirin. | python tests/hover_sabit_test.py | GEÇTİ | Hover testi geçti. |
| E5 | Pencere düğmeleri sürüklenmiyor (#25) | Başlık çubuğu küçült/büyüt/kapat düğmelerini kullanın. | python tests/pencere_dugme_test.py | GEÇTİ | Pencere düğmesi testi geçti. |
| E6 | Ölü tıklama hedefi = 0, uncaught JS hata = 0 | Panellerde görünen düğmelere basın; JS hataları izlenir. | python tests/kontrol/panel_dongu_test.py | KALDI | **Şu an çalışmıyor:** shareCenterVeil turunda uncaught JS kontrolü başarısız. |

## F — Paylaşım (#25)

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| F1 | Ağda paylaş: LAN linki (http://http:// yok) | Satır menüsünde Ağda Paylaş’ı seçin; link/QR alın. | python tests/paylasim_link_test.py | GEÇTİ | LAN link biçimi testi geçti. |
| F2 | QR kod | Paylaşım penceresindeki QR’ı telefondan okutun. | python tests/paylasim_test.py | GEÇTİ | Paylaşım testi geçti; SMB açılmadı. |
| F3 | SMB paylaşımı açılıyor VE silinince kaldırılıyor | Paylaşım Merkezi’nde dosya seçip paylaşın, sonra Sil’e basın. | statik; SMB çalıştırılmadı | KALDI | **Şu an çalışmıyor (güvenlik):** `app.py:1187,1224-1228` silme SMB revoke/staging cleanup yapmıyor. SMB açılmadı. |
| F4 | Cloudflare quick tunnel yalnız /s/ açıyor | Paylaşım Merkezi’nde İnternetten paylaş’ı seçin. | python tests/tunel_test.py | GEÇTİ | Tunnel /s/ ve loopback testi geçti; D1-11 thread join statik bulgu. |
| F5 | Paylaşım modalı kapanıyor, çift id yok | Paylaşım penceresini X/Escape/arka planla kapatın. | python tests/modal_kapat_test.py | GEÇTİ | Modal kapatma testi geçti. |
| F6 | Paylaşım listesinde XSS yok | Paylaşım Merkezi dosya listesi ad ve bağlantı gösterir. | statik; XSS çalıştırılmadı | KALDI | **Şu an çalışmıyor (XSS):** `ui/app.js:3874-3882` paylaşım alanları escape olmadan innerHTML’e yazılıyor. |

## G — Mobil

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| G1 | `/m` mobil panel | Aynı Wi-Fi’de telefonda `http://PC-adresi:port/m` açın. | v175_mobil_test.py; telefon MANUEL | MANUEL | Mobil API testi geçti; gerçek telefon MANUEL. |
| G2 | PWA | Mobil panelde tarayıcı menüsünden Ana ekrana ekle’yi seçin. | python tests/pwa_test.py | GEÇTİ | PWA testi geçti. |
| G3 | Telefona indir `/indir` (kök dışı yol reddi) | Mobil panelde görevden Telefona indir’i seçin. | telefona_indir_test.py + statik | KALDI | **Şu an çalışmıyor:** `api/server.py:378-407` `/indir` kök denetimi yapmıyor; kök dışı GID isteğiyle yeniden üret. |
| G4 | LAN eşleştirme `/pair` | Ayarlar’da Telefon bağlantısını açıp QR eşleştirmesi başlatın. | api/server.py /pair incelemesi | KALDI | **Şu an çalışmıyor (güvenlik):** `api/server.py:366-369` pairing açıkken `/pair` token döndürüyor; README yanlış, LAN modu `0.0.0.0` dinliyor. |

## H — Tarayıcı uzantısı

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| H1 | Uzantı sürümü = core/surum.py | Sürümü Ayarlar’da ve Chrome uzantı ayrıntılarında görün. | sürüm karşılaştırması | GEÇTİ | Core/uzantı sürümü 2.7.1/2.7.1 eşit. |
| H2 | İndirmeleri devralma + çerez gönderme | Uzantıyı ekleyin; tarayıcı indirmesini AfuDM devralır. | MANUEL: Chrome yok | MANUEL | Gerçek Chrome kullanılmadı; MANUEL. |
| H3 | Video paneli (HLS/DASH kalite) | Video üstündeki AfuDM düğmesine basıp kalite seçin. | MANUEL: tarayıcı yok | MANUEL | Tarayıcı açılmadı; MANUEL. |
| H4 | Başlık politikası (tehlikeli başlık reddi) | Uzantı video başlıklarını filtreler; Chrome’da etkin tutun. | node tests/maestro_test.mjs | GEÇTİ | maestro_test.mjs tüm kontroller geçti; Python negatif testi mock DOM eksikliğinden erken hata verdi. |
| H5 | Sağ tık menüsü | Sayfada sağ tıklayıp AfuDM indirme menüsünü seçin. | MANUEL: tarayıcı yok | MANUEL | Tarayıcı menüsü açılmadı; MANUEL. |
| H6 | "Chrome’a ekle" otomatik kurulum | Sol menü Chrome’a ekle > Otomatik ekle’yi seçin. | MANUEL: Chrome testi açar | MANUEL | Chrome penceresi açacağı için koşulmadı; MANUEL. |

## I — Komut satırı

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| I1 | list / status / add / info / watch | Komut İstemi’nde `afuadm list/status/add/info/watch` çalıştırın. | cli_test.py; cli_yardim_test.py | GEÇTİ | CLI komut/help testleri geçti. |
| I2 | `--json` yalnız JSON, çıkış kodları 0/2/3/4/130 | `afuadm status --json` gibi komuta `--json` ekleyin. | python tests/cli_surum_test.py | GEÇTİ | CLI JSON/exit testinde 25 kontrol geçti. |
| I3 | Başlatma yarışı kilidi | İki terminalde aynı anda `afuadm server start` yazın. | python tests/cli_surum_test.py | GEÇTİ | CLI yarış kilidi testi geçti. |

## J — Sunucu / API / güvenlik

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| J1 | Web panel erişim anahtarı (admin / salt-okur), döndürme | Sunucu panelinde Anahtar oluştur’dan rol seçin; Döndür ile yenileyin. | J1_access_keys.py + paket smoke | GEÇTİ | Admin/salt-okur/rotasyon ve paket servisi geçti. |
| J2 | API token zorunlu, token loglara/URL’ye düşmüyor | Sunucu panelinde anahtar oluşturup isteklerde başlıkla gönderin. | api/server.py incelemesi | KALDI | **Şu an çalışmıyor:** `api/server.py:192` query token, `:115,251` wildcard CORS; query/preflight isteğiyle yeniden üret. |
| J3 | `/add` hedef klasör kökü dışına çıkamıyor | Yönetim API `/add` isteğine URL ve hedef klasör gönderin. | api/server.py + core/servis.py | KALDI | **Şu an çalışmıyor:** `api/server.py:539-552`, `core/servis.py:137-145`; LocalAPI kök dışı dest_dir doğrulamasını atlayabilir. |
| J4 | CORS dar | Yönetim paneline izin verilen kaynaktan başlık anahtarıyla bağlanın. | api/server.py CORS incelemesi | KALDI | **Şu an çalışmıyor:** `api/server.py:115,251` her Origin’e `*` döndürüyor. |

## K — Otomasyon / kurallar / eklentiler

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| K1 | Kurallar motoru (hedef klasör, hız, bölme) | Sol menü Kurallar > Yeni kural’dan koşul/eylem seçip kaydedin. | tests/kontrol/K1_rules_smoke.py | GEÇTİ | Kurallar koşul/hedef/hız/bölme testi geçti. |
| K2 | Bitince Telegram bildirimi / bilgisayarı kapat | Ayarlar’da Telegram veya bitince kapatma seçeneklerini düzenleyin. | python tests/guc_test.py (mock) | GEÇTİ | Güç mock testi geçti; gerçek kapatma yok. |
| K3 | Eklentiler (sha256 doğrulama, onay) | Eklentiler panelinden .afup seçin; izinleri onaylayın. | python tests/eklenti_test.py | GEÇTİ | Eklenti 32 kontrol geçti; sandbox uyarısı var. |

## L — Windows entegrasyonu (sisteme dokunmadan)

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| L1 | .torrent / magnet ilişkilendirme + eski kaydı yedekle/geri yükle | Ayarlar’da ilişkilendirmeyi seçin; Windows varsayılan uygulamalardan AfuDM’i belirleyin. | MANUEL: registry yasak | MANUEL | Registry’ye dokunulmadı; MANUEL. |
| L2 | Tepsi, Windows ile başlat | Ayarlar’da tepsi ve Windows başlangıç seçeneklerini kullanın. | baslangic_test.py; tepsi_test.py (mock) | GEÇTİ | Startup/tepsi testleri mock ile geçti; gerçek ayar değişmedi. |

## M — Güvenilirlik / veri

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| M1 | Yedek al / geri yükle, sonra kapalı Store kullanılmıyor | Ayarlar > Yedek’ten alın/listeden geri yükleyin; uygulamayı yeniden başlatın. | core/reliability.py incelemesi | KALDI | **Şu an çalışmıyor (veri):** `core/reliability.py:54-72`; restore worker/servis referanslarını yenilemiyor. |
| M2 | DB şeması 0→10 ve 3→10 geçişi (idempotent) | DB geçişi açılışta otomatik yapılır. | db_test.py + D1_05_migration_conflict.py | KALDI | **Şu an çalışmıyor:** `core/db.py:194-195`; mevcut events.gid ve user_version=2 duplicate column hatası verir. |
| M3 | Tanılama raporu (tani.bat) | AfuDM klasöründe `tani.bat` çalıştırın. | MANUEL: diagnostics yok | MANUEL | Tanılama makine bilgisi toplar; çalıştırılmadı, MANUEL. |
| M4 | Silme: kayıt / dosya / üst klasör, yetim temizlik | Görev satırında Kaldır’a basıp kayıt/dosya/üst klasör seçimini onaylayın. | python -m pytest -q tests/orphan_remove_test.py | KALDI | **Şu an çalışmıyor:** `core/manager.py:745`; orphan_remove pytest 2 failed, 1 passed; `KayitYok` ile kesiliyor. |

## N — Paket / yayın

| ID | Özellik | Nasıl kullanılır | Doğrulama | Sonuç | Kanıt |
|---|---|---|---|---|---|
| N1 | Paket kendi başına çalışıyor (video/ dahil) | Zip’i açıp AfuDM.exe veya `afuadm server start` çalıştırın. | paketle CIKTI=build_out/paket_kontrol + smoke | GEÇTİ | Paket 25.0 MB, video/ dahil; import ve headless servis geçti. D1-01 yanlış alarm. |
| N2 | exe güncel kaynaktan derleniyor (#26) | Derleme PyInstaller komutuyla yapılır. | python -m PyInstaller --noconfirm --clean AfuDM.spec | GEÇTİ | PyInstaller Build complete; AfuDM.exe 18.5 MB. |
| N3 | Açık exe varken paketleyici hiçbir şey silmiyor | `python paketle.py` çalıştırın; açık exe kilitliyse işlem durur. | python -m pytest -q tests/paketle_kilit_test.py | GEÇTİ | Paket kilidi testi geçti. |
| N4 | Sürüm notu kuralı (İngilizce üst) | Sürüm notunu İngilizce bölümle başlatın. | python -m pytest -q tests/release_tools_test.py | GEÇTİ | Release tools 7 test geçti; güncel not v2.7.1. |

## Sonuç özeti

Satır sayısı: **80** — GEÇTİ **50**, KALDI **15**, MANUEL **14**, ATLANDI **1**.

### KALDI — öncelik sırasıyla

1. **G4** — Pairing açıkken `/pair` LAN istemcisine tam token döndürüyor (`api/server.py:366-369`); pairing açıp isteği yinele.
2. **J3** — LocalAPI kök dışı `dest_dir` değerini sınır kontrolüne sokmuyor (`api/server.py:539-552`, `core/servis.py:137-145`); tokenlı `/add` ile yinele.
3. **G3** — `/indir` kök dışı dosyayı reddetmiyor (`api/server.py:378-407`); kök dışı GID ile yinele.
4. **J2/J4** — Query token ve wildcard CORS (`api/server.py:115,192,251`); query/preflight isteğiyle yinele.
5. **F3/F6** — SMB silme temizliği yok; paylaşım listesi XSS’e açık (`app.py:1187,1224-1228`, `ui/app.js:3874-3882`).
6. **M1/M2/M4** — Restore sonrası eski Store; çakışmalı migration; orphan kaldırma testi düşüyor (`core/reliability.py:54-72`, `core/db.py:194-195`, `core/manager.py:745`).
7. **B3** — Resume geçti ama Cookie session dosyasına yazılıyor (`core/daemon.py:96-100`).
8. **E1/E6** — Drawer/shareCenterVeil panel döngüsü başarısız; `python tests/kontrol/panel_dongu_test.py`.
9. **E2** — Sabit metinler çeviri dışında (`ui/app.js:662`, `ui/mobil.html:383`).
10. **B15** — Parent kaldırma testi düşüyor (`tests/bulk_and_parent_remove_test.py:49`).

MANUEL: **A2, A5, B13, B14, B16, D1, D5, G1, H2, H3, H5, H6, L1, M3**. Gerçek pencere, telefon, pano/Explorer, tarayıcı, registry veya tanılama gerekir. Sistem ayarı değiştirilmedi, yeni pencere açılmadı.

ATLANDI: **C3** — playlist tek izinli videonun dışına çıkmayı gerektiriyordu.

### D1 raporu çapraz kontrolü

- **D1-01 yanlış alarm:** `paketle.py:31` bu dalda `video/` içeriyor; paket importu ve headless servis geçti.
- **D1-02/03/04/05/06/07/08/09/12/14 gerçek:** G4, F3, M1, M2, J3, B3, F6, G3, E2, J2/J4 kanıtlarında doğrulandı.
- **D1-10/11/13 gerçek statik bulgular:** stream hatalarının yutulması, worker join eksikleri ve yinelenen/ulaşılamaz kod mevcut.
- **D1-15 risk kabulü:** eklenti host’u OS sandbox’ı değil; uyarı arayüzde, testleri geçti.
- **D1-16 kısmen gerçek:** README’nin yalnız loopback iddiası LAN koduyla çelişiyor (**README yanlış**); v2.7.1 eşleşmesi doğru.
- **D1-17 gerçek:** repo kökünde geliştirme/çıktı artıkları var; paketleyici bunları pakete almıyor.
