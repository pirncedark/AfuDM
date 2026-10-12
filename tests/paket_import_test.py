from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paketle  # noqa: E402

PROMPT_ASSETS = ("ui/download.html", "ui/download.js", "extension/download-handoff.js", "extension/download-preflight.js")


def test_release_bundle_imports_without_checkout_path() -> None:
    with tempfile.TemporaryDirectory(prefix="afudm-paket-test-") as gecici:
        gecici_yol = Path(gecici)
        kaynak = gecici_yol / "kaynak"
        kaynak.mkdir()

        for ad in paketle.KOPYALANACAK_DOSYALAR:
            dosya = ROOT / ad
            (kaynak / ad).write_bytes(
                dosya.read_bytes() if dosya.is_file() else b"test placeholder"
            )
        for ad in paketle.KOPYALANACAK_KLASORLER:
            shutil.copytree(ROOT / ad, kaynak / ad, ignore=shutil.ignore_patterns("__pycache__"))
        (kaynak / "engine").mkdir()
        for ad in paketle.CEKIRDEK_MOTORLAR:
            (kaynak / "engine" / ad).write_bytes(b"test motoru")

        cikti = gecici_yol / "build_out" / "paket"
        with patch.object(paketle, "KOK", kaynak), patch.object(paketle, "CIKTI", cikti):
            paket = paketle.paketle(tam=False)

        for ad in PROMPT_ASSETS:
            assert (paket / ad).read_bytes() == (ROOT / ad).read_bytes(), ad
        # The extension directory is the unpacked browser package shipped in release.
        assert "download-handoff.js" in (paket / "extension/background.js").read_text(encoding="utf-8")
        archive = shutil.make_archive(str(gecici_yol / "release"), "zip", root_dir=cikti, base_dir="AfuDM")
        with zipfile.ZipFile(archive) as release:
            for ad in PROMPT_ASSETS:
                assert release.read("AfuDM/" + ad) == (ROOT / ad).read_bytes(), ad

        ortam = os.environ.copy()
        ortam.pop("PYTHONPATH", None)
        calistir = subprocess.run(
            [sys.executable, "-c", "import core.manager, api.server, headless"],
            cwd=str(paket),
            env=ortam,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=30,
        )
        assert calistir.returncode == 0, (
            f"Paket importlari basarisiz (exit {calistir.returncode}):\n"
            f"{calistir.stdout}\n{calistir.stderr}"
        )


def test_exe_asset_gate_rejects_missing_and_empty_assets() -> None:
    from scripts.verify_exe import REQUIRED_ASSETS, verify_assets

    class Archive:
        def __init__(self, contents):
            self.contents = contents
            self.toc = dict.fromkeys(contents)

        def extract(self, name):
            return self.contents[name]

    contents = {name.replace("/", "\\"): b"asset" for name in REQUIRED_ASSETS}
    verify_assets(Archive(contents))
    for asset in REQUIRED_ASSETS:
        for empty in (False, True):
            broken = dict(contents)
            key = asset.replace("/", "\\")
            if empty:
                broken[key] = b""
            else:
                del broken[key]
            try:
                verify_assets(Archive(broken))
            except RuntimeError as exc:
                assert asset in str(exc)
            else:
                raise AssertionError(f"Invalid embedded asset accepted: {asset}")


def test_packaging_gates_include_prompt_assets() -> None:
    import ast

    spec = ast.parse((ROOT / "AfuDM.spec").read_text(encoding="utf-8-sig"))
    analysis = next(node for node in ast.walk(spec) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Analysis")
    datas = ast.literal_eval(next(kw.value for kw in analysis.keywords if kw.arg == "datas"))
    assert ("ui", "ui") in datas
    assert ("extension", "extension") in datas
    for script in ("build_exe.ps1", "build_release.ps1", "verify_release.ps1"):
        source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        for asset in PROMPT_ASSETS:
            assert asset in source, (script, asset)


if __name__ == "__main__":
    test_release_bundle_imports_without_checkout_path()
    test_exe_asset_gate_rejects_missing_and_empty_assets()
    test_packaging_gates_include_prompt_assets()
    print("Paket import testi gecti.")
