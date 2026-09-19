"""v1.7.5 — Ayar dogrulama katmani (alan bazli, i18n anahtarli).

Sozlesme:
  * Her dogrulayici ya NORMALIZE EDILMIS degeri dondurur ya da `AyarHatasi`
    firlatir. Hata mesaji DUZ METIN DEGIL, bir i18n ANAHTARIDIR (`err.*`);
    metni UI kendi dilinde uretir.
  * `ayarlari_dogrula()` HEPSI-YA-HICBIRI calisir: bir alan bile gecersizse
    cagiran taraf HICBIR seyi kaydetmez. Bu yuzden fonksiyon kaydetmez,
    yalnizca `(hatalar, temiz)` ciftini dondurur; kayit hatalar bosken yapilir.

Gizlilik: proxy adresi parola icerebilir. Bu modul ASLA ham proxy'yi (ya da
baska bir sirri) loga/hataya koymaz — `proxy_maskele()` disari verilecek tek
bicimdir ve kimlik bolumunu tamamen siler.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# --- hata tasiyicisi ------------------------------------------------------


class AyarHatasi(ValueError):
    """Tek bir ayar alaninin dogrulama hatasi (i18n anahtari tasir)."""

    def __init__(self, alan: str, mesaj_anahtari: str) -> None:
        super().__init__(mesaj_anahtari)
        self.alan = alan
        self.mesaj_anahtari = mesaj_anahtari

    def sozluk(self) -> dict[str, str]:
        return {"alan": self.alan, "mesaj_anahtari": self.mesaj_anahtari}


# --- sinirlar -------------------------------------------------------------

PORT_MIN = 1024
PORT_MAX = 65535
SNAIL_MIN = 1
SNAIL_MAX = 1_000_000

# Uzanti adinda yasak: joker ve yol karakterleri. Bunlar dosya secicide
# desen/klasor anlamina gelir; uzanti listesine girerse esleme saskinlasir.
_UZANTI_YASAK = set("*?/\\:")
_UZANTI_AYIRICI = re.compile(r"[,;\s]+")
_UZANTI_GECERLI = re.compile(r"^[0-9a-z][0-9a-z._+-]*$")
UZANTI_MAX = 24

# host:port (core/proxy.py ile ayni kural)
_HOST_PORT = re.compile(r"^[^:\s/@]+:\d+$")
_PROXY_TIPLERI = ("http", "https", "socks5", "socks5h", "socks4")
PROXY_MAX = 1024


# --- yardimci -------------------------------------------------------------


def _tamsayi(alan: str, deger: Any, anahtar: str) -> int:
    """bool/ondalik/metin gurultusunu eleyen kati tamsayi okuyucu."""
    if isinstance(deger, bool):
        raise AyarHatasi(alan, anahtar)
    if isinstance(deger, int):
        return deger
    if isinstance(deger, float):
        if not deger.is_integer():
            raise AyarHatasi(alan, anahtar)
        return int(deger)
    if isinstance(deger, str):
        ham = deger.strip()
        if re.fullmatch(r"[+-]?\d+", ham):
            return int(ham)
    raise AyarHatasi(alan, anahtar)


def proxy_maskele(proxy: object) -> str:
    """Loglanabilir proxy gosterimi: kullanici/parola bolumu TAMAMEN atilir.

    Bicimi bozuk girdi bile sizdirilmaz — cozulemezse "<proxy>" doner.
    """
    ham = str(proxy or "").strip()
    if not ham:
        return ""
    try:
        tip, giris = _proxy_parcala(ham)
    except AyarHatasi:
        return "<proxy>"
    return "%s://%s" % (tip, giris)


def _proxy_parcala(ham: str) -> tuple[str, str]:
    """('socks5', 'host:1080') — kimlik bolumu DUSURULUR (asla dondurulmez)."""
    giris = ham
    tip = "http"
    if "://" in giris:
        sekme, _, geri = giris.partition("://")
        tip = sekme.strip().lower()
        giris = geri
        if tip not in _PROXY_TIPLERI:
            raise AyarHatasi("proxy", "err.proxyScheme")
    if "@" in giris:
        _, _, giris = giris.rpartition("@")
    giris = giris.strip()
    if not _HOST_PORT.match(giris):
        raise AyarHatasi("proxy", "err.proxyFormat")
    try:
        port = int(giris.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        raise AyarHatasi("proxy", "err.proxyFormat") from None
    if not 1 <= port <= PORT_MAX:
        raise AyarHatasi("proxy", "err.proxyPort")
    return tip, giris


# --- alan dogrulayicilari -------------------------------------------------


def dogrula_api_port(deger: Any) -> int:
    port = _tamsayi("api_port", deger, "err.portRange")
    if not PORT_MIN <= port <= PORT_MAX:
        raise AyarHatasi("api_port", "err.portRange")
    return port


def dogrula_api_listen_port(deger: Any) -> int:
    """Kullanicinin SECTIGI port (baglanilan calisan port ayri alandir)."""
    port = _tamsayi("api_listen_port", deger, "err.portRange")
    if not PORT_MIN <= port <= PORT_MAX:
        raise AyarHatasi("api_listen_port", "err.portRange")
    return port


def dogrula_snail_speed_kb(deger: Any) -> int:
    hiz = _tamsayi("snail_speed_kb", deger, "err.snailRange")
    if not SNAIL_MIN <= hiz <= SNAIL_MAX:
        raise AyarHatasi("snail_speed_kb", "err.snailRange")
    return hiz


def dogrula_proxy(deger: Any) -> str:
    """Bos proxy gecerlidir (= proxy kullanma). Doluysa bicim zorunlu.

    NOT: donen deger KULLANICININ yazdigi (kimlik bilgisi dahil) adrestir;
    saklanmasi gerekir. Loglamak icin `proxy_maskele()` kullan.
    """
    ham = str(deger or "").strip()
    if not ham:
        return ""
    if len(ham) > PROXY_MAX:
        raise AyarHatasi("proxy", "err.proxyLong")
    _proxy_parcala(ham)  # bicim denetimi; ciktisi loglama icindir
    return ham


def dogrula_clipboard_exts(deger: Any) -> str:
    """Virgul/bosluk/noktali virgul/satir ile ayrilmis uzanti listesi.

    Normalize: kucuk harf, bastaki nokta atilir, yinelenenler temizlenir,
    sira KORUNUR. Joker (`*?`) ve yol karakteri (`/\\:`) iceren giris reddedilir.
    Bos liste gecerlidir (pano izleme filtresiz degil, KAPALI demektir).
    """
    if isinstance(deger, (list, tuple)):
        ham = ",".join(str(p) for p in deger)
    else:
        ham = str(deger or "")
    temiz: list[str] = []
    for parca in _UZANTI_AYIRICI.split(ham):
        uzanti = parca.strip().lower()
        if not uzanti:
            continue
        if _UZANTI_YASAK & set(uzanti):
            raise AyarHatasi("clipboard_exts", "err.extWildcard")
        uzanti = uzanti.lstrip(".")
        if not uzanti:
            raise AyarHatasi("clipboard_exts", "err.extInvalid")
        if len(uzanti) > UZANTI_MAX or not _UZANTI_GECERLI.match(uzanti):
            raise AyarHatasi("clipboard_exts", "err.extInvalid")
        if uzanti not in temiz:
            temiz.append(uzanti)
    return ",".join(temiz)


def clipboard_exts_listesi(deger: Any) -> list[str]:
    """Dogrulanmis uzantilarin liste hali (UI/eslesme icin kolaylik)."""
    normal = dogrula_clipboard_exts(deger)
    return [p for p in normal.split(",") if p]


def dogrula_ag_konumlari(deger: Any) -> str:
    """Satir basina bir UNC yolu (`\\\\sunucu\\paylasim`).

    Yerel yollar (C:\\..., ./x), eksik/yarim UNC ve surucu harfleri REDDEDILIR.
    Yinelenenler (buyuk/kucuk harf farki dahil) temizlenir, sira korunur.
    Erisim denetimi BURADA YAPILMAZ (ag gecici kopabilir); bicim denetimidir.
    """
    if isinstance(deger, (list, tuple)):
        satirlar = [str(p) for p in deger]
    else:
        satirlar = str(deger or "").splitlines()
    temiz: list[str] = []
    gorulen: set[str] = set()
    for satir in satirlar:
        yol = satir.strip().replace("/", "\\").rstrip("\\")
        if not yol:
            continue
        if not yol.startswith("\\\\"):
            raise AyarHatasi("ag_konumlari", "err.netPathFormat")
        govde = yol[2:]
        parcalar = [p for p in govde.split("\\") if p]
        # En az sunucu + paylasim; "\\\\sunucu" tek basina bir paylasim degildir.
        if len(parcalar) < 2 or len(parcalar) != len(govde.split("\\")):
            raise AyarHatasi("ag_konumlari", "err.netPathFormat")
        if any(set(p) & set('*?<>|"') for p in parcalar):
            raise AyarHatasi("ag_konumlari", "err.netPathFormat")
        anahtar = yol.lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        temiz.append(yol)
    return "\n".join(temiz)


# Alan adi -> dogrulayici. Burada OLMAYAN alanlar dokunulmadan gecer.
DOGRULAYICILAR: dict[str, Callable[[Any], Any]] = {
    "api_port": dogrula_api_port,
    "api_listen_port": dogrula_api_listen_port,
    "snail_speed_kb": dogrula_snail_speed_kb,
    "proxy": dogrula_proxy,
    "clipboard_exts": dogrula_clipboard_exts,
    "ag_konumlari": dogrula_ag_konumlari,
}


def ayarlari_dogrula(ayarlar: dict) -> tuple[list[dict], dict]:
    """HEPSI-YA-HICBIRI dogrulama.

    Doner: (hatalar, temiz_ayarlar)
      * `hatalar` bos DEGILSE `temiz_ayarlar` KULLANILMAZ ve HICBIR alan
        kaydedilmez. Kismi kayit yoktur.
      * Tum alanlar taranir (ilk hatada durulmaz) ki UI butun hatalari
        birden gosterebilsin.
    """
    hatalar: list[dict] = []
    temiz: dict[str, Any] = {}
    for alan, deger in (ayarlar or {}).items():
        dogrulayici = DOGRULAYICILAR.get(alan)
        if dogrulayici is None:
            temiz[alan] = deger
            continue
        try:
            temiz[alan] = dogrulayici(deger)
        except AyarHatasi as exc:
            hatalar.append(exc.sozluk())
        except (TypeError, ValueError):
            hatalar.append({"alan": alan, "mesaj_anahtari": "err.invalidValue"})
    if hatalar:
        return hatalar, {}
    return [], temiz
