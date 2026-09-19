# -*- coding: utf-8 -*-
"""Motor yonetimi testleri — AG GEREKTIRMEZ (indirme YAPILMAZ).

Denetlenen: hangi motor zorunlu, eksik olan dogru bulunuyor mu, bozuk indirme
calisan kurulumu bozuyor mu, bilinmeyen motor reddediliyor mu.

"Indirme sirasinda hata cikarsa mevcut ffmpeg silinmis olmasin" kurali onemli:
kullanicinin calisan kurulumu, basarisiz bir guncelleme yuzunden bozulmamali.
"""
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core import engines  # noqa: E402

hatalar: list[str] = []


def kontrol(ad: str, kosul: bool, detay: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {detay}" if detay else ""))
    if not kosul:
        hatalar.append(ad)


print("1) Motor tanimlari")
kontrol("aria2c ZORUNLU", engines.MOTORLAR["aria2c"].zorunlu)
kontrol("yt-dlp istege bagli", not engines.MOTORLAR["yt-dlp"].zorunlu)
kontrol("ffmpeg istege bagli", not engines.MOTORLAR["ffmpeg"].zorunlu)
kontrol("her motorun adresi https", all(m.adres.startswith("https://")
                                        for m in engines.MOTORLAR.values()))
kontrol("her motorun ne ise yaradigi yazili", all(m.ne_icin for m in engines.MOTORLAR.values()))
kontrol("ffmpeg zip icinden alinir", engines.MOTORLAR["ffmpeg"].zip_icinde is not None)
kontrol("yt-dlp dogrudan exe", engines.MOTORLAR["yt-dlp"].zip_icinde is None)

print("2) Mevcut kurulum")
d = engines.durum()
kontrol("durum() her motoru bildiriyor", set(d) == set(engines.MOTORLAR), ", ".join(d))
if d["aria2c"]["var"]:
    kontrol("aria2c kurulu", True, f'{d["aria2c"]["boyut_mb"]} MB')
else:
    # Offline CI job'i motorlari INDIRMIYOR (indirme yalniz build job'inda var);
    # engine/aria2c.exe yoksa bu denetim ORTAMA bagli olur, atlanir.
    print("  [ATLANDI] engine/aria2c.exe yok (CI) — kurulu motor dogrulamasi atlandi")
for ad in ("yt-dlp", "ffmpeg"):
    if d[ad]["var"]:
        kontrol(f"{ad} kurulu", True, f'{d[ad]["boyut_mb"]} MB')
kontrol("var_mi() durum() ile tutarli",
        all(engines.var_mi(a) == d[a]["var"] for a in d))

print("2b) Motor nereden geliyor")
kontrol("her motorun kaynagi bildiriliyor",
        all(d[a]["kaynak"] in ("paket", "sistem", "yok") for a in d),
        ", ".join(f'{a}={d[a]["kaynak"]}' for a in d))
kontrol("paket kaynakli motor var_mi ile ayni",
        all((d[a]["kaynak"] == "paket") == d[a]["var"] for a in d))
kontrol("kullanilabilir = paket veya sistem",
        all(d[a]["kullanilabilir"] == (d[a]["kaynak"] != "yok") for a in d))
kontrol("sistem kaynaklinin yolu yazili",
        all(bool(d[a]["sistem_yolu"]) for a in d if d[a]["kaynak"] == "sistem"),
        "sistemden gelen yok" if not any(d[a]["kaynak"] == "sistem" for a in d) else "")
kontrol("paket icindekinin sistem yolu bos",
        all(not d[a]["sistem_yolu"] for a in d if d[a]["kaynak"] == "paket"))

print("3) Eksik bulma")
eksik = engines.eksikler()
kontrol("eksikler() yalniz istege baglilari sayar",
        all(not engines.MOTORLAR[a].zorunlu for a in eksik), ", ".join(eksik) or "(eksik yok)")
kontrol("kurulu motor eksik sayilmaz",
        all(not engines.var_mi(a) for a in eksik))

print("4) Hatali kullanim")
try:
    engines.indir("boyle-bir-motor-yok")
    kontrol("bilinmeyen motor reddedilir", False, "hata vermedi")
except ValueError:
    kontrol("bilinmeyen motor reddedilir", True)

print("5) Bozuk indirme calisan kurulumu bozmaz")
# _dogrula'yi hep False dondurecek sekilde degistir: indirme 'bozuk' sayilsin.
gercek_dogrula = engines._dogrula
gercek_adres = engines.MOTORLAR["yt-dlp"].adres
try:
    engines._dogrula = lambda _yol: False
    var_onceden = engines.var_mi("yt-dlp")
    boyut_onceden = engines.durum()["yt-dlp"]["boyut_mb"]
    # Ag'a cikmadan hata almak icin dosya adresine cevir (var olmayan yerel dosya)
    engines.MOTORLAR["yt-dlp"] = engines.Motor(
        **{**engines.MOTORLAR["yt-dlp"].__dict__,
           "adres": "https://127.0.0.1:1/olmayan.exe"}
    )
    try:
        engines.indir("yt-dlp")
        kontrol("basarisiz indirme hata veriyor", False, "sessizce gecti")
    except Exception:
        kontrol("basarisiz indirme hata veriyor", True)
    kontrol("mevcut yt-dlp SILINMEDI", engines.var_mi("yt-dlp") == var_onceden)
    kontrol("mevcut yt-dlp boyutu degismedi",
            engines.durum()["yt-dlp"]["boyut_mb"] == boyut_onceden)
finally:
    engines._dogrula = gercek_dogrula
    engines.MOTORLAR["yt-dlp"] = engines.Motor(
        **{**engines.MOTORLAR["yt-dlp"].__dict__, "adres": gercek_adres}
    )

print("6) Eksik motor aciklamasi")
kontrol("ffmpeg eksikse ne olacagi yazili", "mp3" in engines.EKSIK_NE_YAPAMAZ["ffmpeg"])
kontrol("yt-dlp eksikse ne olacagi yazili", bool(engines.EKSIK_NE_YAPAMAZ["yt-dlp"]))

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
