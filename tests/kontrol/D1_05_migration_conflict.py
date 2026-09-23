"""Reproduce the reported pre-existing events.gid migration collision."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import db  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="afudm_d1_05_", dir=ROOT) as tmp:
        conn = sqlite3.connect(str(Path(tmp) / "legacy.db"))
        conn.executescript(db._SCHEMA)
        conn.execute("ALTER TABLE events ADD COLUMN gid TEXT")
        conn.execute("PRAGMA user_version=2")
        try:
            db._guncelle_sema(conn)
        except sqlite3.OperationalError as exc:
            if "duplicate column" in str(exc).lower():
                print(f"BULGU DOĞRULANDI: user_version=2 ve events.gid mevcutken migration 3 hata verdi: {exc}")
                return 0
            raise
        finally:
            conn.close()
        print("BULGU YANLIŞ ALARM: çakışmalı eski DB migration'ı tamamladı")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
