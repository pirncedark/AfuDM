"""Pending downloads survive restart without persisting browser credentials."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import kaydet


class PendingPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.patch = patch.object(kaydet.paths, "DATA", self.data)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_restart_identity_and_removal(self):
        queue = kaydet.Bekleyenler()
        ident = queue.ekle({"url": "https://example.test/a.pdf", "source": "browser"})
        restarted = kaydet.Bekleyenler()
        self.assertEqual(restarted.ozet()[0]["id"], ident)
        self.assertGreater(restarted.ekle({"url": "https://example.test/b.pdf"}), ident)
        restarted.al(ident)
        self.assertNotIn(ident, [r["id"] for r in kaydet.Bekleyenler().ozet()])

    def test_request_retry_survives_restart_without_second_prompt(self):
        request = {"url": "https://example.test/a.zip", "request_id": "retry-123"}
        queue = kaydet.Bekleyenler()
        ident = queue.ekle(request)
        self.assertEqual(queue.ekle(request), ident)
        restarted = kaydet.Bekleyenler()
        self.assertEqual(restarted.ekle(request), ident)
        self.assertEqual(len(restarted.ozet()), 1)
        with self.assertRaises(ValueError):
            restarted.ekle({**request, "url": "https://example.test/b.zip"})

    def test_atomic_failure_keeps_previous_file_and_memory(self):
        queue = kaydet.Bekleyenler()
        queue.ekle({"url": "https://example.test/a.pdf"})
        before = (self.data / "pending_downloads.json").read_bytes()
        with patch("core.kaydet.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                queue.ekle({"url": "https://example.test/b.pdf"})
        self.assertEqual((self.data / "pending_downloads.json").read_bytes(), before)
        self.assertEqual(len(queue.ozet()), 1)

    def test_credentials_are_memory_only(self):
        queue = kaydet.Bekleyenler()
        ident = queue.ekle({"url": "https://example.test/a.pdf", "cookies": [{"value": "SECRET"}],
                           "headers": {"Authorization": "SECRET", "Referer": "https://example.test/"}})
        disk = (self.data / "pending_downloads.json").read_text("utf-8")
        self.assertNotIn("SECRET", disk)
        self.assertEqual(queue.bak(ident)["cookies"][0]["value"], "SECRET")
        self.assertNotIn("cookies", kaydet.Bekleyenler().bak(ident))

    def test_corrupt_file_is_preserved_for_diagnosis(self):
        (self.data / "pending_downloads.json").write_text("broken", encoding="utf-8")
        self.assertEqual(kaydet.Bekleyenler().ozet(), [])
        self.assertTrue(list(self.data.glob("pending_downloads.json.corrupt*")))

    def test_old_download_survives_but_credentials_expire(self):
        queue = kaydet.Bekleyenler()
        ident = queue.ekle({"url": "https://example.test/a.pdf", "cookies": [{"value": "SECRET"}]})
        queue._isler[ident]["zaman"] = 0
        self.assertEqual(queue.ozet()[0]["id"], ident)
        self.assertNotIn("cookies", queue.bak(ident))


if __name__ == "__main__":
    unittest.main()
