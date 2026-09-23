"""Check whether aria2 serializes a synthetic Cookie header in its session."""
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
    root = Path(tempfile.mkdtemp(prefix="afudm_cookie_session_", dir=ROOT))
    data, downloads = root / "data", root / "downloads"
    paths.DATA, paths.DOWNLOADS, paths.PLUGINS = data, downloads, root / "plugins"
    paths.SECRET_FILE = data / "rpc_secret.txt"
    paths.SESSION_FILE = data / "aria2.session"
    paths.ARIA2_LOG = data / "aria2.log"
    paths.ensure_dirs()
    settings = SunucuAyarlari(veri=b"x" * 3_000_000, gecikme_sn=0.03)
    port, httpd = baslat(settings)
    daemon = Aria2Daemon(download_dir=str(downloads))
    probe = "AFUDM_SYNTHETIC_COOKIE_PROBE"
    try:
        rpc = daemon.start()
        rpc.change_global_option({"max-overall-download-limit": "32K"})
        gid = rpc.add_uri([f"http://127.0.0.1:{port}/cookie.bin"], {
            "dir": str(downloads), "out": "cookie.bin", "split": "1",
            "max-connection-per-server": "1", "max-tries": "1",
            "header": [f"Cookie: {probe}"]})
        deadline = time.time() + 8
        while time.time() < deadline:
            if rpc.tell_status(gid).get("status") == "active":
                break
            time.sleep(0.05)
        rpc.pause(gid)
        rpc.save_session()
        serialized = paths.SESSION_FILE.read_text(encoding="utf-8", errors="replace")
        found = probe in serialized
        print(f"D1-07 {'DOĞRULANDI' if found else 'YANLIŞ ALARM'}: synthetic Cookie header session dosyasında {'bulundu' if found else 'bulunamadı'}; içerik yazdırılmadı")
        return 0 if found else 1
    except Exception as exc:
        print(f"KALDI: {type(exc).__name__}: {exc}")
        return 1
    finally:
        daemon.stop()
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
