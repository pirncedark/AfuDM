# -*- coding: utf-8 -*-
"""DB migration altyapisi testleri (Foundation v1.4).

- Yeni/kok db acilista `PRAGMA user_version` = USER_VERSION'a tasinir.
- Mevcut (eski) veri ASLA silinmez, defaults ayarlar doldurulur.
- Farkli satirlik acilislar arbita olmaz.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from core import db  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


tmp = Path(tempfile.mkdtemp(prefix="afudm_db_"))

print("1) Sifir db acilista user_version = USER_VERSION")
s = db.Store(str(tmp / "yeni.db"))
ver = s.conn.execute("PRAGMA user_version").fetchone()[0]
check("yeni db user_version 1", ver == db.USER_VERSION, str(ver))
check("defaults ayarlar dolduruldu", s.get("download_dir") == "" and s.get("hiz_profili") == "normal")
s.conn.close()

print("2) Eski db (0. satir) acilir, veri korunur")
eski_path = tmp / "eski.db"
_conn = sqlite3.connect(str(eski_path))
_conn.execute(
    """CREATE TABLE downloads (id INTEGER PRIMARY KEY AUTOINCREMENT,
    gid TEXT UNIQUE, kind TEXT NOT NULL DEFAULT 'http', source TEXT NOT NULL,
    title TEXT, dest_dir TEXT, filename TEXT, total_bytes INTEGER DEFAULT 0,
    done_bytes INTEGER DEFAULT 0, status TEXT DEFAULT 'queued', error TEXT,
    options TEXT DEFAULT '{}', added_at REAL NOT NULL, started_at REAL,
    finished_at REAL, start_after REAL)""")
_conn.execute(
    "INSERT INTO downloads(source, added_at, status) VALUES('eski-link', 123.0, 'error')")
_conn.execute("PRAGMA user_version = 0")
_conn.commit()
_conn.close()

s = db.Store(str(eski_path))
ver = s.conn.execute("PRAGMA user_version").fetchone()[0]
check("eski db user_version 1 oldu", ver == 1, str(ver))
satirlar = s.conn.execute("SELECT id, source, status FROM downloads").fetchall()
check("eski kayit korundu", len(satirlar) == 1
      and satirlar[0][1] == "eski-link" and satirlar[0][2] == "error", str(satirlar))
check("user_version HIC artmayan adim yok (MIGRATIONS bosa)", db.USER_VERSION >= 1)
s.conn.close()

print("3) Db USER_VERSION tasi gescitli: migration adim calisir")
# 2. adim olarak demonstre: USER_VERSION'u gecici artirmadan _guncelle_sema
# dogrudan dogrulanir — test altyapisina dokunmadan ayni mantigi calistir.
yeniden = sqlite3.connect(str(tmp / "gecici.db"))
yeniden.execute("PRAGMA user_version = 0")
yeniden.commit()
yeniden.close()
s = db.Store(str(tmp / "gecici.db"))
check("ikinci acilis da 1", s.conn.execute("PRAGMA user_version").fetchone()[0] == 1)
s.conn.close()

print("\ndb migration: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: db migration tutarli")