"""v1.4 Foundation — ekleme istegi modeli (TEK KAYNAK).

`core/manager.Manager.add`, `app.bekleyen_onayla` ve HTTP `/add` eskiden ayri
ayri dict/flat-kwargs uretiyordu; hepsi artik `DownloadRequest` kurar. Boyut
sinirlari da burada TEK kez yasar (her cagirici kendi sinirini uretmez).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

SOURCE_MAX = 8192
TITLE_MAX = 200
USER_AGENT_MAX = 512
HEADER_COUNT_MAX = 40
PROXY_MAX = 1024

# v1.6 Video Pro — serbest metin alanlari icin makul ust sinirlar.
KUCUK_RESIM_SECENEKLERI = ("goem", "dosya")
BOLUMLER_SECENEKLERI = ("goem", "ayir")
KAPSAYICI_SECENEKLERI = ("mp4", "mkv", "webm")
SES_FORMATI_SECENEKLERI = ("mp3", "m4a", "aac", "opus", "flac", "wav")
TARAYICI_CEREZI_SECENEKLERI = (
    "chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi", "safari",
)
ALTYAZI_MAX = 200
SPONSORBLOCK_MAX = 200
BOLUM_ARALIGI_MAX = 64
KAPSAYICI_MAX = 32
SES_FORMATI_MAX = 32
DOSYA_SABLONU_MAX = 1000
TARAYICI_CEREZI_MAX = 128

# aria2'nin destekledigi checksum tipleri -> resmi yazimlar (daslarik isimler
# kullanici rahatligi icin eklendi). Yukarida bagli kalan tip ornegi VERILMEZ.
CHECKSUM_TURLERI = {
    "md5": "md5",
    "sha-1": "sha-1",
    "sha1": "sha-1",
    "sha-224": "sha-224",
    "sha-256": "sha-256",
    "sha256": "sha-256",
    "sha-384": "sha-384",
    "sha-512": "sha-512",
    "sha512": "sha-512",
}
_CHECKSUM_RE = re.compile(r"^([A-Za-z0-9-]+)[:=]([0-9a-fA-F]+)$")
_SPONSORBLOCK_RE = re.compile(r"^[A-Za-z0-9_]+(?:,[A-Za-z0-9_]+)*$")
_BOLUM_ARALIGI_RE = re.compile(
    r"^(?:\d{2}:\d{2}:\d{2}|\d{2}:\d{2})-(?:\d{2}:\d{2}:\d{2}|\d{2}:\d{2})$"
)


def parse_time_spec(s: object) -> float | None:
    """'23:30' / '2026-09-19 23:30' / '19.09.2026 23:30' / epoch-sayi -> epoch.

    - Yalniz saat:dakika verilirse, o an GECMISSE yarina planlar.
    - Sadece sayi gelirse epoch olarak kabul edilir (zaten epoch olanlar).
    - Anlasilamazsa ValueError (UI'a giden anlasilir Turkce mesaj).
    """
    s = str(s).strip()
    if not s:
        return None
    if s.isdigit():
        return float(s)
    now = time.time()
    for fmt, gecmise_erteler in (("%Y-%m-%d %H:%M", False),
                                 ("%d.%m.%Y %H:%M", False),
                                 ("%H:%M", True)):
        try:
            cal = time.strptime(s, fmt)
        except ValueError:
            continue
        if gecmise_erteler:
            bugun = time.localtime()
            cal = time.struct_time((
                bugun.tm_year, bugun.tm_mon, bugun.tm_mday,
                cal.tm_hour, cal.tm_min, cal.tm_sec, -1, -1, -1))
        t = time.mktime(cal)
        if gecmise_erteler and t <= now:
            t += 86400.0
        return t
    raise ValueError(
        f"zamanlama anlasilamadi: {s!r} ('23:30' veya 'YYYY-AA-GG SS:DD')")


def checksum_ayikla(check: object) -> str | None:
    """'sha-256:hex' / 'sha-256=hex' / 'md5:hex' → aria2 'TYPE=HEX'.

    Boss verevre None; gecersiz bicim/tip → ValueError (mesaj Turkce).
    Tiksinlen ama dogrulanması: hex gercektir; tip bilinmiyorsa aria2 hata
    verir, o yüzden bilinmeyen tip daha ekleme aninda elenir.
    """
    if check in (None, ""):
        return None
    ham = str(check).strip()
    m = _CHECKSUM_RE.match(ham)
    if not m:
        raise ValueError("checksum 'tip:hex' biciminde olmali (orn. sha-256:...)")
    tip = CHECKSUM_TURLERI.get(m.group(1).lower())
    if not tip:
        raise ValueError(
            "checksum tipi desteklenmiyor: %s (md5 | sha-1 | sha-256 | sha-512)"
            % m.group(1))
    return "%s=%s" % (tip, m.group(2).lower())


def _metin_al(data: Mapping[str, Any], anahtar: str, sinir: int) -> str:
    """Guvenilmeyen /add girdisinde serbest metin alani: bos -> '', fazlalik RED.

    Ayracli listeler (altyazi "tr,en"), adres/bezlestirici (sponsorblock,
    bolum araligi) ve sablon gibi alanlarda sessizce KESMEK anlami bozar;
    o yuzden proxy'deki usul gibi asiri uzun gelen istek RED edilir."""
    deger = data.get(anahtar)
    if deger in (None, ""):
        return ""
    if not isinstance(deger, str):
        raise ValueError(f"{anahtar} metin olmali")
    deger = " ".join(deger.split())
    if len(deger) > sinir:
        raise ValueError(f"{anahtar} cok uzun (>{sinir} karakter)")
    return deger


def _secim_al(data: Mapping[str, Any], anahtar: str,
              secenekler: tuple[str, ...], sinir: int | None = None) -> str:
    """Ikili secenek alanlari: bos -> '', bilinmeyen deger -> ValueError."""
    if sinir is not None:
        deger = _metin_al(data, anahtar, sinir)
        if not deger:
            return ""
    else:
        deger = data.get(anahtar)
    if deger in (None, ""):
        return ""
    if not isinstance(deger, str):
        raise ValueError(f"{anahtar} metin olmali")
    deger = deger.strip().lower()
    if deger not in secenekler:
        raise ValueError(
            f"{anahtar} su degerlerden biri olmali: {', '.join(secenekler)}"
        )
    return deger


def _desenli_metin_al(data: Mapping[str, Any], anahtar: str, sinir: int,
                       desen: re.Pattern[str], bicim: str) -> str:
    deger = _metin_al(data, anahtar, sinir)
    if deger and not desen.fullmatch(deger):
        raise ValueError(f"{anahtar} {bicim} biciminde olmali")
    return deger


@dataclass(slots=True)
class DownloadRequest:
    """Bir indirme isteginin tamamI: /add gövdesi ve manager.add'in girdisi.

    Alani guvenilmeyen girdiye karsi burada sinirlandiririz; `from_mapping`
    disaridan gelen flat dict'i kurallar.
    """
    source: str
    kind: str | None = None
    dest_dir: str | None = None
    quality: str | None = None
    audio_only: bool = False
    playlist: bool = False
    headers: dict[str, str] | None = None
    filename: str | None = None
    cookies: list | None = None
    user_agent: str | None = None
    title: str | None = None
    start_after: float | None = None
    proxy: str | None = None
    checksum: str | None = None
    # --- v1.6 Video Pro (tum varsayilanlar BOS/False; videoda islenir) ----
    altyazi_diller: str = ""
    oto_altyazi: bool = False
    altyazi_goem: bool = False
    kucuk_resim: str = ""
    ustveri_goem: bool = False
    bolumler: str = ""
    sponsorblock: str = ""
    bolum_araligi: str = ""
    kapsayici: str = ""
    ses_formati: str = ""
    dosya_sablonu: str = ""
    tarayici_cerezi: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DownloadRequest":
        kaynak = data.get("source") or data.get("url") or ""
        if not isinstance(kaynak, str):
            raise ValueError("bos link")
        kaynak = kaynak.strip()
        if not kaynak:
            raise ValueError("bos link")
        if len(kaynak) > SOURCE_MAX:
            raise ValueError(f"baglanti cok uzun (>{SOURCE_MAX})")

        basliklar = data.get("headers")
        if basliklar is None:
            basliklar = {}
        if not isinstance(basliklar, dict):
            raise ValueError("headers sozluk olmali")
        if len(basliklar) > HEADER_COUNT_MAX:
            raise ValueError(f"en fazla {HEADER_COUNT_MAX} ozel baslik")

        baslik_text = data.get("title")
        if isinstance(baslik_text, str):
            baslik_text = " ".join(baslik_text.split())[:TITLE_MAX]
        ua = data.get("user_agent")
        if isinstance(ua, str):
            ua = " ".join(ua.split())[:USER_AGENT_MAX]

        px = data.get("proxy")
        if px is not None and not isinstance(px, str):
            raise ValueError("proxy metin olmali")
        if isinstance(px, str):
            px = px.strip() or None
            if px and len(px) > PROXY_MAX:
                raise ValueError(f"proxy adresi cok uzun (> {PROXY_MAX})")

        checksum = checksum_ayikla(data.get("checksum"))

        start_after = data.get("start_after")
        if start_after is None and data.get("start_at") not in (None, ""):
            start_after = parse_time_spec(data["start_at"])

        # v1.6 Video Pro — dogrulama burada TEK kez yasar; /add ve CLI baska
        # sinir uretmez. Ikili secenekler gecersizse istek daha ekleme aninda
        # reddedilir (proxy/checksum'daki usul).
        kucuk_resim = _secim_al(data, "kucuk_resim", KUCUK_RESIM_SECENEKLERI)
        bolumler = _secim_al(data, "bolumler", BOLUMLER_SECENEKLERI)
        kapsayici = _secim_al(data, "kapsayici", KAPSAYICI_SECENEKLERI, KAPSAYICI_MAX)
        ses_formati = _secim_al(data, "ses_formati", SES_FORMATI_SECENEKLERI, SES_FORMATI_MAX)
        tarayici_cerezi = _secim_al(
            data, "tarayici_cerezi", TARAYICI_CEREZI_SECENEKLERI, TARAYICI_CEREZI_MAX)

        return cls(
            source=kaynak,
            kind=data.get("kind") or None,
            dest_dir=data.get("dest_dir"),
            quality=data.get("quality") or None,
            audio_only=bool(data.get("audio_only")),
            playlist=bool(data.get("playlist")),
            headers=dict(basliklar),
            filename=data.get("filename") or None,
            cookies=data.get("cookies"),
            user_agent=ua,
            title=baslik_text,
            start_after=start_after,
            proxy=px,
            checksum=checksum,
            altyazi_diller=_metin_al(data, "altyazi_diller", ALTYAZI_MAX),
            oto_altyazi=bool(data.get("oto_altyazi")),
            altyazi_goem=bool(data.get("altyazi_goem")),
            kucuk_resim=kucuk_resim,
            ustveri_goem=bool(data.get("ustveri_goem")),
            bolumler=bolumler,
            sponsorblock=_desenli_metin_al(
                data, "sponsorblock", SPONSORBLOCK_MAX, _SPONSORBLOCK_RE, "kategori listesi"),
            bolum_araligi=_desenli_metin_al(
                data, "bolum_araligi", BOLUM_ARALIGI_MAX, _BOLUM_ARALIGI_RE,
                "SS:DD:SS-SS:DD:SS veya DD:SS-DD:SS"),
            kapsayici=kapsayici,
            ses_formati=ses_formati,
            dosya_sablonu=_metin_al(data, "dosya_sablonu", DOSYA_SABLONU_MAX),
            tarayici_cerezi=tarayici_cerezi,
        )
