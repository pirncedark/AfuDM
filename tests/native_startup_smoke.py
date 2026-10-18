"""Opt-in real WebView2 startup smoke, bounded and isolated from user data.

Run on Windows with pywebview/WebView2: python tests/native_startup_smoke.py
Not part of the offline test runner. Creates and closes only its own windows.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def child():
    import webview
    from core import paths
    with tempfile.TemporaryDirectory(prefix="afudm-native-", ignore_cleanup_errors=True) as directory:
        base = Path(directory)
        for name in ("DATA", "DOWNLOADS", "PLUGINS", "PLUGIN_YEDEK", "DB_PATH",
                     "SESSION_FILE", "ARIA2_LOG", "SECRET_FILE", "API_TOKEN_FILE", "TRACKERS_CACHE"):
            setattr(paths, name, base / getattr(paths, name).relative_to(ROOT))
        from core.db import Store
        store = Store()
        store.set("api_listen_port", 34997)
        for key in ("auto_update_trackers", "automation_enabled", "sunucu_acik",
                    "clipboard_watch", "guncelleme_otomatik", "lan_erisimi"):
            store.set(key, False)
        store.conn.close()
        import app
        outcome = []
        original_create = webview.create_window
        original_start = webview.start

        def create(*args, **kwargs):
            return original_create(*args, **kwargs)

        def verify():
            try:
                windows = list(webview.windows)
                assert len(windows) == 2, f"expected two windows, got {len(windows)}"
                for index, window in enumerate(windows):
                    if index == 1:
                        window.show()
                    assert window.events._pywebviewready.wait(25), f"native bridge {index} readiness timeout"
                    print(f"native bridge {index} ready", flush=True)
                prompt = windows[1]
                names = prompt.evaluate_js("Object.keys(window.pywebview.api).sort()")
                expected = sorted(name for name in dir(app.IndirmePenceresiApi)
                                  if not name.startswith('_')
                                  and callable(getattr(app.IndirmePenceresiApi, name)))
                assert names == expected, f"unexpected prompt API keys: {names}"
                state = prompt.evaluate_js("window.pywebview.api.pencere_durumu()")
                assert state == {"reset": 0, "hidden": False}, f"prompt bridge call failed: {state}"
                assert windows[0].evaluate_js("typeof window.pywebview.api.snapshot") == "function"
                api = windows[0]._js_api.local_api
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{api.port}/ping", timeout=3) as response:
                    assert json.loads(response.read()) == {"ok": True, "app": "AfuDM"}
                outcome.append("PASS: both native bridges ready; prompt API exact; RPC call and /ping OK")
            except Exception as exc:
                outcome.append(f"FAIL: {type(exc).__name__}: {exc}")
            finally:
                windows = list(webview.windows)
                if windows:
                    windows[0]._js_api._cikiliyor = True
                    for window in reversed(windows):
                        window.destroy()

        def start(callback, **kwargs):
            def started():
                callback()
                threading.Thread(target=verify, daemon=True).start()
            return original_start(started, gui="edgechromium", **kwargs)

        with patch.object(app, "calisan_ornege_yolla", return_value=False), \
             patch("api.server._dosya_iznini_kisitla"), \
             patch.object(app.smb_paylasim, "artiklari_temizle"), \
             patch.object(app.engines, "eksikler", return_value=[]), \
             patch.object(app, "build_tray", return_value=None), \
             patch("core.manager.WindowsIntegration", return_value=None), \
             patch.object(app.clipboard.ClipboardWatcher, "prime"), \
             patch.object(app.clipboard.ClipboardWatcher, "start"), \
             patch.object(app.clipboard.ClipboardWatcher, "stop"), \
             patch.object(webview, "create_window", side_effect=create), \
             patch.object(webview, "start", side_effect=start):
            sys.argv = ["app.py"]
            result = app.main()
        print(outcome[0] if outcome else f"FAIL: main exited {result} without checking bridges", flush=True)
        return 0 if outcome and outcome[0].startswith("PASS:") else 1


if __name__ == "__main__":
    if "--child" in sys.argv:
        sys.exit(child())
    import psutil  # clean up only this probe's process tree on timeout
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child"],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        stdout, stderr = process.communicate(timeout=80)
        print(stdout, end="")
        if process.returncode:
            print(stderr[-6000:], end="")
        sys.exit(process.returncode)
    except subprocess.TimeoutExpired:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for owned in children + [parent]:
            try:
                owned.terminate()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(children + [parent], timeout=5)
        print("FAIL: native smoke exceeded 80 seconds")
        sys.exit(1)
