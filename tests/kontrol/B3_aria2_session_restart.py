"""Verify a real active aria2 download survives a clean engine restart."""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from core import paths  # noqa: E402
from core.daemon import Aria2Daemon  # noqa: E402
from fake_http import SunucuAyarlari, baslat  # noqa: E402


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="afudm_session_", dir=ROOT))
    data, downloads = root / "data", root / "downloads"
    paths.DATA, paths.DOWNLOADS, paths.PLUGINS = data, downloads, root / "plugins"
    paths.SECRET_FILE = data / "rpc_secret.txt"
    paths.SESSION_FILE = data / "aria2.session"
    paths.ARIA2_LOG = data / "aria2.log"
    paths.ensure_dirs()
    payload = __import__("hashlib").shake_256(b"afudm-session-restart").digest(2_000_000)
    settings = SunucuAyarlari(veri=payload, gecikme_sn=0.02)
    port, httpd = baslat(settings)
    first = Aria2Daemon(download_dir=str(downloads))
    second = None
    try:
        rpc = first.start()
        rpc.change_global_option({"max-overall-download-limit": "64K"})
        gid = rpc.add_uri([f"http://127.0.0.1:{port}/session.bin"], {
            "dir": str(downloads), "out": "session.bin", "split": "1",
            "max-connection-per-server": "1", "max-tries": "1"})
        time.sleep(0.2)
        before = rpc.tell_status(gid)
        if (before.get("status") != "active"
                or int(before.get("completedLength", "0")) >= len(payload)
                or not paths.SESSION_FILE.exists()):
            raise AssertionError(f"indirme oturumu kaydedilmedi: {before}")
        rpc.pause(gid)
        before = rpc.tell_status(gid)
        if before.get("status") != "paused":
            raise AssertionError(f"restart öncesi pause uygulanmadı: {before}")
        first.stop()

        second = Aria2Daemon(download_dir=str(downloads))
        resumed_rpc = second.start()
        resumed = resumed_rpc.tell_status(gid)
        if resumed.get("status") not in {"active", "waiting", "paused"}:
            raise AssertionError(f"GID oturumdan dönmedi: {resumed}")
        resumed_rpc.change_global_option({"max-overall-download-limit": "0"})
        if resumed.get("status") == "paused":
            resumed_rpc.unpause(gid)
        deadline = time.time() + 35
        while time.time() < deadline:
            resumed = resumed_rpc.tell_status(gid)
            if resumed.get("status") == "complete":
                break
            if resumed.get("status") == "error":
                raise AssertionError(resumed.get("errorMessage"))
            time.sleep(0.1)
        actual = (downloads / "session.bin").read_bytes()
        if resumed.get("status") != "complete" or actual != payload:
            raise AssertionError(f"session resume failed: {resumed.get('status')}, {len(actual)} bytes")
        print(f"GEÇTİ: aynı GID={gid}, ilk={before.get('completedLength')} bayt; yeniden açılış sonrası SHA-256 içerik eşleşti")
        return 0
    except Exception as exc:
        print(f"KALDI: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if second:
            second.stop()
        else:
            first.stop()
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
