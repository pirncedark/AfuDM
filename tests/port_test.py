"""Uzanti PORT KESFI canli testi — AfuDM 6811'de DEGILKEN de bulunmali.

Cozulen gercek kusur: `api_port` veritabaninda saklaniyordu. 6811 bir kez dolu
oldugunda (onceki calismanin TIME_WAIT artigi, ikinci kopya) uygulama 6812'ye
dusuyor ve bu deger KALICI oluyordu; uzanti ise hep 6811'i deniyordu, bu yuzden
uygulama ACIKKEN "AfuDM kapali" diyordu ve hicbir indirme devralinmiyordu.

Burada durum birebir kuruluyor: 6811 baska bir soketle dolduruluyor, AfuDM'in
API'si 6812'ye dusuyor, uzantiya 6811 yaziliyor ve acilir pencerenin yine de
"calisiyor · 6812" demesi bekleniyor.

ONKOSUL: AfuDM KAPALI olmali (API portlarini bu test acar). AG GEREKTIRMEZ.
"""
from __future__ import annotations

import json
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from api.server import LocalAPI  # noqa: E402

EXT = ROOT / "extension"
ENDPOINT_FILE = ROOT / "data" / "api_endpoint.json"
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  [{'GECTI' if passed else 'BASARISIZ'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)


def popup_durumu(ext_dir: Path, port: int, token: str) -> str:
    """Uzantiyi yukle, kayitli portu <port> yap, acilir pencerenin durumunu don."""
    with sync_playwright() as play:
        ctx = play.chromium.launch_persistent_context(
            tempfile.mkdtemp(prefix="afudm-port-"),
            headless=False,
            args=[f"--disable-extensions-except={ext_dir}",
                  f"--load-extension={ext_dir}", "--no-first-run"],
        )
        try:
            worker = ctx.service_workers[0] if ctx.service_workers else \
                ctx.wait_for_event("serviceworker", timeout=20000)
            ext_id = worker.url.split("/")[2]
            page = ctx.new_page()
            page.goto(f"chrome-extension://{ext_id}/popup.html")
            page.wait_for_timeout(1200)
            page.evaluate("c => chrome.storage.local.set(c)", {"port": port, "token": token})
            page.reload()
            # Kayitli port cevap vermeyince uzanti araligi tarar: birkac saniye ver
            for _ in range(20):
                page.wait_for_timeout(500)
                durum = page.inner_text("#state")
                if "127.0.0.1" in durum:
                    return durum
            return page.inner_text("#state")
        finally:
            ctx.close()


def main() -> int:
    print("AfuDM uzanti port kesfi testi\n")
    yedek = ENDPOINT_FILE.read_text(encoding="utf-8") if ENDPOINT_FILE.exists() else None

    # 6811'i doldur: AfuDM'in API'si bir sonraki porta dusecek
    dolu = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        dolu.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        dolu.bind(("127.0.0.1", 6811))
        dolu.listen(1)
    except OSError as exc:
        print(f"ATLANDI: 6811 doldurulamadi ({exc}). AfuDM acik olabilir.")
        return 0

    api = LocalAPI(manager=None, port=6811)
    try:
        port = api.start()
        record("AfuDM 6811 doluyken bir sonraki porta dustu", port != 6811, f"port {port}")

        durum = popup_durumu(EXT, 6811, api.token)
        record("uzanti 6811 cevap vermeyince dogru portu buldu",
               f"127.0.0.1:{port}" in durum, durum)

        # Kullanici ARALIK DISI bir port yazdiysa secimi ezilmemeli
        disarisi = popup_durumu(EXT, 6998, api.token)
        record("aralik disi port taranmaz (kullanici secimi korunur)",
               "127.0.0.1" not in disarisi, disarisi)
    finally:
        api.stop()
        dolu.close()
        if yedek is not None:
            ENDPOINT_FILE.write_text(yedek, encoding="utf-8")

    print("\n" + "=" * 52)
    gecen = sum(1 for _, ok, _ in results if ok)
    print(f"SONUC: {gecen}/{len(results)} test gecti")
    return 0 if gecen == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
