# -*- coding: utf-8 -*-
"""Sahte HTTP sunucusu — gercek ag yok, davranislar TEKRARLANABILIR.

Foundation v1.4 test altyapisi. Range/206 resume, 401/403, 302 redirect,
baglanti kesme (drop) ve checksum senaryolarini gercek bir sunucuya ihtiyac
olmadan dogrular. Ileride proxy (Network Core) ve aria2 entegrasyon
testlerinin temeli olur.

Kullanim:
    ayarlar = SunucuAyarlari(veri=..., temel_auth=("k", "s"))
    ayarlar, port = fake_http.baslat(ayarlar)
    # urllib/aria2 bu porta istek atar
    ayarlar.durdur()
"""
from __future__ import annotations

import base64
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class SunucuAyarlari:
    veri: bytes = b""
    temel_auth: tuple[str, str] | None = None  # (kullanici, sifre) -> 401
    zorunlu_cerez: str | None = None            # Cookie basligi birebir eslesmeli
    yasakli: bool = False                      # -> 403
    yonlendir: str | None = None               # -> 302 Location
    drop_sonrasi_bayt: int | None = None       # N bayt sonra baglantiyi kes
    log: list[dict[str, Any]] = field(default_factory=list)  # gelen istekler
    gecikme_sn: float = 0.0                    # her istege verilen gecikme


def rastgele_bytes(n: int = 200_000, tohum: int = 42) -> bytes:
    """Deterministik test verisi: ayni tohum ayni icerik (checksum egrisi)."""
    import hashlib
    c = ""
    i = 0
    while len(c) < n * 2:  # her byte icin ~2 hex char
        i += 1
        c += hashlib.sha256(f"{tohum}:{i}".encode()).hexdigest()
    return (c[: n * 2]).encode("ascii")[: n * 2 // 2]


class _FakeHandler(BaseHTTPRequestHandler):
    ayarlar: SunucuAyarlari | None = None

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _kisa(self, durum: int, govde: bytes, ekstra: dict[str, str]) -> None:
        self.send_response(durum)
        self.send_header("Content-Length", str(len(govde)))
        for k, v in ekstra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self) -> None:  # noqa: N802
        ay = self.__class__.ayarlar
        if ay is None:
            self._kisa(500, b"ayar yok", {})
            return
        if ay.gecikme_sn > 0:
            import time
            time.sleep(ay.gecikme_sn)
        ay.log.append({"path": self.path, "headers": dict(self.headers)})

        if ay.yasakli:
            self._kisa(403, b"yasak", {})
            return

        if ay.temel_auth:
            beklenen = "Basic " + base64.b64encode(
                f"{ay.temel_auth[0]}:{ay.temel_auth[1]}".encode()).decode()
            if self.headers.get("Authorization") != beklenen:
                self._kisa(401, b"", {"WWW-Authenticate": 'Basic realm="fake"'})
                return

        if ay.zorunlu_cerez and ay.zorunlu_cerez not in self.headers.get("Cookie", ""):
            self._kisa(403, b"cookie gerekli", {})
            return

        if ay.yonlendir and self.path != ay.yonlendir:
            self._kisa(302, b"", {"Location": ay.yonlendir})
            return

        veri = ay.veri
        toplam = len(veri)
        rng = self.headers.get("Range", "")
        durum = 200
        bas = 0
        bit = toplam - 1
        ekstra: dict[str, str] = {"Accept-Ranges": "bytes"}
        if rng.startswith("bytes="):
            try:
                parc = rng[6:].split(",")[0].split("-")
                bas = int(parc[0]) if parc[0] else bas
                bit = int(parc[1]) if len(parc) > 1 and parc[1] else bit
                bit = min(bit, toplam - 1)
                durum = 206
                ekstra["Content-Range"] = f"bytes {bas}-{bit}/{toplam}"
            except ValueError:
                durum = 416
                ekstra["Content-Range"] = f"bytes */{toplam}"

        if durum == 416:
            self._kisa(416, b"", ekstra)
            return

        govde = veri[bas:bit + 1]

        if ay.drop_sonrasi_bayt is not None and not rng.startswith("bytes="):
            # ISTEMCIYE gercek Content-Length (tam boy) ver ama yarida kes.
            # Range (resume) istekleri ETKILENMEZ: gercek dunyada kesilme bir
            # kez olur, istemci .aria2 ile devam ederken 206 alir.
            self.send_response(durum)
            self.send_header("Content-Length", str(len(govde)))
            for k, v in ekstra.items():
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(govde[: ay.drop_sonrasi_bayt])
                self.wfile.flush()
            except OSError:
                pass
            self.connection.close()  # baglanti kes — istemci IncompleteRead
            return

        self._kisa(durum, govde, ekstra)


def baslat(ayarlar: SunucuAyarlari) -> tuple[int, ThreadingHTTPServer]:
    """Sunucuyu 127.0.0.1 uzerinde baslatir; (port, httpd) dondurur.

    Her cagriya AYRI bir handler sinifi turer: birden cok sunucu AYNI ANDA
    calisabilir (paralel firebase testleri), sinif-attir olan ayarlar iki
    sunucu arasinda karismaz.
    """
    class _TekHandler(_FakeHandler):  # type: ignore[misc]
        pass

    _TekHandler.ayarlar = ayarlar
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _TekHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_port, httpd
