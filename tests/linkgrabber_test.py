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

print("2b) normalize — URL canonicalization (scheme/host kucuk, path/query korunur)")
check("scheme kucuk harf", lg.normalize("HTTPS://X.com/a.zip") == "https://x.com/a.zip",
      lg.normalize("HTTPS://X.com/a.zip"))
check("scheme kucuk harf (ftp)", lg.normalize("FTP://X.com/a.zip") == "ftp://x.com/a.zip",
      lg.normalize("FTP://X.com/a.zip"))
check("host kucuk harf", lg.normalize("https://GIThub.COM/Rapo/File.exe") == "https://github.com/Rapo/File.exe",
      lg.normalize("https://GIThub.COM/Rapo/File.exe"))
check("path case korunur", lg.normalize("https://x.com/File.zip") == "https://x.com/File.zip",
      lg.normalize("https://x.com/File.zip"))
check("query case korunur", lg.normalize("https://x.com/a?TOKEN=AbC&b=1") == "https://x.com/a?TOKEN=AbC&b=1",
      lg.normalize("https://x.com/a?TOKEN=AbC&b=1"))
check("fragment atilir", lg.normalize("https://x.com/a.zip#kaydir") == "https://x.com/a.zip",
      lg.normalize("https://x.com/a.zip#kaydir"))
check("port korunur", lg.normalize("HTTP://X.com:8080/a") == "http://x.com:8080/a",
      lg.normalize("HTTP://X.com:8080/a"))
check("userinfo host'u etkilemez", lg.normalize("https://KULLANICI:sifre@X.com/a") == "https://KULLANICI:sifre@x.com/a",
      lg.normalize("https://KULLANICI:sifre@X.com/a"))
check("magnet dokunulmaz", lg.normalize("MAGNET:?xt=urn:btih:ABC") == "MAGNET:?xt=urn:btih:ABC",
      lg.normalize("MAGNET:?xt=urn:btih:ABC"))

print("3) tekil_les — ayni URL / magnet infohash tekrar edilmez")
check("ayni URL bir kez", lg.tekil_les(["https://x.com/a.zip", "https://x.com/a.zip"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://x.com/a.zip", "https://x.com/a.zip"])))
check("noktali hali tekille", lg.tekil_les(["https://x.com/a.zip.", "https://x.com/a.zip"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://x.com/a.zip.", "https://x.com/a.zip"])))
check("sira korunur", lg.tekil_les(["https://b.com/1", "https://a.com/2", "https://b.com/1"])
      == ["https://b.com/1", "https://a.com/2"], str(lg.tekil_les(["https://b.com/1", "https://a.com/2", "https://b.com/1"])))
check("host case tekille", lg.tekil_les(["https://X.COM/a.zip", "https://x.com/a.zip"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://X.COM/a.zip", "https://x.com/a.zip"])))
check("fragment farki tekille", lg.tekil_les(["https://x.com/a.zip#x", "https://x.com/a.zip#y"]) == ["https://x.com/a.zip"],
      str(lg.tekil_les(["https://x.com/a.zip#x", "https://x.com/a.zip#y"])))
check("path case AYRI KALIR", lg.tekil_les(["https://x.com/File.zip", "https://x.com/file.zip"])
      == ["https://x.com/File.zip", "https://x.com/file.zip"],
      str(lg.tekil_les(["https://x.com/File.zip", "https://x.com/file.zip"])))
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
check("www on ekli video sitesi", lg.tur_bul("https://www.vimeo.com/123") == "video")
check("taklit video sitesi (evil.com HARIC)", lg.tur_bul("https://evilyoutube.com/x") == "http")
check("taklit video sitesi (youtube.com.evil.com HARIC)", lg.tur_bul("https://youtube.com.evil.com/x") == "http")

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

print("5b) filtrele — domain matching dogru uca dayali (subdomain dahil, taklit haric)")
gh = ["https://github.com/a.zip", "https://api.github.com/b.mp4",
      "https://sub.api.github.com/c", "https://evilgithub.com/x.zip",
      "https://notgithub.com/y", "https://github.com.evil.com/z"]
check("github.com kendisi", lg.filtrele(gh, domain="github.com")[0] == "https://github.com/a.zip",
      str(lg.filtrele(gh, domain="github.com")))
check("alt alan adi dahil", set(lg.filtrele(gh, domain="github.com")) >=
      {"https://api.github.com/b.mp4", "https://sub.api.github.com/c"},
      str(lg.filtrele(gh, domain="github.com")))
check("evilgithub.com HARIC", "https://evilgithub.com/x.zip" not in lg.filtrele(gh, domain="github.com"),
      str(lg.filtrele(gh, domain="github.com")))
check("notgithub.com HARIC", "https://notgithub.com/y" not in lg.filtrele(gh, domain="github.com"),
      str(lg.filtrele(gh, domain="github.com")))
check("github.com.evil.com HARIC", "https://github.com.evil.com/z" not in lg.filtrele(gh, domain="github.com"),
      str(lg.filtrele(gh, domain="github.com")))
check("www on eki sadece on ek (wwexample.com HARIC)",
      lg.filtrele(["https://wwexample.com/a.zip"], domain="example.com") == [],
      str(lg.filtrele(["https://wwexample.com/a.zip"], domain="example.com")))
check("www.example.com host dahil",
      lg.filtrele(["https://www.example.com/a.zip"], domain="example.com") == ["https://www.example.com/a.zip"],
      str(lg.filtrele(["https://www.example.com/a.zip"], domain="example.com")))
check("www.example.com domain, host dropsuz dahil",
      lg.filtrele(["https://example.com/a.zip"], domain="www.example.com") == ["https://example.com/a.zip"],
      str(lg.filtrele(["https://example.com/a.zip"], domain="www.example.com")))

print("5c) ogeleri_filtrele — arama/wildcard + tur + domain + boyut BIRLIKTE")
_ogeler = [
    {"url": "https://cdn.com/file1.zip", "tur": "arsiv", "filename": "file1.zip", "size": 850 * (1 << 20)},
    {"url": "https://cdn.com/file2.zip", "tur": "arsiv", "filename": "file2.zip", "size": 1400 * (1 << 20)},
    {"url": "https://cdn.com/image.jpg", "tur": "http", "filename": "image.jpg", "size": 420 * (1 << 10)},
    {"url": "https://video.example.com/wp.mp4", "tur": "video", "filename": "wp.mp4", "size": 5 * (1 << 30)},
    {"url": "magnet:?xt=urn:btih:abc", "tur": "torrent", "filename": "", "size": None},
]
check("filtresiz hepsi", lg.ogeleri_filtrele(_ogeler) == [0, 1, 2, 3, 4], "bos filtre")
check("wildcard *.zip", lg.ogeleri_filtrele(_ogeler, ara="*.zip") == [0, 1], str(lg.ogeleri_filtrele(_ogeler, ara="*.zip")))
check("basit arama (parca)", lg.ogeleri_filtrele(_ogeler, ara="image") == [2], "image")
check("buyuk kucuk harf duyarsiz", lg.ogeleri_filtrele(_ogeler, ara="*IMAGE*") == [2], "*IMAGE*")
check("soru isareti joker", lg.ogeleri_filtrele(_ogeler, ara="file?.zip") == [0, 1], "file?.zip")
check("tur filtre", lg.ogeleri_filtrele(_ogeler, sadece={"video"}) == [3], "video")
check("domain filtre (subdomain dahil)",
      lg.ogeleri_filtrele(_ogeler, domain="example.com") == [3], "example.com -> wp.mp4")
check("domain filtre taklit haric",
      lg.ogeleri_filtrele(_ogeler, domain="cdn.com") == [0, 1, 2], "cdn.com")
check("min_boyut 1 GB", lg.ogeleri_filtrele(_ogeler, min_boyut=1 << 30) == [1, 3], "1GB+")
check("max_boyut 1 GB", lg.ogeleri_filtrele(_ogeler, max_boyut=1 << 30) == [0, 2], "1GB alti")
check("boyut araligi", lg.ogeleri_filtrele(_ogeler, min_boyut=1 << 20, max_boyut=1 << 30) == [0], "1MB..1GB")
check("boyut filtresi sondasiz bilinmeyeni eler",
      lg.ogeleri_filtrele(_ogeler, min_boyut=1) == [0, 1, 2, 3], "magnet bilinmeyen elendi")
check("hepsi birlikte", lg.ogeleri_filtrele(
    _ogeler, ara="*.zip", sadece={"arsiv"}, domain="cdn.com", min_boyut=100 * (1 << 20)) == [0, 1],
    "*.zip + arsiv + cdn.com + 100MB")
check("eslesmeyen bos liste", lg.ogeleri_filtrele(_ogeler, ara="cisim") == [], "cisim")
check("ogeler bos ise bos", lg.ogeleri_filtrele([], ara="x") == [], "bos")

print("5d) onceki_eslesen — gecmis kayitlarina gore mevcut olanlar (engellemez, isaretler)")
_gecmis = [
    "https://cdn.com/file1.zip",
    "HTTP://cdn.com/file1.zip",  # ayni URL farkli case -> normalize birlestirir
    "magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef",
    "magnet:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF",  # infohash buyuk harf
]
_kontrol = [
    "https://cdn.com/file1.zip",   # gecmiste var
    "http://cdn.com/file1.zip?x=1",  # farkli query -> YOK
    "magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef",  # infohash eslesir
    "https://cdn.com/line2.zip",   # yok
]
check("gecmistekiler isaretlenir",
      set(lg.onceki_eslesen(_kontrol, _gecmis)) ==
      {"https://cdn.com/file1.zip",
       "magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef"},
      str(lg.onceki_eslesen(_kontrol, _gecmis)))
check("buyuk/kucuk harf normalize birlesir",
      len(lg.onceki_eslesen(["HTTP://cdn.com/File1.ZIP?"], ["http://cdn.com/file1.zip"])) == 0,
      "path farki File1 vs file1 -> farkli (case korunur)")
check("gecmis bos ise bos", lg.onceki_eslesen(_kontrol, []) == [], "bos gecmis")
check("adres bos ise bos", lg.onceki_eslesen([], _gecmis) == [], "bos adres")
check("infohash thumbnailsiz tekrar etmez", len(lg.onceki_eslesen(
    ["magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef"] * 3, _gecmis)) == 1,
    "magnet tekili")
print("5e) manager.gecmis_sources — DB'den kaynak listesi")
import inspect
import core.manager as mgr
if hasattr(mgr, "Manager"):
    sig = inspect.signature(mgr.Manager.gecmis_sources)
    check("gecmis_sources limit parametresi var",
          any(p.name == "limit" for p in sig.parameters.values()), str(sig))
    donen = sig.return_annotation
    check("gecmis_sources list[str] doner", "list" in str(donen), str(donen))
else:
    check("manager.Manager bulunamadi", False, "gecmis_sources eksik")

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

    check("hard limit tanimli ve mantikli",
          0 < lg.PROBE_MAKS_WORKER <= 16, str(lg.PROBE_MAKS_WORKER))
    # es_zamanli 0/negatif/e-posta yuksek girilse havuz patlamaz, cap takilir
    cok = lg.probe_es_zamanli([url], es_zamanli=9999, timeout=3.0)
    check("es_zamanli 9999 cap'lenir", cok.get(url, {}).get("ok") is True,
          str(cok.get(url, {})))
    sifir = lg.probe_es_zamanli([url], es_zamanli=0, timeout=3.0)
    check("es_zamanli 0 en az 1 worker", sifir.get(url, {}).get("ok") is True,
          str(sifir.get(url, {})))
    hatali = lg.probe_es_zamanli([url], es_zamanli="asci", timeout=3.0)
    check("es_zamanli metin varsayilana duser", hatali.get(url, {}).get("ok") is True,
          str(hatali.get(url, {})))
finally:
    httpd.shutdown()

print()
if fails:
    print(f"BASARISIZ ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"Hepsi gecti ({_toplam} kontrol)")