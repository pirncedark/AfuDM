# -*- coding: utf-8 -*-
"""Tek ornek yonetimi (masaustu + headless cakismasi) — v2.1.

SORUN: AfuDM portable. Ayni klasorden hem `python app.py` (masaustu) hem
`afuadm server start` (headless) calistirilirsa IKI surec ayni SQLite
dosyasina, ayni aria2 oturumuna ve ayni portlara asilir. Belirti kotudur:
indirmeler iki kez baslar, ayar yazimlari birbirini ezer, port rastgele
surece duser.

COZUM: `data/ornek.json` kilidi. Ilk surec kilidi alir ve icine kendi PID'ini,
kipini ve portlarini yazar. Ikinci surec kilidi GORUR ve iki secenekten birini
uygular:
  * `baglan`  -> mevcut ornege HTTP ile is verir, kendi surecini kapatir
  * `dur`     -> net bir mesajla durur (kip farkliysa; ornegin masaustu
                 acikken `server start` denenirse)

KILIT BAYAT OLABILIR (surec cokmusse). PID canli degilse kilit otomatik
devralinir; bu ISLEM IDEMPOTENTTIR ve veri silmez.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import paths

KILIT_DOSYA = "ornek.json"
KIP_MASAUSTU = "masaustu"
KIP_HEADLESS = "headless"


def _kilit_yolu() -> Path:
    return paths.DATA / KILIT_DOSYA


def surec_canli(pid: int) -> bool:
    """PID hala calisiyor mu? Windows'ta OpenProcess, digerinde os.kill(0).

    Yanlis pozitif mumkundur (PID geri donusumu); bu yuzden kilit sahipligi
    ayrica `/ping` ile de dogrulanabilir (bkz. `mevcut()`)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            kod = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(kod))
            ctypes.windll.kernel32.CloseHandle(handle)
            return kod.value == 259  # STILL_ACTIVE
        except Exception:
            return True  # emin degilsek "canli" say: veriyi riske atma
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def mevcut() -> dict | None:
    """Calisan bir AfuDM ornegi varsa bilgisi, yoksa None.

    Bayat kilit (surec olmus) None doner; cagiran kilidi devralabilir."""
    yol = _kilit_yolu()
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = int(veri.get("pid") or 0)
    if pid == os.getpid():
        return veri
    if not surec_canli(pid):
        return None
    return veri


def cakisma_raporu(istenen_kip: str) -> dict:
    """Ikinci ornek icin KARAR: ne yapmali?

    Doner: {"cakisma": bool, "karar": "baglan"|"dur"|"yok",
            "mevcut": {...}|None, "mesaj_anahtari": str}

    `mesaj_anahtari` UI/CLI'nin i18n tablosunda aradigi anahtardir; metni
    burada URETMEYIZ (dil katmani tek yerde).
    """
    var = mevcut()
    if var is None:
        return {"cakisma": False, "karar": "yok", "mevcut": None,
                "mesaj_anahtari": ""}
    mevcut_kip = str(var.get("kip") or KIP_MASAUSTU)
    # Ayni klasorde IKINCI bir surec asla acilmaz. Masaustu istegi acik
    # ornege devredilebilir (pencereyi one getir); headless istegi devredilemez
    # cunku zaten calisan bir servis vardir.
    if istenen_kip == KIP_MASAUSTU and mevcut_kip == KIP_MASAUSTU:
        karar, anahtar = "baglan", "ornek.zatenAcik"
    elif istenen_kip == KIP_MASAUSTU and mevcut_kip == KIP_HEADLESS:
        karar, anahtar = "baglan", "ornek.headlessCalisiyor"
    elif istenen_kip == KIP_HEADLESS and mevcut_kip == KIP_MASAUSTU:
        karar, anahtar = "dur", "ornek.masaustuAcik"
    else:
        karar, anahtar = "dur", "ornek.sunucuZatenAcik"
    return {"cakisma": True, "karar": karar, "mevcut": var,
            "mesaj_anahtari": anahtar}


class OrnekKilidi:
    """Kilidi alan/birakan baglam. `al()` False donerse SUREC ACILMAMALIDIR."""

    def __init__(self, kip: str) -> None:
        paths.ensure_dirs()
        self.kip = kip
        self.yol = _kilit_yolu()
        self.sahip = False
        self.veri: dict = {}

    def al(self) -> tuple[bool, dict]:
        """(alindi, cakisma_raporu). Bayat kilidi devralir (idempotent)."""
        rapor = cakisma_raporu(self.kip)
        if rapor["cakisma"]:
            return False, rapor
        self.veri = {
            "pid": os.getpid(),
            "kip": self.kip,
            "baslangic": time.time(),
            "api_port": 0,
            "sunucu_port": 0,
            "sunucu_adres": "",
            "klasor": str(paths.BASE),
        }
        self._yaz()
        self.sahip = True
        return True, rapor

    def guncelle(self, **alanlar) -> None:
        """Kilit dosyasindaki bilgileri tazele (port acildiginda vb.).

        ASLA anahtar/token yazilmaz: bu dosya yalnizca kimin calistigini
        anlatir, hicbir sir tasimaz."""
        if not self.sahip:
            return
        yasak = {"token", "anahtar", "gizli", "secret", "key", "cookie", "parola"}
        for ad, deger in alanlar.items():
            if ad.lower() in yasak:
                continue
            self.veri[ad] = deger
        self._yaz()

    def _yaz(self) -> None:
        gecici = self.yol.with_suffix(".tmp")
        try:
            gecici.write_text(json.dumps(self.veri, indent=1), encoding="utf-8")
            os.replace(gecici, self.yol)  # atomik: yarim dosya okunmaz
        except OSError:
            pass

    def birak(self) -> None:
        """Kilidi birak. Baskasinin kilidini ASLA silmez (PID kontrolu)."""
        if not self.sahip:
            return
        self.sahip = False
        try:
            veri = json.loads(self.yol.read_text(encoding="utf-8"))
            if int(veri.get("pid") or 0) == os.getpid():
                self.yol.unlink()
        except (OSError, ValueError):
            pass

    def __enter__(self) -> "OrnekKilidi":
        return self

    def __exit__(self, *_exc) -> None:
        self.birak()
