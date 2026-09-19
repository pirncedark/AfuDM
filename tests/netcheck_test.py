# -*- coding: utf-8 -*-
"""IPv6 yoksa aria2 komutlarina --disable-ipv6 girmeli, varsa GIRMEMELI.

Ag gerektirmez; yalniz komut kurulumunu dogrular. (Kok neden: aria2c IPv6 yolu
olmayan makinede AAAA adresini deneyip indirmeyi iptal ediyordu.)

Yt-dlp bayragi YALNIZCA harici indirici (aria2c) kullanilirken uretildigi icin
test build_cmd'e VAR OLAN bir aria2c yolu verir (sahte dosya; icerigi onemsiz,
CI'da gercek engine/aria2c.exe yok). Ayrica netcheck._cached gecici olarak
True/False'a zorlanip her iki IPv6 dali da AYNI kosuda dogrulanir; boylece test
ortamin IPv6 durumuna gore sessizce atlanamaz.
"""
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

fails = []

try:
    from core import netcheck
except Exception as exc:
    print("[BASARISIZ] core.netcheck yok:", exc)
    sys.exit(1)

gercek = netcheck.ipv6_usable()
print("ipv6_usable() =", gercek)

from video.ytdlp import VideoJob
from core import daemon


def ytdlp_komutu(ipv6_var: bool, aria2c_yolu: str) -> list[str]:
    """netcheck onbellegini gecici olarak zorla, yt-dlp komutunu kur, eski degeri geri koy."""
    eski = netcheck._cached
    netcheck._cached = ipv6_var
    try:
        job = VideoJob(job_id="t", url="https://www.youtube.com/watch?v=x",
                       dest_dir=".", quality="audio")
        return job.build_cmd(aria2c=aria2c_yolu)
    finally:
        netcheck._cached = eski


def downloader_arg(cmd: list[str]) -> str:
    """--downloader-args'in ARGUMANI (tek tokendir). Yoksa bossa dis indirici dali calismadi."""
    if "--downloader-args" not in cmd:
        return ""
    i = cmd.index("--downloader-args")
    return cmd[i + 1] if i + 1 < len(cmd) else ""


# CI'da engine/aria2c.exe yok; Path(...).exists() True donduren sahte dosya ver.
with tempfile.TemporaryDirectory() as td:
    sahte_aria2c = Path(td) / "aria2c.exe"
    sahte_aria2c.write_bytes(b"calistirilmayacak; sadece var olmasi lazim")

    for ipv6 in (True, False):
        cmd_list = ytdlp_komutu(ipv6, str(sahte_aria2c))
        cmd_str = " ".join(cmd_list)
        dargs = downloader_arg(cmd_list)
        print("[YTDLP ipv6=%s] downloader-args: %r" % (ipv6, dargs))
        if not dargs:
            fails.append("dis indirici (aria2c) dali calismadi: --downloader-args bos")
        if ipv6 and "--disable-ipv6=true" in cmd_str:
            fails.append("IPv6 calisiyorken yt-dlp komutunda --disable-ipv6 olmamali")
        if not ipv6 and "--disable-ipv6=true" not in dargs:
            fails.append("IPv6 yokken yt-dlp downloader-args icinde --disable-ipv6=true olmali")
        if not ipv6 and "--disable-ipv6=true" in cmd_str and \
                "--disable-ipv6=true" not in dargs:
            fails.append("IPv6 yokken --disable-ipv6=true --downloader-args DISINDA goruldu")

    # aria2 daemon: ortamin GERCEK durumuna gore (mevcut kontrolleri bozma).
    dargs = " ".join(daemon._args("secret", "."))
    dflag = "--disable-ipv6=true" in dargs
    print("daemon ipv6=", gercek, "dflag=", dflag)
    if gercek and dflag:
        fails.append("IPv6 calisiyorken aria2 daemon'da --disable-ipv6 olmamali")
    if not gercek and not dflag:
        fails.append("IPv6 yokken aria2 daemon args icinde --disable-ipv6=true olmali")

if fails:
    for f in fails:
        print("[BASARISIZ]", f)
    sys.exit(1)
print("[GECTI] IPv6 bayragi dogru kuruluyor (iki dal da dogrulandi)")