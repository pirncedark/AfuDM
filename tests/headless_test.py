# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import paths
DB_PATH = Path(tempfile.gettempdir()) / f"headless_test_{int(time.time())}.sqlite"
paths.DB_PATH = DB_PATH

from api.web import ANAHTAR_BASLIK, CSRF_BASLIK
from core.manager import Manager
from core.servis import AfuDMServis
from core.erisim import ROL_YONETICI, ROL_SALT_OKUR

total_checks = 0
passed_checks = 0
failed_checks = 0
fails: list[str] = []

def check(name: str, condition: bool, detail: str = "") -> None:
    global total_checks, passed_checks, failed_checks
    total_checks += 1
    if condition:
        passed_checks += 1
        print(f" [OK] {name}")
    else:
        failed_checks += 1
        msg = f" [FAIL] {name}"
        if detail:
            msg += f" ({detail})"
        print(msg)
        fails.append(msg)

def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def request(url: str, method: str = "GET", headers=None, data=None):
    if headers is None: headers = {}
    req = urllib.request.Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read().decode("utf-8") or "{}"), res.headers
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}"), exc.headers
    except Exception as exc:
        return 0, str(exc), {}

def test_headless():
    manager = Manager()
    servis = AfuDMServis(manager, kip="test")

    check("Sunucu varsayilan olarak kapali (sunucu_acik=False)", 
          not servis.store.get("sunucu_acik"))

    port = find_free_port()
    servis.store.set("sunucu_port", port)
    servis.store.set("sunucu_izinli_originler", "http://test-origin.local")
    
    # Kilit saniyesi max(5, ...) kurali oldugu icin 5 yapiyoruz. 
    # Fakat testte 5 sn beklememek icin limitciyi manuel modifiye edebiliriz
    # ya da sadece 5.1 sn bekleriz.
    servis.limitci.ayarla(limit=50, hatali_limit=3, kilit_saniye=5)
    
    res = servis.sunucu_baslat()
    check("Sunucu acilabilir", res.get("ok", False) and res.get("calisiyor", False))
    
    url = f"http://127.0.0.1:{port}"
    api_endpoint = f"{url}/api/yetenekler"

    st, bd, hd = request(api_endpoint)
    check("Anahtarsiz istek REDDEDILIR (401)", st == 401 and bd.get("code") == "ANAHTAR_GEREKLI", str(bd))
    
    res = servis.anahtar_olustur("Test Yonetici", ROL_YONETICI)
    anahtar = res["gizli"]
    
    st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar})
    check("Gecerli anahtarla GECER", st == 200 and bd.get("ok", False), str(bd))

    st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar, "Origin": "http://kotu-origin.com"})
    check("Izinli olmayan Origin REDDEDILIR (403)", st == 403 and bd.get("code") == "ORIGIN_REDDEDILDI", str(bd))
    
    st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar, "Origin": "http://test-origin.local"})
    check("Izinli Origin GECER", st == 200, str(bd))

    # Yanlis denemeler - 3 defa
    for i in range(3):
        st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: "yanlis_123"})
        check(f"Yanlis anahtar deneme {i+1} -> 401", st == 401)
    
    st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar})
    check("Hatali limit asildiktan sonra dogru anahtar bile 429 REDDEDILIR", st == 429 and bd.get("code") == "COK_FAZLA_ISTEK", str(bd))
    
    time.sleep(5.1) # 5 saniye kilit bekle
    st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar})
    check("Kilit suresi gecince IP tekrar kabul edilir", st == 200)
    
    servis.limitci.ayarla(limit=5)
    
    gecti = 0
    for i in range(10):
        st, bd, hd = request(api_endpoint, headers={ANAHTAR_BASLIK: anahtar})
        if st == 200:
            gecti += 1
    check("Istek limiti (5) uygulandi, fazlasi reddedildi", gecti <= 5, f"{gecti} gecti")

    # Limiti tekrar yukselt, kilitleri ac
    servis.limitci.ayarla(limit=50)
    servis.limitci._istekler.clear()
    servis.limitci._kilitler.clear()

    res_okur = servis.anahtar_olustur("Test Okur", ROL_SALT_OKUR)
    anahtar_okur = res_okur["gizli"]

    st, bd, hd = request(f"{url}/api/ayarlar", headers={ANAHTAR_BASLIK: anahtar_okur})
    check("Salt okur ayar OKUYABILIR", st == 200)

    st, bd, hd = request(f"{url}/api/ayarlar", method="POST", headers={ANAHTAR_BASLIK: anahtar_okur, CSRF_BASLIK: "1"}, data={"settings": {}})
    check("Salt okur ayar YAZAMAZ (403)", st == 403 and bd.get("code") == "YETKI_YOK", str(bd))
    
    st, bd, hd = request(f"{url}/api/ayarlar", method="POST", headers={ANAHTAR_BASLIK: anahtar}, data={"settings": {}})
    check("POST istegi CSRF basligi olmadan REDDEDILIR", st == 403 and bd.get("code") == "CSRF_BASLIGI_YOK", str(bd))

    st, bd, hd = request(f"{url}/api/ayarlar", method="POST", headers={ANAHTAR_BASLIK: anahtar, CSRF_BASLIK: "1"}, data={"settings": {}})
    check("POST istegi CSRF basligi ile GECER", st == 200)

    res_revoke = servis.anahtar_iptal(res_okur["id"])
    check("Anahtar iptal edildi", res_revoke.get("ok", False))
    st, bd, hd = request(f"{url}/api/ayarlar", headers={ANAHTAR_BASLIK: anahtar_okur})
    check("Iptal edilen anahtar 401 doner", st == 401 and bd.get("code") == "GECERSIZ_ANAHTAR", str(bd))
    
    servis.sunucu_durdur()
    time.sleep(0.5)
    
    port_yerel = find_free_port()
    servis.store.set("sunucu_port", port_yerel)
    servis.store.set("sunucu_adres", "yerel")
    res = servis.sunucu_baslat()
    
    sunucu_url = res.get("url", "")
    check("yerel mod url 127.0.0.1 icerir", "127.0.0.1" in sunucu_url)
    check("yerel mod lan_url bostur", not res.get("lan_url"))
    servis.sunucu_durdur()
    
    port_lan = find_free_port()
    servis.store.set("sunucu_port", port_lan)
    servis.store.set("sunucu_adres", "lan")
    res = servis.sunucu_baslat()
    check("lan mod lan_url doludur", bool(res.get("lan_url")))
    
    servis.sunucu_durdur()

def main():
    global failed_checks
    print("Headless Server Testleri Basliyor...")
    try:
        test_headless()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        failed_checks += 1
    finally:
        try:
            DB_PATH.unlink(missing_ok=True)
        except:
            pass

    print(f"\nSONUC: {passed_checks} gecti, {failed_checks} basarisiz")
    if fails:
        for f in fails:
            print(f)
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
