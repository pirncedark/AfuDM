"""Network Core v1.4 — proxy kaynaklari ve motor kurallari.

Proxy UÇ katmandan gelir (ayri ayri ayarlanabilir, oncelik sirasiyla):
  1. o istege ozel acik proxy   → `models.DownloadRequest.proxy`
  2. Windows sistem proxy        → Ayarlar "system_proxy" aciksa (Internet Settings)
  3. AfuDM genel proxy           → Ayarlar "proxy" (varsayilan)

`parcala` her katmandan gelen adresi TEK kuralla normalize eder; `aria2_secenekleri`
o sozlugu aria2 add/changeOption anahtarlarina, `url` ise yt-dlp'nin --proxy
girdisine cevirir. Gecersiz adresler VakdeVakabacili ValueError ile elenir.

Sistem proxy PAC (AutoConfigURL) KASTEN DESTEKLENMEZ: bellegi calistirmak
(bir .pac dosyasindaki JS) AfuDM'in risk yuzeyini buyutur — AutoConfigURL varsa
yok sayilir, kullanici gerekirse Acik/Sistem/Diger katmanlardan net adres yazar.
"""
from __future__ import annotations

import os
import re

# Windows HKCU anahtari: ProxyEnable / ProxyServer / ProxyOverride / AutoConfigURL
_SISTEM_ANAHTAR = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

_TIP_SINIRI = 1024

# host:port (host alan sag alani sayisal port). bos adres, ":" gibi eksik
# yazimlar ve alanalan karakterler elenir.
_HOST_PORT = re.compile(r"^[^:\s/]+:\d+$")


def sistem_proxysi() -> str | None:
    """Windows Internet Settings'ten sistem proxy adresi (yalniz http tarafi).

    - ProxyEnable=0 veya ProxyServer bos ise None.
    - 'http=host:8123;https=host:8124' bilesik biciminden http girdisi secilir.
    - AutoConfigURL (PAC) okunmaz (modul basligindaki karar).
    - Best-effort: anahtar/acma hatalari sessizce None doner; hicbir cagri
      patlamaz (GUI'de Ayarlar bunu gosterirken de guvenle cagirilir).
    """
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _SISTEM_ANAHTAR)
        try:
            aktif, _ = winreg.QueryValueEx(k, "ProxyEnable")
            sunucu, _ = winreg.QueryValueEx(k, "ProxyServer")
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None
    if not aktif or not sunucu:
        return None
    sunucu = str(sunucu).strip()
    bolumler = {}
    for parca in sunucu.split(";"):
        if "=" in parca:
            anahtar, _, deger = parca.partition("=")
            bolumler[anahtar.strip().lower()] = deger.strip()
    adres = bolumler.get("http") or bolumler.get("https") or sunucu
    adres = adres.strip()
    if not adres:
        return None
    # Nadir "http://host:port" yazimi varsa basligi kirp
    if "://" in adres:
        adres = adres.split("://", 1)[1]
    return adres


def parcala(uri: object) -> dict:
    """'socks5://user:pass@host:port', 'http://host:port', 'host:port' → dict.

    Donen sozluk:
        {'tip': 'http'|'socks5'|'socks4',
         'adres': 'host:port',
         'kullanici': str | '',
         'sifre': str | ''}

    - Sekmesiz "host:port" http varsayilir.
    - 'https' sekmesi http'ya indirgenir (SSL proxy desteklenmez).
    - 'socks5h' (DNS proxy'de cozulur) 'socks5' olarak kabul edilir — aria2
      socks5 zaten adi proxy'de cozer.
    - Gecersiz sekme / 'host:port' bicimi eksik / asiri uzun → ValueError.
    """
    ham = str(uri or "").strip()
    if not ham:
        raise ValueError("proxy adresi bos")
    tip = "http"
    giris = ham
    if "://" in giris:
        sekme, _, geri = giris.partition("://")
        tip = sekme.strip().lower()
        giris = geri
        if tip == "https":
            tip = "http"
        elif tip == "socks5h":
            tip = "socks5"
        if tip not in ("http", "socks5", "socks4"):
            raise ValueError("desteklenen proxy: http, socks5, socks4")
    kullanici = ""
    sifre = ""
    if "@" in giris:
        kimlik, _, giris = giris.rpartition("@")
        if ":" in kimlik:
            kullanici, _, sifre = kimlik.partition(":")
        else:
            kullanici = kimlik
    giris = giris.strip()
    if not _HOST_PORT.match(giris):
        raise ValueError("proxy 'host:port' biciminde olmali (orn. 127.0.0.1:1080)")
    if len(ham) > _TIP_SINIRI:
        raise ValueError("proxy adresi cok uzun (max %d)" % _TIP_SINIRI)
    return {"tip": tip, "adres": giris, "kullanici": kullanici, "sifre": sifre}


def aria2_secenekleri(p: dict) -> dict:
    """Normalize proxy'yi aria2 add/changeOption seceneklerine cevirir.

    `all-proxy-type=socks5` ile BitTorrent bağlantilari da SOCKS uzerinden
    gider (aria2 belgeli davranis); 'http' tipi yalniz HTTP/FTP islerine etkir.
    """
    sec: dict = {"all-proxy": p["adres"], "all-proxy-type": p["tip"]}
    if p.get("kullanici"):
        sec["all-proxy-user"] = p["kullanici"]
    if p.get("sifre"):
        sec["all-proxy-passwd"] = p["sifre"]
    return sec


def url(p: dict) -> str:
    """yt-dlp'nin --proxy girdisi: 'socks5://user:pass@host:port'."""
    kimlik = "%s:%s@" % (p["kullanici"], p["sifre"]) if p.get("kullanici") else ""
    return "%s://%s%s" % (p["tip"], kimlik, p["adres"])


def komut_secenekleri(p: dict) -> str:
    """aria2c komut satiri (yt-dlp --downloader-args icin) secenekleri."""
    return " ".join("--%s=%s" % (k, v) for k, v in aria2_secenekleri(p).items())