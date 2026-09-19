# -*- coding: utf-8 -*-
"""Isletimsel sozlesme testleri (kullanici onayli v1.3.2 guclendirmesi).

1) STALE ENDPOINT: api_endpoint.json var ama islem olu / baska servis → CLI
   sunucuyu taniyamaz, `--no-start` ile exit 2 dondurur.
2) CIFT CLI AUTO-START: iki surec ayni anda `afuadm` cagirirsa (kilit dosyasi
   O_CREAT|O_EXCL tabanli) YALNIZ BIRI AfuDM'i spawn eder; digeri /ping
   sayesinde baslatmadan baglanir.
3) GECMIS --start-at: CLI `add` '23:30'yi gecmisse server tarafini besler;
   zamanlama semantigi cli_test'te yerel saat dogrulanir.
4) JSON SAFLIGI + EXIT KODLARI + TOKEN SIZMASI: --json'da stdout SADECE
   JSON/NDJSON olur, mesajlar/hatalar stderr'e gider; 0/2/3/4 kodlari; token
   hicbir ciktiya sizmaz.
"""
from __future__ import annotations

import io
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

import afuadm  # noqa: E402
from core import paths  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


class _Sunucu(BaseHTTPRequestHandler):
    token = "TEST-TOKEN-GIZLI"
    alinan: list[tuple[str, dict, dict]] = []  # (yol, govde, basliklar)
    kayip = {"ok": False, "code": "KAYIT_YOK",
             "message": "kayit bulunamadi: kayip", "error": "kayit bulunamadi: kayip"}

    def log_message(self, fmt, *args):
        pass

    def _json(self, durum: int, govde: dict) -> None:
        body = json.dumps(govde, ensure_ascii=False).encode("utf-8")
        self.send_response(durum)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _oku(self) -> dict:
        uz = int(self.headers.get("Content-Length") or 0)
        if not uz:
            return {}
        try:
            return json.loads(self.rfile.read(uz).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        yol = self.path.split("?")[0]
        if yol == "/ping":
            self._json(200, {"ok": True, "app": "AfuDM"})
        elif yol == "/snapshot":
            self._json(200, {"ok": True, "items": [], "engine_ok": True,
                             "download_dir": "C:/test", "lang": "tr",
                             "settings": {"hiz_profili": "normal"},
                             "stat": {"downloadSpeed": 0, "uploadSpeed": 0,
                                      "numActive": 0, "numWaiting": 0, "numStopped": 0}})
        else:
            self._json(404, {"ok": False, "code": "BILINMEYEN_YOL",
                             "message": "bilinmeyen yol", "error": "bilinmeyen yol"})

    def do_POST(self):
        govde = self._oku()
        self.__class__.alinan.append((self.path, govde, dict(self.headers)))
        if self.path == "/add":
            self._json(200, {"ok": True, "id": 7, "gid": "g1", "kind": "http"})
        elif self.path == "/control":
            if govde.get("gid") == "kayip":
                self._json(400, dict(self.__class__.kayip))
            else:
                self._json(200, {"ok": True})
        else:
            self._json(404, {"ok": False, "code": "BILINMEYEN_YOL",
                             "message": "bilinmeyen yol", "error": "bilinmeyen yol"})


def _sunucu_baslat() -> tuple[ThreadingHTTPServer, int]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Sunucu)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_port


def _endpoint_yaz(tmp: Path, port: int, token: str = _Sunucu.token) -> Path:
    dosya = tmp / "api_endpoint.json"
    dosya.write_text(json.dumps({"port": port, "token": token}), encoding="utf-8")
    return dosya


def _serbest_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


tmp = Path(tempfile.mkdtemp(prefix="afudm_surum_"))
paths.DATA = tmp  # _servis/_baslatmak bu surecte gecici DATA kullanir

# ---- 1) stale endpoint ----------------------------------------------------
print("1) Stale endpoint")
_stale_port = _serbest_port()
osob = _endpoint_yaz(tmp, _stale_port)  # port dolu degil, islem olu
try:
    afuadm._ac(no_start=True)
    check("oliu endpoint --no-start RED", False)
except afuadm.CliHata as exc:
    check("oliu endpoint --no-start exit 2", exc.kod == afuadm.CC_YOK, str(exc.kod))

# port dolu ama yanlis servis (kimlik sagligi)
class _Yabanci(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = b'{"ok": true, "app": "BASKA-SERVIS"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
_yab = ThreadingHTTPServer(("127.0.0.1", 0), _Yabanci)
threading.Thread(target=_yab.serve_forever, daemon=True).start()
_endpoint_yaz(tmp, _yab.server_port)
check("yabanci servis AfuDM sayilmaz", not afuadm._ping(_yab.server_port))
try:
    afuadm._ac(no_start=True)
    check("yabanci servis --no-start RED", False)
except afuadm.CliHata as exc:
    check("yabanci servis exit 2", exc.kod == afuadm.CC_YOK)
_yab.shutdown()
_yab.server_close()

# ---- 2) cift CLI auto-start (kilit yarisi) ---------------------------------
print("2) Cift CLI auto-start yarisi")
_gorLen_popen = []
_server2, port2 = _sunucu_baslat()


def _sahte_popen(cmd, **kw):
    _gorLen_popen.append(1)

    def _ac_later():
        time.sleep(0.6)
        _endpoint_yaz(tmp, port2)  # servis hazir; artik ping gecer
    threading.Thread(target=_ac_later, daemon=True).start()
    return object()  # subprocess.Popen donus degeri kullanilmaz


afuadm.subprocess.Popen = _sahte_popen
afuadm.BAGLANMA_BEKLEME = 8.0
sonuc1: list[int] = []
sonuc2: list[int] = []


def _kos_ac():
    try:
        afuadm._ac(no_start=False)
        sonuc1.append(0)
    except afuadm.CliHata as exc:
        sonuc1.append(exc.kod)


def _kos_ac2():
    try:
        afuadm._ac(no_start=False)
        sonuc2.append(0)
    except afuadm.CliHata as exc:
        sonuc2.append(exc.kod)


t1 = threading.Thread(target=_kos_ac)
t2 = threading.Thread(target=_kos_ac2)
t1.start()
t2.start()
t1.join(timeout=12)
t2.join(timeout=12)
check("iki istemci de baglandi", sonuc1 == [0] and sonuc2 == [0], (sonuc1, sonuc2))
check("YALNIZ bir spawn (kilit calisti)", len(_gorLen_popen) == 1, str(_gorLen_popen))
# kilit dosyasi temizlenmis olmali
check("kilit dosyasi kaldi mi", not (tmp / "afuadm_baslat.lock").exists())
afuadm.subprocess.Popen = subprocess.Popen  # geri yukle

# ---- 3) gecmis --start-at CLI uzerinden ------------------------------------
print("3) Gecmis --start-at (CLI -> srv)")
_Sunucu.alinan.clear()
_endpoint_yaz(tmp, port2)
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["add", "https://ornek.com/d.zip", "--start-at", "00:00"])
check("add --start-at cikis 0", kod == 0, str(kod))
yol, govde, basliklar = _Sunucu.alinan[-1]
check("server start_at'i aldi", govde.get("start_at") == "00:00", str(govde))
tok_baslik = next((v for k, v in basliklar.items()
                   if k.lower() == "x-afudm-token"), None)
check("token baslikla gitti", tok_baslik == _Sunucu.token, str(basliklar))

print("4) JSON safinligi + exit kodlari + token")
# 4a. --no-start status: sunucu yok (dosyayi sil)
(tmp / "api_endpoint.json").unlink(missing_ok=True)
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["--no-start", "status", "--json"])
check("4a sunucu yok: exit 2", kod == 2, str(kod))
check("4a stdout SAF (bos)", cikis.getvalue() == "", repr(cikis.getvalue()))
check("4a hata stderr'de", "HATA" in hata.getvalue())

# 4b. KAYIT_YOK -> exit 3, stdout saf boş
_endpoint_yaz(tmp, port2)
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["remove", "kayip", "--json"])
check("4b KAYIT_YOK: exit 3", kod == 3, str(kod))
check("4b stdout SAF (bos)", cikis.getvalue() == "", repr(cikis.getvalue()))

# 4b1. remove --delete-files: body'de delete_files=true ile gider (vs duz remove)
_Sunucu.alinan.clear()
with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    kod1 = afuadm.main(["remove", "g1", "--delete-files"])
with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    kod2 = afuadm.main(["remove", "g1"])
_, govde1, _ = _Sunucu.alinan[0]
_, govde2, _ = _Sunucu.alinan[1]
check("4b1 remove --delete-files true", kod1 == 0 and govde1.get("delete_files") is True, str(govde1))
check("4b1 duz remove false", kod2 == 0 and govde2.get("delete_files") is False, str(govde2))

# 4c. status --json: tek satir JSON, icerik ayristirilabilir
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["status", "--json"])
satirlar = [s for s in cikis.getvalue().splitlines() if s.strip()]
check("4c exit 0", kod == 0)
check("4c tek JSON satiri", len(satirlar) == 1, cikis.getvalue())
_govde = json.loads(satirlar[0])
check("4c JSON alanlari var", "hiz_profili" in _govde and "stat" in _govde, str(_govde))

# 4d. mode --json (argumanisiz): tek satir JSON
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["mode", "--json"])
satirlar = [s for s in cikis.getvalue().splitlines() if s.strip()]
check("4d mode --json tek satir", kod == 0 and len(satirlar) == 1
      and json.loads(satirlar[0]) == {"hiz_profili": "normal"}, cikis.getvalue())

# 4di. kok --json / --no-start (subparser clobber'i duzeltildi)
cikis = io.StringIO(); hata = io.StringIO()
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.main(["--json", "status"])
satirlar = [s for s in cikis.getvalue().splitlines() if s.strip()]
check("4di kok --json korunuyor", kod == 0 and len(satirlar) == 1
      and json.loads(satirlar[0]).get("stat"), cikis.getvalue())

# 4e. watch --json KeyboardInterrupt: NDJSON, ekstra yeni satir/iz yok
_gorilen_snap = [{
    "ok": True, "items": [{"gid": "g1", "status": "active", "progress": 33.5,
                           "downloadSpeed": 0, "title": "t"}],
}]
kac = {"n": 0}


def _sabit_snap(yontem, yol):
    if kac["n"] >= 2:
        raise KeyboardInterrupt()
    kac["n"] += 1
    return _gorilen_snap[0]


afuadm._istek = _sabit_snap
import argparse
cikis = io.StringIO(); hata = io.StringIO()
tas = argparse.Namespace(json=True, gid=None, interval=0.2)
with redirect_stdout(cikis), redirect_stderr(hata):
    kod = afuadm.komut_watch(tas)
satirlar = cikis.getvalue().splitlines()
check("4e watch NDJSON 2 satir, ozel benzer", kod == 0 and len(satirlar) == 2, repr(cikis.getvalue()))
check("4e her satir gecerli JSON", all(json.loads(s) for s in satirlar))
check("4e stderr bos degil iz yok", "\x1b" not in cikis.getvalue())

# 4f. token hicbir ciktiya sizmaz
_tum_cikti = ""
for _c in (cikis.getvalue(), hata.getvalue()):
    _tum_cikti += _c
check("token ciktilarda YOK", _Sunucu.token not in _tum_cikti)

tmp_sunucu_2 = None
_server2.shutdown()
_server2.server_close()

print("\nisletim: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: cli surum sozlesmesi tutarli")