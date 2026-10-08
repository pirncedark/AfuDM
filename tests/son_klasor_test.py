import unittest
from pathlib import Path
import tempfile
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import Api, IndirmePenceresiApi

class MockStore:
    def __init__(self, download_dir):
        self.data = {"download_dir": download_dir, "son_klasor": ""}
    def get(self, key, default=None):
        return self.data.get(key, default)
    def set(self, key, value):
        self.data[key] = value
    def log(self, *args, **kwargs):
        pass

class TestSonKlasor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = SimpleNamespace(
            store=MockStore(self.temp_dir.name),
            current_download_dir=lambda: self.manager.store.get("download_dir"),
            add=lambda req: {"ok": True, "gid": "test"},
            detect_kind=lambda url: "http",
            guess_name=lambda url: "test.zip"
        )
        self.api = Api.__new__(Api)
        self.api._cikiliyor = False
        self.api.manager = self.manager
        from core.kaydet import Bekleyenler
        self.api._bekleyenler = Bekleyenler()
        self.api._hedef_klasor = lambda a,b,c,d: a
        self.pencere = IndirmePenceresiApi(self.api)

        self.test_id = self.api.tarayicidan_sor({"url": "http://example.com/test.zip", "source": "browser", "kind": "http"})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_klasor_degistirilmeden_onay(self):
        self.pencere.bekleyen_onayla(self.test_id, {"dest_dir": self.temp_dir.name, "folder_edited": False})
        kayit = self.manager.store.get("son_klasor")
        self.assertFalse(kayit)

    def test_elle_secim_sonraki_pencerede_gelir(self):
        yeni_klasor = os.path.join(self.temp_dir.name, "yeni_klasor")
        self.pencere.bekleyen_onayla(self.test_id, {"dest_dir": yeni_klasor, "folder_edited": True})

        kayit = self.manager.store.get("son_klasor")
        self.assertIsInstance(kayit, dict)
        self.assertEqual(kayit.get("yol"), yeni_klasor)
        self.assertEqual(kayit.get("ana"), self.manager.current_download_dir())

        bilgi = self.pencere.kaydet_bilgi("http://example.com/test2.zip")
        self.assertEqual(bilgi.get("son_klasor"), yeni_klasor)

    def test_download_dir_ayari_degisince_son_klasor_gelmez(self):
        yeni_klasor = os.path.join(self.temp_dir.name, "yeni_klasor")
        self.pencere.bekleyen_onayla(self.test_id, {"dest_dir": yeni_klasor, "folder_edited": True})

        baska_ana_klasor = os.path.join(self.temp_dir.name, "baska_ana")
        self.manager.store.set("download_dir", baska_ana_klasor)

        bilgi = self.pencere.kaydet_bilgi("http://example.com/test2.zip")
        self.assertEqual(bilgi.get("son_klasor"), "")

if __name__ == '__main__':
    unittest.main()
