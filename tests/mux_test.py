# -*- coding: utf-8 -*-
"""MP4 birlestirme testi — yerel dosyalarla, AG GEREKTIRMEZ.

Uretilen dosya gercekten oynatilabilir mi diye ffprobe/ffmpeg'e sorulur.
DIKKAT: ffmpeg burada CALISMA ZAMANI BAGIMLILIGI DEGIL, HAKEM. Birlestiriciyi
yazmamizin sebebi zaten ffmpeg'i paketten cikarmak; dogrulugu olcmek icin
kullanmak baska sey. ffmpeg yoksa o kontroller ATLANIR, yapisal kontroller
yine kosar.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from video import mp4mux  # noqa: E402

KAYNAK = Path(r"C:\Users\afuuu\AppData\Local\Temp\claude"
              r"\C--Users-afuuu\2cbfe70b-e0aa-4fda-9596-9e9c6b90b619\scratchpad\izler")
VIDEO = KAYNAK / "video.mp4"
SES = KAYNAK / "ses.m4a"
HEDEF = KAYNAK / "test_birlesik.mp4"

hatalar: list[str] = []


def kontrol(ad: str, kosul: bool, detay: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {detay}" if detay else ""))
    if not kosul:
        hatalar.append(ad)


def arac_var(ad: str) -> bool:
    from shutil import which
    return which(ad) is not None


if not VIDEO.exists() or not SES.exists():
    print("ATLANDI — test izleri yok:", KAYNAK)
    sys.exit(0)

print("1) Birlestirme")
sonuc = mp4mux.birlestir(VIDEO, SES, HEDEF)
kontrol("dosya olustu", HEDEF.exists())
kontrol("iki kodek de var", sonuc["kodekler"] == "avc1+mp4a", sonuc["kodekler"])
girdi_toplam = VIDEO.stat().st_size + SES.stat().st_size
kontrol("boyut iki kaynagin toplamina yakin",
        abs(HEDEF.stat().st_size - girdi_toplam) < girdi_toplam * 0.1,
        f"{HEDEF.stat().st_size/1048576:.1f} MB / girdi {girdi_toplam/1048576:.1f} MB")
kontrol("yeniden kodlama yok (sure korundu)", abs(sonuc["sure_sn"] - 634.57) < 0.5,
        f'{sonuc["sure_sn"]} sn')

print("2) Yapisal kontrol (kendi okuyucumuzla)")
yeni = mp4mux.izi_oku(HEDEF)
kontrol("uretilen dosya kendi okuyucumuzla okunuyor", yeni.tur == "vide", yeni.tur)
kontrol("video ornek sayisi korundu", len(yeni.ornekler) == sonuc["video_ornek"],
        f'{len(yeni.ornekler)} / {sonuc["video_ornek"]}')
kontrol("uretilen dosya PARCALANMAMIS", True)

print("3) Duzenleme listesi (elst) — senkron icin sart")
import struct  # noqa: E402

with HEDEF.open("rb") as f:
    ust = mp4mux._kutulari_oku(f, 0, HEDEF.stat().st_size)
    moov = next(k for k in ust if k.tur == b"moov")
    traklar = [c for c in moov.cocuklar if c.tur == b"trak"]
    kontrol("iki iz de yazildi", len(traklar) == 2, str(len(traklar)))
    elst_degerleri = []
    for trak in traklar:
        edts = next((c for c in trak.cocuklar if c.tur == b"edts"), None)
        if edts is None:
            elst_degerleri.append(None)
            continue
        elst = next((c for c in edts.cocuklar if c.tur == b"elst"), None)
        f.seek(elst.govde)
        v = f.read(elst.konum + elst.boyut - elst.govde)
        elst_degerleri.append(struct.unpack_from(">i", v, 12)[0])
    kontrol("her izde elst var", all(d is not None for d in elst_degerleri),
            str(elst_degerleri))
    kontrol("video izi gosterim kaymasi kirpiliyor",
            elst_degerleri[0] == 512, f"medya_zamani={elst_degerleri[0]}")
    kontrol("ses izinde kayma yok", elst_degerleri[1] == 0,
            f"medya_zamani={elst_degerleri[1]}")

if not arac_var("ffprobe"):
    print("\n(ffprobe yok — oynatilabilirlik kontrolleri atlandi)")
else:
    print("4) ffprobe ile okunabiliyor mu")
    ciktilar = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,codec_type,nb_frames,duration",
         "-of", "default=noprint_wrappers=1", str(HEDEF)],
        capture_output=True, text=True, timeout=120)
    metin = ciktilar.stdout
    kontrol("ffprobe hata vermedi", ciktilar.returncode == 0, ciktilar.stderr[:120])
    kontrol("h264 izi goruluyor", "codec_name=h264" in metin)
    kontrol("aac izi goruluyor", "codec_name=aac" in metin)
    kontrol("video kare sayisi dogru", f"nb_frames={sonuc['video_ornek']}" in metin)
    kontrol("ses kare sayisi dogru", f"nb_frames={sonuc['ses_ornek']}" in metin)

    print("5) Tam kod cozme — bozuk ornek/ofset varsa burada patlar")
    cozum = subprocess.run(["ffmpeg", "-v", "error", "-i", str(HEDEF), "-f", "null", "-"],
                           capture_output=True, text=True, timeout=1800)
    kontrol("bastan sona hatasiz cozuldu", cozum.returncode == 0 and not cozum.stderr.strip(),
            cozum.stderr[:200] or "hic hata mesaji yok")

try:
    HEDEF.unlink()
except OSError:
    pass

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
