"""Running Windows executables must keep the existing package intact."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paketle as paketleyici  # noqa: E402


class PaketleKilitTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows image-lock test")
    def test_running_exe_aborts_without_deleting_package_files(self):
        ping = Path(r"C:\Windows\System32\PING.EXE")
        if not ping.exists():
            self.skipTest("PING.EXE is unavailable")

        with tempfile.TemporaryDirectory() as temp:
            cikti = Path(temp) / "build_out" / "paket"
            hedef = cikti / "AfuDM"
            hedef.mkdir(parents=True)
            exe = hedef / "AfuDM.exe"
            diger = hedef / "afuadm.py"
            shutil.copy2(ping, exe)
            diger.write_text("keep me", encoding="utf-8")

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.Popen(
                [str(exe), "-n", "30", "127.0.0.1"],
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                with patch.object(paketleyici, "CIKTI", cikti):
                    with self.assertRaisesRegex(
                        SystemExit, r"AfuDM\.exe.*calisiyor"
                    ) as hata:
                        paketleyici.paketle(tam=True)
                self.assertNotEqual(hata.exception.code, 0)
                self.assertTrue(proc.poll() is None, "PING process exited before check")
                self.assertTrue(exe.exists())
                self.assertEqual(diger.read_text(encoding="utf-8"), "keep me")
                self.assertEqual(sorted(p.name for p in hedef.iterdir()),
                                 ["AfuDM.exe", "afuadm.py"])
            finally:
                proc.kill()
                proc.wait()

    def test_unlocked_package_rebuild_still_removes_and_recreates_target(self):
        with tempfile.TemporaryDirectory() as temp:
            cikti = Path(temp) / "build_out" / "paket"
            hedef = cikti / "AfuDM"
            hedef.mkdir(parents=True)
            (hedef / "stale.txt").write_text("remove me", encoding="utf-8")

            with patch.object(paketleyici, "CIKTI", cikti), \
                    patch.object(paketleyici, "KOPYALANACAK_DOSYALAR", ()), \
                    patch.object(paketleyici, "KOPYALANACAK_KLASORLER", ()), \
                    patch.object(paketleyici, "CEKIRDEK_MOTORLAR", ()):
                sonuc = paketleyici.paketle(tam=False)

            self.assertEqual(sonuc, hedef)
            self.assertFalse((hedef / "stale.txt").exists())
            self.assertTrue((hedef / "engine").is_dir())
            self.assertTrue((hedef / "downloads").is_dir())


if __name__ == "__main__":
    unittest.main()
