"""Eklenti host sureci — AfuDM'in ANA SURECINDEN AYRI calisir.

Neden ayri surec: bir eklenti sonsuz donguye girse, bellek yakip cokse veya
yorumlayiciyi oldurse bile ANA UYGULAMA ETKILENMEZ. Ana surec bu sureci
oldurur, hatayi kaydeder ve kullaniciya "Yeniden baslat" dugmesini gosterir.

DURUSTLUK NOTU (cok onemli):
    Bu ayri surec bir SANDBOX DEGILDIR. Eklenti kodu AfuDM'i calistiran
    kullanicinin tum yetkileriyle calisir: diski okuyabilir/yazabilir, aga
    cikabilir. Manifestteki "izinler" ve "domainler" alanlari yalnizca
    BEYANDIR — burada teknik olarak ZORLANMAZ. Saglanan sey COKME ve
    TAKILMA izolasyonudur, guvenlik izolasyonu degil.

Protokol: stdin/stdout uzerinde satir basina bir JSON.
    istek  -> {"id": 1, "eylem": "ping|baslat|olay|ayar|durdur", "veri": {...}}
    yanit  -> {"id": 1, "ok": true, "sonuc": ...}
              {"id": 1, "ok": false, "hata": "..."}

Eklentinin giris dosyasinda BULUNABILECEK (hepsi istege bagli) adlar:
    baslat(ctx)            -> kurulum/abonelik
    olay(ad, veri)         -> AfuDM'den gelen olay
    ayar_degisti(ayarlar)  -> kullanici ayar kaydetti
    durdur()               -> temiz kapanis
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback


class Baglam:
    """Eklentiye verilen baglam. Yetki VERMEZ, yalniz bilgi tasir."""

    def __init__(self, veri: dict) -> None:
        self.ad = str(veri.get("ad") or "")
        self.surum = str(veri.get("surum") or "")
        self.afudm_surum = str(veri.get("afudm_surum") or "")
        self.klasor = str(veri.get("klasor") or "")
        self.ayarlar = dict(veri.get("ayarlar") or {})
        # Beyan edilen izin/domain listesi — ZORLANMAZ, bilgi amaclidir.
        self.izinler = list(veri.get("izinler") or [])
        self.domainler = list(veri.get("domainler") or [])

    def log(self, mesaj: str) -> None:
        """Eklenti gunlugu. stderr'e gider; ana surec bunu UI'da gosterir."""
        sys.stderr.write(f"{mesaj}\n")
        sys.stderr.flush()


def _yukle(klasor: str, giris: str):
    yol = os.path.join(klasor, giris)
    if not os.path.isfile(yol):
        raise FileNotFoundError(f"giris dosyasi yok: {giris}")
    ad = "afudm_eklenti_" + os.path.splitext(os.path.basename(giris))[0]
    spec = importlib.util.spec_from_file_location(ad, yol)
    if spec is None or spec.loader is None:
        raise ImportError(f"giris dosyasi yuklenemedi: {giris}")
    modul = importlib.util.module_from_spec(spec)
    # Eklenti kendi klasorundeki yardimci dosyalari import edebilsin
    if klasor not in sys.path:
        sys.path.insert(0, klasor)
    spec.loader.exec_module(modul)
    return modul


def main() -> int:
    # Eklentinin print() cagrisi protokolu BOZMASIN: 1 numarali betimleyiciyi
    # kopyalayip protokole ayiriyoruz, stdout'u stderr'e yonlendiriyoruz.
    try:
        kanal = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
        os.dup2(2, 1)
        sys.stdout = sys.stderr
    except OSError:
        kanal = sys.stdout

    def yaz(govde: dict) -> None:
        kanal.write(json.dumps(govde, ensure_ascii=False) + "\n")
        kanal.flush()

    ilk = sys.stdin.readline()
    if not ilk.strip():
        return 2
    try:
        yapilandirma = json.loads(ilk)
    except ValueError:
        return 2

    baglam = Baglam(yapilandirma)
    modul = None
    yaz({"id": 0, "ok": True, "sonuc": {"hazir": True, "pid": os.getpid()}})

    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        try:
            istek = json.loads(satir)
        except ValueError:
            continue
        kimlik = istek.get("id", 0)
        eylem = str(istek.get("eylem") or "")
        veri = istek.get("veri") or {}
        try:
            if eylem == "ping":
                yaz({"id": kimlik, "ok": True, "sonuc": {"pong": True}})
            elif eylem == "baslat":
                modul = _yukle(baglam.klasor, str(yapilandirma.get("giris") or ""))
                islev = getattr(modul, "baslat", None)
                sonuc = islev(baglam) if callable(islev) else None
                yaz({"id": kimlik, "ok": True,
                     "sonuc": {"baslatildi": True, "donus": _guvenli(sonuc)}})
            elif eylem == "olay":
                islev = getattr(modul, "olay", None) if modul else None
                sonuc = islev(str(veri.get("ad") or ""), veri.get("veri")) if callable(islev) else None
                yaz({"id": kimlik, "ok": True, "sonuc": _guvenli(sonuc)})
            elif eylem == "ayar":
                baglam.ayarlar = dict(veri.get("ayarlar") or {})
                islev = getattr(modul, "ayar_degisti", None) if modul else None
                if callable(islev):
                    islev(dict(baglam.ayarlar))
                yaz({"id": kimlik, "ok": True, "sonuc": {"uygulandi": True}})
            elif eylem == "durdur":
                islev = getattr(modul, "durdur", None) if modul else None
                if callable(islev):
                    islev()
                yaz({"id": kimlik, "ok": True, "sonuc": {"durduruldu": True}})
                break
            else:
                yaz({"id": kimlik, "ok": False, "hata": f"bilinmeyen eylem: {eylem}"})
        except Exception as exc:  # eklenti hatasi HOST'u dusurmez
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            yaz({"id": kimlik, "ok": False,
                 "hata": f"{type(exc).__name__}: {exc}"[:500]})
    return 0


def _guvenli(deger):
    """Eklenti donusu JSON'a cevrilemiyorsa metne dusur — protokol kirilmasin."""
    try:
        json.dumps(deger)
        return deger
    except (TypeError, ValueError):
        return str(deger)[:500]


if __name__ == "__main__":
    sys.exit(main())
