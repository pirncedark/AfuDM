"""Tarayici uzantisi CANLI testi — uzanti gercek Chromium'a yuklenir.

ONKOSUL: AfuDM ACIK olmali (6811'de API). Ag GEREKTIRMEZ: indirilecek
dosyalar 127.0.0.1 uzerindeki gecici bir sunucudan gelir.

Sinananlar (hepsi uzantinin KENDI koduyla):
  - service worker ayaga kalkiyor, acilir pencere durumu dogru yaziyor
  - "Otomatik baglan" eslestirme KAPALIYKEN reddediliyor, ACIKKEN anahtari aliyor
  - tarayici indirmesi AfuDM'e devrediliyor, tarayicidaki kopya siliniyor
  - atlanacak uzantilar (.txt) devralinmiyor
  - AfuDM kapaliyken indirmeye DOKUNULMUYOR (tarayici kendisi indiriyor)
  - sayfadaki .mp4 istegi yakalaniyor

Eslestirme icin calisan uygulamanin penceresine dokunulmaz: ayni token
dosyasini kullanan IKINCI bir API (6899) acilip eslestirme penceresi acilir.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from api.server import LocalAPI  # noqa: E402

EXT = ROOT / "extension"
ENDPOINT_FILE = ROOT / "data" / "api_endpoint.json"
APP_PORT = 6811
PAIR_PORT = 6899
DEAD_PORT = 6998  # hicbir sey dinlemiyor = "AfuDM kapali"
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  [{'GECTI' if passed else 'BASARISIZ'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)


def api(path: str, token: str = "", body: dict | None = None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{APP_PORT}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "X-AfuDM-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")
    except OSError:
        return 0, {}


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


class _QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # uzanti indirmeyi yarida iptal ediyor: kopan baglanti BEKLENEN


def serve_files(folder: Path) -> tuple[ThreadingHTTPServer, int]:
    httpd = _QuietServer(("127.0.0.1", 0), partial(_Quiet, directory=str(folder)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def wait_for(fn, timeout: float = 15.0, step: float = 0.3):
    end = time.time() + timeout
    value = fn()
    while not value and time.time() < end:
        time.sleep(step)
        value = fn()
    return value


def main() -> int:
    print("AfuDM tarayici uzantisi canli testi\n")
    status, _ = api("/ping")
    if status != 200:
        print(f"AfuDM {APP_PORT} portunda calismiyor — once uygulamayi ac.")
        return 2
    endpoint_backup = ENDPOINT_FILE.read_text("utf-8")
    token = json.loads(endpoint_backup)["token"]

    work = Path(tempfile.mkdtemp(prefix="afudm_ext_"))
    site_dir = work / "site"
    site_dir.mkdir()
    (site_dir / "devral.zip").write_bytes(os.urandom(3 * 1048576))
    (site_dir / "kapali.zip").write_bytes(os.urandom(3 * 1048576))
    (site_dir / "not.txt").write_bytes(b"x" * 3 * 1048576)
    (site_dir / "klip.mp4").write_bytes(os.urandom(64 * 1024))
    (site_dir / "index.html").write_text(
        '<a id="devral" href="devral.zip">z</a> <a id="kapali" href="kapali.zip">k</a>'
        ' <a id="txt" href="not.txt" download>t</a>', "utf-8")
    site, site_port = serve_files(site_dir)
    base = f"http://127.0.0.1:{site_port}"

    # /add'e hic gelinmez; eslestirme icin yonetici gerekmiyor.
    pair_api = LocalAPI(manager=None, port=PAIR_PORT)
    pair_port = pair_api.start()
    # start() api_endpoint.json'u bu porta gore yeniden yazar — asil kaydi geri koy.
    ENDPOINT_FILE.write_text(endpoint_backup, encoding="utf-8")

    added_gids: list[str] = []
    _, before = api("/snapshot", token)
    gids_before = {i["gid"] for i in before.get("items", [])}

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(work / "profil"),
                headless=False,
                accept_downloads=True,
                args=[f"--disable-extensions-except={EXT}",
                      f"--load-extension={EXT}", "--lang=tr"],
            )
            sw = ctx.service_workers[0] if ctx.service_workers else \
                ctx.wait_for_event("serviceworker", timeout=15000)
            ext_id = sw.url.split("/")[2]
            record("Service worker ayaga kalkti", bool(ext_id), ext_id)

            def set_cfg(**cfg) -> None:
                sw.evaluate("cfg => chrome.storage.local.set(cfg)", cfg)

            def stored_token() -> str:
                return sw.evaluate("chrome.storage.local.get('token')").get("token", "")

            def browser_downloads(suffix: str, state: str | None = None) -> list:
                items = sw.evaluate("new Promise(r => chrome.downloads.search({}, r))")
                return [d for d in items if d["url"].endswith(suffix)
                        and (state is None or d["state"] == state)]

            # --- acilir pencere + eslestirme ---------------------------------
            errors: list[str] = []
            popup = ctx.new_page()
            popup.on("pageerror", lambda e: errors.append(str(e)))
            popup.goto(f"chrome-extension://{ext_id}/popup.html")
            state = wait_for(lambda: "çalışıyor" in popup.inner_text("#state")
                             and popup.inner_text("#state"))
            record("Acilir pencere AfuDM'i calisiyor goruyor", bool(state), state or "")
            popup.click("details summary")  # ayarlar katli gelir, kullanici gibi ac
            pair_label = popup.inner_text("#pair").strip()
            record("Acilir pencere Turkce", pair_label == "Otomatik bağlan", pair_label)

            popup.fill("#port", str(pair_port))
            popup.click("#pair")
            note = wait_for(lambda: "Eşleştirme kapalı" in popup.inner_text("#note")
                            and popup.inner_text("#note"))
            record("Eslestirme KAPALIYKEN anahtar alinamadi",
                   bool(note) and not stored_token(), (note or "")[:60])

            pair_api.open_pairing(30)
            popup.click("#pair")
            got = wait_for(stored_token)
            paired_note = wait_for(lambda: "Bağlandı" in popup.inner_text("#note")
                                   and popup.inner_text("#note"))
            record("Eslestirme ACIKKEN anahtar alindi", got == token and bool(paired_note),
                   (paired_note or popup.inner_text("#note"))[:60])

            # --- devralma: AfuDM acik ---------------------------------------
            set_cfg(port=APP_PORT, token=token, enabled=True, minSizeMB=1)
            page = ctx.new_page()
            page.goto(base + "/index.html")
            page.click("#devral")

            def new_item():
                _, snap = api("/snapshot", token)
                return next((i for i in snap.get("items", [])
                             if i["gid"] not in gids_before
                             and i.get("source", "").endswith("/devral.zip")), None)

            item = wait_for(new_item, timeout=20)
            if item:
                added_gids.append(item["gid"])
            record("Tarayici indirmesi AfuDM'e devredildi", bool(item),
                   f"{item['title']} · {item['status']}" if item else "")
            done = wait_for(lambda: (new_item() or {}).get("status") == "complete",
                            timeout=30)
            final = new_item() or {}
            record("AfuDM dosyayi tamamladi", bool(done),
                   f"{final.get('completedLength', 0) // 1024} KB")
            left = wait_for(lambda: not browser_downloads("/devral.zip"), timeout=5)
            record("Tarayicidaki kopya iptal edilip silindi", bool(left))

            # --- atlanan uzanti ----------------------------------------------
            page.click("#txt")
            txt = wait_for(lambda: browser_downloads("/not.txt", "complete"), timeout=20)
            _, snap = api("/snapshot", token)
            in_afudm = any(i.get("source", "").endswith("/not.txt") for i in snap["items"])
            record(".txt devralinmadi, tarayici indirdi", bool(txt) and not in_afudm)

            # --- AfuDM kapali ------------------------------------------------
            set_cfg(port=DEAD_PORT)
            page.click("#kapali")
            kept = wait_for(lambda: browser_downloads("/kapali.zip", "complete"), timeout=20)
            record("AfuDM kapaliyken tarayici indirmesine dokunulmadi", bool(kept),
                   f"{kept[0]['fileSize'] // 1048576} MB tarayicida" if kept else "")
            set_cfg(port=APP_PORT)

            # --- sayfadaki medya ---------------------------------------------
            page.evaluate("fetch('/klip.mp4').then(r => r.arrayBuffer())")
            media = wait_for(lambda: sw.evaluate(
                "[...mediaByTab.values()].flat().map(m => m.url)"), timeout=5)
            record("Sayfadaki .mp4 istegi yakalandi",
                   any(u.endswith("/klip.mp4") for u in media or []),
                   f"{len(media or [])} medya")

            record("Acilir pencerede JS hatasi yok", not errors, "; ".join(errors)[:80])
            ctx.close()
    finally:
        for gid in added_gids:
            api("/control", token, {"action": "remove", "gid": gid, "delete_files": True})
        pair_api.stop()
        site.shutdown()
        ENDPOINT_FILE.write_text(endpoint_backup, encoding="utf-8")
        shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'=' * 52}\nSONUC: {passed}/{len(results)} test gecti")
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print("Gecmeyenler: " + ", ".join(failed))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
