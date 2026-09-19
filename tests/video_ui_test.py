# -*- coding: utf-8 -*-
"""Video Pro arayuz sozlesmesi — ag ve pencere gerektirmez."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
I18N = (ROOT / "ui" / "i18n.js").read_text(encoding="utf-8")

ALANLAR = {
    "video_altyazi_diller": ("sVideoAltyaziDiller", "kayVideoAltyaziDiller", "altyazi_diller"),
    "video_oto_altyazi": ("sVideoOtoAltyazi", "kayVideoOtoAltyazi", "oto_altyazi"),
    "video_altyazi_goem": ("sVideoAltyaziGoem", "kayVideoAltyaziGoem", "altyazi_goem"),
    "video_kucuk_resim": ("sVideoKucukResim", "kayVideoKucukResim", "kucuk_resim"),
    "video_ustveri_goem": ("sVideoUstveriGoem", "kayVideoUstveriGoem", "ustveri_goem"),
    "video_bolumler": ("sVideoBolumler", "kayVideoBolumler", "bolumler"),
    "video_sponsorblock": ("sVideoSponsorblock", "kayVideoSponsorblock", "sponsorblock"),
    "video_bolum_araligi": ("sVideoBolumAraligi", "kayVideoBolumAraligi", "bolum_araligi"),
    "video_kapsayici": ("sVideoKapsayici", "kayVideoKapsayici", "kapsayici"),
    "video_ses_formati": ("sVideoSesFormati", "kayVideoSesFormati", "ses_formati"),
    "video_dosya_sablonu": ("sVideoDosyaSablonu", "kayVideoDosyaSablonu", "dosya_sablonu"),
    "video_tarayici_cerezi": ("sVideoTarayiciCerezi", "kayVideoTarayiciCerezi", "tarayici_cerezi"),
}


def blok(metin: str, baslangic: str) -> str:
    i = metin.index(baslangic) + len(baslangic) - 1
    derinlik = 0
    for j in range(i, len(metin)):
        if metin[j] == "{":
            derinlik += 1
        elif metin[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[i:j + 1]
    raise AssertionError(f"kapanmayan blok: {baslangic}")


def anahtarlar(dil: str) -> set[str]:
    return set(re.findall(r'"([A-Za-z0-9_.-]+)"\s*:', blok(I18N, f"{dil}: {{")))


def kontrol(ad: str, kosul: bool, detay: str = "") -> bool:
    print(f"  [{'GECTI' if kosul else 'BASARISIZ'}] {ad}" + (f" — {detay}" if detay else ""))
    return kosul


def main() -> int:
    basarisiz = []
    tr, en = anahtarlar("tr"), anahtarlar("en")
    vid = set(re.findall(r'data-i18n(?:-ph)?="(vid\.[^"]+)"', HTML))
    if not kontrol("vid anahtarlari tr ve en'de var", vid <= tr and vid <= en,
                   ", ".join(sorted(vid - tr | vid - en))):
        basarisiz.append("i18n")

    for ayar, (ayar_id, is_id, alan) in ALANLAR.items():
        var = ayar_id in HTML and is_id in HTML and f'$("{ayar_id}")' in APP and f'$("{is_id}")' in APP
        if not kontrol(f"{ayar}: ayar ve is alani okunuyor", var):
            basarisiz.append(ayar)

    bos_metinseldir = all(
        f'{alan}: $("{is_id}").value.trim()' in APP
        for _, (_, is_id, alan) in ALANLAR.items()
        if alan not in {"oto_altyazi", "altyazi_goem", "ustveri_goem"}
    )
    bos_onay_kutusudur = all(
        f'{alan}: $("{is_id}").checked ? true : ""' in APP
        for _, (_, is_id, alan) in ALANLAR.items()
        if alan in {"oto_altyazi", "altyazi_goem", "ustveri_goem"}
    )
    if not kontrol("bos gelismis alanlar bos deger gonderir", bos_metinseldir and bos_onay_kutusudur):
        basarisiz.append("bos-deger")

    if basarisiz:
        print("BASARISIZ:", ", ".join(dict.fromkeys(basarisiz)))
        return 1
    print("Hepsi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
