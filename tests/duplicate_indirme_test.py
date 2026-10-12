"""Offline duplicate regression tests; all persistence uses temporary data."""
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import kaydet
from core.db import Store
from core.manager import Manager


class DuplicateDownloadTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        data = patch.object(kaydet.paths, "DATA", self.folder)
        data.start()
        self.addCleanup(data.stop)
        self.manager = Manager.__new__(Manager)
        self.manager.store = Store(str(self.folder / "test.db"))
        self.addCleanup(self.manager.store.conn.close)
        self.manager._lock = threading.RLock()
        self.manager.video_jobs = {}
        self.manager._cerezler = {}
        self.manager._live_statuses = lambda: None
        self.manager.current_download_dir = lambda: str(self.folder)

    def add(self, source):
        return self.manager.add(source, start_after=time.time() + 3600)

    def test_pending_without_request_id(self):
        queue = kaydet.Bekleyenler()
        first = queue.ekle({"url": "https://example.test/a"})
        self.assertEqual(queue.ekle({"url": "https://example.test/a"}), first)
        self.assertEqual(len(queue.ozet()), 1)

    def test_pending_different_urls(self):
        queue = kaydet.Bekleyenler()
        self.assertNotEqual(queue.ekle({"url": "https://example.test/a"}),
                            queue.ekle({"url": "https://example.test/b"}))
        self.assertEqual(len(queue.ozet()), 2)

    def test_pending_normalized_url_and_new_request_id(self):
        queue = kaydet.Bekleyenler()
        first = queue.ekle({"url": "https://EXAMPLE.test", "request_id": "one"})
        self.assertEqual(queue.ekle({"url": "https://example.test/#x", "request_id": "two"}), first)
        self.assertNotEqual(queue.ekle({"url": "https://example.test/?a=2"}), first)

    def test_normalized_duplicate(self):
        first = self.add("https://EXAMPLE.test")
        self.assertEqual(self.manager.find_duplicate("https://example.test/#x")["id"], first["id"])
        with self.assertRaisesRegex(ValueError, "bu baglanti zaten kuyrukta:"):
            self.add("https://example.test/#x")

    def test_distinct_queries(self):
        self.assertNotEqual(self.add("https://example.test/?a=1")["id"],
                            self.add("https://example.test/?a=2")["id"])

    def test_duplicate_while_launch_is_in_progress(self):
        entered = threading.Event()
        release = threading.Event()
        self.manager._live_statuses = lambda: []

        def launch(row):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("Launch did not release")
            return row

        self.manager._launch = launch
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.manager.add, "https://example.test/launch")
            try:
                self.assertTrue(entered.wait(timeout=5))
                # A different thread can acquire the lock while launch is waiting.
                acquired = self.manager._lock.acquire(timeout=1)
                self.assertTrue(acquired)
                if acquired:
                    self.manager._lock.release()
                with self.assertRaisesRegex(ValueError, "zaten kuyrukta"):
                    self.manager.add("https://example.test/launch")
            finally:
                release.set()
            self.assertIsInstance(first.result(timeout=5), dict)
        self.assertEqual(len(self.manager.store.list()), 1)

    def test_finished_download_can_be_added_again(self):
        for status in ("complete", "error"):
            source = "https://example.test/" + status
            first = self.add(source)
            self.manager.store.update_by_id(first["id"], status=status)
            self.assertNotEqual(self.add(source)["id"], first["id"])

    def test_concurrent_add(self):
        barrier = threading.Barrier(2)
        original = self.manager.store.add

        def slow_add(**kwargs):
            time.sleep(0.05)  # Widen the check/insert race without blocking the lock owner.
            return original(**kwargs)

        def submit():
            barrier.wait(timeout=5)
            try:
                return self.add("https://example.test/race")
            except ValueError as exc:
                return exc

        with patch.object(self.manager.store, "add", side_effect=slow_add):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        errors = [r for r in results if isinstance(r, ValueError)]
        self.assertEqual(len(errors), 1)
        self.assertIn("zaten kuyrukta", str(errors[0]))
        self.assertEqual(len(self.manager.store.list()), 1)


if __name__ == "__main__":
    unittest.main()
