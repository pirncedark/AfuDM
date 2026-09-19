"""Yerel API duman testi — tarayici uzantisinin kullandigi yolun aynisi.

Token dogrulamasi, eslestirme penceresi, link ekleme, durum okuma ve
duraklat/kaldir komutlari gercek HTTP istekleriyle sinanir.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.server import LocalAPI  # noqa: E402
from core.manager import Manager  # noqa: E402

TEST_URL = "https://download.thinkbroadband.com/100MB.zip"
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  [{'GECTI' if passed else 'BASARISIZ'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)


def request(port: int, path: str, token: str | None = None, body: dict | None = None):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-AfuDM-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def main() -> int:
    print("AfuDM yerel API testi\n")
    # LocalAPI.start() api_endpoint.json'u EZER; AfuDM aciksa uzanti yanlis
    # porta gider. Yedekle, sonda geri yaz.
    endpoint = Path(__file__).resolve().parent.parent / "data" / "api_endpoint.json"
    endpoint_backup = endpoint.read_text("utf-8") if endpoint.exists() else None
    manager = Manager()
    manager.start()
    api = LocalAPI(manager, port=6811)
    port = api.start()
    try:
        status, body = request(port, "/ping")
        record("/ping token istemiyor", status == 200 and body.get("ok"), f"port {port}")

        status, _ = request(port, "/snapshot", token="yanlis-token")
        record("Yanlis token reddedildi", status == 401)

        status, _ = request(port, "/snapshot")
        record("Tokensiz istek reddedildi", status == 401)

        status, body = request(port, "/pair")
        record("Eslestirme kapaliyken anahtar verilmiyor", status == 403)

        api.open_pairing(30)
        status, body = request(port, "/pair")
        record("Eslestirme acikken anahtar veriliyor",
               status == 200 and body.get("token") == api.token)

        status, body = request(port, "/add", token=api.token, body={"url": TEST_URL})
        gid = body.get("gid", "")
        record("Uzantidan link eklendi", status == 200 and bool(gid), f"gid {gid}")

        time.sleep(6)
        status, body = request(port, "/snapshot", token=api.token)
        item = next((i for i in body.get("items", []) if i["gid"] == gid), None)
        record("Durum okunuyor ve veri akiyor",
               bool(item) and item["completedLength"] > 0,
               f"{item['completedLength'] // 1024} KB, {item['connections']} baglanti"
               if item else "kayit yok")

        status, _ = request(port, "/control", token=api.token,
                            body={"action": "pause", "gid": gid})
        time.sleep(2)
        _, body = request(port, "/snapshot", token=api.token)
        item = next((i for i in body.get("items", []) if i["gid"] == gid), None)
        record("Duraklat komutu isledi",
               status == 200 and bool(item) and item["status"] == "paused",
               item["status"] if item else "")

        status, _ = request(port, "/control", token=api.token,
                            body={"action": "remove", "gid": gid, "delete_files": True})
        record("Kaldir komutu isledi", status == 200)

        status, body = request(port, "/add", token=api.token, body={"url": ""})
        record("Bos link anlasilir hata veriyor",
               status == 400 and "bos" in (body.get("error", "").lower()),
               body.get("error", "")[:50])

        # Browser -> LinkGrabber handoff: uzanti ham metni panele devreder.
        # Hook yokken istek reddedilir; hook ayarlaninca metin iletilir.
        from api.server import _Handler
        status, body = request(port, "/linkgrabber", token=api.token,
                               body={"metin": "https://ornek.com/a.zip"})
        record("LinkGrabber hook yokken reddedilir",
               status == 503 and body.get("code") == "UI_YOK", body.get("code", ""))

        _Handler.on_linkgrabber = lambda metin, dosya: _Handler._son_handoff.append((metin, dosya))
        _Handler._son_handoff = []
        status, body = request(port, "/linkgrabber", token=api.token,
                               body={"metin": "https://ornek.com/a.zip\nhttps://ornek.com/b.zip",
                                     "dosya": True})
        record("LinkGrabber handoff metni iletiyor",
               status == 200 and body.get("ok")
               and _Handler._son_handoff[0][0].count("\n") == 1
               and _Handler._son_handoff[0][1] is True,
               f"adet {len(_Handler._son_handoff[0][0].splitlines()) if _Handler._son_handoff else 0}")

        status, body = request(port, "/linkgrabber", token=api.token, body={"metin": "  "})
        record("Bos LinkGrabber metni reddedilir",
               status == 400 and "metin" in (body.get("error", "").lower()),
               body.get("error", "")[:50])
        _Handler.on_linkgrabber = None
    finally:
        api.stop()
        manager.stop()
        if endpoint_backup is not None:
            endpoint.write_text(endpoint_backup, encoding="utf-8")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'=' * 52}\nSONUC: {passed}/{len(results)} test gecti")
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print("Gecmeyenler: " + ", ".join(failed))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
