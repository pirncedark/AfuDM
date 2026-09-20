# -*- coding: utf-8 -*-
"""Gonderilecek paketi hazirlar.

    python paketle.py            # cekirdek paket (~23 MB) — video motorlari HARIC
    python paketle.py --tam      # her sey icinde (~137 MB)

Cekirdek paket neden var: kullanici 137 MB indirmek zorunda kalmasin. Icinde
yalniz ZORUNLU motor (aria2c) bulunur; video motorlarini isteyen Ayarlar'dan
tek tikla indirir (bkz. core/engines.py).

Paket tam PORTABLE kalir: `data/` ve `downloads/` ilk calistirmada uygulama
klasorunun icinde olusur, sisteme hicbir sey yazilmaz.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "build_out" / "paket"

# Paketin icine giren dosyalar. engine/ ozel: hangi motorun gireceği secime bagli.
# afuadm.py/.bat: komut satiri araci (core/ + api/ Python kaynagi da gerekli).
# headless.py: `afuadm server start` arayuzsuz servisi bununla acar
# (webview'i hic import etmez; bkz. headless.py modul basligi).
KOPYALANACAK_DOSYALAR = ("AfuDM.exe", "README.md", "THIRD_PARTY_NOTICES.md",
                         "afuadm.py", "afuadm.bat", "headless.py")
KOPYALANACAK_KLASORLER = ("ui", "extension", "trackers", "core", "api")

CEKIRDEK_MOTORLAR = ("aria2c.exe",)
TAM_MOTORLAR = ("aria2c.exe", "yt-dlp.exe", "ffmpeg.exe")

# Paketin icine ASLA girmeyecekler (gelistirme artiklari / kisisel veri)
ATLANACAK = {"__pycache__", ".playwright-mcp"}


def mb(bayt: int) -> float:
    return round(bayt / 1048576, 1)


def klasor_boyutu(yol: Path) -> int:
    return sum(f.stat().st_size for f in yol.rglob("*") if f.is_file())


def paketle(tam: bool) -> Path:
    hedef = CIKTI / "AfuDM"
    if CIKTI.exists():
        shutil.rmtree(CIKTI)
    hedef.mkdir(parents=True)

    eksikler = []
    for ad in KOPYALANACAK_DOSYALAR:
        kaynak = KOK / ad
        if not kaynak.exists():
            eksikler.append(ad)
            continue
        shutil.copy2(kaynak, hedef / ad)

    for ad in KOPYALANACAK_KLASORLER:
        kaynak = KOK / ad
        if not kaynak.exists():
            eksikler.append(ad + "/")
            continue
        shutil.copytree(
            kaynak, hedef / ad,
            ignore=shutil.ignore_patterns(*ATLANACAK),
        )

    motorlar = TAM_MOTORLAR if tam else CEKIRDEK_MOTORLAR
    (hedef / "engine").mkdir()
    for ad in motorlar:
        kaynak = KOK / "engine" / ad
        if not kaynak.exists():
            eksikler.append("engine/" + ad)
            continue
        shutil.copy2(kaynak, hedef / "engine" / ad)

    if eksikler:
        raise SystemExit("HATA — paketin icine girecek dosya bulunamadi: "
                         + ", ".join(eksikler))

    # Bos klasorler: ilk calistirmada zaten olusur ama kullanici gorsun diye acilir
    (hedef / "downloads").mkdir()

    return hedef


def main() -> int:
    ayristirici = argparse.ArgumentParser(description="AfuDM paketleyici")
    ayristirici.add_argument("--tam", action="store_true",
                             help="video motorlarini da koy (~137 MB)")
    secim = ayristirici.parse_args()

    hedef = paketle(secim.tam)
    toplam = klasor_boyutu(hedef)

    print(("TAM PAKET" if secim.tam else "CEKIRDEK PAKET") + " hazir:")
    print("  " + str(hedef))
    for parca in sorted(hedef.iterdir()):
        boyut = parca.stat().st_size if parca.is_file() else klasor_boyutu(parca)
        if boyut > 100_000:
            print(f"  {mb(boyut):7.1f} MB  {parca.name}")
    print(f"  {'-' * 24}\n  {mb(toplam):7.1f} MB  TOPLAM")
    if not secim.tam:
        print("\n  Not: yt-dlp ve ffmpeg YOK — kullanici Ayarlar > Motorlar'dan indirir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
