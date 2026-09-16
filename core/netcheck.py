"""Ag yetenegi tespiti — IPv6 GERCEKTEN kullanilabiliyor mu?

Neden gerekli: aria2c bir sunucunun AAAA kaydini gorunce IPv6'yi dener; makinede
IPv6 yolu yoksa WSAENETUNREACH alir ve indirmeyi IPTAL EDER, IPv4'e dusmez.
(yt-dlp'nin kendi indiricisi duser; bu yuzden hata sadece aria2c dis indirici
kullanilirken cikar.) Bu makinede yalnizca Tailscale ULA adresi var, genel IPv6
yok — googlevideo AAAA dondurunce video indirmeleri boyle patliyordu.

Bayragi sabit yazmak yanlis olurdu: klasor PORTABLE, IPv6'si calisan baska bir
makineye kopyalanabilir. Bu yuzden olcum calisma aninda yapilir ve onbelleklenir.
Olcum UDP "connect" ile yapilir: paket GONDERILMEZ, cekirdek sadece rota secer,
yani internet trafigi ve gecikme olusturmaz.
"""
from __future__ import annotations

import socket

# Rota secimi icin kullanilan genel IPv6 adresleri (Google ve Cloudflare DNS).
_PROBE_TARGETS = (("2001:4860:4860::8888", 53), ("2606:4700:4700::1111", 53))

_cached: bool | None = None


def _is_global_unicast(addr: str) -> bool:
    """2000::/3 disindaki her sey (loopback, fe80:: link-local, fc00::/7 ULA)
    internete cikis icin ise yaramaz. Tailscale'in fd7a:: adresi de buraya girer."""
    try:
        packed = socket.inet_pton(socket.AF_INET6, addr.split("%")[0])
    except OSError:
        return False
    return (packed[0] & 0xE0) == 0x20


def _probe() -> bool:
    if not socket.has_ipv6:
        return False
    for host, port in _PROBE_TARGETS:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.settimeout(0.5)
            sock.connect((host, port))
            local = sock.getsockname()[0]
        except OSError:
            continue
        finally:
            if sock is not None:
                sock.close()
        if _is_global_unicast(local):
            return True
    return False


def ipv6_usable(refresh: bool = False) -> bool:
    """IPv6 ile internete cikilabiliyor mu? Sonuc surec omru boyunca saklanir."""
    global _cached
    if _cached is None or refresh:
        _cached = _probe()
    return _cached


def aria2_ipv6_args() -> list[str]:
    """IPv6 yoksa aria2'yi IPv4'e kilitle; varsa hicbir sey degistirme."""
    return [] if ipv6_usable() else ["--disable-ipv6=true"]
