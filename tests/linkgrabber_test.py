# -*- coding: utf-8 -*-
"""LinkGrabber cekirdegi testleri (v1.5 P0).

- ayikla: metin icinde gomulu http/https/ftp/magnet URL'leri yakalar
- normalize: sondaki noktalama/tirnak ayracini temizler
- tekil_les: ayni URL ve ayni magnet infohash tekrarlanmaz, sira korunur
- tur_bul: torrent/video/arsiv/http tahmini
- filtrele: tur + domain filtreleri
- probe_es_zamanli: fake_http ile boyut/dosya adi, eszamanlilik siniri

Foundation test deseni: check() + fails listesi, sys.exit(1) hata ile.
"""
from __future__ import annotations

import hashlib
import sys
import time

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")
sys.path.insert(0, r"C:\Users\afuuu\AfuDM\tests")

from core import linkgrabber as lg  # noqa: E402
from fake_http import SunucuAyarlari, baslat  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


print("1) ayikla — metin icinden URL cikarma")
cikti = lg.ayikla(
    "Bugun su dosyayi indir: https://ornek.com/dosya.iso lutfen. "
    "magnet:?xt=urn:btih:abc123 ve ftp://ftp.ornek.com/video.mp4"
)
check("http yakalandi", "https://ornek.com/dosya.iso" in cikti, str(cikti))
check("magnet yakalandi", "magnet:?xt=urn:btih:abc123" in cikti, str(cikti))
check("ftp yakalandi", "ftp://ftp.ornek.com/video.mp4" in cikti, str(cikti))
check("nokta URL'ye yapismadi (ayikla sonrası)", all(
    not u.endswith((".", ",")) for u in cikti), str(cikti))

print("2) normalize — son noktalama temizligi")
check("sondaki nokta atilir", lg.normalize("https://x.com/a.zip.") == "https://x.com/a.zip",
      lg.normalize("https://x.com/a.zip."))
check("sondaki virgul atilir", lg.normalize("https://x.com/a,") == "https://x.com/a",
      lg.normalize("https://x.com/a,"))
check("tirnak atilir", lg.normalize('"https://x.com/a"') == "https://x.com/a",
      lg.normalize('"https://x.com/a"'))
check("trim", lg.normalize("  https://x.com/a.zip  ") == "https://x.com/a.zip",
      lg.normalize("  https://x.com/a.zip  "))
check("sorgu korunur", lg.normalize("https://x.com/a?b=1&c=2") == "https://x.com/a?b=1&c=2",
      lg.normalize("https://x.com/a?b=1&c=2"))

print("3) tekil_les — ayni URL / magnet infohash tekrar edilmez")
check("ayni URL bir kez", lg.tekil_les(["https://x.com/a.zip", "https://x.com/a.zip"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://x.com/a.zip", "https://x.com/a.zip"])))
check("noktali hali tekille", lg.tekil_les(["https://x.com/a.zip.", "https://x.com/a.zip"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://x.com/a.zip.", "https://x.com/a.zip"])))
check("sira korunur", lg.tekil_les(["https://b.com/1", "https://a.com/2", "https://b.com/1"])
      == ["https://b.com/1", "https://a.com/2"], str(lg.tekil_les(["https://b.com/1", "https://a.com/2", "https://b.com/1"])))
m1 = "magnet:?xt=urn:btih:ABC123&dn=a&tr=http://t/announce"
m2 = "magnet:?xt=urn:btih:abc123&dn=b&tr=http://t/x"
check("ayni infohash bir kez (kucuk harf)", lg.tekil_les([m1, m2]) == [m1],
      str(lg.tekil_les([m1, m2])))
farkli = "magnet:?xt=urn:btih:ZYX999&dn=c"
check("farkli infohash ayrilir", len(lg.tekil_les([m1, m2, farkli])) == 2,
      str(lg.tekil_les([m1, m2, farkli])))

print("4) tur_bul — torrent / video / arsiv / http")
check("magnet -> torrent", lg.tur_bul("magnet:?xt=urn:btih:abc") == "torrent")
check(".torrent -> torrent", lg.tur_bul("https://x.com/a.torrent") == "torrent")
check(".zip -> arsiv", lg.tur_bul("https://x.com/a.zip") == "arsiv")
check(".tar.gz -> arsiv", lg.tur_bul("https://x.com/a.tar.gz") == "arsiv")
check(".mp4 -> video", lg.tur_bul("https://x.com/video.mp4") == "video")
check(".mp3 -> (video sayilir)", lg.tur_bul("https://x.com/sarki.mp3") == "video")
check("youtube -> video", lg.tur_bul("https://www.youtube.com/watch?v=abc") == "video")
check("vimeo -> video", lg.tur_bul("https://vimeo.com/123") == "video")
check("bilinmeyen -> http", lg.tur_bul("https://x.com/sayfa") == "http")
check("alt alan adi video sitesi", lg.tur_bul("https://m.youtube.com/watch?v=abc") == "video")

print("5) filtrele — tur + domain")
liste = ["https://x.com/a.zip", "https://x.com/b.mp4", "magnet:?xt=urn:btih:abc",
         "https://y.com/c.mp4"]
check("sadece video", lg.filtrele(liste, sadece={"video"}) == ["https://x.com/b.mp4", "https://y.com/c.mp4"],
      str(lg.filtrele(liste, sadece={"video"})))
check("sadece torrent", lg.filtrele(liste, sadece={"torrent"}) == ["magnet:?xt=urn:btih:abc"],
      str(lg.filtrele(liste, sadece={"torrent"})))
check("domain x.com", lg.filtrele(liste, domain="x.com") == ["https://x.com/a.zip", "https://x.com/b.mp4"],
      str(lg.filtrele(liste, domain="x.com")))
check("domain + tur birlikte",
      lg.filtrele(liste, sadece={"video"}, domain="x.com") == ["https://x.com/b.mp4"],
      str(lg.filtrele(liste, sadece={"video"}, domain="x.com")))
check("www on eki esnek", lg.filtrele(liste, domain="www.x.com") == ["https://x.com/a.zip", "https://x.com/b.mp4"],
      str(lg.filtrele(liste, domain="www.x.com")))

print("6) probe_es_zamanli — fake_http ile boyut/ad, eszamanlilik siniri")
veri = hashlib.sha256(b"LinkGrabber").digest() * 5  # 160 bayt deterministic
ayarlar = SunucuAyarlari(veri=veri)
port, httpd = baslat(ayarlar)
try:
    url = f"http://127.0.0.1:{port}/dizin/video_clip.mp4"
    sonuc = lg.probe_es_zamanli([url], es_zamanli=2, timeout=3.0)
    bilgi = sonuc.get(url, {})
    check("probe ok=True", bilgi.get("ok") is True, str(bilgi))
    check("boyut dogru", bilgi.get("size") == len(veri),
          f"{bilgi.get('size')} != {len(veri)}")
    check("dosya adi cozuldu", bilgi.get("filename", "").endswith(".mp4"), str(bilgi.get("filename")))

    # eszamanlilik siniri: 6 URL, max 2 worker — log patlamasi olmadan biter
    urller = [f"http://127.0.0.1:{port}/dosya{i}.bin" for i in range(6)]
    basla = time.time()
    sonuclar = lg.probe_es_zamanli(urller, es_zamanli=2, timeout=3.0)
    gecen = time.time() - basla
    check("6 URL'den 6 sonuc", len(sonuclar) == 6, str(len(sonuclar)))
    check("hepsi ok", all(s.get("ok") for s in sonuclar.values()), str(sonuclar))
    check("hizli biter (toplu probe)", gecen < 5.0, f"{gecen:.2f} s")
finally:
    httpd.shutdown()

print()
if fails:
    print(f"BASARISIZ ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"Hepsi gecti ({_toplam} kontrol)")