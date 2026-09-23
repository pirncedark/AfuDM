"""Real aria2 HTTP, pause/resume, speed option and checksum checks.

All files and the aria2 session live in a temporary folder under this worktree;
the only HTTP peer is tests.fake_http on 127.0.0.1.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from core import paths  # noqa: E402
from core.daemon import Aria2Daemon  # noqa: E402
from fake_http import SunucuAyarlari, baslat  # noqa: E402


def wait_status(rpc, gid: str, expected: str, timeout: float = 20) -> dict:
    end = time.time() + timeout
    last = {}
    while time.time() < end:
        last = rpc.tell_status(gid)
        if last.get("status") == expected:
            return last
        time.sleep(0.05)
    raise AssertionError(f"{gid}: {expected} bekleniyordu; son durum={last}")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="afudm_aria2_", dir=ROOT))
    data_dir, downloads = root / "data", root / "downloads"
    paths.DATA = data_dir
    paths.DOWNLOADS = downloads
    paths.PLUGINS = root / "plugins"
    paths.SECRET_FILE = data_dir / "rpc_secret.txt"
    paths.SESSION_FILE = data_dir / "aria2.session"
    paths.ARIA2_LOG = data_dir / "aria2.log"
    paths.ensure_dirs()

    payload = __import__("hashlib").shake_256(b"afudm-real-aria2-check").digest(3_000_000)
    settings = SunucuAyarlari(veri=payload, gecikme_sn=0.008)
    port, httpd = baslat(settings)
    daemon = Aria2Daemon(download_dir=str(downloads))
    failures = []
    try:
        rpc = daemon.start()
        rpc.change_global_option({"max-overall-download-limit": "64K"})
        url = f"http://127.0.0.1:{port}/dosya.bin"
        gid = rpc.add_uri([url], {"dir": str(downloads), "out": "indir.bin",
                                  "split": "1", "max-connection-per-server": "1",
                                  "max-tries": "1"})
        time.sleep(0.2)
        rpc.pause(gid)
        paused = wait_status(rpc, gid, "paused")
        print(f"[{'GEÇTİ' if paused.get('status') == 'paused' else 'KALDI'}] gerçek aria2 pause: {gid}")
        rpc.unpause(gid)
        rpc.change_global_option({"max-overall-download-limit": "0"})
        wait_status(rpc, gid, "complete")
        actual = (downloads / "indir.bin").read_bytes()
        ok = actual == payload
        print(f"[{'GEÇTİ' if ok else 'KALDI'}] fake_http gerçek HTTP indirme + SHA-256: {hashlib.sha256(actual).hexdigest()}")
        if not ok:
            failures.append("indirilen içerik farklı")

        rpc.change_global_option({"max-overall-download-limit": "128K"})
        limit = rpc.get_global_option().get("max-overall-download-limit", "")
        ok = int(limit) == 128 * 1024
        print(f"[{'GEÇTİ' if ok else 'KALDI'}] canlı hız seçeneği: {limit!r}")
        if not ok:
            failures.append(f"hız seçeneği uygulanmadı: {limit}")

        rpc.change_global_option({"max-overall-download-limit": "0"})
        bad = rpc.add_uri([url], {"dir": str(downloads), "out": "checksum.bin",
                                  "split": "1", "max-connection-per-server": "1",
                                  "max-tries": "1", "checksum": "sha-256=" + "0" * 64})
        status = wait_status(rpc, bad, "error")
        ok = status.get("status") == "error"
        print(f"[{'GEÇTİ' if ok else 'KALDI'}] yanlış SHA-256 indirmeyi reddetti: {status.get('errorMessage', '')}")
        if not ok:
            failures.append("yanlış checksum hata durumuna geçmedi")
    except Exception as exc:
        failures.append(str(exc))
        print(f"[KALDI] {type(exc).__name__}: {exc}")
    finally:
        daemon.stop()
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(root, ignore_errors=True)
    print(f"Sonuç: {3-len(failures)}/3 geçiş; geçici worktree verisi temizlendi")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
