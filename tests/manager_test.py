# -*- coding: utf-8 -*-
"""Ag gerektirmeyen davranis testleri.

1) Magnet ustveri kaydi ([METADATA]...) kullaniciya gosterilmemeli; gercek
   torrent devralinca (followedBy) o satir listeden dusmeli.
2) Video basligi URL'den tahmin edilen "watch" gibi bir sey degil, yt-dlp'nin
   urettigi gercek dosya adi olmali.
"""
import sys

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from core.manager import Manager  # noqa: E402
from video.ytdlp import VideoJob  # noqa: E402

fails: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("  [GECTI] " if condition else "  [BASARISIZ] ") + name + (f" — {detail}" if detail else ""))
    if not condition:
        fails.append(name)


print("1) Magnet ustveri satiri")
devralindi = {
    "gid": "aaa",
    "followedBy": ["bbb"],
    "bittorrent": {"info": {"name": "[METADATA]Sintel"}},
    "files": [{"path": "[METADATA]08ada5a7"}],
}
cozuluyor = {
    "gid": "aaa",
    "bittorrent": {"info": {"name": "[METADATA]Sintel"}},
    "files": [{"path": "[METADATA]08ada5a7"}],
}
gercek = {
    "gid": "bbb",
    "bittorrent": {"info": {"name": "Sintel"}},
    "files": [{"path": "downloads/Sintel/Sintel.mp4"}],
}
check("devralinan ustveri kaydi gizlenir", Manager.is_metadata_only(devralindi) is True)
check("cozulmeyi bekleyen ustveri kaydi gizlenmez", Manager.is_metadata_only(cozuluyor) is False,
      "kullanici magneti ekledigini gormeli")
check("gercek torrent gizlenmez", Manager.is_metadata_only(gercek) is False)
check("ustveri basligindaki [METADATA] eki temizlenir",
      Manager.clean_title("[METADATA]Sintel") == "Sintel")
check("normal baslik degismez", Manager.clean_title("Sintel") == "Sintel")

print("2) Video basligi")
job = VideoJob(job_id="yt:1", url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
               dest_dir=".", title="watch")
check("dosya adi bilinmeden URL tahmini kalir", job.display_title() == "watch")
job.filename = "Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp3"
check("dosya adi gelince gercek baslik kullanilir",
      job.display_title() == "Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film",
      job.display_title())
bos = VideoJob(job_id="yt:2", url="https://ornek.com/video", dest_dir=".")
check("baslik da dosya adi da yoksa URL'e duser", bos.display_title() == "https://ornek.com/video")

print("3) Desteklenen kaynak")
for iyi in ("https://a.com/f.zip", "http://a.com/f.zip", "ftp://a.com/f.zip",
            "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10"):
    check(f"kabul: {iyi[:28]}", Manager.is_supported_source(iyi) is True)
# Panodan/elle gelen duz metin aria2'ye gidince "Unrecognized URI or unsupported
# protocol" diye kaybolurdu; artik ekleme aninda anlasilir hata veriyor.
for kotu in ("Ternet Ninja 3 2025 WEB DL 1080p DUAL.mp4", "merhaba dunya",
             "C:/yok/olmayan.torrent", "www.ornek.com/f.zip"):
    check(f"red: {kotu[:28]}", Manager.is_supported_source(kotu) is False)

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
