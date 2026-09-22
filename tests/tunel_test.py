"""Cloudflare tunnel ve dar kapsamli internet paylasim sunucusu testleri."""
from __future__ import annotations

import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.paylasim_sunucusu import PaylasimSunucusu
from core.tunel import TunnelError, TunnelManager


class SahteProc:
    def __init__(self, lines=(), returncode=None):
        self.stdout = io.StringIO("".join(lines))
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode or 0


class TunnelTest(unittest.TestCase):
    def test_stderr_url_yakalanir_tek_ornek_ve_kapanista_durur(self):
        proc = SahteProc(["INF bekleniyor\n", "https://abc.trycloudflare.com\n"])
        calls = []
        manager = TunnelManager("cloudflared.exe", popen_factory=lambda *a, **k: (calls.append((a, k)) or proc),
                                timeout=1)
        self.assertEqual(manager.start(43210), "https://abc.trycloudflare.com")
        self.assertEqual(manager.start(43210), "https://abc.trycloudflare.com")
        self.assertEqual(manager.launch_count, 1)
        self.assertEqual(calls[0][0][0], ["cloudflared.exe", "tunnel", "--url", "http://127.0.0.1:43210", "--no-autoupdate"])
        manager.stop()
        self.assertTrue(proc.terminated)

    def test_zaman_asimi_ve_cokme_bir_kez_yeniden_dener(self):
        procs = [SahteProc([], returncode=1), SahteProc([], returncode=1)]
        manager = TunnelManager("cloudflared.exe", popen_factory=lambda *a, **k: procs.pop(0),
                                timeout=0.05)
        with self.assertRaises(TunnelError):
            manager.start(43210)
        self.assertEqual(manager.launch_count, 2)

    def test_paylasim_sunucusu_token_range_ve_yol_siniri(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "ok.txt"
            file.write_bytes(b"abcdef")
            shares = {"good": {"path": file, "created": time.time()}}
            server = PaylasimSunucusu(shares)
            port = server.start()
            try:
                with urlopen(f"http://127.0.0.1:{port}/s/good") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"abcdef")
                request = Request(f"http://127.0.0.1:{port}/s/good",
                                  headers={"Range": "bytes=1-3"})
                with urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b"bcd")
                with urlopen(Request(f"http://127.0.0.1:{port}/s/good", method="HEAD")) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"")
                for path in ("/s/bad", "/m", "/api/ayarlar", "/s/../ok.txt"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(f"http://127.0.0.1:{port}{path}")
                    self.assertEqual(error.exception.code, 404)
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
