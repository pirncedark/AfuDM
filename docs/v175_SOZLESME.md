# v1.7.5 — UI Kontrol Sözleşmesi (paralel ajanlar bu dosyaya uyar)

Bu dosya BAĞLAYICIDIR. Dört ajan aynı anda farklı dosyalarda çalışıyor; hepsi
aşağıdaki id / ayar adı / i18n anahtarı üçlüsünü AYNEN kullanır. Kimse kendi adını
uydurmaz, yoksa parçalar birbirine bağlanmaz.

Kapsam: `docs/UI_EKSIKLER.md` bölüm A'daki 7 ayar + bölüm B'deki 3 durum alanı.

## Ayarlar modalı — yeni bölümler

Mevcut Ayarlar modalı `#setVeil > .sheet > .body` içine, MEVCUT bölüm kalıbıyla
(`<div><label for=...><input id=...></div>`) eklenecek. Yeni bölüm başlıkları
mevcut `<h3>` / `label` düzenine uyar. Yeni mimari İCAT EDİLMEZ.

### Bölüm 1 — Uzaktan Erişim (`set.remote.*`)

| Kontrol | Element id | Tip | Ayar anahtarı | i18n anahtarı |
|---|---|---|---|---|
| Bölüm başlığı | — | `<h3>` | — | `set.remote.title` |
| Telefondan bağlan | `sLanAccess` | checkbox | `lan_erisimi` | `set.remote.lan` |
| Açıklama | — | `.hint` | — | `set.remote.lanHint` |
| API portu | `sApiPort` | number (1024–65535) | `api_port` | `set.remote.port` |
| Bağlantı adresi | `sLanAddr` | salt-okunur metin | — (türetilir) | `set.remote.addr` |

`sApiPort` yalnızca `sLanAccess` açıkken etkin olur (kapalıyken `disabled`).
`sLanAddr` açıkken `http://<yerel-ip>:<port>` gösterir, kapalıyken boş kalır.

### Bölüm 2 — Ağ (`set.net.*`)

| Kontrol | Element id | Tip | Ayar anahtarı | i18n anahtarı |
|---|---|---|---|---|
| Bölüm başlığı | — | `<h3>` | — | `set.net.title` |
| Sistem proxy'sini kullan | `sSystemProxy` | checkbox | `system_proxy` | `set.net.systemProxy` |
| Proxy adresi | `sProxy` | text | `proxy` | `set.net.proxy` |
| Proxy ipucu | — | `.hint` | — | `set.net.proxyHint` |
| Ağ konumları | `sNetLocations` | textarea (her satır bir UNC) | `ag_konumlari` | `set.net.locations` |

`sSystemProxy` açıkken `sProxy` `disabled` olur (sistem proxy'si öncelikli).

### Bölüm 3 — Pano izleme eki (`set.clip.*`)

Mevcut pano izleme bölümüne EKLENİR, yeni bölüm açılmaz.

| Kontrol | Element id | Tip | Ayar anahtarı | i18n anahtarı |
|---|---|---|---|---|
| Yakalanacak uzantılar | `sClipExts` | text | `clipboard_exts` | `set.clip.exts` |
| İpucu | — | `.hint` | — | `set.clip.extsHint` |

### Bölüm 4 — Hız profili eki (`set.speed.*`)

Mevcut hız ayarı bölümüne EKLENİR.

| Kontrol | Element id | Tip | Ayar anahtarı | i18n anahtarı |
|---|---|---|---|---|
| Salyangoz hızı (KB/s) | `sSnailSpeed` | number (min 1) | `snail_speed_kb` | `set.speed.snail` |
| İpucu | — | `.hint` | — | `set.speed.snailHint` |

### Bölüm 5 — Tracker durumu (salt-okunur) (`set.tracker.*`)

Mevcut tracker bölümüne EKLENİR. Kullanıcı BURAYA YAZMAZ, sadece görür.

| Alan | Element id | Kaynak ayar | i18n anahtarı |
|---|---|---|---|
| Son tarama zamanı | `sTrackerScanTime` | `tracker_tarama_zamani` | `set.tracker.lastScan` |
| Canlı / toplam özet | `sTrackerSummary` | `tracker_tarama_ozeti`, `canli_trackerlar` | `set.tracker.summary` |
| Hiç tarama yapılmadıysa | — | — | `set.tracker.never` |

## Kablolama kuralı (`ui/app.js`)

- **Yükleme:** ayarlar modalı açılırken mevcut `ayarlariYukle`/`setVeil` akışında
  her alan `s.<ayar_anahtari> ?? <varsayilan>` ile doldurulur.
  Varsayılanlar: `lan_erisimi=false`, `api_port=6811`, `system_proxy=false`,
  `proxy=""`, `ag_konumlari=""`, `clipboard_exts` (mevcut sabit liste), `snail_speed_kb=100`.
- **Kaydetme:** mevcut kaydetme nesnesine aynı anahtarlarla eklenir.
  Sayısal alanlar `Number(...)`, boş/geçersizse varsayılana düşer.
  `api_port` 1024–65535 dışındaysa 6811'e düşer.
- **Bağımlılık:** `sLanAccess` ve `sSystemProxy` değişince bağlı alanların
  `disabled` durumu anında güncellenir (kaydetmeyi beklemez).
- Tracker durum alanları salt-okunur; kaydetme nesnesine GİRMEZ.

## i18n kuralı (`ui/i18n.js`)

Yukarıdaki HER anahtarın TR ve EN karşılığı olacak. Sabit metin YASAK.
EN metinleri düzgün İngilizce olacak (makine çevirisi değil).

## Test kuralı (`tests/`)

Yeni dosya: `tests/v175_ayar_test.py`, projenin `check("...", kosul)` + sonda
`sys.exit(1)` / `print("Hepsi gecti")` kalıbında. En az şunları doğrular:
1. Sözleşmedeki her element id'si `ui/index.html` içinde var.
2. Sözleşmedeki her i18n anahtarı `ui/i18n.js` içinde HEM TR HEM EN'de var.
3. Her ayar anahtarı `ui/app.js` içinde hem yükleme hem kaydetme tarafında geçiyor.
4. `api_port` aralık kontrolü (1024–65535) kodda mevcut.
5. `core/db.py` varsayılanlarıyla UI varsayılanları tutuyor.
