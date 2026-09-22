"""Dosya paylasimi API/UI akisi icin GUI'siz regresyon testi."""
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import Api
from api.server import _ExclusiveServer, _Handler, LocalAPI

ROOT = Path(__file__).resolve().parents[1]


class SahteStore:
    def by_gid(self, _gid):
        return None


class SahteManager:
    def __init__(self, path):
        self.path = path
        self.store = SahteStore()

    def resolve_item_path(self, gid):
        return self.path if gid == "gid-1" else None


class PaylasimTest(unittest.TestCase):
    def test_api_gercek_dosya_icin_link_ve_liste_uretir(self):
        with tempfile.TemporaryDirectory() as temp:
            dosya = Path(temp) / "ornek.txt"
            dosya.write_text("AfuDM paylasim", encoding="utf-8")
            manager = SahteManager(dosya)
            local_api = LocalAPI(manager, port=0)
            api = Api.__new__(Api)
            api.manager, api.local_api = manager, local_api
            _Handler.shared_files.clear()
            sonuc = api.share_create("gid-1")
            self.assertTrue(sonuc["ok"])
            self.assertIn("/s/", sonuc["url"])
            self.assertEqual(api.share_list()["shares"][0]["filename"], "ornek.txt")
            server = _ExclusiveServer(("127.0.0.1", 0), _Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_address[1]}/s/{sonuc['token']}") as response:
                    self.assertEqual(response.read(), b"AfuDM paylasim")
                with self.assertRaises(Exception):
                    urlopen(f"http://127.0.0.1:{server.server_address[1]}/s/../ornek.txt")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertTrue(api.share_delete(sonuc["token"])["ok"])

    def test_ui_tekil_modal_ve_akisi_bagli(self):
        html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
        js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
        css = (ROOT / "ui/style.css").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="shareVeil"'), 1)
        self.assertEqual(html.count('id="shareCenterVeil"'), 1)
        self.assertIn('id="shareSelectBtn"', html)
        self.assertIn('call("dosya_sec_ve_paylas")', js)
        self.assertIn('call("share_list")', js)
        self.assertIn(".modal-head", css)
        self.assertIn(".modal-head .modal-close", css)
        self.assertIn("padding: 16px 18px", css)

    def test_paylasim_tokeni_dizin_disina_tasamaz(self):
        source = (ROOT / "api/server.py").read_text(encoding="utf-8")
        self.assertIn("token not in _Handler.shared_files", source)
        self.assertIn('parsed.path.startswith("/s/")', source)
        self.assertNotRegex(source, r'open\([^\n]*parsed\.path')


if __name__ == "__main__":
    unittest.main()
