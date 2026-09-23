"""Istege bagli motorlari indirir — "cekirdek paket" bunun icin var.

Gonderilen klasor kucuk olsun diye yalniz ZORUNLU motor (aria2c) yanina konur;
video isleri icin gerekenler kullanici isteyince indirilir ve `engine/` icine
girer. Portable kurali bozulmaz: hicbir sey sisteme yazilmaz.

Neden boyle:
  aria2c   5.4 MB  ZORUNLU  — indirme motoru, onsuz uygulama calismaz
  yt-dlp    17 MB  istege bagli — video sitelerini cozer
  ffmpeg    97 MB  istege bagli — ses+video birlestirme ve mp3

YouTube 2026'da ses ile goruntuyu AYRI gonderiyor (birlesik format birakmadi),
bu yuzden ffmpeg olmadan YouTube videosu sesli inmez. Kullaniciya bunu indirme
aninda soylemek icin `EKSIK_NE_YAPAMAZ` metinleri burada duruyor.
"""
from __future__ import annotations

import os
import hashlib
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import paths

CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class Motor:
    ad: str
    dosya: str                  # engine/ icindeki hedef dosya adi
    adres: str                  # indirme adresi
    zip_icinde: str | None      # zip ise: icinden alinacak uyenin adi (sonu ile eslesir)
    indirme_boyutu_mb: int      # kullaniciya gosterilecek kaba boyut
    zorunlu: bool
    ne_icin: str
    sha256: str | None = None


MOTORLAR: dict[str, Motor] = {
    "aria2c": Motor(
        ad="aria2c",
        dosya="aria2c.exe",
        adres="https://github.com/aria2/aria2/releases/download/release-1.37.0/"
              "aria2-1.37.0-win-64bit-build1.zip",
        zip_icinde="aria2c.exe",
        indirme_boyutu_mb=3,
        zorunlu=True,
        ne_icin="indirme motoru",
    ),
    "yt-dlp": Motor(
        ad="yt-dlp",
        dosya="yt-dlp.exe",
        adres="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
        zip_icinde=None,
        indirme_boyutu_mb=17,
        zorunlu=False,
        ne_icin="video sitelerinden indirme (YouTube, Instagram, TikTok...)",
    ),
    "ffmpeg": Motor(
        ad="ffmpeg",
        dosya="ffmpeg.exe",
        adres="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
              "ffmpeg-n8.1-latest-win64-lgpl-8.1.zip",
        zip_icinde="bin/ffmpeg.exe",
        indirme_boyutu_mb=164,
        zorunlu=False,
        ne_icin="ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme",
    ),
    "cloudflared": Motor(
        ad="cloudflared",
        dosya="cloudflared.exe",
        adres="https://github.com/cloudflare/cloudflared/releases/download/2026.9.1/"
              "cloudflared-windows-amd64.exe",
        zip_icinde=None,
        indirme_boyutu_mb=21,
        zorunlu=False,
        ne_icin="farkli aglardan guvenli dosya paylasimi",
        sha256="2837888cc0f5d58f15b6dc478376de90b4d3ba5241c7947455d1e0a0df429712",
    ),
}

EKSIK_NE_YAPAMAZ = {
    "yt-dlp": "video sitelerinden indirme",
    "ffmpeg": "1080p ve ustu video (ses ayri geliyor) ve mp3'e cevirme",
}


def _hedef(motor: Motor) -> Path:
    return paths.ENGINE / motor.dosya


def var_mi(ad: str) -> bool:
    """Motor PAKETIN ICINDE mi? (sistemdeki kurulum burada sayilmaz)"""
    motor = MOTORLAR.get(ad)
    return bool(motor) and _hedef(motor).exists()


def sistemde(ad: str) -> str:
    """Motor sistemde (PATH'te) kurulu mu? Kuruluysa yolunu dondurur.

    `core/paths.py` paket icinde bulamazsa sistemdekine DUSER. Kullaniciya
    "kurulu degil" deyip arkadan sistemdekini calistirmak yaniltici olur —
    ustelik portable vaadi de bozulur: uygulama makineden makineye farkli
    surumle calisir. O yuzden kaynak acikca bildirilir."""
    motor = MOTORLAR.get(ad)
    if motor is None or _hedef(motor).exists():
        return ""
    bulunan = shutil.which(Path(motor.dosya).stem)
    return bulunan or ""


def durum() -> dict[str, dict]:
    """Her motor icin: nereden geliyor, kac MB, ne ise yarar.

    kaynak: "paket"  -> engine/ icinde (istenen durum)
            "sistem" -> PATH'te bulundu, surumu bizim denetimimizde DEGIL
            "yok"    -> hicbir yerde yok
    """
    out: dict[str, dict] = {}
    for ad, motor in MOTORLAR.items():
        hedef = _hedef(motor)
        sistem_yolu = sistemde(ad)
        if hedef.exists():
            kaynak = "paket"
        elif sistem_yolu:
            kaynak = "sistem"
        else:
            kaynak = "yok"
        out[ad] = {
            "var": hedef.exists(),
            "kaynak": kaynak,
            "sistem_yolu": sistem_yolu,
            "kullanilabilir": kaynak != "yok",
            "boyut_mb": round(hedef.stat().st_size / 1048576, 1) if hedef.exists() else 0,
            "zorunlu": motor.zorunlu,
            "ne_icin": motor.ne_icin,
            "indirme_boyutu_mb": motor.indirme_boyutu_mb,
        }
    return out


def eksikler(sadece_istege_bagli: bool = True) -> list[str]:
    return [
        ad for ad, motor in MOTORLAR.items()
        if not _hedef(motor).exists() and (not sadece_istege_bagli or not motor.zorunlu)
    ]


def _dogrula(hedef: Path) -> bool:
    """Inen ikili gercekten calisiyor mu? (bozuk/yarim indirme yakalanir)

    Surum bayragi araclar arasinda ayni DEGIL: yt-dlp ve aria2c `--version`,
    ffmpeg `-version` ister. Yanlis bayrak calisan bir ikiliyi "bozuk" gosterir,
    o yuzden ikisi de denenir."""
    for bayrak in ("--version", "-version"):
        try:
            proc = subprocess.run(
                [str(hedef), bayrak], capture_output=True, timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if proc.returncode == 0 and proc.stdout.strip():
            return True
    return False


def indir(ad: str, ilerleme=None) -> dict:
    """Motoru indirir, gerekirse zip'ten cikarir, engine/ icine koyar.

    ilerleme(inen_bayt, toplam_bayt) geri cagrilir (toplam bilinmiyorsa 0).
    Dosya once gecici ada inip DOGRULANDIKTAN sonra yerine tasinir; yarim
    indirme calisan bir kurulumu bozmaz.
    """
    motor = MOTORLAR.get(ad)
    if motor is None:
        raise ValueError(f"bilinmeyen motor: {ad}")
    paths.ENGINE.mkdir(parents=True, exist_ok=True)
    hedef = _hedef(motor)

    gecici_dizin = Path(tempfile.mkdtemp(prefix="afudm_motor_"))
    try:
        inen = gecici_dizin / ("paket.zip" if motor.zip_icinde else motor.dosya)
        istek = urllib.request.Request(motor.adres, headers={"User-Agent": "AfuDM/1.0"})
        with urllib.request.urlopen(istek, timeout=60) as yanit, inen.open("wb") as f:
            toplam = int(yanit.headers.get("Content-Length") or 0)
            okunan = 0
            while True:
                parca = yanit.read(256 * 1024)
                if not parca:
                    break
                f.write(parca)
                okunan += len(parca)
                if ilerleme:
                    ilerleme(okunan, toplam)

        if motor.zip_icinde:
            with zipfile.ZipFile(inen) as z:
                uye = next(
                    (u for u in z.namelist()
                     if u.replace("\\", "/").endswith(motor.zip_icinde)), None)
                if uye is None:
                    raise RuntimeError(f"zip icinde {motor.zip_icinde} bulunamadi")
                cikan = gecici_dizin / motor.dosya
                with z.open(uye) as kaynak, cikan.open("wb") as f:
                    shutil.copyfileobj(kaynak, f)
            inen = cikan

        if motor.sha256:
            ozet = hashlib.sha256()
            with inen.open("rb") as f:
                for parca in iter(lambda: f.read(1024 * 1024), b""):
                    ozet.update(parca)
            if ozet.hexdigest().lower() != motor.sha256.lower():
                raise RuntimeError(f"{motor.dosya} SHA-256 dogrulamasi basarisiz")

        if not _dogrula(inen):
            raise RuntimeError(f"{motor.dosya} indi ama calismadi (bozuk indirme?)")

        yedek = hedef.with_suffix(hedef.suffix + ".eski")
        if hedef.exists():
            hedef.replace(yedek)
        shutil.move(str(inen), str(hedef))
        if yedek.exists():
            try:
                yedek.unlink()
            except OSError:
                pass
        return {"ad": ad, "dosya": str(hedef),
                "boyut_mb": round(hedef.stat().st_size / 1048576, 1)}
    finally:
        shutil.rmtree(gecici_dizin, ignore_errors=True)
