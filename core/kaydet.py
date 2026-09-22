"""Kaydetme penceresi arka ucu — IDM'in "indirme bilgisi" penceresi gibi.

Link nereden gelirse gelsin (elle, pano, tarayici uzantisi) kullanici indirmeden
once: dosya adini, KLASOR AGACINDAN konumu, kategoriyi ve ne zaman baslayacagini
secer.

- Kategori: dosya uzantisindan/turden tahmin; secilen kategori ana indirme
  klasorunun altinda kendi klasorune gider (downloads/Video, downloads/Muzik...).
- Klasor agaci: kisayollar (AfuDM, Masaustu, Indirilenler, Belgeler, Videolar,
  Muzik) + diskler; alt klasorler istendikce okunur (tum disk taranmaz).
- Bekleyenler: uzantidan gelen indirme hemen baslamaz; cerezler/basliklar dahil
  TUM istek bellekte tutulur, pencere onaylayinca aynen yonetici'ye verilir.
  (Cerezler burada da yalniz bellekte; bkz. core/cerez.py.)
"""
from __future__ import annotations

import ctypes
import itertools
import os
import string
import threading
import time
import urllib.parse
import winreg
from pathlib import Path
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
    SURE = 30 * 60  # yarim saatte onaylanmayan istek (ve cerezleri) atilir

    def __init__(self) -> None:
        self._kilit = threading.Lock()
        self._sayac = itertools.count(1)
        self._isler: dict[int, dict] = {}

    def ekle(self, istek: dict) -> int:
        with self._kilit:
            self._temizle()
            kimlik = next(self._sayac)
            self._isler[kimlik] = {"istek": dict(istek), "zaman": time.time()}
            return kimlik

    def al(self, kimlik: int) -> dict | None:
        with self._kilit:
            kayit = self._isler.pop(int(kimlik), None)
            return kayit["istek"] if kayit else None

    def ozet(self) -> list[dict]:
        """Arayuze giden liste: cerez/baslik YOK, yalniz gosterilecekler."""
        with self._kilit:
            self._temizle()
            return [{"id": k, "url": v["istek"].get("url", ""), "title": v["istek"].get("title") or "",
                     "filename": v["istek"].get("filename") or "", "kind": v["istek"].get("kind") or "",
                     "quality": v["istek"].get("quality") or ""}
                    for k, v in sorted(self._isler.items())]

    def _temizle(self) -> None:
        esik = time.time() - self.SURE
        for kimlik in [k for k, v in self._isler.items() if v["zaman"] < esik]:
            del self._isler[kimlik]
