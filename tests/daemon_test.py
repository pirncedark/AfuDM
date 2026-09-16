"""aria2 sahipligi testi — AG GEREKTIRMEZ (gercek aria2c, yalniz 127.0.0.1).

Kusur: ikinci bir Aria2Daemon calisan motora BAGLANIYOR, kapanirken de onu
KAPATIYORDU. api_smoke, calisan AfuDM'in motorunu boyle oldurdu.
Kural: motoru kim baslattiysa yalniz o kapatir.

ONKOSUL: AfuDM KAPALI olmali (6810 bos) — yoksa test atlanir.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.daemon import Aria2Daemon  # noqa: E402

fails: list[str] = []


def check(name: str, condition: bool) -> None:
    print(("  [GECTI] " if condition else "  [BASARISIZ] ") + name)
    if not condition:
        fails.append(name)


sahip = Aria2Daemon()
if sahip.rpc.alive():
    print("6810'da calisan bir motor var (AfuDM acik?) — test ATLANDI")
    sys.exit(0)

sahip.start()
check("sahip motoru baslatti", sahip.rpc.alive() and sahip.proc is not None)

misafir = Aria2Daemon()
misafir.start()
check("misafir mevcut motora baglandi (yeni surec acmadi)", misafir.proc is None)

misafir.stop()
time.sleep(3)  # aria2 shutdown EŞZAMANSIZ: hemen bakmak kusuru gizler
check("misafir kapaninca motor AYAKTA kaldi", sahip.rpc.alive())

sahip.stop()
check("sahip kapaninca motor kapandi", not sahip.rpc.alive())

print("\n" + ("Hepsi gecti" if not fails else "BASARISIZ: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
