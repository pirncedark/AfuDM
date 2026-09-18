# -*- coding: utf-8 -*-
"""Seed / tracker tazeleme testleri — AG GEREKTIRMEZ, saniyeler surer.

OLCULEN GERCEKLER (2026-09-18, ayri bir aria2 ornegiyle):
 1. `aria2.changeOption(gid, {"bt-tracker": ...})` "OK" doner ama torrentin
    duyuru listesi DEGISMEZ — calisan torrente tracker EKLENEMIYOR.
 2. Torrenti kaldirip AYNI dizine yeniden eklemek ISE YARIYOR: 15.5 MB inmis
    is, yeniden eklendikten sonra 26 MB'dan devam etti ve tracker 2 -> 3 oldu.
Bu yuzden `Manager.seed_tazele` kaldir+yeniden ekle yolunu kullanir. Burada
o yolun DOSYAYA DOKUNMADIGI ve kullanicinin elle ekledigi tracker'larin
listeye ONDE girdigi dogrulanir.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import trackers  # noqa: E402
from core.db import Store  # noqa: E402
from core.manager import Manager  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


HASH = "08ada5a7a6183aae1e09d831df6748d566095a10"
KENDI = "udp://benim-tracker.ornek.org:1337/announce"


class SahteRPC:
    """aria2 taklidi: hangi cagrilarin yapildigini kaydeder."""

    def __init__(self, dizin: str):
        self.dizin = dizin
        self.cagrilar: list[tuple] = []
        self.global_ayar: dict = {"bt-tracker": "", "enable-dht": "true"}
        self.eklenen: list[tuple] = []

    def tell_status(self, gid, keys=None):
        self.cagrilar.append(("tell_status", gid))
        return {"gid": gid, "status": "active", "infoHash": HASH, "dir": self.dizin,
                "numSeeders": "2", "connections": "6", "completedLength": "500",
                "totalLength": "1000",
                "bittorrent": {"announceList": [["udp://a/announce"], ["udp://b/announce"]]}}

    def change_global_option(self, secenekler):
        self.global_ayar.update(secenekler)
        self.cagrilar.append(("change_global_option", secenekler))
        return "OK"

    def get_global_option(self):
        return dict(self.global_ayar)

    def pause(self, gid, force=False):
        self.cagrilar.append(("pause", gid))
        return "OK"

    def remove(self, gid, force=False):
        self.cagrilar.append(("remove", gid))
        return "OK"

    def remove_result(self, gid):
        self.cagrilar.append(("remove_result", gid))
        return "OK"

    def add_uri(self, uris, options=None):
        self.eklenen.append((uris, options or {}))
        return "yeni-gid"

    def add_torrent(self, b64, options=None):
        self.eklenen.append((["<torrent>"], options or {}))
        return "yeni-gid-torrent"

    def tell_active(self, *a, **k):
        return []

    def tell_waiting(self, *a, **k):
        return []

    def tell_stopped(self, *a, **k):
        return []


def yonetici(tmp: Path, rpc) -> Manager:
    tmp.mkdir(parents=True, exist_ok=True)
    m = Manager.__new__(Manager)
    m.store = Store(str(tmp / "seed.db"))
    m.rpc = rpc
    m.video_jobs = {}
    m._video_seq = 0
    m._lock = threading.RLock()
    m._known_complete = set()
    m._cerezler = {}
    m.last_error = ""
    return m


print("1) Elle eklenen tracker'lari ayiklama")
ham = f"""{KENDI}
  http://izleyici.ornek.com/announce , {KENDI}
bu bir tracker degil
magnet:?xt=urn:btih:{HASH}"""
cikan = trackers.ayikla(ham)
check("gecerli iki adres alindi", cikan == [KENDI, "http://izleyici.ornek.com/announce"], str(cikan))
check("mukerrer adres bir kez giriyor", cikan.count(KENDI) == 1)
check("tracker olmayan satir dusuruldu", not any("magnet" in a for a in cikan))
check("bos metin bos liste", trackers.ayikla("") == [])

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    tmp = Path(gecici)

    print("2) Elle eklenenler listenin BASINA giriyor")
    rpc = SahteRPC(str(tmp))
    sayi = trackers.apply_to_aria2(rpc, force=False, ek=KENDI)
    uygulanan = rpc.global_ayar["bt-tracker"].split(",")
    check("aria2'ye yazildi", sayi >= 1, f"{sayi} tracker")
    check("elle eklenen EN BASTA", uygulanan[0] == KENDI, uygulanan[0])

    print("3) seed_bilgi: pencerenin gosterdigi degerler")
    m = yonetici(tmp / "a", SahteRPC(str(tmp)))
    m.store.set("ek_trackerlar", KENDI)
    bilgi = m.seed_bilgi("gid1")
    check("seed sayisi geliyor", bilgi["seed"] == 2, str(bilgi.get("seed")))
    check("baglanti sayisi geliyor", bilgi["baglanti"] == 6)
    check("torrentin tracker sayisi", bilgi["tracker"] == 2)
    check("elle eklenenin sayisi", bilgi["ek_sayisi"] == 1)
    check("DHT durumu okunuyor", bilgi["dht"] is True)

    print("4) seed_tazele: DOSYAYA DOKUNMADAN yeniden duyurma")
    rpc = SahteRPC(str(tmp))
    m = yonetici(tmp / "b", rpc)
    m.store.set("ek_trackerlar", KENDI)
    kimlik = m.store.add("torrent", f"magnet:?xt=urn:btih:{HASH}", title="Dene", gid="eski-gid")
    m.store.update_by_id(kimlik, status="active")
    sonuc = m.seed_tazele("eski-gid")
    yapilan = [c[0] for c in rpc.cagrilar]
    check("islem basarili", sonuc.get("ok") is True, str(sonuc)[:120])
    check("once duraklatildi", "pause" in yapilan)
    check("motordan cikarildi", "remove" in yapilan)
    check("yeniden eklendi", len(rpc.eklenen) == 1)
    check("AYNI dizine eklendi", rpc.eklenen[0][1].get("dir") == str(tmp))
    # En kritigi: hicbir dosya silme cagrisi YOK (indirilen parcalar duruyor)
    check("dosya silme cagrisi YOK", not any("delete" in c[0] or "purge" in c[0] for c in rpc.cagrilar))
    check("kayit yeni GID'e baglandi", m.store.by_id(kimlik)["gid"] == "yeni-gid")
    check("elle eklenen tracker yine listede",
          rpc.global_ayar["bt-tracker"].split(",")[0] == KENDI)

    print("5) Torrent olmayan is tazelenemez")
    class TorrentDegil(SahteRPC):
        def tell_status(self, gid, keys=None):
            return {"gid": gid, "status": "active", "infoHash": "", "dir": self.dizin}

    m2 = yonetici(tmp / "c", TorrentDegil(str(tmp)))
    sonuc = m2.seed_tazele("http-gid")
    check("hata donuyor", sonuc.get("ok") is False, str(sonuc)[:80])

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
