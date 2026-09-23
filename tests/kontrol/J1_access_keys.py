"""Access-key roles, rotation and old-key invalidation in an isolated DB."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.db import Store  # noqa: E402
from core.erisim import ErisimDeposu, ROL_SALT_OKUR, ROL_YONETICI  # noqa: E402


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="afudm_keys_", dir=ROOT))
    store = Store(str(root / "keys.db"))
    try:
        db = ErisimDeposu(store)
        admin = db.anahtar_olustur("admin smoke", ROL_YONETICI)
        reader = db.anahtar_olustur("reader smoke", ROL_SALT_OKUR)
        assert db.dogrula(admin["gizli"])["rol"] == ROL_YONETICI
        assert db.dogrula(reader["gizli"])["rol"] == ROL_SALT_OKUR
        rotated = db.anahtar_rotasyon(admin["id"])
        assert db.dogrula(admin["gizli"]) is None
        assert db.dogrula(rotated["gizli"])["rol"] == ROL_YONETICI
        print("GEÇTİ: admin/salt-okur anahtarları doğrulandı; rotasyonda eski anahtar anında geçersiz oldu")
        return 0
    finally:
        store.conn.close()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
