# -*- coding: utf-8 -*-
"""Baslangic kisayolu (core/baslangic.py) — AG GEREKTIRMEZ, saniyeler surer.

PENCERE ACMAZ, AfuDM.exe'yi CALISTIRMAZ; sadece bir .lnk dosyasi yazar/siler.
Kullanicinin GERCEK Baslangic klasorunu KIRLETMEMEK icin `baslangic.KLASOR`
gecici bir klasore yonlendirilir.

Dogruladiklari:
 1. Kisayol yokken acik_mi() False
 2. ac() sonrasi dosya var, acik_mi() True
 3. Ikinci ac() patlamiyor (idempotent)
 4. kapat() sonrasi dosya yok, acik_mi() False
 5. hedef() gercekten var olan bir calistirilabilir gosteriyor
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import baslangic  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


with tempfile.TemporaryDirectory() as gecici:
    baslangic.KLASOR = Path(gecici) / "Startup"

    print("1) Hedef")
    calistirilabilir, argumanlar = baslangic.hedef()
    check("hedef var olan bir calistirilabilir dosya",
          Path(calistirilabilir).is_file(), calistirilabilir)
    check("argumanlar metin", isinstance(argumanlar, str))

    print("2) Kisayol yokken")
    check("klasor henuz olusmadi (ac() cagrilmadan)", not baslangic.KLASOR.is_dir())
    check("acik_mi() False", baslangic.acik_mi() is False)

    print("3) ac()")
    baslasi = time.time()
    baslangic.ac()
    sure = time.time() - baslasi
    check("kisayol dosyasi olustu", baslangic.kisayol_yolu().is_file())
    check("acik_mi() True", baslangic.acik_mi() is True)
    check("saniyeler surdu (pencere acilmadi, takilmadi)", sure < 20, f"{sure:.1f} sn")

    print("4) Ikinci ac()")
    try:
        baslangic.ac()
        check("ikinci ac() patlamiyor", True)
    except Exception as exc:  # noqa: BLE001
        check("ikinci ac() patlamiyor", False, repr(exc))
    check("dosya hala tek ve duruyor", baslangic.acik_mi() is True)

    print("5) kapat()")
    baslangic.kapat()
    check("kisayol dosyasi gitti", not baslangic.kisayol_yolu().is_file())
    check("acik_mi() False", baslangic.acik_mi() is False)

    print("6) kapat() ikinci kez (dosya yokken) patlamamali")
    try:
        baslangic.kapat()
        check("bos klasorde kapat() sessiz gecer", True)
    except Exception as exc:  # noqa: BLE001
        check("bos klasorde kapat() sessiz gecer", False, repr(exc))

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
