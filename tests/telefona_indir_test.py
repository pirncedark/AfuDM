# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERVER_PY = ROOT / "api" / "server.py"
MOBIL_HTML = ROOT / "ui" / "mobil.html"

fails: list[str] = []

def check(ad: str, kosul: bool, detay: str = "") -> None:
    durum = "GECTI" if kosul else "DUSTU"
    print(f"  [{durum}] {ad}")
    if not kosul:
        fails.append(ad + (f" ({detay})" if detay else ""))

print("1) API /indir endpoint'i")
srv_kod = SERVER_PY.read_text(encoding="utf-8")
check("server.py'de /indir yolu mevcut", 'parsed.path == "/indir"' in srv_kod)
check("Dosya icerik tipi ayarli", '"Content-Type", "application/octet-stream"' in srv_kod)
check("Indirme basligi ekli (Content-Disposition)", '"Content-Disposition"' in srv_kod and 'filename*=UTF-8' in srv_kod)
check("Dosya icerigini basariyla donduruyor (shutil)", "shutil.copyfileobj(dosya, self.wfile)" in srv_kod)

print("2) Mobil Arayuz (mobil.html) - PWA kurulum ve Dosya İndirme")
html_kod = MOBIL_HTML.read_text(encoding="utf-8")
check("Telefona Indir butonu eklendi", 'data-eylem="indir"' in html_kod and 'Telefona İndir' in html_kod)
check("Butona basilinca /indir yoluna yonlendiriliyor", 'window.location.href = "/indir?gid="' in html_kod)
check("PWA Kurulum butonu var (APK/PWA)", 'id="pwaKur"' in html_kod and 'Uygulamayı Kur' in html_kod)
check("Tarayici uyarisi iceriyor (HTTP icin manuel menu uyari fall-back'i)", "Ana Ekrana Ekle" in html_kod and "alert(" in html_kod)
check("Klasor seciminde varsayilan klasor adi gosteriliyor", "veri.ana ?" in html_kod and "varsayılan" in html_kod)

print()
if fails:
    print(f"BASARISIZ ({len(fails)} test dustu):", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
