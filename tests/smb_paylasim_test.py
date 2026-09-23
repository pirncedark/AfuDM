"""SMB paylasim temizligi: acilista artik AfuDM_ paylasimlari kapatilir."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import smb_paylasim  # noqa: E402

NET_CIKTI = r"""Share name   Resource                        Remark

-------------------------------------------------------------------------------
C$           C:\                              Default share
AfuDM_abc123 C:\Temp\AfuDM-network-shares\abc
AfuDM_xyz789
             C:\Users\u\AppData\Local\Temp\AfuDM-network-shares\xyz
Belgeler     D:\Belgeler
The command completed successfully.
"""


class SmbTemizlikTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "net share yalniz Windows")
    def test_yalniz_afudm_paylasimlari_silinir(self):
        cagrilar = []

        def sahte(cmd, **kw):
            cagrilar.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, NET_CIKTI if cmd == ["net", "share"] else "", "")

        with patch("subprocess.run", side_effect=sahte), patch("shutil.rmtree") as rm:
            self.assertEqual(smb_paylasim.artiklari_temizle(), 2)
        silinen = [c[2] for c in cagrilar if "/delete" in c]
        self.assertEqual(silinen, ["AfuDM_abc123", "AfuDM_xyz789"])
        rm.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "net share yalniz Windows")
    def test_net_ciktisi_oem_kod_sayfasiyla_okunur(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            smb_paylasim.acik_paylasimlar()
        self.assertEqual(run.call_args.kwargs.get("encoding"), "oem")
        self.assertEqual(run.call_args.kwargs.get("errors"), "replace")

    @unittest.skipUnless(os.name == "nt", "net share yalniz Windows")
    def test_gercek_net_share_turkce_ciktida_cokmez(self):
        # Gercek komut: TR Windows'ta cp1254 ile okununca UnicodeDecodeError veriyordu.
        self.assertIsInstance(smb_paylasim.acik_paylasimlar(), list)


if __name__ == "__main__":
    unittest.main()
