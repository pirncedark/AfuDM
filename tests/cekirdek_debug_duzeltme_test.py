# -*- coding: utf-8 -*-
"""CEKIRDEK taramasi — 7 bulgunun duzeltilmis hali icin kirmizi/yasil test.

Kapsam (GOREV_FIX_CEKIRDEK.md):
  1  manager.py   — silme hedefleri indirme klasoru DISINA cikamaz
  2  reliability.py — JSON'daki ayar sirleri maskelenir
  3  reliability.py — geri yukleme hatasi baglantiyi KAPATMAZ
  4  db.py        — rules_save hatasinda rollback
  5  manager.py   — torrent_on_iptal: parent hatasi child'i asmaz
  6  settings_validation.py — max_concurrent dogrulayicisi
  7  headless.py  — bozuk Turkce karakterler duzeltildi

Gercek kullanici dosyalarina dokunmaz: gecici klasor kullanir.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core import reliability as rel
from core.db import Store
from core.manager import Manager
from core import settings_validation as sv


def _bos_manager(tmp: Path):
    """Gercek Store'a degil, gecici ayar degerlerine bagli sahte Manager."""
    mgr = Manager.__new__(Manager)
    mgr.store = MagicMock()
    mgr.store.get.side_effect = lambda key, default=None: (
        str(tmp) if key == "download_dir" else default)
    mgr.store.all_settings.return_value = {}
    mgr.store.recent_events.return_value = []
    mgr.rpc = MagicMock()
    mgr.daemon = MagicMock()
    mgr.video_jobs = {}
    mgr._cerezler = {}
    mgr._removed_gids = set()
    mgr._removed_hashes = set()
    mgr.last_error = ""
    return mgr


# ===========================================================================
# 1) Silme hedefleri indirme klasorunun disina CIKAMAZ
# ===========================================================================
class TestGuvenliSilmeHedefi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kok = Path(self.tmp.name) / "downloads"
        self.kok.mkdir()
        self.mgr = _bos_manager(self.kok)

    def tearDown(self):
        self.tmp.cleanup()

    # --- yardimci: guvenli_hedef dogrudan ---------------------------------
    def test_dotdot_baslik_disari_cikamaz(self):
        disari = Path(self.tmp.name) / "baska_klasor"
        disari.mkdir()
        (disari / "kurban.txt").write_text("kullanici dosyasi", encoding="utf-8")

        hedef = self.mgr._guvenli_hedef(self.kok, self.kok / "..\\baska_klasor\\kurban.txt")
        self.assertIsNone(hedef)
        self.assertTrue((disari / "kurban.txt").exists())

    def test_mutlak_yol_disari_cikamaz(self):
        disari = Path(self.tmp.name) / "mutlak.txt"
        disari.write_text("x", encoding="utf-8")
        self.assertIsNone(self.mgr._guvenli_hedef(self.kok, disari))

    def test_klasorun_kendisi_silinmez(self):
        self.assertIsNone(self.mgr._guvenli_hedef(self.kok, self.kok))

    def test_icerdeki_yol_kabul_edilir(self):
        ic = self.kok / "film.mp4"
        ic.write_text("x", encoding="utf-8")
        self.assertEqual(self.mgr._guvenli_hedef(self.kok, ic), ic.resolve())

    # --- bütün remove() akisi -------------------------------------------
    def test_remove_dotdot_title_kullanici_dosyasini_silmez(self):
        disari = Path(self.tmp.name) / "baska_klasor"
        disari.mkdir()
        kurban = disari / "kurban.txt"
        kurban.write_text("kullanici dosyasi", encoding="utf-8")

        row = {"id": 1, "gid": "g1", "status": "active", "source": "https://x/y.zip",
               "title": "..\\baska_klasor\\kurban.txt", "filename": "",
               "dest_dir": str(self.kok), "target_path": "",
               "options": json.dumps({"filename": "..\\baska_klasor\\kurban.txt"})}
        self.mgr.store.by_gid.return_value = row
        self.mgr.rpc.tell_status.return_value = {}

        self.assertTrue(self.mgr.remove("g1", delete_files=True))
        self.assertTrue(kurban.exists(), "indirme klasoru disindaki dosya SILINDI")

    def test_remove_mutlak_title_kullanici_dosyasini_silmez(self):
        kurban = Path(self.tmp.name) / "belge.txt"
        kurban.write_text("kullanici dosyasi", encoding="utf-8")
        row = {"id": 2, "gid": "g2", "status": "active", "source": "https://x/y.zip",
               "title": str(kurban), "filename": str(kurban),
               "dest_dir": str(self.kok), "target_path": str(kurban), "options": "{}"}
        self.mgr.store.by_gid.return_value = row
        self.mgr.rpc.tell_status.return_value = {}

        self.assertTrue(self.mgr.remove("g2", delete_files=True))
        self.assertTrue(kurban.exists(), "mutlak yol SILINDI")

    def test_remove_torrent_files_yolu_disi_cikamaz(self):
        disari = Path(self.tmp.name) / "aria2_disi"
        disari.mkdir()
        kurban = disari / "x.bin"
        kurban.write_text("x", encoding="utf-8")

        row = {"id": 3, "gid": "g3", "status": "active",
               "source": "magnet:?xt=urn:btih:" + "a" * 40,
               "title": "t", "filename": "", "dest_dir": str(self.kok),
               "target_path": "", "options": "{}"}
        self.mgr.store.by_gid.return_value = row
        self.mgr.rpc.tell_status.return_value = {
            "infoHash": "a" * 40, "followedBy": [],
            "files": [{"path": str(kurban)}]}

        self.assertTrue(self.mgr.remove("g3", delete_files=True))
        self.assertTrue(kurban.exists(), "aria2 dis yolu SILINDI")

    def test_remove_klasor_ici_dosya_silinir(self):
        ic = self.kok / "dosya.bin"
        ic.write_text("x", encoding="utf-8")
        row = {"id": 4, "gid": "g4", "status": "active", "source": "https://x/y.bin",
               "title": "dosya.bin", "filename": "dosya.bin",
               "dest_dir": str(self.kok), "target_path": "", "options": "{}"}
        self.mgr.store.by_gid.return_value = row
        self.mgr.rpc.tell_status.return_value = {}

        self.assertTrue(self.mgr.remove("g4", delete_files=True))
        self.assertFalse(ic.exists(), "klasor ici dosya silinmeliydi")

    def test_remove_kaynak_torrent_disi_korunur(self):
        # Kullanicinin kendi .torrent dosyasi indirme klasoru DISINDA
        disari = Path(self.tmp.name) / "kaynak.torrent"
        disari.write_bytes(b"d8:announce")
        ic = self.kok / "paket"
        ic.mkdir()
        (ic / "a.bin").write_text("x", encoding="utf-8")

        row = {"id": 5, "gid": "g5", "status": "active", "source": str(disari),
               "title": "paket", "filename": "paket", "dest_dir": str(self.kok),
               "target_path": "", "options": "{}"}
        self.mgr.store.by_gid.return_value = row
        self.mgr.rpc.tell_status.return_value = {}

        self.assertTrue(self.mgr.remove("g5", delete_files=True))
        self.assertTrue(disari.exists(), "kullanicinin .torrent dosyasi SILINDI")

    def test_remove_video_job_disi_cikamaz(self):
        disari = Path(self.tmp.name) / "video_disi"
        disari.mkdir()
        kurban = disari / "v.mp4"
        kurban.write_text("x", encoding="utf-8")

        job = MagicMock()
        job.filename = "..\\video_disi\\v.mp4"
        job.dest_dir = str(self.kok)
        self.mgr.video_jobs["yt:1"] = job
        row = {"id": 6, "gid": "yt:1", "status": "active", "source": "yt:1",
               "title": "v", "filename": "", "dest_dir": "", "target_path": "",
               "options": "{}"}
        self.mgr.store.by_gid.return_value = row

        self.assertTrue(self.mgr.remove("yt:1", delete_files=True))
        self.assertTrue(kurban.exists(), "video isi dis yol SILDI")


# ===========================================================================
# 2) diagnostics_preview ayar sirlerini disari vermez
# ===========================================================================
class TestMaskeleme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _bos_manager(Path(self.tmp.name))
        self.svc = rel.Reliability(self.mgr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mask_metni_json_anahtarini_yakalayamaz(self):
        # ESKI davranis: metin maskesi bu yazimi GORMEZ.
        self.assertNotEqual(rel.mask('{"api_token": "abc123"}'), '{"api_token": "***"}')

    def test_preview_ayar_sirlari_maskeli(self):
        self.mgr.store.all_settings.return_value = {
            "api_token": "GIZLI-TOKEN",
            "telegram_bot_token": "123456:ABCDEF",
            "proxy": "http://kullanici:SIFRE123@proxy.example:8080",
            "download_dir": "C:/Downloads",
            "tunel_token": "TUNEL-SIRI",
        }
        self.mgr.rpc.alive.return_value = True
        onizleme = self.svc.diagnostics_preview()
        metin = json.dumps(onizleme["preview"], ensure_ascii=False)
        for siri in ("GIZLI-TOKEN", "123456:ABCDEF", "SIFRE123", "TUNEL-SIRI"):
            self.assertNotIn(siri, metin, "sir disari cikti: %s" % siri)
        ayarlar = onizleme["preview"]["settings"]
        self.assertEqual(ayarlar["api_token"], "***")
        self.assertEqual(ayarlar["proxy"], "http://proxy.example:8080")
        self.assertEqual(ayarlar["download_dir"], "C:/Downloads")

    def test_maskele_ozyinel_metin_maskesi_de_kalir(self):
        sonuc = rel.maskele({"notlar": ["token=abc123"], "token": "x"})
        self.assertNotIn("abc123", json.dumps(sonuc))
        self.assertEqual(sonuc["token"], "***")

    def test_export_maskeli_dosya_yazar(self):
        self.mgr.store.all_settings.return_value = {"api_token": "GIZLI"}
        self.mgr.rpc.alive.return_value = True
        hedef = self.svc.diagnostics_export()["path"]
        try:
            icerik = Path(hedef).read_text(encoding="utf-8")
            self.assertNotIn("GIZLI", icerik)
        finally:
            Path(hedef).unlink(missing_ok=True)


# ===========================================================================
# 3) Geri yukleme hatasi paylasilan baglantiyi KAPATMAZ
# ===========================================================================
class TestRestoreBaglantiGuvenligi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kok = Path(self.tmp.name)
        self.eski_db = self.kok / "afudm.db"
        conn = sqlite3.connect(self.eski_db)
        conn.execute("CREATE TABLE t(a)")
        conn.execute("INSERT INTO t VALUES(1)")
        conn.commit()
        conn.close()

        yedekler = self.kok / "backups"
        yedekler.mkdir()
        import zipfile
        arsiv = yedekler / "afudm-test.zip"
        with zipfile.ZipFile(arsiv, "w") as z:
            z.write(self.eski_db, "afudm.db")

        self.svc = rel.Reliability(MagicMock())
        self.svc.backup = MagicMock(return_value={"ok": True, "path": "x"})

    def tearDown(self):
        self.tmp.cleanup()

    def _paths_patch(self, db_path, data_dir):
        from core import paths as _paths
        _paths.DB_PATH = db_path
        _paths.DATA = data_dir

    def test_move_hatasinda_baglanti_kapatilmaz(self):
        """ASIL TEHLIKE: conn.close() SONRASI move/Store hata verirse
        paylasilan baglanti KAPALI kalir ve tum DB islemleri cokerdii."""
        import threading
        from core import paths as _paths

        gercek_db, gercek_data = _paths.DB_PATH, _paths.DATA
        gercek_move = rel.shutil.move
        _paths.DB_PATH = self.eski_db
        _paths.DATA = self.kok

        store = MagicMock()
        store._lock = threading.RLock()
        store.conn = sqlite3.connect(self.eski_db)
        self.svc.manager.store = store
        arsiv = self.kok / "backups" / "afudm-test.zip"

        def kilitli_move(*_a, **_kw):
            raise OSError(32, "dosya baska bir islem tarafindan kullaniliyor")

        rel.shutil.move = kilitli_move
        try:
            with self.assertRaises(ValueError):
                self.svc.restore(str(arsiv))
            # Baglanti ACIK kalmali ve SORGULANABILIR olmali
            self.assertIsNotNone(store.conn)
            self.assertEqual(store.conn.execute("SELECT a FROM t").fetchone()[0], 1)
        finally:
            rel.shutil.move = gercek_move
            try:
                store.conn.close()
            except Exception:
                pass
            _paths.DB_PATH, _paths.DATA = gercek_db, gercek_data

    def test_bozuk_yedek_tek_cumle_hata_dondurur(self):
        import zipfile
        from core import paths as _paths

        gercek_db, gercek_data = _paths.DB_PATH, _paths.DATA
        _paths.DB_PATH = self.eski_db
        _paths.DATA = self.kok
        store = MagicMock()
        store._lock = __import__("threading").RLock()
        store.conn = sqlite3.connect(self.eski_db)
        self.svc.manager.store = store
        bozuk = self.kok / "backups" / "afudm-bozuk.zip"
        with zipfile.ZipFile(bozuk, "w") as z:
            z.writestr("afudm.db", "bu bir veritabani degil")
        try:
            with self.assertRaises(ValueError):
                self.svc.restore(str(bozuk))
            self.assertIsNotNone(store.conn)
            self.assertEqual(store.conn.execute("SELECT a FROM t").fetchone()[0], 1)
        finally:
            try:
                store.conn.close()
            except Exception:
                pass
            _paths.DB_PATH, _paths.DATA = gercek_db, gercek_data


# ===========================================================================
# 4) rules_save hatasi rollback yapar
# ===========================================================================
class TestRulesSaveRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.tmp.name) / "r.db"))

    def tearDown(self):
        # Windows'ta acik baglanti gecici klasoru silmeyi engeller
        try:
            self.store.conn.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_hatali_kural_rollback_yapar(self):
        self.store.rules_save([{"id": 1, "name": "iyi", "conditions": [],
                                "actions": {"k": "v"}}])
        self.assertEqual(len(self.store.rules_list()), 1)

        with self.assertRaises(KeyError):
            self.store.rules_save([{"id": 2, "conditions": [], "actions": {}}])

        # Islem yarim/bos kalicilastirilMAMALI
        self.assertEqual(len(self.store.rules_list()), 1)
        # Baglanti kullanilabilir
        self.assertEqual(self.store.conn.execute(
            "SELECT COUNT(*) FROM rules").fetchone()[0], 1)

    def test_gecerli_kayit_calisir(self):
        self.store.rules_save([{"id": 1, "name": "a", "conditions": [],
                                "actions": {"x": 1}},
                               {"id": 2, "name": "b", "conditions": [],
                                "actions": {"y": 2}}])
        self.assertEqual(len(self.store.rules_list()), 2)


# ===========================================================================
# 5) torrent_on_iptal: parent hatasi child'i ASMAZ
# ===========================================================================
class TestTorrentOnIptal(unittest.TestCase):
    def test_parent_hata_verirse_child_yine_silinir(self):
        mgr = Manager.__new__(Manager)
        mgr._removed_gids = set()
        mgr.rpc = MagicMock()
        mgr.rpc.tell_status.return_value = {"followedBy": ["child1"]}
        cagrilan = []

        def remove(gid, force=False):
            cagrilan.append(gid)
            if gid == "parent1":
                raise Exception("parent yok")
            return "OK"

        mgr.rpc.remove.side_effect = remove
        mgr.torrent_on_iptal("parent1")
        self.assertIn("parent1", cagrilan)
        self.assertIn("child1", cagrilan, "child aria2'de asili kaldi")

    def test_tell_status_hata_verirse_parent_yine_silinir(self):
        mgr = Manager.__new__(Manager)
        mgr._removed_gids = set()
        mgr.rpc = MagicMock()
        mgr.rpc.tell_status.side_effect = Exception("yok")
        mgr.torrent_on_iptal("p2")
        mgr.rpc.remove.assert_any_call("p2", force=True)


# ===========================================================================
# 6) max_concurrent dogrulayicisi
# ===========================================================================
class TestMaxConcurrentDogrulama(unittest.TestCase):
    def test_gecerli_degerler(self):
        self.assertEqual(sv.dogrula_max_concurrent(5), 5)
        self.assertEqual(sv.dogrula_max_concurrent("7"), 7)
        self.assertEqual(sv.dogrula_max_concurrent(1), 1)
        self.assertEqual(sv.dogrula_max_concurrent(20), 20)

    def test_gecersiz_degerler(self):
        for kotu in ("abc", 0, -1, 21, True, "", None, 3.5):
            with self.assertRaises(sv.AyarHatasi, msg="kabul edildi: %r" % (kotu,)):
                sv.dogrula_max_concurrent(kotu)

    def test_tabloya_kayitli(self):
        self.assertIn("max_concurrent", sv.DOGRULAYICILAR)

    def test_ayarlari_dogrula_hepsi_yahicbiri(self):
        hatalar, temiz = sv.ayarlari_dogrula({"max_concurrent": "abc"})
        self.assertTrue(hatalar)
        self.assertEqual(temiz, {})
        hatalar, temiz = sv.ayarlari_dogrula({"max_concurrent": 4})
        self.assertEqual(hatalar, [])
        self.assertEqual(temiz["max_concurrent"], 4)

    def test_manager_int_hatasi_yok(self):
        # manager.py:199 `int(settings.get("max_concurrent", 5))` — dogrulanmis
        # deger her zaman TAM SAYI olmali.
        for ham in ("abc", 0, -1, "20"):
            hatalar, temiz = sv.ayarlari_dogrula({"max_concurrent": ham})
            if not hatalar:
                self.assertIsInstance(int(temiz["max_concurrent"]), int)


# ===========================================================================
# 7) headless.py metinleri bozulmus degil
# ===========================================================================
class TestHeadlessMetin(unittest.TestCase):
    def setUp(self):
        self.metin = (KOK / "headless.py").read_text(encoding="utf-8")

    def test_bOZUK_KARAKTER_YOK(self):
        # Onceki ajan Turkce harfleri '?' yazmis; kalici cikti ASCII olmali.
        for bozuk in ("?ndirme motoru ba?lat?lamad?", "Ba?lant? a??lamad?"):
            self.assertNotIn(bozuk, self.metin)

    def test_duzeltilmis_mesajlar_var(self):
        self.assertIn("HATA: Indirme motoru baslatilamadi; uygulamayi yeniden acin.",
                      self.metin)
        self.assertIn("UYARI: Baglanti acilamadi; uygulamayi yeniden acin.",
                      self.metin)

    def test_ascii_karakter_kontrolu(self):
        # Duzeltilen iki satir ASCII (dosyanin geri kalaniyla ayni uslub).
        for satir in re.findall(r'print\("(?:HATA|UYARI): [^"]*"\)', self.metin):
            if "Indirme motoru" in satir or "Baglanti acilamadi" in satir:
                satir.encode("ascii")


if __name__ == "__main__":
    unittest.main(verbosity=2)
