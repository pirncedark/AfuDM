# AfuDM Gelecek Sürümler UI ve UX Mimari Tasarım Planı (v1.7.5 – v2.3.0)

> **Kullanıcı Kuralı (Değişmez İlke):**  
> *"Bütün eklenen özellikler UI ve UX kısmında KULLANILIR, AYARLANIR ve KONTROL EDİLEBİLİR olsun."*  
> Hiçbir özellik arka planda, görünmez konfigürasyon dosyalarında veya gizli parametrelerde bırakılamaz. Kullanıcı her özelliği arayüzden tetikleyebilmeli, yapılandırabilmeli, durumunu anlık izleyebilmeli ve geçmiş kayıtlarını görebilmelidir.

---

## 1. Giriş ve Tasarım Sistemi Çerçevesi

Bu doküman, AfuDM'in **v1.7.5** ile **v2.3.0** arasındaki yol haritasında yer alan tüm özelliklerin masaüstü ve mobil arayüz karşılıklarını ayrıntılı olarak şartnameye bağlar. Yeni mimari icat edilmemiş; AfuDM'in mevcut **koyu temalı (#16181d zemin, #3b82f6 vurgu rengi)** sol menü (rail), üst araç çubuğu (bar), indirme listesi (list), alt detay çekmecesi (drawer) ve ayarlar modalı (sheet/veil) şablonu genişletilmiştir.

### 1.1 Varlık ve İkon Eşleştirmesi (`assets/afudm-menu-icon-set.svg`)
Hazır bulunan 8 vektörel menü ikonu, UI bileşenleri ve gezinme noktalarıyla birebir eşleştirilmiştir:

| İkon Adı | SVG Glifi / Karakteri | Kullanıldığı UI Yeri | İşlev / Karşılık |
| :--- | :--- | :--- | :--- |
| **Automation** | Dairesel akış + saat ibresi | Sol Menü (`#filterAutomation`), Detay Çekmecesi (`#dTabAutomation`), Ayarlar Sekmesi (`#setTabAutomation`) | Otomasyon kuyruğu, post-processing adımları, çıkarma ve betik çalıştırma |
| **Rules** | Huni / Filtre + kural düğümleri | Sol Menü (`#filterRules`), Detay Çekmecesi (`#dTabRules`), Ayarlar Sekmesi (`#setTabRules`) | Yönlendirme kuralları, regex eşleştirici, kural öncelik sıralaması |
| **Plugins** | Puzzle parçası | Ayarlar Sekmesi (`#setTabPlugins`), Sol Menü Eklenti Görünümü (`#filterPlugins`) | Eklenti yöneticisi, pazar yeri, izin denetimi ve yetki anahtarları |
| **Server** | Rack sunucu çekmeceleri + LED'ler | Ayarlar Sekmesi (`#setTabServer`), Üst Durum Göstergesi (`#serverDot`) | Headless API, uzaktan erişim, kimlik doğrulama anahtarları, NAS bağlantısı |
| **Windows Integration** | Pencere çerçevesi + dişli çark | Ayarlar Sekmesi (`#setTabWindows`) | Başlangıçta çalıştırma, sistem tepsisi, sağ tık kabuk menüsü, Defender entegrasyonu |
| **Security** | Kalkan + kilit gövdesi | Ayarlar Sekmesi (`#setTabSecurity`), Detay Çekmecesi Doğrulama Rozeti | İzin denetimi, token rotasyonu, veri arındırma (redaction), DB onarımı |
| **Scheduler** | Takvim sayfası + analog saat | Detay Çekmecesi Zamanlayıcı, Ayarlar Sekmesi Zaman Planı, İndirme Bilgi Modalı | Saatinde başlatma/durdurma, gece kuyruğu, hız kısıtlama saat dilimleri |
| **Bandwidth** | Hız göstergesi + çift yönlü oklar | Üst Bant İzi (`#traceReadout`), Ayarlar Sekmesi Ağ ve Hız, Hız Profilleri Modalı | Turbo/Normal/Salyangoz profilleri, bağlantı başı hız limitleri, dinamik kısıtlama |

---

## 2. Global Arayüz Mimarisi Genişletmesi

Mevcut HTML (`ui/index.html`), stil (`ui/style.css`) ve JS mimarisine entegre edilecek üç ana genişleme noktası tanımlanmıştır:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ÜST BANT İZİ: Hız Grafiği | Aktif: 2 | Kuyruk: 5 | Paylaşım | [● Motor] [● Server] [PWA: 1 Bağlı]│
├───────────────────┬──────────────────────────────────────────────────────────────────────────────┤
│ SOL MENÜ (RAIL)   │ ARAÇ ÇUBUĞU (BAR): [Link Ekle] [Link Yakala] [Zamanlayıcı] [Hız Profili ▾]  │
│ ───────────────── ├──────────────────────────────────────────────────────────────────────────────┤
│ Tümü              │ İNDİRME LİSTESİ (LIST)                                                       │
│ İndiriliyor       │ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ Duraklatıldı      │ │ [Torrent/Video/Dosya Kartı]  %64  3.2 MB/s  [Boost] [Kurallar] [Oto]    │ │
│ Video             │ └──────────────────────────────────────────────────────────────────────────┘ │
│ Torrent           ├──────────────────────────────────────────────────────────────────────────────┤
│ Otomasyon (v1.8)  │ DETAY ÇEKMECESİ (DRAWER TABS):                                               │
│ Kurallar (v1.9)   │ [Genel Bakış] [Dosyalar] [Trackerlar] [Kurallar] [Otomasyon] [Güvenlik & Log]│
│ Bitti / Hata      │ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ ───────────────── │ │ Tab İçeriği: Canlı kural eşleşmesi, çıkarma durumu, hash doğrulaması     │ │
│ [Klasörü Aç]      │ └──────────────────────────────────────────────────────────────────────────┘ │
│ [Mobil / PWA (QR)]├──────────────────────────────────────────────────────────────────────────────┤
│ [Ayarlar ⚙]       │ AYARLAR MODALI (SEKMELİ SHEET):                                              │
│                   │ [Genel] [Ağ/Hız] [Otomasyon] [Kurallar] [Eklentiler] [Sunucu] [Windows] [Güvenlik]
└───────────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Sürüm Bazlı Özellik-UI Eşleştirme Matrisi

| Sürüm | Özellik | Kullanıcı Ne Yapabilmeli | UI Yeri | Kontrol Tipi | i18n Anahtar Ailesi | Hangi İkon |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **v1.7.5** | PWA / Mobil Remote Web UI | Telefondan tarayıcıyla PC indirmelerini canlı izleyebilmeli, durdurup başlatabilmeli. | Mobil PWA Görünümü (`m.html` / Responsive Shell) | Kart listesi, yüzen buton (FAB), dokunmatik hız kaydırıcı | `mobile.*` (TR+EN) | Server / Bandwidth |
| **v1.7.5** | QR Eşleştirme & Oturum | Tek tıkla ekrandaki dinamik QR'ı okutup token girmeden telefondan yetkili bağlanabilmeli. | Ayarlar Sekmesi: "Mobil / PWA" + Sol Menü Hızlı Butonu | QR modalı, yeniden üret (regenerate) butonu, aktif cihaz tablosu | `mobile.pair.*` (TR+EN) | Security |
| **v1.7.5** | Telefondan İndirme Gönderme | Telefondan link, magnet veya paylaşılan video adresini anında evdeki masaüstüne gönderebilmeli. | PWA Üst Araç Çubuğu "+" Modalı | Çok satırlı metin kutusu, kategori açılır kutusu (select), Gönder butonu | `mobile.add.*` (TR+EN) | Automation |
| **v1.7.5** | Mobil Hız Profili Değişimi | Dışarıdayken ev internetini kilitlememek için tek dokunuşla Turbo / Normal / Salyangoz seçebilmeli. | PWA Alt Gezinme Çubuğu (Bottom Nav) | 3 kademeli segmentli buton (segmented button) | `mobile.speed.*` (TR+EN) | Bandwidth |
| **v1.7.5** | Mobil Torrent Sağlık & Boost | Telefondan torrent eşlerini, seed sayısını görüp tek dokunuşla "Torrent Boost" tetikleyebilmeli. | PWA Torrent Detay Kartı | Vurgulu aksiyon butonu, canlı sayaç rozeti | `mobile.tor.*` (TR+EN) | Bandwidth |
| **v1.8.0** | Otomatik Checksum Doğrulama | İndirme biter bitmez SHA256/MD5/SHA1 değerini orijinal hash ile karşılaştırabilmeli. | İndirme Bilgi Modalı (`#kayVeil`) + Detay Çekmecesi "Otomasyon" | Checkbox, hash giriş alanı, durum doğrulama rozeti (yeşil/kırmızı) | `auto.checksum.*` (TR+EN) | Security |
| **v1.8.0** | Otomatik Arşiv Açma (Extract) | ZIP/RAR/7z inince otomatik belirlediği alt klasöre açıp şifre havuzundan şifre deneyebilmeli. | Ayarlar Sekmesi: "Otomasyon" (`#setTabAutomation`) + Detay Çekmecesi | Anahtar (switch), parola listesi metin alanı, hedef klasör seçici | `auto.extract.*` (TR+EN) | Automation |
| **v1.8.0** | Otomatik Taşıma ve Yeniden Adlandırma | Biten dosyayı şablona göre (`{kategori}/{yil}/{sanatci} - {baslik}`) yeniden adlandırıp taşıyabilmeli. | Ayarlar Sekmesi: "Otomasyon" + Detay Çekmecesi | Etiketli şablon giriş kutusu, önizleme alanı, test butonu | `auto.organize.*` (TR+EN) | Automation |
| **v1.8.0** | Özel Betik Çalıştırma (Hook) | Bittiğinde/hatada `.bat`, `.cmd` veya `.py` betiğini argümanlarla tetikleyebilmeli. | Ayarlar Sekmesi: "Otomasyon" + Detay Çekmecesi "Otomasyon" | Dosya yolu seçici, argüman giriş kutusu, zaman aşımı kaydırıcısı | `auto.script.*` (TR+EN) | Automation |
| **v1.8.0** | Post-Processing Görev Kuyruğu | Arşiv açma, taşıma ve betik adımlarının anlık ilerlemesini, kuyruğunu ve hatasını izleyebilmeli. | Sol Menü: "Otomasyon" Görünümü (`#filterAutomation`) | İşlem durum listesi, yeniden dene butonu, iptal butonu | `auto.queue.*` (TR+EN) | Automation |
| **v1.8.0** | Görev Sonu Eylemi (Uyut/Kapat) | İndirme listesi tamamen boşaldığında veya seçili indirmeler bittiğinde PC'yi kapat/uyut seçebilmeli. | Üst Araç Çubuğu Eylem Açılır Menüsü + Ayarlar | Açılır menü (select), geri sayım iptal banner'ı | `auto.power.*` (TR+EN) | Scheduler |
| **v1.9.0** | Kural Listesi & Öncelik Sıralama | Domain, uzantı veya boyuta göre indirme davranışını belirleyen kuralları sürükleyip sıralayabilmeli. | Ayarlar Sekmesi: "Kurallar" (`#setTabRules`) + Sol Menü | Sürüklenebilir sıralı liste (drag-drop table), aktif/pasif anahtarları | `rules.list.*` (TR+EN) | Rules |
| **v1.9.0** | Görsel Kural Editörü (Kriterler) | `EĞER domain = youtube.com VE boyut > 500MB` gibi koşulları form arayüzünden tanımlayabilmeli. | Kural Ekle/Düzenle Modalı (`#ruleEditVeil`) | Koşul blokları (dropdown + operatör + değer), "+ Koşul Ekle" butonu | `rules.editor.if.*` (TR+EN) | Rules |
| **v1.9.0** | Kural Eylemleri (Actions) | Kurala uyan dosyaya otomatik klasör, hız limiti, bağlantı sayısı, proxy veya çerez atayabilmeli. | Kural Ekle/Düzenle Modalı (`#ruleEditVeil`) | Eylem onay kutuları (checkbox), klasör seçici, hız profili seçici | `rules.editor.then.*` (TR+EN) | Rules |
| **v1.9.0** | Kural Test & Simülatör Alanı | Bir URL yapıştırıp hangi kuralların eşleşeceğini, dosyanın nereye gideceğini kaydedilmeden görebilmeli. | Kural Ekle/Düzenle Modalı Alt Bölümü | Test URL giriş kutusu, "Simüle Et" butonu, eşleşen adım ağacı | `rules.sim.*` (TR+EN) | Rules |
| **v1.9.0** | İndirme Özelinde Kural Denetimi | Bir indirmeye tıklayıp hangi kuralın devreye girdiğini görebilmeli, kuralı geçersiz kılabilmeli (override). | Detay Çekmecesi: "Kurallar" Sekmesi (`#dTabRules`) | Eşleşen kural kartı, "Kuralı Devre Dışı Bırak" toggle butonu | `rules.item.*` (TR+EN) | Rules |
| **v2.0.0** | Eklenti Listesi & Yönetimi | Kurulu eklentileri listeleyebilmeli, tek tıkla aktif/pasif yapabilmeli, sürümünü güncelleyebilmeli. | Ayarlar Sekmesi: "Eklentiler" (`#setTabPlugins`) | Eklenti kartları ızgarası (grid), açma/kapama anahtarları, kaldır butonu | `plugin.manage.*` (TR+EN) | Plugins |
| **v2.0.0** | Eklenti Pazar Yeri & Yükleme | Güvenli eklenti havuzunu arayabilmeli, tek tıkla veya `.afup` manifest dosyası sürükleyerek kurabilmeli. | Ayarlar Sekmesi: "Eklentiler" > "Pazar Yeri" Alt Sekmesi | Arama kutusu, kategori filtreleri, "Yükle" butonu, sürükle-bırak kutusu | `plugin.market.*` (TR+EN) | Plugins |
| **v2.0.0** | Eklenti İzin Denetimi (Auditor) | Eklentinin erişmek istediği domainleri, disk yetkilerini görüp bireysel olarak onaylayabilmeli. | Eklenti İzin Modalı (`#pluginPermVeil`) | İzin maddeleri onay listesi (dosya sistemi, ağ, çerezler), Kabul/Reddet | `plugin.perm.*` (TR+EN) | Security |
| **v2.0.0** | Eklenti Özel Ayar Paneli | Site çözücü (resolver) eklentisinin API anahtarını veya oturum çerezlerini UI'dan girebilmeli. | Eklenti Kartı > "Ayarlar" Modalı | Dinamik form üretici (manifest schema'sına göre input/password kutuları) | `plugin.config.*` (TR+EN) | Plugins |
| **v2.1.0** | Headless Mod & Servis Durumu | AfuDM'in penceresiz daemon/server modunu başlatabilmeli, IP ve dinleme portunu ayarlayabilmeli. | Ayarlar Sekmesi: "Sunucu / Headless" (`#setTabServer`) | Açma/kapama anahtarı, IP/Port giriş alanları, çalışma durumu rozeti | `server.status.*` (TR+EN) | Server |
| **v2.1.0** | API Token & İzin Yönetimi | Uzak bağlantılar (CLI, mobil, NAS, tarayıcı) için ayrı tokenlar üretip erişim seviyesini seçebilmeli. | Ayarlar Sekmesi: "Sunucu / Headless" | Token tablosu, "Yeni Token Oluştur" butonu, silme/iptal butonu | `server.tokens.*` (TR+EN) | Security |
| **v2.1.0** | Uzak İndirme Web İstemcisi | Masaüstü istemcisinden bağımsız, uzaktan erişilen tam teşekküllü web konsoluna bağlanabilmeli. | Bağımsız Tarayıcı URL'si (`http://ip:port/web`) | Responsive masaüstü web kopyası, oturum açma kartı | `server.webui.*` (TR+EN) | Server |
| **v2.1.0** | Canlı Bağlantı Günlüğü & İstemciler | O an sunucuya bağlı olan PWA, uzantı ve CLI oturumlarını canlı görüp bağlantıyı kesebilmeli. | Ayarlar Sekmesi: "Sunucu" > "Bağlı İstemciler" | İstemci IP/Cihaz listesi, "Bağlantıyı Sonlandır" butonu | `server.clients.*` (TR+EN) | Server |
| **v2.2.0** | Windows Başlangıç & Arka Plan | Windows açılışında başlama, sistem tepsisine simge olarak gitme ve servis modunu kontrol edebilmeli. | Ayarlar Sekmesi: "Windows Entegrasyonu" (`#setTabWindows`) | Onay kutuları (checkbox), radyo butonları | `win.startup.*` (TR+EN) | Windows Integration |
| **v2.2.0** | Windows Explorer Sağ Tık Menüsü | Dosya Gezgini'nde dosya veya klasöre sağ tıklayıp "AfuDM ile İndir" menü girdisini açıp kapatabilmeli. | Ayarlar Sekmesi: "Windows Entegrasyonu" | Anahtar (switch), "Gezgin Menüsünü Kaydet / Kaldır" butonu | `win.shell.*` (TR+EN) | Windows Integration |
| **v2.2.0** | Protokol İlişkilendirme (`afudm://`) | Tarayıcıdan veya linkten `afudm://` çağrıldığında otomatik açılmasını Windows ayarlarından onaylayabilmeli. | Ayarlar Sekmesi: "Windows Entegrasyonu" | Durum göstergesi rozeti, "Varsayılan Protokol Yap" butonu | `win.proto.*` (TR+EN) | Windows Integration |
| **v2.2.0** | Windows Defender Entegrasyonu | Dosya iner inmez Windows Defender MpCmdRun ile taranmasını, şüpheli dosyaların karantinaya alınmasını ayarlayabilmeli. | Ayarlar Sekmesi: "Windows Entegrasyonu" + Detay Çekmecesi | Onay kutusu, tarama seviyesi seçici (Hızlı/Tam), Defender durum rozeti | `win.defender.*` (TR+EN) | Security |
| **v2.2.0** | Windows Yerel Bildirimleri (Toast) | İndirme bittiğinde sesli ve butonlu zengin Windows Action Center bildirimlerini özelleştirebilmeli. | Ayarlar Sekmesi: "Windows Entegrasyonu" | Bildirim önizleme anahtarları, ses aç/kapat, buton aksiyonu seçici | `win.toast.*` (TR+EN) | Windows Integration |
| **v2.3.0** | Veritabanı Otomatik Onarım | Elektrik kesintisi veya çökme sonrası SQLite bozulmalarını tek tıkla UI'dan onarabilmeli. | Ayarlar Sekmesi: "Güvenlik & Güvenilirlik" (`#setTabSecurity`) | "Veritabanını Doğrula ve Onar" butonu, sağlık durumu rozeti | `sec.db.*` (TR+EN) | Security |
| **v2.3.0** | Bozuk İndirme Kurtarma Sihirbazı | Yarım kalan veya `.aria2` dosyası bozulan indirmeyi dosya boyutu ve hash ile analiz edip kurtarabilmeli. | Sağ Tık Menüsü > "İndirmeyi Onar / Kurtar" Modalı | Adım adım sihirbaz penceresi, dosya analiz çubuğu, onarımı başlat butonu | `sec.recovery.*` (TR+EN) | Security |
| **v2.3.0** | Ayarları Yedekleme ve Geri Yükleme | Tüm kuralları, eklenti ayarlarını ve geçmişi `.afubak` dosyası olarak dışa/içe aktarabilmeli. | Ayarlar Sekmesi: "Güvenlik & Güvenilirlik" | "Yedek Al" butonu, "Yedekten Yükle" dosya seçicisi, onay uyarısı | `sec.backup.*` (TR+EN) | Security |
| **v2.3.0** | Tanı Verisi Dışa Aktarma & Arındırma | Hata raporlamak için şifre ve tokenları maskeleyen (redacted) tek paket log zip'i oluşturabilmeli. | Ayarlar Sekmesi: "Güvenlik & Güvenilirlik" | "Tanı Paketini Hazırla (ZIP)" butonu, maskeleme önizleme alanı | `sec.diag.*` (TR+EN) | Security |
| **v2.3.0** | Motor Sağlık & Otomatik İyileştirme | aria2 veya yt-dlp kilitlendiğinde kullanıcının motoru tek tıkla yeniden başlatabilmesini sağlamalı. | Üst Durum Çubuğu Motor Rozeti Açılır Kartı (`#enginePopup`) | Durum kartı, "Motorları Yeniden Başlat" butonu, gecikme/ping süresi | `sec.engine.*` (TR+EN) | Bandwidth |

---

## 4. Sürüm Bazında Derinlemesine UI Tasarım Detayları

### 4.1 v1.7.5 — Mobile Remote & PWA Arayüzü

#### A. Masaüstü Tarafı: Eşleştirme ve QR Modalı (`#telefonKutu` Genişletmesi)
Mevcut ayarlar modalındaki `#telefonKutu` ve sol alt araç çubuğuna eklenecek mobil ikonu tıklandığında açılan `pairVeil` modalı:
- **UI Yeri:** Sol menü altı mobil butonu (`#railMobile`) veya Ayarlar > Sunucu & Mobil sekmesi.
- **Bileşenler:**
  - `sTelefonQr`: Dinamik SVG QR kodu (İçerik: `http://192.168.1.X:PORT/#token=KISA_OMURLU_HEX`).
  - `sTelefonKopya`: Adresi ve tek kullanımlık eşleştirme anahtarını kopyalama butonu.
  - `mobileCihazlar`: Eşleşmiş telefonların listesi (Model, IP, Son Görülme, Yetkiyi Kaldır butonu).
  - `sMobileOnlyWifi`: Yalnızca yerel ağ (LAN) erişimine izin ver anahtarı (Varsayılan: Açık).

#### B. Mobil PWA Tarafı (Responsive WebView / Mobil Tarayıcı Shell)
Mobil tarayıcıda masaüstü arayüzü küçültülmez; dokunmatik kullanıma özel ergonomik mobil arayüz açılır:
1. **Üst Bant (Mobile Header):**
   - Anlık toplam indirme hızı büyük dijital sayaçla gösterilir.
   - Sağ üstte hızlı hız profili geçişi: `[T]` (Turbo), `[N]` (Normal), `[S]` (Salyangoz).
2. **Kuyruk Kartları (Mobile Cards):**
   - Her indirme tam genişlikte karttır: Başlık, dosya türü ikonu, canlı ilerleme çubuğu, hız ve ETA.
   - Kart üstünde tek dokunuşla Duraklat / Sürdür aksiyonu.
   - Torrent kartlarında: `Peers: 12 | Seeds: 3` yanında belirgin **[Boost]** butonu.
3. **Yüzen Eylem Butonu (FAB - Floating Action Button):**
   - Sağ altta mavi `+` butonu. Basıldığında telefon panosundaki linki algılar, tek tıkla "PC'ye Gönder" kartını açar.
4. **Zamanlayıcı ve PC Gücü:**
   - Menüden "İndirmeler bitince PC'yi Kapat" komutunu uzaktan verebilme anahtarı.

---

### 4.2 v1.8.0 — Automation & Post-Processing Arayüzü

#### A. Detay Çekmecesi "Otomasyon" Sekmesi (`#dPanelAutomation`)
Mevcut boş placeholder (`#dAutomationContent`) şu canlı bileşenlerle doldurulur:
- **İşlem Hattı (Pipeline) Görünümü:**
  ```
  [ İndirme ] ──> [ SHA256 Kontrolü ] ──> [ Arşiv Çıkarma ] ──> [ Taşıma & Yeniden Adlandırma ] ──> [ Bildirim ]
     Tamamlandı         Doğrulandı              İşleniyor (%45)              Bekliyor                       Bekliyor
  ```
- **Checksum Kartı:**
  - Beklenen Hash: `<input type="text" placeholder="SHA256 / MD5">`
  - Hesaplanan Hash: Canlı hesaplanan özet değeri ve `[Eşleşti ✓]` / `[Uyuşmazlık ✗]` rozeti.
- **Arşiv Açma Durumu:**
  - Çıkarılan dosya sayısı, hedef klasör ve varsa parola deneme logları.

#### B. Ayarlar Sekmesi: "Otomasyon" (`#setTabAutomation`)
- **Arşiv Açma Motoru (Extraction):**
  - `autoExtractEnabled`: "İndirilen arşivleri otomatik aç" anahtarı (Switch).
  - `autoExtractDir`: Çıkarma konumu (Aynı klasör / Özel alt klasör).
  - `autoExtractPasswordPool`: Parola havuzu (Her satıra bir şifre girilebilen textarea).
  - `autoExtractDeleteArchive`: "Açıldıktan sonra arşivi sil / geri dönüşüm kutusuna at" onay kutusu.
- **Yeniden Adlandırma ve Düzenleme (File Renamer):**
  - Dosya türüne göre klasörleme kuralı (Müzik, Video, Doküman, Yazılım).
  - Şablon etiketleri: `{name}`, `{ext}`, `{date}`, `{quality}`, `{resolution}`, `{uploader}`.
- **Harici Betik Çalıştırma (Hook Scripts):**
  - İndirme tamamlandığında çalışacak komut satırı: `C:\Scripts\islem.bat "{filepath}" "{filesize}"`.
  - Hata durumunda çalışacak alternatif komut satırı.

#### C. Sol Menü: "Otomasyon Kuyruğu" Listesi (`#filterAutomation`)
Sol menüdeki yeni "Otomasyon" filtresi seçildiğinde ana listede indirmeler değil, post-processing işleminde olan arka plan görevleri gösterilir (Örn: 14 GB RAR arşivi çıkarılıyor: %72, 45 MB/s disk hızı).

---

### 4.3 v1.9.0 — Rules Engine (Kural Motoru Arayüzü)

#### A. Ayarlar Sekmesi: "Kurallar" (`#setTabRules`)
- **Kural Tablosu:**
  - Öncelik sırası (Yukarı/Aşağı taşıma tutamaçları ile sıralanabilir).
  - Kural Adı, Koşul Özeti, Eylem Özeti, Aktiflik Anahtarı, Sil butonu.
  - Örnek: `1 | YouTube 1080p+ | domain == youtube.com AND res >= 1080 | D:\Videolar\HD | [Açık]`
- **Yeni Kural Ekle Butonu:** `#btnNewRule` tıklandığında kural editörü modalı açılır.

#### B. Kural Editörü Modalı (`#ruleEditVeil`)
Görsel bloklarla kural oluşturma sihirbazı:
1. **Koşul Alanı (EĞER - IF):**
   - Kriter seçici: `Domain`, `Dosya Uzantısı`, `Dosya Boyutu`, `Protokol`, `İçerik Türü`, `Regex URL`.
   - Operatör: `Eşittir`, `İçerir`, `Büyüktür`, `Küçüktür`, `Regex Eşleşir`.
   - Değer giriş kutusu (Örn: `*.mkv;*.mp4` veya `github.com`).
   - `[+ Koşul Ekle]` (VE / VEYA mantıksal operatörü ile bağlama).
2. **Eylem Alanı (O HALDE - THEN):**
   - **Hedef Klasör:** Özel klasör belirle (Klasör seçici butonu ile).
   - **Bağlantı & Hız:** Özel sunucu bağlantı sayısı (1–32) ve hız tavanı belirle.
   - **Hız Profili:** Bu indirmeyi otomatik "Salyangoz" veya "Turbo" moduna al.
   - **Zamanlama:** "Gece Kuyruğuna (01:00-07:00) Ekle" anahtarı.
   - **Proxy Yönlendirme:** Doğrudan / Özel Proxy profilini kullan.
   - **Otomasyon Tetikleyici:** İndirme bittiğinde özel betik çalıştır.
3. **Canlı Kural Simülatörü:**
   - Altta yer alan test çubuğu: `https://example.com/files/archive.iso`. Kullanıcı bu adresi yapıştırdığında editör, kuralın bu linki yakalayıp yakalamayacağını yeşil/kırmızı göstergelerle simüle eder.

#### C. Detay Çekmecesi "Kurallar" Sekmesi (`#dPanelRules`)
- İndirilen dosyanın hangi kuralla eşleştiği gösterilir:  
  `✓ "Büyük Arşivler" kuralı uygulandı: 16 parça bağlantı, D:\ISO klasörüne yönlendirildi.`
- İstenirse `[Bu İndirmede Kuralı İptal Et]` butonu ile genel ayarlara dönülür.

---

### 4.4 v2.0.0 — Plugin Platform (Eklenti Ekosistemi Arayüzü)

#### A. Ayarlar Sekmesi: "Eklentiler" (`#setTabPlugins`)
- **İki Sekmeli Görünüm:** `[Kurulu Eklentiler]` ve `[Eklenti Mağazası / Pazar Yeri]`.
- **Eklenti Kartı Bileşenleri:**
  - Başlık, Eklenti Türü Rozeti (`Site Resolver`, `Post Processor`, `Notification`, `Theme`).
  - Açıklama, Geliştirici, Sürüm numarası.
  - Açma / Kapama anahtarı (Switch).
  - Yapılandırma Dişli Çarkı (`⚙ Yapılandır`): Eklentinin ihtiyaç duyduğu API anahtarı veya giriş bilgileri modalı.
  - İzin Rozeti (`🔒 3 İzin`): Eklentinin nelere eriştiğini gösteren denetim kartı.

#### B. Eklenti İzin Denetim Modalı (`#pluginPermVeil`)
Kullanıcının güvenliğini garanti altına alan onay ekranı:
- **Erişim İzinleri:**
  - `Ağ Erişimi:` Hangi domainlere bağlanabileceği (Örn: `*.rapidgator.net`).
  - `Disk Erişimi:` Dosya okuma/yazma yetkisi (Sadece indirme klasörü mü, tüm sistem mi?).
  - `Çerez Erişimi:` Tarayıcıdan oturum çerezi okuma izni.
- **Onay Butonları:** `[Tümünü Onayla ve Etkinleştir]` / `[İptal Et]`.

#### C. Eklenti Yükleme Seçenekleri:
- Mağazadan tek tıkla "Yükle" butonu.
- "Yerel Eklenti Yükle" butonu ile `.afup` (AfuDM Plugin Paketi) dosyasını seçme veya arayüze sürükleyip bırakma.

---

### 4.5 v2.1.0 — Headless Server & NAS Arayüzü

#### A. Ayarlar Sekmesi: "Sunucu / Headless" (`#setTabServer`)
- **Sunucu Anahtarı:** `AfuDM API & Web UI Sunucusunu Başlat` (Açık/Kapalı).
- **Ağ Yapılandırması:**
  - Dinleme Adresi: `127.0.0.1` (Yalnızca yerel), `192.168.X.X` (Yerel Ağ), `0.0.0.0` (Tüm Ağlar).
  - Port: Varsayılan `6800` (aria2 uyumlu) veya `8990` (AfuDM REST API).
  - HTTPS / TLS Sertifika Seçimi: Kendi kendine imzalı veya özel cert/key dosyası seçici.
- **Kimlik Doğrulama & Erişim Tokenları Tablosu:**
  - Token Adı (Örn: `Oturma Odası NAS`, `Laptop CLI`, `Android Telefon`).
  - Yetki Seviyesi: `Salt Okunur (Monitor)`, `İndirme Ekleme`, `Tam Yönetici`.
  - Son Kullanım Tarihi, `[Tokenı Yenile]` ve `[İptal Et]` aksiyonları.
- **Bağlı İstemciler (Canlı Session Monitor):**
  - Aktif WebSocket bağlantılarının listesi (IP, Kullanıcı Ajanı, Açık Olduğu Süre, Anlık Veri Transferi).

#### B. Bağımsız Headless Web İstemcisi (`http://host:port/web`)
Masaüstü uygulaması kapalıyken veya uzaktaki bir sunucuya bağlanırken tarayıcıdan açılan arayüz:
- Masaüstü koyu temasıyla birebir uyumlu, hafifletilmiş Web Standartları (HTML5/CSS3/Vanilla JS).
- Sağ üstte "Bağlı Sunucu: 192.168.1.50:8990 | Gecikme: 4 ms" bilgi rozeti.

---

### 4.6 v2.2.0 — Windows Integration (Windows Entegrasyonu Arayüzü)

#### A. Ayarlar Sekmesi: "Windows Entegrasyonu" (`#setTabWindows`)
- **Sistem Başlangıcı ve Tepsi (Startup & Tray):**
  - `[x]` Windows açıldığında AfuDM'i otomatik başlat.
  - `[x]` Başlangıçta ana pencereyi gösterme, sistem tepsisinde sessiz başla.
  - `[x]` Pencere kapatıldığında (X) uygulamadan çıkma, sistem tepsisine küçült.
- **Dosya Gezgini (Explorer) Kabuk Entegrasyonu:**
  - `[x]` Windows Gezgini sağ tık menüsüne "AfuDM ile İndir" seçeneğini ekle.
  - `[x]` İndirilen dosyalara Gezgin'de özel durum simgesi (overlay icon) ekle.
  - `[Menüyü Windows'a Kaydet]` ve `[Kaldır]` komut butonları.
- **Protokol ve Dosya Türü İlişkilendirmeleri:**
  - `[x]` `afudm://` protokolünü AfuDM'e bağla.
  - `[x]` `.torrent` dosyaları ve `magnet:` bağlantıları için varsayılan uygulama ol.
  - `[x]` `.metalink` dosyalarını otomatik yakala.
  - `[Windows Varsayılan Uygulama Ayarlarını Aç]` sistem kısayol butonu.
- **Windows Defender Güvenlik Taraması:**
  - `[x]` İndirme bittiğinde Windows Defender (MpCmdRun.exe) ile otomatik tara.
  - Tarama Modu: `Hızlı Tarama` / `Derin Dosya Taraması`.
  - Tehdit Algılanırsa: `Dosyayı Karantinaya Al ve İndirmeyi Hata Olarak İşaretle`.

#### B. Windows Yerel Bildirim Ayarları:
- `[x]` Windows Bildirim Merkezi (Action Center) bildirimlerini kullan.
- Bildirim Eylemleri: Bildirim üzerinde `[Dosyayı Aç]` ve `[Klasörde Göster]` butonlarını göster.

---

### 4.7 v2.3.0 — Reliability, Security & Recovery Arayüzü

#### A. Ayarlar Sekmesi: "Güvenlik & Güvenilirlik" (`#setTabSecurity`)
- **Veritabanı Sağlığı & Otomatik Onarım:**
  - Veritabanı Dosya Boyutu, Toplam Kayıt Sayısı, Parçalanma Oranı (Fragmentation).
  - `[Veritabanını Optimize Et (VACUUM)]` butonu.
  - `[Bozuk Veritabanını Onar]` butonu: SQLite bütünlük denetimi (`PRAGMA integrity_check`) çalıştırır ve bozuk indeksleri kurtarır.
- **Ayarları Yedekleme ve Geri Yükleme:**
  - `[Tüm Yapılandırmayı Yedekle (.afubak)]`: Kurallar, ayarlar, tracker listesi ve eklenti yapılandırmalarını tek şifreli pakette dışa aktarır.
  - `[Yedekten Geri Yükle]`: Eski bir yedeği seçip ayarları geri getirir.
- **Tanı Paketi ve Log Arındırma (Diagnostics & Redaction):**
  - `[Tanı Verilerini Dışa Aktar (ZIP)]`: Geliştiriciye iletmek üzere logları paketler.
  - Önizleme ve Gizlilik Anahtarı: `[x] Parolaları, Telegram tokenlarını ve özel URL parametrelerini otomatik maskele (Redact)`.
  - Kullanıcı dışa aktarmadan önce hangi verilerin sansürlendiğini modalda satır satır inceler.

#### B. Sağ Tık Menüsü: "Bozuk İndirmeyi Kurtar" Sihirbazı Modalı (`#recoveryVeil`)
- Elektrik kesintisi veya disk hatasıyla `.aria2` kontrol dosyası silinmiş ya da bozulmuş indirmelerde:
  - Adım 1: Diskteki mevcut geçici dosya taranır ve indirilen bloklar tespit edilir.
  - Adım 2: Sunucudan `Range` başlığı ile dosya boyutu doğrulanır.
  - Adım 3: Yeni kontrol dosyası üretilerek indirme baştan başlamadan kaldığı bloktan devam ettirilir.
  - Ekranda: `3.4 GB / 4.0 GB diskte bulundu. Kalan 600 MB indirilecek.` kurtarma özeti gösterilir.

---

## 5. Eksiksiz i18n Dil Sözlüğü Tasarımı (TR & EN)

Tüm yeni özellikler için `ui/i18n.js` içine eklenecek anahtar aileleri aşağıda tam karşılıklarıyla tanımlanmıştır. Kod içinde sabit/hardcoded metin bulunamaz.

```javascript
/* =========================================================================
 * AfuDM Gelecek Sürümler i18n Sözlük Eklentileri (v1.7.5 - v2.3.0)
 * ========================================================================= */

// --- TÜRKÇE (tr) ---
const tr_additions = {
  // v1.7.5 Mobile & PWA
  "mobile.title": "Mobil & PWA Uzaktan Kumanda",
  "mobile.pairTitle": "Telefonu Eşleştir",
  "mobile.pairHint": "Telefonunun kamerasıyla bu QR kodu okutarak indirmelerini uzaktan yönet.",
  "mobile.devices": "Bağlı Cihazlar",
  "mobile.noDevices": "Henüz eşleşmiş mobil cihaz yok.",
  "mobile.revoke": "Yetkiyi Kaldır",
  "mobile.lanOnly": "Yalnızca yerel Wi-Fi ağına izin ver",
  "mobile.sendLink": "Telefondan Link Gönder",
  "mobile.speedTurbo": "Turbo Mod",
  "mobile.speedNormal": "Normal Mod",
  "mobile.speedSnail": "Salyangoz Mod",
  "mobile.boostAction": "Torrent Boost Başlat",

  // v1.8.0 Automation
  "auto.title": "Otomasyon & Son İşlemler",
  "auto.tab": "Otomasyon",
  "auto.checksum.title": "Dosya Bütünlüğü Doğrulama",
  "auto.checksum.expected": "Beklenen Hash (SHA256/MD5)",
  "auto.checksum.calculated": "Hesaplanan Hash",
  "auto.checksum.match": "Hash doğrulandı, dosya sağlam.",
  "auto.checksum.mismatch": "DİKKAT: Hash uyuşmuyor, dosya bozuk veya değiştirilmiş!",
  "auto.extract.enable": "İndirilen arşivleri otomatik klasöre çıkar",
  "auto.extract.dir": "Çıkarma Hedef Klasörü",
  "auto.extract.passPool": "Parola Havuzu (Her satıra bir parola)",
  "auto.extract.deleteArchive": "Çıkarma başarılı olunca arşiv dosyasını sil",
  "auto.organize.enable": "Dosyaları kategori ve şablona göre otomatik taşı",
  "auto.organize.pattern": "Adlandırma Şablonu",
  "auto.script.enable": "İndirme bitince özel betik çalıştır",
  "auto.script.path": "Betik Dosyası Yolu (.bat, .py, .ps1)",
  "auto.script.args": "Betik Parametreleri",
  "auto.queue.title": "Otomasyon İşlem Kuyruğu",
  "auto.queue.extracting": "Arşiv açılıyor: {pct}%",
  "auto.queue.verifying": "Hash kontrol ediliyor...",
  "auto.power.shutdown": "Tüm indirmeler bittiğinde bilgisayarı kapat",
  "auto.power.sleep": "Tüm indirmeler bittiğinde bilgisayarı uykuya al",
  "auto.power.cancelBanner": "Bilgisayar {sec} saniye içinde kapatılacak. İptal etmek için tıkla.",

  // v1.9.0 Rules Engine
  "rules.title": "İndirme Yönlendirme Kuralları",
  "rules.tab": "Kurallar",
  "rules.btnNew": "Yeni Kural Ekle",
  "rules.priority": "Öncelik",
  "rules.name": "Kural Adı",
  "rules.condition": "Koşul",
  "rules.action": "Eylem",
  "rules.active": "Aktif",
  "rules.empty": "Tanımlanmış kural yok. Dosyaları tür, boyut ve alan adına göre yönlendirmek için yeni kural ekle.",
  "rules.editor.title": "Kural Düzenleyici",
  "rules.editor.if": "EĞER Bu Koşullar Sağlanırsa (IF):",
  "rules.editor.addCond": "+ Koşul Ekle",
  "rules.editor.then": "O HALDE Bu Eylemleri Uygula (THEN):",
  "rules.editor.setDest": "Belirli Klasöre Kaydet",
  "rules.editor.setConn": "Özel Parça/Bağlantı Sayısı",
  "rules.editor.setSpeed": "Özel Hız Limiti (KB/s)",
  "rules.editor.setProxy": "Belirtilen Proxy Profilini Kullan",
  "rules.editor.setSchedule": "Gece Kuyruğuna Ekle (01:00-07:00)",
  "rules.sim.title": "Kural Test Alanı",
  "rules.sim.ph": "Test edilecek örnek indirme bağlantısını yapıştır...",
  "rules.sim.btn": "Kuralı Test Et",
  "rules.sim.match": "✓ Bu kural bağlantıyla eşleşti!",
  "rules.sim.noMatch": "✗ Bağlantı bu kuralın kriterlerine uymuyor.",
  "rules.item.override": "Bu indirme için uygulanan kuralı devre dışı bırak",

  // v2.0.0 Plugin Platform
  "plugin.title": "Eklenti Yöneticisi",
  "plugin.tabInstalled": "Yüklü Eklentiler",
  "plugin.tabMarket": "Eklenti Mağazası",
  "plugin.btnInstallLocal": "Yerel Eklenti Yükle (.afup)",
  "plugin.empty": "Henüz yüklü eklenti bulunmuyor.",
  "plugin.type.resolver": "Site Çözücü",
  "plugin.type.processor": "Son İşlemci",
  "plugin.type.notification": "Bildirim",
  "plugin.type.theme": "Görsel Tema",
  "plugin.version": "Sürüm",
  "plugin.author": "Geliştirici",
  "plugin.config": "Eklenti Ayarları",
  "plugin.permissions": "İzinleri İncele",
  "plugin.permModalTitle": "Eklenti Güvenlik İzinleri",
  "plugin.permNotice": "Bu eklenti bilgisayarınızda aşağıdaki işlemleri yapma yetkisi talep ediyor:",
  "plugin.permNet": "Şu alan adlarına ağ istekleri gönderme: {domains}",
  "plugin.permFs": "İndirme klasöründeki dosyaları okuma ve değiştirme",
  "plugin.permCookies": "Desteklenen tarayıcılardan indirme çerezlerini okuma",
  "plugin.permAllow": "İzin Ver ve Yükle",
  "plugin.permDeny": "Reddet ve İptal Et",

  // v2.1.0 Headless Server
  "server.title": "Sunucu & Headless Yapılandırması",
  "server.enable": "AfuDM Headless Arka Plan Sunucusunu Etkinleştir",
  "server.ip": "Dinleme IP Adresi",
  "server.port": "Port",
  "server.statusRunning": "Sunucu {ip}:{port} üzerinde aktif çalışıyor",
  "server.statusStopped": "Sunucu devre dışı",
  "server.tokensTitle": "API Erişim Anahtarları (Tokens)",
  "server.btnNewToken": "Yeni API Anahtarı Üret",
  "server.tokenName": "Cihaz / Uygulama Adı",
  "server.tokenRole": "Yetki Derecesi",
  "server.clientsTitle": "Aktif Bağlı İstemciler",
  "server.disconnectClient": "Bağlantıyı Kes",

  // v2.2.0 Windows Integration
  "win.title": "Windows Entegrasyonu",
  "win.startOnBoot": "Windows açılışında AfuDM'i otomatik başlat",
  "win.startMinimized": "Açılışta pencereyi açma, sistem tepsisinde gizli başla",
  "win.closeToTray": "Kapatma düğmesine (X) basıldığında sistem tepsisine küçült",
  "win.shellMenu": "Windows Dosya Gezgini sağ tık menüsüne 'AfuDM ile İndir' ekle",
  "win.protoRegister": "afudm:// web protokolünü sisteme kaydet",
  "win.torrentAssoc": ".torrent dosyalarını ve magnet bağlantılarını AfuDM ile aç",
  "win.defenderEnable": "İndirme tamamlandığında dosyayı Windows Defender ile otomatik tara",
  "win.defenderClean": "Defender taraması temiz: Tehdit bulunamadı.",
  "win.defenderInfected": "UYARI: Windows Defender zararlı yazılım tespit etti ve dosyayı karantinaya aldı!",
  "win.nativeToast": "Windows Eylem Merkezi (Action Center) yerel bildirimlerini göster",

  // v2.3.0 Reliability & Security
  "sec.title": "Güvenlik & Güvenilirlik",
  "sec.dbHealth": "Veritabanı Sağlığı",
  "sec.dbCheck": "Veritabanı Bütünlüğünü Denetle",
  "sec.dbVacuum": "Veritabanını Optimize Et (VACUUM)",
  "sec.dbRepair": "Bozuk Veritabanını Onar",
  "sec.dbOk": "Veritabanı sağlam, hata tespit edilmedi.",
  "sec.backupTitle": "Yedekleme ve Geri Yükleme",
  "sec.backupBtn": "Tüm Ayarları Yedekle (.afubak)",
  "sec.restoreBtn": "Yedekten Geri Yükle",
  "sec.diagTitle": "Tanı ve Hata Günlükleri",
  "sec.diagBtn": "Tanı Paketini Hazırla (ZIP)",
  "sec.diagRedact": "Hassas verileri (parolalar, tokenlar, kimlikler) sansürle",
  "sec.recoverTitle": "Bozuk İndirmeyi Kurtar",
  "sec.recoverScan": "Mevcut dosya parçaları taranıyor...",
  "sec.recoverSuccess": "{size} boyutundaki veri doğrulandı. İndirme sıfırlanmadan devam edecek.",
  "sec.engineRestart": "İndirme Motorlarını Yeniden Başlat (aria2 / yt-dlp)"
};

// --- İNGİLİZCE (en) ---
const en_additions = {
  // v1.7.5 Mobile & PWA
  "mobile.title": "Mobile & PWA Remote Control",
  "mobile.pairTitle": "Pair Your Phone",
  "mobile.pairHint": "Scan this QR code with your mobile camera to remotely manage your downloads.",
  "mobile.devices": "Connected Devices",
  "mobile.noDevices": "No paired mobile devices yet.",
  "mobile.revoke": "Revoke Access",
  "mobile.lanOnly": "Allow local Wi-Fi connections only",
  "mobile.sendLink": "Send Link from Mobile",
  "mobile.speedTurbo": "Turbo Mode",
  "mobile.speedNormal": "Normal Mode",
  "mobile.speedSnail": "Snail Mode",
  "mobile.boostAction": "Start Torrent Boost",

  // v1.8.0 Automation
  "auto.title": "Automation & Post-Processing",
  "auto.tab": "Automation",
  "auto.checksum.title": "File Integrity Verification",
  "auto.checksum.expected": "Expected Hash (SHA256/MD5)",
  "auto.checksum.calculated": "Calculated Hash",
  "auto.checksum.match": "Hash verified, file integrity intact.",
  "auto.checksum.mismatch": "WARNING: Hash mismatch! File is corrupted or modified.",
  "auto.extract.enable": "Automatically extract downloaded archives",
  "auto.extract.dir": "Extraction Destination Directory",
  "auto.extract.passPool": "Password Pool (One per line)",
  "auto.extract.deleteArchive": "Delete archive file after successful extraction",
  "auto.organize.enable": "Automatically organize files by category and pattern",
  "auto.organize.pattern": "Naming Pattern",
  "auto.script.enable": "Execute custom script upon completion",
  "auto.script.path": "Script File Path (.bat, .py, .ps1)",
  "auto.script.args": "Script Arguments",
  "auto.queue.title": "Automation Processing Queue",
  "auto.queue.extracting": "Extracting archive: {pct}%",
  "auto.queue.verifying": "Checking file hash...",
  "auto.power.shutdown": "Shut down computer when all downloads finish",
  "auto.power.sleep": "Put computer to sleep when all downloads finish",
  "auto.power.cancelBanner": "Computer will shut down in {sec} seconds. Click to cancel.",

  // v1.9.0 Rules Engine
  "rules.title": "Download Routing Rules",
  "rules.tab": "Rules",
  "rules.btnNew": "Add New Rule",
  "rules.priority": "Priority",
  "rules.name": "Rule Name",
  "rules.condition": "Condition",
  "rules.action": "Action",
  "rules.active": "Active",
  "rules.empty": "No rules defined. Add a new rule to route downloads by type, size, and domain.",
  "rules.editor.title": "Rule Editor",
  "rules.editor.if": "IF These Conditions Are Met:",
  "rules.editor.addCond": "+ Add Condition",
  "rules.editor.then": "THEN Perform These Actions:",
  "rules.editor.setDest": "Save to Specific Folder",
  "rules.editor.setConn": "Custom Connections / Splits",
  "rules.editor.setSpeed": "Custom Speed Limit (KB/s)",
  "rules.editor.setProxy": "Use Specified Proxy Profile",
  "rules.editor.setSchedule": "Add to Night Queue (01:00-07:00)",
  "rules.sim.title": "Rule Testing Simulator",
  "rules.sim.ph": "Paste a sample download URL to test...",
  "rules.sim.btn": "Test Rule",
  "rules.sim.match": "✓ This rule successfully matched the URL!",
  "rules.sim.noMatch": "✗ The URL does not meet the rule conditions.",
  "rules.item.override": "Override active rule for this download",

  // v2.0.0 Plugin Platform
  "plugin.title": "Plugin Manager",
  "plugin.tabInstalled": "Installed Plugins",
  "plugin.tabMarket": "Plugin Marketplace",
  "plugin.btnInstallLocal": "Install Local Plugin (.afup)",
  "plugin.empty": "No plugins installed yet.",
  "plugin.type.resolver": "Site Resolver",
  "plugin.type.processor": "Post Processor",
  "plugin.type.notification": "Notification",
  "plugin.type.theme": "Visual Theme",
  "plugin.version": "Version",
  "plugin.author": "Author",
  "plugin.config": "Plugin Settings",
  "plugin.permissions": "Review Permissions",
  "plugin.permModalTitle": "Plugin Security Permissions",
  "plugin.permNotice": "This plugin requests permission to perform the following actions on your computer:",
  "plugin.permNet": "Send network requests to domains: {domains}",
  "plugin.permFs": "Read and modify files in download directories",
  "plugin.permCookies": "Read download session cookies from supported browsers",
  "plugin.permAllow": "Grant Permissions & Install",
  "plugin.permDeny": "Deny & Cancel",

  // v2.1.0 Headless Server
  "server.title": "Server & Headless Configuration",
  "server.enable": "Enable AfuDM Headless Background Server",
  "server.ip": "Listen IP Address",
  "server.port": "Port",
  "server.statusRunning": "Server active and running on {ip}:{port}",
  "server.statusStopped": "Server is stopped",
  "server.tokensTitle": "API Access Tokens",
  "server.btnNewToken": "Generate New API Token",
  "server.tokenName": "Device / App Name",
  "server.tokenRole": "Permission Role",
  "server.clientsTitle": "Active Connected Clients",
  "server.disconnectClient": "Disconnect Client",

  // v2.2.0 Windows Integration
  "win.title": "Windows Integration",
  "win.startOnBoot": "Start AfuDM automatically on Windows startup",
  "win.startMinimized": "Start minimized to system tray on boot",
  "win.closeToTray": "Minimize to system tray when close button (X) is clicked",
  "win.shellMenu": "Add 'Download with AfuDM' to Windows Explorer context menu",
  "win.protoRegister": "Register afudm:// web protocol handler",
  "win.torrentAssoc": "Associate .torrent files and magnet links with AfuDM",
  "win.defenderEnable": "Automatically scan completed downloads with Windows Defender",
  "win.defenderClean": "Defender scan clean: No threats found.",
  "win.defenderInfected": "WARNING: Windows Defender detected malware and quarantined the file!",
  "win.nativeToast": "Show native Windows Action Center notifications",

  // v2.3.0 Reliability & Security
  "sec.title": "Security & Reliability",
  "sec.dbHealth": "Database Health",
  "sec.dbCheck": "Verify Database Integrity",
  "sec.dbVacuum": "Optimize Database (VACUUM)",
  "sec.dbRepair": "Repair Corrupt Database",
  "sec.dbOk": "Database is healthy, no errors detected.",
  "sec.backupTitle": "Backup & Restore",
  "sec.backupBtn": "Backup All Settings (.afubak)",
  "sec.restoreBtn": "Restore from Backup",
  "sec.diagTitle": "Diagnostics & Incident Logs",
  "sec.diagBtn": "Generate Diagnostic Bundle (ZIP)",
  "sec.diagRedact": "Sanitize sensitive data (passwords, tokens, credentials)",
  "sec.recoverTitle": "Recover Damaged Download",
  "sec.recoverScan": "Scanning existing file blocks on disk...",
  "sec.recoverSuccess": "{size} verified on disk. Resuming download without reset.",
  "sec.engineRestart": "Restart Download Engines (aria2 / yt-dlp)"
};
```

---

## 6. Geliştirici Uygulama Rehberi ve Kabul Kriterleri (Acceptance Criteria)

Bir geliştirici bu yol haritasından bir sürüm aldığında aşağıdaki kontrol listesini tamamlamadan UI işini "bitti" sayamaz:

1. **Görünürlük ve Kontrol Edilebilirlik:**
   - Eklenen motor özelliği Ayarlar sekmesinde bir anahtara veya liste yönetimine sahip mi?
   - Kullanıcı bu özelliği çalışırken detay çekmecesinde (`#drawer`) veya ana listede anlık olarak izleyebiliyor mu?
   - Özellik hata verdiğinde kullanıcıya anlaşılır bir toast/rozet mesajı dönüyor mu?
2. **İki Dilli (i18n) Bütünlük:**
   - `ui/i18n.js` içine hem Türkçe (`tr`) hem İngilizce (`en`) anahtar eklenmiş mi?
   - HTML tarafında `data-i18n`, `data-i18n-ph` ve `data-i18n-title` etiketleri dışında tek bir İngilizce veya Türkçe sabit metin bırakılmış mı?
3. **Mevcut UI Mimarisine Sadakat:**
   - Yeni pencereler `class="veil"` ve `class="sheet"` yapısını kullanıyor mu?
   - Vurgu rengi `#3b82f6` ve koyu zemin `#16181d` renk değişkenleriyle uyumlu mu?
   - `assets/afudm-menu-icon-set.svg` içindeki 8 ilgili ikon doğru yerlerde kullanıldı mı?
4. **Kullanıcı Kararı Teyidi:**
   - Özellik arka planda gizli kalmadı; UI üzerinden ayarlanabilir, test edilebilir ve izlenebilir kılındı.
