"""Startup recovery of video jobs whose yt-dlp process no longer exists."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import Store
from core.manager import Manager


class OrphanVideoRecoveryTest(unittest.TestCase):
    def test_different_signed_urls_same_title_and_dest_dir_are_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(str(Path(temp) / "test.db"))
            try:
                orphan = store.add("video", "https://okcdn.test/video?expires=1&sig=old",
                                   "video", temp, options={"title": "Aynı video"})
                store.update_by_id(orphan, status="active")
                complete = store.add("video", "https://okcdn.test/video?expires=2&sig=new",
                                     "video", temp, options={"title": "Aynı video"})
                store.update_by_id(complete, status="complete")

                manager = Manager.__new__(Manager)
                manager.store = store
                manager._recover_orphan_video_jobs()

                self.assertEqual(store.by_id(orphan)["status"], "removed")
                self.assertEqual(store.by_id(complete)["status"], "complete")
            finally:
                store.conn.close()

    def test_same_title_in_different_dest_dir_stays_paused(self):
        with tempfile.TemporaryDirectory() as temp:
            first_dir = str(Path(temp) / "first")
            second_dir = str(Path(temp) / "second")
            store = Store(str(Path(temp) / "test.db"))
            try:
                orphan = store.add("video", "https://okcdn.test/video?expires=1&sig=old",
                                   "video", first_dir, options={"title": "Aynı video"})
                store.update_by_id(orphan, status="active")
                complete = store.add("video", "https://okcdn.test/video?expires=2&sig=new",
                                     "video", second_dir, options={"title": "Aynı video"})
                store.update_by_id(complete, status="complete")

                manager = Manager.__new__(Manager)
                manager.store = store
                manager._recover_orphan_video_jobs()

                self.assertEqual(store.by_id(orphan)["status"], "paused")
                self.assertEqual(store.by_id(complete)["status"], "complete")
            finally:
                store.conn.close()

    def test_orphans_become_resumable_or_hidden_when_duplicate_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(str(Path(temp) / "test.db"))
            try:
                resumable = store.add("video", "https://example.test/resume", "resume",
                                      temp, gid="yt:1")
                store.update_by_id(resumable, status="active")
                hidden = store.add("video", "https://example.test/done", "old",
                                   temp, gid="yt:2")
                store.update_by_id(hidden, status="waiting")
                complete = store.add("video", "https://example.test/done", "done",
                                     temp, gid="yt:3")
                store.update_by_id(complete, status="complete")

                manager = Manager.__new__(Manager)
                manager.store = store
                manager._recover_orphan_video_jobs()

                self.assertEqual(store.by_id(resumable)["status"], "paused")
                self.assertEqual(store.by_id(hidden)["status"], "removed")
                self.assertEqual(store.by_id(complete)["status"], "complete")
            finally:
                store.conn.close()


if __name__ == "__main__":
    unittest.main()
