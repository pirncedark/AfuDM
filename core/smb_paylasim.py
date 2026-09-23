"""Agda Paylas'in actigi SMB paylasimlarinin yasam dongusu.

`net share AfuDM_x=... /GRANT:Everyone,READ` agdaki HERKESE okuma verir.
Silme ve cikista Api._paylasim_kaynaklarini_temizle kapatir; bu modul
cokme/zorla kapatma sonrasi ACILISTA kalan AfuDM_ paylasimlarini kapatir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ONEK = "AfuDM_"
KOK = Path(tempfile.gettempdir()) / "AfuDM-network-shares"
_PENCERESIZ = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _net(*args: str) -> subprocess.CompletedProcess | None:
    if os.name != "nt":
        return None
    try:
        # net.exe konsol (OEM, TR'de cp857) kod sayfasiyla yazar; varsayilan
        # cp1254 ile okumak "ı" gibi baytlarda UnicodeDecodeError verir.
        return subprocess.run(["net", *args], capture_output=True, text=True,
                              encoding="oem", errors="replace",
                              timeout=15, creationflags=_PENCERESIZ)
    except (OSError, subprocess.SubprocessError):
        return None


def acik_paylasimlar() -> list[str]:
    sonuc = _net("share")
    if not sonuc or sonuc.returncode != 0:
        return []
    adlar = []
    for satir in sonuc.stdout.splitlines():
        ilk = satir.split(maxsplit=1)[0] if satir.strip() else ""
        if ilk.startswith(ONEK):
            adlar.append(ilk)
    return adlar


def artiklari_temizle() -> int:
    """Onceki oturumdan kalan AfuDM_ paylasimlarini ve kopyalari kaldirir."""
    adlar = acik_paylasimlar()
    for ad in adlar:
        _net("share", ad, "/delete", "/y")
    shutil.rmtree(KOK, ignore_errors=True)
    return len(adlar)
