"""Guncel tracker listesini gunluk indirip aria2'ye uygular.

Olu torrentlerde seed bulma sansini ciddi artirir: ngosang/trackerslist
listesi her gun guncellenir, biz 24 saatte bir cekip bt-tracker'a yaziyoruz.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request

from . import paths

SOURCES = [
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt",
    "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_best.txt",
]
MAX_AGE = 24 * 3600  # 24 saat


def _fetch() -> list[str]:
    last_error: Exception | None = None
    for url in SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AfuDM/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", "replace")
            trackers = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if trackers:
                return trackers
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def cached() -> list[str]:
    if not paths.TRACKERS_CACHE.exists():
        return []
    text = paths.TRACKERS_CACHE.read_text(encoding="utf-8", errors="replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def is_fresh() -> bool:
    if not paths.TRACKERS_CACHE.exists():
        return False
    return (time.time() - paths.TRACKERS_CACHE.stat().st_mtime) < MAX_AGE



def cache_yasi() -> float | None:
    """Onbellek kac saniye once yazildi? Dosya yoksa None (hic indirilmemis)."""
    if not paths.TRACKERS_CACHE.exists():
        return None
    return time.time() - paths.TRACKERS_CACHE.stat().st_mtime

def refresh(force: bool = False) -> list[str]:
    """Gerekiyorsa indir, onbellege yaz ve listeyi don. Cevrimdisiysa onbellegi kullan."""
    paths.ensure_dirs()
    if not force and is_fresh():
        return cached()
    try:
        trackers = _fetch()
    except Exception:
        return cached()  # internet yoksa eldekiyle devam
    if trackers:
        paths.TRACKERS_CACHE.write_text("\n".join(trackers), encoding="utf-8")
    return trackers


def ayikla(metin: str) -> list[str]:
    """Kullanicinin yapistirdigi metinden tracker adreslerini cikar.

    Satir, virgul ya da bosluk ile ayrilmis olabilir; yalniz gercek tracker
    semalari kabul edilir (yanlis yapistirmalar sessizce dusurulur).
    """
    parcalar: list[str] = []
    for satir in (metin or "").replace(",", "\n").split("\n"):
        for parca in satir.split():
            aday = parca.strip()
            if aday.lower().startswith(("udp://", "http://", "https://", "ws://", "wss://")):
                if aday not in parcalar:
                    parcalar.append(aday)
    return parcalar


def apply_to_aria2(rpc, force: bool = False, ek: str = "") -> int:
    """Guncel listeyi + KULLANICININ ekledigi tracker'lari aria2'ye yazar.

    Donen deger: uygulanan toplam tracker sayisi. Kullanicinin eklediklerini
    BASA koyar: aria2 listeyi sirayla duyurur, elle eklenen once denensin.
    """
    kendi = ayikla(ek)
    liste = refresh(force=force)
    tumu = kendi + [t for t in liste if t not in kendi]
    if not tumu:
        return 0
    rpc.change_global_option({"bt-tracker": ",".join(tumu)})
    return len(tumu)
