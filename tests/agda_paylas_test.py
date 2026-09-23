"""Agda paylas: UI -> bridge -> SMB/HTTP fallback -> QR regresyon testleri."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import Api

ROOT = Path(__file__).resolve().parents[1]


class _Store:
    def __init__(self):
        self.logs = []

    def get(self, key, default=None):
        return default

    def log(self, level, message):
        self.logs.append((level, message))


class _Manager:
    def __init__(self, path):
        self.path = path
        self.store = _Store()

    def resolve_item_path(self, gid):
        return self.path if gid == "gid-1" else None


class AgdaPaylasTest(unittest.TestCase):
    def test_share_delete_revoke_mocked_share_and_remove_staging(self):
        from api.server import _Handler
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp) / "stage"
            staging.mkdir()
            api = Api.__new__(Api)
            api.manager = _Manager(Path(temp) / "file.txt")
            api._tunel = type("Tunnel", (), {"stop": lambda self: None})()
            api._paylasim_sunucusu = type("Server", (), {"stop": lambda self: None})()
            _Handler.shared_files.clear()
            _Handler.shared_files["cleanup-token"] = {
                "path": Path(temp) / "file.txt", "created": 1,
                "share_name": "AfuDM_test", "staging_path": str(staging),
            }
            with patch("subprocess.run", return_value=__import__("subprocess").CompletedProcess([], 0)) as run:
                result = api.share_delete("cleanup-token")
            self.assertTrue(result["ok"])
            self.assertEqual(run.call_args.args[0], ["net", "share", "AfuDM_test", "/delete", "/y"])
            self.assertFalse(staging.exists())
            self.assertNotIn("cleanup-token", _Handler.shared_files)

    def test_app_close_cleans_share_with_mocked_subprocess(self):
        from api.server import _Handler
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp) / "stage"
            staging.mkdir()
            api = Api.__new__(Api)
            api.manager = _Manager(Path(temp) / "file.txt")
            api._tepsi_bildirimi = lambda: None
            api._Handler = _Handler
            _Handler.shared_files.clear()
            _Handler.shared_files["shutdown-token"] = {
                "path": Path(temp) / "file.txt", "created": 1,
                "share_name": "AfuDM_shutdown", "staging_path": str(staging),
            }
            with patch("subprocess.run", return_value=__import__("subprocess").CompletedProcess([], 0)) as run:
                api.paylasim_stop()
            self.assertEqual(run.call_args.args[0], ["net", "share", "AfuDM_shutdown", "/delete", "/y"])
            self.assertFalse(staging.exists())
            self.assertNotIn("shutdown-token", _Handler.shared_files)

    def test_app_close_reports_cleanup_failure_in_tray_notification(self):
        from api.server import _Handler
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp) / "stage"
            staging.mkdir()
            notifications = []
            api = Api.__new__(Api)
            api.manager = _Manager(Path(temp) / "file.txt")
            api._window = None
            api._tepsi = type("Tray", (), {"notify": lambda self, message, title: notifications.append((message, title))})()
            _Handler.shared_files.clear()
            _Handler.shared_files["shutdown-failure-token"] = {
                "path": Path(temp) / "file.txt", "created": 1,
                "share_name": "AfuDM_denied", "staging_path": str(staging),
            }
            failure = __import__("subprocess").CompletedProcess([], 1, "", "access denied")
            with patch("subprocess.run", return_value=failure):
                api.paylasim_stop()
            self.assertTrue(notifications)
            self.assertIn("access denied", notifications[0][0])
            self.assertEqual(notifications[0][1], "AfuDM")
            self.assertTrue(api.manager.store.logs)

    def test_backend_smb_yetkisi_yoksa_http_qr_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            dosya = Path(temp) / "telefon.pdf"
            dosya.write_bytes(b"AfuDM")
            api = Api.__new__(Api)
            api.manager = _Manager(dosya)
            api.local_api = type("Local", (), {
                "lan_adresi": lambda self: "192.168.1.20",
                "port": 6811,
            })()
            with patch("subprocess.run", side_effect=PermissionError("yonetici yetkisi gerekli")) as run:
                sonuc = api.agda_paylas("gid-1")
            self.assertTrue(sonuc["ok"])
            self.assertEqual(sonuc["transport"], "http")
            self.assertIn("/s/", sonuc["url"])
            self.assertTrue(sonuc["qr"].startswith("data:image/"))
            run.assert_called_once()

    def test_backend_smb_komutu_sahte_basariyla_unc_doner(self):
        with tempfile.TemporaryDirectory() as temp:
            dosya = Path(temp) / "arsiv.zip"
            dosya.write_bytes(b"AfuDM")
            api = Api.__new__(Api)
            api.manager = _Manager(dosya)
            api.local_api = type("Local", (), {
                "lan_adresi": lambda self: "192.168.1.20",
                "port": 6811,
            })()
            with patch("subprocess.run", return_value=__import__("subprocess").CompletedProcess([], 0)) as run:
                sonuc = api.agda_paylas("gid-1")
            self.assertTrue(sonuc["ok"])
            self.assertEqual(sonuc["transport"], "smb")
            self.assertTrue(sonuc["smb"].startswith("\\\\"))
            self.assertIn("arsiv.zip", sonuc["smb"])
            run.assert_called_once()

    def test_nonzero_smb_result_falls_back_without_recording_share(self):
        from api.server import _Handler
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "file.bin"
            source.write_bytes(b"AfuDM")
            api = Api.__new__(Api)
            api.manager = _Manager(source)
            api.local_api = type("Local", (), {
                "lan_adresi": lambda self: "192.168.1.20", "port": 6811,
            })()
            _Handler.shared_files.clear()
            failure = __import__("subprocess").CompletedProcess([], 1, "", "share denied")
            with patch("app.os.name", "nt"), patch("tempfile.gettempdir", return_value=temp), \
                    patch("subprocess.run", return_value=failure) as run:
                result = api.agda_paylas("gid-1")
            self.assertEqual(result["transport"], "http")
            token = result["token"]
            self.assertEqual(_Handler.shared_files[token]["share_name"], "")
            self.assertFalse((Path(temp) / "AfuDM-network-shares" / token).exists())
            run.assert_called_once()

    def test_ui_agda_paylas_bridge_ve_qr_akisini_tanimlar(self):
        js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
        html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
        self.assertIn('call("agda_paylas", gid)', js)
        self.assertIn('data-act="network-share"', js)
        self.assertIn('id="shareQrImg"', html)
        self.assertIn('id="shareSmbPath"', html)

    def test_headless_tikla_bridge_link_qr_ve_konsol_temiz(self):
        errors = []
        qr = Api._qr_uret("http://192.168.1.20:6811/s/fake")
        self.assertTrue(qr.startswith("data:image/png;base64,"))
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel=__import__("os").environ.get("AFUDM_TEST_BROWSER", "msedge"),
                headless=True,
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""
                window.bridgeCalls = [];
                window.fakeBackendState = {
                  items: [{gid: "gid-1", status: "complete", kind: "file", title: "telefon.pdf",
                           filename: "telefon.pdf", dir: "C:\\\\Downloads", progress: 100, size: 5}],
                  settings: {language: "tr"}, stat: {downloadSpeed: 0, uploadSpeed: 0,
                    numActive: 0, numWaiting: 0, numStopped: 1}, engine_ok: true,
                  port_status: {calisan: 6811}, lang: "tr"
                };
                const api = {
                  snapshot: async () => window.fakeBackendState,
                  port_durumu: async () => ({calisan: 6811}), api_info: async () => ({port: 6811}),
                  motor_durumu: async () => ({motorlar: {}, ilerleme: {}}),
                  surum_bilgi: async () => ({surum: "2.7.1"}),
                  telefon_durumu: async () => ({acik: false, adres: ""}),
                  reliability_integrity: async () => "OK",
                  agda_paylas: async gid => {
                    window.bridgeCalls.push(["agda_paylas", gid]);
                    return {ok: true, transport: "http", url: "http://192.168.1.20:6811/s/fake",
                      smb: String.raw`\\\\PC\\AfuDM_fake\\telefon.pdf`,
                      qr: "__REAL_QR__", warning: ""};
                  },
                  panoya_kopyala: async () => ({ok: true}),
                  control: async () => ({ok: true}),
                  share_list: async () => ({ok: true, shares: []}),
                  ayar_rozetleri: async () => ({uygulama: {}})
                };
                window.pywebview = {api};
            """.replace("__REAL_QR__", qr))
            page.goto((ROOT / "ui/index.html").as_uri())
            page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
            page.wait_for_function("state.ready === true")
            button = page.locator('button[data-act="network-share"]')
            expect(button).to_be_visible()
            button.click()
            expect(page.locator("#shareVeil")).to_have_class(__import__("re").compile(r"\bopen\b"))
            expect(page.locator("#shareLink")).to_have_value("http://192.168.1.20:6811/s/fake")
            expect(page.locator("#shareSmbPath")).to_have_value("\\\\PC\\AfuDM_fake\\telefon.pdf")
            expect(page.locator("#shareQrImg")).to_have_attribute("src", qr)
            self.assertEqual(page.evaluate("window.bridgeCalls"), [["agda_paylas", "gid-1"]])
            page.screenshot(path=str(ROOT / "_gorev" / "sonra_agda_paylas.png"), full_page=True)
            self.assertEqual(errors, [])
            browser.close()


if __name__ == "__main__":
    unittest.main()
