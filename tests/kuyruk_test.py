"""Kuyruk kimligi testleri — "zaten kuyrukta" yanilgisi ve magnet GID kaymasi.

AG GEREKTIRMEZ, saniyeler surer. Iki gercek kusuru kapsar:

1. Uygulama beklenmedik kapaninca (ya da aria2 oturumu silinince) veritabaninda
   "active" duran ama motorda KARSILIGI OLMAYAN kayit kaliyordu. Ayni magnet
   yeniden eklenince "bu torrent zaten kuyrukta" deniyor, listede de
   gorunmedigi icin kullanici torrentin hic calismadigini saniyordu.
2. Yeniden baslatmada aria2 magneti oturumdan yeniden okur ve GID'i DEGISIR;
   veritabanindaki kayit sahipsiz kalir (bitince "tamamlandi" yazilmaz).

Ayrica motor CEVAP VERMEZKEN hicbir kaydin olu sayilmamasi dogrulanir: gecici
bir RPC hatasi calisan indirmenin kaydini bozmamali.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import Store  # noqa: E402
from core.manager import Manager  # noqa: E402
from core.rpc import Aria2Error  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


HASH = "08ada5a7a6183aae1e09d831df6748d566095a10"
MAGNET = f"magnet:?xt=urn:btih:{HASH}&dn=Sintel"


class SahteRPC:
    """Motorun tuttugu isler disaridan verilir; kopuk ise Aria2Error atar."""

    def __init__(self, isler: list[dict] | None = None, kopuk: bool = False):
        self.isler = isler or []
        self.kopuk = kopuk

    def _liste(self):
        if self.kopuk:
            raise Aria2Error("baglanti yok")
        return list(self.isler)

    def tell_active(self, *a, **k):
        return self._liste()

    def tell_waiting(self, *a, **k):
        return []

    def tell_stopped(self, *a, **k):
        return []


def yonetici(rpc: SahteRPC, tmp: Path) -> Manager:
    tmp.mkdir(parents=True, exist_ok=True)
    m = Manager.__new__(Manager)
    m.store = Store(str(tmp / "test.db"))
    m.rpc = rpc
    m.video_jobs = {}
    m._video_seq = 0
    m._lock = threading.RLock()
    m._known_complete = set()
    m._cerezler = {}
    m.last_error = ""
    return m


# Store baglantilari acik kaldigi icin Windows silemez: temizlik hatasi yutulur.
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    tmp = Path(gecici)

    print("1) Motorda karsiligi olmayan kayit kuyrukta SAYILMAZ")
    m = yonetici(SahteRPC([]), tmp / "a")
    kimlik = m.store.add("torrent", MAGNET, title="Sintel", gid="olu-gid")
    m.store.update_by_id(kimlik, status="active")
    check("olu kayit mukerrer sayilmiyor", m.find_duplicate(MAGNET) is None)
    kayit = m.store.by_id(kimlik)
    check("olu kayit hata olarak isaretlendi", kayit["status"] == "error", kayit["status"])
    check("hata metni kullaniciya bir sey anlatiyor", "motorda" in (kayit["error"] or ""),
          str(kayit["error"]))

    print("2) Motorda GERCEKTEN duran is mukerrer sayilir")
    m = yonetici(SahteRPC([{"gid": "canli-gid", "status": "active", "infoHash": HASH}]), tmp / "b")
    kimlik = m.store.add("torrent", MAGNET, title="Sintel", gid="canli-gid")
    m.store.update_by_id(kimlik, status="active")
    check("info hash eslesince mukerrer", m.find_duplicate(MAGNET) is not None)
    check("kayit bozulmadi", m.store.by_id(kimlik)["status"] == "active")

    print("3) Zamanlanmis is motorda olmadan da kuyruktadir")
    m = yonetici(SahteRPC([]), tmp / "c")
    kimlik = m.store.add("http", "https://ornek.com/f.zip", start_after=2 ** 40)
    check("zamanlanmis is mukerrer sayiliyor",
          (m.find_duplicate("https://ornek.com/f.zip") or {}).get("id") == kimlik)
    check("zamanlanmis kayit bozulmadi", m.store.by_id(kimlik)["status"] == "scheduled")

    print("4) Motor CEVAP VERMEZKEN hicbir kayit olu sayilmaz")
    m = yonetici(SahteRPC(kopuk=True), tmp / "d")
    kimlik = m.store.add("http", "https://ornek.com/f.zip", gid="gid-1")
    m.store.update_by_id(kimlik, status="active")
    check("RPC kopukken kayit korunuyor",
          (m.find_duplicate("https://ornek.com/f.zip") or {}).get("id") == kimlik)
    check("kayit hala aktif", m.store.by_id(kimlik)["status"] == "active")

    print("5) Video isleri de motorda aranmaz, bellekte durur")
    m = yonetici(SahteRPC([]), tmp / "e")
    kimlik = m.store.add("video", "https://ornek.com/izle", gid="yt:1")
    m.store.update_by_id(kimlik, status="active")
    m.video_jobs["yt:1"] = object()
    check("calisan video kaydi olu sayilmiyor",
          (m.find_duplicate("https://ornek.com/izle") or {}).get("id") == kimlik)

    print("6) Yeniden baslatmada magnet kaydi yeni GID'e baglanir")
    m = yonetici(SahteRPC([]), tmp / "f")
    kimlik = m.store.add("torrent", MAGNET, title="Sintel", gid="eski-gid")
    m.store.update_by_id(kimlik, status="active")
    yeni = m._reattach_torrent({"gid": "yeni-gid", "infoHash": HASH.upper()})
    check("kayit info hash ile bulundu", (yeni or {}).get("id") == kimlik)
    check("kayda yeni GID yazildi", m.store.by_id(kimlik)["gid"] == "yeni-gid")
    check("ilgisiz info hash baglanmiyor",
          m._reattach_torrent({"gid": "x", "infoHash": "f" * 40}) is None)

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
