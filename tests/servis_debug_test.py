# -*- coding: utf-8 -*-
"""core/servis.py — BOLUM A regresyon testleri (2 ertelenen API hatasi).

Kapsam:
  1. Baslangic istek limiti ETKIN PROFILIN limitidir (profil > genel ayar).
     `AfuDMServis.__init__` dogrudan genel ayari okuyordu; profil seciliyken
     genel ayarin eski limiti sessizce gecerli kaliyordu.
  2. Ham teknik istisna kullaniciya GONDERILMEZ. API yaniti tek cumle
     kullanici metni dondurur; teknik ayrinti tek kaynak olarak `store.log`
     dosyasina yazilir.
  3. `sunucu_baslat()` limitci uzerindeki elle ayari EZMEZ.

Cevrimdisi: ag, Chrome, acik pencere ve gercek indirme yok.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db  # noqa: E402
from core.erisim import ErisimDeposu  # noqa: E402
from core.servis import AfuDMServis  # noqa: E402

# Ham istisna metninde kullaniciya sizabilecek teknik ayrintilar.
_GIZLI = ("C:\\Users\\afuuu\\kullanicilar\\gizli\\rpc_secret.txt "
          "sqlite3.OperationalError: disk I/O error (code 14) errno 2")


class _SahteManager:
    """Manager yerine: yalnizca servisin cagirdigi iki yontem."""

    def __init__(self, store):
        self.store = store
        self.hata = None

    def retry(self, row_id):
        if self.hata:
            raise self.hata
        return {"gid": "g1"}


class ServisBaslangicLimitiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="afudm-servis-test-")
        self.store = db.Store(str(Path(self._tmp.name) / "t.db"))

    def tearDown(self):
        self.store.conn.close()
        self._tmp.cleanup()

    def _servis(self):
        return AfuDMServis(_SahteManager(self.store), kip="test")

    def _profil(self, ad, port, limit):
        return ErisimDeposu(self.store).profil_kaydet(
            ad, "yerel", port, originler="", istek_limiti=limit)

    def test_profil_yokken_genel_ayar_uygulanir(self):
        self.store.set("sunucu_istek_limiti", 42)
        self.assertEqual(self._servis().limitci.limit, 42)

    def test_profil_limiti_baslangicta_uygulanir(self):
        """Profil seciliyken BASLANGIC limiti profilinki olmali."""
        self.store.set("sunucu_istek_limiti", 120)
        self.store.set("sunucu_profil_id", self._profil("Dar", 7001, 7)["id"])

        servis = self._servis()
        self.assertEqual(servis.limitci.limit, 7,
                         "baslangiscta profilin istek limiti uygulanmadi")

    def test_profil_degisince_limit_yenilenir(self):
        profil = self._profil("Genis", 7002, 99)
        servis = self._servis()
        self.assertEqual(servis.limitci.limit, 120, "profil yokken genel ayar")

        servis.profil_etkinlestir(profil["id"])
        self.assertEqual(servis.limitci.limit, 99,
                         "profil degisince istek limiti tazelenmedi")

    def test_sunucu_baslat_elle_ayari_ezmez(self):
        """Sunucuyu acan kod limitciyi sonradan ayarladiysa ezilmemeli."""
        servis = self._servis()
        servis.limitci.ayarla(limit=50, hatali_limit=3, kilit_saniye=5)
        try:
            servis.sunucu_baslat()
        except Exception:
            pass  # port/ortam kisiti: esleme yeter, limit degismemeli
        finally:
            try:
                servis.sunucu_durdur()
            except Exception:
                pass
        self.assertEqual(servis.limitci.limit, 50,
                         "sunucu_baslat elle ayarlanan limiti ezdi")
        self.assertEqual(servis.limitci.hatali_limit, 3)
        self.assertEqual(servis.limitci.kilit_saniye, 5)


class ServisHataMetniTest(unittest.TestCase):
    """AGENTS.md kural 4: hata mesaji tek cumle, teknik ayrinti gunlukte."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="afudm-servis-hata-")
        self.store = db.Store(str(Path(self._tmp.name) / "t.db"))
        self.manager = _SahteManager(self.store)
        self.servis = AfuDMServis(self.manager, kip="test")
        self.manager.hata = RuntimeError(_GIZLI)

    def tearDown(self):
        self.store.conn.close()
        self._tmp.cleanup()

    def _gunluk(self):
        return "\n".join(e["message"] for e in self.store.recent_events(50))

    def test_ham_istisna_kullaniciya_gitmez(self):
        sonuc = self.servis.yeniden_dene(1)
        self.assertFalse(sonuc["ok"])
        self.assertEqual(sonuc["code"], "ISLEM_HATASI")
        mesaj = sonuc["message"]
        self.assertTrue(mesaj)
        for parca in ("sqlite3", "OperationalError", "rpc_secret.txt",
                      "disk I/O error", "C:\\Users", "errno"):
            self.assertNotIn(parca, mesaj,
                             f"teknik ayrinti kullanici metnine sizdi: {parca}")
        self.assertNotIn(_GIZLI, sonuc["error"])
        self.assertEqual(sonuc["error"], mesaj)

    def test_teknik_ayrinti_gunluge_yazilir(self):
        self.servis.yeniden_dene(1)
        gunluk = self._gunluk()
        self.assertIn("RuntimeError", gunluk,
                      "istisna tipi gunluge yazilmadi")
        self.assertIn("disk I/O error", gunluk,
                      "teknik ayrinti gunluge yazilmadi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
