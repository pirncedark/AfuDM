# -*- coding: utf-8 -*-
"""Makine-okur hata sozlesmesi (API error contract).

Sunucu hata yanitlari UC hep birlikte doner (geriye donuk uyumluluk icin):
    {"ok": false, "code": "RENEW_UNSUPPORTED", "message": "...", "error": "..."}
      code    — makine icin: CLI exit kodlarini belirler, scriptler eslesir
      message — insan icin: UI/gosterim
      error   — eskiden var olan alan; UI/mobil bunu okur, uyumluluk icin kalir

Kodlar:
    BAD_REQUEST       istek yapisi bozuk / deger gecersiz
    BAD_SOURCE        link desteklenmiyor (http(s)/ftp/magnet/.torrent degil)
    DUPLICATE         ayni kaynak kuyrukta zaten var
    KAYIT_YOK         gid / kayit bulunamadi
    RENEW_UNSUPPORTED islem bu is turunde kullanilamaz (torrent, magnet, video)
    ENGINE_ERROR      aria2/yt-dlp motor hatasi
    IO                dosya/disk hatasi
    INTERNAL          beklenmeyen hata
"""
from __future__ import annotations

import json


class AfuHata(Exception):
    """Sunucuya tasinan, `code` tasiyan hata. Layman ValueError yerine
    istemcinin makinece anlayabilecegi koduyla donar."""

    code = "INTERNAL"

    def __init__(self, mesaj: str = "", code: str | None = None) -> None:
        super().__init__(mesaj or self.code)
        if code:
            self.code = code

    def json(self) -> dict:
        mesaj = str(self)
        return {"ok": False, "code": self.code, "message": mesaj, "error": mesaj}


class BadRequest(AfuHata):
    code = "BAD_REQUEST"


class BadSource(BadRequest):
    code = "BAD_SOURCE"


class Duplicate(BadRequest):
    code = "DUPLICATE"


class KayitYok(BadRequest):
    code = "KAYIT_YOK"


class RenewDesteklenmez(BadRequest):
    code = "RENEW_UNSUPPORTED"


def hata_json(exc: BaseException) -> dict:
    """Herhangi bir istisnayi standart hata sozlesmesine cevirir.

    AfuHata kendi code'unu tasir; digerleri tipine gore eslenir. Hicbir yerde
    ham gövde/iz (stack) disariya sizmez, yalnizca mesaj kisa tutulur."""
    if isinstance(exc, AfuHata):
        return exc.json()
    if isinstance(exc, ValueError):
        return AfuHata(str(exc), code="BAD_REQUEST").json()
    if isinstance(exc, KeyError):
        return AfuHata(str(exc), code="BAD_REQUEST").json()
    if isinstance(exc, (OSError, PermissionError)):
        return AfuHata(str(exc), code="IO").json()
    # Aria2Error dahil her sey buraya: nedeni ayirt edilemiyorsa ENGINE de
    # olabilir, ama genel soy eslestirme INTERNAL ile kapanir.
    return AfuHata(str(exc)[:300], code="INTERNAL").json()


def kod_bul(govde: dict | None) -> str:
    """HTTP hata gövdesinden `code` alanini guvenle okur (yoksa boş)."""
    if isinstance(govde, dict):
        return str(govde.get("code") or govde.get("message") or "")
    return ""


def msg_bul(govde: dict | None) -> str:
    if isinstance(govde, dict):
        return str(govde.get("message") or govde.get("error") or "")
    return ""


def _kontrol() -> None:
    """Sozlesme tutarli mi? (tests/cli_surum_test.py cagirir)"""
    ornek = AfuHata("olen link", code="RENEW_UNSUPPORTED").json()
    assert ornek["code"] == "RENEW_UNSUPPORTED"
    assert ornek["message"] == "olen link"
    assert ornek["error"] == "olen link"
    assert json.dumps(ornek)  # serialize edilebilir
    assert hata_json(ValueError("x"))["code"] == "BAD_REQUEST"
    assert hata_json(OSError("x"))["code"] == "IO"
    assert RenewDesteklenmez().code == "RENEW_UNSUPPORTED"
    print("hata sozlesmesi tutarli: OK")


if __name__ == "__main__":
    _kontrol()