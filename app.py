"""AfuDM — portable indirme yoneticisi.

Calistirma:  python app.py        (veya AfuDM.bat)
Her sey uygulama klasorunde kalir; sisteme kurulum yapmaz.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eklenti hostu AYRI SUREctir. Paketlenmis (PyInstaller) kopyada yanimizda
# ayri bir python yok; bu yuzden host kendimizi bu bayrakla acar ve pencere
# acmadan yalniz host dongusune girer (bkz. core/eklenti_host.py).
if os.environ.get("AFUDM_EKLENTI_HOST") == "1":
    from core import eklenti_host  # noqa: E402

    sys.exit(eklenti_host.main())

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

import webview  # noqa: E402

from api.server import LocalAPI  # noqa: E402

VARSAYILAN_API_PORT = 6811   # uzantinin da ilk denedigi port
from core import (baslangic, chrome_kurulum, clipboard, dosya_adi, engines, guc, iliskilendir,  # noqa: E402
                  ornek, tracker_saglik,
                  kaydet, lang, linkgrabber, models, paths, pencere, surum)
from core.manager import Manager  # noqa: E402
from core.manager import AyarGecersiz  # noqa: E402
from core import settings_validation  # noqa: E402
from core.servis import AfuDMServis  # noqa: E402
from core.windows_integration import WindowsIntegration  # noqa: E402
from core.reliability import Reliability  # noqa: E402
from core.paylasim_sunucusu import PaylasimSunucusu  # noqa: E402
from core.tunel import TunnelError, TunnelManager  # noqa: E402
from core.manager import AyarGecersiz  # noqa: E402
from core import settings_validation  # noqa: E402

# Pencere basligi dile gore secilir (bkz. core/lang.py); ayar okunana kadar bu durur.
WINDOW_TITLE = "AfuDM"


def parse_start_at(text: str) -> float | None:
    """'23:30' veya '2026-09-17 23:30' -> epoch. Bos ise None.

    Tek kaynak: core/models.parse_time_spec (v1.4 Foundation)."""
    return models.parse_time_spec(text)


# Acilis boyutu oncelikleri (bkz. pencere_boyutu): istenen hedef, sol menunun
# kaydirmasiz sigmasi icin en kucuk boyut ve (hesap hata verirse) eski sabitler.
PENCERE_HEDEF = (1600, 980)    # sol menu tamami + arac cubugu tek satir
PENCERE_MIN = (1100, 900)      # sol menunun kaydirmasiz sigacagi en kucuk
PENCERE_ESKI = (1180, 760)     # v2.7.1 ve oncesi sabit boyut
PENCERE_ESKI_MIN = (880, 560)


def _calisma_alani() -> tuple[int, int, int, int, int]:
    """Birincil monitorun gorev cubugu haric calisma alanini ve DPI'yi doner."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                           ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    monitorlar: list[tuple[int, int, int, int, int]] = []
    callback_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                    wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    @callback_t
    def monitor_cb(handle, _dc, _rect, _data):
        bilgi = MONITORINFO()
        bilgi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(handle, ctypes.byref(bilgi)):
            r = bilgi.rcWork
            monitorlar.append((r.left, r.top, r.right, r.bottom, bilgi.dwFlags))
        return True

    if not user32.EnumDisplayMonitors(None, None, monitor_cb, 0) or not monitorlar:
        raise OSError("monitor calisma alani okunamadi")
    # PRIMARY monitor secilir; yoksa en buyuk calisma alanina dusulur.
    return max(monitorlar, key=lambda item: (bool(item[4] & 1),
                                             (item[2] - item[0]) * (item[3] - item[1])))


def pencere_boyutu() -> tuple[int | None, int | None, int, int, int, int]:
    """Acilis pencere boyutu: (x, y, w, h, min_w, min_h).

    Hedef 1600x980'tir; gorev cubugu haric calisma alani (SPI_GETWORKAREA)
    kucukse hedef, calisma alaninin %92'si ile sinirlanir. min_w/min_h sol
    menunun kaydirmasiz sigmasi icin 1100x900 olur; ekran daha kucukse ekrana
    siginacak kadar daraltilir (baslangic boyutu hicbir zaman min'in altinda
    kalmaz). Pencere calisma alanina ortalanir.

    Not: yeni surec/exe ACMAZ — ctypes ayni surecte calisma alanini okur.
    Hesaplama hata verirse eski sabit degerlere duser; uygulama asla
    acilmazlik yapmaz."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        left, top, right, bottom, _flags = _calisma_alani()
        wa_w, wa_h = right - left, bottom - top
        dpi = int(getattr(user32, "GetDpiForSystem", lambda: 96)() or 96)
        dpi_orani = max(1.0, dpi / 96.0)
        hedef_w = round(PENCERE_HEDEF[0] * dpi_orani)
        hedef_h = round(PENCERE_HEDEF[1] * dpi_orani)
        min_hedef_w = round(PENCERE_MIN[0] * dpi_orani)
        min_hedef_h = round(PENCERE_MIN[1] * dpi_orani)
        # Ekran kucukse calisma alaninin %92'sini gecme; oncelik hedef boyut.
        w = min(hedef_w, int(wa_w * 0.92))
        h = min(hedef_h, int(wa_h * 0.92))
        # min_size: sol menunun kaydirmasiz sigmasi; ekran kucukse ekrana sigdir.
        min_w = min(min_hedef_w, wa_w)
        min_h = min(min_hedef_h, wa_h)
        # Kucuk ekranlarda %92 kesigi min'in altina dusecegi icin baslangic
        # boyutu min'den kucuk kalmasin (yine de ekrana sigar).
        w = max(w, min_w)
        h = max(h, min_h)
        x = left + (wa_w - w) // 2
        y = top + (wa_h - h) // 2
        return x, y, w, h, min_w, min_h
    except Exception:
        # Eski sabit degerler; x/y yok sayilir (pywebview kendisi ortalar).
        return None, None, *PENCERE_ESKI, *PENCERE_ESKI_MIN


def protocol_link(argument: str) -> str:
    """`afudm://download?url=...` baglantisini gercek indirme kaynagina cevir.

    Protokol yalniz HTTP(S)/FTP/magnet veya yerel .torrent gonderir; diger
    parametreler yok sayilir, boylece shell argumani ayar enjekte edemez.
    """
    if not argument.lower().startswith("afudm:"):
        return argument
    parsed = urllib.parse.urlparse(argument)
    if parsed.netloc.lower() not in ("download", "add"):
        return ""
    return urllib.parse.parse_qs(parsed.query).get("url", [""])[0].strip()


def open_in_explorer(target: str) -> None:
    path = Path(target)
    if not path.exists():
        return
    if path.is_dir():
        os.startfile(str(path))  # noqa: S606 — Windows dosya gezgini
    else:
        subprocess.Popen(["explorer", "/select,", str(path)])


class Api:
    """Arayuzun cagirdigi kopru. Her metot JSON'a cevrilebilir sozluk doner."""

    _window: webview.Window | None = None
    _baslik_dili: str | None = None
    _windows: Any = None
    _tepsi: Any = None
    _cikiliyor: bool = False

    def __init__(self, manager: Manager, local_api: LocalAPI,
                 servis: AfuDMServis | None = None) -> None:
        self._window = None
        self._baslik_dili = None
        self.manager = manager
        self.local_api = local_api
        # v2.1: is mantigi TEK yerde. Masaustu arayuzu de web paneli de bu
        # servisi cagirir; asagidaki RPC'ler yalnizca ince kabuktur.
        self.servis = servis or AfuDMServis(manager, kip=ornek.KIP_MASAUSTU)
        self.reliability = Reliability(manager)
        # Alt cizgili: pywebview js_api'nin ozelliklerini DOLASIR; `window.native`
        # (.NET formu) sonsuz derinlige inip gunlugu "Empty.Empty..." ile dolduruyordu.
        # Motor indirmeleri: {"ffmpeg": {"durum": "iniyor", "inen": .., "toplam": ..}}
        self._motor_ilerleme: dict[str, dict] = {}
        self._ozel_baslik = False  # Windows basligi kaldirildi mi (core/pencere.py)
        self._chrome = chrome_kurulum.OtomatikEkleme()
        self._tepsi = None              # pystray simgesi (bkz. build_tray)
        self._cikiliyor = False           # yalniz tepsi > Cikis gercekten kapatir
        self._tepsi_bildirimi = lambda: None
        self._bekleyenler = kaydet.Bekleyenler()
        self._chrome_baslangic = 0.0
        self._probe_iptal: threading.Event | None = None
        self._windows = getattr(manager, "windows", None)
        from api.server import _Handler
        self._paylasim_sunucusu = PaylasimSunucusu(_Handler.shared_files)
        self._tunel = TunnelManager(str(paths.ENGINE / "cloudflared.exe"))

        def _otomatik_motorlar():
            for m in engines.eksikler(sadece_istege_bagli=True):
                if m == "cloudflared":
                    continue
                self.motor_indir(m)
        threading.Thread(target=_otomatik_motorlar, daemon=True).start()

    @property
    def windows(self) -> Any:
        return getattr(self, "_windows", None) or getattr(self.manager, "windows", None)

    @windows.setter
    def windows(self, val: Any) -> None:
        self._windows = val

    # v2.3 Reliability & Security: desktop and HTTP use this shared service.
    def reliability_integrity(self) -> dict: return self.reliability.integrity()
    def reliability_backup(self) -> dict: return self.reliability.backup()
    def reliability_backups(self) -> dict: return self.reliability.backups()
    def reliability_restore(self, archive: str) -> dict: return self.reliability.restore(archive)
    def reliability_diagnostics_preview(self) -> dict: return self.reliability.diagnostics_preview()
    def reliability_diagnostics_export(self) -> dict: return self.reliability.diagnostics_export()
    def reliability_health(self) -> dict: return self.reliability.health()
    def reliability_restart_engine(self) -> dict: return self.reliability.restart_engine()
    def reliability_recovery_preview(self, row_id: int) -> dict: return self.reliability.recovery_preview(row_id)
    def security_rotate_token(self) -> dict:
        self.local_api.rotate_token()
        return {"ok": True, "message": "Yeni anahtar etkin; eski anahtar aninda gecersiz."}

    # --- durum ------------------------------------------------------------
    def snapshot(self) -> dict:
        snap = self.manager.snapshot()
        try:
            self._basligi_esitle(snap.get("lang"))
        except Exception:
            pass
        return snap

    def _basligi_esitle(self, dil: str | None) -> None:
        """Pencere basligini gecerli dile esitler.

        Arayuzdeki metinleri app.js ceviriyor ama pencere basligi Windows'un
        elinde — dil nereden degisirse degissin (Ayarlar penceresi, yerel API
        veya Windows dili) her turda burada esitlenir."""
        baslik_dili = getattr(self, "_baslik_dili", None)
        win = getattr(self, "_window", None)
        if not dil or dil == baslik_dili or win is None:
            return
        try:
            win.set_title(lang.t("window.title", dil))
            self._baslik_dili = dil
        except Exception:
            pass

    def motor_durumu(self) -> dict:
        """Hangi motor kurulu, hangisi iniyor — Ayarlar penceresi bunu gosterir."""
        return {
            "ok": True,
            "motorlar": engines.durum(),
            "ilerleme": dict(self._motor_ilerleme),
        }

    def motor_indir(self, ad: str) -> dict:
        """Istege bagli motoru arka planda indirir; ilerleme motor_durumu()'ndan okunur."""
        if self._motor_ilerleme.get(ad, {}).get("durum") == "iniyor":
            return {"ok": True, "zaten": True}

        def is_parcasi() -> None:
            self._motor_ilerleme[ad] = {"durum": "iniyor", "inen": 0, "toplam": 0}

            def ilerleme(inen: int, toplam: int) -> None:
                self._motor_ilerleme[ad] = {
                    "durum": "iniyor", "inen": inen, "toplam": toplam,
                }

            try:
                sonuc = engines.indir(ad, ilerleme=ilerleme)
                self._motor_ilerleme[ad] = {"durum": "bitti", "boyut_mb": sonuc["boyut_mb"]}
            except Exception as exc:
                self._motor_ilerleme[ad] = {"durum": "hata", "hata": str(exc)[:200]}

        threading.Thread(target=is_parcasi, daemon=True).start()
        return {"ok": True}

    def api_info(self) -> dict:
        return {"ok": True, "port": self.local_api.port, "token": self.local_api.token}

    def surum_bilgi(self) -> dict:
        """Arayuzdeki surum rozeti (tek kaynak core/surum.py + uzanti manifesti).

        Kopru metodu app.js'in surumuYukle cagrisina karsilik gelir; eski
        derlemelerde yoktu ve rozet sessizce bos kaliyordu."""
        return {"surum": surum.SURUM, "uzanti": surum.uzanti_surumu()}

    def peers(self, gid: str) -> dict:
        return {"ok": True, "peers": self.manager.peers(gid)}

    def start_pairing(self, seconds: int = 120) -> dict:
        """Uzanti anahtari elle yapistirmadan alabilsin; pencere kisa surelidir."""
        self.local_api.open_pairing(float(seconds))
        return {"ok": True, "seconds": int(seconds), "port": self.local_api.port}

    # --- ekleme -----------------------------------------------------------
    # --- kaydetme penceresi (bkz. core/kaydet.py) ------------------------
    def _hedef_klasor(self, secilen: str, url: str, kind: str, kategori: str) -> str | None:
        """Tek kaynak: core/servis.AfuDMServis.hedef_klasor (ayni oncelik kurali)."""
        return self.servis.hedef_klasor(secilen, url, kind, kategori)

    def kaydet_bilgi(self, url: str) -> dict:
        url = (url or "").strip()
        kind = self.manager.detect_kind(url) if url else ""
        kategori = kaydet.kategori_tahmin(url, kind) if url else "genel"
        ana = self.manager.current_download_dir()
        return {
            "ok": True,
            "kind": kind,
            "kategori": kategori,
            "dosya_adi": self.manager.guess_name(url) if url and kind == "http" else "",
            "ana": ana,
            "kategori_klasorleri": bool(self.manager.store.get("kategori_klasorleri")),
            "klasorler": {k: kaydet.kategori_klasoru(ana, k) for k in kaydet.KATEGORI_KLASORU},
        }

    def probe_link(self, url: str) -> dict:
        """Arka planda HEAD + Range 0-0 GET ile dosya adi, boyut ve MIME sondajlar."""
        url = (url or "").strip()
        if not url or not url.lower().startswith(("http://", "https://")):
            return {"ok": False}
        sonuc = dosya_adi.probe_url_info(url, timeout=3.0)
        cozulmus_ad = sonuc.get("filename", "")
        kategori = kaydet.kategori_tahmin(url, "http", cozulmus_ad)
        return {
            "ok": True,
            "filename": cozulmus_ad,
            "size": sonuc.get("size"),
            "content_type": sonuc.get("content_type"),
            "kategori": kategori,
            "resumable": sonuc.get("resumable", False),
        }

    # --- rules engine ----------------------------------------------------
    def rules_list(self) -> dict:
        return {"ok": True, "rules": self.manager.store.rules_list()}

    def rules_save(self, rules: list[dict]) -> dict:
        import uuid
        clean = []
        for rule in rules or []:
            if not isinstance(rule, dict) or not str(rule.get("name") or "").strip():
                return {"ok": False, "error": "kural adi gerekli"}
            clean.append({"id": str(rule.get("id") or uuid.uuid4()), "name": str(rule["name"]).strip()[:100], "active": bool(rule.get("active", True)), "match_type": rule.get("match_type") if rule.get("match_type") in ("all", "any") else "all", "conditions": rule.get("conditions") if isinstance(rule.get("conditions"), list) else [], "actions": rule.get("actions") if isinstance(rule.get("actions"), dict) else {}})
        self.manager.store.rules_save(clean)
        return {"ok": True, "rules": self.manager.store.rules_list()}

    def rules_simulate(self, url: str, filename: str = "", size_bytes: int = 0, protocol: str = "http", category: str = "") -> dict:
        from core import rules
        all_rules = self.manager.store.rules_list()
        out = rules.evaluate(all_rules, {"dest_dir": self.manager.current_download_dir(), "proxy": self.manager.store.get("proxy", ""), "max_speed_kb": self.manager.store.get("max_speed_kb", 0), "split": self.manager.store.get("max_conn_per_server", 16)}, rules.context(url, filename, size_bytes, protocol, category))
        matched = [r for r in all_rules if r["id"] in out["matched_rules"]]
        conflicts = [k for k in out["effective_options"] if sum(1 for r in matched if k in r.get("actions", {})) > 1]
        return {"ok": True, **out, "matched_rules": matched, "conflicts": conflicts}

    def download_rules(self, gid: str) -> dict:
        import json
        row = self.manager.store.by_gid(gid)
        if not row: return {"ok": False, "error": "kayit bulunamadi"}
        return {"ok": True, "trace": json.loads(row.get("options") or "{}").get("rules_trace", {})}

    # --- LinkGrabber (v1.5) ---------------------------------------------
    def linkgrabber_analiz(self, metin: str, filtre: dict | None = None) -> dict:
        """Ham metinden URL cikarir: ayikla -> normalize -> tekil -> tur+domain filtre.

        filtre: {"sadece": ["video","arsiv","torrent"], "domain": "ornek.com"}
        onemli: discriminate sonrasi tür tahmini hafiftir (uzanti/site); net
        tur ayrimi indirme aninda manager.detect_kind'da yapilir.
        """
        filtre = filtre or {}
        sadece = {t for t in (filtre.get("sadece") or []) if t and t != "all"}
        domain = filtre.get("domain") or ""
        urller = linkgrabber.ayikla(metin or "")
        urller = linkgrabber.tekil_les(urller)
        urller = linkgrabber.filtrele(urller, sadece=sadece, domain=domain)
        ogeler = [{"url": u, "tur": linkgrabber.tur_bul(u)} for u in urller]
        return {"ok": True, "toplam": len(ogeler), "ogeler": ogeler, "filtre": filtre}

    def linkgrabber_suz(self, ogeler: list[dict], filtre: dict | None = None) -> dict:
        """Paneldeki canli filtre: arama (wildcard), tur, domain, boyut araligi.

        Tek mantik core/linkgrabber.ogeleri_filtrele'dedir — UI'da kural
        kopyasi YOKTUR. Donus: eslesen ogelerin indeksleri + toplam/gosterim.
        """
        filtre = filtre or {}
        sadece = {t for t in (filtre.get("sadece") or []) if t and t != "all"}
        try:
            min_bayt = int(filtre.get("min_boyut")) if filtre.get("min_boyut") not in (None, "") else None
            max_bayt = int(filtre.get("max_boyut")) if filtre.get("max_boyut") not in (None, "") else None
        except (TypeError, ValueError):
            min_bayt = max_bayt = None
        indeks = linkgrabber.ogeleri_filtrele(
            ogeler or [],
            ara=filtre.get("ara") or "",
            sadece=sadece,
            domain=filtre.get("domain") or "",
            min_boyut=min_bayt,
            max_boyut=max_bayt,
        )
        return {
            "ok": True,
            "toplam": len(ogeler or []),
            "gosterilen": len(indeks),
            "indeks": indeks,
            "domainler": linkgrabber.domainler(ogeler or []),
        }

    def linkgrabber_iptal(self) -> dict:
        """Devam eden lazy probe'u oldugu yere kadar durdur (yeni is gerekmez)."""
        if self._probe_iptal is not None:
            self._probe_iptal.set()
        return {"ok": True}

    def linkgrabber_onceki(self, urller: list[str]) -> dict:
        """Paneldeki adreslerden DB'de daha once kayitli olanlar (uyari).

        Engellemez yalnizca isaretler: kullanici isterse yine ekler.
        Magnet icin info hash, digerleri icin normalize URL eslestirilir.
        """
        eslesen = linkgrabber.onceki_eslesen(
            urller or [], self.manager.gecmis_sources())
        return {"ok": True, "onceki": eslesen, "sayi": len(eslesen)}

    def linkgrabber_probe(self, urller: list[str], es_zamanli: int = 8) -> dict:
        """Seçilen URL'ler icin toplu lazy probe (sinirli eszamanlilik).

        Calisan bir probe varken yenisi istenirse eskisi iptal edilir (isleme
        devam eder ama yeni is yok), hepsi ise ilerler.
        """
        urller = urller or []
        if self._probe_iptal is not None:
            self._probe_iptal.set()
        self._probe_iptal = threading.Event()
        sonuclar = linkgrabber.probe_es_zamanli(
            urller, es_zamanli=es_zamanli, iptal=self._probe_iptal)
        ogeler = []
        for url in urller:
            bilgi = sonuclar.get(url, {"ok": False})
            ad = bilgi.get("filename") or ""
            ogeler.append({
                "url": url,
                "ok": bilgi.get("ok", False),
                "filename": ad,
                "size": bilgi.get("size"),
                "content_type": bilgi.get("content_type"),
                "kategori": kaydet.kategori_tahmin(url, linkgrabber.tur_bul(url), ad)
                if url.lower().startswith(("http://", "https://")) else "",
                "resumable": bilgi.get("resumable", False),
            })
        return {"ok": True, "ogeler": ogeler}

    def linkgrabber_ekle(self, urller: list[str], secim: dict | None = None) -> dict:
        """LinkGrabber panelinden secilen baglantilari topluca kuyruga ekler."""
        urller = [u for u in (urller or []) if u]
        secim = secim or {}
        if not urller:
            return {"ok": False, "error": lang.t("err.noLink", self.manager.store.get("language", "auto"))}
        return self.add_links({
            "urls": urller,
            "dest_dir": secim.get("dest_dir") or "",
            "kategori": secim.get("kategori") or "",
            "quality": secim.get("quality") or None,
            "audio_only": bool(secim.get("audio_only")),
            "playlist": bool(secim.get("playlist")),
            "start_at": secim.get("start_at") or "",
        })

    def klasor_kisayollar(self) -> dict:
        return {"ok": True, "ogeler": kaydet.kisayollar(
            self.manager.current_download_dir(),
            str(self.manager.store.get("ag_konumlari", "")))}

    def ag_konumu_ekle(self, yol: str) -> dict:
        """Modem/NAS paylasimini klasor agacina ekle (once ERISIM dogrulanir)."""
        try:
            temiz = kaydet.ag_konumu_dogrula(yol)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        mevcut = kaydet.ag_konumlari(str(self.manager.store.get("ag_konumlari", "")))
        if temiz not in mevcut:
            mevcut.append(temiz)
        self.manager.store.set("ag_konumlari", "\n".join(mevcut))
        return {"ok": True, "yol": temiz, "sayi": len(mevcut)}

    def ag_konumu_sil(self, yol: str) -> dict:
        mevcut = [y for y in kaydet.ag_konumlari(str(self.manager.store.get("ag_konumlari", "")))
                  if y != (yol or "").strip()]
        self.manager.store.set("ag_konumlari", "\n".join(mevcut))
        return {"ok": True, "sayi": len(mevcut)}

    def klasor_alt(self, yol: str) -> dict:
        try:
            return {"ok": True, "ogeler": kaydet.alt_klasorler(yol)}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def klasor_yeni(self, ust: str, ad: str) -> dict:
        try:
            return {"ok": True, "yol": kaydet.klasor_olustur(ust, ad)}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def klasor_gozat(self, baslangic: str = "") -> dict:
        if not self._window:
            return {"ok": False}
        secim = self._window.create_file_dialog(
            webview.FOLDER_DIALOG, directory=baslangic or self.manager.current_download_dir())
        return {"ok": True, "yol": secim[0] if secim else ""}

    def tarayicidan_sor(self, istek: dict) -> int:
        """Yerel API (uzanti) cagirir: istegi beklet, pencereyi ac ve one getir."""
        kimlik = self._bekleyenler.ekle(istek)
        if self._window:
            pencere.one_getir(self._window)
            try:
                self._window.evaluate_js("window.afudmBekleyen && window.afudmBekleyen()")
            except Exception:
                pass  # sayfa hazir degil: arayuz tick'te kendisi sorar
        return kimlik

    def bekleyen_listesi(self) -> dict:
        return {"ok": True, "ogeler": self._bekleyenler.ozet()}

    def bekleyen_iptal(self, kimlik: int) -> dict:
        self._bekleyenler.al(kimlik)
        return {"ok": True}

    def bekleyen_onayla(self, kimlik: int, secim: dict) -> dict:
        istek = self._bekleyenler.al(kimlik)
        if not istek:
            return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}
        url = istek.get("url") or ""
        kind = istek.get("kind") or self.manager.detect_kind(url)
        try:
            ad = kaydet.guvenli_dosya_adi(secim.get("filename") or "")
            istek_req = models.DownloadRequest.from_mapping({
                "source": url,
                "kind": kind,
                "dest_dir": self._hedef_klasor(secim.get("dest_dir") or "", url, kind, secim.get("kategori") or ""),
                "quality": secim.get("quality") or istek.get("quality"),
                "audio_only": bool(secim.get("audio_only", istek.get("audio_only"))),
                "start_at": secim.get("start_at") or "",
                "headers": istek.get("headers") or {},
                "filename": (ad or istek.get("filename")) if kind == "http" else None,
                "cookies": istek.get("cookies"),
                "user_agent": istek.get("user_agent"),
                "title": (ad or istek.get("title")) if kind == "video" else istek.get("title"),

                "altyazi_diller": secim.get("altyazi_diller") or "",
                "oto_altyazi": bool(secim.get("oto_altyazi")),
                "altyazi_goem": bool(secim.get("altyazi_goem")),
                "kucuk_resim": secim.get("kucuk_resim") or "",
                "ustveri_goem": bool(secim.get("ustveri_goem")),
                "bolumler": secim.get("bolumler") or "",
                "sponsorblock": secim.get("sponsorblock") or "",
                "bolum_araligi": secim.get("bolum_araligi") or "",
                "kapsayici": secim.get("kapsayici") or "",
                "ses_formati": secim.get("ses_formati") or "",
                "dosya_sablonu": secim.get("dosya_sablonu") or "",
                "tarayici_cerezi": secim.get("tarayici_cerezi") or "",
            })
            sonuc = self.manager.add(istek_req)
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, **sonuc}

    # --- sistem baglantilari (baslangic, .torrent/magnet) ----------------
    # Ikisi de Windows'a dokunur (Baslangic klasoru / HKCU\Software\Classes):
    # her acilista degil, YALNIZ Ayarlar acilinca sorulur.
    def sistem_durumu(self) -> dict:
        try:
            return {
                "ok": True,
                "baslangic": baslangic.acik_mi(),
                "torrent": iliskilendir.durum(),
            }
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def baslangic_ayarla(self, acik: bool, tepside: bool = True) -> dict:
        try:
            if acik:
                # Kisayol argumani ayarla birlikte degisir (bkz. baslangic.ac)
                baslangic.ac("--tepside" if tepside else "")
            else:
                baslangic.kapat()
        except (OSError, RuntimeError) as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, "acik": baslangic.acik_mi()}

    def varsayilan_uygulama_ekrani(self) -> dict:
        """Windows'un "Varsayilan uygulamalar" ekranini ac.

        .torrent'in hangi programla acilacagini SADECE kullanici secebilir
        (UserChoice hash korumali); yapabilecegimiz en iyi sey dogru ekrani
        onune getirmek."""
        try:
            os.startfile("ms-settings:defaultapps")      # noqa: S606
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True}

    def torrent_iliskilendir(self, acik: bool) -> dict:
        try:
            iliskilendir.ac() if acik else iliskilendir.kapat()
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, "durum": iliskilendir.durum()}

    # --- Windows Integration v2.2 --------------------------------------
    def windows_integration_status(self) -> dict:
        if not self.windows:
            return {"ok": False, "error": "Windows integration is not available in this environment.", "integrations": {}}
        try:
            out = self.windows.status()
            out["integrations"]["torrent"] = {"registered": iliskilendir.acik_mi(), "scope": "current_user"}
            out["integrations"]["startup"] = {"registered": baslangic.acik_mi(), "scope": "current_user"}
            out["integrations"]["notify"] = {"registered": bool(self.manager.store.get("windows_notifications")), "scope": "current_user"}
            
            program = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Windows Defender" / "MpCmdRun.exe"
            out["integrations"]["defender"] = {"registered": bool(self.manager.store.get("defender_auto_scan")), "scope": "current_user", "available": program.exists()}
            
            return out
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def windows_integration_apply(self, ident: str) -> dict:
        if not self.windows: return {"ok": False, "error": "Unavailable"}
        try:
            if ident == "torrent":
                iliskilendir.ac()
            elif ident == "startup":
                baslangic.ac("--tepside")
            elif ident == "notify":
                self.manager.store.set("windows_notifications", True)
            elif ident == "defender":
                self.manager.store.set("defender_auto_scan", True)
            else:
                self.windows.apply(str(ident))
            return self.windows_integration_status()
        except PermissionError as exc:
            return {"ok": False, "error": "Windows kaydina yazma izni yok. Uygulamayi uygun kullanici hesabi ile yeniden deneyin: " + str(exc)[:120]}
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def windows_integration_remove(self, ident: str) -> dict:
        if not self.windows: return {"ok": False, "error": "Unavailable"}
        try:
            if ident == "torrent":
                iliskilendir.kapat()
            elif ident == "startup":
                baslangic.kapat()
            elif ident == "notify":
                self.manager.store.set("windows_notifications", False)
            elif ident == "defender":
                self.manager.store.set("defender_auto_scan", False)
            else:
                self.windows.remove(str(ident))
            return self.windows_integration_status()
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def windows_integration_test(self, ident: str) -> dict:
        if not self.windows: return {"ok": False, "error": "Unavailable"}
        try:
            if ident == "torrent": return {"ok": iliskilendir.acik_mi(), "registered": iliskilendir.acik_mi()}
            if ident == "startup": return {"ok": baslangic.acik_mi(), "registered": baslangic.acik_mi()}
            if ident == "notify":
                if callable(getattr(self.manager, "windows_notify", None)):
                    self.manager.windows_notify("AfuDM Test", "Bildirimler calisiyor!")
                return {"ok": True, "registered": bool(self.manager.store.get("windows_notifications"))}
            if ident == "defender":
                program = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Windows Defender" / "MpCmdRun.exe"
                return {"ok": program.exists(), "registered": bool(self.manager.store.get("defender_auto_scan"))}
            return self.windows.test(str(ident))
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def defender_scan(self, gid: str) -> dict:
        if not self.windows: return {"ok": False, "error": "Windows integration unavailable."}
        for item in self.manager.snapshot().get("items", []):
            if item.get("gid") == gid:
                path = Path(item.get("dir") or self.manager.current_download_dir()) / (item.get("filename") or "")
                return self.windows.scan_file(str(path))
        return {"ok": False, "error": "indirme bulunamadi"}

    # --- seed penceresi (torrent) ----------------------------------------
    def seed_bilgi(self, gid: str) -> dict:
        return self.manager.seed_bilgi(gid)

    def seed_tazele(self, gid: str) -> dict:
        return self.manager.seed_tazele(gid)
    def torrent_on_ekle(self, source: str) -> dict:
        """Dosya secimi icin torrenti duraklatilmis olarak aria2'ye ekler."""
        try:
            gid = self.manager.torrent_on_ekle(source)
            return {"ok": True, "gid": gid}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def torrent_on_iptal(self, gid: str) -> dict:
        """On-eklenmis torrenti kaldirir."""
        try:
            self.manager.torrent_on_iptal(gid)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def torrent_dosyalari(self, gid: str) -> dict:
        """Torrent dosya agaci ve secim bilgisi."""
        try:
            dosyalar = self.manager.torrent_dosyalari(gid)
            hazir_degil = bool(getattr(dosyalar, "hazir_degil", False))
            neden = str(getattr(dosyalar, "neden", ""))
            return {
                "ok": True,
                "gid": getattr(dosyalar, "gid", gid),
                "hazir_degil": hazir_degil,
                "neden": neden,
                "dosyalar": list(dosyalar),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def torrent_secimi_ayarla(self, gid: str, indeksler: list[int]) -> dict:
        """Torrent dosya secimini canli uygula ve DB'ye yaz."""
        try:
            return self.manager.torrent_secimi_ayarla(gid, indeksler)
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}
    def torrent_metrikleri(self, gid: str) -> dict:
        """Torrent seed/ratio/tracker metrikleri koprusu."""
        try:
            sonuc = self.manager.torrent_metrikleri(gid)
            hazir_degil = bool(sonuc.get("hazir_degil", False))
            neden = str(sonuc.get("neden", ""))
            return {
                "ok": True,
                "gid": gid,
                "hazir_degil": hazir_degil,
                "neden": neden,
                "metrikler": sonuc if not hazir_degil else {},
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300], "hazir_degil": True, "neden": str(exc)[:300]}

    def loglar(self, gid: str = "") -> dict:
        """Detay paneli icin olay ve hata gunlukleri."""
        try:
            events = self.manager.store.recent_events(limit=50, gid=gid)
            return {"ok": True, "events": events}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200], "events": []}



    def tracker_tara(self, gid: str = "") -> dict:
        """Klasordeki tracker'lari olc ve canli sonucu hemen uygula."""
        return self.manager.tracker_tara(gid)

    def tracker_klasoru_ac(self) -> dict:
        tracker_saglik.klasoru_hazirla()
        try:
            os.startfile(str(tracker_saglik.KLASOR))          # noqa: S606
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True}

    def seed_dosyalari(self) -> dict:
        """Ayarlar > Seed listeleri: klasordeki .txt'ler + son tarama ozeti."""
        return self.manager.seed_dosyalari()

    def seed_dosya_ekle(self, yol: str = "") -> dict:
        """Yol bossa dosya secici acilir; secilen .txt trackers/ icine kopyalanir."""
        if not yol:
            if not self._window:
                return {"ok": False, "error": "pencere hazir degil"}
            secim = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Tracker listesi (*.txt)", "Tum dosyalar (*.*)"))
            if not secim:
                return {"ok": True, "iptal": True}
            yol = secim[0]
        return self.manager.seed_dosya_ekle(yol)

    def seed_dosya_sil(self, ad: str) -> dict:
        return self.manager.seed_dosya_sil(ad)

    def seed_tracker_kaydet(self, metin: str) -> dict:
        """Elle eklenen tracker'lari sakla (uygulanmasi tazelemede olur)."""
        from core import trackers as _tr
        temiz = _tr.ayikla(metin)
        self.manager.store.set("ek_trackerlar", "\n".join(temiz))
        return {"ok": True, "sayi": len(temiz), "liste": "\n".join(temiz)}


    # --- eklentiler (v2.0 Plugin Platform) -------------------------------
    # DURUSTLUK: eklentiler AfuDM'in TUM yetkileriyle calisir. Ayri surec
    # yalnizca COKME/TAKILMA izolasyonu saglar, GUVENLIK sandbox'i DEGILDIR.
    # Izin ve domain listeleri BEYANDIR; teknik olarak zorlanmaz.
    def eklenti_listesi(self) -> dict:
        return self.manager.eklentiler.liste()

    def eklenti_incele(self, yol: str = "") -> dict:
        """Kurulumdan ONCE manifest + istenen izinler + domainler.

        Yol bossa dosya secici acilir (yerel .afup paketi)."""
        if not yol:
            if not self._window:
                return {"ok": False, "error": "pencere hazir degil"}
            secim = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("AfuDM eklenti paketi (*.afup)", "Tum dosyalar (*.*)"))
            if not secim:
                return {"ok": True, "iptal": True}
            yol = secim[0]
        return self.manager.eklentiler.incele(yol)

    def eklenti_kur(self, yol: str, onaylanan_izinler: list | None = None) -> dict:
        """Arka planda kurar; ilerleme `eklenti_islem` ile izlenir."""
        return self.manager.eklentiler.kur(yol, onaylanan_izinler)

    def eklenti_guncelle(self, ad: str, yol: str) -> dict:
        """Basarisiz olursa ONCEKI SURUME geri doner (rollback)."""
        return self.manager.eklentiler.guncelle(ad, yol)

    def eklenti_kaldir(self, ad: str) -> dict:
        return self.manager.eklentiler.kaldir(ad)

    def eklenti_etkinlestir(self, ad: str, acik: bool) -> dict:
        return self.manager.eklentiler.etkinlestir(ad, bool(acik))

    def eklenti_yeniden_baslat(self, ad: str) -> dict:
        return self.manager.eklentiler.yeniden_baslat(ad)

    def eklenti_ayar_kaydet(self, ad: str, ayarlar: dict | None = None) -> dict:
        return self.manager.eklentiler.ayar_kaydet(ad, ayarlar or {})

    def eklenti_gunluk(self, ad: str) -> dict:
        return self.manager.eklentiler.gunluk(ad)

    def eklenti_islem(self) -> dict:
        return self.manager.eklentiler.islem()

    def eklenti_islem_iptal(self) -> dict:
        return self.manager.eklentiler.islem_iptal()

    def eklenti_klasoru_ac(self) -> dict:
        try:
            paths.PLUGINS.mkdir(parents=True, exist_ok=True)
            os.startfile(str(paths.PLUGINS))          # noqa: S606
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True}

    # --- telefon arayuzu (ui/mobil.html + LocalAPI) ----------------------
    def telefon_durumu(self) -> dict:
        """Ayarlar penceresi icin: acik mi, adres ne, QR nerede."""
        acik = bool(self.manager.store.get("lan_erisimi"))
        adres = self.local_api.lan_adresi() if acik else ""
        return {
            "ok": True,
            "acik": acik,
            "adres": adres,
            "qr": self._qr_uret(adres) if adres else "",
            "port": self.local_api.port,
        }

    @staticmethod
    def _qr_uret(metin: str) -> str:
        """Adresi QR olarak dondur (data URI). qrcode yoksa sessizce bos doner:
        arayuz o zaman yalniz adresi gosterir, ozellik kaybolmaz."""
        try:
            import base64
            from io import BytesIO

            import qrcode
        except ImportError:
            return ""
        try:
            kod = qrcode.QRCode(box_size=6, border=2)
            kod.add_data(metin)
            kod.make(fit=True)
            resim = kod.make_image(fill_color="#0f131a", back_color="#e6eaf0")
            tampon = BytesIO()
            resim.save(tampon, format="PNG")
            return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode()
        except Exception:
            return ""

    def telefon_ayarla(self, acik: bool) -> dict:
        """Yerel agi ac/kapat ve sunucuyu YENIDEN baslat.

        Baglanacak adres soket acilirken seciliyor; ayarin hemen gecerli olmasi
        icin sunucu yeniden kuruluyor (yeniden baslatma beklenmesin).
        """
        sonuc = self.local_api.lan_ayarla(bool(acik))
        if not sonuc.get("ok"):
            return {"ok": False, "error": "lan_bind_failed", "acik": bool(sonuc.get("acik"))}
        self.manager.store.set("lan_erisimi", bool(acik))
        self.manager.store.set("api_port", int(sonuc.get("port") or 0))
        return self.telefon_durumu()

    # --- uyku / telefondan uyandirma (core/guc.py) -----------------------
    def guc_durumu(self) -> dict:
        """Ayarlar icin: ag kartinin MAC'i ve uyandirmaya hazir olup olmadigi."""
        try:
            return {"ok": True, **guc.durum()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def simdi_uyu(self) -> dict:
        """Kullanici "simdi uyut" derse (deneme icin)."""
        return {"ok": bool(guc.uyut())}

    def add_links(self, payload: dict) -> dict:
        """Link ekle. Is mantigi core/servis.py'de; burada KOPYA YOKTUR."""
        return self.servis.ekle(payload)

    # --- kontrol ----------------------------------------------------------
    def control(self, action: str, gid: str, delete_files: bool = False) -> dict:
        df = delete_files.get("delete_files", False) if isinstance(delete_files, dict) else delete_files
        return self.servis.kontrol(action, gid, bool(df))

    def retry(self, row_id: int) -> dict:
        return self.servis.yeniden_dene(row_id)

    def clear_finished(self) -> dict:
        return self.servis.bitmisleri_temizle()

    # --- v1.8 Automation -------------------------------------------------
    def automation_jobs(self, gid: str = "") -> dict:
        return {"ok": True, "jobs": self.manager.store.automation_jobs(str(gid))}

    def automation_retry(self, job_id: int) -> dict:
        try: return {"ok": True, "job": self.manager.automation.retry(int(job_id))}
        except Exception as exc: return {"ok": False, "error": str(exc)[:300]}

    def automation_cancel(self, job_id: int) -> dict:
        try: return {"ok": True, "job": self.manager.automation.cancel(int(job_id))}
        except Exception as exc: return {"ok": False, "error": str(exc)[:300]}

    # --- v1.8 Automation -------------------------------------------------
    def automation_jobs(self, gid: str = "") -> dict:
        return {"ok": True, "jobs": self.manager.store.automation_jobs(str(gid))}

    def automation_retry(self, job_id: int) -> dict:
        try: return {"ok": True, "job": self.manager.automation.retry(int(job_id))}
        except Exception as exc: return {"ok": False, "error": str(exc)[:300]}

    def automation_cancel(self, job_id: int) -> dict:
        try: return {"ok": True, "job": self.manager.automation.cancel(int(job_id))}
        except Exception as exc: return {"ok": False, "error": str(exc)[:300]}

    # --- ayarlar ----------------------------------------------------------
    def settings_save(self, payload: dict) -> dict:
        return self.ayarlari_dogrula_kaydet(payload)

    def ayarlari_dogrula_kaydet(self, ayarlar: dict) -> dict:
        """Atomik ayar RPC'si: hata metni degil i18n anahtari tasir."""
        try:
            kayit = self.manager.update_settings(ayarlar)
            if kayit.get("internet_paylasim") is False:
                self.paylasim_stop()
            return {"ok": True, "hatalar": [], "ayarlar": kayit, "settings": kayit}
        except AyarGecersiz as exc:
            return {"ok": False, "hatalar": exc.hatalar, "ayarlar": self.manager.store.all_settings()}
        except Exception:
            return {"ok": False, "hatalar": [{"alan": "_genel", "mesaj_anahtari": "err.invalidValue"}], "ayarlar": self.manager.store.all_settings()}

    def proxy_testi(self, proxy: str) -> dict:
        try:
            temiz = settings_validation.dogrula_proxy(proxy)
        except settings_validation.AyarHatasi as exc:
            return {"ok": False, "gecikme_ms": 0, "mesaj_anahtari": exc.mesaj_anahtari}
        if not temiz:
            return {"ok": False, "gecikme_ms": 0, "mesaj_anahtari": "err.proxyRequired"}
        import socket
        try:
            _, hostport = settings_validation._proxy_parcala(temiz)
            host, port = hostport.rsplit(":", 1)
            basla = time.monotonic(); sock = socket.create_connection((host, int(port)), timeout=4)
            sock.close()
            return {"ok": True, "gecikme_ms": round((time.monotonic()-basla)*1000), "mesaj_anahtari": ""}
        except OSError:
            return {"ok": False, "gecikme_ms": 0, "mesaj_anahtari": "err.proxyUnreachable"}

    def port_durumu(self) -> dict:
        return self.local_api.durum()

    def ag_konumlari_listele(self) -> dict:
        ham = str(self.manager.store.get("ag_konumlari") or "")
        return {"ok": True, "konumlar": [x for x in ham.splitlines() if x.strip()]}
        return self.servis.ayar_kaydet(payload)

    def ayar_rozetleri(self) -> dict:
        """Her ayarin UYGULANMA ZAMANI (hemen / yeni indirmelerde / sonraki
        baslatmada / servis yeniden baslayinca). Arayuz rozetleri bunu okur."""
        return {"ok": True, "uygulama": self.servis.ayarlar()["uygulama"]}

    # --- v2.1 yonetim sunucusu -------------------------------------------
    def sunucu_durumu(self) -> dict:
        return self.servis.sunucu_durumu()

    def sunucu_ayarla(self, acik: bool) -> dict:
        """Tek anahtar: sunucuyu ac/kapat. Yonetici anahtari YOKSA ACMAZ —
        anahtarsiz acilan bir sunucu kimseye yaramaz, yanlis guven verir."""
        if acik and not self.servis.erisim.yonetici_var_mi():
            return {"ok": False, "code": "ANAHTAR_YOK",
                    "error": "once bir yonetici erisim anahtari olustur"}
        return self.servis.sunucu_ayarla(bool(acik))

    def sunucu_yeniden(self) -> dict:
        return self.servis.sunucu_yeniden()

    def sunucu_panel_ac(self) -> dict:
        """Panel adresini varsayilan tarayicida acar. Anahtar URL'ye KONMAZ."""
        durum = self.servis.sunucu_durumu()["sunucu"]
        if not durum["calisiyor"]:
            return {"ok": False, "code": "SUNUCU_KAPALI", "error": "sunucu kapali"}
        try:
            import webbrowser
            webbrowser.open(durum["url"])
        except Exception as exc:
            return {"ok": False, "code": "ACILAMADI", "error": str(exc)[:200]}
        return {"ok": True, "url": durum["url"]}

    def sunucu_anahtarlar(self) -> dict:
        return self.servis.anahtarlar()

    def sunucu_anahtar_olustur(self, ad: str, rol: str, not_metni: str = "") -> dict:
        return self.servis.anahtar_olustur(ad, rol, not_metni)

    def sunucu_anahtar_rotasyon(self, key_id: int) -> dict:
        return self.servis.anahtar_rotasyon(key_id)

    def sunucu_anahtar_iptal(self, key_id: int) -> dict:
        return self.servis.anahtar_iptal(key_id)

    def sunucu_anahtar_sil(self, key_id: int) -> dict:
        return self.servis.anahtar_sil(key_id)

    def sunucu_anahtar_rol(self, key_id: int, rol: str) -> dict:
        return self.servis.anahtar_rol_ayarla(key_id, rol)

    def sunucu_istemciler(self, dakika: int = 0) -> dict:
        return self.servis.istemciler(dakika)

    def sunucu_istemci_iptal(self, client_id: int) -> dict:
        return self.servis.istemci_iptal(client_id)

    def sunucu_istemci_temizle(self, gun: int = 7) -> dict:
        return self.servis.istemcileri_temizle(gun)

    def sunucu_kilit_temizle(self) -> dict:
        return self.servis.kilitleri_temizle()

    def sunucu_profiller(self) -> dict:
        return self.servis.profiller()

    def sunucu_profil_kaydet(self, veri: dict) -> dict:
        return self.servis.profil_kaydet(veri)

    def sunucu_profil_sil(self, profil_id: int) -> dict:
        return self.servis.profil_sil(profil_id)

    def sunucu_profil_etkinlestir(self, profil_id: int) -> dict:
        return self.servis.profil_etkinlestir(profil_id)


    # --- klasor -----------------------------------------------------------
    def open_download_dir(self) -> dict:
        open_in_explorer(self.manager.current_download_dir())
        return {"ok": True}

    def open_item_folder(self, gid: str) -> dict:
        for item in self.manager.snapshot()["items"]:
            if item["gid"] == gid:
                folder = item.get("dir") or self.manager.current_download_dir()
                hedef = self.manager.resolve_item_path(gid)
                open_in_explorer(str(hedef) if hedef else folder)
                return {"ok": True}
        return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}

    def _paylasim_url(self, token: str) -> str:
        """Paylasim icin LAN hostundan tek ve dogru indirme URL'si uretir."""
        adres = self.local_api.lan_adresi()
        host = ""
        if adres:
            try:
                parse_edilecek = adres if "://" in adres else f"//{adres}"
                host = urllib.parse.urlparse(parse_edilecek).hostname or ""
            except ValueError:
                host = ""
        if not host or host.startswith("127."):
            host = "127.0.0.1"
        return f"http://{host}:{self.local_api.port}/s/{token}"

    def _internet_linki(self, token: str) -> tuple[str, str]:
        """Cloudflare yalniz dar paylasim sunucusuna baglanir."""
        if getattr(self.manager.store, "get", lambda *_args: True)("internet_paylasim", True) is False:
            return "", ""
        if not engines.var_mi("cloudflared"):
            return "", "share.cloudflaredMissing"
        try:
            port = self._paylasim_sunucusu.start()
            adres = self._tunel.start(port)
            return f"{adres}/s/{token}", ""
        except Exception:
            return "", "share.tunnelError"

    def _paylasim_sonucu(self, token: str, yol: Path, warning: str = "") -> dict:
        yerel = self._paylasim_url(token)
        internet, internet_hata = self._internet_linki(token)
        kullanilacak = internet or yerel
        return {
            "ok": True, "transport": "http", "token": token,
            "url": kullanilacak, "local_url": yerel,
            "internet_url": internet, "qr": self._qr_uret(kullanilacak),
            "filename": yol.name, "smb": "", "warning": warning,
            "internet_error_key": internet_hata,
        }

    def share_create(self, gid: str) -> dict:
        yol = self.manager.resolve_item_path(gid)
        if not yol or not yol.exists() or not yol.is_file():
            return {"ok": False, "error": "Sadece tamamlanmış tekil dosyalar paylaşılabilir veya dosya diskte bulunamadı."}
        from api.server import _Handler
        import secrets
        import time
        token = secrets.token_urlsafe(12)
        _Handler.shared_files[token] = {"path": yol, "created": time.time()}
        return self._paylasim_sonucu(token, yol)

    def agda_paylas(self, gid: str) -> dict:
        """Tamamlanan dosyayi SMB/UNC olarak dene; yetki yoksa HTTP+QR'a dus.

        `net share` Windows sistem ayaridir; bu nedenle gercek paylasim yalnızca
        kullanici eylemiyle burada denenir ve testlerde subprocess sahte olur.
        SMB basarisiz olsa bile LocalAPI linki calisan bir alternatif olarak kalir.
        """
        yol = self.manager.resolve_item_path(gid)
        if not yol or not yol.exists() or not yol.is_file():
            return {"ok": False, "error": "Sadece tamamlanmış tekil dosyalar paylaşılabilir veya dosya diskte bulunamadı."}
        from api.server import _Handler
        import secrets
        import time

        token = secrets.token_urlsafe(12)
        _Handler.shared_files[token] = {"path": yol, "created": time.time(),
                                        "share_name": "", "staging_path": ""}
        url = self._paylasim_url(token)
        result = self._paylasim_sonucu(token, yol,
            "SMB paylasimi icin yonetici izni bulunamadi; HTTP LAN baglantisi hazirlandi.")
        result.update({
            "ok": True,
            "transport": "http",
            "token": token,
            "url": result["url"],
            "qr": result["qr"],
            "filename": yol.name,
            "smb": "",
            "warning": "SMB paylaşımı için yönetici izni bulunamadı; HTTP LAN bağlantısı hazırlandı.",
        })
        if os.name != "nt":
            return result

        # Dosyanın bulunduğu klasörü değil, yalnızca bu dosyanın kopyasını paylaş.
        share_root = Path(tempfile.gettempdir()) / "AfuDM-network-shares" / token
        share_root.mkdir(parents=True, exist_ok=True)
        staged = share_root / yol.name
        try:
            shutil.copy2(yol, staged)
            share_name = "AfuDM_" + token.replace("-", "")[:12]
            share_result = subprocess.run(
                ["net", "share", f"{share_name}={share_root}", "/GRANT:Everyone,READ"],
                check=True, capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if share_result.returncode:
                raise subprocess.CalledProcessError(
                    share_result.returncode, share_result.args,
                    output=share_result.stdout, stderr=share_result.stderr,
                )
            _Handler.shared_files[token].update({
                "share_name": share_name, "staging_path": str(share_root),
            })
            host = socket.gethostname() or "127.0.0.1"
            result.update({
                "transport": "smb",
                "smb": f"\\\\{host}\\{share_name}\\{yol.name}",
                "warning": "",
            })
        except (OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(share_root, ignore_errors=True)
            result["warning"] = "SMB paylaşımı açılamadı (%s); HTTP LAN bağlantısı ve QR hazırlandı." % str(exc)[:120]
        return result

    def _paylasim_kaynaklarini_temizle(self, bilgi: dict) -> list[str]:
        """Revoke a Windows share and remove its staging folder; safe to repeat."""
        sorunlar = []
        share_name = bilgi.get("share_name")
        if share_name:
            try:
                sonuc = subprocess.run(
                    ["net", "share", share_name, "/delete", "/y"],
                    check=False, capture_output=True, text=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                cikti = f"{sonuc.stderr} {sonuc.stdout}".lower()
                share_yok = any(ifad in cikti for ifad in
                                ("does not exist", "not found", "no such", "bulunamad"))
                if sonuc.returncode and not share_yok:
                    sorunlar.append(f"{share_name}: {sonuc.stderr or sonuc.stdout or sonuc.returncode}")
            except (OSError, subprocess.SubprocessError) as exc:
                sorunlar.append(f"{share_name}: {exc}")
        staging_path = bilgi.get("staging_path")
        if staging_path:
            try:
                shutil.rmtree(staging_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                sorunlar.append(f"{staging_path}: {exc}")
        for sorun in sorunlar:
            print(f"Share cleanup failed: {sorun}")
            try:
                self.manager.store.log("error", f"Share cleanup failed: {sorun}")
            except Exception:
                pass
        return sorunlar

    def share_list(self) -> dict:
        from api.server import _Handler
        aktif_paylasimlar = []
        for token, bilgi in _Handler.shared_files.items():
            yol = Path(bilgi["path"])
            local_url = self._paylasim_url(token)
            internet_url = (self._tunel.url + f"/s/{token}"
                            if getattr(self, "_tunel", None) and self._tunel.active else "")
            aktif_paylasimlar.append({
                "token": token,
                "url": internet_url or local_url,
                "local_url": local_url,
                "internet_url": internet_url,
                "filename": yol.name,
                "size": yol.stat().st_size if yol.exists() else 0,
                "created": bilgi["created"]
            })
        # Yeni olanlar en ustte
        aktif_paylasimlar.sort(key=lambda x: x["created"], reverse=True)
        return {"ok": True, "shares": aktif_paylasimlar}

    def share_delete(self, token: str) -> dict:
        from api.server import _Handler
        if token in _Handler.shared_files:
            bilgi = _Handler.shared_files[token]
            sorunlar = self._paylasim_kaynaklarini_temizle(bilgi)
            if sorunlar:
                return {"ok": False, "error": "Payla\u015f\u0131m kaynaklar\u0131 temizlenemedi: " + "; ".join(sorunlar)}
            del _Handler.shared_files[token]
            if not _Handler.shared_files:
                if hasattr(self, "_tunel"):
                    self._tunel.stop()
                if hasattr(self, "_paylasim_sunucusu"):
                    self._paylasim_sunucusu.stop()
            return {"ok": True}
        return {"ok": False, "error": "Paylaşım bulunamadı."}

    def dosya_sec_ve_paylas(self) -> dict:
        if not self._window:
            return {"ok": False}
        import webview
        secim = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if not secim:
            return {"ok": False, "error": "Dosya seçimi iptal edildi."}
        
        from api.server import _Handler
        import secrets
        import time
        
        sonuclar = []
        for dosya in secim:
            yol = Path(dosya)
            if not yol.is_file():
                continue
            token = secrets.token_urlsafe(12)
            _Handler.shared_files[token] = {"path": yol, "created": time.time()}
            sonuclar.append(self._paylasim_sonucu(token, yol))
            
        if not sonuclar:
            return {"ok": False, "error": "Geçerli dosya seçilmedi."}
            
        return {"ok": True, "files": sonuclar}

    def paylasim_stop(self) -> None:
        from api.server import _Handler
        for token, bilgi in list(_Handler.shared_files.items()):
            sorunlar = self._paylasim_kaynaklarini_temizle(bilgi)
            if sorunlar:
                mesaj = "Payla\u015f\u0131m temizli\u011fi tamamlanamad\u0131: " + "; ".join(sorunlar)
                try:
                    self.manager.store.log("error", mesaj)
                except Exception:
                    pass
                if self._window:
                    try:
                        self._window.evaluate_js("toast(" + json.dumps(mesaj) + ", true)")
                    except Exception:
                        pass
                tepsi = getattr(self, "_tepsi", None)
                if tepsi:
                    try:
                        tepsi.notify(mesaj, "AfuDM")
                    except Exception:
                        print(mesaj)
                elif not self._window:
                    print(mesaj)
            else:
                _Handler.shared_files.pop(token, None)
        if hasattr(self, "_tunel"):
            self._tunel.stop()
        if hasattr(self, "_paylasim_sunucusu"):
            self._paylasim_sunucusu.stop()

    def dosya_ac(self, gid: str) -> dict:
        """Inen dosyayi kendi programiyla ac (klasoru degil dosyayi).

        Dosya adi bilinmiyorsa ya da henuz diskte yoksa klasore duseriz:
        kullanici bos bir hata yerine en azindan yerini gorur."""
        for item in self.manager.snapshot()["items"]:
            if item["gid"] != gid:
                continue
            klasor = item.get("dir") or self.manager.current_download_dir()
            ad = item.get("filename") or ""
            hedef = self.manager.resolve_item_path(gid)
            if hedef and hedef.is_file():
                os.startfile(str(hedef))  # noqa: S606 — Windows kabugu
            else:
                open_in_explorer(str(klasor))
            return {"ok": True}
        return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}

    def item_yolu(self, gid: str) -> dict:
        """Satirin kaynak adresi ve diskteki tam yolu (sag tik menusu icin)."""
        for item in self.manager.snapshot()["items"]:
            if item["gid"] != gid:
                continue
            klasor = item.get("dir") or self.manager.current_download_dir()
            ad = item.get("filename") or ""
            hedef = self.manager.resolve_item_path(gid)
            if hedef:
                klasor = str(hedef.parent)
                ad = hedef.name
            return {"ok": True, "url": item.get("source") or "", "klasor": str(klasor),
                    "ad": ad, "yol": str(Path(klasor) / ad) if ad else str(klasor)}
        return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}

    def panoya_kopyala(self, metin: str = "") -> dict:
        """Arayuzden gelen metni panoya yaz.

        WebView2 icinde navigator.clipboard kullanici hareketi olmadan ya da
        guvenli baglam disinda SESSIZCE dusuyor; Windows'un kendi `clip`
        komutu her kosulda calisir (core/chrome_kurulum.panoya_kopyala)."""
        metin = str(metin or "")
        if not metin:
            return {"ok": False}
        return {"ok": chrome_kurulum.panoya_kopyala(metin)}

    def panodan_oku(self) -> dict:
        """Panodaki metin (sag tik > Yapistir icin).

        Tarayici tarafinda navigator.clipboard.readText() WebView2'de izin
        istiyor ve gomulu pencerede sessizce dusuyor; Windows panosunu dogrudan
        okuyoruz (core/clipboard.py)."""
        try:
            return {"ok": True, "metin": clipboard.read_text()}
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    # --- ozel baslik cubugu (bkz. core/pencere.py) ------------------------
    def pencere_kucult(self) -> dict:
        if self._window:
            self._window.minimize()
        return {"ok": True}

    def pencere_buyut(self) -> dict:
        if self._window:
            if pencere.buyutulmus_mu(self._window):
                self._window.restore()
            else:
                self._window.maximize()
        return self.pencere_durumu()

    def pencere_kapat(self) -> dict:
        # qBittorrent tipi davranis: X uygulamayi kapatmaz, tepsiye gizler.
        # Tepsi simgesi kurulamadiysa gizlemek pencereyi erisilmez yapacagi icin
        # o durumda gercek kapatma guvenli geri donustur.
        tepside = bool(
            self._window
            and self._tepsi is not None
            and self.manager.store.get("tepsiye_kucult")
            and not self._cikiliyor
        )
        if self._window:
            if tepside:
                self._window.hide()
                self._tepsi_bildirimi()
            else:
                self._window.destroy()
        return {"ok": True, "tepside": tepside}

    def pencere_durumu(self) -> dict:
        return {
            "ok": True,
            "ozel": self._ozel_baslik,
            "buyuk": bool(self._window and pencere.buyutulmus_mu(self._window)),
        }

    def pencere_kenar(self, kenar: str) -> dict:
        return {"ok": bool(self._window and pencere.kenardan_boyutla(self._window, kenar))}

    # --- Chrome'a uzanti ekleme (bkz. core/chrome_kurulum.py) ---------------
    def chrome_durum(self) -> dict:
        return {
            "ok": True,
            "chrome": bool(chrome_kurulum.chrome_yolu()),
            "klasor": str(chrome_kurulum.uzanti_klasoru()),
            "adres": "chrome://extensions/",
        }

    def chrome_hazirla(self) -> dict:
        """Pencere acildi: eslestirmeyi 10 dk ac ki ELLE kurulumda da uzanti
        kendiliginden baglansin; "baglandi" bu andan sonraki eslesmeye bakar."""
        self._chrome_baslangic = time.time()
        self.local_api.open_pairing(600.0)
        return self.chrome_durum()

    def chrome_otomatik(self) -> dict:
        self._chrome_baslangic = self._chrome_baslangic or time.time()
        # Eslestirme penceresi kurulumdan ONCE: uzanti kurulur kurulmaz baglanir.
        baslatildi = self._chrome.baslat(once=lambda: self.local_api.open_pairing(600.0))
        return {"ok": True, "baslatildi": baslatildi}

    def chrome_ilerleme(self) -> dict:
        durum = self._chrome.durum()
        durum["baglandi"] = self.local_api.son_eslesme >= self._chrome_baslangic > 0
        return {"ok": True, **durum}

    def chrome_kopyala(self, ne: str) -> dict:
        metin = "chrome://extensions/" if ne == "adres" else str(chrome_kurulum.uzanti_klasoru())
        return {"ok": chrome_kurulum.panoya_kopyala(metin)}

    def chrome_ac(self) -> dict:
        # chrome:// adresi komut satirindan ACILMAZ: bos sekme acilir, adres kopyalanir.
        chrome_kurulum.panoya_kopyala("chrome://extensions/")
        return {"ok": bool(chrome_kurulum.sayfayi_ac())}

    def probe(self, url: str) -> dict:
        try:
            return {"ok": True, "info": self.manager.probe_video(url)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}


# --- komut satirindan gelen link (.torrent cift tiklama, magnet:) -----------
def argvden_link(argv: list[str]) -> str:
    """Gezgin/tarayici "AfuDM.exe <yol|magnet>" diye cagirir; ilk anlamli baglanti."""
    for arg in argv[1:]:
        deger = arg.strip().strip('"')
        if not deger or deger.startswith("-"):
            continue
        if deger.startswith(("magnet:", "http://", "https://", "ftp://")):
            return deger
        if deger.lower().endswith(".torrent") and Path(deger).exists():
            return str(Path(deger).resolve())
    return ""


def calisan_ornege_yolla(link: str = "") -> bool:
    """AfuDM zaten aciksa isi ONA ver ve IKINCI PENCERE ACMA.

    Link varsa eklenir; link yoksa (kullanici kisayola tekrar tikladi) acik
    pencere one getirilir. Iki ornek ayni veritabanina ve ayni motora
    asilmasin diye: her ikinci acilis buradan doner.
    """
    try:
        bilgi = json.loads((paths.DATA / "api_endpoint.json").read_text("utf-8"))
        port, token = int(bilgi["port"]), str(bilgi["token"])
    except (OSError, ValueError, KeyError):
        return False
    basliklar = {"Content-Type": "application/json", "X-AfuDM-Token": token}
    try:
        if link:
            govde = json.dumps({"url": link, "interactive": True}).encode("utf-8")
            istek = urllib.request.Request(
                f"http://127.0.0.1:{port}/add", data=govde, headers=basliklar)
            with urllib.request.urlopen(istek, timeout=3) as yanit:
                if json.loads(yanit.read().decode("utf-8")).get("ok") is not True:
                    return False
        # Pencereyi one getir: linksiz acilista tek is budur.
        istek = urllib.request.Request(
            f"http://127.0.0.1:{port}/show", headers={"X-AfuDM-Token": token})
        with urllib.request.urlopen(istek, timeout=3) as yanit:
            return json.loads(yanit.read().decode("utf-8")).get("ok") is True
    except (urllib.error.URLError, OSError, ValueError):
        return False       # acik degil (ya da baska bir program o portta)


def build_tray(window, manager: Manager, api: Api | None = None):
    """Sistem tepsisi simgesi; kurulan simgeyi dondurur (kurulamazsa None).

    Donen deger onemli: simge YOKSA "kucultunce tepsiye in" davranisi
    kapatilir, yoksa pencere gizlenir ve uygulamaya ulasilamaz."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        # Paketlenmis exe'de konsol YOK: sebep veritabanina da yazilir,
        # yoksa "simge neden gorunmuyor" disaridan anlasilmiyor.
        manager.store.log("warn", f"tepsi simgesi kurulamadi (import): {exc}")
        return None

    image = Image.new("RGBA", (64, 64), (20, 24, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.polygon([(32, 46), (18, 28), (46, 28)], fill=(91, 157, 255, 255))
    draw.rectangle([26, 12, 38, 28], fill=(91, 157, 255, 255))
    draw.rectangle([14, 52, 50, 56], fill=(167, 139, 250, 255))

    def show(_icon=None, _item=None) -> None:
        # Gizli VE simge durumunda olabilir: one_getir ikisini de duzeltir.
        try:
            pencere.one_getir(window)
        except Exception:
            try:
                window.show()
            except Exception:
                pass

    def hide(_icon=None, _item=None) -> None:
        try:
            window.hide()
        except Exception:
            pass

    def quit_app(icon=None, _item=None) -> None:
        if api is not None:
            api._cikiliyor = True
        if icon:
            icon.stop()
        try:
            window.destroy()
        except Exception:
            os._exit(0)

    def yazi(anahtar):
        # pystray metin olarak fonksiyon kabul eder: menu her acildiginda
        # yeniden okunur, boylece dil ayari degisince tepsi de guncellenir.
        return lambda _item: lang.t(anahtar, str(manager.store.get("language", "auto")))

    menu = pystray.Menu(
        pystray.MenuItem(yazi("tray.show"), show, default=True),
        pystray.MenuItem(yazi("tray.hide"), hide),
        pystray.MenuItem(yazi("tray.pauseAll"), lambda i, t: manager.pause_all()),
        pystray.MenuItem(yazi("tray.resumeAll"), lambda i, t: manager.resume_all()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(yazi("tray.quit"), quit_app),
    )
    icon = pystray.Icon("AfuDM", image, "AfuDM", menu)

    def calistir() -> None:
        try:
            icon.run()
        except Exception as exc:                 # simge kurulamazsa sebebi kalsin
            manager.store.log("warn", f"tepsi simgesi calismadi: {exc!r}")

    threading.Thread(target=calistir, daemon=True).start()
    return icon


def main() -> int:
    paths.ensure_dirs()
    if "--headless" in sys.argv or "--sunucu" in sys.argv:
        # Arayuzsuz kip AYRI bir giristir (headless.py): orada `webview` HIC
        # import edilmez. Kaynaktan calisirken kullaniciyi oraya yonlendiririz.
        # PAKETLENMIS exe'de ayri bir giris dosyasi yoktur (tek dosya), bu
        # yuzden orada servisi dogrudan burada calistiririz.
        import headless
        if getattr(sys, "frozen", False):
            return headless.calistir()
        print("Arayuzsuz kip icin: afuadm server start  (veya python headless.py)")
        return 2
    link = protocol_link(argvden_link(sys.argv))
    # Tepside basla: Baslangic kisayolu bu bayrakla cagirir (bkz. core/baslangic.py)
    tepside_basla = "--tepside" in sys.argv
    if calisan_ornege_yolla(link):
        return 0                      # zaten acik: is ona verildi, ikinci pencere yok
    # Ayni klasorde headless servis calisiyorsa IKINCI SUREC ACMA: aksi halde
    # iki surec ayni SQLite ve ayni aria2 oturumuna asilir.
    _rapor = ornek.cakisma_raporu(ornek.KIP_MASAUSTU)
    if _rapor["cakisma"]:
        print(lang.t(_rapor["mesaj_anahtari"], "auto"))
        return 0
    if not paths.ARIA2C.exists():
        print(f"HATA: motor bulunamadi -> {paths.ARIA2C}")
        return 2

    _kilit = ornek.OrnekKilidi(ornek.KIP_MASAUSTU)
    _kilit.al()
    manager = Manager()
    tracker_saglik.klasoru_hazirla()   # kullanici .txt atabilsin diye hep dursun
    try:
        manager.start()
    except Exception as exc:
        print(f"HATA: aria2 baslatilamadi: {exc}")
        return 3

    # HER ACILISTA 6811'den basla. Onceki calismada port dolu oldugu icin
    # 6812'ye dusulmusse bu DEGER KAYDEDILIP kalici olurdu: uygulama hep
    # 6812'de acilir, uzanti ise 6811'i denerdi ve "AfuDM kapali" derdi.
    # Kayit artik yalnizca "su an hangi port" bilgisi; baslangic noktasi degil.
    local_api = LocalAPI(manager, port=int(manager.store.get("api_listen_port") or VARSAYILAN_API_PORT),
                         lan=bool(manager.store.get("lan_erisimi")))
    try:
        port = local_api.start()
        manager.store.set("api_port", port)
        manager.store.set("api_port", port)
    except Exception as exc:
        print(f"UYARI: yerel API acilamadi: {exc}")

    _kilit.guncelle(api_port=local_api.port)
    servis = AfuDMServis(manager, kip=ornek.KIP_MASAUSTU)
    api = Api(manager, local_api, servis)
    # Ayar "sunucu acik" ise yonetim sunucusunu da ac. Anahtar yoksa ACILMAZ:
    # anahtarsiz sunucu hicbir sey yapamaz, sahte bir guven verir.
    if manager.store.get("sunucu_acik") and servis.erisim.yonetici_var_mi():
        _sonuc = servis.sunucu_baslat()
        if _sonuc.get("ok"):
            _kilit.guncelle(sunucu_port=servis.sunucu.port,
                            sunucu_adres=servis.sunucu.adres)
        else:
            print("UYARI: yonetim sunucusu acilamadi: %s" % _sonuc.get("error"))
    pencere.webview2_hazirligini_yama()  # CSS app-region: drag, ilk sayfadan once
    _px, _py, _pw, _ph, _min_w, _min_h = pencere_boyutu()
    _pencere_kwargs: dict[str, Any] = dict(
        js_api=api,
        width=_pw,
        height=_ph,
        min_size=(_min_w, _min_h),
        background_color="#14181F",
        text_select=False,
        hidden=tepside_basla,
    )
    if _px is not None and _py is not None:
        _pencere_kwargs["x"] = _px
        _pencere_kwargs["y"] = _py
    window = webview.create_window(
        lang.t("window.title", str(manager.store.get("language", "auto"))),
        str(paths.UI / "index.html"),
        **_pencere_kwargs,
    )
    api._window = window
    from api.server import _Handler as _ApiHandler  # noqa: E402
    _ApiHandler.servis = servis          # /capabilities tek kaynaktan
    _ApiHandler.on_ask = api.tarayicidan_sor
    _ApiHandler.on_show = lambda: pencere.one_getir(window)

    # Uzanti "Sayfadaki linkleri gönder": pencere one getirilir; UI hazirsa
    # panel acilip metin konur, hazir degilse sayfa yuklenince islenir.
    _bekleyen_linkgrabber: list = [None]  # [metin, dosya] | None

    def linkgrabber_devret(metin: str, dosya: bool) -> None:
        _bekleyen_linkgrabber[0] = {"metin": metin, "dosya": dosya}
        try:
            pencere.one_getir(window)
            window.evaluate_js(
                "window.afudmLinkgrabber(%s, %s)"
                % (json.dumps(metin), "true" if dosya else "false")
            )
        except Exception:
            pass  # UI henuz yuklenmemis; sayfa_hazir devralir

    _ApiHandler.on_linkgrabber = linkgrabber_devret

    def tepsi_bildirimi() -> None:
        # Windows 11 YENI bir uygulamanin tepsi simgesini varsayilan olarak
        # "gizli simgeler" (^) altina koyar ve bu disaridan degistirilemez.
        # Kullanici pencerenin nereye gittigini bilsin diye BIR KEZ soylenir.
        if manager.store.get("tepsi_bildirimi_yapildi"):
            return
        manager.store.set("tepsi_bildirimi_yapildi", True)
        simge = getattr(api, "_tepsi", None)
        if simge is None:
            return
        try:
            simge.notify(
                lang.t("tray.hidden", str(manager.store.get("language", "auto"))), "AfuDM"
            )
        except Exception:
            pass

    api._tepsi_bildirimi = tepsi_bildirimi
    manager.windows_notify = lambda baslik, metin: getattr(api, "_tepsi", None) and api._tepsi.notify(metin, baslik)

    def baslik_hazir() -> None:
        try:
            pencere.kapatinca_gizle(
                window,
                # Tepsi simgesi kurulamadiysa GIZLEME: pencereye donus yolu kalmaz.
                lambda: bool(manager.store.get("tepsiye_kucult"))
                and getattr(api, "_tepsi", None) is not None,
                lambda: bool(api._cikiliyor),
                tepsi_bildirimi,
            )
        except Exception as exc:
            print(f"UYARI: X ile tepsiye gizleme kurulamadi: {exc}")
        try:
            ozel = pencere.basligi_kaldir(window)
        except Exception as exc:  # kaldirilamazsa Windows basligi kalir, uygulama calisir
            print(f"UYARI: ozel baslik kurulamadi: {exc}")
            ozel = False
        api._ozel_baslik = ozel

    def sayfa_hazir() -> None:
        # Pencere gosterildiginde sayfa henuz yuklenmemis olabilir (evaluate_js
        # o anda istisna firlatir); dugmeleri sayfa yuklenince goster.
        try:
            window.evaluate_js("window.afudmPencere && window.afudmPencere()")
        except Exception:
            pass
        # Cift tiklanan .torrent / magnet: kaydetme penceresinde acilsin
        if link:
            api.tarayicidan_sor({"url": link})
        # UI yuklenmeden gelen LinkGrabber handoff'u da simdi islenir
        bekleyen = _bekleyen_linkgrabber[0]
        if bekleyen:
            _bekleyen_linkgrabber[0] = None
            window.evaluate_js(
                "window.afudmLinkgrabber(%s, %s)"
                % (json.dumps(bekleyen["metin"]), "true" if bekleyen["dosya"] else "false")
            )

    window.events.shown += baslik_hazir
    window.events.loaded += sayfa_hazir

    watcher = clipboard.ClipboardWatcher(
        on_link=lambda url: window.evaluate_js(
            "window.afudmClipboard(%s)" % json.dumps(url)
        ),
        is_enabled=lambda: bool(manager.store.get("clipboard_watch")),
        get_extensions=lambda: str(manager.store.get("clipboard_exts", "")),
    )

    def on_start() -> None:
        # ONCE tepsi: pano izleyicisi patlarsa simge de kurulmadan kalirdi.
        api._tepsi = build_tray(window, manager, api)
        if tepside_basla and api._tepsi is None:
            # Simge yoksa gizli baslamak uygulamayi erisilmez yapardi.
            manager.store.log("warn", "tepsi simgesi yok: pencere gosteriliyor")
            window.show()
        try:
            watcher.prime()
            watcher.start()
        except Exception as exc:
            print(f"UYARI: pano izleyici baslatilamadi: {exc}")

    try:
        webview.start(on_start, debug=bool(os.environ.get("AFUDM_DEBUG")))
    finally:
        watcher.stop()
        servis.sunucu_durdur()
        api.paylasim_stop()
        local_api.stop()
        manager.stop()
        _kilit.birak()
    return 0


if __name__ == "__main__":
    sys.exit(main())
