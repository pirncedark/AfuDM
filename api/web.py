# -*- coding: utf-8 -*-
"""Yonetim sunucusu (HTTP) — v2.1 Headless Server.

Bu sunucu masaustu arayuzuyle AYNI servis katmanini (`core.servis.AfuDMServis`)
cagirir; burada hicbir is mantigi tekrarlanmaz. Gorevi yalnizca: HTTP'yi
cozmek, ROLU dogrulamak, hiz sinirini uygulamak ve yaniti JSON'a cevirmek.

GUVENLIK — NE YAPAR, NE YAPMAZ
------------------------------
YAPAR:
  * Her istek bir ERISIM ANAHTARI ile dogrulanir (SHA-256 ozetiyle, sabit
    zamanli karsilastirma). Anahtarsiz hicbir veri donmez.
  * Rol denetimi: `salt_okur` yalnizca okur; yazma/ayar/yonetim `yonetici`.
  * IP basina hiz sinirlama ve ust uste hatali denemede gecici kilit.
  * Origin allowlist + durum degistiren isteklerde zorunlu ozel baslik
    (`X-AfuDM-CSRF`). Bu baslik tarayicidan ONUCUS (preflight) olmadan
    gonderilemez; onucus de yalnizca izinli origin'e olumlu doner.
  * Anahtar, parola, cerez ve sorgu dizesi HICBIR YERE yazilmaz; erisim
    gunlugu tamamen kapalidir.
YAPMAZ:
  * TLS YOKTUR. Trafik duz HTTP'dir. "lan" kipinde yalnizca ayni yerel agdaki
    cihazlar erisebilir; internete acmak KULLANICININ kendi yonlendirmesiyle
    olur ve bu durumda gizlilik GARANTI EDILMEZ. Arayuz bunu acikca yazar.
  * Bu bir DDoS kalkani DEGILDIR; sayaclar surec omrundedir.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core import erisim, paths
from core.hata import hata_json

# Durum degistiren isteklerde aranan ozel baslik (CSRF kalkani).
CSRF_BASLIK = "X-AfuDM-CSRF"
ANAHTAR_BASLIK = "X-AfuDM-Key"
OTURUM_BASLIK = "X-AfuDM-Oturum"

# (yol, gereken_izin). Burada OLMAYAN yol 404 doner: sessiz gecis yoktur.
GET_YOLLARI: dict[str, str] = {
    "/api/yetenekler": "oku",
    "/api/durum": "oku",
    "/api/liste": "oku",
    "/api/ayarlar": "oku",
    "/api/olaylar": "oku",
    "/api/anahtarlar": "yonet",
    "/api/istemciler": "yonet",
    "/api/profiller": "yonet",
}

POST_YOLLARI: dict[str, str] = {
    "/api/oturum": "oku",
    "/api/oturum/kapat": "oku",
    "/api/ekle": "yaz",
    "/api/kontrol": "yaz",
    "/api/yeniden-dene": "yaz",
    "/api/temizle": "yaz",
    "/api/hiz-profili": "yaz",
    "/api/baglanti-ayarla": "yaz",
    "/api/ayarlar": "ayar",
    "/api/anahtar/olustur": "yonet",
    "/api/anahtar/rotasyon": "yonet",
    "/api/anahtar/iptal": "yonet",
    "/api/anahtar/sil": "yonet",
    "/api/anahtar/rol": "yonet",
    "/api/istemci/iptal": "yonet",
    "/api/istemci/temizle": "yonet",
    "/api/kilit/temizle": "yonet",
    "/api/profil/kaydet": "yonet",
    "/api/profil/sil": "yonet",
    "/api/profil/etkinlestir": "yonet",
    "/api/sunucu/durdur": "yonet",
}

VARLIKLAR = {
    "/varlik/i18n.js": ("i18n.js", "application/javascript; charset=utf-8"),
    "/varlik/style.css": ("style.css", "text/css; charset=utf-8"),
}


def lan_ip() -> str:
    """Makinenin yerel ag adresi. UDP rota secimi — PAKET GITMEZ."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return ""
    return "" if not ip or ip.startswith("127.") else ip


class _PaylasmayanSunucu(ThreadingHTTPServer):
    """Portu PAYLASMAYAN sunucu (bkz. api/server.py'deki ayni gerekce).

    Windows SO_REUSEADDR ile ayni porta IKINCI bir surecin baglanmasina izin
    verir ve istekler iki surece rastgele dagilir. Burada bu ACIKCA yasaklanir
    ki "port dolu" hatasi gercekten gorulsun."""

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class _Handler(BaseHTTPRequestHandler):
    server_version = "AfuDM-Panel"
    sunucu = None  # YonetimSunucusu — calisma aninda atanir

    # --- gunluk: TAMAMEN KAPALI ------------------------------------------
    def log_message(self, fmt: str, *args) -> None:
        """Erisim gunlugu YOKTUR.

        BaseHTTPRequestHandler varsayilani istek satirini (yani sorgu dizesini)
        stderr'e basar. Anahtarin sorgu parametresiyle gelmesi mumkun oldugu
        icin bu satir tamamen susturulur — token/cerez/ozel parametre asla
        bir yere yazilmaz."""
        return

    def log_error(self, fmt: str, *args) -> None:
        return

    # --- yardimcilar ------------------------------------------------------
    @property
    def _servis(self):
        return self.sunucu.servis

    def _ip(self) -> str:
        return self.client_address[0] if self.client_address else "?"

    def _izinli_originler(self) -> set[str]:
        """Bos ayar = EN SIKI: yalnizca sunucunun kendi adresleri."""
        ayar = str(self._servis.store.get("sunucu_izinli_originler") or "")
        ozel = {p.strip().rstrip("/") for p in ayar.replace(",", "\n").split("\n")
                if p.strip()}
        port = self.sunucu.port
        kendi = {"http://127.0.0.1:%d" % port, "http://localhost:%d" % port}
        ip = self.sunucu.lan_ip
        if ip:
            kendi.add("http://%s:%d" % (ip, port))
        return kendi | ozel

    def _origin_uygun(self) -> bool:
        """Origin yoksa (curl/CLI) gecerdir; VARSA allowlist'te olmalidir."""
        origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        if not origin:
            return True
        return origin in self._izinli_originler()

    def _cors(self) -> None:
        origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        if origin and origin in self._izinli_originler():
            # JOKER YOK: yalnizca izinli origin yansitilir.
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, %s, %s, %s"
                         % (ANAHTAR_BASLIK, OTURUM_BASLIK, CSRF_BASLIK))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def _send(self, code: int, payload: dict, ek: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for ad, deger in (ek or {}).items():
            self.send_header(ad, deger)
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass  # istemci kapatti

    def _hata(self, durum: int, kod: str, mesaj: str, ek: dict | None = None) -> None:
        """Sozlesme: `code` makine icin, `message`/`error` insan icin."""
        self._send(durum, {"ok": False, "code": kod, "message": mesaj,
                           "error": mesaj}, ek)

    def _govde(self) -> dict:
        try:
            uzunluk = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if uzunluk <= 0 or uzunluk > 2_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(uzunluk).decode("utf-8")) or {}
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return {}

    # --- kimlik + rol -----------------------------------------------------
    def _kimlik(self) -> tuple[dict | None, str]:
        """(anahtar_kaydi, hata_kodu). Anahtar SADECE baslikta beklenir.

        Sorgu dizesinde anahtar KABUL EDILMEZ: URL'ler tarayici gecmisine ve
        araci gunluklerine dusebilir."""
        sunulan = (self.headers.get(ANAHTAR_BASLIK) or "").strip()
        if not sunulan:
            yetki = (self.headers.get("Authorization") or "").strip()
            if yetki.lower().startswith("bearer "):
                sunulan = yetki[7:].strip()
        if not sunulan:
            return None, "ANAHTAR_GEREKLI"
        kayit = self._servis.erisim.dogrula(sunulan)
        if kayit is None:
            return None, "GECERSIZ_ANAHTAR"
        return kayit, ""

    def _yetkilendir(self, izin: str, yazma: bool) -> dict | None:
        """Tum kapi kontrolleri tek yerde. Gecerse anahtar kaydi doner."""
        ip = self._ip()
        izin_ver, kalan = self._servis.limitci.izin_ver(ip)
        if not izin_ver:
            self.sunucu.reddedilen += 1
            self._hata(429, "COK_FAZLA_ISTEK",
                       "cok fazla istek — %d saniye sonra tekrar dene" % int(kalan + 1),
                       {"Retry-After": str(int(kalan + 1))})
            return None
        if not self._origin_uygun():
            self.sunucu.reddedilen += 1
            self._hata(403, "ORIGIN_REDDEDILDI",
                       "bu adresten gelen istekler izinli degil")
            return None
        if yazma and not self.headers.get(CSRF_BASLIK):
            self.sunucu.reddedilen += 1
            self._hata(403, "CSRF_BASLIGI_YOK",
                       "durum degistiren istek %s basligi ister" % CSRF_BASLIK)
            return None
        kayit, kod = self._kimlik()
        if kayit is None:
            self._servis.limitci.hatali(ip)
            self.sunucu.reddedilen += 1
            mesaj = ("erisim anahtari gerekli" if kod == "ANAHTAR_GEREKLI"
                     else "anahtar gecersiz veya iptal edilmis")
            self._hata(401, kod, mesaj)
            return None
        self._servis.limitci.basarili(ip)
        if not erisim.izinli(kayit["rol"], izin):
            self.sunucu.reddedilen += 1
            self._hata(403, "YETKI_YOK",
                       "bu islem icin 'yonetici' rolu gerekir (rolun: %s)"
                       % kayit["rol"])
            return None
        # Oturum takibi: kim bagli ekrani bunu okur. Ayar kapaliysa tutulmaz.
        oturum = (self.headers.get(OTURUM_BASLIK) or "").strip()
        if oturum and self._servis.store.get("sunucu_istemci_kaydi"):
            if self._servis.erisim.oturum_dokun(oturum, ip) is None:
                self._hata(401, "OTURUM_IPTAL",
                           "oturumun iptal edildi — yeniden baglan")
                return None
        self._servis.erisim.kullanim_isle(kayit["id"])
        self.sunucu.istek_sayisi += 1
        return kayit

    # --- statik sayfalar --------------------------------------------------
    def _dosya_gonder(self, yol, tur: str) -> None:
        try:
            govde = yol.read_bytes()
        except OSError:
            self._hata(404, "SAYFA_YOK", "dosya bulunamadi")
            return
        self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        try:
            self.wfile.write(govde)
        except OSError:
            pass

    # ==================================================================
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204 if self._origin_uygun() else 403)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        yol = parsed.path.rstrip("/") or "/"
        sorgu = parse_qs(parsed.query)

        # --- anahtarsiz, bilgi amacli
        if yol == "/api/ping":
            self._send(200, {"ok": True, "app": "AfuDM", "panel": True})
            return
        if yol in ("/", "/panel"):
            self._dosya_gonder(paths.UI / "panel.html", "text/html; charset=utf-8")
            return
        if yol in VARLIKLAR:
            ad, tur = VARLIKLAR[yol]
            self._dosya_gonder(paths.UI / ad, tur)
            return

        izin = GET_YOLLARI.get(yol)
        if izin is None:
            self._hata(404, "BILINMEYEN_YOL", "bilinmeyen yol")
            return
        kayit = self._yetkilendir(izin, yazma=False)
        if kayit is None:
            return
        try:
            self._send(200, self._get_calistir(yol, sorgu, kayit))
        except Exception as exc:
            govde = hata_json(exc)
            self._send(400 if govde.get("code") != "INTERNAL" else 500, govde)

    def _get_calistir(self, yol: str, sorgu: dict, kayit: dict) -> dict:
        s = self._servis
        if yol == "/api/yetenekler":
            return {**s.yetenekler(), "rol": kayit["rol"]}
        if yol == "/api/durum":
            return {**s.durum(), "rol": kayit["rol"]}
        if yol == "/api/liste":
            return s.liste(sorgu.get("filtre", [""])[0], sorgu.get("arama", [""])[0])
        if yol == "/api/ayarlar":
            return s.ayarlar()
        if yol == "/api/olaylar":
            return s.olaylar(sorgu.get("gid", [""])[0],
                             int(sorgu.get("limit", ["60"])[0] or 60))
        if yol == "/api/anahtarlar":
            return s.anahtarlar()
        if yol == "/api/istemciler":
            return s.istemciler(int(sorgu.get("dakika", ["0"])[0] or 0))
        if yol == "/api/profiller":
            return s.profiller()
        return {"ok": False, "code": "BILINMEYEN_YOL", "error": "bilinmeyen yol"}

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        yol = parsed.path.rstrip("/") or "/"
        izin = POST_YOLLARI.get(yol)
        if izin is None:
            self._hata(404, "BILINMEYEN_YOL", "bilinmeyen yol")
            return
        # /api/oturum ve /api/oturum/kapat okuma izniyle calisir ama yine de
        # CSRF basligi ister: tarayicidan gelen her POST ayni kapidan gecer.
        kayit = self._yetkilendir(izin, yazma=True)
        if kayit is None:
            return
        veri = self._govde()
        try:
            self._send(200, self._post_calistir(yol, veri, kayit))
        except Exception as exc:
            govde = hata_json(exc)
            self._send(400 if govde.get("code") != "INTERNAL" else 500, govde)

    def _post_calistir(self, yol: str, veri: dict, kayit: dict) -> dict:
        s = self._servis
        if yol == "/api/oturum":
            oturum = ""
            if s.store.get("sunucu_istemci_kaydi"):
                oturum = s.erisim.oturum_ac(
                    kayit["id"], kayit["rol"], self._ip(),
                    (self.headers.get("User-Agent") or "")[:120])
            return {"ok": True, "rol": kayit["rol"], "anahtar_adi": kayit["ad"],
                    "oturum": oturum, "csrf_baslik": CSRF_BASLIK,
                    "izinler": sorted(erisim.IZINLER.get(kayit["rol"], set()))}
        if yol == "/api/oturum/kapat":
            oturum = (self.headers.get(OTURUM_BASLIK) or "").strip()
            kayitli = s.erisim.oturum_dokun(oturum, self._ip()) if oturum else None
            if kayitli:
                s.erisim.oturum_iptal(kayitli["id"])
            return {"ok": True}
        if yol == "/api/ekle":
            return s.ekle(veri)
        if yol == "/api/kontrol":
            return s.kontrol(veri.get("action") or veri.get("eylem") or "",
                             veri.get("gid") or "",
                             bool(veri.get("delete_files")))
        if yol == "/api/baglanti-ayarla":
            return s.baglanti_ayarla(veri.get("gid") or "",
                                     baglanti=veri.get("baglanti"),
                                     hiz_kb=veri.get("hiz_kb"))
        if yol == "/api/yeniden-dene":
            return s.yeniden_dene(int(veri.get("id") or 0))
        if yol == "/api/temizle":
            return s.bitmisleri_temizle()
        if yol == "/api/hiz-profili":
            return s.hiz_profili(str(veri.get("profil") or ""))
        if yol == "/api/ayarlar":
            return s.ayar_kaydet(veri.get("settings") or veri)
        if yol == "/api/anahtar/olustur":
            return s.anahtar_olustur(veri.get("ad") or "", veri.get("rol") or "",
                                     veri.get("not_metni") or "")
        if yol == "/api/anahtar/rotasyon":
            return s.anahtar_rotasyon(int(veri.get("id") or 0))
        if yol == "/api/anahtar/iptal":
            return s.anahtar_iptal(int(veri.get("id") or 0))
        if yol == "/api/anahtar/sil":
            return s.anahtar_sil(int(veri.get("id") or 0))
        if yol == "/api/anahtar/rol":
            return s.anahtar_rol_ayarla(int(veri.get("id") or 0),
                                        veri.get("rol") or "")
        if yol == "/api/istemci/iptal":
            return s.istemci_iptal(int(veri.get("id") or 0))
        if yol == "/api/istemci/temizle":
            return s.istemcileri_temizle(int(veri.get("gun") or 7))
        if yol == "/api/kilit/temizle":
            return s.kilitleri_temizle()
        if yol == "/api/profil/kaydet":
            return s.profil_kaydet(veri)
        if yol == "/api/profil/sil":
            return s.profil_sil(int(veri.get("id") or 0))
        if yol == "/api/profil/etkinlestir":
            return s.profil_etkinlestir(int(veri.get("id") or 0))
        if yol == "/api/sunucu/durdur":
            # Kendini kapatan istek: yanit gonderildikten SONRA kapanmali,
            # yoksa istemci "baglanti koptu" hatasi gorur.
            threading.Timer(0.5, s.sunucu_durdur).start()
            return {"ok": True, "kapaniyor": True}
        return {"ok": False, "code": "BILINMEYEN_YOL", "error": "bilinmeyen yol"}


class YonetimSunucusu:
    """Panel + API sunucusu. `AfuDMServis` disinda hicbir seye bagli degildir."""

    def __init__(self, servis, adres: str = "yerel", port: int = 6821) -> None:
        self.servis = servis
        self.adres = "lan" if str(adres).lower() == "lan" else "yerel"
        self.istenen_port = int(port or 6821)
        self.port = self.istenen_port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.baslangic = 0.0
        self.istek_sayisi = 0
        self.reddedilen = 0
        self.lan_ip = ""

    @property
    def calisiyor(self) -> bool:
        return self.httpd is not None and self.thread is not None and self.thread.is_alive()

    def start(self) -> int:
        """Portu ac. Dolu ise +9'a kadar dener; hicbiri acilmazsa HATA verir."""
        bind = "0.0.0.0" if self.adres == "lan" else "127.0.0.1"
        son_hata: Exception | None = None
        for port in range(self.istenen_port, self.istenen_port + 10):
            try:
                self.httpd = _PaylasmayanSunucu((bind, port), _Handler)
                self.port = port
                break
            except OSError as exc:
                son_hata = exc
        if self.httpd is None:
            raise RuntimeError(
                "yonetim sunucusu portu acilamadi (%d-%d): %s"
                % (self.istenen_port, self.istenen_port + 9, son_hata))
        self.lan_ip = lan_ip() if self.adres == "lan" else ""
        _Handler.sunucu = self
        self.baslangic = time.time()
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, name="afudm-panel", daemon=True)
        self.thread.start()
        return self.port

    def panel_url(self) -> str:
        return "http://127.0.0.1:%d/panel" % self.port

    def lan_url(self) -> str:
        if self.adres != "lan" or not self.lan_ip:
            return ""
        return "http://%s:%d/panel" % (self.lan_ip, self.port)

    def stop(self) -> None:
        if self.httpd is None:
            return
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        finally:
            self.httpd = None
            self.thread = None
            self.baslangic = 0.0
