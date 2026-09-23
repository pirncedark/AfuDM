"""Local API path, auth, CORS and error handling regression tests."""
from __future__ import annotations

import sys
import unittest
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
        kok = ROOT / "indirilenler"
        self.assertFalse(server._yol_kok_icinde(kok.parent / "gizli.txt", kok))

    def test_cors_yalniz_uzanti_ve_loopback(self):
        self.assertTrue(server._origin_izinli("chrome-extension://abcdefghijklmnop"))
        self.assertTrue(server._origin_izinli("http://127.0.0.1:6811"))
        self.assertTrue(server._origin_izinli("http://localhost:6811"))
        self.assertFalse(server._origin_izinli("https://attacker.example"))

    def test_query_token_kabul_edilmez(self):
        from types import SimpleNamespace
        handler = SimpleNamespace(headers={}, token="secret")
        self.assertFalse(server._Handler._authorized(handler, {"token": ["secret"]}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
