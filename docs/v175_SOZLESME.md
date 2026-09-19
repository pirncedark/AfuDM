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

## Telefon arayüzü — torrent paneli

Mobil arayüzde (`ui/mobil.html`) torrent indirmeleri için dosya seçimi, anlık seed/bağlantı takibi ve tracker taraması bu sözleşmeye göre çalışır.

### Element id listesi

| Element id | Tip / Etiket | Açıklama |
|---|---|---|
| `torrentKatman` | `div.katman` | Torrent yönetim modal katmanı (`hidden` ile açılır/kapanır) |
| `torrentBaslik` | `h2` | Modal başlığı ("Torrent dosyaları") |
| `trackerTara` | `button.sessiz` | Aktif torrent için tracker taramasını tetikleyen buton |
| `seedOzet` | `div.seed-ozet` | Anlık seed, peer ve bağlantı özet bilgisi |
| `torrentDosyalar` | `div.torrent-dosyalar` | Dosya listesi ve seçim onay kutuları kapsayıcısı |
| `torrentVazgec` | `button.sessiz` | Değişiklikleri iptal edip modalı kapatan buton |
| `torrentKaydet` | `button.ana` | Seçilen dosya indekslerini sunucuya gönderip kaydeden buton |

### REST uçlarının TAM sözleşmesi

Telefon arayüzünün torrent paneli tarafından tüketilen uçlar, HTTP yöntemleri, parametreleri, yanıt yapıları ve hata kodları aşağıda listelenmiştir. Yetkilendirme gerektiren uçlarda geçerli token bulunmazsa `401 Unauthorized` ile `{"ok": false, "kod": "ANAHTAR_GEREKLI", "mesaj": "anahtar gerekli"}` veya `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}` döner.

#### 1. `GET /torrent/dosyalar`
- **Yöntem:** `GET`
- **Sorgu parametreleri:** `gid` (zorunlu string)
- **İstek gövdesi:** Yok
- **Hata kodları:**
  - `400 Bad Request` → `{"ok": false, "kod": "GID_GEREKLI", "mesaj": "gid gerekli"}` (gid verilmediğinde)
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "gid": "2089b05e0a3d5014",
    "hazir_degil": false,
    "neden": "",
    "dosyalar": [
      {
        "index": 1,
        "path": "film/video.mkv",
        "length": 1073741824,
        "completedLength": 52428800,
        "selected": true
      }
    ]
  }
  ```

#### 2. `GET /torrent/metrik`
- **Yöntem:** `GET`
- **Sorgu parametreleri:** `gid` (zorunlu string)
- **İstek gövdesi:** Yok
- **Hata kodları:**
  - `400 Bad Request` → `{"ok": false, "kod": "GID_GEREKLI", "mesaj": "gid gerekli"}`
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "gid": "2089b05e0a3d5014",
    "num_seeders": 12,
    "connections": 25,
    "upload_speed": 1048576,
    "download_speed": 5242880,
    "seeder": false
  }
  ```

#### 3. `GET /seed`
- **Yöntem:** `GET`
- **Sorgu parametreleri:** `gid` (zorunlu string)
- **İstek gövdesi:** Yok
- **Hata kodları:**
  - `400 Bad Request` → `{"ok": false, "kod": "GID_GEREKLI", "mesaj": "gid gerekli"}`
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "seed": 12,
    "baglanti": 25,
    "seeder": false
  }
  ```

#### 4. `POST /torrent/secim`
- **Yöntem:** `POST`
- **İstek gövdesi:** JSON
  ```json
  {
    "gid": "2089b05e0a3d5014",
    "indeksler": [1, 2, 4]
  }
  ```
- **Hata kodları:**
  - `400 Bad Request` → `{"ok": false, "kod": "GID_GEREKLI", "mesaj": "gid gerekli"}` (gid boş/yoksa)
  - `400 Bad Request` → `{"ok": false, "kod": "GECERSIZ_SECIM", "mesaj": "indeksler liste olmali"}` (liste değilse)
  - `400 Bad Request` → `{"ok": false, "kod": "GECERSIZ_SECIM", "mesaj": "indeksler tam sayi olmali"}` (elemanlar tam sayı değilse veya bool/float ise)
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "gid": "2089b05e0a3d5014",
    "secilenler": [1, 2, 4]
  }
  ```

#### 5. `POST /seed/tazele`
- **Yöntem:** `POST`
- **İstek gövdesi:** JSON
  ```json
  {
    "gid": "2089b05e0a3d5014"
  }
  ```
- **Hata kodları:**
  - `400 Bad Request` → `{"ok": false, "kod": "GID_GEREKLI", "mesaj": "gid gerekli"}`
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "gid": "2089b05e0a3d5014",
    "seed": 12,
    "baglanti": 25,
    "seeder": false
  }
  ```

#### 6. `POST /tracker/tara`
- **Yöntem:** `POST`
- **İstek gövdesi:** JSON
  ```json
  {
    "gid": "2089b05e0a3d5014"
  }
  ```
- **Hata kodları:**
  - `401 Unauthorized` → `{"ok": false, "kod": "GECERSIZ_TOKEN", "mesaj": "gecersiz token"}`
- **Yanıt anahtarları (`200 OK`):**
  ```json
  {
    "ok": true,
    "gid": "2089b05e0a3d5014",
    "taranan": 15,
    "canli": 9
  }
  ```

### `/torrent/dosyalar` yanıtı DÜZ olmalı kuralı

Sunucu tarafında `GET /torrent/dosyalar` yanıtı mutlaka düz sözlük yapısında dönmelidir:
`{"ok": true, "gid": gid, "hazir_degil": bool, "neden": str, "dosyalar": list}`.

**Gerekçe:**
`core/manager.py` içindeki `TorrentDosyaListesi` sınıfı `list[dict]` alt sınıfıdır (`class TorrentDosyaListesi(list[dict])`). Python `json.dumps()` bu nesneyi serileştirirken nesneyi doğrudan ham bir JSON dizisi (`[...]`) olarak dışa aktarır; nesne örneğine atanmış olan `hazir_degil`, `neden` ve `gid` özel öznitelikleri JSON çıktısına dahil edilmez ve **DÜŞER**.

Telefon arayüzü (`ui/mobil.html`) magnet indirmelerinde "üstveri henüz çözümlenmedi / hazır değil" durumunu `veri.hazir_degil` ve `veri.neden` alanlarına bakarak tespit eder. Eğer yanıt düz sözlük olarak sarılmazsa telefon bu alanları okuyamaz ve kullanıcıya yanıltıcı biçimde boş liste veya hata gösterir. Bu nedenle `api/server.py` endpoint'i `dosyalar` nesnesini listeye dönüştürerek kök sözlük içinde `{"ok": true, "gid": ..., "hazir_degil": ..., "neden": ..., "dosyalar": list(dosyalar)}` biçiminde göndermekle yükümlüdür.
