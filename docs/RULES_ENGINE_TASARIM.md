# AfuDM v1.9.0 "Rules Engine" Tasarim Dokumani

Bu dokuman, AfuDM v1.9.0 ile eklenecek olan Kurallar Motoru (Rules Engine) ozelliginin veri modelini, mimarisini ve UI taslagini tanimlar.

## 1. Deklaratif Kosul ve Eylem Veri Modeli

Kurallar, bagimsiz JSON objeleri olarak ifade edilir ve SQLite'da saklanir.

### JSON Semasi

Bir kural asagidaki yapiya sahiptir:

```json
{
  "id": "a1b2c3d4-e5f6-7890",
  "name": "Gece Torrentleri",
  "active": true,
  "priority": 1,
  "match_type": "all",
  "conditions": [
    {"field": "domain", "op": "ends_with", "value": "tracker.example.com"},
    {"field": "extension", "op": "in", "value": ["iso", "mkv"]},
    {"field": "filename", "op": "regex", "value": ".*-1080p\\..*"},
    {"field": "size_mb", "op": "gt", "value": 20480},
    {"field": "protocol", "op": "eq", "value": "torrent"},
    {"field": "category", "op": "eq", "value": "video"}
  ],
  "actions": {
    "dest_dir": "D:\\GeceKuyrugu",
    "proxy": "socks5://127.0.0.1:1080",
    "max_speed_kb": 500,
    "split": 16,
    "start_after": "23:30",
    "automation_script": "post_process.bat"
  }
}
```

Kosul operatorleri (`op`): `eq` (esittir), `neq` (esit degildir), `contains` (icerir), `ends_with` (ile biter), `regex` (duzenli ifade), `in` (listede var), `gt` (buyuktur), `lt` (kucuktur).

### SQLite Tablo Semasi ve Migration Plani

`core/db.py` icindeki `USER_VERSION` degiskeni 3'ten 4'e cikarilacak ve `MIGRATIONS` sozlugune yeni bir adim eklenecektir.

```python
def _v4_rules_engine(conn: sqlite3.Connection) -> None:
    # Kurallari saklayacagimiz tablo
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            active     INTEGER DEFAULT 1,
            priority   INTEGER NOT NULL,
            match_type TEXT NOT NULL,
            conditions TEXT NOT NULL,
            actions    TEXT NOT NULL
        )
    """)
    # Oncelik sirasina gore hizli cekmek icin indeks
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority)")
```

## 2. Kural Onceligi ve Cakisma Cozumu

Karar mekanizmasinin altin kurali, oncelik sirasidir (Nihai karar):
**Indirmeye Ozel Secim > Eslesen Kural > Genel Varsayilan**

1. Eger kullanici arayuzde (Kaydetme penceresi) hiz sinirini veya klasoru elden degistirirse, bu HER SEYI ezer.
2. Eger elden degistirme yoksa, kurallara bakilir.
3. Hicbir kural eslesmezse, genel AfuDM ayarlari kullanilir.

Birden fazla kuralin ayni linkle eslesmesi durumu (Cakisma):
Kurallar `priority` (oncelik) sayisina gore siralidir (1 en yuksek onceliktir).
- Eslesen tum kurallarin `actions` bloklari, en dusuk oncelikten (en buyuk rakam) en yuksek oncelige (en kucuk rakam) dogru uste bindirilerek (merge) islenir.
- Yani, Kural 1 (priority=1) ve Kural 2 (priority=2) eslesirse ve ikisi de `dest_dir` atamaya calisiyorsa; Kural 1'in degeri Kural 2'nin degerini ezer. Kural 1 kazanir.

## 3. Etkin Degerin Kaynagini Gosterme (Trace)

Bir indirme eklendiginde veya secenekleri belirlendiginde, arayuze (UI) bu degerlerin "nereden geldigini" bildirmek icin bir `trace` (iz/kaynak) sozlugu donulur. Bu yapi sayesinde UI'da "Etkin hiz siniri: 500 KB/sn · Kaynak: Gece indirme kurali" yazilabilir.

Ornek ic API donusu (`manager.py`'dan cikip UI'a giden yapi):
```json
{
  "options": {
    "max_speed_kb": 500,
    "dest_dir": "D:\\GeceKuyrugu",
    "split": 16
  },
  "trace": {
    "max_speed_kb": {"source": "rule", "source_id": "a1b2...", "source_name": "Gece Torrentleri"},
    "dest_dir": {"source": "rule", "source_id": "a1b2...", "source_name": "Gece Torrentleri"},
    "split": {"source": "default", "source_id": null, "source_name": "Genel Ayarlar"}
  }
}
```

- Eger kullanici degeri elle girdiyse `source` degeri `"user"` olur.
- Eger kural bulduysa `"rule"`, hicbir sey bulamadiysa `"default"` olur.
- Bu iz bilgisi yalnizca UI tarafinda gosterim (badge/tooltip) icin kullanilir, veritabaninda bu trace sozlugu saklanmaz (cunku options icine direkt gomulmus sayilir).

## 4. Gorsel Kural Editoru UI Taslagi

UI'da "Ayarlar > Kurallar" sekmesi altinda yer alacaktir.

```text
[ Kurallar (Rules Engine) ]

+-------------------------------------------------------------------------+
| [ Yeni Kural Ekle ]   [ Tumu Aktif/Pasif ]        [ Siralamayi Kaydet ] |
+-------------------------------------------------------------------------+
| = | # | Kural Adi           | Kosullar          | Eylemler          |   |
|---+---+---------------------+-------------------+-------------------+---|
| = | 1 | [x] Gece indirmesi  | Boyut > 20GB      | Hiz, Saat, Klasor | X |
| = | 2 | [x] YouTube video   | Domain=youtube... | Klasor            | X |
| = | 3 | [ ] ISO dosyalari   | Uzanti=iso        | Baglanti(16)      | X |
+-------------------------------------------------------------------------+

--- [ Kural Duzenle: Gece indirmesi ] -------------------------------------
Kosullar: ( [ Tumu Saglanmali (AND) v] )
  [ Kural Ekle ]
  [-] [ Boyut (MB)  v] [ Buyuktur (>) v] [ 20480           ]
  [-] [ Protokol    v] [ Esittir (=)  v] [ torrent         ]

Eylemler:
  [x] Hedef Klasor: [ D:\GeceKuyrugu                       ] [ Sec ]
  [x] Zamanlama:    [ 23:30 ] sonrasina ertele
  [x] Hiz Siniri:   [ 500 ] KB/sn
  [ ] Baglanti:     [     ] (Split)
  [ ] Proxy:        [                                      ]
  [ ] Otomasyon:    [ extract_and_move.bat                 ] [ Sec ]
---------------------------------------------------------------------------

--- [ Kural Test (Simulator) ] --------------------------------------------
URL, Dosya adi veya Link girin:
> https://example.com/ubuntu-24.04-desktop-amd64.iso (Boyut: 4GB)
[ Test Et ]

Sonuc: "ISO dosyalari" (Oncelik #3) kuralina takildi.
Etki:
 - Baglanti sayisi: 16 (Kaynak: ISO dosyalari kurali)
 - Hedef Klasor: C:\Downloads (Kaynak: Genel Ayarlar)
---------------------------------------------------------------------------
```

## 5. Onerilen RPC Imzalari

Python (api/server.py veya manager.py) tarafinda JavaScript'e acilacak fonksiyon imzalari:

```python
def rules_list() -> dict:
    """Tanimli butun kurallari priority sirasinda doner."""
    # Donus: {"ok": True, "rules": [...]}

def rules_save(rules: list[dict]) -> dict:
    """
    UI'da yapilan siralama ve degisiklikleri tek seferde kaydeder.
    Listedeki index sirasi, otomatik olarak 'priority' kabul edilir.
    """
    # Donus: {"ok": True}

def rules_simulate(url: str, filename: str = "", size_bytes: int = 0, protocol: str = "http") -> dict:
    """
    Verilen parametrelere gore hangi kurallarin tetiklendigini ve 
    ortaya cikan nihai actions/trace tablosunu doner.
    """
    # Donus: {
    #   "ok": True, 
    #   "matched_rules": ["id1", "id2"], 
    #   "effective_options": {...}, 
    #   "trace": {...}
    # }
```

## 6. Riskler ve Kenar Durumlar

- **Sonsuz Dongu Riski:** Kural hesaplama islemi yalitimli ve state-free olmalidir. Eylemler yalnizca url ekleme (add/resolve) asamasinda calistirilir. Devam eden (paused -> resume) bir indirmede kural motoru YENIDEN CALISTIRILMAZ.
- **Cakisan Hiz Sinirlari:** Kural tarafindan konulan hiz limiti, aria2 tarafina `max-overall-download-limit` (global) degil, `max-download-limit` (per-download) olarak iletilmelidir. Yoksa bir video indirme kurali, diger islerin de hizini keser.
- **Kural Silinince Ne Olur?** Mevcut inen veya inmis olan isler `downloads` tablosunda kendi `options` alanlarina sahiptir. Kural motoru degerleri bu alana bastigi icin, kural sonradan silinse bile devam eden is bu durumdan etkilenmez.
- **Migration Geri Alinabilirligi (Downgrade):** Yeni surume gecilip `rules` tablosu olustuktan sonra eski surum exe calistirilirse, eski exe'nin kodunda `rules` tablosunu okuyan bir blok olmadigi icin hicbir sey cokmez, uygulama normal calisir. Yeni eklenen indeksler ve tablolar DB'de atil olarak kalir.
- **Dosya Adi Bilinmezligi:** HTTP indirmelerinde (ozellikle CDN'ler) linkte dosya adi ve boyutu onceden bilinemeyebilir (Content-Disposition gerektirir). Bu durumda kural motoru yalnizca `url`, `domain` ve `protocol` uzerinden once bir islem yapar. LinkGrabber veya Probe ozelligi dosya adini/boyutunu cozerse kural motoru tekrar calistirilip (on-flight update) gercek klasor/hiz ayarlari set edilebilir. Bu asenkron yapinin "baslamadan once" (queued/paused) asamasinda yapilmasi cok kritiktir.
