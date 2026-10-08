# -*- coding: utf-8 -*-
"""Indirme satiri metrikleri: ortalama hiz, kalan miktar, gecen sure.

Kapsam:
  1) Manager._shape_aria2  -> avgSpeed / remaining / elapsed
  2) VideoJob.to_dict      -> avgSpeed / remaining / elapsed
  3) ui/app.js satirinda bu alanlar gosteriliyor (TR + EN i18n anahtarlari)

Gercek indirme yapmaz, motoru cagirmayan sahte yoneticiler kullanir.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core.manager import Manager
from video.ytdlp import VideoJob


def _manager(started_at=None) -> Manager:
    """started_at verilirse store.by_gid o started_at'li bir satir dondurur."""
    mgr = Manager.__new__(Manager)
    mgr.store = MagicMock()
    mgr.store.by_gid.return_value = (
        {"id": 1, "kind": "http", "title": "x", "source": "https://x",
         "started_at": started_at} if started_at else None)
    mgr._removed_gids = set()
    mgr._removed_hashes = set()
    mgr._preview_gids = set()
    mgr._auth_required_gids = set()
    return mgr


def _aria2(mgr: Manager, **ek) -> dict:
    status = {"gid": "g", "status": "active", "files": [{"path": "C:/x/a.bin"}]}
    status.update(ek)
    return mgr._shape_aria2(status)


# ===========================================================================
# 1) aria2 sekli
# ===========================================================================
class TestAria2Metrikleri(unittest.TestCase):
    def test_alanlar_uretildi(self):
        oge = _aria2(_manager(time.time() - 10), totalLength=100_000_000,
                     completedLength=50_000_000, downloadSpeed=1_000_000)
        for alan in ("avgSpeed", "remaining", "elapsed", "downloadSpeed", "eta"):
            self.assertIn(alan, oge, "metrik alani eksik: %s" % alan)

    def test_kalan_miktar_toplam_indirilen_farki(self):
        oge = _aria2(_manager(time.time() - 10), totalLength=1000,
                     completedLength=400, downloadSpeed=100)
        self.assertEqual(oge["remaining"], 600)

    def test_kalan_miktar_asla_negatif_olmaz(self):
        """Bazı motorlarda totalLength tamamlanmış veriden küçük döner;
        negatif kalırsa arayüz "-50 MB kaldı" gibi saçma metin basar."""
        oge = _aria2(_manager(time.time() - 10), status="complete",
                     totalLength=100, completedLength=150, downloadSpeed=0)
        self.assertGreaterEqual(oge["remaining"], 0)

    def test_ortalama_hiz_indirilen_uzere_sure(self):
        oge = _aria2(_manager(time.time() - 10), totalLength=100_000_000,
                     completedLength=50_000_000, downloadSpeed=10)
        self.assertGreater(oge["avgSpeed"], 1000, "ortalama hiz hesaplanmadi")
        self.assertGreaterEqual(oge["elapsed"], 9)

    def test_baslamamis_kayitta_ortalama_hiz_sifir(self):
        """started_at yoksa ortalama hız uydurulmaz."""
        oge = _aria2(_manager(None), totalLength=1000,
                     completedLength=500, downloadSpeed=100)
        self.assertEqual(oge["avgSpeed"], 0)
        self.assertEqual(oge["elapsed"], 0)

    def test_bayt_alani_her_zaman_tam_sayi(self):
        """JSON üzerinden gittiği için kesirli değer olmamalı."""
        oge = _aria2(_manager(time.time() - 3), totalLength=3333,
                     completedLength=1111, downloadSpeed=77)
        for alan in ("avgSpeed", "remaining", "elapsed"):
            self.assertIsInstance(oge[alan], int, alan)

    def test_ortalamasiz_birim_hiz_yoksa_sifir(self):
        oge = _aria2(_manager(time.time() - 5), totalLength=1000,
                     completedLength=0, downloadSpeed=0)
        self.assertEqual(oge["avgSpeed"], 0)


# ===========================================================================
# 2) Video işi — aria2 ile aynı sözleşme
# ===========================================================================
class TestVideoMetrikleri(unittest.TestCase):
    def _is(self) -> VideoJob:
        is_ = VideoJob(job_id="yt:1", dest_dir="C:/x", url="https://x/v")
        is_.total = 100_000_000
        is_.downloaded = 25_000_000
        is_.speed = 500_000
        return is_

    def test_alanlar_uretildi(self):
        oge = self._is().to_dict()
        for alan in ("avgSpeed", "remaining", "elapsed"):
            self.assertIn(alan, oge, "video metrigi eksik: %s" % alan)

    def test_degerler(self):
        oge = self._is().to_dict()
        self.assertEqual(oge["remaining"], 75_000_000)
        self.assertGreaterEqual(oge["elapsed"], 0)
        self.assertGreater(oge["avgSpeed"], 0)

    def test_toplam_bilinmiyorken_kalan_sifir(self):
        is_ = self._is()
        is_.total = 0
        is_.downloaded = 0
        oge = is_.to_dict()
        self.assertEqual(oge["remaining"], 0)
        self.assertEqual(oge["avgSpeed"], 0)

    def test_bayt_alani_her_zaman_tam_sayi(self):
        oge = self._is().to_dict()
        for alan in ("avgSpeed", "remaining", "elapsed"):
            self.assertIsInstance(oge[alan], int, alan)


# ===========================================================================
# 3) Arayüz — metrikler satırda görünüyor
# ===========================================================================
class TestArayuzMetrikleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (KOK / "ui" / "app.js").read_text(encoding="utf-8")
        cls.i18n = (KOK / "ui" / "i18n.js").read_text(encoding="utf-8")

    def test_satirda_kalan_miktar_gosteriliyor(self):
        self.assertIn('t("row.left")', self.app,
                      "satira kalan miktar satiri eklenmemis")

    def test_satirda_ortalama_hiz_gosteriliyor(self):
        self.assertIn('t("row.avg")', self.app,
                      "satira ortalama hiz satiri eklenmemis")

    def test_satirda_gecen_sure_gosteriliyor(self):
        self.assertIn("clockShort(item.elapsed)", self.app,
                      "satira gecen sure eklenmemis")

    def test_anahtar_her_dilde_tanimli(self):
        # Bir dilde eksik kalırsa arayüz anahtarı ham metin olarak basar.
        for anahtar in ("row.avg", "row.left", "row.elapsed"):
            tanim = self.i18n.count('"%s":' % anahtar)
            self.assertGreaterEqual(
                tanim, 3,
                "%s yalniz %d dilde tanimli (en az 3 olmali)" % (anahtar, tanim))

    def test_baglanti_satiri_kaybolmaz(self):
        """Ortalama hız anlık hıza eşitse bağlantı sayısı gösterilmeye devam eder."""
        self.assertRegex(self.app, r"item\.avgSpeed\s*&&\s*item\.avgSpeed\s*!==\s*item\.downloadSpeed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
