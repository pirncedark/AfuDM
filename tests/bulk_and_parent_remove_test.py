# -*- coding: utf-8 -*-
import unittest
import sys
from unittest.mock import MagicMock
from pathlib import Path
import tempfile
import time

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core.manager import Manager
from core.servis import AfuDMServis


class BulkAndParentRemoveTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.manager = Manager()

        def store_get(key, default=None):
            if key == "download_dir":
                return self.tmp_dir.name
            if key == "sunucu_istek_limiti":
                return 120
            if key == "sunucu_hatali_limit":
                return 8
            if key == "sunucu_kilit_saniye":
                return 300
            return default

        self.manager.store.get = MagicMock(side_effect=store_get)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_parent_child_gid_remove(self):
        parent_gid = "gid_parent_123"
        child_gid = "gid_child_456"
        parent_file = Path(self.tmp_dir.name) / "parent.bin"
        child_file = Path(self.tmp_dir.name) / "child.bin"
        parent_file.write_bytes(b"parent")
        child_file.write_bytes(b"child")

        def mock_tell_status(gid, keys=None):
            if gid == parent_gid:
                return {"gid": parent_gid, "followedBy": [child_gid], "infoHash": "aabbcc112233",
                        "files": [{"path": str(parent_file)}]}
            elif gid == child_gid:
                return {"gid": child_gid, "following": parent_gid, "infoHash": "aabbcc112233",
                        "files": [{"path": str(child_file)}]}
            return {}

        self.manager.rpc.tell_status = MagicMock(side_effect=mock_tell_status)
        self.manager.rpc.remove = MagicMock(return_value="OK")
        self.manager.rpc.remove_result = MagicMock(return_value="OK")
        self.manager.rpc.save_session = MagicMock(return_value="OK")

        res = self.manager.remove(parent_gid, delete_files=False)

        self.assertTrue(res)
        self.assertIn(parent_gid, self.manager._removed_gids)
        self.assertIn(child_gid, self.manager._removed_gids)
        self.assertIn("aabbcc112233", self.manager._removed_hashes)
        self.assertTrue(self.manager.rpc.save_session.called)
        self.assertTrue(parent_file.exists())
        self.assertTrue(child_file.exists())

    def test_parent_child_delete_files_removes_all_files(self):
        parent_gid = "gid_parent_files"
        child_gid = "gid_child_files"
        parent_file = Path(self.tmp_dir.name) / "parent.bin"
        child_file = Path(self.tmp_dir.name) / "child.bin"
        parent_file.write_bytes(b"parent")
        child_file.write_bytes(b"child")

        def mock_tell_status(gid, keys=None):
            if gid == parent_gid:
                return {"gid": parent_gid, "followedBy": [child_gid], "infoHash": "deadbeef",
                        "files": [{"path": str(parent_file)}]}
            if gid == child_gid:
                return {"gid": child_gid, "following": parent_gid, "infoHash": "deadbeef",
                        "files": [{"path": str(child_file)}]}
            return {}

        self.manager.rpc.tell_status = MagicMock(side_effect=mock_tell_status)
        self.manager.rpc.remove = MagicMock(return_value="OK")
        self.manager.rpc.remove_result = MagicMock(return_value="OK")
        self.manager.rpc.save_session = MagicMock(return_value="OK")

        self.assertTrue(self.manager.remove(parent_gid, delete_files=True))
        self.assertFalse(parent_file.exists())
        self.assertFalse(child_file.exists())

    def test_bulk_service_removal(self):
        servis = AfuDMServis(self.manager)
        self.manager.rpc.remove = MagicMock(return_value="OK")
        self.manager.rpc.remove_result = MagicMock(return_value="OK")
        self.manager.rpc.tell_status = MagicMock(return_value={})
        self.manager.rpc.save_session = MagicMock(return_value="OK")

        gids = ["gid_bulk_1", "gid_bulk_2", "gid_bulk_3"]
        for gid in gids:
            res = servis.kontrol("remove", gid, delete_files=False)
            self.assertTrue(res["ok"])

        for gid in gids:
            self.assertIn(gid, self.manager._removed_gids)

        self.manager.rpc.tell_active = MagicMock(return_value=[
            {"gid": "gid_bulk_1", "status": "active"},
            {"gid": "gid_bulk_2", "status": "active"},
            {"gid": "gid_valid", "status": "active"}
        ])
        self.manager.rpc.tell_waiting = MagicMock(return_value=[])
        self.manager.rpc.tell_stopped = MagicMock(return_value=[])

        snap = self.manager.snapshot()
        item_gids = [item["gid"] for item in snap["items"]]
        self.assertNotIn("gid_bulk_1", item_gids)
        self.assertNotIn("gid_bulk_2", item_gids)
        self.assertIn("gid_valid", item_gids)


if __name__ == "__main__":
    unittest.main()
