# -*- coding: utf-8 -*-
"""aria2c motorunu indirir: engine/aria2c.exe (yalniz stdlib).

CI ve release hatti bunu cagirir: `python scripts/aria2_indir.py`.
Zip'i gecici klasore indirir, aria2c.exe'yi cikarir, calistigini dogrular
(`--version`), sonra engine/ altina tasir. Yarim indirme varolani bozmaz.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ADRES = ("https://github.com/aria2/aria2/releases/download/release-1.37.0/"
         "aria2-1.37.0-win-64bit-build1.zip")
ZIP_ICI = "aria2c.exe"
KOK = Path(__file__).resolve().parent.parent
HEDEF = KOK / "engine" / "aria2c.exe"


def main() -> int:
    gecici = Path(tempfile.mkdtemp(prefix="afudm_aria2_"))
    try:
        zip_yolu = gecici / "paket.zip"
        istek = urllib.request.Request(ADRES, headers={"User-Agent": "AfuDM-CI/1.0"})
        with urllib.request.urlopen(istek, timeout=120) as yanit, zip_yolu.open("wb") as f:
            shutil.copyfileobj(yanit, f)
        with zipfile.ZipFile(zip_yolu) as z:
            uye = next((u for u in z.namelist()
                        if u.replace("\\", "/").endswith(ZIP_ICI)), None)
            if uye is None:
                print(f"zip icinde {ZIP_ICI} bulunamadi", file=sys.stderr)
                return 1
            cikan = gecici / "aria2c.exe"
            with z.open(uye) as kaynak, cikan.open("wb") as f:
                shutil.copyfileobj(kaynak, f)
        proc = subprocess.run([str(cikan), "--version"], capture_output=True, timeout=60)
        if proc.returncode != 0 or not proc.stdout.strip():
            print("aria2c indi ama calismadi (bozuk indirme?)", file=sys.stderr)
            return 1
        HEDEF.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cikan, HEDEF)
        print(f"aria2c hazir: {HEDEF}")
        return 0
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
