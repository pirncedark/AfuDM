# Görev 3A — 30 Eylül 2026

Dal `fix/pdf-ve-cift-indirme` korundu. Önceki değişiklikler korundu; commit/push/merge, dal değiştirme, EXE üretimi, canlı uygulamayı kapatma ve görünür pencere açma yapılmadı.

## Adım 1: önceki sekiz kusurun kod denetimi

| Madde | Başlangıçtaki durum ve kanıt |
|---|---|
| 1. Gizli pencerenin çıkışı engellemesi | Kodda çözülmüş: `app.py:1501` ana pencerenin gerçek kapanışında çıkış bayrağı ve yardımcı pencere temizliği; `app.py:1894` closed bağlantısı. Güncelleme `app.py:357`, tepsi çıkışı `app.py:1758` aynı ana pencereyi kapatıyor. |
| 2. İndirme penceresi X/Alt+F4 | Pencere tekrar kullanılabiliyordu ama istek yanlışlıkla iptal ediliyordu. Bu tur düzeltildi: `app.py:1633` yalnız gizler, kuyruğu korur; `app.py:1605` gizliyken yoklama pencereyi açamaz. |
| 3. Tek onay ve kaynak ayrımı | Kodda çözülmüş: `app.py:599` tarayıcı yolu; `ui/app.js:2687` tarayıcıları ana panelden çıkarır; `ui/download.js:32` yalnız tarayıcıları gösterir. Masaüstü yolu korunuyor. |
| 4. PDF kategori/klasör | Kodda çözülmüş: `app.py:379`, `core/kaydet.py:43`; dosya adıyla kategori belirleniyor. Gerçek HTTP/PDF testleri mevcut. Özgün canlı PDF sorununun birebir sebebi kanıtlanmış değil. |
| 5. Video kalite/ses | Kodda çözülmüş: `app.py:635`, `ui/download.js:67`, `ui/download.js:96`; değiştirilmeyen değerler korunuyor. |
| 6. Dil, hata ve yerleşim | Kodda çözülmüş: `ui/i18n.js:20` ve `:870`, `ui/download.js:30`, `:106`; TR/EN yerleşim testi var. |
| 7. Paketleme | Kaynak/paket kapıları çözülmüş: `AfuDM.spec:82`, `scripts/verify_exe.py:11`, `tests/paket_import_test.py`. Yeni gerçek EXE derlemesi yapılmadı. |
| 8. Hata kaydı ve tarayıcıya geri dönüş | Mevcut HTTP/onay hata kayıtları: `api/server.py:203`, `app.py:616`. Başarısız/uygun olmayan devirde resume vardı; zaman aşımı sınırı eksikti, bu tur eklendi (`extension/background.js:115`, `:133`, `extension/download-handoff.js:7`). API tamamen kapalıyken ona hata kaydı gönderilemez. |

`download_audit_results*.json` önceki izole denetimlerin üretilmiş test çıktılarıdır; kaynak commit'ine önerilmez. `tests/_download_audit_runner.py` testleri geçici yollarla çalıştırır, canlı data yazmasını engeller, isteğe bağlı dış fontları yerel boş yanıtla karşılar; tekrar kullanılabilir test aracı olarak commit'e girebilir, üretim paketine gerekmez. `_gorev/sonra_agda_paylas.png` görev ekran görüntüsüdür; uygulamanın çalışma girdisi değildir, kaynak commit'ine önerilmez. Hiçbiri silinmedi. Yeni UI, devir yardımcı dosyası, testler ve ilgili kaynak/build değişiklikleri özellik için gereklidir; diğer AfuTube görev dosyaları bu tur kapsam dışıdır.

## Adım 2–4

- X/Alt+F4 gizler, isteği korur; yeni tarayıcı isteği veya ana pencerenin tekrar gösterilmesi bekleyen onayı açar. Gizliyken JS yoklaması durur. Vazgeç açıkça iptal eder.
- Ana pencere gerçek kapanışı, güncelleme ve tepsi çıkışı gizli pencereyi bir kez yok eder; tepsiye küçültme tercihi korunur. Mock pencere ve gerçek tepsi callback'iyle 15 yaşam döngüsü/onay testi geçti. Canlı Windows sürecinin gerçek kapanışı kullanıcı kısıtı gereği çalıştırılmadı.
- Chrome başarılı kabul yanıtından önce iptal edilmez. HTTP gönderiminde 10 sn, hata raporunda 3 sn, devrin uygunluk/gönderim aşamalarında 15 sn sınır var. Reddetme, kapalı uygulama ve zaman aşımı Chrome'u devam ettirir. Kabul edilen indirme kimliği uzantı worker belleğinde tekrar devredilmez; mevcut eşzamanlı URL ve 5 sn URL kontrolü korunur.
- Ana panelin browser filtresi ve indirme penceresinin browser filtresi tek onayı korur; UI ve devretme regresyonları geçti.

## Kalan riskler

Bekleyen istekler yalnız bellektedir (`core/kaydet.py:196`); çıkışta kaybolur ve 30 dakika sonunda temizlenir. Chrome kabul yanıtından sonra iptal edilmişse bu istek tarayıcıdan otomatik geri alınamaz. Görevde izin verilen seçenek doğrultusunda bu risk açıkça raporlandı; kalıcılık veya çıkış onayı eklenmedi. HTTP yanıtının kaybolması/zaman aşımı sunucunun isteği almamış olduğunu kanıtlamaz: Chrome devam ederken AfuDM tarafında da bekleyen istek kalabilir. Worker yeniden başlatılınca kimlik deduplikasyon belleği sıfırlanır. Kalıcı sunucu idempotency/işlemsel devir bu tur yapılmadı.

Bu tur değişen dosyalar: `app.py`, `ui/download.js`, `extension/background.js`, `extension/download-handoff.js`, `tests/download_window_test.py`, `tests/extension_download_handoff_test.mjs`, bu rapor.

## Doğrulama

`scripts/test.ps1` listesinin tamamı çalıştırıldı: **57 test dosyası geçti, 0 başarısız**, çıkış kodu 0. Python çağrıları aynı testleri `tests/_download_audit_runner.py` üzerinden geçici veri yollarıyla yürüttü; `AFUDM_AUDIT_OFFLINE_FONTS=1`, `PYTHONUTF8=1`. Test beklentileri ve üretim güvenlik kodu değiştirilmedi. Python yaşam döngüsü 15 test, iki JavaScript regresyon dosyası ve `git diff --check` geçti.
