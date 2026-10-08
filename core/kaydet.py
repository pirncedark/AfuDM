"""Kaydetme penceresi arka ucu — IDM'in "indirme bilgisi" penceresi gibi.

Link nereden gelirse gelsin (elle, pano, tarayici uzantisi) kullanici indirmeden
once: dosya adini, KLASOR AGACINDAN konumu, kategoriyi ve ne zaman baslayacagini
secer.

- Kategori: dosya uzantisindan/turden tahmin; secilen kategori ana indirme
  klasorunun altinda kendi klasorune gider (downloads/Video, downloads/Muzik...).
- Klasor agaci: kisayollar (AfuDM, Masaustu, Indirilenler, Belgeler, Videolar,
  Muzik) + diskler; alt klasorler istendikce okunur (tum disk taranmaz).
- Bekleyenler: uzantidan gelen indirme hemen baslamaz; cerezler/basliklar dahil
  Istek atomik dosyada, cerezler/basliklar yalniz bellekte tutulur.
  (Cerezler burada da yalniz bellekte; bkz. core/cerez.py.)
"""
from __future__ import annotations

import ctypes
import itertools
import json
import tempfile
import os
import string
import threading
import time
import urllib.parse
import winreg
from pathlib import Path
from core import paths
from . import dosya_adi as _dosya_mod
from .dosya_adi import guvenli_dosya_adi, resolve_filename, split_stem_ext


KATEGORILER: dict[str, tuple[str, ...]] = {
    "video": ("mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "ts", "mpg", "mpeg", "3gp", "m3u8"),
    "muzik": ("mp3", "m4a", "flac", "wav", "aac", "ogg", "opus", "wma"),
    "belge": ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "epub", "odt", "csv", "rtf"),
    "program": ("exe", "msi", "apk", "dmg", "deb", "rpm", "appx", "msix", "bat"),
    "arsiv": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso", "img", "cab"),
    "resim": ("jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "heic", "tiff"),
}
KATEGORI_KLASORU = {
    "telefon": "📱 Telefona İndir",
    "video": "Video", "muzik": "Müzik", "belge": "Belgeler", "program": "Programlar",
    "arsiv": "Arşiv", "resim": "Resimler", "torrent": "Torrent", "genel": "Genel",
}
def kategori_tahmin(url: str, tur: str = "", dosya_adi: str = "") -> str:
    if tur == "torrent" or url.lower().startswith("magnet:"):
        return "torrent"
    uzanti = ""
    if dosya_adi:
        _, ext = split_stem_ext(dosya_adi)
        if ext:
            uzanti = ext.lower()
    if not uzanti:
        yol = urllib.parse.urlparse(url).path.lower()
        parca = yol.rsplit("/", 1)[-1] if "/" in yol else yol
        _, ext = split_stem_ext(parca)
        if ext:
            uzanti = ext.lower()
        elif "." in parca:
            uzanti = parca.rsplit(".", 1)[-1]
    for kategori, uzantilar in KATEGORILER.items():
        if uzanti in uzantilar:
            return kategori
    if tur == "video":
        return "video"
    return "genel"


def kategori_klasoru(ana: str, kategori: str) -> str:
    return str(Path(ana) / KATEGORI_KLASORU.get(kategori, "Genel"))

# --- klasor agaci ------------------------------------------------------------
def _kabuk_klasoru(ad: str, yedek: str) -> Path:
    """Masaustu vb. OneDrive'a tasinmis olabilir: kayit defterindeki gercek yol."""
    anahtar = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, anahtar) as k:
            deger, _ = winreg.QueryValueEx(k, ad)
            yol = Path(os.path.expandvars(deger))
            if yol.is_dir():
                return yol
    except OSError:
        pass
    return Path.home() / yedek


def kisayollar(ana_indirme: str, ag: str = "") -> list[dict]:
    adaylar = [
        ("afudm", Path(ana_indirme)),
        ("masaustu", _kabuk_klasoru("Desktop", "Desktop")),
        ("indirilenler", _kabuk_klasoru("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads")),
        ("belgeler", _kabuk_klasoru("Personal", "Documents")),
        ("videolar", _kabuk_klasoru("My Video", "Videos")),
        ("muzik", _kabuk_klasoru("My Music", "Music")),
    ]
    sonuc, gorulen = [], set()
    for anahtar, yol in adaylar:
        try:
            if anahtar == "afudm":
                yol.mkdir(parents=True, exist_ok=True)
            if yol.is_dir() and str(yol).lower() not in gorulen:
                gorulen.add(str(yol).lower())
                sonuc.append({"anahtar": anahtar, "ad": yol.name, "yol": str(yol), "alt": _alt_var(yol)})
        except OSError:
            continue
    # Kullanicinin ag konumlari (modem/NAS): diskten ONCE, elinin altinda olsun
    for yol in ag_konumlari(ag):
        try:
            sonuc.append({"anahtar": "ag", "ad": yol.rstrip("\\").rsplit("\\", 1)[-1] or yol,
                          "yol": yol, "alt": _alt_var(Path(yol))})
        except OSError:
            continue
    for harf in string.ascii_uppercase:
        kok = f"{harf}:\\"
        # 2 = cikarilabilir, 3 = sabit, 4 = ag; CD-ROM (5) bos surucude takilir
        if ctypes.windll.kernel32.GetDriveTypeW(kok) in (2, 3, 4) and os.path.isdir(kok):
            sonuc.append({"anahtar": "disk", "ad": f"{harf}:", "yol": kok, "alt": True})
    return sonuc


def _alt_var(yol: Path) -> bool:
    try:
        with os.scandir(yol) as girdiler:
            return any(_gorunur_klasor(g) for g in itertools.islice(girdiler, 400))
    except OSError:
        return False


def _gorunur_klasor(girdi: os.DirEntry) -> bool:
    try:
        if not girdi.is_dir(follow_symlinks=False) or girdi.name.startswith(("$", ".")):
            return False
        oznitelik = girdi.stat(follow_symlinks=False).st_file_attributes
        return not oznitelik & 0x2 and not oznitelik & 0x4  # gizli / sistem
    except (OSError, AttributeError):
        return False


def alt_klasorler(yol: str, sinir: int = 500) -> list[dict]:
    sonuc = []
    try:
        with os.scandir(yol) as girdiler:
            for girdi in girdiler:
                if len(sonuc) >= sinir:
                    break
                if _gorunur_klasor(girdi):
                    sonuc.append({"ad": girdi.name, "yol": girdi.path, "alt": _alt_var(Path(girdi.path))})
    except OSError as exc:
        raise ValueError(f"klasor okunamadi: {exc.strerror or exc}") from exc
    return sorted(sonuc, key=lambda g: g["ad"].lower())


def klasor_olustur(ust: str, ad: str) -> str:
    ad = guvenli_dosya_adi(ad)
    if not ad:
        raise ValueError("klasor adi bos")
    hedef = Path(ust) / ad
    hedef.mkdir(parents=False, exist_ok=True)
    return str(hedef)


# --- ag konumlari (modem/NAS paylasimi) --------------------------------------
def ag_yolu_mu(yol: str) -> bool:
    """UNC mi (\\sunucu\paylasim) ya da eslenmis ag surucusu mu?"""
    return str(yol).startswith("\\\\")


def ag_konumlari(ayar: str) -> list[str]:
    """Ayarda saklanan ag konumlari; yalniz UNC olanlar, tekrarsiz."""
    sonuc: list[str] = []
    for satir in (ayar or "").splitlines():
        yol = satir.strip().rstrip("\\")
        if yol and ag_yolu_mu(yol) and yol not in sonuc:
            sonuc.append(yol)
    return sonuc


def ag_konumu_dogrula(yol: str) -> str:
    """Yolu temizle ve ERISILEBILDIGINI dogrula; olmazsa anlasilir hata ver.

    Paylasim kimlik dogrulamasi isterse Windows'un kendisi sorar; buradan
    sifre alinmaz. Kullaniciya "once Gezgin'den bir kez ac" demek dogrusu.
    """
    temiz = (yol or "").strip().rstrip("\\")
    if not temiz:
        raise ValueError("bos yol")
    if not ag_yolu_mu(temiz):
        raise ValueError("ag konumu \\\\sunucu\\paylasim biciminde olmali")
    try:
        varmi = Path(temiz).is_dir()
    except OSError as exc:
        raise ValueError(f"erisilemedi: {exc.strerror or exc}") from exc
    if not varmi:
        raise ValueError("erisilemedi — paylasimi once Gezgin'den bir kez ac")
    return temiz


# --- tarayicidan gelip onay bekleyen indirmeler -------------------------------
class Bekleyenler:
    SURE = 30 * 60  # yalniz gecici tarayici kimlik bilgilerinin omru

    def __init__(self) -> None:
        self._kilit = threading.Lock()
        self._isler: dict[int, dict] = {}
        self._dosya = paths.DATA / "pending_downloads.json"
        try:
            payload = json.loads(self._dosya.read_text(encoding="utf-8"))
            if payload.get("version") != 1:
                raise ValueError("Unsupported pending download format")
            for row in payload["items"]:
                ident = int(row["id"])
                if ident < 1 or ident in self._isler or not isinstance(row["istek"], dict):
                    raise ValueError("Invalid pending download")
                self._isler[ident] = {"istek": row["istek"], "zaman": float(row["zaman"])}
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, KeyError, AttributeError):
            self._isler = {}
            self._dosya.rename(self._dosya.with_name(self._dosya.name + f".corrupt-{time.time_ns()}"))
        self._sayac = itertools.count(max(self._isler, default=0) + 1)

    def _sakla(self, isler: dict) -> None:
        """Replace only after a complete, flushed write; secrets remain in RAM."""
        rows = []
        for ident, row in sorted(isler.items()):
            request = {k: v for k, v in row["istek"].items()
                       if k not in ("cookies", "headers", "user_agent")}
            rows.append({"id": ident, "istek": request, "zaman": row["zaman"]})
        self._dosya.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="pending-", suffix=".tmp", dir=self._dosya.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "items": rows}, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self._dosya)
        finally:
            Path(name).unlink(missing_ok=True)

    def bak(self, kimlik: int) -> dict | None:
        """Approval reads without removing the durable request prematurely."""
        with self._kilit:
            self._temizle()
            row = self._isler.get(int(kimlik))
            return dict(row["istek"]) if row else None

    def ekle(self, istek: dict) -> int:
        with self._kilit:
            self._temizle()
            request_id = istek.get("request_id")
            if request_id:
                if not isinstance(request_id, str) or len(request_id) > 128:
                    raise ValueError("Invalid download request identity")
                for ident, row in self._isler.items():
                    if row["istek"].get("request_id") == request_id:
                        if row["istek"].get("url") != istek.get("url"):
                            raise ValueError("Download request identity conflicts with URL")
                        return ident
            kimlik = next(self._sayac)
            yeni = {**self._isler, kimlik: {"istek": dict(istek), "zaman": time.time()}}
            self._sakla(yeni)
            self._isler = yeni
            return kimlik

    def al(self, kimlik: int) -> dict | None:
        with self._kilit:
            kimlik = int(kimlik)
            kayit = self._isler.get(kimlik)
            if kayit:
                yeni = {k: v for k, v in self._isler.items() if k != kimlik}
                self._sakla(yeni)
                self._isler = yeni
            return kayit["istek"] if kayit else None

    def geri_koy(self, kimlik: int, istek: dict) -> None:
        """Keep a failed approval available under its original UI identity."""
        with self._kilit:
            yeni = {**self._isler, int(kimlik): {"istek": dict(istek), "zaman": time.time()}}
            self._sakla(yeni)
            self._isler = yeni

    def ozet(self) -> list[dict]:
        """Arayuze giden liste: cerez/baslik YOK, yalniz gosterilecekler."""
        with self._kilit:
            self._temizle()
            return [{"id": k, "url": v["istek"].get("url", ""), "title": v["istek"].get("title") or "",
                     "filename": v["istek"].get("filename") or "", "kind": v["istek"].get("kind") or "",
                     "quality": v["istek"].get("quality") or "",
                     "audio_only": bool(v["istek"].get("audio_only")),
                     "source": v["istek"].get("source") or ""}
                    for k, v in sorted(self._isler.items())]

    def _temizle(self) -> None:
        esik = time.time() - self.SURE
        for row in self._isler.values():
            if row["zaman"] < esik:
                for key in ("cookies", "headers", "user_agent"):
                    row["istek"].pop(key, None)
