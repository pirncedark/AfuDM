# -*- coding: utf-8 -*-
"""Tracker normalize hatti: ham havuz -> temiz, tekil, varsayilana uygun liste.

Kullanici karari (2026): '300 tracker = hizli DEMEK DEGIL'. Deger en buyuk
liste degil, normalizasyon + saglik taramasindan gecmis dinamik havuzdur.
Bu test ham metindeki KAYNAK SIRASINI bozmadan su her seyi dogrular:
  - yapismis iki URL'yi bolme
  - satir basindaki *, bosluk, tirnak temizligi
  - yalniz udp/http/https kabulu (ws/wss, 'dp://' yazim hatasi dusurulur)
  - buyuk/kucuk harf duyarsiz tekil kilma
  - yerel ag (retracker.local, ozel IP) ve domain-policy cikarimi
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from core import trackers  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool) -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad)


def normalize(*satirlar: str) -> list[str]:
    return trackers.tracker_normalize("\n".join(satirlar))


# --- 1. yapismis iki URL bolunur -----------------------------------------
_cikan = normalize(
    "udp://ttk2.nbaonlineservice.com:6969/announceudp://tracker.opentrackr.org:1337/announce",
)
check("yapismis bolme", _cikan == [
    "udp://ttk2.nbaonlineservice.com:6969/announce",
    "udp://tracker.opentrackr.org:1337/announce",
])

# --- 2. '*' ve bosluk/tirnak temizligi ------------------------------------
_temiz = normalize(" *https://tracker.ghostchu-services.top:443/announce ")
check("* silindi", _temiz == ["https://tracker.ghostchu-services.top:443/announce"])

# --- 3. gecersiz sema dusurulur --------------------------------------------
_sema = normalize(
    "dp://tracker.theoks.net:6969/announce",       # yazim hatasi (udp olacakti)
    "ws://tracker.example.com:80/announce",        # WebTorrent, aria2 kullanamaz
    "wss://tracker.example.com:443/announce",
    "ftp://tracker.example.com:21/announce",       # ftp torrent tracker degil
    "udp://tracker.opentrackr.org:1337/announce",
)
check("gecersiz semalar dusuruldu", _sema == ["udp://tracker.opentrackr.org:1337/announce"])

# --- 4. tekil kilma (harf duyarsiz) -----------------------------------------
_tekil = normalize(
    "udp://open.demonii.com:1337/announce",
    "UDP://OPEN.DEMONII.COM:1337/announce",        # buyuk harf ayni kayit
    "udp://tracker.qu.ax:6969/announce",
    "udp://tracker.qu.ax:6969/announce ",
)
check("harf duyarsiz tekil", _tekil == [
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.qu.ax:6969/announce",
])

# --- 5. yerel ag / domain-policy cikarimi ------------------------------------
_yerel = normalize(
    "http://retracker.local/announce",             # yalniz yerel ag
    "udp://192.168.1.50:6969/announce",            # ozel IP
    "udp://10.0.0.5:6969/announce",
    "http://127.0.0.1:8080/announce",              # loopback
    "udp://tracker1.myporn.club:9337/announce",    # domain-policy
    "udp://tracker.opentrackr.org:1337/announce",
)
check("yerel+yasak cikarildi", _yerel == ["udp://tracker.opentrackr.org:1337/announce"])

# --- 6. kaynak sirasi korunur -------------------------------------------------
_sira = normalize(
    "udp://explodie.org:6969/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
)
check("sira korundu", _sira == [
    "udp://explodie.org:6969/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
])

# --- 7. bos / None guvenli ------------------------------------------------------
check("None guvenli", trackers.tracker_normalize(None) == [])
check("bos guvenli", trackers.tracker_normalize("") == [])

# --- 8. ayikla aynı normalize hattini kullanir (saglik taramasi/paste yolu) ------
_ayikla = trackers.ayikla(
    "udp://tracker.opentrackr.org:1337/announce, *udp://open.demonii.com:1337/announce"
)
check("ayikla ayni hat", _ayikla == [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
])

print("\ntrackerlar: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: tracker normalize hatti tutarli")