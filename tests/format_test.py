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

print("2) ffmpeg YOKKEN (birlestirmeyi KENDIMIZ yapiyoruz)")
# Artik ffmpeg yoksa da iki izi ayri isteyebiliyoruz: video/mp4mux.py birlestiriyor.
# Sart su: iki iz de MP4 ailesinden olmali (video mp4 + ses m4a), cunku
# birlestiricimiz webm/opus'u mp4'e koyamaz.
f = ytdlp.format_secimi("best", audio_only=False, birlestirilebilir=False)
kontrol("ayri iz istenir (kendi birlestiricimiz icin)", "bv*" in f and "+ba" in f, f)
kontrol("video mp4 sart kosulur", "[ext=mp4]" in f, f)
kontrol("ses m4a sart kosulur", "ba[ext=m4a]" in f, f)
kontrol("son care birlesik format", "acodec!=none" in f, f)
f720 = ytdlp.format_secimi("720", audio_only=False, birlestirilebilir=False)
kontrol("720 siniri korunur", "height<=720" in f720, f720)
kontrol("sinir hem ayri hem birlesik secenege uygulanir",
        f720.count("height<=720") >= 3, f"{f720.count('height<=720')} yerde")
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

print("\nVideo paneli: keyfi yukseklik, Referer, sayfa basligi")
kontrol("tabloda olmayan 360 'best'e DUSMEZ",
        ytdlp.format_secimi("360", False, True) == "bestvideo[height<=360]+bestaudio/best[height<=360]",
        ytdlp.format_secimi("360", False, True))
kontrol("ffmpeg'siz 360 kendi birlestiriciye gider",
        "[height<=360]" in ytdlp.format_secimi("360", False, False)
        and "[ext=m4a]" in ytdlp.format_secimi("360", False, False))
kontrol("tablodaki 720 degismedi",
        ytdlp.format_secimi("720", False, True) == ytdlp.QUALITY_FORMATS["720"])
job6 = ytdlp.VideoJob(job_id="t6", url="https://cdn.ornek.com/master.m3u8", dest_dir="C:/indir",
                      headers={"Referer": "https://oynatici.ornek.com/e/1", "Origin": "https://oynatici.ornek.com",
                               "Cookie": "gizli=1"},
                      dosya_adi='Film: "Adı" / %100 ?')
cmd6 = job6.build_cmd(aria2c="yok.exe", ffmpeg_var=True)
kontrol("Referer yt-dlp'ye --referer ile gider",
        cmd6[cmd6.index("--referer") + 1] == "https://oynatici.ornek.com/e/1")
kontrol("diger basliklar --add-header ile gider", "Origin:https://oynatici.ornek.com" in cmd6)
kontrol("Cookie basligi komut satirina YAZILMAZ", not any("gizli=1" in parca for parca in cmd6))
cikti = cmd6[cmd6.index("-o") + 1]
kontrol("sayfa basligi dosya adi olur, yasak karakter ve % kacisi",
        cikti.endswith('Film_ _Adı_ _ %%100 _.%(ext)s'), cikti)

print("7) Dusen kosudan sonra yedek plan (yedek_karari)")
# Olculdu: uzantinin yolladigi tarayici cerezleriyle YouTube 403 veriyor,
# cerezsiz ayni video iniyor. aria2c dis indirici de bazi CDN'lerde 22 ile dusuyor.
karar = ytdlp.VideoJob.yedek_karari
kontrol("aria2c dusunce kendi indiricisiyle tekrar",
        karar("ERROR: aria2c exited with code 22", True, True, False, False) == "aria2c")
kontrol("403 gelince cerezsiz tekrar",
        karar("unable to download video data: HTTP Error 403: Forbidden",
              True, True, True, False) == "cerezsiz")
kontrol("cerez yoksa 403 icin tekrar YOK",
        karar("HTTP Error 403: Forbidden", True, False, True, False) == "")
kontrol("kalici hatada tekrar YOK (bosuna bekleme)",
        karar("ERROR: Video unavailable", True, True, False, False) == "")
kontrol("her iki yedek denenmisse pes edilir",
        karar("HTTP Error 403", True, True, True, True) == "")

is_cerez = ytdlp.VideoJob(job_id="yt:9", url="https://ornek.com/izle", dest_dir=".",
                    cookie_file="C:/x/cerez.txt", user_agent="UA/1",
                    headers={"Referer": "https://ornek.com/"})
cerezli = is_cerez.build_cmd(None, False)
cerezsiz = is_cerez.build_cmd(None, False, cerezsiz=True)
kontrol("normal komutta cerez var", "--cookies" in cerezli)
kontrol("cerezsiz komutta cerez YOK", "--cookies" not in cerezsiz)
kontrol("cerezsiz komutta user-agent YOK", "--user-agent" not in cerezsiz)
kontrol("cerezsiz komutta referer YOK", "--referer" not in cerezsiz)
kontrol("cerezsiz komut yine de dogru adresi indiriyor",
        cerezsiz[-1] == "https://ornek.com/izle")

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
