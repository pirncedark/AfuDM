"""Uygulama surumu — TEK KAYNAK.

Buraya kadar surum yalnizca yayin notlarinda (docs/DURUM.md) ve uzantinin
manifest.json'unda duruyordu; calisan uygulamada HICBIR yerde gorunmuyordu,
yani "hangi kopyayi kullaniyorum" sorusunun cevabi yoktu. Artik arayuz
(sol serit + Ayarlar) bunu gosterir.

Uzanti surumu AYRIDIR ve manifest.json'dan OKUNUR: ikisi ayri yayinlanabilir,
elle kopyalamak ikisini sessizce uyumsuz birakirdi.
"""
from __future__ import annotations

import json

from . import paths

SURUM = "2.1.0"


def uzanti_surumu() -> str:
    """extension/manifest.json icindeki surum; okunamazsa bos."""
    try:
        veri = json.loads((paths.BASE / "extension" / "manifest.json")
                          .read_text(encoding="utf-8"))
        return str(veri.get("version") or "")
    except (OSError, ValueError):
        return ""
