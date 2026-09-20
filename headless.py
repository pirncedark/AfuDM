# -*- coding: utf-8 -*-
"""AfuDM arayuzsuz servis girisi (headless) — v2.1.

    python headless.py          (veya: afuadm server start)

BU DOSYA `webview` MODULUNU IMPORT ETMEZ. pywebview kurulu olmayan ya da
masaustu oturumu bulunmayan bir makinede de calisir: yalnizca indirme motoru
(Manager), ortak servis katmani (core/servis.py) ve yonetim sunucusu
(api/web.py) ayaga kalkar.

Ayni klasorde bir masaustu AfuDM aciksa BU SUREC ACILMAZ — iki surec ayni
SQLite dosyasina ve ayni aria2 oturumuna asilmasin diye (bkz. core/ornek.py).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.server import LocalAPI  # noqa: E402
from core import lang, ornek, paths  # noqa: E402
from core.manager import Manager  # noqa: E402
from core.servis import AfuDMServis  # noqa: E402

VARSAYILAN_API_PORT = 6811   # uzantinin da ilk denedigi port


def calistir() -> int:
    """UI OLMADAN calisan servis. `afuadm server start` bunu cagirir.

    pywebview/tepsi/pencere YOK: yalnizca Manager + servis katmani + yonetim
    sunucusu. Ayni klasorde bir masaustu AfuDM aciksa ACILMAZ (bkz. core/ornek).
    """
    paths.ensure_dirs()
    kilit = ornek.OrnekKilidi(ornek.KIP_HEADLESS)
    alindi, rapor = kilit.al()
    if not alindi:
        var = rapor.get("mevcut") or {}
        print("HATA: %s (pid %s, kip %s)"
              % (lang.t(rapor["mesaj_anahtari"], "auto"),
                 var.get("pid"), var.get("kip")))
        return 4
    if not paths.ARIA2C.exists():
        kilit.birak()
        print(f"HATA: motor bulunamadi -> {paths.ARIA2C}")
        return 2

    manager = Manager()
    try:
        manager.start()
    except Exception as exc:
        kilit.birak()
        print(f"HATA: aria2 baslatilamadi: {exc}")
        return 3

    servis = AfuDMServis(manager, kip=ornek.KIP_HEADLESS)
    from api.server import _Handler as _ApiHandler  # noqa: E402
    _ApiHandler.servis = servis          # /capabilities tek kaynaktan
    # Uzanti/CLI koprusu headless kipte de calisir (mevcut yerel API).
    local_api = LocalAPI(manager, port=VARSAYILAN_API_PORT,
                         lan=bool(manager.store.get("lan_erisimi")))
    try:
        port = local_api.start()
        manager.store.set("api_port", port)
        kilit.guncelle(api_port=port)
    except Exception as exc:
        print(f"UYARI: yerel API acilamadi: {exc}")

    if not servis.erisim.yonetici_var_mi():
        # Anahtarsiz sunucu kimseye yaramaz ve YANLIS bir guven verir.
        print("HATA: yonetici erisim anahtari yok. Once masaustu AfuDM'de"
              " Sunucu sekmesinden bir anahtar olustur.")
        local_api.stop()
        manager.stop()
        kilit.birak()
        return 5

    sonuc = servis.sunucu_baslat()
    if not sonuc.get("ok"):
        print("HATA: %s" % sonuc.get("error"))
        local_api.stop()
        manager.stop()
        kilit.birak()
        return 6
    durum = servis.sunucu_durumu()["sunucu"]
    kilit.guncelle(sunucu_port=durum["port"], sunucu_adres=durum["adres"])
    print("AfuDM sunucu kipinde calisiyor.")
    print("  panel : %s" % durum["url"])
    if durum["lan_url"]:
        print("  ag    : %s" % durum["lan_url"])
    print("  durdur: afuadm server stop")
    # Duzenli kapanis bayragi: Windows'ta konsolsuz surece sinyal gonderilemez,
    # bu yuzden `afuadm server stop` bu dosyayi olusturur ve biz temiz kapaniriz
    # (aria2 oturumu kaydedilir, indirmeler kaybolmaz).
    dur_bayragi = paths.DATA / "sunucu_dur.flag"
    try:
        dur_bayragi.unlink()           # onceki calismadan kalan bayat bayrak
    except OSError:
        pass
    try:
        while True:
            if dur_bayragi.exists():
                try:
                    dur_bayragi.unlink()
                except OSError:
                    pass
                print("kapatiliyor...")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        servis.sunucu_durdur()
        local_api.stop()
        manager.stop()
        kilit.birak()
    return 0

if __name__ == "__main__":
    sys.exit(calistir())
