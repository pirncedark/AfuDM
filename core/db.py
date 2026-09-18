"""SQLite durum deposu: indirme gecmisi, ayarlar, zamanlanmis isler.

aria2 kendi kuyrugunu ve oturumunu zaten tutuyor; burada aria2'nin bilmedigi
seyleri tutuyoruz: kaynak URL turu, baslik, zamanlama, gecmis, ayarlar.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from . import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gid         TEXT UNIQUE,
    kind        TEXT NOT NULL DEFAULT 'http',
    source      TEXT NOT NULL,
    title       TEXT,
    dest_dir    TEXT,
    filename    TEXT,
    total_bytes INTEGER DEFAULT 0,
    done_bytes  INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'queued',
    error       TEXT,
    options     TEXT DEFAULT '{}',
    added_at    REAL NOT NULL,
    started_at  REAL,
    finished_at REAL,
    start_after REAL
);
CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_downloads_gid    ON downloads(gid);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    at       REAL NOT NULL,
    level    TEXT NOT NULL,
    message  TEXT NOT NULL
);
"""

DEFAULTS: dict[str, Any] = {
    # auto = Windows dilinden karar ver (bkz. core/lang.py)
    "language": "auto",
    "download_dir": "",
    "max_concurrent": 5,
    "split": 64,
    "max_conn_per_server": 16,
    "max_speed_kb": 0,
    "clipboard_watch": True,
    "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
    "notify_telegram": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "shutdown_when_done": False,
    # Bitince UYUT (kapatma degil): uyanista sifre istemez, is kaldigi yerden surer
    "sleep_when_done": False,
    "seed_ratio": 1.0,
    "auto_update_trackers": True,
    "video_quality": "best",
    "api_port": 6811,
    # Tarayicidan gelen indirmede once kaydetme penceresi (IDM gibi)
    "kaydetme_penceresi": True,
    # Bos hedefte indirmeler downloads/Video, downloads/Muzik... altina
    "kategori_klasorleri": True,
    # qBittorrent gibi: kucult gorev cubuguna, X sistem tepsisine gitsin
    "tepsiye_kucult": True,
    # Bilgisayar acilinca pencere ACILMADAN tepside basla
    "baslangicta_tepside": True,
    # Kullanicinin elle ekledigi tracker'lar (her satirda bir adres)
    "ek_trackerlar": "",
    # trackers/ klasoru + elle eklenenler taranip CANLI kalanlar (otomatik)
    "canli_trackerlar": "",
    "tracker_tarama_zamani": 0,
    "tracker_tarama_ozeti": {},
    # Gunde bir kendiliginden tara (olu tracker'lar duyuruyu geciktiriyor)
    "tracker_otomatik_tara": True,
    # Telefondan baglan: yerel API 0.0.0.0'a acilir (VARSAYILAN KAPALI)
    "lan_erisimi": False,
    # Kullanicinin ekledigi ag konumlari (her satirda bir UNC yolu)
    "ag_konumlari": "",
}


class Store:
    def __init__(self, path: str | None = None) -> None:
        paths.ensure_dirs()
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(
            path or str(paths.DB_PATH), check_same_thread=False, timeout=15
        )
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(_SCHEMA)
            for key, value in DEFAULTS.items():
                self.conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, json.dumps(value)),
                )
            self.conn.commit()

    # --- ayarlar ----------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self.conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return DEFAULTS.get(key, default)
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
            self.conn.commit()

    def all_settings(self) -> dict[str, Any]:
        with self._lock:
            rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        out = dict(DEFAULTS)
        for row in rows:
            try:
                out[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                out[row["key"]] = row["value"]
        return out

    # --- indirmeler -------------------------------------------------------
    def add(
        self,
        kind: str,
        source: str,
        title: str | None = None,
        dest_dir: str | None = None,
        options: dict | None = None,
        start_after: float | None = None,
        gid: str | None = None,
    ) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO downloads(gid, kind, source, title, dest_dir, options,"
                " added_at, start_after, status) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    gid,
                    kind,
                    source,
                    title,
                    dest_dir,
                    json.dumps(options or {}),
                    time.time(),
                    start_after,
                    "scheduled" if start_after else "queued",
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def attach_gid(self, row_id: int, gid: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE downloads SET gid = ?, status = 'active', started_at = ?"
                " WHERE id = ?",
                (gid, time.time(), row_id),
            )
            self.conn.commit()

    def update_by_gid(self, gid: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join("%s = ?" % k for k in fields)
        with self._lock:
            self.conn.execute(
                "UPDATE downloads SET %s WHERE gid = ?" % cols,
                (*fields.values(), gid),
            )
            self.conn.commit()

    def update_by_id(self, row_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join("%s = ?" % k for k in fields)
        with self._lock:
            self.conn.execute(
                "UPDATE downloads SET %s WHERE id = ?" % cols,
                (*fields.values(), row_id),
            )
            self.conn.commit()

    def by_gid(self, gid: str) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM downloads WHERE gid = ?", (gid,)
            ).fetchone()
        return dict(row) if row else None

    def by_id(self, row_id: int) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM downloads WHERE id = ?", (row_id,)
            ).fetchone()
        return dict(row) if row else None

    def list(self, status: str | None = None, limit: int = 500) -> list[dict]:
        sql = "SELECT * FROM downloads"
        args: tuple = ()
        if status:
            sql += " WHERE status = ?"
            args = (status,)
        sql += " ORDER BY added_at DESC LIMIT ?"
        with self._lock:
            rows = self.conn.execute(sql, (*args, limit)).fetchall()
        return [dict(r) for r in rows]

    def max_video_seq(self) -> int:
        """En buyuk 'yt:<n>' is numarasi. Video is kimlikleri surecler arasinda
        tekrar etmemeli: veritabani kalici, sayac ise her acilista sifirlaniyordu."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT gid FROM downloads WHERE gid LIKE 'yt:%'"
            ).fetchall()
        highest = 0
        for row in rows:
            try:
                highest = max(highest, int(str(row["gid"]).split(":", 1)[1]))
            except (IndexError, ValueError):
                continue
        return highest

    def due_scheduled(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM downloads WHERE status = 'scheduled'"
                " AND start_after IS NOT NULL AND start_after <= ?",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, row_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM downloads WHERE id = ?", (row_id,))
            self.conn.commit()

    def clear_finished(self) -> int:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM downloads WHERE status IN ('complete','removed','error')"
            )
            self.conn.commit()
            return cur.rowcount

    # --- olay kaydi -------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO events(at, level, message) VALUES(?,?,?)",
                (time.time(), level, message),
            )
            self.conn.commit()

    def recent_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
