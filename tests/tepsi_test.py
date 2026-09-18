# -*- coding: utf-8 -*-
"""qBittorrent tipi pencere davranisi: kucult gorev cubugu, X tepsi."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import Api  # noqa: E402

fails = []


def check(ad, kosul):
    print("  [%s] %s" % ("GECTI" if kosul else "DUSTU", ad))
    if not kosul:
        fails.append(ad)


class Pencere:
    def __init__(self):
        self.gizlendi = 0
        self.kuculdu = 0
        self.kapandi = 0

    def hide(self):
        self.gizlendi += 1

    def minimize(self):
        self.kuculdu += 1

    def destroy(self):
        self.kapandi += 1


class Store:
    def __init__(self, tepsi=True):
        self.tepsi = tepsi

    def get(self, key, default=None):
        return self.tepsi if key == "tepsiye_kucult" else default


class Manager:
    def __init__(self, tepsi=True):
        self.store = Store(tepsi)


def api_yap(tepsi=True, simge=True):
    api = Api.__new__(Api)
    api.manager = Manager(tepsi)
    api._window = Pencere()
    api._tepsi = object() if simge else None
    api._cikiliyor = False
    api._tepsi_bildirimi = lambda: None
    return api


print("1) Kucult dugmesi Windows gorev cubuguna gider")
api = api_yap()
Api.pencere_kucult(api)
check("minimize cagrildi", api._window.kuculdu == 1)
check("kucultmede gizlenmedi", api._window.gizlendi == 0)

print("2) X dugmesi qBittorrent gibi tepsiye gider")
api = api_yap()
out = Api.pencere_kapat(api)
check("pencere gizlendi", api._window.gizlendi == 1)
check("uygulama kapatilmadi", api._window.kapandi == 0)
check("sonuc tepsiye gittigini bildiriyor", out.get("tepside") is True)

print("3) Tepsi simgesi yoksa pencere erisilemez kalmaz")
api = api_yap(simge=False)
out = Api.pencere_kapat(api)
check("simge yoksa gercek kapatma", api._window.kapandi == 1)
check("tepside sonucu false", out.get("tepside") is False)

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    raise SystemExit(1)
print("Hepsi gecti")
