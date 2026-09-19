# -*- coding: utf-8 -*-
"""Torrent dosya veri katmani testleri -- ag veya gercek aria2 gerekmez."""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.db import Store  # noqa: E402
from core.manager import Manager  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" -- {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


class SahteRPC:
    def __init__(self, durum: dict, dosyalar: list[dict]) -> None:
        self.durum = durum
        self.dosyalar = dosyalar

    def tell_status(self, gid: str, keys=None) -> dict:
        return dict(self.durum, gid=gid)

    def get_files(self, gid: str) -> list[dict]:
        return list(self.dosyalar)


def yonetici(tmp: Path, rpc: SahteRPC) -> Manager:
    manager = Manager.__new__(Manager)
    manager.store = Store(str(tmp / "torrent.db"))
    manager.rpc = rpc
    manager.video_jobs = {}
    manager._lock = threading.RLock()
    manager._known_complete = set()
    manager._cerezler = {}
    manager.last_error = ""
    return manager


DOSYALAR = [
    {"index": "1", "path": r"C:\Indirilenler\Film\video\bolum01.mkv",
     "length": "1048576", "completedLength": "524288", "selected": "true", "uris": []},
    {"index": "2", "path": r"C:\Indirilenler\Film\altyazi\tr.srt",
     "length": "1024", "completedLength": "1024", "selected": "false", "uris": []},
]
TORRENT = {"status": "active", "infoHash": "abc123", "bittorrent": {"info": {"name": "Film"}}}

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    tmp = Path(gecici)
    manager = yonetici(tmp, SahteRPC(TORRENT, DOSYALAR))
    manager.store.add("torrent", "magnet:?xt=urn:btih:abc123", gid="torrent-1")

    print("1) aria2 getFiles kullanici diline cevrilir")
    sonuc = manager.torrent_dosyalari("torrent-1")
    ilk = sonuc[0]
    check("dosya adi ayristi", ilk["ad"] == "bolum01.mkv", str(ilk))
    check("tam yol korundu", ilk["yol"] == r"C:\Indirilenler\Film\video\bolum01.mkv")
    check("boyut ve insan boyutu", ilk["boyut"] == 1048576 and ilk["boyut_insan"] == "1.0 MB")
    check("yuzde ve secim", ilk["yuzde"] == 50.0 and ilk["secili"] is True)
    check("uzanti ve tur tahmini", ilk["uzanti"] == ".mkv" and ilk["tur"] == "video")

    print("2) Ic ice klasor yollarinda parent bilgisi var")
    check("klasor parcalari", ilk["yol_parcalari"] == ["Film", "video", "bolum01.mkv"], str(ilk))
    check("parent yol", ilk["parent_yol"] == "Film/video")
    check("ikinci dosya ayri parent", sonuc[1]["parent_yol"] == "Film/altyazi")

    print("3) Magnet ustverisi gelmeden liste cokmez")
    manager.rpc = SahteRPC({"status": "active", "bittorrent": {}}, [])
    bekleyen = manager.torrent_dosyalari("torrent-1")
    check("liste bos", bekleyen == [])
    check("hazir degil isareti", getattr(bekleyen, "hazir_degil", False) is True,
          getattr(bekleyen, "neden", ""))

    print("4) Torrent olmayan gid net hata verir")
    manager.store.add("http", "https://ornek.test/dosya.zip", gid="http-1")
    try:
        manager.torrent_dosyalari("http-1")
        hata = ""
    except ValueError as exc:
        hata = str(exc)
    check("torrent olmayan hata", "torrent" in hata.lower(), hata)

    print("5) Dosya secimi DB'de kalici")
    manager.torrent_dosya_secimini_kaydet("torrent-1", [2])
    check("kayit geri okunur", manager.torrent_dosya_secimleri("torrent-1") == [2])
    manager.store.conn.close()
    manager = yonetici(tmp, SahteRPC(TORRENT, DOSYALAR))
    check("yeniden baslatmada secim geri okunur", manager.torrent_dosya_secimleri("torrent-1") == [2])
    manager.rpc = SahteRPC(TORRENT, DOSYALAR)
    secimli = manager.torrent_dosyalari("torrent-1")
    check("saklanan secim aria2 yanitini ezer", secimli[0]["secili"] is False and secimli[1]["secili"] is True)
    manager.store.conn.close()

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
