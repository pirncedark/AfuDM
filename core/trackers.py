"""Guncel tracker listesini gunluk indirip aria2'ye uygular.

Olu torrentlerde seed bulma sansini ciddi artirir: ngosang/trackerslist
listesi her gun guncellenir, biz 24 saatte bir cekip bt-tracker'a yaziyoruz.

Gelen her liste (indirilen, kullanicinin attigi .txt, yapistirdigi metin)
`tracker_normalize` adimindan gecer: icine gomulen `*` temizlenir, yapisik
iki URL bolunur, yalniz udp/http/https kabul edilir, yineler tek kayda
dusurulur, yerel ag ve domain-policy kapsamindaki adresler havuzdan cikar.

NOT (olculmus karar): fazla tracker = hizli torrent DEMEK DEĞILDIR. Olu
tracker'lar DNS/timeout yukuyle duyuruyu YAVASLATIR; deger, en büyük liste
degil, temizlenmis havuzdur. Saglik olcumu tracker_saglik.py'dedir, tarama
sonrasi YALNIZ canlilar uygulanir.
"""
from __future__ import annotations

import ipaddress
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import paths

SOURCES = [
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt",
    "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_best.txt",
]
MAX_AGE = 24 * 3600  # 24 saat

# aria2 yalnizca UDP/HTTP(S) tracker destekler. ws:// ve wss:// WebTorrent
# semasidir — parseli ise yaramaz, sadece zaman asimi geciktirir.
GECERLI_SEMA = ("udp://", "http://", "https://")
_AYRAC = re.compile(r"(?:udp|https?)://", re.IGNORECASE)

# Varsayilan havuzdan cikarilan alan adlari. Neden: bu tip adresler basit
# "en buyuk liste" derlemelerinde dolasir; AfuDM'nin genel bt-tracker'ina
# girmesi istenmez. Normalize her kaynak icin (indirilen + kullanici) calisir.
YASAK_HOST_ALT = (
    "myporn.club",
)

_YEREL_EKLER = (".local", ".localhost")


def _host(adres: str) -> str | None:
    try:
        host = urllib.parse.urlsplit(adres).hostname
    except ValueError:
        return None
    return host.lower().rstrip(".") if host else None


def _yerel_mi(host: str) -> bool:
    """Yalniz yerel agda anlamli olan ve public havuzda yeri olmayan ana
    bilgisayarlar: localhost, '* .local' (retracker.local gibi), loopback ve
    ozel (RFC1918) IP adresleri."""
    if host in ("localhost", "127.0.0.1", "::1") or any(host.endswith(a) for a in _YEREL_EKLER):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return False


def _parcala(blok: str) -> list[str]:
    """Bir metin parcasindaki tracker adreslerini ayristirir.

    Birbirine yapismis iki URL'yi ayirir; gomulu '*', bosluklar vb. blok
    parcasinda kalir ve ayri adimda temizlenir:
        '.../announceudp://tracker.opentrackr.org:1337/announce'
        -> ['.../announce', 'udp://tracker.opentrackr.org:1337/announce']
    """
    uyumlar = list(_AYRAC.finditer(blok))
    parcalar: list[str] = []
    for i, u in enumerate(uyumlar):
        bitis = uyumlar[i + 1].start() if i + 1 < len(uyumlar) else len(blok)
        parcalar.append(blok[u.start():bitis])
    return parcalar


def tracker_normalize(ham: str | None) -> list[str]:
    """HAM tracker metnini normalize eder: temizle → bol → dogrula → tekil.

    - satir gomulu `*`, yapistirma, tirnak vb. temizlenir
    - yalniz udp/http/https kabul edilir (ws/wss, `dp://` yazim hatasi silinir)
    - iki URL yapismissa bolunur
    - yineler tek kayda dusurulur (buyuk/kucuk harf duyarsiz)
    - yerel ag (retracker.local, ozel IP) ve domain-policy adresleri cikarilir

    Kaynak sirasi korunur; her guncellemede calisir, acilista degil."""
    adaylar: list[str] = []
    for satir in (ham or "").replace(",", "\n").split("\n"):
        for parca in _parcala(satir):
            temiz = parca.strip(" \t*'\"()[]")
            if temiz.lower().startswith(GECERLI_SEMA):
                adaylar.append(temiz)

    sonuc: list[str] = []
    gorulen: set[str] = set()
    for adres in adaylar:
        host = _host(adres)
        if not host or _yerel_mi(host):
            continue
        if any(y in host for y in YASAK_HOST_ALT):
            continue
        anahtar = adres.lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        sonuc.append(adres)
    return sonuc


def _fetch() -> list[str]:
    last_error: Exception | None = None
    for url in SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AfuDM/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", "replace")
            trackers = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if trackers:
                return trackers
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def cached() -> list[str]:
    if not paths.TRACKERS_CACHE.exists():
        return []
    text = paths.TRACKERS_CACHE.read_text(encoding="utf-8", errors="replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def is_fresh() -> bool:
    if not paths.TRACKERS_CACHE.exists():
        return False
    return (time.time() - paths.TRACKERS_CACHE.stat().st_mtime) < MAX_AGE



def cache_yasi() -> float | None:
    """Onbellek kac saniye once yazildi? Dosya yoksa None (hic indirilmemis)."""
    if not paths.TRACKERS_CACHE.exists():
        return None
    return time.time() - paths.TRACKERS_CACHE.stat().st_mtime

def refresh(force: bool = False) -> list[str]:
    """Gerekiyorsa indir, normalize et, onbellege yaz ve listeyi don.
    Cevrimdisiysa onbellegi kullan."""
    paths.ensure_dirs()
    if not force and is_fresh():
        return cached()
    try:
        trackers = tracker_normalize("\n".join(_fetch()))
    except Exception:
        return cached()  # internet yoksa eldekiyle devam
    if trackers:
        paths.TRACKERS_CACHE.write_text("\n".join(trackers), encoding="utf-8")
    return trackers


def ayikla(metin: str) -> list[str]:
    """Kullanicinin yapistirdigi metinden tracker adreslerini cikar.

    Satir, virgul ya da bosluk ile ayrilmis olabilir; normalize hattinin
    aynisi uygulanir (bolme, sema filtre, tekil kilma, yerel/yasak ayikla).
    """
    return tracker_normalize(metin)


def apply_to_aria2(rpc, force: bool = False, ek: str = "", canli: str = "") -> int:
    """Guncel listeyi + KULLANICININ tracker'larini aria2'ye yazar.

    `canli` verilirse (bkz. core/tracker_saglik.py) OLCULMUS canli liste
    kullanilir ve en basa konur: cevap vermeyen tracker'lar aria2'yi her
    duyuruda zaman asimi kadar bekletiyordu (olculdu: 192 adresin 151'i olu).
    Donen deger: uygulanan toplam tracker sayisi.
    """
    filtreli = ayikla(canli)
    # Saglik taramasi varsa SADECE cevap verenler uygulanir. Elle girilenler de
    # tracker_saglik.tazele tarafindan taramaya katilir; cevap vermeyenleri
    # burada geri eklemek, olu elemenin tum faydasini yok ederdi. Kaynak
    # listeler silinmez ve ertesi gun yeniden denenir.
    if filtreli:
        tumu = filtreli
    else:
        kendi = ayikla(ek)
        liste = refresh(force=force)
        tumu = kendi + [t for t in liste if t not in kendi]
    if not tumu:
        return 0
    rpc.change_global_option({"bt-tracker": ",".join(tumu)})
    return len(tumu)
