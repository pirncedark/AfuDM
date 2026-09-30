"""Real loopback requests; all persistence and ports are isolated from live AfuDM."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.server import _Handler, _ExclusiveServer
from app import Api
from core import db, kaydet


class PDFHandoffHTTPTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        data_patch = patch.object(kaydet.paths, "DATA", Path(self.tmp.name))
        data_patch.start()
        self.addCleanup(data_patch.stop)
        with patch.object(db.paths, "ensure_dirs"):
            self.store = db.Store(str(Path(self.tmp.name) / "test.db"))
        self.store.set("kaydetme_penceresi", True)
        self.requests = []
        self.api = Api.__new__(Api)
        self.api._bekleyenler = kaydet.Bekleyenler()
        self.api._indirme_penceresi = SimpleNamespace(goster=lambda: None)
        self.api.manager = SimpleNamespace(store=self.store, detect_kind=lambda url: "http",
            current_download_dir=lambda: self.tmp.name, add=self.add)
        self.api.servis = SimpleNamespace(hedef_klasor=lambda *args: self.tmp.name)
        self.patches = [patch.object(_Handler, "manager", self.api.manager),
                        patch.object(_Handler, "token", "isolated-test-token"),
                        patch.object(_Handler, "on_ask", self.api.tarayicidan_sor),
                        patch.object(_Handler, "_rate", {})]
        for p in self.patches: p.start()
        self.httpd = _ExclusiveServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def add(self, request):
        self.requests.append(request)
        return {"gid": "test-pdf"}

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        for p in reversed(self.patches): p.stop()
        self.store.conn.close()
        self.tmp.cleanup()

    def post(self, data, token="isolated-test-token", path="/add"):
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request("POST", path, json.dumps(data),
                           {"Content-Type": "application/json", "X-AfuDM-Token": token})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_pdf_ask_and_approval(self):
        cases = [
            {"url": "https://example.test/document", "mime": "application/pdf", "filename": "download.pdf"},
            {"url": "https://example.test/document", "headers": {"Content-Disposition": 'inline; filename="paper.pdf"'}, "filename": "paper.pdf"},
            {"url": "https://example.test/document?signature=" + "x" * 3000, "filename": "long.pdf"},
            {"url": "https://example.test/document", "filename": 'a:b*?"<>|.pdf'},
        ]
        for data in cases:
            with self.subTest(data=data):
                status, result = self.post({"interactive": True, "kind": "http", **data})
                self.assertEqual(status, 200, result)
                self.assertTrue(result["pending"])
                approval = self.api.bekleyen_onayla(result["id"], {"filename": ""})
                self.assertTrue(approval["ok"], approval)
                event = self.store.recent_events()[0]
                self.assertEqual(event["message"], "Download approval accepted")
                self.assertEqual(event["gid"], "test-pdf")
                self.assertEqual(self.requests[-1].source, data["url"])
                self.assertTrue(self.requests[-1].filename.endswith(".pdf"))
                self.assertFalse(any(c in self.requests[-1].filename for c in ':*?"<>|'))
        self.assertEqual(len(self.requests), 4)

    def test_existing_instance_desktop_handoff_keeps_source(self):
        from unittest.mock import Mock
        self.api._window = Mock()
        with patch('app.pencere.one_getir'):
            status, result = self.post({"url": "magnet:?xt=urn:btih:test",
                "interactive": True, "prompt_source": "desktop"})
        self.assertEqual(status, 200, result)
        self.assertEqual(self.api.bekleyen_listesi()["ogeler"][0]["source"], "desktop")
        self.api._window.evaluate_js.assert_called_once()

    def test_pdf_ask_accepts_explicit_local_destination(self):
        status, result = self.post({"url": "https://example.test/document",
            "interactive": True, "mime": "application/pdf", "filename": "paper.pdf",
            "dest_dir": self.tmp.name})
        self.assertEqual(status, 200, result)
        self.assertTrue(result["pending"])
        self.assertTrue(self.api.bekleyen_onayla(result["id"], {})["ok"])

    def test_unexpected_ask_exception_keeps_actual_error_in_events(self):
        with patch.object(_Handler, "on_ask", side_effect=RuntimeError("specific PDF failure")):
            status, _ = self.post({"url": "https://example.test/pdf", "interactive": True})
        self.assertEqual(status, 500)
        self.assertIn("specific PDF failure", self.store.recent_events()[0]["message"])

    def test_rejected_requests_leave_error_events(self):
        self.assertEqual(self.post({}, token="wrong")[0], 401)
        self.assertEqual(self.post({"url": "https://example.test/a", "dest_dir": "//outside/share"})[0], 403)
        self.assertEqual(self.post([])[0], 400)
        with patch.object(_Handler, "on_ask", side_effect=ValueError("ask failed")):
            self.assertEqual(self.post({"url": "https://example.test/a", "interactive": True})[0], 400)
        events = self.store.recent_events()
        self.assertEqual(len(events), 4)
        self.assertTrue(all(e["level"] == "error" for e in events))
        self.assertIn("ask failed", events[0]["message"])
        self.assertEqual(self.post({"error": "transport failed"}, path="/handoff/error")[0], 200)
        self.assertIn("transport failed", self.store.recent_events()[0]["message"])


if __name__ == "__main__":
    unittest.main()
