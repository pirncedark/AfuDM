# -*- coding: utf-8 -*-
"""Guc yonetimi testleri (core/guc.py) — AG GEREKTIRMEZ, makineyi UYUTMAZ.

Neden bu modul var: kullanici "PC kapaliyken indirsin" istedi. Kapatma
calismaz — acilista Windows sifresi istenir ve Baslangic'taki AfuDM oturum
acilana kadar baslamaz. Uykudan uyanista oturum zaten acik oldugu icin is
kaldigi yerden surer. Telefon tarayicisi UDP paketi GONDEREMEZ, bu yuzden
uyandirmayi telefondaki bir WoL uygulamasi yapar; AfuDM MAC'i ve kartin
durumunu gosterir.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import guc  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


print("1) Sihirli paket (Wake-on-LAN) bicimi")
for gecerli in ("30-9C-23-E0-FF-82", "309C23E0FF82", "30:9c:23:e0:ff:82"):
    try:
        # 255.255.255.255'e UDP: kimse dinlemiyorsa bile paket gider, kimse uyanmaz
        check(f"kabul: {gecerli}", guc.wol_gonder(gecerli) is True)
    except ValueError as exc:
        check(f"kabul: {gecerli}", False, str(exc))
for kotu in ("", "kisa", "zz-zz-zz-zz-zz-zz", "30-9C-23-E0-FF"):
    try:
        guc.wol_gonder(kotu)
        check(f"red: {kotu!r}", False, "kabul edildi")
    except ValueError:
        check(f"red: {kotu!r}", True)

print("2) Makinenin ag karti okunuyor")
kart = guc.aktif_kart()
check("kart adi geldi", bool(kart["ad"]), kart["ad"])
check("MAC 6 bloktan olusuyor", len(kart["mac"].replace(":", "-").split("-")) == 6, kart["mac"])
check("MAC buyuk harf (telefona elle girilecek)", kart["mac"] == kart["mac"].upper())

print("3) Durum ozeti (Ayarlar bunu gosterir)")
d = guc.durum()
for alan in ("kart", "mac", "wol", "hazir"):
    check(f"'{alan}' alani var", alan in d)
check("wol ucu deger: True/False/None (bilinmiyor AYRI)", d["wol"] in (True, False, None), str(d["wol"]))
check("hazir bool", isinstance(d["hazir"], bool), str(d["hazir"]))

print("4) Bilinmeyen kart adiyla cagri patlamiyor")
check("bos kart adi None doner", guc.wol_acik_mi("") is None)
check("olmayan kart None doner", guc.wol_acik_mi("YokBoyleBirKart") is None)

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
