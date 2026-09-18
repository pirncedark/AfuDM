# -*- coding: utf-8 -*-
"""Iliskilendirme (core/iliskilendir.py) — AG VE PENCERE GEREKTIRMEZ, saniyeler surer.

GERCEK kayit defterini KIRLETMEZ: KOK bir test anahtarina yonlendirilir
(Software\\AfuDM-iliskilendir-test\\Classes), test bitince o anahtar
KOKUNDEN sokulup tamamen silinir.

Dogruladiklari:
 1. ac() sonrasi anahtarlar var, komut satiri gercek bir exe/pythonw gosteriyor
 2. acik_mi() True, ikinci ac() patlamiyor (yedek bozulmuyor)
 3. kapat() sonrasi TEMIZ durumda (hicbir seyin oncesi yoksa) her sey silinir
 4. EN ONEMLISI: onceden BASKA bir ProgId / komut varsa (sahte qBittorrent
    kaydi), ac()+kapat() sonrasi o deger AYNEN geri geliyor
"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import iliskilendir  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


TEST_KOK = r"Software\AfuDM-iliskilendir-test\Classes"


def _oku_ham(alt_anahtar: str, deger_adi: str = "") -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{TEST_KOK}\\{alt_anahtar}") as k:
            deger, _ = winreg.QueryValueEx(k, deger_adi)
            return str(deger)
    except OSError:
        return None


def _yaz_ham(alt_anahtar: str, deger: str, deger_adi: str = "") -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{TEST_KOK}\\{alt_anahtar}") as k:
        winreg.SetValueEx(k, deger_adi, 0, winreg.REG_SZ, deger)


def _agac_sil(yol: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, yol, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    alt_ad = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _agac_sil(f"{yol}\\{alt_ad}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, yol)
    except FileNotFoundError:
        pass


# Gercek kayit defterine DOKUNMADAN test koku kullan.
iliskilendir.KOK = TEST_KOK
_agac_sil(TEST_KOK)  # onceki bir kosudan artik kalmis olabilir

try:
    print("1) hedef() gercek bir calistirilabiliyi gosteriyor")
    exe, komut = iliskilendir.hedef()
    check("hedef dosya var", Path(exe).exists(), exe)
    check("komut %1 iceriyor", '"%1"' in komut, komut)
    check("komut hedefi tirnak icinde tasiyor", f'"{exe}"' in komut, komut)

    print("2) temiz durumda ac()")
    iliskilendir.ac()
    check(".torrent bizim ProgId'e bagli", _oku_ham(".torrent") == iliskilendir.TORRENT_PROGID)
    check("OpenWithProgids listesinde AfuDM var",
          _oku_ham(".torrent\\OpenWithProgids", iliskilendir.TORRENT_PROGID) == "")
    check("torrent ProgId komutu dogru", _oku_ham(f"{iliskilendir.TORRENT_PROGID}\\shell\\open\\command") == komut)
    check("magnet komutu dogru", _oku_ham("magnet\\shell\\open\\command") == komut)
    check("magnet URL Protocol isaretli", _oku_ham("magnet", "URL Protocol") == "")
    check("temiz durumda oncesi yok isaretlendi (torrent)",
          _oku_ham(iliskilendir.TORRENT_PROGID, "AfuDM_OncekiVarMi") == "0")
    check("temiz durumda oncesi yok isaretlendi (magnet)",
          _oku_ham("magnet", "AfuDM_OncekiVarMi") == "0")

    print("3) acik_mi() ve ikinci ac() patlamiyor")
    check("acik_mi() True", iliskilendir.acik_mi() is True)
    try:
        iliskilendir.ac()
        ikinci_ac_patladi = False
    except Exception as exc:  # ikinci cagri asla patlamamali
        ikinci_ac_patladi = True
        print(f"    istisna: {exc}")
    check("ikinci ac() patlamiyor", not ikinci_ac_patladi)
    check("ikinci ac() sonrasi da acik_mi() True", iliskilendir.acik_mi() is True)
    check("yedek bayragi ikinci ac()'ta BOZULMADI (hala '0')",
          _oku_ham(iliskilendir.TORRENT_PROGID, "AfuDM_OncekiVarMi") == "0")

    print("4) kapat() temiz durumda her seyi siler")
    iliskilendir.kapat()
    check(".torrent varsayilani silindi", _oku_ham(".torrent") is None)
    check("torrent ProgId anahtari tamamen silindi", _oku_ham(iliskilendir.TORRENT_PROGID) is None)
    check("magnet anahtari tamamen silindi", _oku_ham("magnet") is None)
    check("acik_mi() artik False", iliskilendir.acik_mi() is False)

    print("5) EN ONEMLI: onceden BASKA kayit varsa aynen geri geliyor")
    _agac_sil(TEST_KOK)  # bastan temiz baslangic
    _yaz_ham(".torrent", "qBittorrent.torrent")
    _yaz_ham("magnet", "URL:BitTorrent Magnet Protokolu")
    _yaz_ham("magnet", "", "URL Protocol")
    _yaz_ham("magnet\\shell\\open\\command", r'"C:\Program Files\qBittorrent\qbittorrent.exe" "%1"')

    iliskilendir.ac()
    check(".torrent gecici olarak bize dondu",
          _oku_ham(".torrent") == iliskilendir.TORRENT_PROGID)
    check("eski torrent ProgId'i yedeklendi",
          _oku_ham(iliskilendir.TORRENT_PROGID, "AfuDM_OncekiProgId") == "qBittorrent.torrent")
    check("magnet gecici olarak bize dondu",
          _oku_ham("magnet\\shell\\open\\command") == komut)
    check("eski magnet komutu yedeklendi",
          _oku_ham("magnet", "AfuDM_OncekiKomut") == r'"C:\Program Files\qBittorrent\qbittorrent.exe" "%1"')

    iliskilendir.kapat()
    check("kapat() sonrasi .torrent AYNEN qBittorrent'e geri dondu",
          _oku_ham(".torrent") == "qBittorrent.torrent", _oku_ham(".torrent"))
    check("kapat() sonrasi magnet komutu AYNEN geri dondu",
          _oku_ham("magnet\\shell\\open\\command") == r'"C:\Program Files\qBittorrent\qbittorrent.exe" "%1"',
          _oku_ham("magnet\\shell\\open\\command"))
    check("kapat() sonrasi magnet aciklamasi AYNEN geri dondu",
          _oku_ham("magnet") == "URL:BitTorrent Magnet Protokolu", _oku_ham("magnet"))
    check("bizim torrent ProgId anahtarimiz kalmadi", _oku_ham(iliskilendir.TORRENT_PROGID) is None)
    check("bizim yedek degerlerimiz magnet'te kalmadi",
          _oku_ham("magnet", "AfuDM_OncekiKomut") is None and _oku_ham("magnet", "AfuDM_OncekiVarMi") is None)

    print("6) durum() sozlugu bekledigimiz bicimde")
    d = iliskilendir.durum()
    check("durum() iki anahtar iceriyor", set(d) == {"torrent", "magnet"}, str(d))
    check("her biri kayitli/varsayilan iceriyor",
          all({"kayitli", "varsayilan"} <= set(v) for v in d.values()), str(d))
    check("kapat() sonrasi torrent artik kayitli degil", d["torrent"]["kayitli"] is False)
    check("kapat() sonrasi magnet artik kayitli degil (qBittorrent bizim komutumuz DEGIL)",
          d["magnet"]["kayitli"] is False)
    check("varsayilan_mi() bool doner (torrent)", isinstance(iliskilendir.varsayilan_mi("torrent"), bool))
    check("varsayilan_mi() bool doner (magnet)", isinstance(iliskilendir.varsayilan_mi("magnet"), bool))
    try:
        iliskilendir.varsayilan_mi("bilinmeyen")
        check("bilinmeyen tur ValueError firlatir", False)
    except ValueError:
        check("bilinmeyen tur ValueError firlatir", True)

finally:
    _agac_sil(TEST_KOK)
    _agac_sil(r"Software\AfuDM-iliskilendir-test")

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
