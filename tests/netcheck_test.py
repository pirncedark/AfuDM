# -*- coding: utf-8 -*-
"""IPv6 yoksa aria2 komutlarina --disable-ipv6 girmeli, varsa GIRMEMELI.

Ag gerektirmez; yalniz komut kurulumunu dogrular. (Kok neden: aria2c IPv6 yolu
olmayan makinede AAAA adresini deneyip indirmeyi iptal ediyordu.)
"""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

fails = []

try:
    from core import netcheck
except Exception as exc:
    print("[BASARISIZ] core.netcheck yok:", exc)
    sys.exit(1)

usable = netcheck.ipv6_usable()
print("ipv6_usable() =", usable)

from video.ytdlp import VideoJob
job = VideoJob(job_id="t", url="https://www.youtube.com/watch?v=x", dest_dir=".", quality="audio")
cmd = " ".join(job.build_cmd())
has_flag = "--disable-ipv6=true" in cmd
if usable and has_flag:
    fails.append("IPv6 calisiyorken yt-dlp komutunda --disable-ipv6 olmamali")
if not usable and not has_flag:
    fails.append("IPv6 yokken yt-dlp downloader-args icinde --disable-ipv6=true olmali")

from core import daemon
dargs = " ".join(daemon._args("secret", "."))
dflag = "--disable-ipv6=true" in dargs
if usable and dflag:
    fails.append("IPv6 calisiyorken aria2 daemon'da --disable-ipv6 olmamali")
if not usable and not dflag:
    fails.append("IPv6 yokken aria2 daemon args icinde --disable-ipv6=true olmali")

if fails:
    for f in fails:
        print("[BASARISIZ]", f)
    sys.exit(1)
print("[GECTI] IPv6 bayragi dogru kuruluyor")
