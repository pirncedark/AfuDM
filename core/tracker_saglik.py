"""Tracker saglik taramasi — olu listeleri ayiklar, canli olanlari one alir.

NEDEN: Kullanicinin listesinde 192 tracker vardi; OLCULDU (2026-09-18) 128 UDP
adresten yalnizca 31'i cevap verdi, 97'si olu ya da sessizdi. aria2 her duyuruda
bunlarin hepsini deniyor ve her biri icin zaman asimi bekliyor — duyuru bu yuzden
gec oturuyor.

NE YAPAR / NE YAPMAZ: Bu modul duyuruyu HIZLANDIRIR, seed SAYISINI ARTIRMAZ.
Ayni olcumde cevap veren 31 tracker'dan yalnizca 3'u o torrenti taniyordu ve
ucu de ayni 3 kisiyi gosteriyordu. Temiz liste var olani daha cabuk bulur,
yenisini yaratmaz.

Kullanim: kullanici `AfuDM/trackers/` klasorune istedigi kadar .txt atar;
`tara()` hepsini okur, her adrese GERCEKTEN sorar (UDP scrape / HTTP scrape) ve
canli olanlari dondurur. Bir info hash verilirse o torrenti TANIYAN tracker'lar
ayrica isaretlenir — seed tazelemede listenin basina onlar konur.

UDP protokolu (BEP 15): connect (action=0, magic 0x41727101980) -> scrape
(action=2, info_hash) -> seeders / completed / leechers.
"""
from __future__ import annotations

import concurrent.futures as cf
import random
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import paths, trackers

KLASOR = paths.BASE / "trackers"
MAGIC = 0x41727101980
ZAMAN_ASIMI = 4.0
ISCI = 40
# Tarama sonucu bu kadar sure taze sayilir (gunde bir yeter; tracker'lar
# saatlik degismez, her aciliste tarama bosuna ag trafigi olur).
TAZELIK = 24 * 3600


def klasoru_hazirla() -> None:
    """trackers/ klasoru + kullaniciya ne yapacagini anlatan kisa bir not."""
    try:
        KLASOR.mkdir(parents=True, exist_ok=True)
        okuma = KLASOR / "BENI_OKU.txt"
        if not okuma.exists():
            okuma.write_text(
                "Buraya istediğin kadar tracker listesi (.txt) atabilirsin.\n"
                "Her satırda bir adres olsun:\n"
                "    udp://tracker.ornek.org:1337/announce\n"
                "    http://izleyici.ornek.com/announce\n\n"
                "AfuDM bu klasördeki bütün dosyaları okur, tekrarları atar ve\n"
                "her adrese gerçekten sorar. Cevap vermeyen (ölü) tracker'lar\n"
                "kullanılmaz — ama silinmez, bir dahaki taramada yine denenir.\n\n"
                "Not: tracker eklemek seed SAYISINI artırmaz; var olan seed'leri\n"
                "daha hızlı bulmanı sağlar.\n",
                encoding="utf-8")
    except OSError:
        pass


def klasorden_oku() -> list[str]:
    """trackers/ altindaki butun .txt dosyalarini birlestir (tekrarsiz)."""
    if not KLASOR.is_dir():
        return []
    toplam: list[str] = []
    for dosya in sorted(KLASOR.glob("*.txt")):
        if dosya.name == "BENI_OKU.txt":
            continue
        try:
            metin = dosya.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for adres in trackers.ayikla(metin):
            if adres not in toplam:
                toplam.append(adres)
    return toplam


def dosyalar() -> list[dict]:
    """Klasordeki seed listelerini ve her birindeki gecerli adres sayisini don.

    Ayarlar'daki "Seed listeleri" bolumu bunu gosterir. BENI_OKU.txt aciklama
    dosyasidir, listede yer almaz.
    """
    klasoru_hazirla()
    liste: list[dict] = []
    for dosya in sorted(KLASOR.glob("*.txt")):
        if dosya.name == "BENI_OKU.txt":
            continue
        try:
            metin = dosya.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        liste.append({"ad": dosya.name, "sayi": len(trackers.ayikla(metin))})
    return liste


def _bos_ad(ad: str) -> Path:
    """Cakisan adi seed.txt -> seed-2.txt -> seed-3.txt diye kaydir."""
    hedef = KLASOR / ad
    if not hedef.exists():
        return hedef
    govde, _, uzanti = ad.rpartition(".")
    for sira in range(2, 1000):
        aday = KLASOR / f"{govde}-{sira}.{uzanti}"
        if not aday.exists():
            return aday
    raise ValueError("cok fazla ayni adli liste var")


def dosya_ekle(yol: str) -> dict:
    """Kullanicinin sectigi .txt'yi trackers/ klasorune KOPYALAR.

    Kaynak dosyaya dokunulmaz. Icerik ayiklanarak yazilir: her satirda bir
    adres, tekrarlar ve tracker olmayan satirlar dusurulur. Ayni adres kumesi
    zaten varsa ikinci kopya olusturulmaz ({"zaten": True} doner).
    """
    kaynak = Path(yol)
    if kaynak.suffix.lower() != ".txt":
        raise ValueError("yalniz .txt liste dosyasi eklenebilir")
    if not kaynak.is_file():
        raise ValueError("dosya bulunamadi")
    try:
        metin = kaynak.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"dosya okunamadi: {exc}") from exc
    adresler = trackers.ayikla(metin)
    if not adresler:
        raise ValueError("dosyada tracker adresi yok")

    klasoru_hazirla()
    yeni = set(adresler)
    for var_olan in KLASOR.glob("*.txt"):
        if var_olan.name == "BENI_OKU.txt":
            continue
        try:
            eski = var_olan.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if set(trackers.ayikla(eski)) == yeni:
            return {"ad": var_olan.name, "sayi": len(adresler), "zaten": True}

    hedef = _bos_ad(kaynak.name)
    try:
        hedef.write_text("\n".join(adresler) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"dosya yazilamadi: {exc}") from exc
    return {"ad": hedef.name, "sayi": len(adresler), "zaten": False}


def dosya_sil(ad: str) -> dict:
    """Klasordeki bir seed listesini sil. Yalniz klasorun ICINDEKI .txt'ler.

    Ad arayuzden geldigi icin yol kacisina (`../`, mutlak yol) izin verilmez.
    """
    if not ad or ad != Path(ad).name or ad.lower().endswith(".exe"):
        raise ValueError("gecersiz dosya adi")
    if not ad.lower().endswith(".txt"):
        raise ValueError("yalniz .txt liste dosyasi silinebilir")
    if ad == "BENI_OKU.txt":
        raise ValueError("aciklama dosyasi silinemez")
    hedef = KLASOR / ad
    if not hedef.is_file():
        raise ValueError("dosya bulunamadi")
    try:
        hedef.unlink()
    except OSError as exc:
        raise ValueError(f"dosya silinemedi: {exc}") from exc
    return {"ad": ad}


def _udp_scrape(adres: str, info_hash: str) -> tuple[str, int, int]:
    ayrik = urllib.parse.urlparse(adres)
    if not ayrik.hostname or not ayrik.port:
        return ("hata", 0, 0)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(ZAMAN_ASIMI)
    try:
        islem = random.randint(0, 2 ** 31 - 1)
        s.sendto(struct.pack(">QII", MAGIC, 0, islem), (ayrik.hostname, ayrik.port))
        veri, _ = s.recvfrom(64)
        if len(veri) < 16:
            return ("hata", 0, 0)
        eylem, donen, baglanti = struct.unpack(">IIQ", veri[:16])
        if eylem != 0 or donen != islem:
            return ("hata", 0, 0)
        if not info_hash:
            return ("canli", 0, 0)          # yalniz ayakta mi diye bakiyorduk
        islem2 = random.randint(0, 2 ** 31 - 1)
        s.sendto(struct.pack(">QII", baglanti, 2, islem2) + bytes.fromhex(info_hash),
                 (ayrik.hostname, ayrik.port))
        veri2, _ = s.recvfrom(256)
        if len(veri2) < 20:
            return ("canli", 0, 0)
        eylem2, _, seed, _tam, leech = struct.unpack(">IIIII", veri2[:20])
        if eylem2 != 2:
            return ("canli", 0, 0)
        return ("canli", seed, leech)
    except socket.timeout:
        return ("sessiz", 0, 0)
    except (OSError, ValueError):
        return ("hata", 0, 0)
    finally:
        s.close()


def _http_scrape(adres: str, info_hash: str) -> tuple[str, int, int]:
    """HTTP tracker: /announce -> /scrape. Cevabi bencode; yalniz ayakta mi ve
    (varsa) kac seed dedigi okunur — tam bencode cozucu gerekmez."""
    hedef = adres.replace("/announce", "/scrape")
    if info_hash:
        try:
            ham = urllib.parse.quote(bytes.fromhex(info_hash))
        except ValueError:
            ham = ""
        hedef += ("&" if "?" in hedef else "?") + "info_hash=" + ham
    try:
        istek = urllib.request.Request(hedef, headers={"User-Agent": "AfuDM/1.2"})
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
            govde = yanit.read(4096)
    except (urllib.error.URLError, OSError, ValueError):
        return ("sessiz", 0, 0)
    seed = leech = 0
    for anahtar, ad in ((b"completei", "seed"), (b"incompletei", "leech")):
        yer = govde.find(anahtar)
        if yer >= 0:
            son = govde.find(b"e", yer + len(anahtar))
            try:
                deger = int(govde[yer + len(anahtar):son])
            except ValueError:
                deger = 0
            if ad == "seed":
                seed = deger
            else:
                leech = deger
    return ("canli", seed, leech)


def sor(adres: str, info_hash: str = "") -> tuple[str, int, int]:
    """Tek bir tracker'a sor: ("canli"|"sessiz"|"hata", seed, leech)."""
    if adres.startswith("udp://"):
        return _udp_scrape(adres, info_hash)
    if adres.startswith(("http://", "https://")):
        return _http_scrape(adres, info_hash)
    return ("hata", 0, 0)


def tara(liste: list[str], info_hash: str = "", isci: int = ISCI) -> dict:
    """Butun listeyi paralel sorgula ve ozetle.

    Donen: {"canli": [...], "olu": [...], "tanyan": [(adres, seed, leech)...],
            "sayilar": {...}, "zaman": epoch}
    """
    canli: list[str] = []
    olu: list[str] = []
    tanyan: list[tuple[str, int, int]] = []
    if not liste:
        return {"canli": [], "olu": [], "tanyan": [], "zaman": time.time(),
                "sayilar": {"toplam": 0, "canli": 0, "olu": 0, "tanyan": 0}}

    with cf.ThreadPoolExecutor(max_workers=max(1, isci)) as havuz:
        for adres, sonuc in zip(liste, havuz.map(lambda a: sor(a, info_hash), liste)):
            durum, seed, leech = sonuc
            if durum == "canli":
                canli.append(adres)
                if seed or leech:
                    tanyan.append((adres, seed, leech))
            else:
                olu.append(adres)
    # Torrenti TANIYANLAR en basa: aria2 listeyi sirayla duyurur
    tanyan.sort(key=lambda x: (-x[1], -x[2]))
    onde = [t[0] for t in tanyan]
    sirali = onde + [a for a in canli if a not in onde]
    return {
        "canli": sirali,
        "olu": olu,
        "tanyan": tanyan,
        "zaman": time.time(),
        "sayilar": {"toplam": len(liste), "canli": len(canli),
                    "olu": len(olu), "tanyan": len(tanyan)},
    }


def tazele(store, info_hash: str = "") -> dict:
    """Klasoru oku, tara, sonucu ayara yaz. Arayuz/zamanlayici bunu cagirir."""
    klasoru_hazirla()
    liste = klasorden_oku()
    # Kullanicinin arayuzden elle ekledikleri de taramaya girsin
    elle = trackers.ayikla(str(store.get("ek_trackerlar", "")))
    for adres in elle:
        if adres not in liste:
            liste.append(adres)
    sonuc = tara(liste, info_hash)
    store.set("canli_trackerlar", "\n".join(sonuc["canli"]))
    store.set("tracker_tarama_zamani", sonuc["zaman"])
    store.set("tracker_tarama_ozeti", sonuc["sayilar"])
    store.log("info",
              f"tracker taramasi: {sonuc['sayilar']['canli']}/{sonuc['sayilar']['toplam']} canli, "
              f"{sonuc['sayilar']['tanyan']} tanesi torrenti taniyor")
    return sonuc


def taze_mi(store) -> bool:
    try:
        return (time.time() - float(store.get("tracker_tarama_zamani", 0) or 0)) < TAZELIK
    except (TypeError, ValueError):
        return False
