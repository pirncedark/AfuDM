"""Tarayicidan gelen oturum cerezleri — giris gerektiren sitelerden indirme icin.

Uzanti, tarayicinin O ADRESE gonderecegi cerezleri (chrome.cookies.getAll({url}))
yollar. Burada dogrulanir ve iki bicime cevrilir:
  - `baslik()`   -> aria2'ye "Cookie:" basligi. aria2 `load-cookies` ayarini
                    indirme basina YOK SAYIYOR (yalniz global okuyor; olculdu),
                    bu yuzden basliktan baska yol yok.
  - `netscape()` -> yt-dlp'nin `--cookies` dosyasi.

GUVENLIK: cerezler oturum anahtaridir.
  - Veritabanina YAZILMAZ; yonetici bellekte tutar, is bitince birakir.
  - yt-dlp dosyasi `data/cerez/` altinda, is bitince/silinince silinir;
    uygulama acilirken artiklar temizlenir.
  - Satir sonu/sekme iceren cerez atilir: aria2 basligina veya dosyaya
    satir enjekte edilemez.
"""
from __future__ import annotations

from pathlib import Path

from core import paths

KLASOR = paths.DATA / "cerez"
EN_COK_CEREZ = 300
EN_COK_BAYT = 32 * 1024
_YASAK = set("\r\n\t\x00")


def _temiz_metin(deger: object, ad_mi: bool = False) -> str | None:
    if not isinstance(deger, str):
        return None
    if any(ch in _YASAK for ch in deger):
        return None
    if ad_mi and (not deger or any(ch in deger for ch in ";= ")):
        return None
    if not ad_mi and ";" in deger:
        return None
    return deger


def temizle(cerezler: object) -> list[dict]:
    """Guvenilmeyen girdiden gecerli cerezleri sec; bozuk olani sessizce at."""
    if not isinstance(cerezler, list):
        return []
    sonuc: list[dict] = []
    toplam = 0
    for ham in cerezler[:EN_COK_CEREZ]:
        if not isinstance(ham, dict):
            continue
        ad = _temiz_metin(ham.get("name"), ad_mi=True)
        deger = _temiz_metin(ham.get("value", ""))
        alan = _temiz_metin(ham.get("domain", ""))
        yol = _temiz_metin(ham.get("path", "/")) or "/"
        if ad is None or deger is None or not alan or " " in alan:
            continue
        toplam += len(ad) + len(deger)
        if toplam > EN_COK_BAYT:
            break
        try:
            bitis = max(0, int(float(ham.get("expirationDate") or 0)))
        except (TypeError, ValueError):
            bitis = 0
        sonuc.append({
            "name": ad,
            "value": deger,
            "domain": alan,
            "path": yol if yol.startswith("/") else "/",
            "secure": bool(ham.get("secure")),
            # hostOnly: yalniz o alan adi; degilse alt alan adlari da dahil
            "hostOnly": bool(ham.get("hostOnly", not alan.startswith("."))),
            "expirationDate": bitis,
        })
    return sonuc


def baslik(cerezler: list[dict]) -> str:
    """aria2 icin tek satir Cookie degeri."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cerezler)


def netscape(cerezler: list[dict]) -> str:
    """yt-dlp / curl'un okudugu Netscape cookies.txt bicimi."""
    satirlar = ["# Netscape HTTP Cookie File", "# AfuDM tarafindan uretildi — is bitince silinir"]
    for c in cerezler:
        alan = c["domain"]
        if c["hostOnly"]:
            alan = alan.lstrip(".")
            alt = "FALSE"
        else:
            alan = alan if alan.startswith(".") else "." + alan
            alt = "TRUE"
        satirlar.append("\t".join([
            alan, alt, c["path"], "TRUE" if c["secure"] else "FALSE",
            str(c["expirationDate"]), c["name"], c["value"],
        ]))
    return "\n".join(satirlar) + "\n"


def _dosya_adi(anahtar: str) -> Path:
    guvenli = "".join(ch if ch.isalnum() else "_" for ch in anahtar)
    return KLASOR / f"{guvenli}.txt"


def dosya_yaz(anahtar: str, cerezler: list[dict]) -> Path:
    KLASOR.mkdir(parents=True, exist_ok=True)
    hedef = _dosya_adi(anahtar)
    hedef.write_text(netscape(cerezler), encoding="utf-8")
    return hedef


def sil(anahtar: str) -> None:
    try:
        _dosya_adi(anahtar).unlink(missing_ok=True)
    except OSError:
        pass


def artiklari_temizle() -> int:
    """Onceki calismadan (cokme vb.) kalan cerez dosyalarini sil."""
    if not KLASOR.is_dir():
        return 0
    sayi = 0
    for dosya in KLASOR.glob("*.txt"):
        try:
            dosya.unlink()
            sayi += 1
        except OSError:
            pass
    return sayi
