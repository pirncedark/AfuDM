# Chrome → AfuDM Tek Pencere Uygulama Planı

> Uygulama yöntemi: Bu oturumda doğrudan uygulama; mevcut kullanıcı değişiklikleri korunur. Her görev kendi davranış testiyle doğrulanır.

**Hedef:** Desteklenen indirme bağlantılarında Chrome kaydetme penceresi ve paralel indirme oluşturmadan tek AfuDM penceresine aktarım.

**Mimari:** Belge başlangıcındaki içerik betiği uygun bağlantının tıklamasını durdurur. Arka plan işçisi mevcut `/add` sınırını kullanır; aynı istekler birleştirilir. Mevcut `downloads.onCreated` yolu önceden tanınamayan indirmeler için korunur.

**Teknolojiler:** Chrome Manifest V3, JavaScript, Python, aria2, Playwright.

**Tasarım:** `docs/superpowers/specs/2026-10-09-chrome-afudm-single-handoff-design.md`

## Ortak kurallar

- Kullanıcı bir kez basar; uygulama aktarımı ve doğru pencereyi yönetir.
- Normal sayfa bağlantıları, eklenti kapalıyken yapılan tıklamalar ve sayfa görselleri engellenmez.
- Çerezler ve yetkilendirme bilgileri kalıcı kayda yazılmaz.
- Belirsiz kabul/timeout yanıtında körlemesine Chrome indirmesi başlatılmaz: AfuDM kabul etmiş olabilir. İstek kimliğiyle sonuç sorgulanır veya yeniden deneme gösterilir.
- Uygulama kapalıyken sessiz kayıp olmaz; açık hata ve yeniden deneme sağlanır.
- Kullanıcı profili ve canlı indirme verileri testlerde kullanılmaz.
- `test_cancel.js` mevcut kullanıcı dosyasıdır; değiştirilmez veya commit edilmez.

## İncelemede özellikle kontrol edilecekler

1. Yönlendirmeli ve uzantısız bağlantılar: normal gezinme yanlışlıkla indirme sayılmaz.
2. Ctrl/Shift/orta tuş ve iframe tıklamaları: kullanıcının normal gezinme davranışı korunur.
3. API kabulünden sonra yanıt kaybı: iki motor aynı dosyayı indirmez.
4. Servis işçisinin yeniden başlaması: aynı istek ikinci bekleyen kayıt oluşturmaz.
5. Magnet, torrent ve bilinçli görsel indirme: doğru tür ve tek kayıt korunur.

## Görev 1 — Tıklama anında aktarım (8–12 dakika)

**Dosyalar:** Yeni `extension/download-preflight.js`; mevcut `extension/manifest.json`, `extension/background.js`; yeni `tests/extension_preflight_test.mjs`.

**Sınır:** İçerik betiği `{type:'downloadPreflight', payload:{url,filename,kind,request_id}}` gönderir. İşçi `{ok,pending,id,error,retryable}` döndürür. Sayfa referansı işçide `sender` üzerinden alınır; sayfadan gelen serbest başlıklar kabul edilmez.

- [ ] Gerçek içerik betiğini çalıştıran testte ZIP/PDF/download-nitelikli bağlantının varsayılanını engellediğini, normal sayfa ve görsel bağlantısını geçirdiğini göster.
- [ ] Eklenti kapalı, tuş değiştiricileri, iframe, magnet ve `.torrent` senaryolarını ekle; ilk test çalışmasında eksik davranışı gör.
- [ ] Betiği `document_start` ile yükle; tıklamayı yalnız uygun adaylarda yakala. Etkinlik ayarını önceden yükle ve değişikliklerde güncelle.
- [ ] İşçide mesajı doğrula, hedef URL için mevcut çerez politikasını kullan ve `sendToAfudm` üzerinden gönder.
- [ ] Testi çalıştır: `node tests/extension_preflight_test.mjs`.

## Görev 2 — Tek istek ve güvenilir kabul (8–12 dakika)

**Dosyalar:** `extension/background.js`, `extension/download-handoff.js`, `api/server.py`, `core/kaydet.py`; `tests/pdf_handoff_http_test.py`, `tests/pending_persistence_test.py`, `tests/extension_download_handoff_test.mjs`.

**Sınır:** `/add` isteği `request_id` taşır. Aynı kimliğe gelen tekrar aynı kabul sonucunu döndürür. Bekleyen ve onaylanmış sonuçlar güvenli alanlarla saklanır; çerezler saklanmaz.

- [ ] Aynı isteğin eşzamanlı ve tekrar gönderiminde tek bekleyen/kayıt oluştuğunu gerçek HTTP sınırında test et.
- [ ] Farklı dosyaların ayrı kayıt oluşturmasını ve bilinçli yeniden indirmeyi test et.
- [ ] Kısa süreli tıklama birleştirmesini ve sunucu tarafında atomik istek kimliği kontrolünü uygula.
- [ ] Kabul sonrası yanıt kaybını test et; tekrar aynı kimlikle yapılır ve ikinci iş oluşmaz.
- [ ] Mevcut `onCreated` geri dönüşünü çalıştır; yalnız kesin reddedilen isteklerde Chrome'a dönüş sağla.
- [ ] Testler: `node tests/extension_download_handoff_test.mjs`; `python scripts/run_isolated_test.py tests/pdf_handoff_http_test.py`; `python scripts/run_isolated_test.py tests/pending_persistence_test.py`.

## Görev 3 — Torrent ve indirme bilgileri (5–8 dakika)

**Dosyalar:** `app.py`, `ui/download.js`, gerekirse `core/manager.py`; `tests/download_window_test.py`, `tests/download_window_ui_test.mjs`, `tests/indirme_metrik_test.py`.

- [ ] Otomatik aktarımın `.torrent` ve magnet türünü doğru belirlediğini test et; mevcut sabit `kind:'http'` gönderimini düzelt.
- [ ] Sayfa kapaklarının iş oluşturmadığını ve açık görsel indirme eyleminin çalıştığını doğrula.
- [ ] Boyutu bilinen/bilinmeyen, durmuş/devam eden/tamamlanan işlerde gerçek boyut-hız-süre gösterimini mevcut metrik testleriyle kontrol et.
- [ ] Yalnız kanıtlanan eksikleri düzelt; ölçüm olmadan hız optimizasyonu ekleme.
- [ ] Testler: `python scripts/run_isolated_test.py tests/download_window_test.py`; `node tests/download_window_ui_test.mjs`; `python scripts/run_isolated_test.py tests/indirme_metrik_test.py`.

## Görev 4 — Gerçek tarayıcı ve paket doğrulaması (10–15 dakika)

**Dosyalar:** `tests/e2e/chrome_devir_e2e.py`, `tests/paket_import_test.py`, `scripts/test.ps1`, gerekirse `scripts/verify_exe.py` ve paket kontrol betikleri.

- [ ] Yeni test dosyasını standart koşucuya ekle; yeni betiğin ZIP ve EXE içinde bulunduğunu doğrula.
- [ ] İzole Chromium profilinde gerçek bağlantıya tıkla: AfuDM'de tek iş, Chrome'da sıfır indirme olayı, tek dosya ve doğru içerik bekle.
- [ ] Çift tıklama, iki farklı dosya, yönlendirme, erişilemez API ve yanıt kaybını çalıştır. Chrome'un kaydetme tercihini devre dışı bırakan eski E2E ayarı ikinci pencere olmadığının kanıtı sayılmaz.
- [ ] Görünür Chrome ve paketlenmiş AfuDM ile kaydetme penceresi davranışını ayrıca doğrula; otomatik testle elle testi raporda ayrı belirt.
- [ ] Tıklama → gönderim → kabul → motor başlangıcı sürelerini ölç ve rapora yaz.
- [ ] Standart kontrol: `powershell -NoProfile -File scripts/test.ps1`; E2E: `python tests/e2e/chrome_devir_e2e.py`; paket: `python scripts/run_isolated_test.py tests/paket_import_test.py`.

## Görev 5 — Teslim ve GitHub (3–5 dakika)

- [ ] İlgili farkları gözden geçir; `git diff --check` çalıştır.
- [ ] Gerçek test sayıları, kalan sınırlar ve kullanılan paket konumuyla sonuç raporu yaz.
- [ ] Yalnız görev dosyalarını commit et. Kullanıcının önceden verdiği push yetkisiyle normal push yap; force push kullanma.
- [ ] Uzak commit kimliğini doğrula. Başarısız test, elle doğrulanamayan davranış veya push engeli varsa açıkça raporla.

## Plan kontrolü

Onaylanan tasarımın aktarım, tekilleştirme, torrent/görsel, metrik, gecikme, test ve push maddeleri görevlerle eşleştirildi. Bilinmeyen dinamik indirmeler mevcut geri dönüşün sınırıdır; tüm sitelerde ikinci pencerenin engellendiği iddia edilmeyecek. Uygulama başladıktan sonra kanıtlanan yeni riskler planın ilgili görevine eklenecek.
