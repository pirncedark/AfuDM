"""Startup recovery of video jobs whose yt-dlp process no longer exists."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import Store
from core.manager import Manager


class OrphanVideoRecoveryTest(unittest.TestCase):
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
