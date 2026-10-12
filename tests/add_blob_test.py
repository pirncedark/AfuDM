"""Binary handoff boundary: isolated loopback HTTP and temporary persistence."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from contextlib import nullcontext
from api.server import _Handler, _ExclusiveServer
from core.db import Store
from core.manager import Manager


class BlobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "downloads"
        self.store = Store(str(Path(self.tmp.name) / "test.db"))
        self.manager = SimpleNamespace(store=self.store, current_download_dir=lambda: str(self.root))
        self.manager.add_completed_file = lambda path: Manager.add_completed_file(self.manager, path)
        self.patches = [patch.object(_Handler, "manager", self.manager),
                        patch.object(_Handler, "token", "test-token"), patch.object(_Handler, "_rate", {})]
        for p in self.patches: p.start()
        self.server = _ExclusiveServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        for p in reversed(self.patches): p.stop()
        self.store.conn.close()
        self.tmp.cleanup()

    def post(self, name="image.png", body=b"PNG", token="test-token", length=None, extra=""):
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Content-Type":"application/octet-stream", "X-AfuDM-Token":token}
        if length is not None: headers["Content-Length"] = str(length)
        c.request("POST", "/add_blob?filename=" + name + extra, body, headers)
        r = c.getresponse()
        result = r.status, json.loads(r.read())
        c.close()
        return result

    def test_token_required(self):
        self.assertEqual(self.post(token="")[0], 401)
        self.assertFalse(self.root.exists())

    def test_limit(self):
        self.assertEqual(self.post(length=512*1024*1024+1)[0], 413)
        self.assertFalse(self.root.exists())

    def test_paths_rejected(self):
        for name in ["..%2Fescape.png", "..%5Cescape.png", "C%3Aescape.png", "%00bad.png"]:
            with self.subTest(name=name): self.assertEqual(self.post(name)[0], 400)
        self.assertEqual(self.post(extra="&dest_dir=elsewhere")[0], 400)
        self.assertFalse(self.root.exists())

    def test_success_and_collision(self):
        for body in [b"first PNG", b"second PNG"]:
            status, result = self.post(body=body)
            self.assertEqual(status, 200)
            row = self.store.by_id(result["id"])
            self.assertEqual(row["status"], "complete")
            self.assertEqual(row["total_bytes"], len(body))
            self.assertEqual(row["done_bytes"], len(body))
            target = Path(row["dest_dir"]) / row["filename"]
            self.assertEqual(target.parent.resolve(), self.root.resolve())
            self.assertEqual(target.read_bytes(), body)
        self.assertEqual(len(list(self.root.iterdir())), 2)
        self.assertEqual((self.root / "image.png").read_bytes(), b"first PNG")

    def test_migration_once(self):
        self.assertFalse(self.store.get("kaydetme_penceresi"))
        self.store.set("kaydetme_penceresi", True)
        filename = str(Path(self.tmp.name) / "test.db")
        self.store.conn.close()
        self.store = Store(filename)
        self.manager.store = self.store
        self.assertTrue(self.store.get("kaydetme_penceresi"), "user disabled automatic acceptance")
        self.store.conn.execute("DELETE FROM settings WHERE key='auto_accept_migrated'")
        self.store.conn.commit()
        self.store.conn.close()
        self.store = Store(filename)
        self.manager.store = self.store
        self.assertFalse(self.store.get("kaydetme_penceresi"), "legacy true migrates once")

    def test_signed_http_rejection_logged_once(self):
        manager = Manager.__new__(Manager)
        manager.store = self.store
        manager._kilit = nullcontext
        manager.rpc = Mock()
        manager.rpc.tell_active.return_value = []
        for code in (401, 403):
            gid = f"denied-{code}"
            self.store.add(kind="http", source="https://fixture.test/signed.png", gid=gid)
            manager.rpc.tell_stopped.return_value = [{"gid":gid, "status":"error",
                "errorMessage":f"The response status is not successful. status={code}"}]
            with patch.object(self.store, "log") as log:
                manager._sync_aria2()
                manager._sync_aria2()
            log.assert_called_once_with("warn", "Görsel indirilemedi; tarayıcıdan yeniden indirin.", gid=gid)


if __name__ == "__main__":
    unittest.main()
