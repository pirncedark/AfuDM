# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import time
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import paths
DB_PATH = Path(tempfile.gettempdir()) / f"v21_test_{int(time.time())}.sqlite"
paths.DB_PATH = DB_PATH

from core.manager import Manager
from core.servis import AfuDMServis
from core.hata import AfuHata, hata_json

passed = 0
failed = 0

def _check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {msg}")

def run_tests():
    # setup
    kok_dir = Path(tempfile.gettempdir()) / f"afudm_kok_{int(time.time())}"
    kok_dir.mkdir(parents=True, exist_ok=True)
    kardes_dir = Path(tempfile.gettempdir()) / f"afudm_kok_{int(time.time())}_baska"
    kardes_dir.mkdir(parents=True, exist_ok=True)

    class MockStore:
        def get(self, key):
            return None
        def log(self, level, msg, gid=""):
            pass

    class MockManager:
        store = MockStore()
        def current_download_dir(self):
            return str(kok_dir)

    manager = MockManager()
    servis = AfuDMServis.__new__(AfuDMServis)
    servis.manager = manager
    servis.store = manager.store

    print("Test: dizin disina yazma (mutlak yol)")
    dis_yol = Path(tempfile.gettempdir()).resolve()
    try:
        servis.hedef_klasor(str(dis_yol), "http://x", "http", "", uzaktan=True)
        _check(False, "Dizin disina yazma reddedilmeliydi")
    except AfuHata as exc:
        _check(exc.code == "HEDEF_DISARIDA", "Dogru hata kodu dönmeli (HEDEF_DISARIDA)")

    print("Test: kok icindeki alt klasor KABUL EDILIR")
    ic_yol = kok_dir / "alt_klasor"
    try:
        sec = servis.hedef_klasor(str(ic_yol), "http://x", "http", "", uzaktan=True)
        _check(str(sec) == str(ic_yol), "Icerideki alt klasor kabul edilmeli")
    except AfuHata:
        _check(False, "Alt klasor kabul edilmeliydi")

    print("Test: .. ile cikis REDDEDILIR")
    kacis_yol = kok_dir / ".."
    try:
        servis.hedef_klasor(str(kacis_yol), "http://x", "http", "", uzaktan=True)
        _check(False, ".. ile cikis reddedilmeliydi")
    except AfuHata as exc:
        _check(exc.code == "HEDEF_DISARIDA", "Dogru hata kodu dönmeli")

    print("Test: benzer isimli kardes klasor REDDEDILIR")
    try:
        servis.hedef_klasor(str(kardes_dir), "http://x", "http", "", uzaktan=True)
        _check(False, "Kardes klasor reddedilmeliydi")
    except AfuHata as exc:
        _check(exc.code == "HEDEF_DISARIDA", "Dogru hata kodu dönmeli")

    print("Test: OSError yaniti mutlak yol ICERMEZ")
    try:
        os.remove(kok_dir / "olmayan_dosya.txt")
    except OSError as e:
        tam_mesaj = str(e)
        _check(kok_dir.name in tam_mesaj, "Orijinal Python hatasi yolu icermeli (test ortami)")
        yanit = hata_json(e)
        _check(str(kok_dir) not in yanit["message"], "JSON yaniti yolu ICERMEMELI")
        _check(yanit["message"] == "dosya islemi basarisiz", "Jenerik mesaj dönmeli")
        _check(yanit["code"] == "IO", "Hata kodu IO olmali")

    print(f"\nSONUC: {passed} gecti / {failed} dustu")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
