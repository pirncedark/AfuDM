# -*- coding: utf-8 -*-
"""Torrent seciminin aria2'ye aninda uygulanmasi -- AG GEREKTIRMEZ.

Bu testin yakaladigi bozulmalar:
- ``select-file`` degerinin 0-tabanli ya da yanlis ayiracli gonderilmesi,
- bos secimin tum dosyalari secmek yerine eski secimi birakmasi,
- magnet ustveri GID'inden cocuk torrent GID'ine tercih kaybinin olmasi,
- seed tazeleme yeniden-eklemesinde tercihlerin unutulmasi.
"""
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
    def __init__(self, dizin: str) -> None:
        self.dizin = dizin
        self.degisenler: list[tuple[str, dict]] = []
        self.eklenenler: list[tuple[list[str], dict]] = []
        self.durumlar: list[dict] = []

    def tell_status(self, gid: str, keys=None) -> dict:
        return {
            "gid": gid, "status": "active", "infoHash": "abc123", "dir": self.dizin,
            "bittorrent": {"info": {"name": "Film"}},
        }

    def get_files(self, gid: str) -> list[dict]:
        return [
            {"index": "1", "path": "Film/a.mkv", "length": "10", "selected": "true"},
            {"index": "2", "path": "Film/b.srt", "length": "10", "selected": "true"},
            {"index": "3", "path": "Film/c.txt", "length": "10", "selected": "true"},
        ]

    def change_option(self, gid: str, secenekler: dict) -> str:
        self.degisenler.append((gid, dict(secenekler)))
        return "OK"

    def tell_active(self, *args, **kwargs) -> list[dict]:
        return list(self.durumlar)

    def tell_stopped(self, *args, **kwargs) -> list[dict]:
        return []

    def change_global_option(self, secenekler: dict) -> str:
        return "OK"

    def pause(self, gid: str, force=False) -> str:
        return "OK"

    def remove(self, gid: str, force=False) -> str:
        return "OK"

    def remove_result(self, gid: str) -> str:
        return "OK"

    def add_uri(self, uriler: list[str], secenekler: dict | None = None) -> str:
        self.eklenenler.append((uriler, dict(secenekler or {})))
        return "yenilenmis-gid"

    def add_torrent(self, veri: str, secenekler: dict | None = None) -> str:
        self.eklenenler.append((["<torrent>"], dict(secenekler or {})))
        return "yenilenmis-gid"


def yonetici(tmp: Path, rpc: SahteRPC) -> Manager:
    manager = Manager.__new__(Manager)
    manager.store = Store(str(tmp / "torrent-secim.db"))
    manager.rpc = rpc
    manager.video_jobs = {}
    manager._lock = threading.RLock()
    manager._known_complete = set()
    manager._cerezler = {}
    manager.last_error = ""
    return manager


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    tmp = Path(gecici)
    rpc = SahteRPC(str(tmp))
    manager = yonetici(tmp, rpc)
    kayit = manager.store.add("torrent", "magnet:?xt=urn:btih:abc123", gid="torrent-gid")
    manager.store.update_by_id(kayit, status="active")

    print("1) Calisan torrentte secim aninda degisir")
    sonuc = manager.torrent_secimi_ayarla("torrent-gid", [3, 1, 3])
    check("sonuc normalize edilir", sonuc["indeksler"] == [1, 3], str(sonuc))
    check("aria2 1-tabanli virgullu deger alir",
          rpc.degisenler[-1] == ("torrent-gid", {"select-file": "1,3"}), str(rpc.degisenler))
    check("kalici secim yazilir", manager.torrent_dosya_secimleri("torrent-gid") == [1, 3])

    print("2) Bos secim tum dosyalari secer")
    sonuc = manager.torrent_secimi_ayarla("torrent-gid", [])
    check("bos secim sonucu", sonuc["indeksler"] == [], str(sonuc))
    check("aria2 secenegi bos birakilir",
          rpc.degisenler[-1] == ("torrent-gid", {"select-file": ""}), str(rpc.degisenler))
    check("bos tercih kalici", manager.torrent_dosya_secimleri("torrent-gid") == [])

    print("3) Gecersiz indeks motor ve DB'ye gitmez")
    once = len(rpc.degisenler)
    hatalar = []
    for gecersiz_indeksler in ([-1], [4]):
        try:
            manager.torrent_secimi_ayarla("torrent-gid", gecersiz_indeksler)
            hata = ""
        except ValueError as exc:
            hata = str(exc)
        hatalar.append(hata)
    check("negatif indeks net hata", "gecersiz" in hatalar[0].lower(), hatalar[0])
    check("dosya sayisini asan indeks net hata", "gecersiz" in hatalar[1].lower(), hatalar[1])
    check("changeOption cagrilmadi", len(rpc.degisenler) == once)
    check("onceki tercih korundu", manager.torrent_dosya_secimleri("torrent-gid") == [])

    print("4) Magnetten cocuk torrente geciste secim devralinir")
    manager.store.torrent_dosya_secimlerini_kaydet("torrent-gid", [2])
    rpc.durumlar = [{"gid": "torrent-gid", "status": "active", "followedBy": ["cocuk-gid"]}]
    manager._sync_aria2()
    check("kayit cocuk GID'e tasindi", manager.store.by_id(kayit)["gid"] == "cocuk-gid")
    check("secim cocukta korundu", manager.torrent_dosya_secimleri("cocuk-gid") == [2])
    check("cocuk motorda da secili", rpc.degisenler[-1] == ("cocuk-gid", {"select-file": "2"}),
          str(rpc.degisenler))

    print("5) Seed tazelemede yeniden ekleme secimi korur")
    sonuc = manager.seed_tazele("cocuk-gid")
    check("tazeleme basarili", sonuc.get("ok") is True, str(sonuc))
    check("yeniden eklemede select-file var",
          rpc.eklenenler[-1][1].get("select-file") == "2", str(rpc.eklenenler))
    check("yenilenmis GID'de tercih korunur",
          manager.torrent_dosya_secimleri("yenilenmis-gid") == [2])
    manager.store.conn.close()

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
