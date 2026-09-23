"""Paketleyici kilitli AfuDM.exe gorunce mevcut paketi korur (Windows)."""
import ctypes
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paketle as paketleyici  # noqa: E402


class PaketleKilitTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows dosya kilidi testi")
    def test_locked_exe_aborts_before_deleting_any_package_file(self):
        with tempfile.TemporaryDirectory() as temp:
            cikti = Path(temp) / "build_out" / "paket"
            hedef = cikti / "AfuDM"
            hedef.mkdir(parents=True)
            exe = hedef / "AfuDM.exe"
            diger = hedef / "afuadm.py"
            exe.write_bytes(b"running executable")
            diger.write_bytes(b"keep me")

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                    ctypes.c_uint32, ctypes.c_void_p,
                                    ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.c_void_p]
            create_file.restype = ctypes.c_void_p
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle.restype = ctypes.c_int
            handle = create_file(str(exe), 0x80000000, 0, None, 3, 0x80, None)
            invalid = ctypes.c_void_p(-1).value
            self.assertNotEqual(handle, invalid, f"CreateFileW error={ctypes.get_last_error()}")
            try:
                with patch.object(paketleyici, "CIKTI", cikti):
                    with self.assertRaisesRegex(SystemExit, "AfuDM.exe calisiyor") as hata:
                        paketleyici.paketle(tam=True)
                self.assertNotEqual(hata.exception.code, 0)
                self.assertTrue(exe.exists())
                self.assertEqual(exe.stat().st_size, len(b"running executable"))
                self.assertEqual(diger.read_bytes(), b"keep me")
                self.assertEqual(sorted(p.name for p in hedef.iterdir()),
                                 ["AfuDM.exe", "afuadm.py"])
            finally:
                close_handle(handle)
            self.assertEqual(exe.read_bytes(), b"running executable")


if __name__ == "__main__":
    unittest.main()
