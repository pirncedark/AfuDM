"""Rust release contracts; no GUI, live instance or network access."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReleaseToolsTest(unittest.TestCase):
    def test_version_reader_matches_all_product_versions(self):
        version = subprocess.check_output(
            [sys.executable, "-B", str(ROOT / "scripts/surum_oku.py")], text=True
        ).strip()
        for path, table in (("rs/Cargo.toml", "workspace"), ("rs/app/Cargo.toml", None)):
            data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
            if table:
                data = data[table]
            self.assertEqual(version, data["package"]["version"])
        self.assertEqual(version, json.loads((ROOT / "rs/app/tauri.conf.json").read_text())["version"])

    def test_release_please_updates_only_workspace_packages_in_cargo_locks(self):
        def read_toml(path):
            return tomllib.loads((ROOT / path).read_text(encoding="utf-8"))

        workspace = read_toml("rs/Cargo.toml")["workspace"]
        workspace_names = {
            read_toml(f"rs/{member}/Cargo.toml")["package"]["name"]
            for member in workspace["members"]
        }
        app_name = read_toml("rs/app/Cargo.toml")["package"]["name"]
        expected_by_lock = {
            "rs/Cargo.lock": workspace_names,
            "rs/app/Cargo.lock": workspace_names | {app_name},
        }
        config = json.loads(
            (ROOT / "release-please-config.json").read_text(encoding="utf-8")
        )
        extra_files = config["packages"]["."]["extra-files"]
        for lock_path, expected_names in expected_by_lock.items():
            with self.subTest(lock=lock_path):
                packages = read_toml(lock_path)["package"]
                local_packages = [p for p in packages if "source" not in p]
                self.assertCountEqual(
                    [p["name"] for p in local_packages], expected_names
                )
                # Exact name filters prevent wildcard/index selectors from
                # silently bumping registry or git dependencies after reordering.
                self.assertCountEqual(
                    [entry for entry in extra_files
                     if isinstance(entry, dict) and entry.get("path") == lock_path],
                    [
                        {
                            "type": "toml",
                            "path": lock_path,
                            "jsonpath": f"$.package[?(@.name.value=='{name}')].version",
                        }
                        for name in expected_names
                    ],
                )

    def test_quality_gate_collects_every_job(self):
        jobs = yaml.safe_load((ROOT / ".github/workflows/quality-gate.yml").read_text())["jobs"]
        self.assertEqual(set(jobs["quality-gate"]["needs"]), set(jobs) - {"quality-gate"})
        self.assertTrue({"rust", "extension-tests", "android-build", "security"} <= jobs.keys())

    def test_release_builds_before_packaging_and_waits_for_gate(self):
        source = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("needs: quality-gate", source)
        self.assertLess(source.index("scripts\\build_release_rust.ps1"), source.index("Compress-Archive"))
        rust = (ROOT / "scripts/build_release_rust.ps1").read_text(encoding="utf-8")
        self.assertIn('"build", "--release", "--locked"', rust)
        self.assertIn('"--manifest-path", "rs/app/Cargo.toml"', rust)
        build_at = rust.index("& cargo @cargoArgs")
        check_at = rust.index("if ($LASTEXITCODE -ne 0)", build_at)
        copy_at = rust.index("Copy-Item -LiteralPath $binary")
        self.assertLess(build_at, check_at)
        self.assertLess(check_at, copy_at)
        self.assertIn('throw "Rust release derlemesi basarisiz"', rust[check_at:copy_at])
        self.assertLess(copy_at, rust.index("Compress-Archive"))

    def test_rust_only_package_verification(self):
        for name in ("verify_release.ps1", "smoke_test.ps1"):
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn('[ValidateSet("Rust")]', source)
            self.assertNotIn("verify_exe.py", source)
            self.assertNotIn("core/surum.py", source)
        source = (ROOT / "scripts/verify_release.ps1").read_text(encoding="utf-8")
        for check in ("ProductVersion", "engine/aria2c.exe", "extension/download-handoff.js", "34404"):
            self.assertIn(check, source)


if __name__ == "__main__":
    unittest.main()
