# AfuDM indirme penceresi denetimi

30 Eylül 2026. Dal: `fix/pdf-ve-cift-indirme`. Çalışma ağacı üzerinde düzeltildi; dal değiştirme, commit, push, merge, sürüm üretimi yapılmadı. Canlı AfuDM süreci kapatılmadı, yeni uygulama penceresi açılmadı. Testlerin veri yolları geçici klasörlere yönlendirildi; canlı `data/` yazmaları test koşucusunda engellendi.

## Sekiz madde

1. Ana pencerenin `closed` olayı tek kapatma noktasına bağlandı. Çıkış bayrağı ayarlanıyor ve gizli indirme penceresi bir kez yok ediliyor; güncelleme, gerçek X ve tepsi çıkışı aynı yolu kullanıyor.
2. İndirme penceresinde X/Alt+F4 gösterilen bekleyen isteği iptal edip pencereyi gizliyor; uygulama çıkarken gerçek kapanışa izin veriliyor. Yerel kapatma callback'i JavaScript sonucunu beklemiyor: arayüz sıfırlaması sayaç üzerinden sonraki JS yoklamasında yapılıyor. Sonraki bekleyen istek tekrar gösteriliyor.
3. Bekleyen özetinde kaynak bilgisi var. Ana panel tarayıcı isteklerini filtreliyor; indirme penceresi yalnız tarayıcı isteklerini gösteriyor. Masaüstü dosya ilişkilendirmesi ve çalışan örneğe masaüstünden devretme ana panelde kalıyor. Kuyruktaki yeni onay, önceki indirme ilerlemesinden önce gösteriliyor.
4. `kaydet_bilgi` dosya adı ve türü de kullanarak kategori belirliyor. Kategori klasörleri açıkken PDF `Belgeler` klasörüne yönleniyor; kapalıyken ana klasör kullanılıyor. Kullanıcının klasör seçimi korunuyor.
5. Video isteğinde kalite ve yalnız ses değerleri kullanıcı değiştirmediği sürece aynen korunuyor. Dosya adı URL'den uydurulmuyor; kalite/ses seçimi mevcut çeviri anahtarlarıyla gösteriliyor.
6. İndirme penceresi uygulamanın `ui/i18n.js` / `lang.t` sistemiyle TR/EN çalışıyor. Yerel pencere başlığı ayardaki dilden güncelleniyor. Kısa hata mesajı çevrilmiş olarak gösteriliyor; teknik ayrıntı olay kaydında kalıyor. Ana düğmenin TR/EN, uzun URL ve video formunda sabit pencereye sığdığı gerçek headless tarayıcıyla doğrulandı.
7. `ui/download.html`, `ui/download.js`, `extension/download-handoff.js` EXE verilerine ve paket denetimlerine eklendi. Sürüm paketinin zaten özyinelemeli kopyaladığı UI/uzantı dosyalarının geçici klasörde ve ZIP içinde kaynakla byte eşitliği test edildi. Eksik/boş EXE varlıklarını reddeden testler eklendi. Gerçek EXE/release derlemesi yapılmadı.
8. `/add` devretme reddetmeleri ve onay başarısızlıkları `events` tablosuna `error` düzeyinde hata metniyle yazılıyor. Uzantı aktarım hatasını erişilebilir yerel API'ye bildiriyor. Başarısız onay aynı kimlikle tekrar denenebilir kalıyor. Chrome'un gerçek `state=in_progress` + `paused=true` biçimi kullanılarak başarısız/uygun olmayan devretmede tarayıcı indirmesi devam ettiriliyor.

## PDF kanıtı

Gerçek HTTP sunucusu, işletim sisteminin seçtiği geçici port ve geçici SQLite deposuyla `/add` onay bekletme yolu ve gerçek `Api.bekleyen_onayla` çağrısı çalıştırıldı:

- Uzantısız URL + `application/pdf`.
- `Content-Disposition: inline` + PDF dosya adı.
- 3000 karakterlik sorgu içeren URL.
- Windows'ta geçersiz karakter içeren dosya adı; boş kullanıcı seçimiyle özgün adın temizlenmesi de sınandı.

Bu dört girdi geçti; bildirilen özgün PDF hatası yeniden üretilemedi. Ek olarak açık hedef klasörü verilen istekte `Path` yerel importunun global `Path` kullanımını gölgelemesi yeniden üretildi ve düzeltildi. Bu kusurun kullanıcının özgün PDF hatası olduğu kanıtlanmış değildir. Yerel API tamamen erişilemezken uygulamanın olay tablosuna o anda yazılamaz.

## Testler

Tam üst dizin `*_test.py` / `*_test.mjs` takımı izole koşucuyla çalıştırıldı. İlk tam koşu: 71 dosya geçti, 5 başarısız, 6 atlandı. Ardından başarısız dört dosya yeniden doğrulandı:

- `paylasim_test.py`, `pwa_test.py`: geçici token dosyalarına Windows hesap ACL kısıtı uygulanmadan geçti; üretim güvenlik kodu değiştirilmedi.
- `panel_dongu_test.py`: 18 test geçti.
- `ui_ux_gate_test.py`: 17 test geçti.

Son iki arayüz testi ağ kısıtı nedeniyle ilk koşuda harici Google Fonts yüklemesinde zaman aşımı / `ERR_NETWORK_ACCESS_DENIED` verdi. Tekrar koşuda yalnız font CSS isteği headless tarayıcıda boş yerel yanıtla karşılandı; test beklentileri değiştirilmedi.

Ek odaklı doğrulamalar: pencere yaşam döngüsü/onay testleri (11), gerçek HTTP/PDF testleri (5), JS indirme penceresi davranış testi, gerçekçi Chrome devretme testi, TR/EN gerçek tarayıcı yerleşim testi ve paket import/ZIP/EXE varlık doğrulama testleri geçti. Python/JS/PowerShell sözdizimi ve `git diff --check` geçti.

`guc_test.py` ortamda ağ kartı adı ve MAC okuyamadığı için başarısız kaldı; bu görev kapsamındaki kodla ilgili değildir.

Canlı süreç/pencere kısıtı nedeniyle atlananlar: `baslik_test.py`, `chrome_ekle_test.py`, `daemon_test.py`, `extension_test.py`, `port_test.py`, `video_panel_test.py`. Gerçek dış ağ indirmesi gerektiren `tests/smoke.py` ve `tests/api_smoke.py` çalıştırılmadı.

`tests/e2e/senaryolar_test.py`: izole gerçek backend + headless UI ile 11 senaryo geçti (212 saniye). Tarayıcı kapanışında mevcut test altyapısından `TargetClosedError` / açık dosya uyarıları basıldı; çıkış kodu 0.

Son toplam (yeniden koşular dahil, dosya/takım bazında): **77 geçti, 1 başarısız (`guc_test.py`), 8 çalıştırılmadı**. Bu sayıya yeni yerleşim testi, E2E takımı ve çalıştırılmayan iki smoke betiği dahildir. Canlı arayüz ve gerçek sürüm derlemesinin test edildiği anlamına gelmez.

## Dosyalar

`app.py`, `api/server.py`, `core/kaydet.py`, `core/lang.py`, `ui/app.js`, `ui/i18n.js`, `ui/download.html`, `ui/download.js`, `extension/background.js`, `extension/download-handoff.js`, `AfuDM.spec`, `scripts/build_exe.ps1`, `scripts/build_release.ps1`, `scripts/verify_release.ps1`, `scripts/verify_exe.py`, `scripts/test.ps1`, `scripts/pre_push_test.ps1`, `tests/paket_import_test.py`, `tests/download_window_test.py`, `tests/download_window_ui_test.mjs`, `tests/download_window_layout_test.py`, `tests/pdf_handoff_http_test.py`, `tests/extension_download_handoff_test.mjs`, `tests/_download_audit_runner.py`, bu rapor.

Doğrulanamayanlar: canlı Windows X/Alt+F4 ile gerçek pencere davranışı, yeni derlenmiş EXE/sürüm ZIP'i, özgün bildirilen PDF hatasının nedeni, API tamamen erişilemezken olay kaydına yazma.
