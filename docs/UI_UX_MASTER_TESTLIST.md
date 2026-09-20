## AfuDM — Kalıcı UI/UX Master Test Listesi

### Test işaretleri

```text
[ ] Test edilmedi
[x] Geçti
[!] Hata bulundu
[-] Bu sürümde uygulanamaz

P0 = release engelleyici
P1 = önemli
P2 = polish / iyileştirme
```

---

# 0. RELEASE GATE — Her sürümde zorunlu

|ID|Test|Öncelik|
|---|---|---|
|G-001|[x] Uygulama temiz Windows ortamında açılıyor|P0|
|G-002|[x] Açılışta beyaz/boş ekran oluşmuyor|P0|
|G-003|[x] Browser console'da uncaught JS error yok|P0|
|G-004|[x] Bozuk HTML / kapanmamış tag yok|P0|
|G-005|[x] Görünen bütün butonlar tıklanabiliyor|P0|
|G-006|[x] Tıklanan buton doğru aksiyonu yapıyor|P0|
|G-007|[x] Gizli panel başka panelin içinde kalmıyor|P0|
|G-008|[x] Açılan bütün modal/paneller kapanabiliyor|P0|
|G-009|[x] `Esc` ile uygun modal kapanıyor|P1|
|G-010|[x] Backdrop tıklaması doğru davranıyor|P1|
|G-011|[x] UI donmadan backend hatası gösterebiliyor|P0|
|G-012|[x] aria2 kapanırsa UI kilitlenmiyor|P0|
|G-013|[x] aria2 tekrar bağlanınca UI toparlanıyor|P0|
|G-014|[x] Uygulama kapanıp açılınca state bozulmuyor|P0|
|G-015|[x] TR ve EN arayüzlerinin ikisi de açılıyor|P0|

**Kural:** `P0` testlerinden biri başarısızsa release yapılmaz.

---

# 1. Ekran boyutu / Windows DPI

Aşağıdaki kombinasyonların tamamı sürekli test edilmeli:

```text
1280×720
1366×768
1920×1080
2560×1440
Ultrawide

DPI:
100%
125%
150%
175%
200%
```

Kontroller:

- [x] Toolbar ekrandan taşmıyor (1280x720, 1366x768, 1920x1080; 125/150/200% DPI).
- [ ] Sidebar kesilmiyor.
- [ ] Sidebar gerektiğinde scroll oluyor.
- [ ] Modal ekranın dışına çıkmıyor.
- [ ] Buton yazıları kesilmiyor.
- [ ] Türkçe uzun metinler layout'u bozmuyor.
- [ ] Search alanı ezilmiyor.
- [ ] Download kartları üst üste binmiyor.
- [ ] Fontlar okunabilir.
- [ ] Minimum pencere boyutunda uygulama kullanılabilir.
- [ ] Pencere büyüyünce gereksiz dev boşluklar oluşmuyor.

---

# 2. Ana ekran

### Sidebar

```text
Tümü
İndiriliyor
Duraklatıldı
Video
Torrent
Bitti
Hata

────────────

İndirme klasörünü aç
Chrome'a ekle
Eklentiler
Sunucu
Ayarlar
Kuralları yönet
```

Test:

- [ ] Aktif bölüm belirgin.
- [ ] Sayaçlar doğru.
- [ ] Sayaç `0` olduğunda layout bozulmuyor.
- [ ] Tümü doğru işleri gösteriyor.
- [ ] İndiriliyor filtresi doğru.
- [ ] Duraklatıldı filtresi doğru.
- [ ] Video doğru.
- [ ] Torrent doğru.
- [ ] Bitti doğru.
- [ ] Hata doğru.
- [ ] Alt araç bölümü download filtrelerinden görsel olarak ayrılmış.
- [ ] Uzun sidebar küçük ekranda scroll oluyor.
- [ ] Seçim değişince yanlış eski içerik kalmıyor.

### Toolbar

- [ ] `Link ekle`
- [ ] `Link yakala`
- [ ] `Tümünü duraklat`
- [ ] `Tümünü sürdür`
- [ ] `Bitenleri temizle`
- [ ] `Listede ara`

UX kuralları:

```text
Link ekle         = Primary
Link yakala       = Secondary
Toplu aksiyonlar  = Normal
Tehlikeli aksiyon = Warning/Danger
```

- [ ] Aktif download yoksa `Tümünü duraklat` disabled.
- [ ] Duraklatılmış download yoksa `Tümünü sürdür` disabled.
- [ ] Bitmiş download yoksa `Bitenleri temizle` disabled/gizli.
- [ ] Search sonuç vermiyorsa düzgün empty state gösteriyor.

---

# 3. Empty / Loading / Error state

Her ekranın üç durumu zorunlu:

### Empty

```text
Kuyruk boş.

Link ekleyerek başlayın.

[+ Link ekle]
```

- [ ] Düz boş tablo gösterilmiyor.
- [ ] Kullanıcıya ne yapacağı söyleniyor.

### Loading

```text
Bağlantı kontrol ediliyor…
```

- [ ] Kullanıcı tıklamanın işlendiğini anlayabiliyor.
- [ ] Aynı işlem yanlışlıkla iki kez başlatılamıyor.

### Error

Yanlış:

```text
aria2 errorCode=3
```

Doğru:

```text
Bağlantı artık geçerli değil.

[URL'yi Yenile] [Tekrar Dene] [Detay]
```

- [ ] Teknik hata kullanıcı diline çevriliyor.
- [ ] Detay isteyen kullanıcı teknik mesajı görebiliyor.
- [ ] Retry butonu gerçekten çalışıyor.

---

# 4. Link Ekle / Yeni İndirme

- [ ] HTTP URL
- [ ] HTTPS URL
- [ ] FTP URL
- [ ] Magnet
- [ ] Torrent
- [ ] Video URL

URL yapıştırınca:

- [ ] URL tanınıyor.
- [ ] Dosya adı bulunuyor.
- [ ] Tür belirleniyor.
- [ ] Boyut mümkünse gösteriliyor.
- [ ] Kategori belirleniyor.
- [ ] Klasör seçilebiliyor.
- [ ] Yeni klasör oluşturulabiliyor.
- [ ] Disk seçilebiliyor.
- [ ] Start now çalışıyor.
- [ ] Scheduled start çalışıyor.
- [ ] İptal çalışıyor.

Advanced:

- [ ] Connections
- [ ] Speed limit
- [ ] Proxy
- [ ] Checksum
- [ ] Referer
- [ ] User-Agent
- [ ] Headers
- [ ] Authentication
- [ ] Schedule

Advanced kapalıyken yeni kullanıcı gereksiz teknik bilgi görmemeli.

---

# 5. Download kartı / satırı

Ana listede öncelikle:

```text
Dosya adı
Progress
Hız
İndirilen / toplam
ETA
Durum
```

Test:

- [ ] Dosya adı düzgün truncate oluyor.
- [ ] Hover/tooltip ile tam adı görülebiliyor.
- [ ] Progress doğru.
- [ ] `0 B/s` düzgün.
- [ ] ETA bilinmiyorsa saçma değer göstermiyor.
- [ ] Pause çalışıyor.
- [ ] Resume çalışıyor.
- [ ] Cancel çalışıyor.
- [ ] Retry çalışıyor.
- [ ] Open file çalışıyor.
- [ ] Open folder çalışıyor.
- [ ] Copy URL çalışıyor.
- [ ] Delete yalnız listeden / diskten sil seçeneklerini ayırıyor.

---

# 6. LinkGrabber — v1.5

- [ ] Manuel metinden link çıkarılıyor.
- [ ] Clipboard.
- [ ] Browser → LinkGrabber.
- [ ] Page links.
- [ ] Selected links.
- [ ] HTTP.
- [ ] HTTPS.
- [ ] FTP.
- [ ] Magnet.
- [ ] Normalize.
- [ ] Duplicate URL.
- [ ] Magnet infohash duplicate.
- [ ] Domain filter.
- [ ] Type filter.
- [ ] Size filter.
- [ ] Search.
- [ ] `*` wildcard.
- [ ] `?` wildcard.
- [ ] Turkish search.
- [ ] Select all.
- [ ] Deselect all.
- [ ] Invert selection.
- [ ] Batch add.
- [ ] Previously downloaded badge.
- [ ] Probe.
- [ ] Probe cancel.
- [ ] Probe timeout.
- [ ] Probe cache.
- [ ] HEAD fallback.
- [ ] 1000+ linkte UI donmuyor.
- [ ] Panel kapanınca probe worker'ları kalmıyor.

---

# 7. Video Pro — v1.6

### Analyze

- [ ] URL analyze.
- [ ] Thumbnail.
- [ ] Title.
- [ ] Uploader.
- [ ] Duration.
- [ ] Format list.

### Quality

- [ ] Best.
- [ ] 4K.
- [ ] 1440p.
- [ ] 1080p.
- [ ] 720p.
- [ ] Audio only.
- [ ] Codec.
- [ ] Container.

### Video Pro

- [ ] Manual subtitles.
- [ ] Auto subtitles.
- [ ] Subtitle language.
- [ ] Embed subtitle.
- [ ] Thumbnail download.
- [ ] Thumbnail embed.
- [ ] Metadata.
- [ ] Chapters.
- [ ] SponsorBlock.
- [ ] Section/time range.
- [ ] Audio format.
- [ ] Filename template.
- [ ] Browser cookies.

### Playlist

- [ ] Playlist algılanıyor.
- [ ] Item listesi.
- [ ] Select all.
- [ ] Tek tek seçim.
- [ ] Range.
- [ ] Büyük playlistte UI donmuyor.

### UX

- [ ] ffmpeg yoksa anlaşılır mesaj.
- [ ] Login gerekiyorsa anlaşılır mesaj.
- [ ] Cookies gerekiyorsa kullanıcı yönlendiriliyor.
- [ ] Unsupported URL düzgün hata veriyor.
- [ ] Video post-processing aşamaları görünür.

---

# 8. Torrent Pro — v1.7

### Torrent opening

- [ ] `.torrent`
- [ ] Magnet
- [ ] Magnet metadata loading
- [ ] Private flag

### Files

- [ ] File tree.
- [ ] Folder selection.
- [ ] File selection.
- [ ] Priority.
- [ ] Skip.
- [ ] Search.
- [ ] Türkçe search.
- [ ] 1000+ files.
- [ ] 250-file limit logic.

### Metrics

- [ ] Seeds.
- [ ] Peers.
- [ ] Connected.
- [ ] Download speed.
- [ ] Upload speed.
- [ ] Ratio.
- [ ] Uploaded amount.

### Tabs

```text
Overview
Files
Trackers
Logs
```

- [ ] Hepsi bağımsız açılıyor.
- [ ] Poll timer panel kapanınca temizleniyor.
- [ ] Stale response eski paneli bozmuyor.
- [ ] Magnet metadata sonradan gelince UI güncelleniyor.

### Trackers

- [ ] Add.
- [ ] Remove.
- [ ] Dedupe.
- [ ] Health.
- [ ] Reannounce.
- [ ] Tracker Boost.

### Private torrent

- [ ] Public tracker injection yok.
- [ ] DHT force yok.
- [ ] PEX force yok.
- [ ] UI'da private badge var.

---

# 9. Mobile/PWA — v1.7.5

Telefon testleri:

```text
Android Chrome
Android installed PWA
Desktop Chrome mobile emulation
```

- [ ] QR pairing.
- [ ] Pairing başarısız state.
- [ ] Token invalid state.
- [ ] Token expired state.
- [ ] Re-pair.
- [ ] Add URL.
- [ ] Add video.
- [ ] Add magnet.
- [ ] Pause.
- [ ] Resume.
- [ ] Cancel.
- [ ] Speed.
- [ ] Progress.
- [ ] Seed/peer.
- [ ] Snail.
- [ ] Normal.
- [ ] Turbo.
- [ ] Notifications.
- [ ] Offline shell.
- [ ] Mobile browser back butonu.
- [ ] Popup/modal telefonda ekrandan taşmıyor.
- [ ] Touch target minimum yeterli.
- [ ] Keyboard açıldığında form kaybolmuyor.
- [ ] Portrait.
- [ ] Landscape.

---

# 10. Phone Download — v2.4

Yeni özellik için ayrıca:

```text
Hedef
○ Bu bilgisayara
● Bu telefona
```

- [ ] Telefona indir seçeneği görünüyor.
- [ ] PC klasör seçiminden ayrı anlaşılıyor.
- [ ] HTTP dosyası telefona aktarılıyor.
- [ ] Video telefona aktarılıyor.
- [ ] Audio telefona aktarılıyor.
- [ ] Büyük dosya.
- [ ] HTTP Range.
- [ ] İndirme yarıda kesilip resume.
- [ ] Token süresi.
- [ ] Geçersiz token.
- [ ] Kullanıcı filesystem path gönderemiyor.
- [ ] Geçici dosya cleanup.
- [ ] Hazırlanıyor state.
- [ ] Hazır state.
- [ ] Telefona Kaydet butonu.
- [ ] Transfer başarısız state.
- [ ] Tekrar dene.
- [ ] Telefon depolama permission/browser davranışı anlaşılır.

---

# 11. Settings

### Genel

- [ ] Sekmeler çalışıyor.
- [ ] Search.
- [ ] Türkçe search.
- [ ] Değişiklik anında uygulanıyorsa uygulanıyor.
- [ ] Restart gerekiyorsa belirtiliyor.
- [ ] Save state doğru.

### Kontroller

- [ ] Language.
- [ ] Download directory.
- [ ] Category folders.
- [ ] Connections.
- [ ] Speed.
- [ ] Snail speed.
- [ ] Clipboard.
- [ ] Proxy.
- [ ] System proxy.
- [ ] API port.
- [ ] Remote access.
- [ ] Tracker health.
- [ ] Engines.
- [ ] Start with Windows.
- [ ] Start minimized/tray.
- [ ] File associations.

### Engines

- [ ] aria2 status.
- [ ] yt-dlp install.
- [ ] yt-dlp update.
- [ ] FFmpeg install.
- [ ] Download progress.
- [ ] Failure.
- [ ] Retry.
- [ ] Installed version gösteriliyor.

---

# 12. Automation — v1.8

Her action için üç durum test edilir:

```text
başarılı
başarısız
restart sonrası devam
```

Actions:

- [ ] Checksum.
- [ ] Defender.
- [ ] ZIP extract.
- [ ] RAR extract.
- [ ] 7z extract.
- [ ] Move.
- [ ] Rename.
- [ ] Script.
- [ ] Notification.
- [ ] Sleep.
- [ ] Shutdown.

UX:

- [ ] Pipeline sırası anlaşılır.
- [ ] Action durumu görülebilir.
- [ ] Hatalı action diğer downloadları kilitlemiyor.
- [ ] Retry.
- [ ] Skip.
- [ ] Log.

---

# 13. Rules — v1.9

Conditions:

- [ ] Domain.
- [ ] Extension.
- [ ] Filename.
- [ ] Size.
- [ ] Protocol.
- [ ] Category.

Actions:

- [ ] Folder.
- [ ] Proxy.
- [ ] Speed.
- [ ] Connections.
- [ ] Schedule.
- [ ] Headers.
- [ ] Post-process.
- [ ] Video options.
- [ ] Torrent options.

UX:

- [ ] Rule add.
- [ ] Edit.
- [ ] Delete.
- [ ] Enable/disable.
- [ ] Priority/order.
- [ ] Conflict gösteriliyor.
- [ ] Test rule.
- [ ] “Bu link hangi kurala eşleşti?” görünür.

---

# 14. Plugins — v2.0

- [ ] Install plugin.
- [ ] Remove.
- [ ] Enable.
- [ ] Disable.
- [ ] Update.
- [ ] Permission display.
- [ ] Domain permission.
- [ ] Version.
- [ ] Minimum AfuDM.
- [ ] Invalid plugin.
- [ ] Plugin crash.
- [ ] Plugin app'i çökertmiyor.
- [ ] Plugin error UI.
- [ ] SHA verification varsa çalışıyor.

---

# 15. Headless — v2.1

Web UI:

- [ ] Login/access key.
- [ ] Wrong key.
- [ ] Expired/rotated key.
- [ ] Administrator.
- [ ] Read-only.
- [ ] Read-only kullanıcı değiştirme yapamıyor.
- [ ] Add.
- [ ] Pause.
- [ ] Resume.
- [ ] Delete.
- [ ] LinkGrabber.
- [ ] Video.
- [ ] Torrent.
- [ ] Settings.
- [ ] Server offline.
- [ ] Reconnect.

UX:

```text
Server disconnected
Reconnecting…
Connected
```

durumları görünür olmalı.

---

# 16. Windows Integration — v2.2

- [ ] Start with Windows.
- [ ] Tray.
- [ ] Restore.
- [ ] Minimize to tray.
- [ ] Exit.
- [ ] Windows notifications.
- [ ] `.torrent` association.
- [ ] `magnet:`.
- [ ] `afudm://`.
- [ ] Explorer right click.
- [ ] Browser Native Messaging.
- [ ] AfuDM kapalıyken browser isteği.
- [ ] App doğru şekilde açılıyor.
- [ ] Second instance oluşmuyor.
- [ ] Existing instance foreground oluyor.

---

# 17. Reliability — v2.3

- [ ] PC zorla kapatılır.
- [ ] AfuDM taskkill.
- [ ] aria2 taskkill.
- [ ] DB yarım yazma simülasyonu.
- [ ] Corrupted `.aria2`.
- [ ] Interrupted HTTP.
- [ ] Interrupted video.
- [ ] Interrupted torrent.
- [ ] Restart.
- [ ] Recovery.
- [ ] Settings backup.
- [ ] Restore.
- [ ] Diagnostics export.
- [ ] Logs.
- [ ] Sensitive data redaction.
- [ ] API token loglanmıyor.
- [ ] Cookie loglanmıyor.
- [ ] Proxy password loglanmıyor.

---

# 18. Browser Extension

- [ ] Chrome install.
- [ ] Edge install.
- [ ] Pair.
- [ ] Unpair.
- [ ] Browser download interception.
- [ ] Normal HTTP.
- [ ] Login-required site.
- [ ] Cookie transfer.
- [ ] Right click.
- [ ] Send page links.
- [ ] Send selected links.
- [ ] Video overlay.
- [ ] Embedded player.
- [ ] AfuDM closed → browser normal downloads.
- [ ] AfuDM running → interception.
- [ ] Wrong/stale token.
- [ ] Extension update.
- [ ] Sensitive headers unrelated domains'a sızmıyor.

---

# 19. Accessibility / Keyboard

Bu bölümü özellikle kalıcı tut:

- [ ] Tab.
- [ ] Shift+Tab.
- [ ] Enter.
- [ ] Space.
- [ ] Escape.
- [ ] Arrow keys gereken yerlerde.
- [ ] Focus görünür.
- [ ] Modal açılınca focus modal içine geçiyor.
- [ ] Modal kapanınca önceki elemente dönüyor.
- [ ] Radio/checkbox keyboard kullanılabilir.
- [ ] Icon-only butonlarda tooltip/accessible label var.
- [ ] Renk tek bilgi kaynağı değil.

---

# 20. TR / EN / metin testi

- [ ] Tüm key'ler TR.
- [ ] Tüm key'ler EN.
- [ ] Hardcoded Türkçe metin yok.
- [ ] Hardcoded İngilizce metin yok.
- [ ] `İ / I / ı / i` search.
- [ ] Uzun İngilizce metin layout bozmaz.
- [ ] Uzun Türkçe metin layout bozmaz.
- [ ] `%`, GB, MB/s, saat biçimleri tutarlı.

---

# 21. Görsel tutarlılık

Her ekran aynı design system'i kullanmalı:

```text
Primary button
Secondary button
Danger button
Input
Select
Checkbox
Radio
Tabs
Badge
Toast
Modal
Drawer
Progress
Empty state
Loading
Error
Tooltip
```

Kontrol:

- [ ] Border radius tutarlı.
- [ ] Padding tutarlı.
- [ ] Font size hiyerarşisi.
- [ ] Icon size.
- [ ] Disabled opacity.
- [ ] Hover.
- [ ] Active.
- [ ] Focus.
- [ ] Danger.
- [ ] Dark theme contrast.
- [ ] Sidebar ve content aynı grid sisteminde.

---

# 22. Performans UX testleri

Özel olarak şunlarla test ettir:

```text
1 download
10 download
100 download
1.000 download

10 LinkGrabber URL
100 URL
1.000 URL

10 torrent files
1.000 torrent files
10.000 torrent files

10 playlist entries
500 playlist entries
```

Kontrol:

- [ ] Scroll akıcı.
- [ ] Typing gecikmiyor.
- [ ] Search donmuyor.
- [ ] CPU anormal yükselmiyor.
- [ ] Polling gereksiz çalışmıyor.
- [ ] Kapalı modal timer bırakmıyor.
- [ ] Memory sürekli artmıyor.

---

# 23. Kritik “Click Everything” testi

Bunu otomatik browser testine özellikle koy:

```text
Her görünür:
button
a
input
select
checkbox
radio
tab
menu item
context action

→ bulunur
→ visible mı?
→ enabled mı?
→ click edilir
→ JS exception oluştu mu?
→ beklenen UI state değişti mi?
```

Bu test senin son yaşadığın:

```text
bozuk HTML
↓
JS yüklenmedi
↓
bütün butonlar öldü
```

problemini release'e çıkmadan yakalamalı.

---

# 24. Modal lifecycle testi

**Her modal/panel için aynı test:**

```text
OPEN
↓
visible
↓
focus
↓
action
↓
close button
↓
reopen
↓
Esc
↓
reopen
↓
backdrop
↓
reopen
↓
backend error
↓
close
```

Ve sonra:

```text
timer kaldı mı?
event listener duplicate oldu mu?
network polling kaldı mı?
body scroll kilidi kaldı mı?
```

kontrol edilir.

---

# 25. Yeni özellik eklenirken zorunlu UX checklist

Bundan sonra AfuDM'ye **hangi özellik eklenirse eklensin**, PR'da şu mini-template doldurulsun:

```text
FEATURE:
________________________

[ ] Normal state
[ ] Empty state
[ ] Loading state
[ ] Error state
[ ] Disabled state
[ ] Success feedback
[ ] Cancel
[ ] Retry
[ ] Keyboard
[ ] Mobile/narrow
[ ] DPI 150%
[ ] Turkish
[ ] English
[ ] Backend offline
[ ] Restart
[ ] Browser console clean
[ ] Automated interaction test
```

Bu bölüm kalıcı checklist'in en önemli parçalarından biri.

---

# Release öncesi tek cümlelik kural

AfuDM release'i ancak şu koşullarda UI/UX açısından **PASS** sayılsın:

```text
0 P0 failure
0 uncaught JS error
0 broken click target
0 inaccessible modal
0 malformed DOM
TR + EN PASS
1280×720 PASS
1920×1080 PASS
150% DPI PASS
Keyboard smoke PASS
Main feature smoke PASS
```

---

## Son otomatik UI/UX Gate özeti (2026-09-20)

- [x] 10/10 UI/UX Gate testi geçti: G-001--G-015, görünür kontroller, modal yaşam döngüsü, TR/EN ve responsive/DPI.
- [x] 3/3 başlangıç UI testi geçti.
- [x] P0 failure: 0; uncaught JS error: 0; broken click target: 0; modal failure: 0.
- [x] Tamamlanan responsive seti: 1280x720, 1366x768, 1920x1080; 125%, 150%, 200% DPI.
- [ ] Bu listede işaretlenmemiş özellik-spesifik manuel testler (indirici, torrent, mobil, eklenti vb.) bu release gate'in kapsamı dışındadır.
