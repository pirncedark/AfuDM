"""Real aria2 keeps authenticated transfers working without persisting credentials."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from core import paths  # noqa: E402
from core import daemon as daemon_module  # noqa: E402
from core.daemon import Aria2Daemon, sanitize_session_file  # noqa: E402
from core.manager import Manager  # noqa: E402
from fake_http import SunucuAyarlari, baslat  # noqa: E402


def main() -> int:
    if not paths.ARIA2C.is_file():
        print(f"ATLANDI: bundled aria2 yok: {paths.ARIA2C}")
        return 1
    root = Path(tempfile.mkdtemp(prefix="afudm_cookie_session_"))
    data, downloads = root / "data", root / "downloads"
    paths.DATA, paths.DOWNLOADS, paths.PLUGINS = data, downloads, root / "plugins"
    paths.SECRET_FILE = data / "rpc_secret.txt"
    paths.SESSION_FILE = data / "aria2.session"
    paths.ARIA2_LOG = data / "aria2.log"
    paths.ensure_dirs()
    probe = "AFUDM_SYNTHETIC_COOKIE_PROBE"
    settings = SunucuAyarlari(veri=b"x" * 16_000_000, gecikme_sn=0.02,
                              zorunlu_cerez=probe)
    port, httpd = baslat(settings)
    original_args = daemon_module._args

    def local_only_args(*args):
        values = original_args(*args)
        return [
            "--enable-dht=false" if item == "--enable-dht=true" else
            "--enable-peer-exchange=false" if item == "--enable-peer-exchange=true" else
            "--bt-enable-lpd=false" if item == "--bt-enable-lpd=true" else item
            for item in values
        ]

    daemon_module._args = local_only_args
    daemon = Aria2Daemon(download_dir=str(downloads))
    ok = False
    try:
        rpc = daemon.start()
        rpc.change_global_option({"max-overall-download-limit": "64K"})
        gid = rpc.add_uri([f"http://127.0.0.1:{port}/cookie.bin"], {
            "dir": str(downloads), "out": "cookie.bin", "split": "1",
            "max-connection-per-server": "1", "max-tries": "1",
            "header": [f"Cookie: {probe}"],
        })
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                state = rpc.tell_status(gid)
            except Exception:
                state = {}
            if any(req["headers"].get("Cookie") == probe for req in settings.log):
                break
            if state.get("status") == "error":
                break
            time.sleep(0.05)
        request_authenticated = any(req["headers"].get("Cookie") == probe
                                    for req in settings.log)
        daemon.save_session()
        session = paths.SESSION_FILE.read_text(encoding="utf-8", errors="replace")
        transfer_status = rpc.tell_status(gid).get("status")
        # Saving a safe recovery session must not alter the live RPC task.
        still_running = transfer_status == "active"
        daemon.stop()
        session = paths.SESSION_FILE.read_text(encoding="utf-8", errors="replace")
        marker = json.loads(paths.SESSION_FILE.with_name("aria2.auth-required.json").read_text("utf-8"))
        no_credentials = ("Cookie" not in session and "Authorization" not in session
                          and not re.search(r"(?im)^\s*header\s*=\s*(?:cookie|authorization)\s*:", session)
                          and probe not in session)
        paused_for_renewal = f"gid={gid}" in session and "pause=true" in session and gid in marker
        view = Manager.__new__(Manager)
        view._auth_required_gids = set(marker)
        row_data = {
            "id": 1, "gid": gid, "kind": "http", "title": "cookie.bin", "source": "http://127.0.0.1/",
        }
        view.store = type("StoreView", (), {
            "by_gid": lambda _self, _gid: row_data,
            "by_id": lambda _self, _row_id: row_data,
        })()
        item = view._shape_aria2({"gid": gid, "status": "paused", "files": []})
        readable_error = (item["status"] == "error" and "Cookie/Authorization" in item["errorMessage"]
                          and "Yenile" in item["errorMessage"])
        try:
            view.resume(gid)
            resume_blocked = False
        except ValueError:
            resume_blocked = True
        try:
            view.retry(1)
            retry_blocked = False
        except ValueError as exc:
            retry_blocked = "Yenile" in str(exc)
        class ResumeRPC:
            def __init__(self): self.unpaused = []
            def tell_active(self): return []
            def tell_waiting(self, *_args): return []
            def tell_stopped(self, *_args): return [{"gid": gid, "status": "paused"}]
            def unpause(self, value): self.unpaused.append(value)
        view.rpc = ResumeRPC()
        view.store.list = lambda: []
        view.resume_all()
        resume_all_blocked = gid not in view.rpc.unpaused
        # Authorization headers use the same scrub path while ordinary headers survive.
        paths.SESSION_FILE.write_text(
            "http://127.0.0.1/auth\n gid=auth-gid\n header=Authorization: TEST_AUTH_SECRET\n header=Referer: http://127.0.0.1/\n",
            encoding="utf-8")
        auth_marked = sanitize_session_file()
        auth_session = paths.SESSION_FILE.read_text("utf-8")
        auth_scrubbed = ("Authorization" not in auth_session and "TEST_AUTH_SECRET" not in auth_session
                         and "Referer: http://127.0.0.1/" in auth_session
                         and "pause=true" in auth_session and "auth-gid" in auth_marked)
        ok = (request_authenticated and still_running and no_credentials and paused_for_renewal
              and readable_error and resume_blocked and retry_blocked and resume_all_blocked and auth_scrubbed)
        print(f"{'GECTI' if ok else 'BASARISIZ'}: cookie istegi={request_authenticated}, "
              f"canli indirme={still_running}, session temiz={no_credentials}, "
              f"yenileme icin duraklatildi={paused_for_renewal}, hata acik={readable_error}, "
              f"yenilemeden devam engelli={resume_blocked}, retry yenilemeye yönlendiriyor={retry_blocked}, "
              f"tumunu surdurmeden koruma={resume_all_blocked}, "
              f"Authorization temizleme={auth_scrubbed}")
        return 0 if ok else 1
    except Exception as exc:
        print(f"BASARISIZ: {type(exc).__name__}: {exc}")
        return 1
    finally:
        daemon.stop()
        httpd.shutdown()
        httpd.server_close()
        daemon_module._args = original_args
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
