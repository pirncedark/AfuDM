"""Static release-tool contracts that are safe to run without Windows UI access."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseToolsTest(unittest.TestCase):
    def test_ci_workflows_build_pyinstaller_before_packaging(self):
        for workflow in ("release.yml", "ci.yml"):
            source = (ROOT / ".github" / "workflows" / workflow).read_text(
                encoding="utf-8"
            )
            build_at = source.index("python -m PyInstaller --noconfirm --clean AfuDM.spec")
            package_at = source.index("build_release.ps1")
            self.assertLess(build_at, package_at, workflow)

    def test_build_release_rejects_missing_or_stale_executable(self):
        source = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("dist\\AfuDM.exe", source)
        self.assertIn("LastWriteTimeUtc", source)
        self.assertIn("core\\surum.py", source)
        self.assertIn("app.py", source)
        self.assertIn("GATE HATA", source)

    def test_verify_release_checks_embedded_executable_module(self):
        source = (ROOT / "scripts" / "verify_release.ps1").read_text(encoding="utf-8")
        self.assertIn("verify_exe.py", source)
        verifier = (ROOT / "scripts" / "verify_exe.py").read_text(encoding="utf-8")
        self.assertIn("CArchiveReader", verifier)
        self.assertIn("core.surum", verifier)
        self.assertIn("app", verifier)

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

    def test_desktop_api_exposes_the_global_version(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("def surum_bilgi", source)

    def test_quality_gate_workflow_covers_all_release_checks(self):
        source = (ROOT / ".github" / "workflows" / "quality-gate.yml").read_text(encoding="utf-8")
        android = (ROOT / ".github" / "workflows" / "android-debug.yml").read_text(encoding="utf-8")
        security = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
        ui_test = (ROOT / "tests" / "ui_ux_gate_test.py").read_text(encoding="utf-8")
        source += android + security + ui_test
        for required in (
            "pull_request:", "push:", "workflow_call:",
            "desktop-tests:", "ui-gate:", "deletion-recovery:",
            "android-build:", "security:", "package-verify:",
            "quality-gate:", "scripts/test.ps1", "assembleDebug",
            "gitleaks", "build_exe.ps1", "build_release.ps1",
            "verify_release.ps1", "smoke_test.ps1", "AFUDM_TEST_VIEWPORT",
            "AFUDM_TEST_DPR", "AFUDM_TEST_LANG", "console.error",
        ):
            self.assertIn(required, source)

    def test_release_workflow_waits_for_quality_gate(self):
        source = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("quality-gate:", source)
        self.assertIn("uses: ./.github/workflows/quality-gate.yml", source)
        self.assertIn("needs: quality-gate", source)


if __name__ == "__main__":
    unittest.main()
