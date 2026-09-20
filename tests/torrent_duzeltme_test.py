# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

UI_JS = ROOT / "ui" / "app.js"
I18N_JS = ROOT / "ui" / "i18n.js"
DB_PY = ROOT / "core" / "db.py"
MANAGER_PY = ROOT / "core" / "manager.py"

fails: list[str] = []


def check(ad: str, kosul: bool, detay: str = "") -> None:
    durum = "GECTI" if kosul else "DUSTU"
    print(f"  [{durum}] {ad}" + (f" -- {detay}" if detay else ""))
    if not kosul:
        fails.append(ad + (f" ({detay})" if detay else ""))


content = UI_JS.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1) Modal Escape tus dinleyicisi (regex hatali negatif duzeltmesi)
# ---------------------------------------------------------------------------
print("1) Modal Escape tus dinleyicisi")
esc_match = re.search(r'event\.key === "Escape".*?closeVeil\(v\.id\)', content, re.DOTALL)
check("Escape tusu modal temizligi icin closeVeil cagirir", esc_match is not None)

# ---------------------------------------------------------------------------
# 2) Magnet metadata retry akisi
# ---------------------------------------------------------------------------
print("2) Magnet metadata retry akisi")
check("Metrik timeri icinde dosyalari yeniden cekme mantigi var",
      "retryCount <= 30" in content and "dosyalariCek()" in content)

# ---------------------------------------------------------------------------
# 3) Buyuk torrent dosya sayaci
# ---------------------------------------------------------------------------
print("3) Buyuk torrent dosya sayaci")
func_match = re.search(r'function torAgacDugumleriCiz.*?function', content, re.DOTALL)
kalan_count = func_match.group(0).count("ctx.kalan--") if func_match else 0
check("ctx.kalan-- sadece dosya satirinda (1 kez) gecmeli", kalan_count == 1)

# ---------------------------------------------------------------------------
# 4) Dosya adi arama ve Turkce karakter uyumu
# ---------------------------------------------------------------------------
print("4) Dosya adi arama ve Turkce karakter uyumu")
func_match = re.search(r'function torFiltrele\(.*?}', content, re.DOTALL)
body = func_match.group(0) if func_match else ""
check("Aramada toLocaleLowerCase(tr-TR) kullanilir ve toLowerCase kalmamistir",
      'toLocaleLowerCase("tr-TR")' in body and 'toLowerCase' not in body)

# ---------------------------------------------------------------------------
# 5) BULGU 1: Veritabani olay gunlukleri GID filtreleme
# ---------------------------------------------------------------------------
print("5) BULGU 1: Veritabani olay gunlukleri GID filtreleme")
from core.db import Store  # noqa: E402
store = Store(":memory:")
store.log("INFO", "global mesaj")
store.log("ERROR", "torrent 1 hatasi", gid="gid1")
store.log("INFO", "torrent 2 mesaji", gid="gid2")
store.log("ERROR", "torrent 1 baska hata", gid="gid1")

global_logs = store.recent_events(limit=10)
check("Global sorgu butun loglari getirir", len(global_logs) == 4)

gid1_logs = store.recent_events(limit=10, gid="gid1")
check("GID filtreli sorgu sadece o GID'i getirir",
      len(gid1_logs) == 2 and all(log["gid"] == "gid1" for log in gid1_logs))

gid2_logs = store.recent_events(limit=10, gid="gid2")
check("Farkli GID icin dogru kayitlar doner",
      len(gid2_logs) == 1 and gid2_logs[0]["gid"] == "gid2")

# ---------------------------------------------------------------------------
# 6) BULGU 1: manager.py store.log cagrilarinda gid parametresi
# ---------------------------------------------------------------------------
print("6) BULGU 1: manager.py store.log cagrilarinda gid parametresi")
mgr_code = MANAGER_PY.read_text(encoding="utf-8")
launch_has_gid = bool(re.search(r'attach_gid.*?\n\s*self\.store\.log\([^)]*gid=gid', mgr_code))
launch_tor_dir_gid = 'self.store.log("error", f"kayit dizini degistirilemedi: {exc}", gid=gid)' in mgr_code
launch_tor_sel_gid = 'self.store.log("error", f"dosya secimi uygulanamadi: {exc}", gid=gid)' in mgr_code
on_complete_has_gid = 'def _on_complete(self, title: str, size: int, gid: str = "")' in mgr_code and 'gid=gid' in mgr_code
other_gid_logs = 'is ayarlari canli degistirildi' in mgr_code and 'gid=gid' in mgr_code and 'adres yenilendi' in mgr_code
check("manager.py indirme ve torrent akisi store.log cagrilarinda gid parametresi gecirir",
      launch_has_gid and launch_tor_dir_gid and launch_tor_sel_gid and on_complete_has_gid and other_gid_logs)

# ---------------------------------------------------------------------------
# 7) BULGU 2: Metrik RPC hata yonetimi ve kullanici bildirimi
# ---------------------------------------------------------------------------
print("7) BULGU 2: Metrik RPC hata yonetimi ve kullanici bildirimi")
metrik_func = re.search(r'async function torMetrikleriGuncelle.*?function', content, re.DOTALL)
metrik_kod = metrik_func.group(0) if metrik_func else ""
ilk_hata_var = 't("tor.metricsInitialError")' in metrik_kod
ok_false_detay = 't("tor.metricsFailedDetail"' in metrik_kod and 't("tor.metricsFailed")' in metrik_kod
check("Metrik RPC ilk basarisizlikta kullaniciya hata gosterir (sessiz kalmaz)", ilk_hata_var)
check("Metrik RPC ok:false durumunda sunucu hata detayini gosterir", ok_false_detay)

# ---------------------------------------------------------------------------
# 8) BULGU 2: ui/i18n.js metrik hata anahtarlari TR ve EN
# ---------------------------------------------------------------------------
print("8) BULGU 2: ui/i18n.js metrik hata anahtarlari TR ve EN")
i18n_code = I18N_JS.read_text(encoding="utf-8")
gerekli_anahtarlar = ["tor.metricsInitialError", "tor.metricsFailed", "tor.metricsFailedDetail"]

def blok_ayikla(metin: str, baslangic: str) -> str:
    i = metin.index(baslangic) + len(baslangic) - 1
    derinlik = 0
    for j in range(i, len(metin)):
        if metin[j] == "{":
            derinlik += 1
        elif metin[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[i:j + 1]
    raise ValueError("kapanmayan blok: " + baslangic)

tr_metin = blok_ayikla(i18n_code, "  tr: {")
en_metin = blok_ayikla(i18n_code, "  en: {")
check("TR sozlugunde tum metrik hata anahtarlari mevcut",
      all(k in tr_metin for k in gerekli_anahtarlar))
check("EN sozlugunde tum metrik hata anahtarlari mevcut",
      all(k in en_metin for k in gerekli_anahtarlar))

# ---------------------------------------------------------------------------
# 9) BULGU 3: dosyalariCek in-flight korumasi
# ---------------------------------------------------------------------------
print("9) BULGU 3: dosyalariCek in-flight korumasi")
tor_veil_func = re.search(r'async function torrentVeilAc.*?/\* Torrent dosya agaci', content, re.DOTALL)
tor_veil_kod = tor_veil_func.group(0) if tor_veil_func else ""
check("dosyalariCek ayni anda birden fazla istegi engeller (in-flight kilidi)",
      "inFlight" in tor_veil_kod and "if (inFlight) return" in tor_veil_kod and "inFlight = false" in tor_veil_kod)

# ---------------------------------------------------------------------------
# 10) BULGU 3: Pencere kimligi (nonce) ve gecikmis RPC yaniti korumasi
# ---------------------------------------------------------------------------
print("10) BULGU 3: Pencere kimligi (nonce) ve gecikmis RPC yaniti korumasi")
nonce_tanimli = "nonce: 0" in content or "torState.nonce" in content
nonce_artan = "pencereNonce = ++torState.nonce" in tor_veil_kod or "torState.nonce" in tor_veil_kod
nonce_denetim = "torState.nonce !== pencereNonce" in tor_veil_kod
acik_denetim = "!torState.acik" in tor_veil_kod
close_veil_temizlik = 'if (id === "torrentVeil")' in content and 'torState.acik = false' in content
check("Pencere acilisinda tekil nonce olusturulur ve geciken yanitlar engellenir",
      nonce_tanimli and nonce_artan and nonce_denetim and acik_denetim and close_veil_temizlik)

print()
if fails:
    print(f"BASARISIZ ({len(fails)} test dustu):", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
