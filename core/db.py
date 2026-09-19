"""SQLite durum deposu: indirme gecmisi, ayarlar, zamanlanmis isler.

aria2 kendi kuyrugunu ve oturumunu zaten tutuyor; burada aria2'nin bilmedigi
seyleri tutuyoruz: kaynak URL turu, baslik, zamanlama, gecmis, ayarlar.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Callable

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
    # Hiz profili: "normal" = max_speed_kb uygulanir,
    #               "turbo"  = sinirsiz (0),
    #               "snail"  = snail_speed_kb (arka planda hissettirmez)
    "hiz_profili": "normal",
    "snail_speed_kb": 100,
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
    # Network Core v1.4: proxy katmanlari (bkz. core/proxy.py)
    #   proxy        -> genel varsayilan proxy (ayri adresler is uzerinde yazabilir)
    #   system_proxy -> Windows Internet Settings'teki sistem proxy kullanilsin mi
    "proxy": "",
    "system_proxy": False,
    # --- v2.1 Headless Server -------------------------------------------
    # HTTP yonetim sunucusu. VARSAYILAN KAPALI: acilmadan hicbir uzak
    # erisim yoktur. Acilinca bile anahtarsiz hicbir sey yapilamaz.
    "sunucu_acik": False,
    # "yerel" = yalniz 127.0.0.1, "lan" = 0.0.0.0 (ayni Wi-Fi).
    # Internete acma OZELLIGI YOKTUR; port yonlendirmeyi kullanici yapar.
    "sunucu_adres": "yerel",
    "sunucu_port": 6821,
    # Kaba kuvvet korumasi: ayni IP'den dakikada izin verilen istek sayisi
    "sunucu_istek_limiti": 120,
    # Ust uste bu kadar yanlis anahtar -> o IP gecici kilitlenir
    "sunucu_hatali_limit": 8,
    "sunucu_kilit_saniye": 300,
    # CSRF/origin: panel disindan gelen tarayici isteklerini reddet.
    # Bos ise YALNIZ sunucunun kendi adresi kabul edilir (en siki).
    "sunucu_izinli_originler": "",
    # Istemci oturum kaydi tutulsun mu (kim bagli ekrani bunu okur)
    "sunucu_istemci_kaydi": True,
    # Etkin sunucu profili (server_profiles.id); 0 = profil yok
    "sunucu_profil_id": 0,
}


# --- sema surumu (migration) ---------------------------------------------
# `USER_VERSION`'i artirinca aradaki ADIMI `MIGRATIONS` sozlugune ekle.
# Adimlar YALNIZCA degisiklik gerektiginde vardir; gecis 0->1 hic is yapmaz
# (mevcut _SCHEMA zaten v1'dir). Eski veri ASLA silinmez.
USER_VERSION = 4


def _v2_torrent_dosya_secimleri(conn: sqlite3.Connection) -> None:
    """Torrent dosya secimlerini aria2 oturumundan bagimsiz sakla.

    `file_index=0` secim kaydinin varligini belirtir; bu sayede kullanicinin
    tum dosyalari kapattigi durum, hic tercih kaydedilmemis durumdan ayrilir.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS torrent_file_selections (
            gid        TEXT NOT NULL,
            file_index INTEGER NOT NULL,
            selected   INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (gid, file_index)
        )
    """)

def _v3_events_gid(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE events ADD COLUMN gid TEXT")

def _v4_sunucu_erisimi(conn: sqlite3.Connection) -> None:
    """v2.1 Headless Server: erisim anahtarlari, istemciler, sunucu profilleri.

    YALNIZCA EKLER. downloads/settings/events tablolarina DOKUNMAZ; kullanici
    ayarlari ve indirme gecmisi oldugu gibi kalir. Idempotent: IF NOT EXISTS.

    `gizli_hash` alani anahtarin SHA-256 ozetidir; anahtarin KENDISI hicbir
    yerde saklanmaz ve loglanmaz. Rotasyon ayni satirin ozetini degistirir,
    boylece eski anahtar ANINDA gecersiz olur.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ad          TEXT NOT NULL,
            rol         TEXT NOT NULL DEFAULT 'salt_okur',
            gizli_hash  TEXT NOT NULL,
            onek        TEXT NOT NULL DEFAULT '',
            olusturuldu REAL NOT NULL,
            son_kullanim REAL,
            son_rotasyon REAL,
            iptal       INTEGER NOT NULL DEFAULT 0,
            not_metni   TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(gizli_hash)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_clients (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id       INTEGER,
            oturum       TEXT NOT NULL UNIQUE,
            ip           TEXT NOT NULL DEFAULT '',
            istemci      TEXT NOT NULL DEFAULT '',
            rol          TEXT NOT NULL DEFAULT 'salt_okur',
            ilk_gorulme  REAL NOT NULL,
            son_gorulme  REAL NOT NULL,
            istek_sayisi INTEGER NOT NULL DEFAULT 0,
            iptal        INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_clients_oturum ON api_clients(oturum)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS server_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ad          TEXT NOT NULL,
            adres       TEXT NOT NULL DEFAULT 'yerel',
            port        INTEGER NOT NULL DEFAULT 6821,
            originler   TEXT NOT NULL DEFAULT '',
            istek_limiti INTEGER NOT NULL DEFAULT 120,
            olusturuldu REAL NOT NULL
        )
    """)


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: _v2_torrent_dosya_secimleri,
    3: _v3_events_gid,
    4: _v4_sunucu_erisimi,
}


def _guncelle_sema(conn: sqlite3.Connection) -> None:
    """`PRAGMA user_version`'u USER_VERSION'a tasir, aradaki adimlari uygular."""
    mevcut = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
    for surum in range(mevcut + 1, USER_VERSION + 1):
        adim = MIGRATIONS.get(surum)
        if adim:
            adim(conn)
        conn.execute(f"PRAGMA user_version = {surum}")


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
            _guncelle_sema(self.conn)

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

    # --- torrent dosya secimleri -----------------------------------------
    def torrent_dosya_secimlerini_kaydet(self, gid: str, indeksler: list[int]) -> None:
        """Bir torrentin kullanici tarafindan secilen aria2 dosya indeksleri."""
        with self._lock:
            self.conn.execute("DELETE FROM torrent_file_selections WHERE gid = ?", (gid,))
            self.conn.execute(
                "INSERT INTO torrent_file_selections(gid, file_index, selected) VALUES(?,?,1)",
                (gid, 0),
            )
            self.conn.executemany(
                "INSERT INTO torrent_file_selections(gid, file_index, selected) VALUES(?,?,1)",
                [(gid, indeks) for indeks in sorted(set(indeksler))],
            )
            self.conn.commit()

    def torrent_dosya_secimleri(self, gid: str) -> list[int]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT file_index FROM torrent_file_selections "
                "WHERE gid = ? AND file_index > 0 AND selected = 1 ORDER BY file_index",
                (gid,),
            ).fetchall()
        return [int(row["file_index"]) for row in rows]

    def torrent_dosya_secimi_var(self, gid: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM torrent_file_selections WHERE gid = ? AND file_index = 0",
                (gid,),
            ).fetchone()
        return row is not None

    def torrent_dosya_secimlerini_tasi(self, eski_gid: str, yeni_gid: str) -> None:
        """Magnet ustverisi cocuk GID urettiginde secimleri de devral."""
        with self._lock:
            self.conn.execute(
                "UPDATE OR IGNORE torrent_file_selections SET gid = ? WHERE gid = ?",
                (yeni_gid, eski_gid),
            )
            self.conn.commit()

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
    def log(self, level: str, message: str, gid: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO events(at, level, message, gid) VALUES(?,?,?,?)",
                (time.time(), level, message, gid or None),
            )
            self.conn.commit()

    def recent_events(self, limit: int = 50, gid: str = "") -> list[dict]:
        with self._lock:
            if gid:
                rows = self.conn.execute(
                    "SELECT * FROM events WHERE gid = ? ORDER BY id DESC LIMIT ?", (gid, limit)
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]
