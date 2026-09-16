"""Video paneli CANLI testi — uzanti gercek Chromium'da, indirme gercek AfuDM'de.

ONKOSUL: AfuDM ACIK, sistemde ffmpeg + ffprobe (test videolarini uretmek icin).
AG GEREKTIRMEZ ve telifli icerik KULLANMAZ: videolar ffmpeg'in test deseninden
uretilir, iki yerel sunucudan servis edilir.

Kurgu (gercek sitelerdeki gomulu oynatici gibi):
  - Film sayfasi (sunucu A) oynaticiyi BASKA kaynaktan (sunucu B) iframe ile gomer.
  - Oynatici HLS ana listesini fetch ile yukler (hls.js gibi); sunucu B, HLS
    isteklerini Referer oynatici degilse 403 ile REDDEDER (hotlink korumasi).

Sinananlar:
  - video oynayinca iframe'in icinde "AfuDM ile indir" dugmesi cikiyor
  - HLS ana listesinden 720p ve 360p secenekleri + sadece ses listeleniyor
  - 360p secilince AfuDM indiriyor: Referer gidiyor, dosya adi sekme basligi,
    cikti GERCEKTEN 360 piksel yuksekliginde
  - duz dosya (webm) videosunda "Dosya" secenegi http indirmesi olarak tamamlaniyor
  - adresi olmayan video (canvas akisi): yt-dlp yedegi denenir, "bulunamadi" denir
  - service worker yeniden baslasa bile yakalanan medya kaybolmuyor
"""
from __future__ import annotations

import json
import shutil
import subprocess
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

EXT = ROOT / "extension"
APP_PORT = 6811
BASLIK = "Deneme Filmi 2026"
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


def wait_for(fn, timeout: float = 15.0, step: float = 0.4):
    end = time.time() + timeout
    value = fn()
    while not value and time.time() < end:
        time.sleep(step)
        value = fn()
    return value


def uret_videolar(klasor: Path) -> None:
    def ff(*args):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       cwd=klasor, check=True)
    ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-t", "4",
       "-c:v", "libvpx", "-b:v", "400k", "klip.webm")
    (klasor / "hls").mkdir()
    ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25", "-f", "lavfi", "-i", "sine=frequency=440",
       "-t", "6", "-filter_complex", "[0:v]split=2[a][b];[b]scale=640:360[b2]",
       "-map", "[a]", "-map", "[b2]", "-map", "1:a", "-map", "1:a",
       "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
       "-b:v:0", "1500k", "-b:v:1", "500k",
       "-f", "hls", "-hls_time", "2", "-hls_playlist_type", "vod",
       "-master_pl_name", "master.m3u8", "-var_stream_map", "v:0,a:0 v:1,a:1",
       "-hls_segment_filename", "hls/v%v/seg%d.ts", "hls/v%v/index.m3u8")


class _Sessiz(SimpleHTTPRequestHandler):
    oynatici_kaynagi = ""                 # "http://127.0.0.1:<B>"
    # (yol, Referer, durum) — .ts PARCALARI: sayfa yalniz ana listeyi ceker,
    # parcalari isteyen her zaman AfuDM (yt-dlp). (yt-dlp de Sec-Fetch-Mode yollar,
    # tarayiciyi o baslikla ayirmak YANILTIR.)
    hls_istekleri: list[tuple[str, str, int]] = []

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        if self.path.endswith(".m3u8"):
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def guess_type(self, path):
        if str(path).endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        return super().guess_type(path)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/hls/"):
            referer = self.headers.get("Referer") or ""
            izinli = referer.startswith(_Sessiz.oynatici_kaynagi + "/")
            if self.path.endswith(".ts"):
                _Sessiz.hls_istekleri.append((self.path, referer, 200 if izinli else 403))
            if not izinli:
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        return super().do_GET()


class _SessizSunucu(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


def sun(klasor: Path) -> tuple[ThreadingHTTPServer, int]:
    sunucu = _SessizSunucu(("127.0.0.1", 0), partial(_Sessiz, directory=str(klasor)))
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    return sunucu, sunucu.server_address[1]


def yukseklik(dosya: Path) -> int:
    cikti = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height",
         "-of", "csv=p=0", str(dosya)], capture_output=True, text=True)
    try:
        return int(cikti.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0


def main() -> int:
    print("AfuDM video paneli canli testi\n")
    if api("/ping")[0] != 200:
        print(f"AfuDM {APP_PORT} portunda calismiyor — once uygulamayi ac.")
        return 2
    token = json.loads((ROOT / "data" / "api_endpoint.json").read_text("utf-8"))["token"]

    is_klasoru = Path(tempfile.mkdtemp(prefix="afudm_vp_"))
    film, oynatici = is_klasoru / "film", is_klasoru / "oynatici"
    film.mkdir()
    oynatici.mkdir()
    uret_videolar(oynatici)
    shutil.copy(oynatici / "klip.webm", film / "klip.webm")
    sunucu_b, port_b = sun(oynatici)
    _Sessiz.oynatici_kaynagi = f"http://127.0.0.1:{port_b}"
    (oynatici / "player.html").write_text(
        '<body style="margin:0"><video id="v" src="/klip.webm" muted autoplay loop '
        'style="width:640px;height:360px"></video>'
        "<script>fetch('/hls/master.m3u8').then(r => r.text())</script></body>", "utf-8")
    (film / "index.html").write_text(
        f"<title>{BASLIK}</title><h1>film</h1>"
        f'<iframe src="http://127.0.0.1:{port_b}/player.html" width="700" height="400"></iframe>', "utf-8")
    (film / "duz.html").write_text(
        '<title>Duz Video</title><video src="/klip.webm" muted autoplay loop '
        'style="width:640px;height:360px"></video>', "utf-8")
    (film / "bos.html").write_text(
        '<title>Akis</title><canvas id="c" width="640" height="360"></canvas>'
        '<video id="v" muted autoplay style="width:640px;height:360px"></video><script>'
        "const c=document.getElementById('c'),x=c.getContext('2d');"
        "setInterval(()=>{x.fillStyle='#'+Math.floor(Math.random()*4095).toString(16);x.fillRect(0,0,640,360)},100);"
        "document.getElementById('v').srcObject=c.captureStream(10);</script>", "utf-8")
    sunucu_a, port_a = sun(film)
    site = f"http://127.0.0.1:{port_a}"

    _, once = api("/snapshot", token)
    onceki = {i["gid"] for i in once.get("items", [])}
    eklenen: list[str] = []

    def yeni_is(sonek):
        _, snap = api("/snapshot", token)
        return next((i for i in snap.get("items", []) if i["gid"] not in onceki
                     and i.get("source", "").endswith(sonek)), None)

    def durum(gid):
        _, snap = api("/snapshot", token)
        return next((i for i in snap.get("items", []) if i["gid"] == gid), {})

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(is_klasoru / "profil"), headless=False,
                args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}",
                      "--lang=tr", "--autoplay-policy=no-user-gesture-required"],
            )
            sw = ctx.service_workers[0] if ctx.service_workers else \
                ctx.wait_for_event("serviceworker", timeout=15000)
            sw.evaluate("cfg => chrome.storage.local.set(cfg)",
                        {"port": APP_PORT, "token": token, "enabled": True, "videoCatch": True})

            # --- gomulu oynatici + HLS -------------------------------------
            sayfa = ctx.new_page()
            hatalar: list[str] = []
            sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
            sayfa.goto(site + "/index.html")
            cerceve = sayfa.frame_locator("iframe")
            dugme = cerceve.locator("afudm-panel .ana")
            try:
                dugme.wait_for(state="visible", timeout=15000)
                gorundu = True
            except Exception:
                gorundu = False
            record("Gomulu oynaticida (iframe) video oynayinca dugme cikti", gorundu,
                   dugme.inner_text().strip() if gorundu else "")

            if gorundu:
                dugme.click()
                secenekler = cerceve.locator("afudm-panel .secenek")
                try:
                    secenekler.first.wait_for(state="visible", timeout=20000)
                except Exception:
                    pass
                etiketler = [s.strip().split("\n")[0] for s in secenekler.all_inner_texts()]
                record("HLS ana listesinden kaliteler listelendi",
                       "720p" in etiketler and "360p" in etiketler, " | ".join(etiketler))
                record("Sadece ses secenegi var", "Sadece ses" in etiketler)

                secenekler.filter(has_text="360p").first.click()
                bilgi = cerceve.locator("afudm-panel .bilgi.iyi")
                try:
                    bilgi.wait_for(state="visible", timeout=10000)
                    record("Panel 'kuyruga eklendi' dedi", True, bilgi.inner_text())
                except Exception:
                    record("Panel 'kuyruga eklendi' dedi", False,
                           cerceve.locator("afudm-panel .bilgi").all_inner_texts()[:1])

                is_ = wait_for(lambda: yeni_is("/hls/master.m3u8"), timeout=15)
                if is_:
                    eklenen.append(is_["gid"])
                son = wait_for(lambda: durum(is_["gid"]).get("status") in ("complete", "error")
                               and durum(is_["gid"]), timeout=90) if is_ else {}
                son = son or {}
                record("AfuDM HLS videoyu indirdi (Referer korumasina ragmen)",
                       son.get("status") == "complete",
                       f"{son.get('status')} {str(son.get('errorMessage') or son.get('error') or '')[:60]}")
                parcalar = list(_Sessiz.hls_istekleri)
                reddedilen = [yol for yol, _, kod in parcalar if kod == 403]
                record("yt-dlp parca istekleri oynaticinin Referer'iyla geldi (403 yok)",
                       bool(parcalar) and not reddedilen,
                       f"{len(parcalar)} parca, {len(reddedilen)} ret; yalniz 360p: "
                       f"{all('/v1/' in yol for yol, _, _ in parcalar)}")
                dosya = Path(son.get("dir") or "") / (son.get("filename") or "")
                record("Dosya adi sekme basligindan", dosya.name.startswith(BASLIK), dosya.name)
                boy = yukseklik(dosya) if dosya.is_file() else 0
                record("Secilen kalite indi (360 piksel)", boy == 360, f"{boy}p")

            # --- duz dosya ---------------------------------------------------
            sayfa.goto(site + "/duz.html")
            dugme = sayfa.locator("afudm-panel .ana")
            dugme.wait_for(state="visible", timeout=15000)
            # service worker'i bilerek oldur: yakalanan medya kaybolmamali
            cdp = ctx.new_cdp_session(sayfa)
            try:
                hedefler = cdp.send("Target.getTargets")["targetInfos"]
                for hedef in hedefler:
                    if hedef["type"] == "service_worker" and "chrome-extension://" in hedef["url"]:
                        cdp.send("Target.closeTarget", {"targetId": hedef["targetId"]})
                sw_oldu = True
            except Exception:
                sw_oldu = False
            dugme.click()
            secenekler = sayfa.locator("afudm-panel .secenek")
            try:
                secenekler.first.wait_for(state="visible", timeout=20000)
            except Exception:
                pass
            etiketler = [s.strip().split("\n")[0] for s in secenekler.all_inner_texts()]
            record("Duz webm videoda 'Dosya' secenegi (service worker yeniden basladiktan sonra)",
                   any(e.startswith("Dosya") for e in etiketler),
                   (" | ".join(etiketler)) + ("" if sw_oldu else " [SW kapatilamadi]"))
            if any(e.startswith("Dosya") for e in etiketler):
                secenekler.filter(has_text="Dosya").first.click()
                is_ = wait_for(lambda: yeni_is("/klip.webm"), timeout=15)
                if is_:
                    eklenen.append(is_["gid"])
                son = wait_for(lambda: durum(is_["gid"]).get("status") == "complete"
                               and durum(is_["gid"]), timeout=30) if is_ else {}
                record("Duz dosya AfuDM'de tamamlandi", bool(son),
                       f"{(son or {}).get('completedLength', 0) // 1024} KB")

            # --- adresi olmayan video -----------------------------------------
            sayfa.goto(site + "/bos.html")
            dugme = sayfa.locator("afudm-panel .ana")
            try:
                dugme.wait_for(state="visible", timeout=15000)
                dugme.click()
                kotu = sayfa.locator("afudm-panel .bilgi.kotu")
                kotu.wait_for(state="visible", timeout=120000)
                record("Adresi olmayan videoda anlasilir 'bulunamadi' mesaji", True, kotu.inner_text())
            except Exception as exc:
                record("Adresi olmayan videoda anlasilir 'bulunamadi' mesaji", False, str(exc)[:60])

            record("Sayfalarda JS hatasi yok", not hatalar, "; ".join(hatalar)[:80])
            ctx.close()
    finally:
        for gid in eklenen:
            api("/control", token, {"action": "remove", "gid": gid, "delete_files": True})
        sunucu_a.shutdown()
        sunucu_b.shutdown()
        shutil.rmtree(is_klasoru, ignore_errors=True)

    gecen = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'=' * 52}\nSONUC: {gecen}/{len(results)} test gecti")
    kalan = [n for n, ok, _ in results if not ok]
    if kalan:
        print("Gecmeyenler: " + ", ".join(kalan))
    return 0 if gecen == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
