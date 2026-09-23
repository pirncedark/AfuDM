from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paketle  # noqa: E402


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
            (kaynak / ad).symlink_to(ROOT / ad, target_is_directory=True)
        (kaynak / "engine").mkdir()
        for ad in paketle.CEKIRDEK_MOTORLAR:
            (kaynak / "engine" / ad).write_bytes(b"test motoru")

        cikti = gecici_yol / "build_out" / "paket"
        with patch.object(paketle, "KOK", kaynak), patch.object(paketle, "CIKTI", cikti):
            paket = paketle.paketle(tam=False)

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


if __name__ == "__main__":
    test_release_bundle_imports_without_checkout_path()
    print("Paket import testi gecti.")
