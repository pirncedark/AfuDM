"""Bilgisayar acilinca AfuDM'i de acan "Baslangic" kisayolu.

Kayit defteri Run anahtari DEGIL, Windows Baslangic (Startup) KLASORU
kullanilir — kullanici Gorev Yoneticisi > Baslangic sekmesinden kapatabilsin
ve bu geri alinabilir kalsin. Kisayol (.lnk) PowerShell uzerinden Windows
Script Host'un WScript.Shell COM nesnesiyle yazilir (pencere ACILMAZ, ek
kutuphane GEREKMEZ); .lnk ikili bicimini Python'da elle uretmek kirilgan ve
hataya acik oldugu icin bu yol secildi.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

from core import paths

CREATE_NO_WINDOW = 0x08000000
_KISAYOL_ADI = "AfuDM.lnk"
_ACIKLAMA = "AfuDM — indirme yoneticisi"

# ASCII-safe: dinamik (Turkce/em-dash icerebilen) degerler PARAMETRE olarak
# gecilir, script dosyasinin kendisi hep ASCII kalir (PowerShell 5.1 BOM'suz
# dosyada Turkce karakterleri bozar; komut satiri parametreleri bu sorunu
# yasamaz, cunku CreateProcess Unicode tasir).
_BETIK = r"""
param(
    [string]$KisayolYolu,
    [string]$Hedef,
    [string]$Argumanlar,
    [string]$CalismaKlasoru,
    [string]$Aciklama,
    [string]$Simge
)
$ErrorActionPreference = "Stop"
$kabuk = New-Object -ComObject WScript.Shell
$kisayol = $kabuk.CreateShortcut($KisayolYolu)
$kisayol.TargetPath = $Hedef
if ($Argumanlar) { $kisayol.Arguments = $Argumanlar }
$kisayol.WorkingDirectory = $CalismaKlasoru
$kisayol.Description = $Aciklama
if ($Simge) { $kisayol.IconLocation = $Simge }
$kisayol.Save()
"""


def _startup_klasoru() -> Path:
    """Baslangic klasorunun GERCEK yolu (OneDrive'a tasinmis olabilir)."""
    anahtar = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, anahtar) as k:
            deger, _ = winreg.QueryValueEx(k, "Startup")
            yol = Path(os.path.expandvars(deger))
            if yol.is_dir():
                return yol
    except OSError:
        pass
    profil = os.environ.get("APPDATA")
    if profil:
        return Path(profil) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home()


# Degistirilebilir modul degiskeni: testler kendi gecici klasorlerini verir
# (core/cerez.py'deki KLASOR deseninin aynisi).
KLASOR = _startup_klasoru()


def kisayol_yolu() -> Path:
    """Baslangic kisayolunun (varsa/olacagi) tam dosya yolu."""
    return KLASOR / _KISAYOL_ADI


def hedef() -> tuple[str, str]:
    """Kisayolun hedefi: (calistirilabilir, argumanlar).

    paths.BASE altinda AfuDM.exe varsa dogrudan o; yoksa kaynaktan calisirken
    pythonw.exe + app.py (konsol penceresi acilmasin diye pythonw).
    """
    exe = paths.BASE / "AfuDM.exe"
    if exe.exists():
        return str(exe), ""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)  # yedek: sadece python.exe var
    return str(pythonw), f'"{paths.BASE / "app.py"}"'


def _simge() -> str:
    """Kisayol simgesi: exe kendi simgesini tasir, yoksa ui/afudm.ico."""
    exe = paths.BASE / "AfuDM.exe"
    if exe.exists():
        return str(exe)
    return str(paths.UI / "afudm.ico")


def acik_mi() -> bool:
    """Baslangic kisayolu su an var mi?"""
    return kisayol_yolu().is_file()


def ac() -> None:
    """Baslangic kisayolunu olustur. Zaten aciksa hicbir sey yapma."""
    if acik_mi():
        return

    hedef_exe, hedef_arg = hedef()
    if not Path(hedef_exe).exists():
        raise RuntimeError(f"baslangic hedefi bulunamadi: {hedef_exe}")

    try:
        KLASOR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"baslangic klasoru olusturulamadi: {exc}") from exc

    betik_dosyasi = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="ascii"
        ) as f:
            f.write(_BETIK)
            betik_dosyasi = Path(f.name)

        komut = [
            "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(betik_dosyasi),
            "-KisayolYolu", str(kisayol_yolu()),
            "-Hedef", hedef_exe,
            "-Argumanlar", hedef_arg,
            "-CalismaKlasoru", str(paths.BASE),
            "-Aciklama", _ACIKLAMA,
            "-Simge", _simge(),
        ]
        sonuc = subprocess.run(
            komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError(f"kisayol olusturma komutu calistirilamadi: {exc}") from exc
    finally:
        if betik_dosyasi is not None:
            betik_dosyasi.unlink(missing_ok=True)

    if sonuc.returncode != 0 or not acik_mi():
        hata = (sonuc.stderr or sonuc.stdout or "bilinmeyen hata").strip()
        raise OSError(f"kisayol olusturulamadi: {hata[:300]}")


def kapat() -> None:
    """Baslangic kisayolunu kaldir. Yoksa sessizce gec."""
    try:
        kisayol_yolu().unlink(missing_ok=True)
    except OSError as exc:
        raise OSError(f"kisayol silinemedi: {exc}") from exc
