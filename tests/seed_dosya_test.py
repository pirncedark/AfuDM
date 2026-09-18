# -*- coding: utf-8 -*-
"""Seed listesi dosya yonetimi testleri — AG GEREKTIRMEZ, saniyeler surer.

NEDEN: Kullanici seed listesi (.txt) eklemek icin `AfuDM/trackers/` klasorune
elle kopyalamak zorundaydi; arayuzde yeri yoktu. Bu modul Ayarlar'daki
"Seed listeleri" bolumunun arkasindaki dosya islerini dogrular:
ekle / listele / sil, tekrar eleme ve yol kacisi korumasi.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import tracker_saglik as ts  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(f"  [{'GECTI' if kosul else 'DUSTU'}] {ad}" + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


def patlar(islem) -> bool:
    """Islem ValueError atiyor mu? (atmasi BEKLENEN durumlar icin)"""
    try:
        islem()
    except ValueError:
        return True
    except Exception:
        return False
    return False


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    kok = Path(gecici)
    ts.KLASOR = kok / "trackers"
    kaynak = kok / "kaynak"
    kaynak.mkdir()

    print("1) Bos klasor")
    check("dosya yokken bos liste", ts.dosyalar() == [], str(ts.dosyalar()))
    check("listeleme klasoru olusturur", ts.KLASOR.is_dir())
    check("BENI_OKU listede gorunmez", not any(d["ad"] == "BENI_OKU.txt" for d in ts.dosyalar()))

    print("2) Dosya ekleme")
    (kaynak / "seed.txt").write_text(
        "udp://bir.ornek:1337/announce\n"
        "http://iki.ornek/announce\n"
        "bu satir adres degil\n"
        "udp://bir.ornek:1337/announce\n",  # tekrar
        encoding="utf-8")
    sonuc = ts.dosya_ekle(str(kaynak / "seed.txt"))
    check("eklenen dosyanin adi donuyor", sonuc["ad"] == "seed.txt", str(sonuc))
    check("gecerli adresler sayildi (tekrar ve cop haric)", sonuc["sayi"] == 2, str(sonuc))
    check("dosya trackers klasorune kopyalandi", (ts.KLASOR / "seed.txt").is_file())
    check("kaynak dosya yerinde kaldi", (kaynak / "seed.txt").is_file())

    liste = ts.dosyalar()
    check("listede tek dosya var", len(liste) == 1, str(liste))
    check("listede adres sayisi dogru", liste[0]["sayi"] == 2, str(liste))

    okunan = ts.klasorden_oku()
    check("eklenen adresler taramaya giriyor", len(okunan) == 2, str(okunan))

    print("3) Ayni icerik iki kez eklenmez")
    tekrar = ts.dosya_ekle(str(kaynak / "seed.txt"))
    check("zaten ekli isareti donuyor", tekrar.get("zaten") is True, str(tekrar))
    check("ikinci kopya olusmadi", len(ts.dosyalar()) == 1, str(ts.dosyalar()))

    print("4) Ayni ad, farkli icerik -> yeni ad")
    (kaynak / "seed.txt").write_text("udp://uc.ornek:1337/announce\n", encoding="utf-8")
    ikinci = ts.dosya_ekle(str(kaynak / "seed.txt"))
    check("cakisan ad degistirildi", ikinci["ad"] == "seed-2.txt", str(ikinci))
    check("iki dosya da duruyor", len(ts.dosyalar()) == 2, str(ts.dosyalar()))
    check("adresler birlesti", len(ts.klasorden_oku()) == 3, str(ts.klasorden_oku()))

    print("5) Gecersiz eklemeler")
    (kaynak / "bos.txt").write_text("hic adres yok\nsadece yazi\n", encoding="utf-8")
    (kaynak / "resim.png").write_bytes(b"\x89PNG")
    check("adres icermeyen dosya reddedilir",
          patlar(lambda: ts.dosya_ekle(str(kaynak / "bos.txt"))))
    check("txt olmayan dosya reddedilir",
          patlar(lambda: ts.dosya_ekle(str(kaynak / "resim.png"))))
    check("olmayan dosya reddedilir",
          patlar(lambda: ts.dosya_ekle(str(kaynak / "yok.txt"))))
    check("gecersiz eklemeler klasoru kirletmedi", len(ts.dosyalar()) == 2, str(ts.dosyalar()))

    print("6) Silme")
    ts.dosya_sil("seed-2.txt")
    check("dosya silindi", not (ts.KLASOR / "seed-2.txt").exists())
    check("listede bir dosya kaldi", len(ts.dosyalar()) == 1, str(ts.dosyalar()))

    print("7) Silme korumalari")
    disarda = kok / "silinmemeli.txt"
    disarda.write_text("udp://dis.ornek:1337/announce\n", encoding="utf-8")
    check("yol kacisi (..) reddedilir",
          patlar(lambda: ts.dosya_sil("../silinmemeli.txt")))
    check("klasor disindaki dosya duruyor", disarda.is_file())
    check("mutlak yol reddedilir", patlar(lambda: ts.dosya_sil(str(disarda))))
    check("BENI_OKU silinemez", patlar(lambda: ts.dosya_sil("BENI_OKU.txt")))
    check("aciklama dosyasi duruyor", (ts.KLASOR / "BENI_OKU.txt").is_file())
    check("olmayan dosya silinmez", patlar(lambda: ts.dosya_sil("yok.txt")))
    check("txt olmayan ad reddedilir", patlar(lambda: ts.dosya_sil("bir.exe")))
    check("kalan dosya hala yerinde", (ts.KLASOR / "seed.txt").is_file())

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
