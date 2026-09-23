"""Migration idempotence and legacy event-column convergence."""
from __future__ import annotations

import sqlite3
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import db, paths  # noqa: E402


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="afudm_db_gecis_"))
    paths.DATA = root / "data"
    paths.DB_PATH = paths.DATA / "afudm.db"
    paths.DOWNLOADS, paths.PLUGINS = root / "downloads", root / "plugins"
    paths.ensure_dirs()
    failures = []

    fresh_path = root / "fresh.db"
    fresh = db.Store(str(fresh_path))
    fresh_version = fresh.conn.execute("PRAGMA user_version").fetchone()[0]
    fresh_events = {r[1] for r in fresh.conn.execute("PRAGMA table_info(events)")}
    fresh.conn.close()
    if fresh_version != 10 or "gid" not in fresh_events:
        failures.append(f"0->10: user_version={fresh_version}, events={fresh_events}")

    legacy_path = root / "legacy.db"
    conn = sqlite3.connect(legacy_path)
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, at REAL NOT NULL,
          level TEXT NOT NULL, message TEXT NOT NULL, gid TEXT);
        INSERT INTO events(at, level, message, gid) VALUES(1, 'info', 'kept', 'legacy-gid');
        PRAGMA user_version = 2;
    """)
    conn.close()
    try:
        first = db.Store(str(legacy_path))
        row = first.conn.execute("SELECT message, gid FROM events").fetchone()
        version = first.conn.execute("PRAGMA user_version").fetchone()[0]
        first.conn.close()
        second = db.Store(str(legacy_path))
        version_again = second.conn.execute("PRAGMA user_version").fetchone()[0]
        second.conn.close()
        if tuple(row) != ("kept", "legacy-gid") or version != 10 or version_again != 10:
            failures.append(f"legacy v2: row={tuple(row)}, versions={version}/{version_again}")
        rerun = sqlite3.connect(legacy_path)
        for migration in db.MIGRATIONS.values():
            migration(rerun)
        rerun.commit()
        still_10 = rerun.execute("PRAGMA user_version").fetchone()[0]
        row_after_rerun = rerun.execute("SELECT message, gid FROM events").fetchone()
        rerun.close()
        if still_10 != 10 or tuple(row_after_rerun) != ("kept", "legacy-gid"):
            failures.append(f"repeat every migration changed version/data: {still_10}, {tuple(row_after_rerun)}")
    except Exception as exc:
        failures.append(f"legacy v2 threw {type(exc).__name__}: {exc}")

    print("GECTI" if not failures else "BASARISIZ")
    for failure in failures:
        print(" - " + failure)
    shutil.rmtree(root, ignore_errors=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
