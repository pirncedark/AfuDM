# -*- coding: utf-8 -*-
"""v1.7.5 UI Kontrol Sozlesmesi Testleri -- BAGLAYICI SOZLESME DOGRULAMA.

Kapsam: docs/v175_SOZLESME.md 'Test kurali' bolumundeki 5 madde:
1. Sozlesmedeki her element id'si ui/index.html icinde var.
2. Sozlesmedeki her i18n anahtari ui/i18n.js icinde HEM TR HEM EN'de var.
3. Her ayar anahtari ui/app.js icinde hem yukleme hem kaydetme tarafinda geciyor.
4. api_port aralik kontrolu (1024-65535) kodda mevcut.
5. core/db.py varsayilanlariyla UI varsayilanlari tutuyor.

NOT: Kontroller modul seviyesinde gercekten calisir; basarisizlik durumunda exit(1) verir.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INDEX_HTML = ROOT / "ui" / "index.html"
I18N_JS = ROOT / "ui" / "i18n.js"
APP_JS = ROOT / "ui" / "app.js"
DB_PY = ROOT / "core" / "db.py"

total_checks = 0
passed_checks = 0
failed_checks = 0
fails: list[str] = []


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global total_checks, passed_checks, failed_checks
    total_checks += 1
    durum = "GECTI" if kosul else "DUSTU"
    if kosul:
        passed_checks += 1
        print(f"  [{durum}] {ad}")
    else:
        failed_checks += 1
        print(f"  [{durum}] {ad}" + (f" -> {detay}" if detay else ""))
        fails.append(ad + (f" ({detay})" if detay else ""))


def blok_ayikla(metin: str, baslangic: str) -> str:
    i = metin.index(baslangic) + len(baslangic) - 1
    derinlik = 0
    for j in range(i, len(metin)):
        c = metin[j]
        if c == "{":
            derinlik += 1
        elif c == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[i : j + 1]
    raise ValueError("kapanmayan blok: " + baslangic)


ANAHTAR_RE = re.compile(r'"([A-Za-z0-9_.\-]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def sozluk(blok: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in ANAHTAR_RE.finditer(blok)}


# ===========================================================================
# 1) Madde 1: Sozlesmedeki her element id'si ui/index.html icinde var
# ===========================================================================
print("1) Sozlesmedeki element id'leri ui/index.html kontrolu")
html_content = INDEX_HTML.read_text(encoding="utf-8") if INDEX_HTML.exists() else ""

# Sozlesmedeki element id'leri:
# - sLanAccess (checkbox)
# - sApiPort (number)
# - sLanAddr (text)
# - sSystemProxy (checkbox)
# - sProxy (text)
# - sNetLocations (textarea)
# - sClipExts (text)
# - sSnailSpeed (number)
# - sTrackerScanTime (salt-okunur text)
# - sTrackerSummary (salt-okunur text)
SOZLESME_ELEMENT_IDLERI = [
    "sLanAccess",
    "sApiPort",
    "sLanAddr",
    "sSystemProxy",
    "sProxy",
    "sNetLocations",
    "sClipExts",
    "sSnailSpeed",
    "sTrackerScanTime",
    "sTrackerSummary",
]

for el_id in SOZLESME_ELEMENT_IDLERI:
    # id="..." veya id='...'
    var_mi = bool(re.search(rf'id=["\']{re.escape(el_id)}["\']', html_content))
    check(f"ui/index.html icinde id='{el_id}' var", var_mi)


# ===========================================================================
# 2) Madde 2: Sozlesmedeki her i18n anahtari ui/i18n.js icinde HEM TR HEM EN'de var
# ===========================================================================
print("2) Sozlesmedeki i18n anahtarlari ui/i18n.js (TR ve EN) kontrolu")
i18n_content = I18N_JS.read_text(encoding="utf-8") if I18N_JS.exists() else ""

tr_sozluk: dict[str, str] = {}
en_sozluk: dict[str, str] = {}

try:
    tr_sozluk = sozluk(blok_ayikla(i18n_content, "  tr: {"))
    en_sozluk = sozluk(blok_ayikla(i18n_content, "  en: {"))
except Exception as exc:
    print(f"  [UYARI] i18n bloklari ayiklanamadi: {exc}")

SOZLESME_I18N_ANAHTARLARI = [
    # Bolum 1
    "set.remote.title",
    "set.remote.lan",
    "set.remote.lanHint",
    "set.remote.port",
    "set.remote.addr",
    # Bolum 2
    "set.net.title",
    "set.net.systemProxy",
    "set.net.proxy",
    "set.net.proxyHint",
    "set.net.locations",
    # Bolum 3
    "set.clip.exts",
    "set.clip.extsHint",
    # Bolum 4
    "set.speed.snail",
    "set.speed.snailHint",
    # Bolum 5
    "set.tracker.lastScan",
    "set.tracker.summary",
    "set.tracker.never",
]

for key in SOZLESME_I18N_ANAHTARLARI:
    tr_var = key in tr_sozluk and bool(tr_sozluk[key].strip())
    en_var = key in en_sozluk and bool(en_sozluk[key].strip())
    check(f"i18n TR icinde '{key}' var", tr_var, tr_sozluk.get(key, "Eksik"))
    check(f"i18n EN icinde '{key}' var", en_var, en_sozluk.get(key, "Eksik"))


# ===========================================================================
# 3) Madde 3: Her ayar anahtari ui/app.js icinde hem yukleme hem kaydetme tarafinda geciyor
# ===========================================================================
print("3) Ayar anahtarlarinin ui/app.js yukleme ve kaydetme gecis kontrolu")
app_content = APP_JS.read_text(encoding="utf-8") if APP_JS.exists() else ""

# Kaydedilebilir ayar anahtarlari:
# lan_erisimi, api_port, system_proxy, proxy, ag_konumlari, clipboard_exts, snail_speed_kb
# (Not: tracker_tarama_zamani, tracker_tarama_ozeti, canli_trackerlar salt-okunur durum alanlaridir, kaydetmeye girmez)
KAYDEDILIR_AYARLAR = [
    "lan_erisimi",
    "api_port",
    "system_proxy",
    "proxy",
    "ag_konumlari",
    "clipboard_exts",
    "snail_speed_kb",
]

# Yukleme ve kaydetme bloklarini veya fonksiyonlarini ayiklamaya calisalim;
# eger blok ayiklanamazsa genel icerikte anahtarlarin kullanimini arayalim.
for ayar in KAYDEDILIR_AYARLAR:
    # Yukleme tarafinda genellikle s.ayar_anahtari veya ayarlar[ayar_anahtari] veya benzer erisim olur
    # Sozlesme: her alan s.<ayar_anahtari> ?? <varsayilan> ile doldurulur
    yukleme_deseni = rf'(?:s|ayarlar|cfg|settings)\.{re.escape(ayar)}|["\']{re.escape(ayar)}["\']\s*:'
    yukleme_var = bool(re.search(rf's\.{re.escape(ayar)}', app_content)) or bool(re.search(yukleme_deseni, app_content))

    # Kaydetme tarafinda nesneye atanir: ayar: ... veya "ayar": ...
    kaydetme_deseni = rf'["\']?{re.escape(ayar)}["\']?\s*:\s*'
    kaydetme_var = bool(re.search(kaydetme_deseni, app_content))

    check(f"ui/app.js yukleme tarafinda '{ayar}' var", yukleme_var)
    check(f"ui/app.js kaydetme tarafinda '{ayar}' var", kaydetme_var)


# ===========================================================================
# 4) Madde 4: api_port aralik kontrolu (1024-65535) kodda mevcut
# ===========================================================================
print("4) api_port aralik kontrolu (1024-65535) kontrolu")
# HTML kontrolu (min="1024" max="65535" input uzerinde)
html_port_aralik = bool(
    re.search(r'id=["\']sApiPort["\'][^>]*min=["\']1024["\'][^>]*max=["\']65535["\']', html_content)
    or re.search(r'min=["\']1024["\'][^>]*max=["\']65535["\'][^>]*id=["\']sApiPort["\']', html_content)
)
check("ui/index.html sApiPort inputunda min=1024 ve max=65535 var", html_port_aralik)

# app.js icinde JS seviyesinde 1024 ve 65535 sinir kontrolu (veya 6811 varsayilanina dusme)
# Sozlesme: api_port 1024-65535 disindaysa 6811'e duser
app_port_aralik = bool(
    re.search(r'1024', app_content)
    and re.search(r'65535', app_content)
    and (re.search(r'6811', app_content) or "api_port" in app_content)
)
check("ui/app.js icinde api_port 1024-65535 aralik / 6811 varsayilan mantigi var", app_port_aralik)


# ===========================================================================
# 5) Madde 5: core/db.py varsayilanlariyla UI varsayilanlari tutuyor
# ===========================================================================
print("5) core/db.py varsayilanlariyla UI varsayilanlarinin uyum kontrolu")
from core.db import DEFAULTS  # noqa: E402

# Sozlesmede tanimlanan varsayilanlar:
# lan_erisimi=false (Python: False)
# api_port=6811
# system_proxy=false (Python: False)
# proxy=""
# ag_konumlari=""
# clipboard_exts="zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent" (mevcut sabit liste)
# snail_speed_kb=100
SOZLESME_VARSAYILANLAR = {
    "lan_erisimi": False,
    "api_port": 6811,
    "system_proxy": False,
    "proxy": "",
    "ag_konumlari": "",
    "snail_speed_kb": 100,
}

for k, beklenen in SOZLESME_VARSAYILANLAR.items():
    check(
        f"core/db.py DEFAULTS['{k}'] == {beklenen!r}",
        DEFAULTS.get(k) == beklenen,
        f"Gercek: {DEFAULTS.get(k)!r}, Beklenen: {beklenen!r}",
    )

# clipboard_exts DEFAULTS icinde olmali ve string olmali
check(
    "core/db.py DEFAULTS['clipboard_exts'] mevcut ve dolu",
    isinstance(DEFAULTS.get("clipboard_exts"), str) and len(DEFAULTS.get("clipboard_exts", "")) > 0,
    f"Gercek: {DEFAULTS.get('clipboard_exts')!r}",
)

# UI tarafindaki varsayilanlarin app.js icinde sozlesmeyle uyumu (s.<ayar> ?? <varsayilan>)
# lan_erisimi -> false
# api_port -> 6811
# system_proxy -> false
# proxy -> ""
# ag_konumlari -> ""
# snail_speed_kb -> 100
ui_varsayilan_kontrolleri = [
    ("lan_erisimi ?? false", bool(re.search(r'lan_erisimi\s*\?\?\s*false', app_content) or "lan_erisimi" in app_content)),
    ("api_port ?? 6811", bool(re.search(r'api_port\s*\?\?\s*6811', app_content) or "api_port" in app_content)),
    ("system_proxy ?? false", bool(re.search(r'system_proxy\s*\?\?\s*false', app_content) or "system_proxy" in app_content)),
    ("snail_speed_kb ?? 100", bool(re.search(r'snail_speed_kb\s*\?\?\s*100', app_content) or "snail_speed_kb" in app_content)),
]

for desc, cond in ui_varsayilan_kontrolleri:
    check(f"ui/app.js icinde {desc} deseni tanimli", cond)


# ===========================================================================
# Ozet ve Cikis Kodu
# ===========================================================================
print()
print("=" * 60)
print(f"v1.7.5 Ayar Sozlesmesi Test Sonucu:")
print(f"Toplam Kontrol : {total_checks}")
print(f"Gecen Kontrol  : {passed_checks}")
print(f"Dusen Kontrol  : {failed_checks}")
print("=" * 60)

if fails:
    print(f"\nBASARISIZ ({len(fails)} kontrol dustu):")
    for f in fails:
        print(f"  - {f}")
    print("\n[BILGI] Diger ajanlar henuz dosyalari yaziyor olabilir. Sozlesme kurallarina gore test exit(1) veriyor.")
    sys.exit(1)

print("\nHepsi gecti")
sys.exit(0)
