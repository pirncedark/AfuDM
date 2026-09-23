"""Restore keeps every service's shared Store usable and fresh."""
from __future__ import annotations

import tempfile
import sys
import shutil
import threading
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import paths
from core.automation import AutomationWorker
from core.db import Store
from core.eklenti import EklentiServisi
from core.erisim import ErisimDeposu
from core.reliability import Reliability
from core.servis import AfuDMServis
from core.windows_integration import WindowsIntegration


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="afudm_restore_store_"))
    paths.DATA, paths.DB_PATH = root / "data", root / "data" / "afudm.db"
    paths.DOWNLOADS, paths.PLUGINS = root / "downloads", root / "plugins"
    paths.ensure_dirs()

    class Manager:
        pass

    manager = Manager()
    manager.store = Store(str(paths.DB_PATH))
    manager.automation = AutomationWorker(manager.store, lambda *_: None)
    manager.eklentiler = EklentiServisi(manager.store)
    manager.windows = WindowsIntegration(manager.store)
    service = AfuDMServis(manager)
    manager.servis = service
    manager.erisim = service.erisim
    manager.reliability = Reliability(manager)

    backup_db = root / "backup-source.db"
    backup_store = Store(str(backup_db))
    backup_store.set("restore_probe", "from-backup")
    ErisimDeposu(backup_store).anahtar_olustur("restore-access", "salt_okur")
    backup_store.conn.close()
    archive = paths.DATA / "backups" / "known.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.write(backup_db, "afudm.db")

    shared = manager.store
    refs = {
        "manager": manager.store,
        "automation": manager.automation.store,
        "plugins": manager.eklentiler.store,
        "windows": manager.windows.store,
        "service": service.store,
        "access": service.erisim.store,
    }
    restore_done = threading.Event()
    restore_errors = []

    def restore_in_thread():
        try:
            manager.reliability.restore(str(archive))
        except Exception as exc:
            restore_errors.append(exc)
        finally:
            restore_done.set()

    with shared._lock:
        worker = threading.Thread(target=restore_in_thread)
        worker.start()
        time.sleep(0.1)
        blocked_during_swap = not restore_done.is_set()
    worker.join(timeout=10)
    results = {}
    for name, store in refs.items():
        try:
            results[name] = store.get("restore_probe")
        except Exception as exc:  # report the exact old-connection failure
            results[name] = f"{type(exc).__name__}: {exc}"
    try:
        access_names = [key["ad"] for key in service.erisim.anahtarlar()]
    except Exception as exc:
        access_names = [f"{type(exc).__name__}: {exc}"]

    ok = (blocked_during_swap and not restore_errors and not worker.is_alive()
          and manager.store is shared and all(v == "from-backup" for v in results.values())
          and access_names == ["restore-access"])
    print(f"{'GECTI' if ok else 'BASARISIZ'}: restore sonrası tüm Store referansları yeni veriyi okuyor: "
          f"{results}; erisim={access_names}; degisim eszamanli DB erisimine kapali={blocked_during_swap}")
    manager.store.conn.close()
    shutil.rmtree(root, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
