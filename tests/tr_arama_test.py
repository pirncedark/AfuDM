# -*- coding: utf-8 -*-
"""Turkce I/i esleme sozlesmesi — arama kutulari tr-TR kuralina uymali.

Gerekce (denetim bulgusu A7): JavaScript'in ciplak `toLowerCase()` metodu
"I" harfini "i"ye cevirir. Turkce'de "I"nin kucugu "ı", "İ"nin kucugu "i"dir.
Bu yuzden "ILAHI.mp3" dosyasi "ilahi" aramasinda CIKAR ama "ıvır" gibi bir
sorgu yanlis eslesir; daha kotusu "İSTANBUL" araninca "istanbul" bulunamaz.
Torrent dosya filtresi bunu `toLocaleLowerCase("tr-TR")` ile dogru yapiyor;
bu test o davranisin geri alinmasini ENGELLER.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

APP_JS = ROOT / "ui" / "app.js"

total_checks = 0
passed_checks = 0
fails: list[str] = []


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global total_checks, passed_checks
    total_checks += 1
    if kosul:
        passed_checks += 1
        print(f"  [GECTI] {ad}")
    else:
        print(f"  [DUSTU] {ad}" + (f" -> {detay}" if detay else ""))
        fails.append(ad + (f" ({detay})" if detay else ""))


def govde_al(metin: str, imza: str) -> str:
    """Bir fonksiyonun govdesini suslu parantez sayarak ayikla."""
    i = metin.index(imza)
    derinlik = 0
    basladi = False
    for j in range(i, len(metin)):
        if metin[j] == "{":
            derinlik += 1
            basladi = True
        elif metin[j] == "}":
            derinlik -= 1
            if basladi and derinlik == 0:
                return metin[i : j + 1]
    raise ValueError("kapanmayan fonksiyon: " + imza)


def python_esleme_kurali() -> None:
    """Beklentiyi once Python'da somutla: tr-TR ile duz kucultme AYNI DEGIL."""
    print("A) Turkce I/i kurali — beklenti somut mu")
    # Python'un casefold'u da "I" -> "i" yapar; yani ciplak kucultme Turkce
    # icin YANLIS. Test bu farkin gercekten var oldugunu gosterir.
    check("A1 'I' duz kucultmede 'i' olur (Turkce'de YANLIS)", "I".lower() == "i")
    check("A2 'İ' duz kucultmede 'i̇' olur (nokta artakalir)", len("İ".lower()) == 2)


def torrent_filtresi_tr_kullanir() -> None:
    print("\nB) ui/app.js torrent dosya filtresi")
    js = APP_JS.read_text(encoding="utf-8")
    govde = govde_al(js, "function torFiltrele(")

    kucultmeler = re.findall(r"\.toLocaleLowerCase\(\s*[\"']tr-TR[\"']\s*\)", govde)
    check("B1 torFiltrele tr-TR ile kuculuyor", len(kucultmeler) >= 3,
          f"bulunan: {len(kucultmeler)}")

    ciplak = re.findall(r"\.toLowerCase\(\s*\)", govde)
    check("B2 torFiltrele icinde ciplak toLowerCase() YOK", not ciplak,
          f"bulunan: {len(ciplak)}")

    check("B3 hem ad hem yol filtreleniyor", "d.ad" in govde and "d.yol" in govde)


if __name__ == "__main__":
    print("AfuDM — Turkce arama esleme testi\n")
    python_esleme_kurali()
    torrent_filtresi_tr_kullanir()
    print(f"\n{'=' * 52}\nSONUC: {passed_checks}/{total_checks} test gecti")
    if fails:
        print("Gecmeyenler: " + ", ".join(fails))
        raise SystemExit(1)
