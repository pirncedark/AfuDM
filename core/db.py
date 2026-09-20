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

CREATE TABLE IF NOT EXISTS automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_gid TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    UNIQUE(download_gid, action)
);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status, id);
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
    # Windows bildirimleri; tepsi altyapisi varsa tamamlanma/hata durumunu gosterir.
    "windows_notifications": True,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "shutdown_when_done": False,
    # Bitince UYUT (kapatma degil): uyanista sifre istemez, is kaldigi yerden surer
    "sleep_when_done": False,
    "seed_ratio": 1.0,
    "auto_update_trackers": True,
    "video_quality": "best",
    # v1.7.5 — PORT IKIYE AYRILDI:
    #   api_listen_port -> KULLANICININ sectigi port (tercih; kalicidir)
    #   api_port        -> GERCEKTEN baglanilan calisan port (yalniz durum
    #                      bilgisi; tercih doluysa +1..+9 kaymis olabilir)
    "api_listen_port": 6811,
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
    # v1.8 Automation: adim sirasi ve parametreler yeni indirmelerde uygulanir.
    "automation_enabled": True,
    "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"],
    "automation_checksum": True,
    "automation_extract": False,
    "automation_move_to": "",
    "automation_rename_to": "",
    "automation_script": "",
    "automation_notify": True,
    "automation_power": "none",
    "automation_power_seconds": 60,
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
    "sunucu_proxy_guven": False,
}


# --- sema surumu (migration) ---------------------------------------------
# `USER_VERSION`'i artirinca aradaki ADIMI `MIGRATIONS` sozlugune ekle.
# Adimlar YALNIZCA degisiklik gerektiginde vardir; gecis 0->1 hic is yapmaz
# (mevcut _SCHEMA zaten v1'dir). Eski veri ASLA silinmez.
# v1.8 ile v1.7.5 ayni v4 numarasini farkli, bagimsiz migration'lar icin
# kullandi. v6 bu iki tarihi yolu idempotent olarak uzlastirir; boylece hangi
# daldan yukseltilirse yukseltilsin her iki ozellik de eksiksiz kalir.
# v1.9 kurallarini v6'yi degistirmeden yeni bir adimda ekler.
# v2.0 eklenti kaydi v8'dedir: v2.0 dali onu once v4 olarak yazmisti, ancak
# o numara v1.8/v1.7.5 tarafindan alinmisti; yeniden numaralandirildi.
# v2.1 sunucu erisimi v9'dadir: v2.1 dali da onu v4 olarak yazmisti (ucuncu
# kez ayni cakisma); yeniden numaralandirildi.
USER_VERSION = 9


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

def _v4_automation_jobs(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS automation_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, download_gid TEXT NOT NULL,
        action TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'queued', attempt INTEGER NOT NULL DEFAULT 0,
        progress INTEGER NOT NULL DEFAULT 0, error TEXT, created_at REAL NOT NULL,
        started_at REAL, finished_at REAL, UNIQUE(download_gid, action)
    );
    CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status, id);
    """)
def _v4_api_listen_port(conn: sqlite3.Connection) -> None:
    """Dinlenecek port (tercih) ile calisan portu AYIR.

    Eski surumde tek `api_port` vardi ve icine "su an baglanilan" port
    yaziliyordu; tercih doluysa 6812'ye kayan deger kalici gorunuyordu.
    Yukseltmede tercih VARSAYILANA (6811) alinir — eski `api_port` kaydi
    oldugu gibi birakilir (calisan port bilgisidir, ilk acilista tazelenir).
    Mevcut kullanici ayarlari ve indirme gecmisi ELLENMEZ.
    """
    eski = conn.execute("SELECT value FROM settings WHERE key='api_port'").fetchone()
    deger = eski[0] if eski and eski[0] else json.dumps(DEFAULTS["api_listen_port"])
    conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('api_listen_port', ?)", (deger,))

def _v5_mobile_devices(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS mobile_devices (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'owner',
        token_hash TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL,
        revoked_at REAL
    )""")

def _v6_v175_v18_uzlastir(conn: sqlite3.Connection) -> None:
    """Tarihi v4 numara cakismasindan kalan eksik semayi tamamla."""
    _v4_automation_jobs(conn)
    _v4_api_listen_port(conn)

def _v7_rules_engine(conn: sqlite3.Connection) -> None:
    """v1.9 kurallarini v1.7.5/v1.8 uzlastirmasinin ardindan ekle."""
    conn.execute("CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY,name TEXT NOT NULL,active INTEGER DEFAULT 1,priority INTEGER NOT NULL,match_type TEXT NOT NULL,conditions TEXT NOT NULL,actions TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority)")

def _v8_eklenti_kaydi(conn: sqlite3.Connection) -> None:
    """v2.0 Plugin Platform — kurulu eklenti kaydi.

    Eklenti DOSYALARI diskte (plugins/<ad>/) durur; burada yalnizca KAYIT
    tutulur: hangi surum, nereden geldi, etkin mi, kullanicinin verdigi
    ayarlar ve son hata. Indirme gecmisi ve ayarlar bu adimda ELLENMEZ."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            ad            TEXT PRIMARY KEY,
            baslik        TEXT NOT NULL DEFAULT '',
            surum         TEXT NOT NULL DEFAULT '',
            kaynak        TEXT NOT NULL DEFAULT '',
            giris         TEXT NOT NULL DEFAULT '',
            manifest      TEXT NOT NULL DEFAULT '{}',
            izinler       TEXT NOT NULL DEFAULT '[]',
            domainler     TEXT NOT NULL DEFAULT '[]',
            ayarlar       TEXT NOT NULL DEFAULT '{}',
            etkin         INTEGER NOT NULL DEFAULT 0,
            son_hata      TEXT NOT NULL DEFAULT '',
            onceki_surum  TEXT NOT NULL DEFAULT '',
            kurulum_at    REAL NOT NULL DEFAULT 0,
            guncelleme_at REAL NOT NULL DEFAULT 0
        )
    """)

def _v9_sunucu_erisimi(conn: sqlite3.Connection) -> None:
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
    4: _v4_automation_jobs,
    5: _v5_mobile_devices,
    6: _v6_v175_v18_uzlastir,
    7: _v7_rules_engine,
    8: _v8_eklenti_kaydi,
    9: _v9_sunucu_erisimi,
}


def _guncelle_sema(conn: sqlite3.Connection) -> None:
    """`PRAGMA user_version`'u USER_VERSION'a tasir, aradaki adimlari uygular."""
    mevcut = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
    for surum in range(mevcut + 1, USER_VERSION + 1):
        adim = MIGRATIONS.get(surum)
        if adim:
            adim(conn)
        conn.execute(f"PRAGMA user_version = {surum}")
    if mevcut < USER_VERSION:
        # Adim bir INSERT/UPDATE yaptiysa islem acik kalabilir; surum atlamasi
        # ile verinin AYNI anda kalici olmasi icin burada kapatiyoruz.
        conn.commit()


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

    def rules_list(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM rules ORDER BY priority, id").fetchall()
        return [{**dict(r), "active":bool(r["active"]), "conditions":json.loads(r["conditions"]), "actions":json.loads(r["actions"])} for r in rows]

    def rules_save(self, rules: list[dict]) -> None:
        with self._lock:
            self.conn.execute("BEGIN"); self.conn.execute("DELETE FROM rules")
            for priority, rule in enumerate(rules, 1):
                self.conn.execute("INSERT INTO rules(id,name,active,priority,match_type,conditions,actions) VALUES(?,?,?,?,?,?,?)", (rule["id"],rule["name"],int(bool(rule.get("active",True))),priority,rule.get("match_type","all"),json.dumps(rule.get("conditions") or []),json.dumps(rule.get("actions") or {})))
            self.conn.commit()

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

    # --- kalici otomasyon kuyrugu ---------------------------------------
    def automation_enqueue(self, gid: str, action: str, payload: dict | None = None) -> None:
        with self._lock:
            self.conn.execute("INSERT OR IGNORE INTO automation_jobs(download_gid,action,payload,created_at) VALUES(?,?,?,?)", (gid, action, json.dumps(payload or {}), time.time()))
            self.conn.commit()

    def automation_jobs(self, gid: str = "", limit: int = 200) -> list[dict]:
        sql, args = ("SELECT * FROM automation_jobs WHERE download_gid=? ORDER BY id", (gid,)) if gid else ("SELECT * FROM automation_jobs ORDER BY id DESC LIMIT ?", (limit,))
        with self._lock: rows = self.conn.execute(sql, args).fetchall()
        out = [dict(row) for row in rows]
        for row in out:
            try: row["payload"] = json.loads(row["payload"] or "{}")
            except json.JSONDecodeError: row["payload"] = {}
        return out

    def automation_claim(self) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM automation_jobs WHERE status IN ('queued','running') ORDER BY id LIMIT 1").fetchone()
            if not row: return None
            self.conn.execute("UPDATE automation_jobs SET status='running',attempt=attempt+1,started_at=?,error=NULL WHERE id=?", (time.time(), row["id"]))
            self.conn.commit()
        return self.automation_jobs_by_id(int(row["id"]))

    def automation_jobs_by_id(self, job_id: int) -> dict | None:
        with self._lock: row = self.conn.execute("SELECT * FROM automation_jobs WHERE id=?", (job_id,)).fetchone()
        if not row: return None
        out=dict(row)
        try: out["payload"] = json.loads(out["payload"] or "{}")
        except json.JSONDecodeError: out["payload"] = {}
        return out

    def automation_update(self, job_id: int, **fields: Any) -> None:
        if not fields: return
        cols=", ".join(f"{key}=?" for key in fields)
        with self._lock:
            self.conn.execute(f"UPDATE automation_jobs SET {cols} WHERE id=?", (*fields.values(), job_id)); self.conn.commit()

    def automation_retry(self, job_id: int) -> None:
        self.automation_update(job_id, status="queued", progress=0, error=None, finished_at=None)

    def automation_cancel(self, job_id: int) -> None:
        self.automation_update(job_id, status="cancelled", finished_at=time.time())

    # --- eklentiler (v2.0) ------------------------------------------------
    def eklenti_listesi(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM plugins ORDER BY ad").fetchall()
        return [_eklenti_coz(dict(r)) for r in rows]

    def eklenti(self, ad: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM plugins WHERE ad = ?", (ad,)).fetchone()
        return _eklenti_coz(dict(row)) if row else None

    def eklenti_yaz(self, kayit: dict) -> None:
        """Idempotent kayit: ayni ad ikinci kez yazilirsa SATIR GUNCELLENIR."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO plugins(ad, baslik, surum, kaynak, giris, manifest, izinler,"
                " domainler, ayarlar, etkin, son_hata, onceki_surum, kurulum_at, guncelleme_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(ad) DO UPDATE SET baslik=excluded.baslik, surum=excluded.surum,"
                " kaynak=excluded.kaynak, giris=excluded.giris, manifest=excluded.manifest,"
                " izinler=excluded.izinler, domainler=excluded.domainler,"
                " ayarlar=excluded.ayarlar, etkin=excluded.etkin, son_hata=excluded.son_hata,"
                " onceki_surum=excluded.onceki_surum, guncelleme_at=excluded.guncelleme_at",
                (
                    str(kayit["ad"]),
                    str(kayit.get("baslik") or ""),
                    str(kayit.get("surum") or ""),
                    str(kayit.get("kaynak") or ""),
                    str(kayit.get("giris") or ""),
                    json.dumps(kayit.get("manifest") or {}, ensure_ascii=False),
                    json.dumps(kayit.get("izinler") or [], ensure_ascii=False),
                    json.dumps(kayit.get("domainler") or [], ensure_ascii=False),
                    json.dumps(kayit.get("ayarlar") or {}, ensure_ascii=False),
                    1 if kayit.get("etkin") else 0,
                    str(kayit.get("son_hata") or "")[:500],
                    str(kayit.get("onceki_surum") or ""),
                    float(kayit.get("kurulum_at") or time.time()),
                    float(kayit.get("guncelleme_at") or time.time()),
                ),
            )
            self.conn.commit()

    def eklenti_alan_yaz(self, ad: str, **alanlar: Any) -> None:
        """Yalniz bilinen alanlari gunceller (etkin/son_hata/ayarlar/...)."""
        izinli = {"baslik", "surum", "kaynak", "giris", "etkin", "son_hata",
                  "onceki_surum", "guncelleme_at"}
        json_alan = {"manifest", "izinler", "domainler", "ayarlar"}
        setler, degerler = [], []
        for anahtar, deger in alanlar.items():
            if anahtar in json_alan:
                setler.append(f"{anahtar} = ?")
                degerler.append(json.dumps(deger, ensure_ascii=False))
            elif anahtar in izinli:
                setler.append(f"{anahtar} = ?")
                degerler.append(int(deger) if anahtar == "etkin" else deger)
        if not setler:
            return
        degerler.append(ad)
        with self._lock:
            self.conn.execute(
                f"UPDATE plugins SET {', '.join(setler)} WHERE ad = ?", degerler)
            self.conn.commit()

    def eklenti_sil(self, ad: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM plugins WHERE ad = ?", (ad,))
            self.conn.commit()

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


def _eklenti_coz(satir: dict) -> dict:
    """DB satirindaki JSON sutunlarini Python nesnesine cevirir.

    Bozuk JSON kaydi UYGULAMAYI DUSURMEZ: bos degerle devam eder, kullanici
    eklentiyi kaldirip yeniden kurabilir."""
    for anahtar, bos in (("manifest", {}), ("izinler", []),
                         ("domainler", []), ("ayarlar", {})):
        try:
            satir[anahtar] = json.loads(satir.get(anahtar) or "null")
        except (TypeError, ValueError):
            satir[anahtar] = bos
        if satir[anahtar] is None:
            satir[anahtar] = bos
    satir["etkin"] = bool(satir.get("etkin"))
    return satir
