"""Local API path, auth, CORS and error handling regression tests."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import server  # noqa: E402


class APIGuvenlikTest(unittest.TestCase):
    def test_add_hedefi_kok_dizinde_olmali(self):
        kok = ROOT / "indirilenler"
        self.assertTrue(server._yol_kok_icinde(kok / "alt", kok))
        self.assertFalse(server._yol_kok_icinde(kok.parent / "disari", kok))

    def test_indir_yolu_kok_dizinde_olmali(self):
        from types import SimpleNamespace
        kok = ROOT / "indirilenler"
        manager = SimpleNamespace(
            resolve_item_path=lambda gid: kok.parent / "gizli.txt",
            current_download_dir=lambda: kok,
        )
        with self.assertRaises(PermissionError):
            server._indir_yolu(manager, "gizli")

    def test_cors_yalniz_uzanti_ve_loopback(self):
        self.assertTrue(server._origin_izinli("chrome-extension://" + "a" * 32))
        self.assertFalse(server._origin_izinli("chrome-extension://abcdefghijklmnop"))
        self.assertTrue(server._origin_izinli("http://127.0.0.1:6811"))
        self.assertTrue(server._origin_izinli("http://localhost:6811"))
        self.assertFalse(server._origin_izinli("https://attacker.example"))

    def test_cors_kontrol_karakterlerini_yansitmaz_ve_loopbacku_aynen_yazar(self):
        class Handler:
            def __init__(self, origin):
                self.headers = {"Origin": origin}
                self.sent = []
            def send_header(self, name, value):
                self.sent.append((name, value))

        h = Handler("http://127.0.0.1:6811\r\nX-Evil: yes")
        server._Handler._cors(h)
        self.assertNotIn("Access-Control-Allow-Origin", [name for name, _ in h.sent])
        h = Handler("http://127.0.0.1:6811")
        server._Handler._cors(h)
        self.assertIn(("Access-Control-Allow-Origin", "http://127.0.0.1:6811"), h.sent)

    def test_ag_ve_aygit_yollari_dosyaya_dokunmadan_reddedilir(self):
        for yol in (r"\\evil\share\x", r"\\?\C:\x"):
            from types import SimpleNamespace
            class Handler:
                path = "/add"
                manager = SimpleNamespace(current_download_dir=lambda: ROOT / "indirilenler")
                def _rate_allowed(self): return True
                def _authorized(self, query): return True
                def _body(self): return {"dest_dir": yol}
                def _hata(self, code, *_args): self.status = code
            with self.subTest(yol=yol), patch.object(Path, "resolve") as resolve:
                handler = Handler()
                server._Handler.do_POST(handler)
                self.assertEqual(handler.status, 403)
                resolve.assert_not_called()

    def test_kok_altindaki_alt_klasor_kabul_edilir(self):
        kok = ROOT / "indirilenler"
        self.assertTrue(server._yol_kok_icinde(kok / "alt" / "dosya.bin", kok))

    def test_query_token_kabul_edilmez(self):
        from types import SimpleNamespace
        handler = SimpleNamespace(headers={}, token="secret")
        self.assertFalse(server._Handler._authorized(handler, {"token": ["secret"]}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
