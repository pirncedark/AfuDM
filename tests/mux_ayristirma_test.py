# -*- coding: utf-8 -*-
"""MP4 ornek (sample) ayristirma testi — AG GEREKTIRMEZ, yerel dosyalarla calisir.

Birlestirici yazabilmek icin once kaynak dosyalari DOGRU okumak gerekiyor:
her ornegin dosyadaki yeri, boyutu, suresi ve anahtar kare olup olmadigi.
Bir tanesini bile kaydirirsak ses ile goruntu senkrondan cikar — ve bu, gozle
zor fark edilen bir hatadir. Bu yuzden sayilar BILINEN gerceklerle karsilastirilir:

  Kaynak: YouTube "Big Buck Bunny 60fps 4K" — sure 634.6 sn
  video.mp4 : itag 137 benzeri, avc1, PARCALANMIS (moof/mdat ~250 parca)
  ses.m4a   : itag 140, mp4a, parcalanmamis

Dosyalar yoksa test ATLANIR (baska makinede kosulabilsin diye).
"""
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from video import mp4mux  # noqa: E402

KAYNAK = Path(os.environ.get(
    "AFUDM_IZ_KLASORU",
    r"C:\Users\afuuu\AppData\Local\Temp\claude"
    r"\C--Users-afuuu\2cbfe70b-e0aa-4fda-9596-9e9c6b90b619\scratchpad\izler",
))
VIDEO = KAYNAK / "video.mp4"
SES = KAYNAK / "ses.m4a"

hatalar: list[str] = []


def kontrol(ad: str, kosul: bool, detay: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {detay}" if detay else ""))
    if not kosul:
        hatalar.append(ad)


if not VIDEO.exists() or not SES.exists():
    print(f"ATLANDI: ornek iz dosyalari yok ({KAYNAK})")
    sys.exit(0)

print("1) Parcalanmis video izi")
v = mp4mux.izi_oku(VIDEO)
kontrol("iz turu video", v.tur == "vide", v.tur)
kontrol("kodek avc1", v.kodek == "avc1", v.kodek)
kontrol("ornek bulundu", len(v.ornekler) > 1000, f"{len(v.ornekler)} ornek")
sure_sn = v.toplam_sure / v.timescale
kontrol("sure 634.6 sn'ye yakin", abs(sure_sn - 634.6) < 2, f"{sure_sn:.1f} sn")
# NOT: itag 137 bu videoda 30 fps. Basliktaki "60fps" ayri bir formatta (298/299).
# Onemli olan sabit sayi degil, kare sayisi ile surenin TUTARLI olmasi.
kare_hizi = len(v.ornekler) / sure_sn
kontrol("kare hizi makul ve tutarli", 20 <= kare_hizi <= 65, f"{kare_hizi:.1f} kare/sn")
kontrol("her parca icin bir anahtar kare",
        abs(sum(1 for o in v.ornekler if o.anahtar) - 123) <= 2,
        f"{sum(1 for o in v.ornekler if o.anahtar)} anahtar / 123 parca")
kontrol("anahtar kare var", sum(1 for o in v.ornekler if o.anahtar) > 0,
        f"{sum(1 for o in v.ornekler if o.anahtar)} anahtar kare")
toplam_bayt = sum(o.boyut for o in v.ornekler)
kontrol("ornek baytlari dosya boyutunu asmiyor", toplam_bayt < VIDEO.stat().st_size,
        f"{toplam_bayt/1048576:.1f} MB / {VIDEO.stat().st_size/1048576:.1f} MB")
kontrol("ornek baytlari dosyanin en az %80'i", toplam_bayt > VIDEO.stat().st_size * 0.8,
        f"%{toplam_bayt / VIDEO.stat().st_size * 100:.0f}")
kontrol("stsd (kodek basligi) alindi", len(v.stsd_ham) > 50, f"{len(v.stsd_ham)} bayt")

print("2) Ornek konumlari tutarli mi")
ilk = v.ornekler[0]
son = v.ornekler[-1]
kontrol("ilk ornek dosya icinde", 0 < ilk.ofset < VIDEO.stat().st_size, str(ilk.ofset))
kontrol("son ornek dosya icinde", son.ofset + son.boyut <= VIDEO.stat().st_size,
        f"{son.ofset + son.boyut}")
artan = all(v.ornekler[i].ofset <= v.ornekler[i + 1].ofset for i in range(len(v.ornekler) - 1))
kontrol("ornek konumlari artan sirada", artan)
kontrol("hicbir ornek sifir boyutlu degil", all(o.boyut > 0 for o in v.ornekler))

print("3) Ses izi (parcalanmamis)")
s = mp4mux.izi_oku(SES)
kontrol("iz turu ses", s.tur == "soun", s.tur)
kontrol("kodek mp4a", s.kodek == "mp4a", s.kodek)
kontrol("ornek bulundu", len(s.ornekler) > 1000, f"{len(s.ornekler)} ornek")
ses_sure = s.toplam_sure / s.timescale
kontrol("ses suresi 634.6 sn'ye yakin", abs(ses_sure - 634.6) < 2, f"{ses_sure:.1f} sn")
kontrol("ses baytlari dosyanin en az %80'i",
        sum(o.boyut for o in s.ornekler) > SES.stat().st_size * 0.8)

print("4) Iki iz ayni uzunlukta mi (senkron on kosulu)")
kontrol("video ve ses suresi 1 sn'den az farkli", abs(sure_sn - ses_sure) < 1.0,
        f"video {sure_sn:.2f} sn / ses {ses_sure:.2f} sn")

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
