# -*- coding: utf-8 -*-
"""v1.6 Video Pro BACKEND testleri — AG GEREKTIRMEZ, gercek yt-dlp CALISTIRILMAZ.

Sinananlar:
  - her yeni alanin build_cmd ciktisinda dogru yt-dlp bayragini urettigi
  - alanlar bosken komutun ESKI haliyle birebir AYNI kaldigi (regresyon yok)
  - ffmpeg yokken --embed-* bayraklarinin SESSIZCE atlanmadigi edilmedigi
  - cookie_file + tarayici_cerezi cakismasinda cookie_file'in kazandigi
  - DownloadRequest.from_mapping alanlari tasiyip sinirlari uyguladigi

Usul: tests/format_test.py ve network_core_test.py ile ayni (AGSIZ + check/fails).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import models, paths  # noqa: E402
from video import ytdlp  # noqa: E402
from video.ytdlp import VideoJob  # noqa: E402

fails: list[str] = []
_toplam = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global _toplam
    _toplam += 1
    if not kosul:
        fails.append(ad + (("  <- " + detay) if detay else ""))


def _isin(*ek, **kw) -> VideoJob:
    """Kisa is kurucusu: URL/hedef varsayilan, Video Pro alanlarini ekler."""
    taban = {"job_id": "yt:t", "url": "https://ornek.com/v", "dest_dir": "."}
    taban.update(kw)
    return VideoJob(**taban)


def _komut(job: VideoJob, ffmpeg_var: bool = True, cerezsiz: bool = False) -> list[str]:
    """dis_indirici=False: aria2 bolumu atlanir, yalniz VideoJob mantigi olculur."""
    return job.build_cmd(aria2c="__yok__", dis_indirici=False,
                         ffmpeg_var=ffmpeg_var, cerezsiz=cerezsiz)


# --- 0) ESKI davranisin referans kopyasi -----------------------------------
# build_cmd'in v1.6 ONCESI ciktisi. Yeni alanlar girince komutun DEGISMEMESI
# bu kopyayla birebir karsilastirilarak kanıtlanır (regresyon kilidi).
def _eski_referans(job: VideoJob, ffmpeg_var: bool = True) -> list[str]:
    fmt = ytdlp.format_secimi(job.quality, job.audio_only, ffmpeg_var)
    govde = "%(title).150B"
    if job.dosya_adi:
        govde = ytdlp.guvenli_ad(job.dosya_adi).replace("%", "%%")
    out_tpl = str(Path(job.dest_dir) / f"{govde}.%(ext)s")
    if job.playlist:
        out_tpl = str(Path(job.dest_dir)
                      / "%(playlist_title).80B"
                      / "%(playlist_index)03d - %(title).120B.%(ext)s")
    cmd = [
        ytdlp.ytdlp_path(),
        "--newline", "--no-warnings", "--encoding", "utf-8",
        "--progress", "--progress-template", ytdlp.PROGRESS_TEMPLATE,
        "--continue", "--no-overwrites", "--retries", "10",
        "--fragment-retries", "10", "--concurrent-fragments", "8",
        "-o", out_tpl, "-f", fmt,
    ]
    if ffmpeg_var:
        cmd += ["--ffmpeg-location", paths.ffmpeg_dir()]
        if job.audio_only or job.quality == "audio":
            cmd += ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            cmd += ["--merge-output-format", "mp4"]
    cmd += ["--yes-playlist"] if job.playlist else ["--no-playlist"]
    if job.cookie_file:
        cmd += ["--cookies", job.cookie_file]
    if job.user_agent:
        cmd += ["--user-agent", job.user_agent]
    for anahtar, deger in (job.headers or {}).items():
        if anahtar.lower() == "referer":
            cmd += ["--referer", str(deger)]
        elif anahtar.lower() not in ("cookie", "user-agent"):
            cmd += ["--add-header", f"{anahtar}:{deger}"]
    if job.proxy:
        cmd += ["--proxy", job.proxy]
    cmd.append(job.url)
    return cmd


YENI_BAYRAMLAR = (
    "--write-subs", "--sub-langs", "--write-auto-subs", "--embed-subs",
    "--embed-thumbnail", "--write-thumbnail", "--embed-metadata",
    "--embed-chapters", "--split-chapters", "--sponsorblock-remove",
    "--download-sections", "--cookies-from-browser",
)


def _hiçbiri_yeni(komut: list[str]) -> bool:
    return not any(b in komut for b in YENI_BAYRAMLAR)


print("1) Alanlar bosken komut ESKI haliyle birebir ayni (regresyon yok)")
for etiket, ff, audi in (("video ffmpeg var", True, False),
                         ("video ffmpeg yok", False, False),
                         ("ses ffmpeg var", True, True)):
    job_eski = _isin(audio_only=True) if audi else _isin()
    yeni = _komut(job_eski, ffmpeg_var=ff)
    eski = _eski_referans(job_eski, ffmpeg_var=ff)
    check(f"{etiket}: komut DEGISMEDI", yeni == eski, str(yeni))
    check(f"{etiket}: hicbir yeni bayrak yok", _hiçbiri_yeni(yeni))
    check(f"{etiket}: dogru adresi indiriyor", yeni[-1] == "https://ornek.com/v")

# Baslikli is (dosya_adi akisi) de bozulmamali: % kacisi + guvenli_ad surer.
is_adi = _isin(dosya_adi='Film: "Adı" / %100')
check("dosya_adi akisi korunur",
      _komut(is_adi) == _eski_referans(is_adi), str(_komut(is_adi)))
check("adli komutta yeni bayrak yok", _hiçbiri_yeni(_komut(is_adi)))

print("2) Yeni alanlar -> dogru bayraklar")
j = _isin(
    altyazi_diller="tr,en", oto_altyazi=True, altyazi_goem=True,
    kucuk_resim="goem", ustveri_goem=True, bolumler="goem",
    sponsorblock="sponsor,selfpromo", bolum_araligi="00:01:00-00:02:30",
    kapsayici="mkv", tarayici_cerezi="chrome",
)
k = _komut(j)
check("altyazi dilleri --write-subs --sub-langs",
      "--write-subs" in k and k[k.index("--sub-langs") + 1] == "tr,en", str(k))
check("oto altyazi --write-auto-subs", "--write-auto-subs" in k)
check("altyazi gomme --embed-subs", "--embed-subs" in k)
check("kucuk resim gomme --embed-thumbnail", "--embed-thumbnail" in k)
check("ustveri gomme --embed-metadata", "--embed-metadata" in k)
check("bolum gomme --embed-chapters", "--embed-chapters" in k)
check("sponsorblock degerle",
      k[k.index("--sponsorblock-remove") + 1] == "sponsor,selfpromo", str(k))
check("bolum araligi yildizla",
      k[k.index("--download-sections") + 1] == "*00:01:00-00:02:30", str(k))
check("kapsayici mp4 yerine mkv",
      k[k.index("--merge-output-format") + 1] == "mkv", str(k))
check("tarayici cerezi --cookies-from-browser chrome",
      k[k.index("--cookies-from-browser") + 1] == "chrome", str(k))

# kucuk resim ayri dosya
k2 = _komut(_isin(kucuk_resim="dosya"))
check("kucuk resim dosya -> --write-thumbnail",
      "--write-thumbnail" in k2 and "--embed-thumbnail" not in k2, str(k2))

# bolumler "ayir"
k3 = _komut(_isin(bolumler="ayir"))
check("bolumler ayir -> --split-chapters",
      "--split-chapters" in k3 and "--embed-chapters" not in k3, str(k3))

# ses bicimi (yalniz audio_only dalinda)
ks1 = _komut(_isin(audio_only=True, ses_formati="aac"))
check("ses bicimi aac", ks1[ks1.index("--audio-format") + 1] == "aac", str(ks1))
ks2 = _komut(_isin(audio_only=True))
check("bos ses bicimi mp3 korunur", ks2[ks2.index("--audio-format") + 1] == "mp3", str(ks2))
kv = _komut(_isin(ses_formati="aac"))
check("video isinde ses bicimi YOK (audio branch isler)",
      "--audio-format" not in kv, str(kv))

# dosya sablonu -o'ya HAM gider (% kacisi bozulmaz)
kd = _komut(_isin(dosya_sablonu="Video/%(title)s.%(ext)s"))
check("dosya sablonu -o degerine yazilir",
      kd[kd.index("-o") + 1] == "Video/%(title)s.%(ext)s", str(kd))

print("3) ffmpeg YOKKEN --embed-* bayraklari atlanir ama not dusulur")
j7 = _isin(
    altyazi_diller="tr", oto_altyazi=True, altyazi_goem=True,
    kucuk_resim="goem", ustveri_goem=True, bolumler="goem",
    sponsorblock="sponsor", bolum_araligi="00:00:01-00:00:02",
)
k7 = _komut(j7, ffmpeg_var=False)
check("ffmpeg'siz gomme istegi gorunur not birakir", bool(j7.error), j7.error)
for bayrak in ("--embed-subs", "--embed-thumbnail", "--embed-metadata",
               "--embed-chapters"):
    check(f"ffmpeg'siz {bayrak} eklenmez", bayrak not in k7, str(k7))
# ffmpeg gerektirmeyenler DURMAZ
check("ffmpeg'siz --write-subs durur", "--write-subs" in k7)
check("ffmpeg'siz --write-auto-subs durur", "--write-auto-subs" in k7)
check("ffmpeg'siz --sponsorblock-remove durur", "--sponsorblock-remove" in k7)
check("ffmpeg'siz --download-sections durur", "--download-sections" in k7)
check("ffmpeg'siz --merge-output-format ISTENMEZ", "--merge-output-format" not in k7)

# kucuk resim 'dosya' ffmpeg'siz ayri dosya olarak iner
k8 = _komut(_isin(kucuk_resim="dosya"), ffmpeg_var=False)
check("ffmpeg'siz --write-thumbnail durur (dosya secenegi)",
      "--write-thumbnail" in k8 and "--embed-thumbnail" not in k8, str(k8))

print("4) cookie_file vs tarayici_cerezi: cookie_file ONCELIKLI")
kc = _komut(_isin(cookie_file="C:/cerez.txt", tarayici_cerezi="chrome"))
check("cookie_file kazanir", "--cookies" in kc and "--cookies-from-browser" not in kc, str(kc))
check("cerez dosyasi dogru deger", kc[kc.index("--cookies") + 1] == "C:/cerez.txt")
kt = _komut(_isin(tarayici_cerezi="chrome"))
check("ymlnz tarayici cerezi gider",
      "--cookies-from-browser" in kt and "--cookies" not in kt, str(kt))
check("profil degeri", kt[kt.index("--cookies-from-browser") + 1] == "chrome")
kcerezsiz = _komut(_isin(tarayici_cerezi="chrome"), cerezsiz=True)
check("cerezsiz denemede tarayici cerezi de DUSER", "--cookies-from-browser" not in kcerezsiz)

print("5) DownloadRequest.from_mapping alanlari tasir + sinirlar")
r = models.DownloadRequest.from_mapping({
    "source": "https://ornek.com/v",
    "altyazi_diller": "  tr,en  ",
    "oto_altyazi": True,
    "altyazi_goem": True,
    "kucuk_resim": "GOEM",
    "ustveri_goem": True,
    "bolumler": "ayir",
    "sponsorblock": "sponsor,selfpromo",
    "bolum_araligi": "00:01:00-00:02:30",
    "kapsayici": "mkv",
    "ses_formati": "aac",
    "dosya_sablonu": "Video/%(title)s.%(ext)s",
    "tarayici_cerezi": "chrome",
})
check("altyazi tasinir + bosluklar kirpilir", r.altyazi_diller == "tr,en", r.altyazi_diller)
check("oto_altyazi tasinir", r.oto_altyazi is True)
check("altyazi_goem tasinir", r.altyazi_goem is True)
check("kucuk_resim normalize", r.kucuk_resim == "goem", r.kucuk_resim)
check("ustveri_goem tasinir", r.ustveri_goem is True)
check("bolumler tasinir", r.bolumler == "ayir")
check("sponsorblock tasinir", r.sponsorblock == "sponsor,selfpromo")
check("bolum_araligi tasinir", r.bolum_araligi == "00:01:00-00:02:30")
check("kapsayici tasinir", r.kapsayici == "mkv")
check("ses_formati tasinir", r.ses_formati == "aac")
check("dosya_sablonu tasinir", r.dosya_sablonu == "Video/%(title)s.%(ext)s")
check("tarayici_cerezi tasinir", r.tarayici_cerezi == "chrome")

bos = models.DownloadRequest.from_mapping({"source": "https://ornek.com/v"})
check("bos girdide yeni alanlarin tumu BOS/False",
      bos.altyazi_diller == "" and bos.oto_altyazi is False and bos.altyazi_goem is False
      and bos.kucuk_resim == "" and bos.ustveri_goem is False and bos.bolumler == ""
      and bos.sponsorblock == "" and bos.bolum_araligi == "" and bos.kapsayici == ""
      and bos.ses_formati == "" and bos.dosya_sablonu == "" and bos.tarayici_cerezi == "",
      str(bos))

try:
    models.DownloadRequest.from_mapping({"source": "x", "kucuk_resim": "carpik"})
    check("gecersiz kucuk_resim RED", False)
except ValueError:
    check("gecersiz kucuk_resim RED", True)
try:
    models.DownloadRequest.from_mapping({"source": "x", "bolumler": "carpik"})
    check("gecersiz bolumler RED", False)
except ValueError:
    check("gecersiz bolumler RED", True)
try:
    models.DownloadRequest.from_mapping({"source": "x", "dosya_sablonu": "S" * 2000})
    check("asiri dosya_sablonu RED", False)
except ValueError:
    check("asiri dosya_sablonu RED", True)
try:
    models.DownloadRequest.from_mapping({"source": "x", "altyazi_diller": 5})
    check("metin olmayan altyazi RED", False)
except ValueError:
    check("metin olmayan altyazi RED", True)

for alan, deger in (
    ("kapsayici", "avi"), ("ses_formati", "ogg"),
    ("tarayici_cerezi", "bilinmeyen"), ("sponsorblock", "sponsor;intro"),
    ("bolum_araligi", "01:02:03"),
):
    try:
        models.DownloadRequest.from_mapping({"source": "x", alan: deger})
        check(f"gecersiz {alan} RED", False)
    except ValueError:
        check(f"gecersiz {alan} RED", True)

try:
    models.DownloadRequest.from_mapping({"source": "x", "kapsayici": "m" * 33})
    check("kapsayici uzunluk siniri korunur", False)
except ValueError as exc:
    check("kapsayici uzunluk siniri korunur", "cok uzun" in str(exc), str(exc))

print("\nvideo pro: %d kontrol, %d hata" % (_toplam, len(fails)))
if fails:
    for f in fails:
        print("  HATA: %s" % f)
    sys.exit(1)
print("OK: video pro backend tutarli")
