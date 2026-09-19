# -*- coding: utf-8 -*-
"""LinkGrabber cekirdegi — ham metinden indirilebilir baglantilari cikarir.

v1.5 P0 masaustu LinkGrabber panelinin kalbi. Akis:
    ayikla -> normalize -> tekil_les -> tur_bul -> filtrele -> probe_es_zamanli

- `ayikla` content.js'teki seciliBaglantilariBul regex'inin Python karsiligidir
  (http/https/ftp + magnet), metin icinde gomulu URL'leri de yakalar.
- `normalize` kurallastirir: trim + sondaki ayrac, scheme/host kucuk harf,
  path/query KORUNUR (File.zip != file.zip), http/https/ftp'de fragment atilir.
- `tekil_les` ayni URL'yi (ve magnet'te ayni infohashi) birden fazla
  gostermez — "ayni URL tekrari engeli" ROADMAP geregidir. Anahtar
  kurallastirilmis URL'dir: scheme/host farki birlesir ama path farki birlesmez
  (File.zip != file.zip).
- `filtrele` alan adini UCUNA dayarir: `github.com` icin github.com ve alt
  alan adlari (api.github.com) eslesir, evilgithub.com eslesmez. www on eki
  simge olarak degil, dogru sekilde (yalniz on ek) elenir.
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
    """URL'yi temizler ve kurallastirir.

    - trim; cevreleyen tirnak/isaret ve metin sonundaki nokta/virgul URL'nin
      parcasi degildir.
    - scheme ve host kucuk harfe indirilir (a/b ve A/B ayni sunucudur).
    - path ve query AYNEN korunur: buyuk/kucuk harf farki URL'nin kendisidir
      (File.zip ile file.zip farkli baglantilardir).
    - http/https/ftp'de fragment atilir: sunucuya giden istekte yeri yoktur.
    """
    url = (url or "").strip()
    # Cevreleyen tirnak/isaret ve metin sonundaki nokta/virgul URL'nin parcasi
    # degildir. (URL regex tirnaklari yakalamaz ama normalize disaridan da
    # cagrilabilir — orn. panodan kopyalanan metin.)
    url = url.strip(".,;:!?\"'")
    try:
        bolum = urllib.parse.urlsplit(url)
        if not bolum.scheme or not bolum.netloc:
            return url
        scheme = bolum.scheme.lower()
        if scheme in ("http", "https", "ftp"):
            # Yalnizca hostu kucuk harfe indir; userinfo (kimlik) ve port korunur.
            netloc = bolum.netloc
            if "@" in netloc:
                kullanici, _, host = netloc.rpartition("@")
                netloc = f"{kullanici}@{host.lower()}"
            else:
                netloc = netloc.lower()
            bolum = bolum._replace(
                scheme=scheme,
                netloc=netloc,
                fragment="",  # sunucuya giden istekte yeri yok
            )
            return bolum.geturl()
        return url
    except Exception:
        return url


def _anahtar(url: str) -> str:
    """Tekillesme anahtari: kurallastirilmis URL, magnet'te infohash.

    `normalize` scheme/host'u kucuk harfe indirir ama path/query'yi KORUR
    (File.zip != file.zip); boylece ayni sunucunun farkli case'leri tekrarli
    sayilmaz ama gercekten farkli dosyalar yanlis birlesmez.
    """
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
    return url


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


def onceki_eslesen(adresler: list[str], gecmis: list[str]) -> list[str]:
    """Verilen adreslerden gecmiste kayitli olanlar (tekil liste olarak).

    Esleme anahtari `_anahtar` ile aynidir: http/https/ftp icin normalize edilmis
    URL, magnet icin btih infohash (buyuk/kucuk harf duyarsiz). Yalnizca
    "uyari cizgisi" icin kullanilir — indirmeyi engellemez.
    """
    bilinen: set[str] = set()
    for eski in gecmis or []:
        anahtar = _anahtar(eski)
        if anahtar:
            bilinen.add(anahtar)
    gorulen: set[str] = set()
    sonuc: list[str] = []
    for adres in adresler or []:
        anahtar = _anahtar(adres)
        if anahtar in bilinen and anahtar not in gorulen:
            gorulen.add(anahtar)
            sonuc.append(adres)
    return sonuc


def _domain_eslesir(host: str, domain: str) -> bool:
    """Bir host'un verilen alan adina ait olup olmadigini dogru sekilde soyler.

    Kural: `host == domain` (github.com == github.com) VEYA host bir alt alan
    adidir (api.github.com, www.github.com ... .github.com biter). `github.com`
    asla `evilgithub.com` ile eslesmez. www on eki iki tarafta da yok sayilir
    (yalniz on ek — `lstrip` gibi karakter kumesiyle oynamaz).
    """
    domain = (domain or "").strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if host.startswith("www."):
        host = host[4:]
    return bool(domain) and (host == domain or host.endswith("." + domain))


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
        if _domain_eslesir(host, site):
            return "video"
    return "http"


def filtrele(
    urller: list[str],
    sadece: set[str] | None = None,
    domain: str = "",
) -> list[str]:
    """Tur (sadece) ve alan adi (domain) filtrelerini uygular."""
    sonuc: list[str] = []
    dom = (domain or "").strip().lower()
    for url in urller:
        if sadece and tur_bul(url) not in sadece:
            continue
        if dom:
            host = _host(url)
            if not _domain_eslesir(host, dom):
                continue
        sonuc.append(url)
    return sonuc


# --- Panel filtreleme (TEK mantik) ----------------------------------------
def _joker_esles(metin: str, desen: str) -> bool:
    """Alt-metin + wildcard aramasi. Desende * ve ? varsa joker olarak
    arama regex'ine cevrilir (orn. `*.zip`, `dosya?.txt`) ve metnin HERHANGI
    bir yerinde eslesir; yoksa parca aramasi yapilir. Buyuk/kucuk harf
    duyarsizdir."""
    metin = (metin or "").casefold()
    desen = (desen or "").strip().casefold()
    if not desen:
        return True
    if "*" in desen or "?" in desen:
        rx = re.escape(desen).replace(r"\*", ".*").replace(r"\?", ".")
        return re.search(rx, metin) is not None
    return desen in metin


def ogeleri_filtrele(
    ogeler: list[dict],
    ara: str = "",
    sadece: set[str] | None = None,
    domain: str = "",
    min_boyut: int | None = None,
    max_boyut: int | None = None,
) -> list[int]:
    """Panelin TEK filtre mantigi. `ogeler`: {"url", "tur", "filename", "size"}
    sozlukleri. Alt-metin/wildcard arama, tur, domain (alt alan adi dahil) ve
    boyut araligi BIRLIKTE calisir; eslesenlerin orijinal INDEXLERI donulur.
    UI kurali kopyalamaz, yalnizca bu sonucu goruntuler.

    - ara: filename + url uzerinde `_joker_esles` (orn. `*.zip`)
    - sadece: tur seti; bos = tum turler
    - domain: `_domain_eslesir` (subdomain dahil, taklit haric)
    - min_boyut/max_boyut: bayt; boyutu bilinmeyen (size=None) ogeler boyut
      filtresi aktifken ELEMEZ (uyari: once probe).
    """
    eslesen: list[int] = []
    for i, o in enumerate(ogeler or []):
        if not isinstance(o, dict):
            continue
        url = (o.get("url") or "").strip()
        if not url:
            continue
        if sadece:
            tur = o.get("tur") or tur_bul(url)
            if tur not in sadece:
                continue
        if domain:
            if not _domain_eslesir(_host(url), domain):
                continue
        if min_boyut is not None or max_boyut is not None:
            boyut = o.get("size")
            if boyut is None:
                continue
            if min_boyut is not None and boyut < int(min_boyut):
                continue
            if max_boyut is not None and boyut > int(max_boyut):
                continue
        if str(ara or "").strip():
            hedef = f"{o.get('filename') or ''} {url}"
            if not _joker_esles(hedef, str(ara)):
                continue
        eslesen.append(i)
    return eslesen


def domainler(ogeler: list[dict]) -> list[str]:
    """Panelin domain acilir kutusu icin benzersiz host listesi (sirali)."""
    tum = {_host((o.get("url") or "").strip())
           for o in ogeler if isinstance(o, dict) and o.get("url")}
    return sorted(h for h in tum if h)


# --- Probe olcutleri -----------------------------------------------------
PROBE_MAKS_WORKER = 16  # eszamanli HEAD/Range sondajinin hard limiti


def probe_es_zamanli(
    urller: list[str],
    es_zamanli: int = 8,
    timeout: float = 3.0,
) -> dict[str, dict]:
    """Toplu lazy probe: her URL icin dosya adi/boyut/tip, eszamanliligi
    sinirli (ThreadPoolExecutor). Sonuc sozlugu: {url: probe_dict}.
    http/https olmayanlar (magnet, .torrent dosyasi) atlanmaz — probe_url_info
    onlar icin ok=False dondurur, panel \"bilgi yok\" gosterir.

    Hard limit: es_zamanli PROBE_MAKS_WORKER (16) ile sinirlanir; 0/negatif
    deger 1'e, metinsel deger varsayilana (8) iner.
    """
    try:
        cap = max(1, min(int(es_zamanli), PROBE_MAKS_WORKER))
    except (TypeError, ValueError):
        cap = 8
    sonuclar: dict[str, dict] = {}

    def _probe(url: str) -> tuple[str, dict]:
        try:
            return url, dosya_adi.probe_url_info(url, timeout=timeout)
        except Exception as exc:  # beklenmedik hata paneli kilitlemesin
            return url, {"ok": False, "error": str(exc)[:120]}

    with ThreadPoolExecutor(max_workers=cap) as havuz:
        gelecekler = {havuz.submit(_probe, u): u for u in urller}
        for gelecek in as_completed(gelecekler):
            url, sonuc = gelecek.result()
            sonuclar[url] = sonuc
    return sonuclar