"""Chrome'a otomatik ekleme — UCTAN UCA, gecici Chrome profiliyle.

Kullanicinin Chrome profiline DOKUNMAZ: `--user-data-dir` ile bos bir profil
acilir, test bitince yalniz o surecler kapatilir ve profil silinir.
ONKOSUL: Google Chrome kurulu. AfuDM'in acik olmasi GEREKMEZ.

Sinananlar:
  - otomasyonun bes adimi (sayfa, gelistirici modu, yukle, klasor, dogrula)
  - kurulan uzanti AfuDM'e KENDILIGINDEN baglaniyor (/pair) — uzantinin gercekten
    yuklenip calistiginin kaniti; eslestirme penceresi kurulumdan once acilir.
    (Profil dosyasina bakmak YANILTIR: Chrome tercihleri ~10 sn gecikmeli yazar,
    zorla kapatilinca hic yazmaz.)

Test kendi eslestirme sunucusunu acar (6811 doluysa sonraki boş port); uzanti
6811-6820'yi sirayla dener.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.server import LocalAPI  # noqa: E402
from core import chrome_kurulum  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {ayrinti}" if ayrinti else ""), flush=True)
    if not kosul:
        fails.append(ad)


def main() -> int:
    print("Chrome'a otomatik ekleme — uctan uca\n")
    if not chrome_kurulum.chrome_yolu():
        print("Chrome kurulu degil — test ATLANDI")
        return 0
    uc = ROOT / "data" / "api_endpoint.json"
    uc_yedek = uc.read_text("utf-8") if uc.exists() else None
    sunucu = LocalAPI(manager=None, port=6811)
    port = sunucu.start()
    if uc_yedek is not None:
        uc.write_text(uc_yedek, encoding="utf-8")  # start() calisan AfuDM'in kaydini ezer
    profil = Path(tempfile.mkdtemp(prefix="afudm_chrome_"))
    baslangic = time.time()
    try:
        ekleme = chrome_kurulum.OtomatikEkleme()
        ekleme.baslat(
            ek_argumanlar=[f"--user-data-dir={profil}", "--no-first-run", "--no-default-browser-check"],
            hedef_pid=-1,
            once=lambda: sunucu.open_pairing(120.0),
        )
        durum = chrome_kurulum.bekle_bitsin(ekleme, 180)
        for adim in chrome_kurulum.ADIMLAR:
            check(f"adim: {adim}", durum["adimlar"].get(adim) == "tamam", durum["adimlar"].get(adim, ""))
        check("otomasyon 'kuruldu' dedi", durum["sonuc"] == "kuruldu", durum["mesaj"])

        eslesti = False
        son = time.time() + 45
        while time.time() < son:
            if sunucu.son_eslesme >= baslangic:
                eslesti = True
                break
            time.sleep(0.5)
        check("uzanti AfuDM'e KENDILIGINDEN baglandi (/pair)", eslesti,
              f"port {port}, {round(sunucu.son_eslesme - baslangic, 1)} sn" if eslesti else "45 sn icinde istek yok")

    finally:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object "
                        f"{{ $_.CommandLine -like '*{profil}*' }} | ForEach-Object "
                        "{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                       capture_output=True)
        sunucu.stop()
        time.sleep(1)
        shutil.rmtree(profil, ignore_errors=True)

    print("\n" + ("Hepsi gecti" if not fails else "BASARISIZ: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
