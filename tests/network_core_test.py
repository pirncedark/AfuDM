# -*- coding: utf-8 -*-
"""Network Core v1.4 testleri (ag GEREKTIRMEZ).

- `core/proxy.parcala` icin sekme/kullanici/sebeke varyontlari
- aria2/youtube komut secenekleri uretimi
- `models.checksum_ayikla` (tip sinesir, format dogrulama)
- `DownloadRequest` proxy/checksum sinirlari
- `Manager._proksi` katman onceligi (is->sistem->genel)
- CLI `--proxy/--checksum` + `ayarla`/`ayar` alt komutlari parse ediliyor
"""
from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core import proxy as P  # noqa: E402
from core import models  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


print("1) proxy.parcala varyontlari")
p = P.parcala("socks5://127.0.0.1:1080")
check("socks5 sekme", p == {"tip": "socks5", "adres": "127.0.0.1:1080",
                            "kullanici": "", "sifre": ""}, str(p))
p = P.parcala("http://proxy.ornek.com:8123")
check("http sekme", p["tip"] == "http" and p["adres"] == "proxy.ornek.com:8123", str(p))
p = P.parcala("user:pass@proxy.ornek.com:3128")
check("sekmesiz + kimlik", p["adres"] == "proxy.ornek.com:3128"
      and p["tip"] == "http" and p["kullanici"] == "user" and p["sifre"] == "pass", str(p))
p = P.parcala("socks5://k:sifre@10.0.0.5:9050")
check("socks5 + kimlik", p["tip"] == "socks5" and p["adres"] == "10.0.0.5:9050"
      and p["kullanici"] == "k" and p["sifre"] == "sifre", str(p))
check("socks5h -> socks5", P.parcala("socks5h://h:1")["tip"] == "socks5")
check("https -> http", P.parcala("https://h:443")["tip"] == "http")
check("socks4 kabul", P.parcala("socks4://h:1080")["tip"] == "socks4")
for kotu in ("", "trash", "socks6://h:1", "http://sadece-host", "mail@:"):
    try:
        P.parcala(kotu)
        check(f"red: {kotu!r}", False)
    except ValueError:
        check(f"red: {kotu!r}", True)
try:
    P.parcala("http://" + "k" * 1200 + ":80")
    check("asiri uzun red", False)
except ValueError:
    check("asiri uzun red", True)

print("2) motor secenecek uretimi")
p = P.parcala("socks5://k:sifre@127.0.0.1:1080")
sec = P.aria2_secenekleri(p)
check("all-proxy adres", sec.get("all-proxy") == "127.0.0.1:1080")
check("all-proxy-type socks5", sec.get("all-proxy-type") == "socks5")
check("auth aktarilir", sec.get("all-proxy-user") == "k" and sec.get("all-proxy-passwd") == "sifre")
check("yt-dlp url", P.url(p) == "socks5://k:sifre@127.0.0.1:1080", P.url(p))
komut = P.komut_secenekleri(P.parcala("http://host:80"))
check("komut satiri", "--all-proxy=host:80" in komut and "--all-proxy-type=http" in komut, komut)

print("3) checksum_ayikla")
check("sha-256:", models.checksum_ayikla("sha-256:AbC123") == "sha-256=abc123")
check("sha-256= :", models.checksum_ayikla("sha-256=ab") == "sha-256=ab")
check("sha1 -> sha-1", models.checksum_ayikla("sha1:ab") == "sha-1=ab")
check("md5:", models.checksum_ayikla("md5:AB") == "md5=ab")
check("bos -> None", models.checksum_ayikla("") is None and models.checksum_ayikla(None) is None)
try:
    models.checksum_ayikla("sha-999:ab")
    check("bilinmeyen tip red", False)
except ValueError:
    check("bilinmeyen tip red", True)
try:
    models.checksum_ayikla("sha-256:XYZ")
    check("hex olmayan red", False)
except ValueError:
    check("hex olmayan red", True)

print("4) DownloadRequest proxy/checksum alanlari")
r = models.DownloadRequest.from_mapping({
    "source": "https://a.com/f.zip",
    "proxy": "  socks5://127.0.0.1:1080  ",
    "checksum": "sha-256:abc",
})
check("proxy temizlenir", r.proxy == "socks5://127.0.0.1:1080", r.proxy)
check("checksum normalize", r.checksum == "sha-256=abc", r.checksum)
try:
    models.DownloadRequest.from_mapping({"source": "https://a.com", "proxy": "x" * 2000})
    check("asiri proxy red", False)
except ValueError:
    check("asiri proxy red", True)

print("5) Manager._proksi katman onceligi")


class _FakeStore:
    def __init__(self, sistem, genel):
        self._sistem, self._genel = sistem, genel

    def get(self, k, d=None):
        if k == "system_proxy":
            return self._sistem
        if k == "proxy":
            return self._genel
        return d


class _FakeSelf:
    store = _FakeStore(True, "")


from core.manager import Manager  # noqa: E402

g = Manager._proksi(_FakeSelf(), {"proxy": "socks5://is:1"})
check("once is proxy", g["tip"] == "socks5" and g["adres"] == "is:1", str(g))
# is proxy yok, sistem kapali
self2 = _FakeSelf()
self2.store = _FakeStore(False, "http://genel:80")
g = Manager._proksi(self2, {"proxy": ""})
check("sistem kapaliyken genel", g["tip"] == "http" and g["adres"] == "genel:80", str(g))
# sistem acik ama registry'de yok -> genel
self3 = _FakeSelf()
self3.store = _FakeStore(True, "http://genel:80")
g = Manager._proksi(self3, {"proxy": ""})
check("isl olmayinca genel (sistem bos)", g["adres"] == "genel:80", str(g))
# hicbir katman yok
self4 = _FakeSelf()
self4.store = _FakeStore(False, "")
check("katman yok -> None", Manager._proksi(self4, {"proxy": ""}) is None)

print("6) _baglanti_secenekleri + VideoJob proxy")
b = Manager._baglanti_secenekleri(object(), {})
check("bos -> bos", b == {})
b = Manager._baglanti_secenekleri(object(), {"baglanti": 8, "hiz_kb": 500})
check("canli ayar geri okunur", b == {"max-connection-per-server": "8",
                                      "max-download-limit": "500K"}, str(b))
b = Manager._baglanti_secenekleri(object(), {"baglanti": 99, "hiz_kb": 0})
check("sinir disi baglanti atlanir", b == {}, str(b))

from video.ytdlp import VideoJob  # noqa: E402
j = VideoJob(job_id="yt:1", url="https://youtube.com/watch?v=x", dest_dir=".",
             proxy="http://127.0.0.1:8123")
komut = j.build_cmd(aria2c="__yok__", dis_indirici=False)
check("yt-dlp --proxy eklenir", "--proxy" in komut and "http://127.0.0.1:8123" in komut, str(komut))

print("7) CLI yeni secenekler parselleniyor")
from afuadm import komutlar_ayirici  # noqa: E402
k = komutlar_ayirici().parse_args(
    ["add", "https://a.com/f.zip", "--proxy", "socks5://h:1",
     "--checksum", "sha-256:ab", "--audio-only"])
check("add --proxy", getattr(k, "proxy", None) == "socks5://h:1")
check("add --checksum", getattr(k, "checksum", None) == "sha-256:ab")
check("ortak --json korunur", getattr(k, "json", None) is False)
k2 = komutlar_ayirici().parse_args(["ayarla", "abc123", "--baglanti", "8", "--hiz", "300"])
check("ayarla parse", getattr(k2, "baglanti", None) == 8 and getattr(k2, "hiz", None) == 300)
k3 = komutlar_ayirici().parse_args(["ayar", "proxy", "socks5://h:1"])
check("ayar parse", getattr(k3, "anahtar", None) == "proxy"
      and getattr(k3, "deger", None) == "socks5://h:1")

print("\nnetwork core: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: network core tutarli")