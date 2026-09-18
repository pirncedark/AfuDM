# -*- coding: utf-8 -*-
"""Kaydetme penceresi arka ucu (core/kaydet.py) — AG GEREKTIRMEZ, saniyeler surer.

Dogruladiklari:
 1. Kategori tahmini (uzanti, magnet, video turu)
 2. Dosya adi temizligi — yol ayraci/kacis karakteri gecmesin
 3. Klasor agaci: kisayollar, alt klasor okuma, yeni klasor
 4. Bekleyenler: cerez/baslik ARAYUZE SIZMAZ, onaylanan istek bir kez alinir,
    suresi gecen istek (ve cerezleri) atilir
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import kaydet  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


print("1) Kategori tahmini")
for url, beklenen in [
    ("https://ornek.com/film.mkv", "video"),
    ("https://ornek.com/a/b/sarki.mp3?x=1", "muzik"),
    ("https://ornek.com/kitap.pdf", "belge"),
    ("https://ornek.com/kur.exe", "program"),
    ("https://ornek.com/paket.tar.gz", "arsiv"),
    ("https://ornek.com/resim.JPEG", "resim"),
    ("magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10", "torrent"),
    ("https://www.youtube.com/watch?v=abc", "genel"),
]:
    check(f"{url[:34]} -> {beklenen}", kaydet.kategori_tahmin(url) == beklenen,
          kaydet.kategori_tahmin(url))
# Uzantisi olmayan video sayfasi: turu yt-dlp'den gelir
check("video sayfasi tur bilgisiyle video olur",
      kaydet.kategori_tahmin("https://www.youtube.com/watch?v=abc", "video") == "video")
check("torrent turu uzantisiz da taninir",
      kaydet.kategori_tahmin("https://ornek.com/x", "torrent") == "torrent")
# Sorgu dizesindeki nokta uzanti sanilmamali
check("sorgudaki nokta uzanti degildir",
      kaydet.kategori_tahmin("https://ornek.com/indir?dosya=a.mp4") == "genel")

print("2) Kategori klasoru")
check("kategori ana klasorun ALTINA iner",
      kaydet.kategori_klasoru(r"C:\\i", "video").endswith("Video"))
check("bilinmeyen kategori Genel'e duser",
      kaydet.kategori_klasoru(r"C:\\i", "yok").endswith("Genel"))
check("her kategorinin klasor adi var",
      set(kaydet.KATEGORILER) <= set(kaydet.KATEGORI_KLASORU))

print("3) Dosya adi temizligi")
KOTU_AD = '..\\..\\sistem<>:"|?*.exe'   # yol ayraci + Windows'un yasak karakterleri
check("yol ayraci ve yasak karakter temizlenir",
      kaydet.guvenli_dosya_adi(KOTU_AD) == ".._.._sistem_______.exe",
      kaydet.guvenli_dosya_adi(KOTU_AD))
check("satir sonu ad icinde kalmaz", "\n" not in kaydet.guvenli_dosya_adi("a\nb"))
check("bos ad bos doner", kaydet.guvenli_dosya_adi("   ") == "")
check("uzun ad kirpilir", len(kaydet.guvenli_dosya_adi("a" * 400)) == 200)
check("sondaki nokta/bosluk atilir (Windows kabul etmez)",
      kaydet.guvenli_dosya_adi("dosya. . ") == "dosya", kaydet.guvenli_dosya_adi("dosya. . "))

with tempfile.TemporaryDirectory() as gecici:
    tmp = Path(gecici)
    print("4) Klasor agaci")
    (tmp / "Filmler" / "2025").mkdir(parents=True)
    (tmp / "bos").mkdir()
    (tmp / "not.txt").write_text("x", encoding="utf-8")
    ogeler = kaydet.alt_klasorler(str(tmp))
    adlar = [o["ad"] for o in ogeler]
    check("yalniz klasorler listelenir", adlar == ["bos", "Filmler"], str(adlar))
    check("alt klasoru olan isaretli", next(o for o in ogeler if o["ad"] == "Filmler")["alt"] is True)
    check("bos klasor isaretsiz", next(o for o in ogeler if o["ad"] == "bos")["alt"] is False)
    try:
        kaydet.alt_klasorler(str(tmp / "yok"))
        check("olmayan klasor hata verir", False)
    except ValueError:
        check("olmayan klasor hata verir", True)

    yeni = kaydet.klasor_olustur(str(tmp), "Yeni Klasör")
    check("yeni klasor olusuyor", Path(yeni).is_dir())
    check("yeni klasor adi temizleniyor",
          Path(kaydet.klasor_olustur(str(tmp), "a/b")).name == "a_b")
    try:
        kaydet.klasor_olustur(str(tmp), "   ")
        check("bos ad reddedilir", False)
    except ValueError:
        check("bos ad reddedilir", True)

    kisa = kaydet.kisayollar(str(tmp / "indirmeler"))
    check("AfuDM klasoru kisayollarda ilk", kisa and kisa[0]["anahtar"] == "afudm")
    check("kisayol yoksa olusturulur", (tmp / "indirmeler").is_dir())
    check("en az bir disk var", any(o["anahtar"] == "disk" for o in kisa))
    check("ayni yol iki kez gelmez",
          len({o["yol"].lower() for o in kisa}) == len(kisa))

print("5) Bekleyen istekler")
b = kaydet.Bekleyenler()
kimlik = b.ekle({
    "url": "https://ornek.com/f.zip", "filename": "f.zip", "kind": "http",
    "cookies": [{"name": "sid", "value": "GIZLI"}], "headers": {"Referer": "https://ornek.com/"},
    "user_agent": "Mozilla/5.0",
})
ozet = b.ozet()
check("bekleyen listede gorunuyor", len(ozet) == 1 and ozet[0]["id"] == kimlik)
check("cerez arayuze SIZMIYOR", "GIZLI" not in str(ozet))
check("baslik da sizmiyor", "Referer" not in str(ozet))
istek = b.al(kimlik)
check("onayda TAM istek doner (cerez dahil)",
      istek and istek["cookies"][0]["value"] == "GIZLI")
check("ayni istek ikinci kez alinamaz", b.al(kimlik) is None)
check("alinan istek listeden dustu", b.ozet() == [])

eski = b.ekle({"url": "https://ornek.com/eski.zip"})
b._isler[eski]["zaman"] = time.time() - kaydet.Bekleyenler.SURE - 1
taze = b.ekle({"url": "https://ornek.com/taze.zip"})
kalanlar = [o["id"] for o in b.ozet()]
check("suresi gecen istek atildi", kalanlar == [taze], str(kalanlar))
check("suresi gecenin istegi de gitti", b.al(eski) is None)

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
