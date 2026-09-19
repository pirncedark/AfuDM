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
        )