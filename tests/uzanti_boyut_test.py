"""Uzantinin BUYUK dosya esigi: yakalama ile suzgec AYNI sayiyi kullanmali.

AG GEREKTIRMEZ, Chrome ACMAZ. Kusur sinifi (2026-09-19): esik iki yerde ayri
yazilirsa dosya kaydedilir ama listede gosterilmez (ya da tersi) — belirti
"400 MB'lik film yine cikmiyor" olur ve kok neden gorunmez.
"""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
hatalar = []


def kontrol(ad, sart, ek=""):
    print(("  [GECTI] " if sart else "  [DUSTU] ") + ad + (f" — {ek}" if ek else ""))
    if not sart:
        hatalar.append(ad)


bg = (KOK / "extension/background.js").read_text(encoding="utf-8")

print("1) esik tek yerde tanimli")
tanim = re.findall(r"const BUYUK_DOSYA = ([0-9* ]+);", bg)
kontrol("BUYUK_DOSYA bir kez tanimli", len(tanim) == 1, str(tanim))
deger = eval(tanim[0]) if tanim else 0
kontrol("esik 400 MB", deger == 400 * 1024 * 1024, f"{deger / 1048576:.0f} MB")

print("2) hem yakalamada hem suzgecte kullaniliyor")
kullanim = bg.count("BUYUK_DOSYA")
kontrol("en az uc yerde geciyor (tanim + yakalama + suzgec)", kullanim >= 3, f"{kullanim} kez")
kontrol("yakalama: tur yoksa boyuta duser", 'boyut >= BUYUK_DOSYA ? "file"' in bg)
kontrol("suzgec: boyuta gore gecirir", "(s.boyut || 0) >= BUYUK_DOSYA" in bg)

print("3) kucuk dosya esigi bozulmadi")
kontrol("arayuz sesi esigi 256 KB duruyor", "boyut < 256 * 1024" in bg)
kontrol("ses dosyasi esigi 1 MB duruyor", "const KUCUK = 1024 * 1024;" in bg)
kontrol("buyuk esik kucuk esikten buyuk", deger > 1024 * 1024)

print("4) surum yukseltildi")
man = (KOK / "extension/manifest.json").read_text(encoding="utf-8")
surum = re.search(r'"version":\s*"([\d.]+)"', man).group(1)
kontrol("surum 1.2.0'dan ileri", tuple(map(int, surum.split("."))) > (1, 2, 0), surum)

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
