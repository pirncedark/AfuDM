"""Dosya adi, uzanti ve Content-Disposition cozumleme motoru — RFC 6266 / RFC 5987.

dlman v1.12.0'in cozumledigi gibi:
1. Sunucunun Content-Disposition basligi (filename= veya UTF-8 filename*=)
2. URL'deki yol ve yuzde kodlamasi (My%20File.zip -> My File.zip)
3. MIME turunden (Content-Type) uzanti tamamlama (application/zip -> .zip)
4. Akilli kok/uzanti ayrimi: app-v1.12.0 veya archive.001 gibi surumler
   uzanti sayilmaz, mukerrer adlandirmada bozulmaz.
5. Windows aygit adi korumasi (CON, PRN, AUX, NUL, COM1-9, LPT1-9 -> _CON vb.)
6. Dizin atlama (../../etc/passwd -> passwd), yasak karakterler (<>:"/\\|?*)
   ve sondaki nokta/bosluk temizligi.
7. Iki asamali ag yoklamasi (HEAD + Range: bytes 0-0 GET fallback).
"""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

VARSAYILAN_AD = "download"
EN_FAZLA_KARAKTER = 200

YASAK_KARAKTERLER = set('<>:"/\\|?*')
DOS_AYGIT_ADLARI = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Yaygin MIME turlerinin guvenli uzanti karsiliklari
MIME_UZANTILARI: dict[str, str] = {
    # Arsivler
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
    "application/gzip": "gz",
    "application/x-gzip": "gz",
    "application/x-tar": "tar",
    "application/x-7z-compressed": "7z",
    "application/vnd.rar": "rar",
    "application/x-rar-compressed": "rar",
    "application/x-bzip2": "bz2",
    "application/x-xz": "xz",
    "application/zstd": "zst",
    # Kurulum / calistirilabilir
    "application/x-msdownload": "exe",
    "application/x-msdos-program": "exe",
    "application/vnd.microsoft.portable-executable": "exe",
    "application/x-msi": "msi",
    "application/x-ms-installer": "msi",
    "application/x-apple-diskimage": "dmg",
    "application/vnd.debian.binary-package": "deb",
    "application/x-deb": "deb",
    "application/x-rpm": "rpm",
    "application/x-redhat-package-manager": "rpm",
    "application/vnd.android.package-archive": "apk",
    "application/x-iso9660-image": "iso",
    # Belgeler
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "application/rtf": "rtf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    # Metin / veri
    "text/plain": "txt",
    "text/html": "html",
    "text/css": "css",
    "text/csv": "csv",
    "text/markdown": "md",
    "application/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/javascript": "js",
    "text/javascript": "js",
    # Medya - Gorsel
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/avif": "avif",
    "image/svg+xml": "svg",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    # Medya - Video
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    # Medya - Ses
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def _unquote(deger: str) -> str:
    """Tirnaklari kaldir ve ters slash kacislarini coz."""
    deger = (deger or "").strip()
    if len(deger) >= 2 and deger[0] == '"' and deger[-1] == '"':
        icerik = deger[1:-1]
        cikti = []
        kacis = False
        for ch in icerik:
            if kacis:
                cikti.append(ch)
                kacis = False
            elif ch == "\\":
                kacis = True
            else:
                cikti.append(ch)
        return "".join(cikti)
    return deger


def _parametreleri_bol(baslik: str) -> list[str]:
    """Tirnak icindeki noktalı virgülleri bölmeden parametreleri ayir."""
    parcalar: list[str] = []
    baslangic = 0
    tirnakta = False
    kacis = False
    for i, ch in enumerate(baslik):
        if kacis:
            kacis = False
            continue
        if ch == "\\":
            if tirnakta:
                kacis = True
        elif ch == '"':
            tirnakta = not tirnakta
        elif ch == ";" and not tirnakta:
            parcalar.append(baslik[baslangic:i])
            baslangic = i + 1
    parcalar.append(baslik[baslangic:])
    return [p.strip() for p in parcalar if p.strip()]


def _decode_rfc5987(deger: str) -> str | None:
    """RFC 5987 bicimi: charset'language'pct-encoded (orn: UTF-8''dosya%20adi.zip)"""
    deger = _unquote(deger)
    parcalar = deger.split("'", 2)
    if len(parcalar) != 3:
        return None
    charset, _, kodlu = parcalar
    charset = charset.strip().lower()
    if charset not in ("utf-8", "us-ascii", "iso-8859-1"):
        return None
    try:
        return urllib.parse.unquote(kodlu, encoding=charset or "utf-8", errors="replace")
    except (UnicodeError, ValueError):
        return None


def filename_from_content_disposition(header: str) -> str | None:
    """Content-Disposition basligindan dosya adini cikarir.
    RFC 6266 §4.3: hem filename hem filename* varsa filename* onceliklidir.
    """
    if not header:
        return None

    plain: str | None = None
    extended: str | None = None

    for param in _parametreleri_bol(header):
        if "=" not in param:
            continue
        anahtar, deger = param.split("=", 1)
        anahtar = anahtar.strip().lower()
        deger = deger.strip()

        if anahtar == "filename" and plain is None:
            plain = _unquote(deger)
        elif anahtar == "filename*" and extended is None:
            extended = _decode_rfc5987(deger)

    secilen = extended or plain
    if secilen and secilen.strip():
        return secilen.strip()
    return None


def is_plausible_extension(uzanti: str) -> bool:
    """Bir dizginin gercek bir dosya uzantisi olup olmadigina karar verir.
    dlman kurali:
    - 1-8 karakter uzunlugunda
    - Salt alfanümerik
    - Tamami RAKAM OLMAMALI (v1.12.0 veya part.001 gibi surumler uzanti degildir!)
    """
    if not uzanti or len(uzanti) > 8:
        return False
    if not uzanti.isalnum():
        return False
    if uzanti.isdigit():
        return False
    return True


def split_stem_ext(dosya_adi: str) -> tuple[str, str | None]:
    """Dosya adini (kok, uzanti) olarak ayirir.
    Standart Path.suffix'ten farkli olarak 'app-v1.12.0'daki '.0'i uzanti
    ZANNETMEZ (kok='app-v1.12.0', uzanti=None dondurur).
    Gizli dosyalar (.gitignore) da uzantisiz kabul edilir.
    """
    if not dosya_adi:
        return ("", None)

    son_nokta = dosya_adi.rfind(".")
    if son_nokta > 0:
        olasi = dosya_adi[son_nokta + 1:]
        if is_plausible_extension(olasi):
            return (dosya_adi[:son_nokta], olasi)
    return (dosya_adi, None)


def ensure_extension(dosya_adi: str, content_type: str | None) -> str:
    """Eger dosya adinin gecerli bir uzantisi yoksa, MIME turunden uygun
    uzantiyi ekler."""
    if not dosya_adi:
        return VARSAYILAN_AD
    _, uzanti = split_stem_ext(dosya_adi)
    if uzanti is not None:
        return dosya_adi

    if not content_type:
        return dosya_adi

    # Parametreleri (charset=utf-8) at
    mime = content_type.split(";", 1)[0].strip().lower()
    eklenecek = MIME_UZANTILARI.get(mime)
    if eklenecek:
        temiz = dosya_adi.rstrip(". ")
        return f"{temiz}.{eklenecek}"
    return dosya_adi


def guvenli_dosya_adi(ad: str) -> str:
    """Dosya adini tek bir guvenli dosya sistemi bileseni haline getirir.

    - Yol ayraclari (/ ve \\) ve yasakli karakterler (<>:"/\\|?*) '_' ile degistirilir
      (boylece ../ ve ..\\ gecisleri ../../etc/passwd -> .._.._etc_passwd olur,
      dizin disina cikamaz).
    - Windows dosya sisteminin attigi sondaki nokta ve bosluklar temizlenir.
    - Windows ayrilmis aygit adlari (CON, PRN, AUX, NUL, COM1-9, LPT1-9) '_' ile on eklenir.
    - Uzanti korunarak en fazla 200 karaktere sigdirilir.
    """
    if not ad:
        return ""

    temiz_karakterler = []
    for ch in ad:
        if ch in YASAK_KARAKTERLER or ord(ch) < 32:
            temiz_karakterler.append("_")
        else:
            temiz_karakterler.append(ch)

    temiz = " ".join("".join(temiz_karakterler).split()).rstrip(". ")
    if not temiz:
        return ""

    # Windows DOS ayrilmis aygit adlari
    kok, uzanti = split_stem_ext(temiz)
    if kok.upper() in DOS_AYGIT_ADLARI:
        if uzanti:
            temiz = f"_{kok}.{uzanti}"
        else:
            temiz = f"_{kok}"

    # Uzantiyi koruyarak kirp (en fazla 200 karakter)
    EN_FAZLA = 200
    if len(temiz) > EN_FAZLA:
        kok, uzanti = split_stem_ext(temiz)
        if uzanti:
            kalan = max(1, EN_FAZLA - len(uzanti) - 1)
            temiz = f"{kok[:kalan].rstrip()}.{uzanti}"
        else:
            temiz = temiz[:EN_FAZLA].rstrip(". ")

    return temiz


def filename_from_url(url: str) -> str | None:
    """URL'nin son gecerli yol bileseninden dosya adini cikarir."""
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if not path:
            return None
        # Sondaki egrileri atip son bileseni al
        segmentler = [s for s in path.split("/") if s]
        if not segmentler:
            return None
        son = urllib.parse.unquote(segmentler[-1])
        guvenli = guvenli_dosya_adi(son)
        return guvenli or None
    except Exception:
        return None


def resolve_filename(
    url: str,
    content_disposition: str | None = None,
    content_type: str | None = None,
) -> str:
    """Bir indirme icin en iyi dosya adini secer.

    Oncelik sirasi:
    1. Content-Disposition basligindaki ad
    2. URL yolunun son parcasi
    3. Varsayilan ad (download)

    Sonuc guvenli hale getirilir ve gerekirse MIME'dan uzanti tamamlanir.
    """
    if url.lower().startswith("magnet:"):
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            dn = query.get("dn", [""])[0]
            if dn:
                return guvenli_dosya_adi(dn) or "magnet baglantisi"
        except Exception:
            pass
        return "magnet baglantisi"

    ad = None
    if content_disposition:
        ad = filename_from_content_disposition(content_disposition)
        if ad:
            ad = guvenli_dosya_adi(ad)

    if not ad:
        ad = filename_from_url(url)

    if not ad:
        ad = VARSAYILAN_AD

    ad = ensure_extension(ad, content_type)
    return guvenli_dosya_adi(ad) or VARSAYILAN_AD


def probe_url_info(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 3.0,
) -> dict:
    """Verilen URL icin dosya adi, boyut ve tur bilgisini sondajlar.

    1. Once HEAD atilir.
    2. Eger Content-Disposition ya da Content-Length yoksa, CDN'ler icin
       'Range: bytes 0-0' ile 1 baytlik kismi GET atilarak basliklar yakalanir.
    """
    url = (url or "").strip()
    if not url or not url.lower().startswith(("http://", "https://")):
        return {
            "ok": False,
            "filename": resolve_filename(url),
            "size": None,
            "content_type": None,
            "resumable": False,
        }

    istek_basliklari = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    if headers:
        istek_basliklari.update(headers)

    content_disposition: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    resumable = False
    son_url = url

    # 1. Adim: HEAD
    try:
        req = urllib.request.Request(url, headers=istek_basliklari, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            son_url = resp.geturl() or url
            resp_headers = resp.headers
            content_disposition = resp_headers.get("Content-Disposition")
            content_type = resp_headers.get("Content-Type")
            cl = resp_headers.get("Content-Length")
            if cl and cl.isdigit():
                content_length = int(cl)
            accept_ranges = resp_headers.get("Accept-Ranges", "")
            if "bytes" in accept_ranges.lower():
                resumable = True
    except Exception:
        pass

    # 2. Adim: CDN fallback — eger Content-Disposition yoksa veya boyut bilinmiyorsa
    # 1 baytlik Range GET dene
    if not content_disposition or content_length is None:
        try:
            get_headers = dict(istek_basliklari)
            get_headers["Range"] = "bytes 0-0"
            req = urllib.request.Request(son_url, headers=get_headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = resp.headers
                if not content_disposition:
                    content_disposition = resp_headers.get("Content-Disposition")
                if not content_type:
                    content_type = resp_headers.get("Content-Type")
                # Content-Range: bytes 0-0/12345
                cr = resp_headers.get("Content-Range", "")
                if "/" in cr:
                    toplam = cr.rsplit("/", 1)[-1].strip()
                    if toplam.isdigit():
                        content_length = int(toplam)
                        resumable = True
                if content_length is None:
                    cl = resp_headers.get("Content-Length")
                    if cl and cl.isdigit() and int(cl) > 1:
                        content_length = int(cl)
        except Exception:
            pass

    cozulmus_ad = resolve_filename(son_url, content_disposition, content_type)

    return {
        "ok": True,
        "filename": cozulmus_ad,
        "size": content_length,
        "content_type": content_type,
        "resumable": resumable,
        "final_url": son_url,
    }
