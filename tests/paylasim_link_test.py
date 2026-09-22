"""Paylasim URL'sinin LAN adresi bicimlerinden dogru uretilmesini test eder."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import Api


class PaylasimLinkTest(unittest.TestCase):
    def _api(self, lan_adresi):
        api = Api.__new__(Api)
        api.local_api = type("Local", (), {
            "lan_adresi": lambda _self: lan_adresi,
            "port": 6811,
        })()
        return api

    def test_tam_mobil_urlunden_yalnizca_hostu_alir(self):
        api = self._api("http://192.168.0.110:6811/m?k=6tMdYJzCTiRsV_FOoQeUFDdaS7zO15mX")

        self.assertEqual(
            api._paylasim_url("_5aM7Zz_ABD9FF9i"),
            "http://192.168.0.110:6811/s/_5aM7Zz_ABD9FF9i",
        )

    def test_ciplak_ip_de_kabul_edilir(self):
        api = self._api("192.168.0.110")

        self.assertEqual(
            api._paylasim_url("token"),
            "http://192.168.0.110:6811/s/token",
        )

    def test_none_ve_loopback_adres_localhosta_duser(self):
        for lan_adresi in (None, "http://127.0.0.1:6811/m?k=token"):
            with self.subTest(lan_adresi=lan_adresi):
                api = self._api(lan_adresi)
                url = api._paylasim_url("token")
                self.assertEqual(url, "http://127.0.0.1:6811/s/token")
                self.assertNotIn("http://http", url)
                self.assertNotIn("/m?k=", url)


if __name__ == "__main__":
    unittest.main()
