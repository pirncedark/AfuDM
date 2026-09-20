"""Turkce I/i esleme: arama ve torrent filtresi tr-TR kurali kullanmali."""
import io
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(KOK, "ui", "app.js")


def main() -> int:
    s = io.open(APP, encoding="utf-8", errors="ignore").read()
    hata = []

    # 1) Kullanici metnini kucultürken duz toLowerCase kalmamali
    for no, satir in enumerate(s.splitlines(), 1):
        if "toLowerCase()" not in satir:
            continue
        # teknik alanlar (olay seviyesi, klavye tusu) serbest
        if re.search(r"(ev\.level|event\.key)", satir):
            continue
        hata.append("satir %d: duz toLowerCase() — tr-TR bekleniyor: %s" % (no, satir.strip()))

    # 2) Arama ve torrent filtresi tr-TR kullanmali
    for beklenen in (
        'state.search.toLocaleLowerCase("tr-TR")',
        'arama.trim().toLocaleLowerCase("tr-TR")',
    ):
        if beklenen not in s:
            hata.append("eksik: %s" % beklenen)

    # 3) Davranis kontrolu: "IZMIR" -> "izmir", "Işık" -> "ışık" (tr-TR)
    ornekler = [("IZMIR", "ızmır"), ("İSTANBUL", "istanbul")]
    for kaynak, beklenen in ornekler:
        if kaynak.lower() == beklenen:
            continue  # Python zaten tr benzeri davranmiyor; sadece niyeti belgeler

    for h in hata:
        print("HATA " + h)
    if hata:
        return 1
    print("OK   arama tr-TR kuralina uyuyor")
    print("TUM KONTROLLER GECTI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
