"""Guncelleme akisinin agsiz, yerel sunuculu testleri."""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import subprocess
import tempfile
import threading
import zipfile
import sys
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import guncelleme

# CI ortaminda pywebview kurulu degil. app import edilirken sadece modul
# seviyesindeki tip ipuclari gerekir; dialog sabitleri runtime cagrilari icin.
if sys.modules.get("webview") is None:
    webview = types.ModuleType("webview")
    webview.FOLDER_DIALOG = 1
    webview.OPEN_DIALOG = 2
    sys.modules["webview"] = webview

from app import Api


class Sunucu(http.server.BaseHTTPRequestHandler):
    dosyalar: dict[str, bytes] = {}

    def do_GET(self):
        veri = self.dosyalar.get(self.path)
        if veri is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *_args):
        pass


def suite():
    server = http.server.HTTPServer(("127.0.0.1", 0), Sunucu)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    onceki_onek = guncelleme.IZINLI_ONEK
    guncelleme.IZINLI_ONEK = base + "/"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_zip = root / "release.zip"
            with zipfile.ZipFile(app_zip, "w") as zf:
                zf.writestr("AfuDM/AfuDM.exe", b"exe")
                zf.writestr("AfuDM/core.py", b"code")
            zip_bytes = app_zip.read_bytes()
            zip_name = "AfuDM-v2.10.0-win64.zip"
            sha_name = zip_name + ".sha256"

            def release(version, *, actual=zip_bytes, checksum=None):
                digest = checksum or hashlib.sha256(actual).hexdigest()
                sha = f"{digest}  {zip_name}".encode()
                Sunucu.dosyalar = {
                    "/release": json.dumps({
                        "tag_name": "v" + version, "body": "release notes",
                        "draft": False, "prerelease": False,
                        "assets": [
                            {"name": zip_name, "browser_download_url": base + "/app.zip"},
                            {"name": sha_name, "browser_download_url": base + "/app.sha"},
                        ],
                    }).encode(),
                    "/app.zip": actual, "/app.sha": sha,
                }

            release("2.10.0")
            with mock.patch.object(guncelleme.surum, "SURUM", "2.9.9"), mock.patch.object(guncelleme.paths, "DATA", root / "data"):
                bilgi = guncelleme.kontrol(base + "/release")
                assert bilgi["ok"] and bilgi["var"] and bilgi["yeni"] == "2.10.0"
                result = guncelleme.indir_ve_dogrula(bilgi)
                assert result["ok"] and (root / "data/guncelleme/yeni/AfuDM/AfuDM.exe").is_file()
                assert guncelleme.hazir(), "verified package must be available after restart"
                exe = root / "data/guncelleme/yeni/AfuDM/AfuDM.exe"
                exe.write_bytes(b"changed after verification")
                assert not guncelleme.hazir(), "changed staging must never be installed"
                assert guncelleme.indir_ve_dogrula(bilgi)["ok"]

                with mock.patch.object(guncelleme.sys, "frozen", True, create=True), \
                     mock.patch.object(guncelleme.subprocess, "Popen") as process:
                    assert guncelleme.uygula(son_kontrol=lambda: False)["bekle"]
                    process.assert_not_called()

                late_api = Api.__new__(Api)
                late_api._guncelleme_kilidi = threading.Lock()
                late_api._cikiliyor = False
                late_api._window = mock.Mock()
                late_api._bekleyenler = mock.Mock()
                late_api._bekleyenler.ozet.return_value = []
                late_api.manager = mock.Mock()
                late_api.manager.store.get.side_effect = lambda key, default=None: default
                live = {"engine_ok": True, "items": [], "stat": {"numActive": 0}}
                late_api.manager.snapshot.side_effect = lambda: live
                real_ready = guncelleme.hazir
                def transfer_during_validation():
                    verified = real_ready()
                    live["stat"]["numActive"] = 1
                    return verified
                with mock.patch.object(guncelleme.sys, "frozen", True, create=True), \
                     mock.patch.object(guncelleme, "hazir", side_effect=transfer_during_validation), \
                     mock.patch.object(guncelleme.subprocess, "Popen") as process:
                    assert late_api.guncelleme_uygula(True)["bekle"]
                    process.assert_not_called()
                    late_api._window.destroy.assert_not_called()
                    assert not late_api._cikiliyor

                for bad_info in ({**bilgi, "zip_url": "https://example.test/app.zip"},
                                 {**bilgi, "sha_url": "https://example.test/app.sha"},
                                 {**bilgi, "yeni": "2.9.0"}):
                    with mock.patch.object(guncelleme, "_indir") as download:
                        assert not guncelleme.indir_ve_dogrula(bad_info)["ok"]
                        download.assert_not_called()
                assert guncelleme.indir_ve_dogrula(bilgi)["ok"]

                with mock.patch.object(guncelleme.surum, "SURUM", "2.10.0"):
                    current = guncelleme.kontrol(base + "/release")
                assert current["ok"] and not current["var"]
                older = guncelleme.kontrol(base + "/release")
                assert older["var"]  # sayisal karsilastirma: 2.10.0 > 2.9.9

                release("2.10.0", checksum="0" * 64)
                bad = guncelleme.kontrol(base + "/release")
                failed = guncelleme.indir_ve_dogrula(bad)
                assert not failed["ok"]
                assert not guncelleme.hazir(), "failed download must invalidate old staging"
                assert not list((root / "data/guncelleme").glob("*.zip"))

                slip = root / "slip.zip"
                with zipfile.ZipFile(slip, "w") as zf:
                    zf.writestr("../escape.txt", "bad")
                release("2.10.0", actual=slip.read_bytes())
                slip_info = guncelleme.kontrol(base + "/release")
                assert not guncelleme.indir_ve_dogrula(slip_info)["ok"]

                down = guncelleme.kontrol("http://127.0.0.1:1/no-server")
                assert not down["ok"] and "hata" in down

                with mock.patch.object(guncelleme.sys, "frozen", True, create=True), \
                     mock.patch.object(guncelleme.subprocess, "Popen") as process:
                    assert not guncelleme.uygula()["ok"]
                    process.assert_not_called()
                release("2.10.0")
                assert guncelleme.indir_ve_dogrula(bilgi)["ok"]

                plain = guncelleme.uygula()
                assert plain == {"ok": False, "hata": "Güncelleme yalnız paketli sürümde çalışır."}
                with mock.patch.object(guncelleme.sys, "frozen", True, create=True), \
                     mock.patch.object(guncelleme.paths, "BASE", root / "base"), \
                     mock.patch.object(guncelleme.paths, "DATA", root / "data"), \
                     mock.patch.object(guncelleme.subprocess, "Popen"):
                    applied = guncelleme.uygula()
                    assert applied["ok"]
                    script = (root / "data/guncelleme/uygula.ps1").read_text(encoding="utf-8")
                    for folder in ("data", "downloads", "plugins"):
                        assert folder in script

            # Başarısız kontrol başarısız denemeyi 24 saatlik cache'e yazmamalı.
            api = Api.__new__(Api)
            with mock.patch("app.paths.DATA", root / "api-data"), \
                 mock.patch("app.guncelleme.kontrol", return_value={"ok": False}):
                assert not api.guncelleme_kontrol()["ok"]
                kontrol_kaydi = root / "api-data/guncelleme/kontrol.json"
                assert not kontrol_kaydi.exists()

            with mock.patch("app.paths.DATA", root / "api-data"), \
                 mock.patch("app.guncelleme.kontrol", return_value={"ok": True, "var": False}):
                assert api.guncelleme_kontrol()["ok"]
                assert json.loads(kontrol_kaydi.read_text(encoding="utf-8"))["zaman"] > 0

            api.manager = mock.Mock()
            api.manager.store.get.side_effect = lambda key, default=None: default
            api.manager.snapshot.return_value = {"engine_ok": True, "items": [], "stat": {}}
            api._bekleyenler = mock.Mock()
            api._bekleyenler.ozet.return_value = []
            api._window = mock.Mock()
            api._cikiliyor = False
            api._guncelleme_kilidi = threading.Lock()
            with mock.patch("app.paths.DATA", root / "api-data"):
                assert api.guncelleme_otomatik_ayarla(True)["ok"]
                assert not kontrol_kaydi.exists()

            # Restarts must never interrupt transfers, seeds, pending approvals, or an offline engine.
            for snap in ({"engine_ok": False, "items": [], "stat": {}},
                         {"engine_ok": True, "items": [{"status": "active"}], "stat": {}},
                         {"engine_ok": True, "items": [{"status": "waiting"}], "stat": {}},
                         {"engine_ok": True, "items": [{"status": "queued"}], "stat": {}},
                         {"engine_ok": True, "items": [{"status": "seeding"}], "stat": {}},
                         {"engine_ok": True, "items": [], "stat": {"numActive": 1}}):
                api.manager.snapshot.return_value = snap
                with mock.patch("app.guncelleme.uygula") as apply:
                    assert api.guncelleme_uygula()["bekle"]
                    apply.assert_not_called()
                    assert not api._cikiliyor
            api.manager.snapshot.return_value = {"engine_ok": True, "items": [], "stat": {}}
            api._bekleyenler.ozet.return_value = [{"id": 1}]
            with mock.patch("app.guncelleme.uygula") as apply:
                assert api.guncelleme_uygula()["bekle"]
                apply.assert_not_called()
            api._bekleyenler.ozet.return_value = []
            api.manager.store.get.side_effect = lambda key, default=None: False
            with mock.patch("app.guncelleme.uygula") as apply:
                assert api.guncelleme_uygula(True)["iptal"]
                apply.assert_not_called()
            api.manager.store.get.side_effect = lambda key, default=None: default
            with mock.patch("app.guncelleme.uygula", return_value={"ok": True}):
                assert api.guncelleme_uygula(True)["ok"]
                assert api._cikiliyor
                api._window.destroy.assert_called_once()

            # A concurrent/retried request must not start a second replacement process.
            api._cikiliyor = False
            api._window.destroy.reset_mock()
            entered, release_apply = threading.Event(), threading.Event()
            results = []
            def slow_apply(**kwargs):
                entered.set()
                assert release_apply.wait(3)
                return {"ok": True}
            with mock.patch("app.guncelleme.uygula", side_effect=slow_apply) as apply:
                first = threading.Thread(target=lambda: results.append(api.guncelleme_uygula(True)))
                second = threading.Thread(target=lambda: results.append(api.guncelleme_uygula(True)))
                first.start()
                assert entered.wait(2)
                second.start()
                release_apply.set()
                first.join(3)
                second.join(3)
                assert len(results) == 2 and all(r["ok"] for r in results)
                assert apply.call_count == 1, "only one replacement process may be launched"
                api._window.destroy.assert_called_once()

            # Execute the real replacement script in an isolated installation.
            if os.name == "nt":
                install = root / "installed"
                data = install / "data"
                source = data / "guncelleme/yeni/AfuDM"
                for rel, content in {"AfuDM.exe": b"old", "ui/app.js": b"old-ui",
                                     "data/history.db": b"history", "downloads/file.zip": b"download",
                                     "plugins/user.py": b"plugin", "engine/ffmpeg.exe": b"user-engine"}.items():
                    p = install / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(content)
                for rel, content in {"AfuDM.exe": b"new", "ui/app.js": b"new-ui",
                                     "engine/aria2c.exe": b"new-engine",
                                     "data/history.db": b"must-not-replace"}.items():
                    p = source / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(content)
                with mock.patch.object(guncelleme.paths, "BASE", install), \
                     mock.patch.object(guncelleme.paths, "DATA", data), \
                     mock.patch.object(guncelleme.os, "getpid", return_value=2147483647):
                    # Only replace process launch, not file-copy or preservation behavior.
                    script = root / "apply-test.ps1"
                    script.write_text('function Start-Process { param($FilePath) }\n'
                                      + guncelleme._uygulama_betigi(), encoding="utf-8-sig")
                run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                      "-File", str(script)], capture_output=True, timeout=30)
                assert run.returncode == 0, run.stderr.decode(errors="replace")
                for rel, expected in {"AfuDM.exe": b"new", "ui/app.js": b"new-ui",
                                      "data/history.db": b"history", "downloads/file.zip": b"download",
                                      "plugins/user.py": b"plugin", "engine/ffmpeg.exe": b"user-engine",
                                      "engine/aria2c.exe": b"new-engine",
                                      "data/guncelleme/yedek/AfuDM.exe": b"old"}.items():
                    assert (install / rel).read_bytes() == expected, rel
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    suite()
    print("OK: guncelleme akis testleri")
