# -*- coding: utf-8 -*-
"""Tracker saglik taramasi testleri — AG GEREKTIRMEZ (sorgu taklit edilir).

NEDEN BU MODUL VAR (olculdu 2026-09-18/19): kullanicinin 192 adreslik
listesinde 151 tracker olu ya da sessizdi. aria2 her duyuruda hepsini deniyor
ve her biri icin zaman asimi bekliyordu. Tarama olulari eler, torrenti
TANIYANLARI listenin basina koyar.

DURUSTLUK NOTU: bu ozellik duyuruyu hizlandirir, seed SAYISINI ARTIRMAZ —
ayni olcumde cevap veren 41 tracker'dan yalnizca 4'u torrenti taniyordu ve
hepsi ayni birkac kisiyi gosteriyordu.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import tracker_saglik as ts  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


class SahteStore:
    """Ayar deposu taklidi — gercek veritabanina dokunmaz."""

    def __init__(self):
        self.veri = {}
        self.gunluk = []

    def get(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def set(self, anahtar, deger):
        self.veri[anahtar] = deger

    def log(self, seviye, mesaj):
        self.gunluk.append((seviye, mesaj))


# Sorguyu taklit et: ag YOK. Adrese gore sabit cevap.
CEVAPLAR = {
    "udp://canli1.ornek:1337/announce": ("canli", 5, 2),     # torrenti TANIYOR
    "udp://canli2.ornek:1337/announce": ("canli", 0, 0),     # ayakta ama tanimiyor
    "http://canli3.ornek/announce": ("canli", 12, 3),        # en cok seed
    "udp://olu1.ornek:6969/announce": ("sessiz", 0, 0),
    "udp://olu2.ornek:6969/announce": ("hata", 0, 0),
}
ts.sor = lambda adres, info_hash="": CEVAPLAR.get(adres, ("sessiz", 0, 0))

print("1) Klasorden okuma")
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    ts.KLASOR = Path(gecici) / "trackers"
    ts.klasoru_hazirla()
    check("klasor olusuyor", ts.KLASOR.is_dir())
    check("aciklama dosyasi yaziliyor", (ts.KLASOR / "BENI_OKU.txt").is_file())

    (ts.KLASOR / "a.txt").write_text(
        "udp://canli1.ornek:1337/announce\nudp://olu1.ornek:6969/announce\n"
        "bu bir adres degil\n", encoding="utf-8")
    (ts.KLASOR / "b.txt").write_text(
        "http://canli3.ornek/announce\nudp://canli1.ornek:1337/announce\n",  # tekrar
        encoding="utf-8")
    liste = ts.klasorden_oku()
    check("iki dosya birlestirildi", len(liste) == 3, str(liste))
    check("tekrar eden adres bir kez", liste.count("udp://canli1.ornek:1337/announce") == 1)
    check("gecersiz satir atildi", not any("adres degil" in a for a in liste))
    check("BENI_OKU okunmadi", not any("Buraya" in a for a in liste))

    print("2) Tarama: olu eleme + oncelik")
    sonuc = ts.tara(list(CEVAPLAR), info_hash="ab" * 20)
    s = sonuc["sayilar"]
    check("toplam dogru", s["toplam"] == 5, str(s))
    check("canli sayisi dogru", s["canli"] == 3, str(s))
    check("olu sayisi dogru", s["olu"] == 2, str(s))
    check("torrenti taniyan sayisi", s["tanyan"] == 2, str(s))
    check("olu adresler canli listede YOK",
          not any("olu" in a for a in sonuc["canli"]), str(sonuc["canli"]))
    check("EN COK seed bildiren en basta",
          sonuc["canli"][0] == "http://canli3.ornek/announce", sonuc["canli"][0])
    check("tanimayan canli tracker listede ama SONDA",
          "udp://canli2.ornek:1337/announce" in sonuc["canli"][2:], str(sonuc["canli"]))

    print("3) Ayara yazma (tazele)")
    store = SahteStore()
    store.set("ek_trackerlar", "udp://canli2.ornek:1337/announce")
    sonuc2 = ts.tazele(store, info_hash="ab" * 20)
    yazilan = store.get("canli_trackerlar", "").splitlines()
    check("canli liste ayara yazildi", len(yazilan) == sonuc2["sayilar"]["canli"], str(yazilan))
    check("elle eklenen de taramaya girdi",
          "udp://canli2.ornek:1337/announce" in yazilan)
    check("tarama zamani kaydedildi", float(store.get("tracker_tarama_zamani", 0)) > 0)
    check("ozet kaydedildi", store.get("tracker_tarama_ozeti", {}).get("toplam", 0) > 0)
    check("gunluge yazildi", any("tracker taramasi" in m for _, m in store.gunluk))

    print("4) Tazelik penceresi")
    check("taze sayiliyor", ts.taze_mi(store) is True)
    store.set("tracker_tarama_zamani", time.time() - ts.TAZELIK - 10)
    check("suresi gecince bayat", ts.taze_mi(store) is False)
    store.set("tracker_tarama_zamani", "bozuk deger")
    check("bozuk deger cokmeye yol acmiyor", ts.taze_mi(store) is False)

    print("5) Bos liste")
    bos = ts.tara([])
    check("bos listede cokmuyor", bos["sayilar"]["toplam"] == 0)
    check("bos listede canli yok", bos["canli"] == [])

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
