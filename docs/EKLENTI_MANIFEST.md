# AfuDM eklenti manifesti (v2.0 "Plugin Platform")

Bu belge semanin ANLATIMIDIR; TEK KAYNAK `core/eklenti.py` icindeki
`manifest_dogrula`. Ikisi ayrilirsa kod gecerlidir.

## Guven modeli — once bunu oku

AfuDM eklentileri **guvenilen eklenti** modeliyle calisir.

* Eklenti kodu AfuDM'i calistiran kullanicinin **tum yetkileriyle** calisir:
  diski okur/yazar, aga cikar.
* **Sandbox YOKTUR.** Ayri surec yalnizca **cokme ve takilma** izolasyonu
  saglar: eklenti coker veya cevap vermezse AfuDM etkilenmez, surec oldurulur
  ve "Yeniden baslat" ile toparlanir.
* Manifestteki `izinler` ve `domainler` **beyandir**. Kurulumdan once
  kullaniciya gosterilir ve kayda gecer, ama **teknik olarak zorlanmaz**.
* Manifestte `sha256` alanı ile paketin imzasını (içerik özetini) sunabilirsin. Aksi takdirde, yalnızca "imzasız eklentiye izin ver" ayarı açık olanlar kurabilir.

## Paket bicimi

`.afup` = ZIP. `eklenti.json` **kokte** olmak zorundadir. Arsiv disina yazmaya
calisan girdi (`..`, mutlak yol) kurulumu reddettirir. Acik klasor de kabul
edilir (gelistirme icin).

## Alanlar

| Alan | Zorunlu | Aciklama |
|---|---|---|
| `ad` | evet | kimlik; `^[a-z0-9][a-z0-9_-]{1,39}$` |
| `surum` | evet | `1.2.3` bicimi |
| `giris` | evet | paket icindeki `.py` dosyasi (koke gore) |
| `baslik` | hayir | arayuzde gorunen ad (bossa `ad`) |
| `aciklama` | hayir | en cok 500 karakter |
| `yazar` | hayir | |
| `afudm_min` / `afudm_max` | hayir | uyumlu AfuDM surum araligi |
| `izinler` | hayir | beyan edilen izin anahtarlari (asagida) |
| `domainler` | hayir | erisilecegi bildirilen alan adlari (`*.ornek.com`) |
| `ayar_semasi` | hayir | arayuzun form uretecegi ayar alanlari |
| `sha256` | hayir | `eklenti.json` HARIC paket icindeki tum dosyalarin (isimlerine gore sirali) okunup birlestirilmesiyle hesaplanan SHA256 ozeti |

Bilinen izin anahtarlari: `indirme_oku`, `indirme_ekle`, `indirme_yonet`,
`ayar_oku`, `ayar_yaz`, `ag`, `dosya_oku`, `dosya_yaz`, `bildirim`.
Bilinmeyen anahtar reddedilmez; arayuzde ham haliyle gosterilir.

### `ayar_semasi` ogesi

```json
{
  "anahtar": "aralik_dk",
  "tur": "sayi",
  "etiket": "Kontrol araligi (dk)",
  "aciklama": "",
  "varsayilan": 15,
  "en_az": 1,
  "en_cok": 1440,
  "uygulama": "hemen"
}
```

`tur`: `metin` | `sayi` | `anahtar` (ac/kapa) | `secim` (+ `secenekler`).
`uygulama` rozeti: `hemen` | `yeni_indirmeler` | `sonraki_baslatma` |
`servis_yeniden`. Gecersiz TEK alan HICBIR alani yazmaz (atomik ayar).

## Ornek manifest

```json
{
  "ad": "ornek-eklenti",
  "baslik": "Ornek Eklenti",
  "surum": "1.0.0",
  "yazar": "Ben",
  "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  "aciklama": "Biten indirmeleri bir dosyaya yazar.",
  "giris": "main.py",
  "afudm_min": "2.0.0",
  "izinler": ["indirme_oku", "dosya_yaz"],
  "domainler": [],
  "ayar_semasi": [
    {"anahtar": "dosya", "tur": "metin", "etiket": "Cikti dosyasi",
     "varsayilan": "gecmis.txt", "uygulama": "hemen"}
  ]
}
```

## Giris dosyasi

Hepsi istege baglidir; bulunani cagrilir (bkz. `core/eklenti_host.py`):

```python
def baslat(ctx):        # ctx.ad, ctx.surum, ctx.ayarlar, ctx.klasor, ctx.log()
    ctx.log("hazir")

def ayar_degisti(ayarlar): ...
def olay(ad, veri): ...
def durdur(): ...
```

`print()` protokolu bozmaz: host stdout'u gunluge yonlendirir, satirlar
arayuzdeki "Gunluk" bolumunde gorunur.

## Zaman asimlari

* `baslat` icin 20 sn, diger istekler icin 15 sn, saglik nabzi icin 5 sn.
* Sure asilirsa surec **oldurulur**, durum `zaman_asimi` olur ve son hata
  arayuzde yazar.

## Guncelleme ve geri alma

Guncellemede once eski klasorun yedegi alinir. Paket acilmazsa, giris dosyasi
yoksa veya yeni surum baslatilamazsa **onceki surume geri donulur** (dosyalar +
kayit + gerekirse surec). Kullanici ayarlari korunur; yeni alanlar varsayilan
degeriyle gelir.
