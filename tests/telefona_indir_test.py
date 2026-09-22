# -*- coding: utf-8 -*-
"""v2.4 "Telefona indir" — /dosya ucu ve guvenlik kisiti.

Kritik nokta: uc istemciden YOL ALMAZ, yalniz gid alir. Yolu sunucu bulur ve
indirme kokunun ICINDE oldugunu dogrular. Bu testler o kurali kanitlar.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GECTI = 0
DUSTU = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global GECTI, DUSTU
    if kosul:
        GECTI += 1
        print(f"  [GECTI] {ad}" + (f" — {detay}" if detay else ""))
    else:
        DUSTU += 1
        print(f"  [DUSTU] {ad}" + (f" — {detay}" if detay else ""))


class SahteRpc:
    def __init__(self, yol: str) -> None:
        self.yol = yol

    def tell_status(self, gid: str) -> dict:
        return {"files": [{"path": self.yol}]} if self.yol else {}


class SahteStore:
    def by_gid(self, gid: str):
        return None


class SahteManager:
    def __init__(self, kok: str, yol: str) -> None:
        self.rpc = SahteRpc(yol)
        self.store = SahteStore()
        self._kok = kok

    def current_download_dir(self) -> str:
        return self._kok


def _uc(kok: str, yol: str):
    """_telefona_dosya'yi Handler ornegi olusturmadan cagirir."""
    from api.server import _Handler
    sahte = SahteManager(kok, yol)
    return _Handler._telefona_dosya.__get__(
        type("K", (), {"manager": sahte})(), object)


def main() -> None:
    kok = Path(tempfile.mkdtemp()) / "indirilenler"
    (kok / "alt").mkdir(parents=True)
    icerideki = kok / "alt" / "film.mkv"
    icerideki.write_bytes(b"x" * 1024)

    disarisi = kok.parent / "gizli.txt"
    disarisi.write_bytes(b"sir")

    print("1) Kok ICINDEKI dosya servis edilir")
    bul = _uc(str(kok), str(icerideki))
    try:
        sonuc = bul("gid1")
        check("kok icindeki dosya bulundu", sonuc == icerideki.resolve(), str(sonuc))
    except Exception as exc:
        check("kok icindeki dosya bulundu", False, repr(exc))

    print("2) Kok DISINDAKI dosya REDDEDILIR")
    bul = _uc(str(kok), str(disarisi))
    try:
        bul("gid2")
        check("kok disindaki dosya reddedildi", False, "reddetmedi!")
    except PermissionError:
        check("kok disindaki dosya reddedildi", True)
    except Exception as exc:
        check("kok disindaki dosya reddedildi", False, repr(exc))

    print("3) '..' ile cikis REDDEDILIR")
    bul = _uc(str(kok), str(kok / "alt" / ".." / ".." / "gizli.txt"))
    try:
        bul("gid3")
        check("'..' ile cikis reddedildi", False, "reddetmedi!")
    except PermissionError:
        check("'..' ile cikis reddedildi", True)
    except Exception as exc:
        check("'..' ile cikis reddedildi", False, repr(exc))

    print("4) Benzer isimli KARDES klasor REDDEDILIR")
    kardes = kok.parent / "indirilenler-baska"
    kardes.mkdir(exist_ok=True)
    yakin = kardes / "a.bin"
    yakin.write_bytes(b"y")
    bul = _uc(str(kok), str(yakin))
    try:
        bul("gid4")
        check("kardes klasor reddedildi", False, "reddetmedi!")
    except PermissionError:
        check("kardes klasor reddedildi", True)
    except Exception as exc:
        check("kardes klasor reddedildi", False, repr(exc))

    print("5) Dosya YOKSA FileNotFoundError")
    bul = _uc(str(kok), str(kok / "yok.bin"))
    try:
        bul("gid5")
        check("olmayan dosya hata verdi", False, "hata vermedi!")
    except FileNotFoundError:
        check("olmayan dosya hata verdi", True)
    except Exception as exc:
        check("olmayan dosya hata verdi", False, repr(exc))

    print("6) Mobil arayuz kablolamasi")
    mobil = (Path(__file__).resolve().parents[1] / "ui" / "mobil.html").read_text(encoding="utf-8")
    check("klasor seciciye telefon secenegi eklendi", '"__telefon"' in mobil)
    check("biten satirda telefona indir dugmesi var", 'data-eylem="telefon"' in mobil)
    check("/dosya ucu cagriliyor", "/dosya?gid=" in mobil)
    check("__telefon kategori olarak GONDERILMIYOR",
          'klasorSecim !== "__telefon"' in mobil)

    print(f"\nSONUC: {GECTI} gecti, {DUSTU} dustu")
    sys.exit(1 if DUSTU else 0)


if __name__ == "__main__":
    main()