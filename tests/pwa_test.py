# -*- coding: utf-8 -*-
"""v1.7.5 PWA uc noktalari — GERCEK sunucuya karsi duman testi."""
import json, sys, urllib.request
sys.path.insert(0, ".")
from api.server import LocalAPI

class SahteStore(dict):
    def get(self, k, d=None): return dict.get(self, k, d)
    def set(self, k, v): self[k] = v

class SahteManager:
    store = SahteStore()
    def current_download_dir(self): return "."

api = LocalAPI(SahteManager(), port=6899, lan=False)
port = api.start()
kok = f"http://127.0.0.1:{port}"
gecti = dusen = 0

def kontrol(ad, kosul, detay=""):
    global gecti, dusen
    if kosul: gecti += 1; print(f"  [GECTI] {ad}")
    else: dusen += 1; print(f"  [DUSTU] {ad} -> {detay}")

def al(yol):
    with urllib.request.urlopen(kok + yol, timeout=5) as y:
        return y.status, dict(y.headers), y.read()

try:
    for yol, tur in (("/manifest.webmanifest", "application/manifest+json"),
                     ("/sw.js", "text/javascript"),
                     ("/ikon.png", "image/png"),
                     ("/m", "text/html")):
        try:
            kod, bas, govde = al(yol)
        except Exception as exc:
            kontrol(f"GET {yol} 200 donuyor", False, repr(exc)); continue
        kontrol(f"GET {yol} 200 donuyor (anahtarsiz)", kod == 200, str(kod))
        kontrol(f"GET {yol} Content-Type {tur}", tur in bas.get("Content-Type", ""),
                bas.get("Content-Type", ""))
        kontrol(f"GET {yol} govdesi bos degil", len(govde) > 0, str(len(govde)))

    _, bas, _ = al("/sw.js")
    kontrol("sw.js 'Service-Worker-Allowed: /' basligi var",
            bas.get("Service-Worker-Allowed") == "/", str(bas.get("Service-Worker-Allowed")))
    kontrol("sw.js Cache-Control no-cache", "no-cache" in bas.get("Cache-Control", ""),
            bas.get("Cache-Control", ""))

    _, bas, govde = al("/manifest.webmanifest")
    m = json.loads(govde.decode("utf-8"))
    kontrol("manifest start_url /m", m.get("start_url") == "/m", str(m.get("start_url")))
    kontrol("manifest scope /", m.get("scope") == "/", str(m.get("scope")))
    kontrol("manifest display standalone", m.get("display") == "standalone", str(m.get("display")))
    kontrol("manifest 192 ve 512 ikon", {i["sizes"] for i in m.get("icons", [])} >= {"192x192", "512x512"})
    kontrol("manifest ikonlari /ikon.png gosteriyor",
            all(i["src"] == "/ikon.png" for i in m.get("icons", [])))

    # API hala korumali mi? PWA yollari anahtarsiz diye kapi acilmasin.
    for yol in ("/snapshot", "/klasorler"):
        try:
            kod, _, _ = al(yol); kontrol(f"{yol} anahtarsiz REDDEDILIYOR", False, f"HTTP {kod}")
        except urllib.error.HTTPError as exc:
            kontrol(f"{yol} anahtarsiz REDDEDILIYOR", exc.code == 401, f"HTTP {exc.code}")

    # Anahtar sizintisi: kabuk dosyalarinin hicbiri token icermesin
    for yol in ("/m", "/sw.js", "/manifest.webmanifest"):
        _, _, govde = al(yol)
        kontrol(f"{yol} icinde API anahtari GECMIYOR",
                api.token.encode() not in govde)
finally:
    api.stop()

print(f"\nSONUC: {gecti} gecti, {dusen} basarisiz")
sys.exit(1 if dusen else 0)
