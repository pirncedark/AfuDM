"""Oturum cerezleri testi — AG GEREKTIRMEZ, aria2/yt-dlp CALISTIRILMAZ.

1) Guvenilmeyen girdi: satir sonu/sekme iceren cerez atilir (baslik/dosya enjeksiyonu)
2) Netscape dosyasi Python'un cookiejar'i ile okunuyor ve alan adi eslesmesi dogru
3) Yonetici: cerez aria2'ye Cookie basligi olarak gidiyor, VERITABANINA YAZILMIYOR
4) Video: yt-dlp'ye --cookies dosyasi veriliyor, is bitince dosya siliniyor
5) Is bitince / silinince bellekteki cerez birakiliyor
"""
from __future__ import annotations

import http.cookiejar
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cerez  # noqa: E402
from core.db import Store  # noqa: E402
from core.manager import Manager  # noqa: E402
from video import ytdlp  # noqa: E402

fails: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("  [GECTI] " if condition else "  [BASARISIZ] ") + name
          + (f" — {detail}" if detail else ""))
    if not condition:
        fails.append(name)


GIZLI = "OTURUM-GIZLI-4f9a"
TARAYICI = [
    {"name": "sid", "value": GIZLI, "domain": "drive.example.com", "path": "/",
     "secure": True, "hostOnly": True, "expirationDate": 0},
    {"name": "tercih", "value": "tr", "domain": ".example.com", "path": "/",
     "secure": False, "hostOnly": False, "expirationDate": 4102444800.5},
]

print("1) Guvenilmeyen girdi")
kotu = TARAYICI + [
    {"name": "x", "value": "a\r\nX-Enjekte: 1", "domain": "example.com"},
    {"name": "y\tz", "value": "1", "domain": "example.com"},
    {"name": "", "value": "1", "domain": "example.com"},
    {"name": "k", "value": "a;b", "domain": "example.com"},
    {"name": "d", "value": "1", "domain": ""},
    "cerez degil", 42,
]
temiz = cerez.temizle(kotu)
check("yalniz gecerli 2 cerez kaldi", [c["name"] for c in temiz] == ["sid", "tercih"],
      str([c["name"] for c in temiz]))
check("liste olmayan girdi bos doner", cerez.temizle({"name": "a"}) == [] and cerez.temizle(None) == [])
check("boyut siniri uygulaniyor",
      len(cerez.temizle([{"name": f"c{i}", "value": "v" * 1000, "domain": "a.com"}
                         for i in range(100)])) < 40)
check("Cookie basligi dogru", cerez.baslik(temiz) == f"sid={GIZLI}; tercih=tr", cerez.baslik(temiz))

print("\n2) Netscape dosyasi (yt-dlp bicimi)")
tmp = Path(tempfile.mkdtemp(prefix="afudm_cerez_"))
dosya = tmp / "c.txt"
dosya.write_text(cerez.netscape(temiz), encoding="utf-8")
try:
    # Asil tuketici yt-dlp: onun okuyucusu "0" bitisi OTURUM cerezi sayar
    # (Python'un MozillaCookieJar'i ise suresi dolmus sayip gondermez).
    from yt_dlp.cookies import YoutubeDLCookieJar
    jar = YoutubeDLCookieJar(str(dosya))
    yt_dlp_okuyucu = True
except ImportError:
    jar = http.cookiejar.MozillaCookieJar(str(dosya))
    yt_dlp_okuyucu = False
jar.load(ignore_discard=True, ignore_expires=True)
print(f"  okuyucu: {type(jar).__name__}")


def gonderilen(url: str) -> str:
    istek = urllib.request.Request(url)
    jar.add_cookie_header(istek)
    return istek.get_header("Cookie") or ""


if yt_dlp_okuyucu:
    # Oturum cerezi (expires=0) gonderimi YALNIZ yt-dlp'nin okuyucusuyla
    # dogrulanabilir; stdlib cookiejar onu "suresi dolmus" sayip gondermez.
    # CI'da yt_dlp pip paketi YOK (AfuDM yt-dlp'yi gomulu exe olarak tasir),
    # o yuzden bu kontrol orada anlamsiz — atlanir, kalan kontroller kosar.
    check("drive.example.com'a iki cerez de gider",
          GIZLI in gonderilen("https://drive.example.com/f") and "tercih" in gonderilen("https://drive.example.com/f"))
else:
    print("  ATLANDI: oturum cerezi (expires=0) gonderimi yalniz yt-dlp okuyucusuyla dogrulanir — CI'da yt_dlp yok, gercek tuketici gomulu yt-dlp.exe")
satir = next(s for s in dosya.read_text("utf-8").splitlines() if "\tsid\t" in s)
check("hostOnly cerez dosyada alt alan KAPALI yaziliyor",
      satir.split("\t")[:2] == ["drive.example.com", "FALSE"], satir.split("\t")[:2])
# NOT: yt-dlp'nin (Python cookiejar) politikasi bu bayragi YOK SAYAR; hostOnly
# cerez x.drive.example.com gibi ALT alanlara da gider. Ayni sitenin icinde kalir,
# yabanci alana gitmez (asagidaki kontrol). curl/aria2 bayraga uyar.
check("hostOnly cerez komsu alana gitmez",
      GIZLI not in gonderilen("https://cdn.example.com/f") and "tercih" in gonderilen("https://cdn.example.com/f"))
check("secure cerez http'ye gitmez", GIZLI not in gonderilen("http://drive.example.com/f"))

print("\n3) Yonetici + aria2")


class SahteRPC:
    def __init__(self):
        self.eklenen: list[tuple[list, dict]] = []

    def add_uri(self, uris, options=None):
        self.eklenen.append((uris, options or {}))
        return f"gid{len(self.eklenen):013d}"

    def remove(self, *a, **k):
        return "ok"

    # find_duplicate motordaki isleri sorar (olu kayit temizligi icin)
    def tell_active(self, *a, **k):
        return []

    def tell_waiting(self, *a, **k):
        return []

    def tell_stopped(self, *a, **k):
        return []

    remove_result = remove


cerez.KLASOR = tmp / "cerez"  # gercek data/ klasorune dokunma
m = Manager.__new__(Manager)
m.store = Store(str(tmp / "test.db"))
m.rpc = SahteRPC()
m.video_jobs = {}
m._video_seq = 0
m._lock = threading.RLock()
m._known_complete = set()
m._cerezler = {}
m.last_error = ""

sonuc = m.add("https://drive.example.com/indir?id=1", kind="http", dest_dir=str(tmp),
              cookies=kotu, user_agent="Mozilla/5.0 Test\r\nX-Enjekte: 1",
              headers={"Referer": "https://drive.example.com/"})
_, secenek = m.rpc.eklenen[-1]
check("aria2'ye Cookie basligi gitti",
      f"Cookie: sid={GIZLI}; tercih=tr" in secenek.get("header", []), str(secenek.get("header")))
check("Referer korundu", "Referer: https://drive.example.com/" in secenek.get("header", []))
check("enjekte satir basliga girmedi",
      not any("X-Enjekte" in h and not h.startswith("User") for h in secenek.get("header", [])))
check("user-agent tek satir", "\n" not in secenek.get("user-agent", "") and
      secenek.get("user-agent", "").startswith("Mozilla/5.0 Test"), repr(secenek.get("user-agent")))

m.store.conn.commit()
db_bayt = b"".join(p.read_bytes() for p in tmp.glob("test.db*"))
check("cerez VERITABANINA YAZILMADI", GIZLI.encode() not in db_bayt,
      f"{len(db_bayt)} bayt tarandi")
check("bellekte tutuluyor", sonuc["id"] in m._cerezler)

m.remove(sonuc["gid"])
check("silinince bellekten birakildi", sonuc["id"] not in m._cerezler)

cerezsiz = m.add("https://example.com/acik.zip", kind="http", dest_dir=str(tmp))
_, secenek = m.rpc.eklenen[-1]
check("cerez yoksa Cookie basligi yok",
      not any(h.startswith("Cookie") for h in secenek.get("header", [])))

print("\n4) Video (yt-dlp)")
komutlar: list[list[str]] = []
ytdlp.VideoJob.start = lambda self, aria2c=None, on_update=None, ffmpeg_var=None: \
    komutlar.append(self.build_cmd(aria2c, ffmpeg_var=True))
video = m.add("https://www.youtube.com/watch?v=abc", kind="video", dest_dir=str(tmp),
              cookies=TARAYICI, user_agent="Mozilla/5.0 Test")
cmd = komutlar[-1]
cdosya = Path(cmd[cmd.index("--cookies") + 1]) if "--cookies" in cmd else None
check("yt-dlp'ye --cookies verildi", bool(cdosya) and cdosya.exists(), str(cdosya))
check("dosyada cerez var", bool(cdosya) and GIZLI in cdosya.read_text("utf-8"))
check("yt-dlp'ye --user-agent verildi", "--user-agent" in cmd)

job = m.video_jobs[video["gid"]]
job.status = "complete"
job.finished_at = 1.0
m._on_complete = lambda *a: None
m._on_video_update(job)
check("is bitince cerez dosyasi silindi", bool(cdosya) and not cdosya.exists())
check("is bitince bellekten birakildi", video["id"] not in m._cerezler)

cerezsiz_video = m.add("https://www.youtube.com/watch?v=def", kind="video", dest_dir=str(tmp))
check("cerez yoksa --cookies yok", "--cookies" not in komutlar[-1])

print("\n5) Artik temizligi")
cerez.dosya_yaz("yt:99", TARAYICI)
check("onceki calismadan kalan dosya temizlendi",
      cerez.artiklari_temizle() == 1 and not any(cerez.KLASOR.glob("*.txt")))

m.store.conn.close()
print("\n" + ("Hepsi gecti" if not fails else "BASARISIZ: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
