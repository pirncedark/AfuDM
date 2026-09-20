"""Static release-tool contracts that are safe to run without Windows UI access."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseToolsTest(unittest.TestCase):
    def test_release_package_includes_support_launchers(self):
        source = (ROOT / "paketle.py").read_text(encoding="utf-8")
        for name in ("tani.bat", "web_panel_baslat.bat", "debug_modu.bat"):
            self.assertIn(f'"{name}"', source)
        self.assertIn("make_archive", source)

    def test_diagnostics_collects_and_redacts_one_zip_report(self):
        source = (ROOT / "tani.bat").read_text(encoding="utf-8")
        for required in (
            "systeminfo", "aria2c.exe", "last error", "REDACTED",
            "Compress-Archive", "support-report", "redact", "error summary",
            "Users\\REDACTED", "api_token.txt", "rpc_secret.txt",
        ):
            self.assertIn(required, source)
        self.assertNotIn("2^>", source)
        self.assertNotIn("^|", source)

    def test_test_runner_executes_ui_gates(self):
        source = (ROOT / "scripts" / "test.ps1").read_text(encoding="utf-8")
        self.assertIn('"tests/ui_startup_test.py"', source)
        self.assertIn('"tests/ui_ux_gate_test.py"', source)


if __name__ == "__main__":
    unittest.main()
