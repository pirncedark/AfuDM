# -*- coding: utf-8 -*-
"""Fake HTTP sunucusu davranis testleri (Foundation v1.4).

Tam indirme, Range/206 resume, Basic auth 401->200, 403, 302 takip,
yarida kesilme (IncompleteRead) sonrasi resume+checksum.
"""
from __future__ import annotations

import base64
import http.client
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_http import SunucuAyarlari, baslat  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


def _get(port: int, yol: str = "/", basliklar: dict | None = None):
    istek = urllib.request.Request(
        f"http://127.0.0.1:{port}{yol}", headers=basliklar or {})
    with urllib.request.urlopen(istek, timeout=5) as y:
        return y.status, y.headers, y.read()


print("1) Tam indirme + checksum")
veri = hashlib.sha256(b"AfuDM").digest() * 3  # 96 bayt, deterministik
ay = SunucuAyarlari(veri=veri)
port, httpd = baslat(ay)
durum, baslik, govde = _get(port)
check("200 + Content-Length", durum == 200 and int(baslik["Content-Length"]) == len(govde),
      str((durum, baslik.get("Content-Length"))))
check("veri birebir", govde == veri)
check("checksum SHA256", hashlib.sha256(govde).hexdigest() == hashlib.sha256(veri).hexdigest())
check("Accept-Ranges var", baslik.get("Accept-Ranges") == "bytes", str(baslik))
httpd.shutdown(); httpd.server_close()

print("2) Range / resume (206)")
veri = rastgele = None
from fake_http import rastgele_bytes
veri = rastgele_bytes(100_000, tohum=7)
ay = SunucuAyarlari(veri=veri)
port, httpd = baslat(ay)
durum, baslik, govde = _get(port, basliklar={"Range": "bytes=50000-"})
check("206 dondu", durum == 206, str(durum))
check("Content-Range dogru", baslik.get("Content-Range") == f"bytes 50000-{len(veri)-1}/{len(veri)}",
      baslik.get("Content-Range"))
check("offset'ten itibaren geldi", govde == veri[50000:], str(len(govde)))
check("kalanin checksum'u", hashlib.sha256(govde).hexdigest() == hashlib.sha256(veri[50000:]).hexdigest())
durum, _, tammGovde = _get(port)
check("tamindirme hala 200", durum == 200 and tammGovde == veri)
httpd.shutdown(); httpd.server_close()

print("3) Basic auth: anasiz 401, dogru ile 200")
veri = b"gizli veri"
ay = SunucuAyarlari(veri=veri, temel_auth=("kullanici", "sifre"))
port, httpd = baslat(ay)
try:
    _get(port)
    check("anasiz RED", False)
except urllib.error.HTTPError as h:
    check("anasiz 401", h.code == 401, str(h.code))
    check("WWW-Authenticate Basic", h.headers.get("WWW-Authenticate", "").startswith("Basic"))
ok = "Basic " + base64.b64encode(b"kullanici:sifre").decode()
durum, _, govde = _get(port, basliklar={"Authorization": ok})
check("dogru auth ile 200 + veri", durum == 200 and govde == veri)
yanlis = "Basic " + base64.b64encode(b"kullanici:yanlis").decode()
try:
    _get(port, basliklar={"Authorization": yanlis})
    check("yanlis sifre RED", False)
except urllib.error.HTTPError as h:
    check("yanlis sifre 401", h.code == 401, str(h.code))
httpd.shutdown(); httpd.server_close()

print("4) 403 yasak")
ay = SunucuAyarlari(veri=b"x", yasakli=True)
port, httpd = baslat(ay)
try:
    _get(port)
    check("403 RED", False)
except urllib.error.HTTPError as h:
    check("403 403", h.code == 403, str(h.code))
httpd.shutdown(); httpd.server_close()

print("5) 302 redirect takibi")
veri = b"hedef sayfa"
ay = SunucuAyarlari(veri=veri, yonlendir="/hedef")
port, httpd = baslat(ay)
durum, _, govde = _get(port, "/eski")
check("302 takip edildi (200)", durum == 200 and govde == veri, str(durum))
check("log'da 2 istek (eski + yeni)", len(ay.log) == 2, str(len(ay.log)))
httpd.shutdown(); httpd.server_close()

print("6) Baglanti yarida kesilir (drop) -> resume ile tamamlanir + checksum")
veri = rastgele_bytes(60_000, tohum=11)
ay = SunucuAyarlari(veri=veri, drop_sonrasi_bayt=25_000)
port, httpd = baslat(ay)
try:
    _get(port)
    check("drop beklenen hata RED", False)
except (urllib.error.URLError, http.client.IncompleteRead) as e:
    check("drop istemci hatasi (IncompleteRead) aldı", True)
except urllib.error.HTTPError:
    check("drop URI olmamali", False)
# Gercek istemci (aria2) kalanini Range ile ister; biz de oyle yapariz:
iritilen = 0
parcalar = []
while iritilen < len(veri):
    durum, baslik, govde = _get(port, basliklar={"Range": f"bytes={iritilen}-"})
    parcalar.append(govde)
    iritilen += len(govde)
birlestirilmis = b"".join(parcalar)
check("resume hic bayt kaybetmedi", birlestirilmis == veri, f"{len(birlestirilmis)}/{len(veri)}")
check("birlesik checksum dogru", hashlib.sha256(birlestirilmis).hexdigest()
      == hashlib.sha256(veri).hexdigest())
httpd.shutdown(); httpd.server_close()

print("\nfake_http: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: fake HTTP davranislari tutarli")