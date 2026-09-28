"""Guncelleme akisinin agsiz, yerel sunuculu testleri."""
from __future__ import annotations

import hashlib
import http.server
import json
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

                with mock.patch.object(guncelleme.surum, "SURUM", "2.10.0"):
                    current = guncelleme.kontrol(base + "/release")
                assert current["ok"] and not current["var"]
                older = guncelleme.kontrol(base + "/release")
                assert older["var"]  # sayisal karsilastirma: 2.10.0 > 2.9.9

                release("2.10.0", checksum="0" * 64)
                bad = guncelleme.kontrol(base + "/release")
                failed = guncelleme.indir_ve_dogrula(bad)
                assert not failed["ok"]
                assert not list((root / "data/guncelleme").glob("*.zip"))

                slip = root / "slip.zip"
                with zipfile.ZipFile(slip, "w") as zf:
                    zf.writestr("../escape.txt", "bad")
                release("2.10.0", actual=slip.read_bytes())
                slip_info = guncelleme.kontrol(base + "/release")
                assert not guncelleme.indir_ve_dogrula(slip_info)["ok"]

                down = guncelleme.kontrol("http://127.0.0.1:1/no-server")
                assert not down["ok"] and "hata" in down

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
            with mock.patch("app.paths.DATA", root / "api-data"):
                assert api.guncelleme_otomatik_ayarla(True)["ok"]
                assert not kontrol_kaydi.exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    suite()
    print("OK: guncelleme akis testleri")
