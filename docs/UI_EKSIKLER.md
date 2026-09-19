# AfuDM — UI Kontrol Eksikleri (kanitlı)

> **Kullanıcı kuralı (değişmez):** "Bütün eklenen özellikler UI ve UX kısmında
> KULLANILIR, AYARLANIR ve KONTROL EDİLEBİLİR olsun."

Bu liste `docs/BACKEND_ENVANTER.md` ile `docs/UI_ENVANTER.md` karşılaştırılarak
DEĞİL, doğrudan **koddan** çıkarıldı: `core/db.py` içindeki ayar şeması taranıp her
anahtarın `ui/app.js` + `ui/index.html` içinde karşılığı olup olmadığı arandı.
Aşağıdakilerin arayüzde **hiçbir kontrolü yok** — yalnızca arka planda yaşıyorlar.

## A) Kullanıcı ayarı ama arayüzde kontrolü YOK

| Ayar | Varsayılan | Ne yapar | Arka planda kullanıldığı yer | Hangi sürümün özelliği |
|---|---|---|---|---|
| `lan_erisimi` | `False` | Telefondan bağlan — yerel API'yi `0.0.0.0`'a açar | `app.py:523` | v1.3 Remote & Mobile |
| `api_port` | `6811` | Yerel API portu | `app.py:566` | v1.3 Remote & Mobile |
| `proxy` | `""` | Genel varsayılan proxy | `core/db.py:99`, `core/proxy.py` | v1.4 Network Core |
| `system_proxy` | `False` | Windows sistem proxy'sini kullan | `core/db.py:100` | v1.4 Network Core |
| `ag_konumlari` | `""` | Kullanıcının eklediği ağ konumları (UNC yolları) | `app.py:285` | v1.4 Network Core |
| `clipboard_exts` | `zip,rar,7z,exe,…` | Pano izlemede yakalanacak dosya uzantıları | `app.py:1047` | v1.1 Browser Integration |
| `snail_speed_kb` | `100` | "Salyangoz" hız profilinin limiti | `core/db.py:63` | v1.2 Download Engine |

**Sonuç:** v1.1, v1.2, v1.3 ve v1.4 sürümlerinin bazı özellikleri kuralı ihlal ediyor —
çalışıyorlar ama kullanıcı arayüzden ne açabiliyor, ne ayarlayabiliyor, ne görebiliyor.

### KARAR (kullanıcı, 19 Eyl 2026): bu 7 eksik **v1.7.5 Mobile & PWA**'ya girecek

v1.7.0 Torrent Pro bu eksikler için BEKLETİLMEYECEK; kendi kapsamıyla yayınlanır.
`lan_erisimi` + `api_port` zaten telefondan bağlanmanın anahtarı olduğu için v1.7.5'in
doğal kapsamına düşüyor; proxy/ağ/pano/hız ayarları da aynı Ayarlar turunda kapanır.

**v1.7.5 UI görev listesi (bu dosyadaki A ve B bölümünden türetildi):**

1. Ayarlar → yeni **"Uzaktan Erişim"** bölümü: `lan_erisimi` anahtarı + `api_port` alanı
   (açıkken bağlanılacak adresi ve QR'ı göster — PWA'nın giriş noktası).
2. Ayarlar → yeni **"Ağ"** bölümü: `proxy` adresi, `system_proxy` anahtarı, `ag_konumlari`
   çok satırlı alan.
3. Ayarlar → Pano izleme bölümüne `clipboard_exts` alanı (şu an sabit liste gibi davranıyor).
4. Hız profili kontrolüne `snail_speed_kb` alanı (salyangoz profilinin limiti ayarlanabilsin).
5. Tracker bölümüne **salt-okunur durum**: son tarama zamanı, kaç tracker canlı/ölü
   (`canli_trackerlar`, `tracker_tarama_zamani`, `tracker_tarama_ozeti`).
6. Hepsinin TR + EN i18n anahtarı olacak; sabit metin YASAK.
7. Her yeni kontrol için test: ayar kaydediliyor mu, geri yükleniyor mu, i18n anahtarı tam mı.

## B) Otomatik durum bilgisi — ayar değil, ama GÖSTERİLMESİ gerekir

Bunlar kullanıcı ayarı değil (sistem kendi üretiyor), fakat kullanıcı bunların
sonucunu göremiyor. En azından salt-okunur gösterilmeli.

| Anahtar | Ne tutar | Nerede üretiliyor |
|---|---|---|
| `canli_trackerlar` | Taramada canlı kalan tracker listesi | `core/db.py:87` |
| `tracker_tarama_zamani` | Son tracker taramasının zamanı | `core/db.py:88` |
| `tracker_tarama_ozeti` | Tarama özeti (kaç tracker canlı/ölü) | `core/db.py:89` |

Kullanıcı `ek_trackerlar` girebiliyor ama taramanın **sonucunu** göremiyor;
"tracker ekledim, işe yaradı mı?" sorusunun arayüzde cevabı yok.

## C) Zaten hazır olan iskelet (sıfırdan yapılmayacak)

Detay çekmecesinde şu paneller **placeholder olarak mevcut**:

- `#dPanelRules` — `ui/index.html:104`, `ui/app.js:239-242` (v1.9 Rules Engine)
- `#dPanelAutomation` — `ui/index.html:108`, `ui/app.js:243-246` (v1.8 Automation)

v1.8 ve v1.9 bu panelleri doldurarak ilerleyecek.

## Yöntem notu

İlk tarama 32 ayarın **hepsini** "UI'de yok" gösterdi; bu yanlıştı — arayüz ayarlara
`s.max_concurrent` gibi tırnaksız erişiyor, arama ise tırnaklı kalıbı arıyordu.
Kelime sınırlı (`\b`) aramayla tekrarlandı ve liste 32'den 10'a indi. Yukarıdaki
satırların her biri tek tek koddan doğrulandı.
