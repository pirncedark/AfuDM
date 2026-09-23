"""v2.3 reliability service.  All operations are explicit and preserve originals."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
import urllib.request
import zipfile
from pathlib import Path

from . import engines, paths

_SECRET = re.compile(r"(?i)(token|password|passwd|cookie|authorization|api[_-]?key)\s*([:=])\s*([^\s,&\"]+)")
_URL_SECRET = re.compile(r"([?&](?:token|key|sig|signature|password|auth)=[^&#\s]+)", re.I)

def mask(value: str) -> str:
    """Remove credentials before anything can be displayed or archived."""
    value = _URL_SECRET.sub(lambda m: m.group(1).split("=", 1)[0] + "=***", str(value))
    return _SECRET.sub(lambda m: m.group(1) + m.group(2) + "***", value)

class Reliability:
    def __init__(self, manager) -> None:
        self.manager = manager

    def integrity(self) -> dict:
        with self.manager.store._lock:
            rows = self.manager.store.conn.execute("PRAGMA integrity_check").fetchall()
        messages = [str(r[0]) for r in rows]
        ok = messages == ["ok"]
        return {"ok": ok, "status": "ok" if ok else "corrupt", "details": messages,
                "action": "none" if ok else "restore_backup", "checked_at": time.time()}

    def backup(self, reason: str = "manual") -> dict:
        paths.ensure_dirs(); folder = paths.DATA / "backups"; folder.mkdir(exist_ok=True)
        target = folder / f"afudm-{time.strftime('%Y%m%d-%H%M%S')}-{reason}.zip"
        # SQLite's backup API takes a consistent snapshot even while UI writes.
        temp = folder / (target.stem + ".db")
        dst = sqlite3.connect(temp)
        try:
            with self.manager.store._lock:
                self.manager.store.conn.backup(dst)
        finally:
            dst.close()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(temp, "afudm.db")
            z.writestr("manifest.json", json.dumps({"created_at": time.time(), "reason": reason,
                "contents": ["settings", "download_history"]}))
        temp.unlink(missing_ok=True)
        return {"ok": True, "path": str(target), "created_at": time.time()}

    def backups(self) -> dict:
        folder = paths.DATA / "backups"
        files = sorted(folder.glob("afudm-*.zip"), reverse=True) if folder.exists() else []
        return {"ok": True, "items": [{"path": str(p), "name": p.name, "size": p.stat().st_size,
                 "modified": p.stat().st_mtime} for p in files]}

    def restore(self, archive: str) -> dict:
        archive_path = Path(archive).resolve()
        backup_root = (paths.DATA / "backups").resolve()
        if backup_root not in archive_path.parents or not archive_path.is_file():
            raise ValueError("yalniz AfuDM yedekleri geri yuklenebilir")
        before = self.backup("before-restore")
        with zipfile.ZipFile(archive_path) as z:
            if "afudm.db" not in z.namelist(): raise ValueError("yedekte veritabani yok")
            temp = paths.DATA / "restore.tmp.db"; temp.write_bytes(z.read("afudm.db"))
        db = sqlite3.connect(temp)
        try:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                temp.unlink(missing_ok=True); raise ValueError("yedek butun degil")
        finally:
            db.close()
        # Keep Store's identity stable: workers and service facades retain this
        # object. Its lock serializes the swap against every Store operation.
        store = self.manager.store
        with store._lock:
            store.conn.close()
            shutil.move(str(temp), str(paths.DB_PATH))
            # Reuse the migration-safe constructor, then transplant its live
            # connection into the shared Store while all readers are blocked.
            from .db import Store
            replacement = Store(str(paths.DB_PATH))
            store.conn = replacement.conn
        return {"ok": True, "pre_restore_backup": before["path"], "restart_required": True}

    def diagnostics_preview(self) -> dict:
        events = self.manager.store.recent_events(150)
        data = {"generated_at": time.time(), "integrity": self.integrity(),
                "engines": engines.durum(), "settings": self.manager.store.all_settings(),
                "events": events}
        safe = json.loads(mask(json.dumps(data, ensure_ascii=False)))
        return {"ok": True, "preview": safe, "masked": True}

    def diagnostics_export(self) -> dict:
        preview = self.diagnostics_preview()["preview"]
        folder = paths.DATA / "diagnostics"; folder.mkdir(exist_ok=True)
        target = folder / f"afudm-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.json"
        target.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "path": str(target), "masked": True}

    def health(self) -> dict:
        e = engines.durum()
        return {"ok": True, "aria2": {"available": bool(e.get("aria2c", {}).get("kullanilabilir")),
                "running": self.manager.rpc.alive()}, "yt_dlp": e.get("yt-dlp", e.get("ytdlp", {}))}

    def restart_engine(self) -> dict:
        # Deliberately not automatic: active jobs may be interrupted but aria2 session persists.
        self.manager.daemon.stop(); self.manager.rpc = self.manager.daemon.start()
        return {"ok": bool(self.manager.rpc.alive()), "message": "motor yeniden baslatildi"}

    def recovery_preview(self, row_id: int) -> dict:
        row = self.manager.store.by_id(int(row_id))
        if not row: raise ValueError("indirme bulunamadi")
        target = Path(row.get("dest_dir") or self.manager.current_download_dir()) / (row.get("filename") or row.get("title") or "")
        control = Path(str(target) + ".aria2")
        local = target.stat().st_size if target.is_file() else 0
        remote = {"etag": None, "length": None, "range": False}
        try:
            req = urllib.request.Request(row["source"], method="HEAD")
            with urllib.request.urlopen(req, timeout=8) as r:
                remote = {"etag": r.headers.get("ETag"), "length": int(r.headers.get("Content-Length") or 0),
                          "range": "bytes" in r.headers.get("Accept-Ranges", "").lower()}
        except Exception as exc: remote["error"] = type(exc).__name__
        verified = local if remote["range"] and remote["etag"] else 0
        return {"ok": True, "original_preserved": True, "control_file": control.exists(), "local_bytes": local,
                "remote": remote, "hash_verified_bytes": 0, "source_verified_bytes": verified,
                "unverified_bytes": max(0, local - verified),
                "can_attempt": bool(control.exists() and remote["range"]),
                "warning": "Dosya boyutu parcalarin saglamligini kanitlamaz; yalniz listelenen dogrulamalar gecerlidir."}
