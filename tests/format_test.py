# -*- coding: utf-8 -*-
"""Video format secimi — AG GEREKTIRMEZ.

Kural: ffmpeg YOKSA yt-dlp'ye ayri video + ayri ses istetmek olmaz, cunku
birlestirecek bir sey kalmaz (kullanici sessiz video indirir). O durumda
SES+VIDEO BIRLESIK gelen formatlar secilmeli — IDM'in yaptigi is budur.
ffmpeg VARSA eski davranis surer: en iyi video + en iyi ses, mp4'e birlestir.
"""
import pathlib
import sys

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from video import ytdlp  # noqa: E402

hatalar: list[str] = []


def kontrol(ad: str, kosul: bool, detay: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {detay}" if detay else ""))
    if not kosul:
        hatalar.append(ad)


print("1) ffmpeg VARKEN (birlestirme yapilabilir)")
f = ytdlp.format_secimi("best", audio_only=False, birlestirilebilir=True)
kontrol("en iyi video + en iyi ses istenir", "bestvideo" in f and "bestaudio" in f, f)
f1080 = ytdlp.format_secimi("1080", audio_only=False, birlestirilebilir=True)
kontrol("1080 siniri korunur", "height<=1080" in f1080, f1080)

print("2) ffmpeg YOKKEN (birlestirme yapilamaz)")
f = ytdlp.format_secimi("best", audio_only=False, birlestirilebilir=False)
kontrol("ayri video+ses ISTENMEZ", "bestvideo" not in f, f)
kontrol("sesi olan format sart kosulur", "acodec!=none" in f, f)
kontrol("once mp4 denenir", "ext=mp4" in f, f)
f720 = ytdlp.format_secimi("720", audio_only=False, birlestirilebilir=False)
kontrol("720 siniri korunur", "height<=720" in f720, f720)
kontrol("yine de bir yedek zincir var", "/" in f720, f720)

print("3) Sadece ses")
f = ytdlp.format_secimi("audio", audio_only=True, birlestirilebilir=True)
kontrol("ffmpeg varken en iyi ses", "bestaudio" in f, f)
f = ytdlp.format_secimi("audio", audio_only=True, birlestirilebilir=False)
kontrol("ffmpeg yokken de ses indirilir", "bestaudio" in f, f)

print("4) Komut kurulumu")
job = ytdlp.VideoJob(job_id="t", url="https://ornek.com/v", dest_dir=".", quality="best")
cmd_var = " ".join(job.build_cmd())
kontrol("ffmpeg varken mp4'e birlestir denir", "--merge-output-format" in cmd_var)

job2 = ytdlp.VideoJob(job_id="t2", url="https://ornek.com/v", dest_dir=".", quality="best")
cmd_yok = " ".join(job2.build_cmd(ffmpeg_var=False))
kontrol("ffmpeg yokken birlestirme ISTENMEZ", "--merge-output-format" not in cmd_yok)
kontrol("ffmpeg yokken --ffmpeg-location verilmez", "--ffmpeg-location" not in cmd_yok)
kontrol("ffmpeg yokken birlesik format istenir", "acodec!=none" in cmd_yok)

job3 = ytdlp.VideoJob(job_id="t3", url="https://ornek.com/v", dest_dir=".",
                      quality="audio", audio_only=True)
cmd_mp3 = " ".join(job3.build_cmd(ffmpeg_var=False))
kontrol("ffmpeg yokken mp3'e cevirme ISTENMEZ", "--audio-format mp3" not in cmd_mp3,
        "ffmpeg olmadan donusturulemez, ses dosyasi oldugu gibi iner")

print("5) Anlasilir hata metni")
job4 = ytdlp.VideoJob(job_id="t4", url="https://ornek.com/v", dest_dir=".", quality="best", dil="tr")
job4.ffmpeg_vardi = False
mesaj = job4.anlasilir_hata("ERROR: [youtube] xyz: Requested format is not available. Use --list-formats")
kontrol("ffmpeg yokken ham hata cevriliyor", "ffmpeg" in mesaj and "Requested format" not in mesaj, mesaj[:70])
kontrol("mesaj Turkce", "gerekiyor" in mesaj)

job4.dil = "en"
mesaj_en = job4.anlasilir_hata("ERROR: Requested format is not available")
kontrol("Ingilizce karsiligi var", "needed" in mesaj_en, mesaj_en[:70])

job4.ffmpeg_vardi = True
ham = "ERROR: Requested format is not available"
kontrol("ffmpeg VARKEN ham hata korunur", job4.anlasilir_hata(ham) == ham)

baska = "ERROR: HTTP Error 403: Forbidden"
job4.ffmpeg_vardi = False
kontrol("ilgisiz hata degistirilmez", job4.anlasilir_hata(baska) == baska)

job5 = ytdlp.VideoJob(job_id="t5", url="https://ornek.com/v", dest_dir=".",
                      quality="audio", audio_only=True, dil="tr")
job5.ffmpeg_vardi = False
ses_mesaj = job5.anlasilir_hata("ERROR: Requested format is not available")
kontrol("ses isinde mp3 mesaji verilir", "mp3" in ses_mesaj, ses_mesaj[:70])

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
