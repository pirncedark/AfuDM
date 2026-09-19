# -*- coding: utf-8 -*-
"""LinkGrabber cekirdegi — ham metinden indirilebilir baglantilari cikarir.

v1.5 P0 masaustu LinkGrabber panelinin kalbi. Akis:
    ayikla -> normalize -> tekil_les -> tur_bul -> filtrele -> probe_es_zamanli

- `ayikla` content.js'teki seciliBaglantilariBul regex'inin Python karsiligidir
  (http/https/ftp + magnet), metin icinde gomulu URL'leri de yakalar.
- `tekil_les` ayni URL'yi (ve magnet'te ayni infohashi) birden fazla
  gostermez — "ayni URL tekrari engeli" ROADMAP geregidir.
- `tur_bul` uzanti + bilinen video sitesi + magnet/.torrent ile tahmin yapar;
  kesin ayrim indirme aninda manager.detect_kind'da yapilir.
- `probe_es_zamanli` core/dosya_adi.probe_url_info'yu sinirli eszamanlilikla
  (varsayilan 8) calistirir: boyut/dosya adi icin lazy probe.

https://github.com/afuuu/AfuDM — ROADMAP.md v1.5 (LinkGrabber)
"""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from core import dosya_adi

# --- URL cikarma -----------------------------------------------------------
# content.js: /(?:https?:\/\/[^\s<>"']+|magnet:\?[^\s<>"']+)/gi
# Python karsiligi: ftp de eklenir; parantez icinde yakalanmaz (metin parcasi).
URL_DESENI = re.compile(
    r"(?:https?://|ftp://)[\w\-._~:/?#\[\]@!$&'()*+,;=%]+"
    r"|magnet:\?[^\s<>\"']+",
    re.IGNORECASE,
)

# --- Tur tahmini -----------------------------------------------------------
ARSIV_UZANTILARI = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".tgz", ".iso"}
VIDEO_UZANTILARI = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".ts", ".m3u8", ".mpd"}
SES_UZANTILARI = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".wav"}
VIDEO_SITELERI = {
    "youtube.com", "youtu.be", "www.youtube.com",
    "vimeo.com", "player.vimeo.com",
    "dailymotion.com", "www.dailymotion.com",
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    "tiktok.com", "www.tiktok.com",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com",
    # X/Twitter kisa adresleri x.com uzerinden doner; genel "x.com" cok yaygin
    # bir alan adi oldugu icin yalniz twitter.com kabul edilir.
    "twitter.com", "www.twitter.com",
    "kick.com", "www.kick.com",
}


def _yol(url: str) -> str:
    try:
        return urllib.parse.urlsplit(url).path.lower()
    except Exception:
        return ""


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


def ayikla(metin: str) -> list[str]:
    """Metinden URL adaylarini cikarir (http/https/ftp/magnet)."""
    if not metin:
        return []
    return URL_DESENI.findall(metin)


def normalize(url: str) -> str:
    """URL'yi temizler: trim, sondaki noktalama ve tirnak ayracini atar."""
    url = (url or "").strip()
    # Cevreleyen tirnak/isaret ve metin sonundaki nokta/virgul URL'nin parcasi
    # degildir. (URL regex tirnaklari yakalamaz ama normalize disaridan da
    # cagrilabilir — orn. panodan kopyalanan metin.)
    return url.strip(".,;:!?\"'")


def _anahtar(url: str) -> str:
    """Tekillesme anahtari: normal URL'de sirali hali, magnet'te infohash."""
    url = normalize(url)
    if url.lower().startswith("magnet:"):
        try:
            sorgu = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            xt = sorgu.get("xt", [""])[0]
            if "urn:btih:" in xt:
                return "btih:" + xt.split("urn:btih:", 1)[1].lower()
        except Exception:
            pass
        return url.lower()
    return url.casefold()


def tekil_les(urller: list[str]) -> list[str]:
    """Normalize edilmis anahtara gore tekrarlari temizler; sira korunur."""
    gorulen: set[str] = set()
    sonuc: list[str] = []
    for url in urller:
        anahtar = _anahtar(url)
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            sonuc.append(normalize(url))
    return sonuc


def tur_bul(url: str) -> str:
    """Hafif tur tahmini: \"torrent\" | \"video\" | \"arsiv\" | \"http\"."""
    u = normalize(url)
    alt = u.lower()
    if alt.startswith("magnet:") or _yol(alt).endswith(".torrent"):
        return "torrent"

    yol = _yol(alt)
    for uz in ARSIV_UZANTILARI:
        if yol.endswith(uz):
            return "arsiv"
    for uz in VIDEO_UZANTILARI | SES_UZANTILARI:
        if yol.endswith(uz):
            return "video"

    host = _host(u)
    for site in VIDEO_SITELERI:
        if host == site or host.endswith("." + site):
            return "video"
    return "http"


def filtrele(
    urller: list[str],
    sadece: set[str] | None = None,
    domain: str = "",
) -> list[str]:
    """Tur (sadece) ve alan adi (domain) filtrelerini uygular."""
    sonuc: list[str] = []
    dom = (domain or "").strip().lower().lstrip("www.")
    for url in urller:
        if sadece and tur_bul(url) not in sadece:
            continue
        if dom:
            host = _host(url).lstrip("www.")
            if dom not in host:
                continue
        sonuc.append(url)
    return sonuc


def probe_es_zamanli(
    urller: list[str],
    es_zamanli: int = 8,
    timeout: float = 3.0,
) -> dict[str, dict]:
    """Toplu lazy probe: her URL icin dosya adi/boyut/tip, eszamanliligi
    sinirli (ThreadPoolExecutor). Sonuc sozlugu: {url: probe_dict}.
    http/https olmayanlar (magnet, .torrent dosyasi) atlanmaz — probe_url_info
    onlar icin ok=False dondurur, panel \"bilgi yok\" gosterir.
    """
    es_zamanli = max(1, int(es_zamanli))
    sonuclar: dict[str, dict] = {}

    def _probe(url: str) -> tuple[str, dict]:
        try:
            return url, dosya_adi.probe_url_info(url, timeout=timeout)
        except Exception as exc:  # beklenmedik hata paneli kilitlemesin
            return url, {"ok": False, "error": str(exc)[:120]}

    with ThreadPoolExecutor(max_workers=es_zamanli) as havuz:
        gelecekler = {havuz.submit(_probe, u): u for u in urller}
        for gelecek in as_completed(gelecekler):
            url, sonuc = gelecek.result()
            sonuclar[url] = sonuc
    return sonuclar