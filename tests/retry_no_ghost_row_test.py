# -*- coding: utf-8 -*-
"""Retry must restart the SAME row; the engine's old error record must not
stay in the list as a second "Hata" row."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core.manager import Manager


class TestRetryNoGhostRow(unittest.TestCase):
    def _manager(self, old_gid):
        store = MagicMock()
        store.by_id.return_value = {"id": 7, "gid": old_gid, "kind": "http", "status": "error"}
        rpc = MagicMock()
        mgr = Manager.__new__(Manager)
        mgr.store = store
        mgr.rpc = rpc
        mgr._removed_gids = set()
        mgr._launch = MagicMock(return_value={"id": 7, "gid": "newgid", "kind": "http"})
        return mgr, store, rpc

    def test_retry_reuses_row_and_hides_old_engine_record(self):
        mgr, store, rpc = self._manager("oldgid")
        res = mgr.retry(7)
        self.assertEqual(res["id"], 7)
        store.update_by_id.assert_called_once_with(7, status="queued", gid=None, error=None)
        rpc.remove_result.assert_called_once_with("oldgid")
        self.assertIn("oldgid", mgr._removed_gids)

    def test_retry_without_old_gid_skips_engine_cleanup(self):
        mgr, _store, rpc = self._manager(None)
        mgr.retry(7)
        rpc.remove_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
