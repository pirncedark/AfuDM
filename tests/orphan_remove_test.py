# -*- coding: utf-8 -*-
"""Orphan record deletion test for AfuDM."""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core.manager import Manager
from core.servis import AfuDMServis


class TestOrphanRemove(unittest.TestCase):
    def test_manager_remove_orphan_gid(self):
        mock_store = MagicMock()
        mock_store.by_gid.return_value = None
        mock_store.by_id.return_value = None

        mock_rpc = MagicMock()
        mock_rpc.remove.side_effect = Exception("No such download")
        mock_rpc.remove_result.side_effect = Exception("No such download")

        mgr = Manager.__new__(Manager)
        mgr.store = mock_store
        mgr.rpc = mock_rpc
        mgr.video_jobs = {}
        mgr._cerezler = {}
        mgr._removed_gids = set()
        mgr._removed_hashes = set()

        # Orphan GID remove should succeed gracefully
        res = mgr.remove("b7bd552af15b9490", delete_files=True)
        self.assertTrue(res)

    def test_manager_remove_orphan_row(self):
        mock_store = MagicMock()
        mock_store.by_id.return_value = None
        mock_store.by_gid.return_value = None

        mock_rpc = MagicMock()

        mgr = Manager.__new__(Manager)
        mgr.store = mock_store
        mgr.rpc = mock_rpc
        mgr.video_jobs = {}
        mgr._cerezler = {}
        mgr._removed_gids = set()
        mgr._removed_hashes = set()

        # Orphan row ID remove should succeed gracefully
        res = mgr.remove("row:99999", delete_files=False)
        self.assertTrue(res)

    def test_servis_kontrol_remove_orphan(self):
        mock_mgr = MagicMock()
        mock_mgr.remove.side_effect = Exception("kayit bulunamadi: orphan_123")

        servis = AfuDMServis.__new__(AfuDMServis)
        servis.manager = mock_mgr

        res = servis.kontrol("remove", "orphan_123", delete_files=True)
        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("orphan"))

    def test_snapshot_filters_removed_gids(self):
        mock_store = MagicMock()
        mock_store.by_gid.return_value = {"id": 1, "gid": "removed_gid", "status": "removed"}
        mock_store.list.return_value = []
        mock_store.all_settings.return_value = {}

        mock_rpc = MagicMock()
        mock_rpc.tell_active.return_value = [{"gid": "removed_gid", "status": "paused"}]
        mock_rpc.tell_waiting.return_value = []
        mock_rpc.tell_stopped.return_value = []
        mock_rpc.global_stat.return_value = {}

        mgr = Manager.__new__(Manager)
        mgr.store = mock_store
        mgr.rpc = mock_rpc
        mgr.video_jobs = {}
        mgr._cerezler = {}
        mgr._removed_gids = {"removed_gid"}
        mgr._removed_hashes = set()
        mgr.last_error = ""

        snap = mgr.snapshot()
        # The removed GID must NOT be present in snapshot items
        self.assertEqual(len(snap["items"]), 0)

    def test_snapshot_reattaches_torrent_after_gid_change(self):
        old_gid = "old_gid"
        new_gid = "new_gid"
        info_hash = "a" * 40
        row = {
            "id": 7,
            "gid": old_gid,
            "kind": "torrent",
            "status": "active",
            "source": f"magnet:?xt=urn:btih:{info_hash}",
            "title": "Kurtarilacak torrent",
        }

        mock_store = MagicMock()
        mock_store.by_gid.return_value = None
        mock_store.list.return_value = [row]
        mock_store.all_settings.return_value = {}
        mock_store.update_by_id.side_effect = lambda _id, **fields: row.update(fields)
        mock_store.by_id.side_effect = lambda _id: row

        mock_rpc = MagicMock()
        mock_rpc.tell_active.return_value = [{
            "gid": new_gid,
            "infoHash": info_hash,
            "status": "active",
            "totalLength": 100,
            "completedLength": 40,
        }]
        mock_rpc.tell_waiting.return_value = []
        mock_rpc.tell_stopped.return_value = []
        mock_rpc.global_stat.return_value = {}

        mgr = Manager.__new__(Manager)
        mgr.store = mock_store
        mgr.rpc = mock_rpc
        mgr.video_jobs = {}
        mgr._cerezler = {}
        mgr._removed_gids = set()
        mgr._removed_hashes = set()
        mgr._known_complete = set()
        mgr.last_error = ""

        snap = mgr.snapshot()
        self.assertEqual(row["gid"], new_gid)
        self.assertEqual(snap["items"][0]["gid"], new_gid)


if __name__ == "__main__":
    unittest.main()
