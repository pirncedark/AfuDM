#!/usr/bin/env python3
"""T1: Python <-> Rust kara kutu uyum testi.

Kullanim:  python rs\\tests_parity\\uyum_testi.py

Ayni HTTP istek dizisini eski Python AfuDM'e (kaynaktan, headless) ve yeni Rust
AfuDM.exe'ye (kopyasindan) gonderir; yanitlarin SEKLINI karsilastirir
(anahtar kumesi, tip, durum kodu, CORS/icerik basliklari, ikili govde hash'i).
Gid, zaman, yol ve token degerleri karsilastirilmaz.

Guvenlik kurallari:
- Kullanicinin calisan AfuDM'ine (6811, P\\data) dokunmaz. Python verisi
  AFUDM_DATA_ROOT ile, Rust verisi exe'nin yanindaki gecici klasorle ayrilir.
- Python aria2 RPC portu AFUDM_RPC_PORT ile ayrilir. Rust kopyasi kendi gecici
  secret'i ile calistigi icin kullanicinin aria2'sine baglanamaz.
- Pencere acan uclar kullanilmaz: /show, /linkgrabber (UI yolu),
  /_listener/quit|exit|notify.
- Bitince surecler ve gecici klasorde calisan her sey kapatilir.

Cikis kodu: 0 = kritik fark yok, 1 = kritik fark var, 2 = kurulum hatasi.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import http.client
import http.server
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from functools import partial
from pathlib import Path

RS = Path(__file__).resolve().parents[1]
PY_ROOT = Path(r"C:\Users\afuuu\Desktop\afuproject\AfuDM")
RS_EXE = RS / "app" / "target" / "release" / "AfuDM.exe"
RAPOR_DIR = RS / "tests_parity" / "rapor"
SENARYO_DIR = RS / "tests_parity" / "senaryolar"
BLOB_BYTES = random.Random(7).randbytes(2048)
KIMLIK_YANLIS = "yanlis-token-degeri"

# Bu anahtarlarin degeri farkliysa kritik sayilir (ok bayragi = istek basarisi).
KRITIK_DEGER_ANAHTARLARI = ("ok",)

WRAPPER = r'''
import os, sys, time
sys.dont_write_bytecode = True
pdir, port, rpc, data_root = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, pdir)
os.environ["AFUDM_DATA_ROOT"] = data_root
from core.baslangic import uyku_yollarini_ayarla
uyku_yollarini_ayarla()
from core import daemon as _d, ornek, paths
_d.RPC_PORT = rpc
_d.RPC_PORT_SON = rpc + 10
from core.manager import Manager
from core.servis import AfuDMServis
from api.server import LocalAPI, _Handler
paths.ensure_dirs()
manager = Manager()
manager.start()
# T1 ikinci tur: kaydetme penceresi kapali -> /add dogrudan indirir, bekleyen kuyruga dusmez.
manager.store.set("kaydetme_penceresi", False)
servis = AfuDMServis(manager, kip=ornek.KIP_HEADLESS)
_Handler.servis = servis
api = LocalAPI(manager, port=port, lan=False)
p = api.start()
print("HAZIR", p, flush=True)
while True:
    time.sleep(1)
'''


def bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def bencode(x) -> bytes:
    if isinstance(x, int):
        return b"i%de" % x
    if isinstance(x, str):
        x = x.encode("utf-8")
    if isinstance(x, bytes):
        return b"%d:" % len(x) + x
    if isinstance(x, list):
        return b"l" + b"".join(bencode(i) for i in x) + b"e"
    if isinstance(x, dict):
        return b"d" + b"".join(bencode(k) + bencode(x[k]) for k in sorted(x)) + b"e"
    raise TypeError(type(x))


def hazirla_dosyalar(serve: Path, fs_url: str, blob: Path) -> None:
    """Yerel HTTP sunucusunun sunacagi test dosyalari (dis internet yok)."""
    rnd = random.Random(42)
    (serve / "paket").mkdir(parents=True, exist_ok=True)
    for ad, boyut in (("a.bin", 65536), ("b.bin", 4096), ("c.bin", 2048),
                      ("d.bin", 2048), ("e.bin", 262144), ("f.bin", 262144)):
        (serve / ad).write_bytes(rnd.randbytes(boyut))
    paket_a = rnd.randbytes(32768)
    paket_b = rnd.randbytes(20000)
    (serve / "paket" / "a.bin").write_bytes(paket_a)
    (serve / "paket" / "b.bin").write_bytes(paket_b)
    veri = paket_a + paket_b
    parca = 16384
    pieces = b"".join(hashlib.sha1(veri[i:i + parca]).digest() for i in range(0, len(veri), parca))
    info = {"name": "paket", "piece length": parca, "pieces": pieces,
            "files": [{"length": len(paket_a), "path": ["a.bin"]},
                      {"length": len(paket_b), "path": ["b.bin"]}]}
    # web-seed: multi-file torrent icin url-list kok adresi (port bilindikten sonra).
    (serve / "paket.torrent").write_bytes(bencode({"info": info, "url-list": fs_url + "/"}))
    blob.write_bytes(BLOB_BYTES)


class SessizIstekci(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def dosya_sunucusu_baslat(serve: Path, port: int):
    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), partial(SessizIstekci, directory=str(serve)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Istemci:
    """Tek sunucuya istek atar; IP basina 60 sn'de 120 sinirini asmamak icin dengeler."""

    def __init__(self, ad: str, port: int, token: str):
        self.ad, self.port, self.token = ad, port, token
        self.zamanlar: collections.deque = collections.deque()

    def _bekle(self):
        while True:
            simdi = time.time()
            while self.zamanlar and simdi - self.zamanlar[0] > 60:
                self.zamanlar.popleft()
            if len(self.zamanlar) < 110:
                break
            time.sleep(max(0.2, 60 - (simdi - self.zamanlar[0]) + 0.5))
        self.zamanlar.append(time.time())

    def istek(self, yontem, yol, kimlik="T", baslik=None, govde=None, ham=None):
        self._bekle()
        h = dict(baslik or {})
        if kimlik == "T":
            h["X-AfuDM-Token"] = self.token
        elif kimlik == "bozuk":
            h["X-AfuDM-Token"] = KIMLIK_YANLIS
        data = None
        if govde is not None:
            data = json.dumps(govde, ensure_ascii=False).encode("utf-8")
            h.setdefault("Content-Type", "application/json; charset=utf-8")
        elif ham is not None:
            data = ham
            h.setdefault("Content-Type", "application/octet-stream")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request(yontem, yol, body=data, headers=h)
            r = conn.getresponse()
            raw = r.read()
            return {"status": r.status, "headers": {k.lower(): v for k, v in r.getheaders()},
                    "body": raw}
        except Exception as exc:  # baglanti hatasi da bir sonuctur
            return {"status": 0, "headers": {}, "body": b"", "hata": str(exc)}
        finally:
            conn.close()


def tip(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "sayi"
    if isinstance(v, str):
        return "metin"
    if isinstance(v, dict):
        return "nesne"
    if isinstance(v, list):
        return "liste"
    return type(v).__name__


def karsilastir(a, b, yol="$") -> list[tuple[str, str, str]]:
    """Sekil karsilastirmasi. Donus: (sinif, yol, aciklama). Siniflar: kritik/orta/kozmetik."""
    out: list[tuple[str, str, str]] = []
    ta, tb = tip(a), tip(b)
    if ta != tb:
        out.append(("orta", yol, f"tip Python={ta} Rust={tb}"))
        return out
    if ta == "nesne":
        for k in a:
            if k not in b:
                out.append(("kritik", f"{yol}.{k}", "Rust'ta anahtar yok"))
            else:
                out += karsilastir(a[k], b[k], f"{yol}.{k}")
        for k in b:
            if k not in a:
                out.append(("orta", f"{yol}.{k}", "Rust'ta fazla anahtar"))
    elif ta == "liste":
        if a and b:
            out += karsilastir(a[0], b[0], yol + "[0]")
        elif bool(a) != bool(b):
            out.append(("kozmetik", yol, "bos/dolu farki (veri zamanlamasi olabilir)"))
    else:
        anahtar = yol.rsplit(".", 1)[-1]
        if anahtar in KRITIK_DEGER_ANAHTARLARI and a != b:
            out.append(("kritik", yol, f"Python={a!r} Rust={b!r}"))
        elif anahtar in ("error", "code", "neden") and a != b:
            out.append(("orta", yol, f"Python={a!r} Rust={b!r}"))
        elif anahtar == "message" and a != b:
            out.append(("kozmetik", yol, "mesaj metni farkli"))
    return out


def sekil(v):
    if isinstance(v, dict):
        return {k: sekil(x) for k, x in v.items()}
    if isinstance(v, list):
        return {"__liste__": sekil(v[0]) if v else "bos"}
    return tip(v)


def dosya_sha(yol: Path) -> str:
    return hashlib.sha256(yol.read_bytes()).hexdigest()[:16]


class Calistirici:
    def __init__(self, port: dict[str, int], tokens: dict[str, str], fs_url: str, blob: bytes,
                 indirme_koku: dict[str, Path], kaynak: Path):
        self.istemci = {s: Istemci(s, port[s], tokens[s]) for s in ("py", "rs")}
        self.var: dict[str, dict] = {"py": {}, "rs": {}}
        self.fs = fs_url
        self.blob = blob
        self.kok = indirme_koku  # her tarafin indirme klasoru (disk dogrulamasi icin)
        self.kaynak = kaynak    # serve klasoru: beklenen icerik buradan okunur

    def yer_tutucu(self, s: str, side: str) -> str:
        s = s.replace("{fs_q}", urllib.parse.quote(self.fs, safe=""))
        s = s.replace("{fs}", self.fs).replace("{token}", self.istemci[side].token)
        for k, v in self.var[side].items():
            s = s.replace("{" + k + "}", str(v))
        return s

    def adim(self, adim: dict, side: str) -> dict:
        if "bekle" in adim:
            return self.bekle(adim["bekle"], side)
        if "bekle_hazir" in adim:
            return self.bekle_hazir(adim["bekle_hazir"], side)
        if "disk" in adim:
            return self.disk(adim["disk"], side)
        ist = self.istemci[side]
        yol = self.yer_tutucu(adim["yol"], side)
        baslik = {k: self.yer_tutucu(v, side) for k, v in (adim.get("baslik") or {}).items()}
        govde = None
        if adim.get("govde") is not None:
            govde = json.loads(self.yer_tutucu(json.dumps(adim["govde"], ensure_ascii=False), side))
        if adim.get("ham"):
            ham = self.blob
        elif "ham_metin" in adim:
            ham = adim["ham_metin"].encode("utf-8")  # bozuk gövde senaryosu (ham JSON metni)
        else:
            ham = None
        r = ist.istek(adim["yontem"], yol, adim.get("kimlik", "T"), baslik, govde, ham)
        ctype = (r["headers"].get("content-type") or "").split(";")[0].strip()
        sonuc = {"status": r["status"], "ctype": ctype,
                 "acao": "access-control-allow-origin" in r["headers"],
                 "ek_basliklar": sorted(k for k in r["headers"] if k in (
                     "content-disposition", "accept-ranges", "content-range",
                     "cache-control", "service-worker-allowed"))}
        if "hata" in r:
            sonuc["baglanti_hatasi"] = r["hata"]
        if ctype.startswith("application/json") or r["body"][:1] in (b"{", b"["):
            try:
                js = json.loads(r["body"].decode("utf-8") or "{}")
            except Exception:
                js = None
            if isinstance(js, dict) and adim.get("satir_gid"):
                gid = self.var[side].get(adim["satir_gid"])
                js = {**js, "items": [x for x in js.get("items", []) if x.get("gid") == gid][:1]}
            sonuc["json"] = js
            sonuc["sekil"] = sekil(js)
            if isinstance(js, dict):
                sonuc["hata"] = {k: js[k] for k in ("error", "code", "neden") if k in js}
        else:
            sonuc["sekil"] = "ikili" if r["body"] else "bos"
            sonuc["sha256"] = hashlib.sha256(r["body"]).hexdigest()[:16]
            sonuc["boyut"] = len(r["body"])
            if adim.get("beklenen"):  # tum govde kaynak dosyayla birebir ayni olmali
                kaynak_bayt = (self.kaynak / adim["beklenen"]).read_bytes()
                sonuc["beklenen_ok"] = r["body"] == kaynak_bayt
            if adim.get("beklenen_kesit"):  # Range cevabi: kaynagin ilk N bayti olmali
                kaynak_bayt = (self.kaynak / adim["beklenen_kesit"]).read_bytes()
                govde = r["body"]
                sonuc["beklenen_ok"] = bool(govde) and govde == kaynak_bayt[:len(govde)]
        for ad, alan in (adim.get("yakala") or {}).items():
            js = sonuc.get("json")
            if isinstance(js, dict) and alan in js:
                self.var[side][ad] = js[alan]
        return sonuc

    def bekle(self, bekle: dict, side: str) -> dict:
        """Indirme tamamlanana kadar /snapshot yokla. Basari yalniz 'complete' ile.

        Teshis icin: son yoklamada gorulen gid'ler ve durumlar kaydedilir
        (gid degerleri raporda kalir, token icermez)."""
        gid = self.var[side].get(bekle["gid"])
        son, t0, gorulen = "gid_yok", time.time(), []
        while time.time() - t0 < bekle.get("sn", 150):
            r = self.istemci[side].istek("GET", "/snapshot")
            try:
                items = json.loads(r["body"].decode("utf-8")).get("items", [])
            except Exception:
                items = []
            gorulen = [(x.get("gid"), x.get("status") or x.get("durum")) for x in items][:12]
            satir = next((x for x in items if x.get("gid") == gid), None)
            if satir is None:
                son = "satir_yok"
            else:
                son = satir.get("status") or satir.get("durum") or "durum_yok"
            if son in ("complete", "error", "removed"):
                break
            time.sleep(1)
        return {"bekle": True, "status": son, "sure_sn": round(time.time() - t0, 1),
                "gorulen": gorulen, "aranan_gid": gid}

    def bekle_hazir(self, bekle: dict, side: str) -> dict:
        """Torrent metadata'sı hazir olana kadar /torrent/dosyalar yokla (web-seed ile yerel)."""
        gid = self.var[side].get(bekle["gid"])
        t0, son = time.time(), None
        while time.time() - t0 < bekle.get("sn", 120):
            r = self.istemci[side].istek("GET", f"/torrent/dosyalar?gid={gid}")
            try:
                js = json.loads(r["body"].decode("utf-8"))
            except Exception:
                js = {}
            son = {"hazir_degil": js.get("hazir_degil"), "dosya_sayisi": len(js.get("dosyalar") or [])}
            if js.get("ok") and js.get("hazir_degil") is False and son["dosya_sayisi"] > 0:
                break
            time.sleep(2)
        return {"bekle_hazir": True, "durum": son, "sure_sn": round(time.time() - t0, 1)}

    def disk(self, disk: dict, side: str) -> dict:
        """Indirme klasorunde (gercek dosya sisteminde) adi/yolu eslesen dosyanin SHA-256'sini kaynakla karsilastirir.

        disk: {"ad": "a.bin" veya "paket/a.bin", "kaynak": "a.bin"}. Yol sonu eslesmesi kullanilir.
        """
        kok = self.kok[side]
        aranan = disk["ad"].replace("\\", "/")
        kaynak_sha = dosya_sha(self.kaynak / disk["kaynak"])
        t0 = time.time()
        while True:  # torrent indirmesi metadata sonrasi farkli gid'le yazilabilir: dosya gorunene dek bekle
            adaylar = []
            if kok.exists():
                for dosya in kok.rglob("*"):
                    if not dosya.is_file():
                        continue
                    rel = dosya.relative_to(kok).as_posix()
                    if rel == aranan or rel.endswith("/" + aranan):
                        adaylar.append((rel, dosya))
            eslesen = [rel for rel, d in adaylar if dosya_sha(d) == kaynak_sha]
            if eslesen or time.time() - t0 >= disk.get("sn", 0):
                break
            time.sleep(2)
        return {"disk": True, "aday_sayisi": len(adaylar), "bulundu": bool(adaylar),
                "sha_ok": bool(eslesen), "eslesen_yol": eslesen[:1],
                "sure_sn": round(time.time() - t0, 1)}


def bekle_ping(port: int, zaman_asimi: float = 90) -> bool:
    t0 = time.time()
    while time.time() - t0 < zaman_asimi:
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            c.request("GET", "/ping")
            if c.getresponse().status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def surec_oldur(procs: list[subprocess.Popen], kok: Path) -> None:
    for p in procs:
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, check=False)
    # Gecici klasore bagli kalan surecleri (aria2c vb.) kapat. Kullanicinin
    # surecleri bu klasorun yolunu komut satirinda tasimaz, dokunulmaz.
    ps = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{kok}*' }} "
          f"| ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, check=False)


def p_imza(kok: Path) -> dict:
    """P\\data'nin ad/boyut/zaman imzasi; test oncesi-sonrasi karsilastirilir."""
    imza = {}
    for dosya in glob.glob(str(kok / "data" / "**" / "*"), recursive=True):
        try:
            st = os.stat(dosya)
            if os.path.isfile(dosya):
                imza[os.path.relpath(dosya, kok)] = [st.st_size, int(st.st_mtime)]
        except OSError:
            pass
    return imza


def senaryolari_yukle() -> list[dict]:
    adimlar: list[dict] = []
    for yol in sorted(SENARYO_DIR.glob("*.json")):
        adimlar += json.loads(yol.read_text(encoding="utf-8"))
    return adimlar


def adim_farklari(py: dict, rs: dict) -> list[tuple[str, str, str]]:
    f: list[tuple[str, str, str]] = []
    if py.get("status") != rs.get("status"):
        f.append(("kritik", "durum_kodu", f"Python={py.get('status')} Rust={rs.get('status')}"))
    if py.get("ctype", "") != rs.get("ctype", ""):
        f.append(("orta", "content-type", f"Python={py.get('ctype')!r} Rust={rs.get('ctype')!r}"))
    if py.get("acao") != rs.get("acao"):
        f.append(("kritik", "access-control-allow-origin",
                  f"Python={py.get('acao')} Rust={rs.get('acao')}"))
    if py.get("ek_basliklar") != rs.get("ek_basliklar"):
        f.append(("orta", "ek basliklar", f"Python={py.get('ek_basliklar')} Rust={rs.get('ek_basliklar')}"))
    if "sha256" in py or "sha256" in rs:
        if py.get("sha256") != rs.get("sha256") or py.get("boyut") != rs.get("boyut"):
            f.append(("orta", "ikili govde", f"boyut Python={py.get('boyut')} Rust={rs.get('boyut')}, hash farkli"))
    elif py.get("json") is not None or rs.get("json") is not None:
        f += karsilastir(py.get("json"), rs.get("json"))
    return f


def main() -> int:
    if not PY_ROOT.exists() or not RS_EXE.exists():
        print("KURULUM HATASI: Python kaynagi ya da Rust exe yok:", PY_ROOT, RS_EXE)
        return 2
    kok = Path(tempfile.mkdtemp(prefix="afudm_t1_"))
    print("Gecici klasor:", kok)
    py_once = p_imza(PY_ROOT)

    serve = kok / "serve"
    fs_port = bos_port()
    fs_url = f"http://127.0.0.1:{fs_port}"
    hazirla_dosyalar(serve, fs_url, kok / "blob.pdf")
    procs: list[subprocess.Popen] = []
    fs_srv = dosya_sunucusu_baslat(serve, fs_port)
    kod = 2
    try:
        # --- Python (kaynaktan, headless benzeri; veri ve aria2 portu ayrik) ---
        wrap = kok / "py_sunucu.py"
        wrap.write_text(WRAPPER, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AFUDM_")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        py_veri = kok / "py_app"
        py_log_yol = kok / "py.log"
        py_log = open(py_log_yol, "w", encoding="utf-8")
        py_rpc = bos_port()
        py_p = subprocess.Popen(
            [sys.executable, str(wrap), str(PY_ROOT), str(bos_port()), str(py_rpc), str(py_veri)],
            env={**env, "AFUDM_DATA_ROOT": str(py_veri)}, stdout=py_log,
            stderr=subprocess.STDOUT, cwd=str(kok))
        procs.append(py_p)
        py_port = None
        for _ in range(900):
            for satir in py_log_yol.read_text(encoding="utf-8", errors="replace").splitlines():
                if satir.startswith("HAZIR "):
                    py_port = int(satir.split()[1])
            if py_port or py_p.poll() is not None:
                break
            time.sleep(0.2)
        if not py_port or not bekle_ping(py_port):
            print("HATA: Python AfuDM ayaga kalkmadi. Log:", py_log_yol)
            return 2

        # --- Rust (kopya exe; kendi veri ve motor klasoru) ---
        rs_app = kok / "rs_app"
        (rs_app / "engine").mkdir(parents=True)
        shutil.copy2(RS_EXE, rs_app / "AfuDM.exe")
        shutil.copy2(PY_ROOT / "engine" / "aria2c.exe", rs_app / "engine" / "aria2c.exe")
        rs_port = bos_port()
        rs_log = open(kok / "rs.log", "w", encoding="utf-8")
        procs.append(subprocess.Popen(
            [str(rs_app / "AfuDM.exe")], env={**env, "AFUDM_PORT": str(rs_port)},
            stdout=rs_log, stderr=subprocess.STDOUT, cwd=str(rs_app)))
        if not bekle_ping(rs_port, 120):
            print("HATA: Rust AfuDM ayaga kalkmadi. Log:", kok / "rs.log")
            return 2

        tokens = {}
        for side, veri in (("py", py_veri / "data"), ("rs", rs_app / "data")):
            tf = veri / "api_token.txt"
            for _ in range(100):
                if tf.exists() and tf.read_text(encoding="utf-8").strip():
                    break
                time.sleep(0.2)
            tokens[side] = tf.read_text(encoding="utf-8").strip()

        calistirici = Calistirici({"py": py_port, "rs": rs_port}, tokens, fs_url, BLOB_BYTES,
                                  {"py": py_veri / "downloads", "rs": rs_app / "downloads"}, serve)
        adimlar = senaryolari_yukle()
        sonuclar = []
        for adim in adimlar:
            kayit = {"id": adim.get("id", ""), "grup": adim.get("grup", ""),
                     "ad": adim.get("ad", adim.get("yol", "")), "not": adim.get("not", "")}
            for side in ("py", "rs"):
                try:
                    kayit[side] = calistirici.adim(adim, side)
                except Exception as exc:
                    kayit[side] = {"status": -1, "hata": f"istemci hatasi: {exc}"}
            kayit["farklar"] = []
            if "bekle" in adim:
                for side in ("py", "rs"):
                    if kayit[side].get("status") != "complete":
                        kayit["farklar"].append(("kritik", f"indirme_tamamlanmadi[{side}]",
                                                 f"durum={kayit[side].get('status')} "
                                                 f"aranan={kayit[side].get('aranan_gid')} "
                                                 f"gorulen={kayit[side].get('gorulen')}"))
                if kayit["py"].get("status") != kayit["rs"].get("status"):
                    kayit["farklar"].append(("kritik", "indirme_sonu",
                                             f"Python={kayit['py'].get('status')} "
                                             f"Rust={kayit['rs'].get('status')}"))
            elif "bekle_hazir" in adim or "disk" in adim:
                for side in ("py", "rs"):
                    res = kayit[side]
                    if "disk" in adim:
                        if not res.get("sha_ok"):
                            kayit["farklar"].append(("kritik", f"dosya_icerigi[{side}]",
                                                     f"bulundu={res.get('bulundu')} "
                                                     f"aday={res.get('aday_sayisi')} sha_eslesmedi"))
                    elif (res.get("durum") or {}).get("hazir_degil") is not False:
                        kayit["farklar"].append(("kritik", f"metadata_hazir[{side}]",
                                                 f"durum={res.get('durum')}"))
                if "disk" in adim and kayit["py"].get("sha_ok") != kayit["rs"].get("sha_ok"):
                    kayit["farklar"].append(("kritik", "dosya_icerigi_esitlik", "taraflar farkli"))
            else:
                kayit["farklar"] = adim_farklari(kayit["py"], kayit["rs"])
                for side in ("py", "rs"):
                    if kayit[side].get("beklenen_ok") is False:
                        kayit["farklar"].append(("kritik", f"govde_kaynakla_uyusmuyor[{side}]",
                                                 "indirilen/servis edilen icerik kaynak dosyayla ayni degil"))
            sonuclar.append(kayit)
            print(f"[{kayit['id']}] {kayit['ad']}: py={kayit['py'].get('status')} "
                  f"rs={kayit['rs'].get('status')} fark={len(kayit['farklar'])}", flush=True)

        RAPOR_DIR.mkdir(parents=True, exist_ok=True)
        rapor_yol = RAPOR_DIR / "sonuc_son.json"
        rapor_yol.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1, default=str),
                             encoding="utf-8")
        kritik = sum(1 for k in sonuclar for f in k["farklar"] if f[0] == "kritik")
        orta = sum(1 for k in sonuclar for f in k["farklar"] if f[0] == "orta")
        koz = sum(1 for k in sonuclar for f in k["farklar"] if f[0] == "kozmetik")
        print(f"OZET: adim={len(sonuclar)} kritik={kritik} orta={orta} kozmetik={koz}")
        print("Rapor:", rapor_yol)
        kod = 1 if kritik else 0
    finally:
        fs_srv.shutdown()
        surec_oldur(procs, kok)
        for ad in ("py.log", "rs.log"):
            yol = kok / ad
            if yol.exists() and kod == 2:
                print(f"--- {ad} (son 15 satir) ---")
                print("\n".join(yol.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]))
        shutil.rmtree(kok, ignore_errors=True)
        print("P\\data degismedi:", p_imza(PY_ROOT) == py_once if py_once else "n/a")
    return kod


if __name__ == "__main__":
    sys.exit(main())
