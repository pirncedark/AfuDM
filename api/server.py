"""Yerel HTTP API — varsayilan 127.0.0.1, token zorunlu.

Tarayici uzantisi, Telegram kopru scripti veya baska bir araci buradan
AfuDM'e is verir. Her istek X-AfuDM-Token (veya ?token=) ile dogrulanir.

Kullanici Ayarlar'dan "Telefondan baglan" derse sunucu YEREL AGA acilir
(0.0.0.0) ve `/m` adresinde telefon arayuzu (ui/mobil.html) servis edilir.
Internete acilma YOKTUR: yalniz ayni Wi-Fi'deki cihazlar erisebilir ve
anahtarsiz hicbir sey yapilamaz.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from core import models, paths
from core.hata import hata_json

_LOG = logging.getLogger(__name__)


def _yol_kok_icinde(yol, kok) -> bool:
    """Resolve both paths before checking containment (including symlinks)."""
    try:
        return Path(yol).resolve().is_relative_to(Path(kok).resolve())
    except (OSError, RuntimeError, ValueError, TypeError):
        return False


def _origin_izinli(origin: str) -> bool:
    """Allow CORS only for browser extensions and loopback web clients."""
    from urllib.parse import urlparse
    if origin.startswith("chrome-extension://"):
        return bool(origin.removeprefix("chrome-extension://"))
    try:
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1")
    except ValueError:
        return False


def _indir_yolu(manager, gid):
    """Return a resolved download only when it remains under the active root."""
    yol = manager.resolve_item_path(gid)
    if not yol:
        return None
    yol = Path(yol).resolve()
    kok = Path(manager.current_download_dir()).resolve()
    if not yol.is_relative_to(kok):
        raise PermissionError("dosya indirme kokunun disinda")
    return yol


def _dosya_iznini_kisitla(yol) -> None:
    """Windows'ta dosyayi yalniz gecerli kullaniciya acan (icacls).

    Mirasi kapatir: ara klasorlerden 'Everyone' vb. devri gecmesin. TANIMLI
    BEST-EFFORT: herhangi bir basarisizlik startup'i/API'yi ASLA engellemez —
    token'in loglanmamasi asil guvenlik garantisidir, ACL ikincildir."""
    if os.name != "nt":
        return
    try:
        kullanici = os.environ.get("USERNAME", "").strip()
        if not kullanici:
            return
        subprocess.run(
            ["icacls", str(yol), "/inheritance:r", "/grant:r", f"{kullanici}:F"],
            capture_output=True,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        _LOG.exception("API dosya izinleri kisitlanamadi: %s", yol)


def _zamanla(s) -> float | None:
    """Eski adres geriye donuk uyumlnaktadir; tek kaynak `parse_time_spec`."""
    return models.parse_time_spec(s)


def _boolean_al(data: dict, anahtar: str) -> bool:
    """JSON booleanini okur; uyumlu true/false metinleri disinda tahmin etmez."""
    deger = data.get(anahtar, False)
    if isinstance(deger, bool):
        return deger
    if deger is None:
        return False
    if isinstance(deger, str):
        normal = deger.strip().lower()
        if normal in ("true", "1"):
            return True
        if normal in ("false", "0"):
            return False
    raise ValueError(f"{anahtar} boolean olmali (true/false/1/0)")


def load_or_create_token() -> str:
    paths.ensure_dirs()
    if paths.API_TOKEN_FILE.exists():
        token = paths.API_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    paths.API_TOKEN_FILE.write_text(token, encoding="utf-8")
    _dosya_iznini_kisitla(paths.API_TOKEN_FILE)
    return token


class _Handler(BaseHTTPRequestHandler):
    server_version = "AfuDM/1.0"
    manager = None       # calisma aninda atanir
    token = ""
    # Uzantinin anahtari otomatik alabilecegi kisa pencere. Kullanici
    # uygulamadan "Uzantiyi bagla" deyince acilir; suresi dolunca kapanir.
    pair_until = 0.0
    # Anahtar en son ne zaman verildi: "Chrome'a ekle" penceresi bununla
    # uzantinin gercekten baglandigini gosterir.
    son_eslesme = 0.0
    # Uzanti "interactive" isterse istek hemen baslamaz: uygulama kaydetme
    # penceresini acar. Uygulama ayarlar; None ise dogrudan eklenir.
    on_ask = None
    # Ikinci kez acilan AfuDM, acik olan pencereyi one getirsin diye cagirir.
    on_show = None
    # Uzanti "Sayfadaki linkleri gönder" dediginde ham metni LinkGrabber
    # paneline iletmek icin. None ise istek reddedilir (panel kapali/UI yok).
    on_linkgrabber = None
    # v2.1: ortak servis katmani (core/servis.AfuDMServis). Atanmissa
    # /capabilities yetenek listesini ORADAN alir — iki ayri liste tutup
    # birinin bayatlamasi diye bir sey olmaz.
    servis = None
    reliability = None
    rotate_token = None
    _rate: dict[str, list[float]] = {}
    shared_files: dict[str, dict] = {}

    # --- yardimcilar ------------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:  # konsolu kirletmesin
        pass

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and _origin_izinli(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-AfuDM-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _hata(self, durum: int, kod: str, mesaj: str) -> None:
        """Sozlesme hata yaniti: makine `code`, insan `message`, geriye-donuk
        uyumluluk `error` alanlarini BIRLIKTE tasimasi zorunludur (UI/mobil
        `error`'u okur, CLI `code`'u)."""
        self._send(durum, {"ok": False, "code": kod, "message": mesaj, "error": mesaj})

    def _telefona_dosya(self, gid: str):
        """gid -> diskteki gercek dosya. Yol ISTEMCIDEN ALINMAZ.

        Dosya indirme kokunun ICINDE degilse PermissionError atar; boylece
        bir sekilde kok disina yazilmis bir kayit da servis EDILEMEZ."""
        from pathlib import Path
        durum = {}
        try:
            durum = self.manager.rpc.tell_status(gid) or {}
        except Exception:
            durum = {}
        dosyalar = durum.get("files") or []
        ham = ""
        for girdi in dosyalar:
            if girdi.get("path"):
                ham = girdi["path"]
                break
        if not ham:
            kayit = self.manager.store.by_gid(gid) or {}
            ham = str(kayit.get("path") or "")
        if not ham:
            raise FileNotFoundError(gid)
        dosya = Path(ham).resolve()
        kok = Path(self.manager.current_download_dir()).resolve()
        if not dosya.is_relative_to(kok):
            raise PermissionError(str(dosya))
        if not dosya.is_file():
            raise FileNotFoundError(str(dosya))
        return dosya

    def _dosya_akit(self, dosya) -> None:
        """Dosyayi parca parca gonderir; buyuk dosya bellege ALINMAZ."""
        import mimetypes
        import urllib.parse
        tur = mimetypes.guess_type(dosya.name)[0] or "application/octet-stream"
        boyut = dosya.stat().st_size
        ad = urllib.parse.quote(dosya.name)
        self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(boyut))
        # RFC 5987: Turkce karakterli dosya adlari telefonda bozulmasin.
        self.send_header("Content-Disposition",
                         "attachment; filename*=UTF-8''" + ad)
        self.end_headers()
        with open(dosya, "rb") as kaynak:
            while True:
                parca = kaynak.read(256 * 1024)
                if not parca:
                    break
                try:
                    self.wfile.write(parca)
                except (BrokenPipeError, ConnectionResetError):
                    return  # telefon indirmeyi iptal etti

    def _authorized(self, query: dict, allow_query: bool = False) -> bool:
        header = self.headers.get("X-AfuDM-Token", "")
        supplied = header
        if allow_query and not supplied and query:
            supplied = query.get("token", [""])[0] or query.get("k", [""])[0]
        return bool(self.token) and secrets.compare_digest(supplied, self.token)


    def _rate_allowed(self) -> bool:
        """Small in-memory per-client limit; no token/IP is written to disk/logs."""
        key = self.client_address[0]; now = time.monotonic()
        hits = [t for t in self._rate.get(key, []) if now - t < 60]
        if len(hits) >= 120: self._rate[key] = hits; return False
        hits.append(now); self._rate[key] = hits; return True

    def _sayfa_gonder(self, yol) -> None:
        """Tek dosyalik arayuzu gonder (telefon icin; CSS/JS iceride gomulu)."""
    def _sayfa_gonder(self, yol, icerik_turu="text/html; charset=utf-8",
                      onbellek="no-store", ek_basliklar=None) -> None:
        """Telefon arayuzu ve PWA dosyalarini dogru basliklarla gonder."""
        try:
            govde = yol.read_bytes()
        except OSError:
            self._hata(404, "SAYFA_YOK", "sayfa bulunamadi")
            return
        self.send_response(200)
        self.send_header("Content-Type", icerik_turu)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", onbellek)
        for ad, deger in (ek_basliklar or {}).items():
            self.send_header(ad, deger)
        self.end_headers()
        self.wfile.write(govde)

    def _dosya_akis_gonder(self, yol) -> None:
        """Bellek dostu (chunked) ve duraklatilabilir (Range) dosya sunumu."""
        import urllib.parse
        try:
            file_size = yol.stat().st_size
            range_header = self.headers.get("Range", "")
            start, end = 0, file_size - 1
            if range_header.startswith("bytes="):
                try:
                    ranges = range_header.split("=")[1].split("-")
                    start = int(ranges[0]) if ranges[0] else 0
                    end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                except ValueError:
                    pass
            if start >= file_size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            chunk_size = end - start + 1
            self.send_response(206 if range_header else 200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            gvn_ad = urllib.parse.quote(yol.name)
            ascii_name = yol.name.encode("ascii", "ignore").decode("ascii").replace('"', '') or "indirilen_dosya"
            self.send_header("Content-Disposition", f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{gvn_ad}')
            self.send_header("Content-Length", str(chunk_size))
            if range_header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self._cors()
            self.end_headers()
            with open(yol, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            _LOG.info("Dosya akis istemcisi baglantiyi kapatti: %s", yol)
        except OSError:
            _LOG.exception("Dosya akisinda IO hatasi: %s", yol)
            self._hata(500, "AKIS_HATASI", "Dosya aktarimi baslatilamadi")
        except Exception:
            _LOG.exception("Dosya akisinda beklenmeyen hata: %s", yol)
            self._hata(500, "AKIS_HATASI", "Dosya aktarimi baslatilamadi")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # --- yollar -----------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/s/"):
            token = parsed.path[3:]
            if token not in _Handler.shared_files:
                self._hata(404, "SAYFA_YOK", "Paylasim bulunamadi veya suresi doldu")
                return
            bilgi = _Handler.shared_files[token]
            self._dosya_akis_gonder(bilgi["path"])
            return
        if not self._rate_allowed(): self._hata(429, "RATE_LIMIT", "cok fazla istek; bir dakika sonra yeniden dene"); return
        if parsed.path == "/ping":
            # Kimlik sagligi: CLI/uzanti endpoint'in bu surece ait oldugunu
            # app alanindan dogrular. Anahtarsizdir (yalnizca bilgi).
            self._send(200, {"ok": True, "app": "AfuDM"})
            return
        if parsed.path == "/klasorler":
            # Telefon arayuzu kategori listesini buradan doldurur.
            if not self._authorized(query):
                self._hata(401, "ANAHTAR_GEREKLI", "anahtar gerekli")
                return
            from core import kaydet
            ana = self.manager.current_download_dir()
            self._send(200, {
                "ok": True,
                "ana": ana,
                "kategoriler": [{"anahtar": k, "ad": ad} for k, ad in kaydet.KATEGORI_KLASORU.items()],
                "acik": bool(self.manager.store.get("kategori_klasorleri")),
            })
            return
        if parsed.path == "/dosya":
            # v2.4 "Telefona indir": biten dosyayi telefonun tarayicisina AKITIR.
            # GUVENLIK: istemciden YOL ALINMAZ, yalnizca gid alinir ve yolu
            # sunucu kendisi bulur. Bulunan yol indirme kokunun ICINDE olmak
            # zorundadir; disari cikan istek reddedilir (v2.1'de eklenen
            # kisitlamayi delmemek icin ayni kural burada da uygulanir).
            if not self._authorized(query, allow_query=True):
                self._hata(401, "ANAHTAR_GEREKLI", "anahtar gerekli")
                return
            gid = query.get("gid", [""])[0]
            if not gid:
                self._hata(400, "GID_GEREKLI", "gid gerekli")
                return
            try:
                dosya = self._telefona_dosya(gid)
            except FileNotFoundError:
                self._hata(404, "DOSYA_YOK", "dosya bulunamadi veya indirme bitmemis")
                return
            except PermissionError:
                self._hata(403, "HEDEF_DISARIDA", "dosya indirme kokunun disinda")
                return
            self._dosya_akit(dosya)
            return
        if parsed.path in ("/m", "/m/"):
            # Telefon arayuzu. Sayfanin KENDISI anahtarsiz gelir (bos kabuk);
            # icindeki her API cagrisi anahtari basliga koyar. Anahtar adres
            # cubugundan (?k=) gelir ve telefonda saklanir.
            self._sayfa_gonder(paths.UI / "mobil.html")
            return
        if parsed.path == "/manifest.webmanifest":
            # Manifest yeni kurulumlarda hemen yenilensin.
            self._sayfa_gonder(
                paths.UI / "manifest.webmanifest",
                "application/manifest+json; charset=utf-8", "no-cache",
            )
            return
        if parsed.path == "/sw.js":
            # Worker tum kok yolu kapsayabilsin ve her acilista kontrol edilsin.
            self._sayfa_gonder(
                paths.UI / "sw.js", "text/javascript; charset=utf-8", "no-cache",
                {"Service-Worker-Allowed": "/"},
            )
            return
        if parsed.path == "/ikon.png":
            self._sayfa_gonder(paths.UI / "icon.png", "image/png", "public, max-age=31536000")
            return
        if parsed.path == "/show":
            # Ikinci kopya: kendi penceresini acmak yerine bunu cagirir.
            if _Handler.on_show:
                _Handler.on_show()
            self._send(200, {"ok": True})
            return
        if parsed.path == "/pair":
            # Anahtari SADECE eslestirme penceresi acikken ver.
            if time.time() < _Handler.pair_until:
                _Handler.son_eslesme = time.time()
                self._send(200, {"ok": True, "token": self.token})
            else:
                self._hata(
                    403,
                    "ESLESME_KAPALI",
                    "eslestirme kapali — AfuDM'de Ayarlar > Uzantiyi bagla'ya bas",
                )
            return
        if parsed.path == "/indir":
            if not self._authorized(query):
                self._hata(401, "ANAHTAR_GEREKLI", "anahtar gerekli")
                return
            gid = query.get("gid", [""])[0]
            if not gid:
                self._hata(400, "GID_GEREKLI", "gid gerekli")
                return
            try:
                yol = _indir_yolu(self.manager, gid)
            except PermissionError:
                self._hata(403, "HEDEF_DISARIDA", "dosya indirme kokunun disinda")
                return
            if not yol or not yol.exists() or not yol.is_file():
                self._hata(404, "BULUNAMADI", "Dosya diskte yok veya hazir degil")
                return

            import urllib.parse
            import shutil
            try:
                dosya = open(yol, "rb")
            except OSError:
                self._hata(403, "ERISIM_ENGEL", "Erisim engellendi")
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                gvn_ad = urllib.parse.quote(yol.name)
                ascii_name = yol.name.encode("ascii", "ignore").decode("ascii").replace('"', '') or "indirilen_dosya"
                self.send_header("Content-Disposition", f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{gvn_ad}')
                self.send_header("Content-Length", str(yol.stat().st_size))
                self._cors()
                self.end_headers()
                shutil.copyfileobj(dosya, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                _LOG.info("/indir istemcisi aktarimi iptal etti: %s", gid)
            except Exception:
                _LOG.exception("/indir aktarim hatasi: %s", gid)
            finally:
                try:
                    dosya.close()
                except OSError:
                    _LOG.exception("/indir dosyasi kapatilamadi: %s", gid)
            return
        if not self._authorized(query):
            self._hata(401, "GECERSIZ_TOKEN", "gecersiz token")
            return
        if parsed.path == "/snapshot":
            self._send(200, {"ok": True, **self.manager.snapshot()})
        elif parsed.path == "/rules":
            self._send(200, {"ok": True, "rules": self.manager.store.rules_list()})
        elif parsed.path == "/probe":
            url = query.get("url", [""])[0]
            try:
                self._send(200, {"ok": True, "info": self.manager.probe_video(url)})
            except Exception as exc:
                govde = hata_json(exc)
                self._send(400, govde)
        elif parsed.path == "/peers":
            gid = query.get("gid", [""])[0]
            self._send(200, {"ok": True, "peers": self.manager.peers(gid)})
        elif parsed.path == "/torrent/dosyalar":
            gid = query.get("gid", [""])[0]
            if not gid:
                self._hata(400, "GID_GEREKLI", "gid gerekli")
                return
            try:
                dosyalar = self.manager.torrent_dosyalari(gid)
            except Exception as exc:
                self._send(400, hata_json(exc))
                return
            # TorrentDosyaListesi bir list alt sinifi: JSON'a cevrilince
            # hazir_degil/neden alanlari DUSER. Telefon arayuzu "magnet
            # ustverisi gelmedi" durumunu bu alanlardan ayirdigi icin
            # masaustu koprusuyle (app.py) ayni duz sozlesmeyi gonderiyoruz.
            self._send(200, {
                "ok": True,
                "gid": getattr(dosyalar, "gid", gid),
                "hazir_degil": bool(getattr(dosyalar, "hazir_degil", False)),
                "neden": str(getattr(dosyalar, "neden", "")),
                "dosyalar": list(dosyalar),
            })
        elif parsed.path == "/torrent/metrik":
            gid = query.get("gid", [""])[0]
            if not gid:
                self._hata(400, "GID_GEREKLI", "gid gerekli")
                return
            try:
                self._send(200, {"ok": True, **self.manager.torrent_metrikleri(gid)})
            except Exception as exc:
                self._send(400, hata_json(exc))
        elif parsed.path == "/seed":
            gid = query.get("gid", [""])[0]
            if not gid:
                self._hata(400, "GID_GEREKLI", "gid gerekli")
                return
            try:
                self._send(200, {"ok": True, **self.manager.seed_bilgi(gid)})
            except Exception as exc:
                self._send(400, hata_json(exc))
        elif parsed.path == "/eklentiler":
            # Eklenti kayit defteri + CANLI durum. pywebview koprusuyle AYNI
            # servis katmani (core/eklenti.EklentiServisi) kullanilir.
            self._send(200, self.manager.eklentiler.liste())
        elif parsed.path == "/eklenti/gunluk":
            ad = query.get("ad", [""])[0]
            self._send(200, self.manager.eklentiler.gunluk(ad))
        elif parsed.path == "/eklenti/islem":
            self._send(200, self.manager.eklentiler.islem())
        elif parsed.path == "/capabilities":
            if _Handler.servis is not None:
                # TEK KAYNAK: yalnizca gercekten calisan ozellikler bildirilir.
                self._send(200, _Handler.servis.yetenekler())
                return
            from core import engines, surum
            self._send(200, {
                "ok": True,
                "app": "AfuDM",
                "surum": surum.SURUM,
                "api": 1,
                "uzanti_surumu": surum.uzanti_surumu(),
                "motorlar": engines.durum(),
                "protokoller": ["http", "https", "ftp", "sftp", "magnet", "torrent"],
                "turler": ["http", "video", "torrent"],
                "ozellikler": [
                    "scheduler", "hiz_profilleri", "renew", "ozel_basliklar",
                    "cerez", "zamanlama", "cli", "api", "kategori_klasorleri",
                    "proxy", "sistem_proxy", "checksum", "canli_ayar",

                    "reliability",
                    "rules_engine",
                    "automation", "automation_queue", "automation_retry", "automation_cancel",
                    "torrent_dosya_secimi", "seed_durumu", "tracker_tarama",
                    # v2.0: yerel .afup eklentisi kurulur, ayri surecte calisir.
                    # SANDBOX DEGILDIR — "guvenilen eklenti" modeli.
                    "eklentiler", "eklenti_ayri_surec", "eklenti_rollback",
                ],
                "sinirlar": {
                    "kaynak": models.SOURCE_MAX,
                    "baslik": models.TITLE_MAX,
                    "user_agent": models.USER_AGENT_MAX,
                    "ozel_baslik": models.HEADER_COUNT_MAX,
                    "proxy": models.PROXY_MAX,
                },
            })
        elif parsed.path == "/windows-integration":
            win = getattr(self.manager, "windows", None)
            if win:
                self._send(200, win.status())
            else:
                self._hata(503, "KULLANILAMIYOR", "Windows entegrasyonu kullanilamiyor")
        else:
            self._hata(404, "BILINMEYEN_YOL", "bilinmeyen yol")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self._rate_allowed(): self._hata(429, "RATE_LIMIT", "cok fazla istek; bir dakika sonra yeniden dene"); return
        if not self._authorized(query):
            self._hata(401, "GECERSIZ_TOKEN", "gecersiz token")
            return
        data = self._body()
        try:
            if parsed.path == "/add":
                url = data.get("url") or data.get("source") or ""
                if (_boolean_al(data, "interactive") and _Handler.on_ask and url.strip()
                        and self.manager.store.get("kaydetme_penceresi")):
                    kimlik = _Handler.on_ask(data)
                    self._send(200, {"ok": True, "pending": True, "id": kimlik})
                    return
                hedef = data.get("dest_dir")
                if hedef:
                    kok = self.manager.current_download_dir()
                    if not _yol_kok_icinde(hedef, kok):
                        self._hata(403, "HEDEF_DISARIDA", "hedef klasor indirme kokunun disinda")
                        return
                    hedef = str(Path(hedef).resolve())
                if not hedef and data.get("kategori"):
                    # Telefon/uzanti kategori yollayabilir; tam yolu burada kurariz
                    from core import kaydet
                    hedef = kaydet.kategori_klasoru(
                        self.manager.current_download_dir(), str(data["kategori"]))
                result = self.manager.add(models.DownloadRequest.from_mapping({
                    "source": url,
                    "kind": data.get("kind"),
                    "dest_dir": hedef,
                    "quality": data.get("quality"),
                    "audio_only": _boolean_al(data, "audio_only"),
                    "playlist": _boolean_al(data, "playlist"),
                    "headers": data.get("headers") or {},
                    "filename": data.get("filename") or None,
                    "cookies": data.get("cookies"),
                    "user_agent": data.get("user_agent") or None,
                    "title": data.get("title") or None,
                    "start_at": data.get("start_at"),
                    "proxy": data.get("proxy"),
                    "checksum": data.get("checksum"),
                    # v1.6 Video Pro — sinirlar/dogrulama from_mapping'de tek yerde.
                    "altyazi_diller": data.get("altyazi_diller") or None,
                    "oto_altyazi": _boolean_al(data, "oto_altyazi"),
                    "altyazi_goem": _boolean_al(data, "altyazi_goem"),
                    "kucuk_resim": data.get("kucuk_resim") or None,
                    "ustveri_goem": _boolean_al(data, "ustveri_goem"),
                    "bolumler": data.get("bolumler") or None,
                    "sponsorblock": data.get("sponsorblock") or None,
                    "bolum_araligi": data.get("bolum_araligi") or None,
                    "kapsayici": data.get("kapsayici") or None,
                    "ses_formati": data.get("ses_formati") or None,
                    "dosya_sablonu": data.get("dosya_sablonu") or None,
                    "tarayici_cerezi": data.get("tarayici_cerezi") or None,
                }))
                self._send(200, {"ok": True, **result})
            elif parsed.path == "/control":
                action = data.get("action", "")
                gid = data.get("gid", "")
                sonuc: dict = {}
                if action == "pause":
                    self.manager.pause(gid)
                elif action == "resume":
                    self.manager.resume(gid)
                elif action == "remove":
                    self.manager.remove(gid, _boolean_al(data, "delete_files"))
                elif action == "pause_all":
                    self.manager.pause_all()
                elif action == "resume_all":
                    self.manager.resume_all()
                elif action == "ayarla":
                    # Network Core: calisan isi KESMEDEN baglanti/hiz ayari
                    sonuc = self.manager.baglanti_ayarla(
                        gid,
                        baglanti=data.get("baglanti"),
                        hiz_kb=data.get("hiz_kb"),
                    )
                else:
                    self._hata(400, "BILINMEYEN_EYLEM", "bilinmeyen eylem")
                    return
                self._send(200, {"ok": True, **sonuc})
            elif parsed.path == "/share_create":
                gid = data.get("gid", "")
                if not gid:
                    self._hata(400, "GID_GEREKLI", "gid gerekli")
                    return
                yol_str = ""
                try:
                    st = self.manager.rpc.tell_status(gid)
                    if st and st.get("status") == "complete":
                        dosyalar = st.get("files") or []
                        if dosyalar and dosyalar[0].get("path"):
                            yol_str = dosyalar[0].get("path")
                except Exception:
                    pass
                if not yol_str:
                    row = self.manager.store.by_gid(gid)
                    if row and row.get("status") == "complete" and row.get("target_path"):
                        yol_str = row["target_path"]
                if not yol_str:
                    self._hata(404, "HAZIR_DEGIL", "Dosya hazir degil veya yolu bulunamadi")
                    return
                from pathlib import Path
                yol = Path(yol_str)
                if not yol.exists() or not yol.is_file():
                    self._hata(404, "BULUNAMADI", "Sadece tekil dosyalar paylasilabilir veya dosya diskte yok")
                    return
                token = secrets.token_urlsafe(12)
                _Handler.shared_files[token] = {"path": yol, "created": time.time()}
                self._send(200, {"ok": True, "token": token, "filename": yol.name})
            elif parsed.path == "/settings":
                self._send(200, {"ok": True, "settings": self.manager.update_settings(data)})
            elif parsed.path == "/rules":
                incoming = data.get("rules")
                if not isinstance(incoming, list):
                    self._hata(400, "BAD_REQUEST", "rules liste olmali")
                    return
                # Same persistent Store/service used by the pywebview bridge.
                normalized = []
                for index, rule in enumerate(incoming, 1):
                    if not isinstance(rule, dict) or not str(rule.get("name") or "").strip():
                        self._hata(400, "BAD_REQUEST", "her kuralin adi olmali")
                        return
                    normalized.append({"id": str(rule.get("id") or f"api-rule-{index}"), "name": str(rule["name"]).strip()[:100], "active": bool(rule.get("active", True)), "match_type": rule.get("match_type") if rule.get("match_type") in ("all", "any") else "all", "conditions": rule.get("conditions") if isinstance(rule.get("conditions"), list) else [], "actions": rule.get("actions") if isinstance(rule.get("actions"), dict) else {}})
                self.manager.store.rules_save(normalized)
                self._send(200, {"ok": True, "rules": self.manager.store.rules_list()})
            elif parsed.path == "/torrent/secim":
                gid = data.get("gid", "")
                indeksler = data.get("indeksler")
                if not gid:
                    self._hata(400, "GID_GEREKLI", "gid gerekli")
                    return
                if not isinstance(indeksler, list):
                    self._hata(400, "GECERSIZ_SECIM", "indeksler liste olmali")
                    return
                temiz = []
                for indeks in indeksler:
                    if isinstance(indeks, bool):
                        self._hata(400, "GECERSIZ_SECIM", "indeksler tam sayi olmali")
                        return
                    try:
                        sayi = int(indeks)
                    except (TypeError, ValueError):
                        self._hata(400, "GECERSIZ_SECIM", "indeksler tam sayi olmali")
                        return
                    if isinstance(indeks, float) and not indeks.is_integer():
                        self._hata(400, "GECERSIZ_SECIM", "indeksler tam sayi olmali")
                        return
                    temiz.append(sayi)
                # Aria2 indeksleri 1-tabanlidir; negatifleri istemci girdisinden ayikla.
                temiz = [indeks for indeks in temiz if indeks > 0]
                self._send(200, {"ok": True, **self.manager.torrent_secimi_ayarla(gid, temiz)})
            elif parsed.path == "/seed/tazele":
                gid = data.get("gid", "")
                if not gid:
                    self._hata(400, "GID_GEREKLI", "gid gerekli")
                    return
                self._send(200, {"ok": True, **self.manager.seed_tazele(gid)})
            elif parsed.path == "/tracker/tara":
                self._send(200, {"ok": True, **self.manager.tracker_tara(data.get("gid", ""))})
            elif parsed.path == "/windows-integration":
                win = getattr(self.manager, "windows", None)
                if not win:
                    self._hata(503, "KULLANILAMIYOR", "Windows entegrasyonu kullanilamiyor")
                    return
                ident = str(data.get("id") or "")
                action = str(data.get("action") or "")
                if action == "apply": result = win.apply(ident)
                elif action == "remove": result = win.remove(ident)
                elif action == "test": result = win.test(ident)
                else: raise ValueError("action apply, remove veya test olmali")
                self._send(200, result)

            elif parsed.path == "/renew":
                # Olen linki yeni adresle devam ettir (afuadm renew <gid> <url>).
                # headers/cookies/user_agent OPSIYONEL: varliksa ayni atomik
                # adimda aria2 seceneklerine ve DB'ye islenir.
                gid = data.get("gid", "")
                yeni_url = data.get("url") or data.get("new_url") or ""
                if not gid or not yeni_url:
                    self._hata(400, "BAD_REQUEST", "gid ve url gerekli")
                    return
                self._send(200, {
                    "ok": True,
                    **self.manager.renew(
                        gid,
                        yeni_url,
                        headers=data.get("headers"),
                        cookies=data.get("cookies"),
                        user_agent=data.get("user_agent"),
                    ),
                })
            elif parsed.path == "/mode":
                # Hiz profili: snail | normal | turbo (canli uygulanir)
                ad = data.get("profil") or data.get("mode") or ""
                if not ad:
                    self._hata(400, "BAD_REQUEST", "profil gerekli (snail|normal|turbo)")
                    return
                self._send(200, {"ok": True, **self.manager.set_mode(ad)})

            elif parsed.path == "/reliability/integrity": self._send(200, self.reliability.integrity())
            elif parsed.path == "/reliability/backup": self._send(200, self.reliability.backup())
            elif parsed.path == "/reliability/diagnostics-preview": self._send(200, self.reliability.diagnostics_preview())
            elif parsed.path == "/reliability/diagnostics-export": self._send(200, self.reliability.diagnostics_export())
            elif parsed.path == "/token/rotate":
                if not self.rotate_token: self._hata(503, "KULLANILAMIYOR", "token rotasyonu kullanilamiyor"); return
                self.rotate_token(); self._send(200, {"ok": True, "rotated": True})
            elif parsed.path == "/eklenti":
                # Tek kapi: {"eylem": "...", ...}. Kurulum/guncelleme ARKA
                # PLANDA baslar; ilerleme GET /eklenti/islem ile izlenir.
                servis = self.manager.eklentiler
                eylem = str(data.get("eylem") or "")
                ad = str(data.get("ad") or "")
                yol = str(data.get("yol") or "")
                if eylem == "incele":
                    self._send(200, servis.incele(yol))
                elif eylem == "kur":
                    self._send(200, servis.kur(yol, data.get("onaylanan_izinler")))
                elif eylem == "guncelle":
                    self._send(200, servis.guncelle(ad, yol))

                elif eylem == "geri_al":
                    self._send(200, servis.elle_geri_al(ad))
                elif eylem == "kaldir":
                    self._send(200, servis.kaldir(ad))
                elif eylem == "etkinlestir":
                    self._send(200, servis.etkinlestir(ad, _boolean_al(data, "acik")))
                elif eylem == "yeniden_baslat":
                    self._send(200, servis.yeniden_baslat(ad))
                elif eylem == "ayar":
                    self._send(200, servis.ayar_kaydet(ad, data.get("ayarlar") or {}))
                elif eylem == "islem_iptal":
                    self._send(200, servis.islem_iptal())
                else:
                    self._hata(400, "BILINMEYEN_EYLEM", "bilinmeyen eklenti eylemi")
            elif parsed.path == "/linkgrabber":
                # Uzanti handoff'u: kopylanamayan/sayfa linkleri LinkGrabber
                # paneline duser. Tehlikesizdir: cabuk kurutma/indirme YOKTUR,
                # is canli UI'da kullanicinindir. Analiz JS tarafinda yapilir.
                metin = (data.get("metin") or "").strip()
                uyari = _boolean_al(data, "dosya")
                if not metin:
                    self._hata(400, "BAD_REQUEST", "metin gerekli")
                    return
                if _Handler.on_linkgrabber is None:
                    self._hata(503, "UI_YOK", "LinkGrabber paneli kullanilamiyor")
                    return
                _Handler.on_linkgrabber(metin, uyari)
                self._send(200, {"ok": True, "pending": True})
            else:
                self._hata(404, "BILINMEYEN_YOL", "bilinmeyen yol")
        except Exception as exc:
            govde = hata_json(exc)
            # Icin-de kodlar 400, INTERNAL 500 ile doner
            durum = 400 if govde.get("code") != "INTERNAL" else 500
            self._send(durum, govde)


class _ExclusiveServer(ThreadingHTTPServer):
    """Portu PAYLASMAYAN sunucu.

    HTTPServer SO_REUSEADDR acar; Windows'ta bu, ayni portu IKINCI bir surecin de
    acabilmesi demek (olculdu: api_smoke calisan AfuDM'in 6811'ine ortak oldu,
    istekler rastgele surece gitti). Port doluysa bind HATA vermeli ki
    LocalAPI.start() bir sonraki portu denesin.
    """

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class LocalAPI:
    def __init__(self, manager, port: int = 6811, lan: bool = False) -> None:
        self.token = load_or_create_token()
        _Handler.manager = manager
        from core.reliability import Reliability
        _Handler.reliability = Reliability(manager)
        _Handler.rotate_token = self.rotate_token
        _Handler.token = self.token
        # tercih_edilen: kullanicinin/uygulamanin ISTEDIGI port (degismez).
        # port: GERCEKTEN baglanilan calisan port (dolulukta +1..+9 kayabilir).
        self.tercih_edilen = int(port)
        self.port = int(port)
        # lan=True: telefon baglanabilsin diye yerel aga ac (bkz. modul basligi)
        self.lan = lan
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    # --- durum ------------------------------------------------------------
    @property
    def calisiyor(self) -> bool:
        return self.httpd is not None

    def durum(self) -> dict:
        """UI kopru sozlesmesi: tercih vs calisan port."""
        return {
            "ok": True,
            "tercih_edilen": int(self.tercih_edilen),
            "calisan": int(self.port) if self.calisiyor else 0,
            "yeniden_baslatma_gerekli": bool(
                self.calisiyor and int(self.port) != int(self.tercih_edilen)
            ),
        }

    # --- yasam dongusu ----------------------------------------------------
    def _baslat(self, adres: str, ilk_port: int) -> ThreadingHTTPServer:
        """Portu (ve dolu ise sonraki 9'u) dene; hicbiri olmazsa hata ver."""
        son_hata: Exception | None = None
        for port in range(int(ilk_port), int(ilk_port) + 10):
            if port > 65535:
                break
            try:
                httpd = _ExclusiveServer((adres, port), _Handler)
            except OSError as exc:
                son_hata = exc
                continue
            self.port = port
            return httpd
        raise RuntimeError("API portu acilamadi: %s" % (son_hata,))

    def start(self) -> int:
        adres = "0.0.0.0" if self.lan else "127.0.0.1"
        httpd = self._baslat(adres, self.tercih_edilen)
        self.httpd = httpd
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self.thread.start()
        self._endpoint_yaz()
        return self.port

    def _endpoint_yaz(self) -> None:
        """Uzantinin okuyabilmesi icin port + token'i dosyaya yaz.

        Token dosyaya YAZILIR ama ASLA loglanmaz; dosya izni kisitlanir.
        """
        endpoint = paths.DATA / "api_endpoint.json"
        endpoint.write_text(
            json.dumps({"port": self.port, "token": self.token}, indent=1),
            encoding="utf-8",
        )
        _dosya_iznini_kisitla(endpoint)

    def stop(self) -> None:
        """Sunucuyu kapat ve REFERANSLARI TEMIZLE.

        Eskiden `httpd`/`thread` kapandiktan sonra da duruyordu; `calisiyor`
        yanlis pozitif veriyor, ikinci bir `stop()` kapali sokete
        `shutdown()` cagirip patlayabiliyordu."""
        httpd, thread = self.httpd, self.thread
        self.httpd = None
        self.thread = None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        except Exception:
            _LOG.exception("LocalAPI HTTP sunucusu kapatilamadi")
        try:
            httpd.server_close()
        except Exception:
            _LOG.exception("LocalAPI socket temizligi basarisiz")
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)

    def lan_ayarla(self, acik: bool) -> dict:
        """LAN'i ac/kapat — BASARISIZLIKTA ESKI DURUMA GERI DON.

        Yerel aga baglanma (0.0.0.0) guvenlik yazilimi ya da baska bir surec
        yuzunden basarisiz olabilir. O zaman:
          * eski `lan` degeri geri alinir,
          * sunucu onceki adres/portta YENIDEN ayaga kaldirilir,
          * doner sozlukte `acik` GERCEK durumu gosterir — cagiran taraf
            ayari yanlislikla "acik" diye kaydetmesin.
        """
        istenen = bool(acik)
        eski_lan = bool(self.lan)
        eski_port = int(self.port)
        if istenen == eski_lan and self.calisiyor:
            return {"ok": True, "acik": eski_lan, "port": self.port, "geri_alindi": False}
        self.stop()
        self.lan = istenen
        try:
            self.start()
        except Exception as exc:
            hata = str(exc)[:200]
            # --- rollback: eski calisma durumu ---
            self.lan = eski_lan
            self.port = eski_port
            try:
                self.start()
            except Exception:
                self.stop()
            return {
                "ok": False,
                "acik": bool(self.lan) and self.calisiyor,
                "port": self.port if self.calisiyor else 0,
                "geri_alindi": True,
                "hata": hata,
            }
        return {"ok": True, "acik": self.lan, "port": self.port, "geri_alindi": False}

    def rotate_token(self) -> str:
        """Replaces the only accepted token immediately; old callers receive 401."""
        self.token = secrets.token_urlsafe(24); _Handler.token = self.token
        paths.API_TOKEN_FILE.write_text(self.token, encoding="utf-8"); _dosya_iznini_kisitla(paths.API_TOKEN_FILE)
        if self.httpd:
            (paths.DATA / "api_endpoint.json").write_text(json.dumps({"port": self.port, "token": self.token}), encoding="utf-8")
            _dosya_iznini_kisitla(paths.DATA / "api_endpoint.json")
        return self.token

    def lan_adresi(self) -> str:
        """Telefonun yazacagi adres. Makinenin LAN IP'si UDP rota secimiyle
        bulunur (paket GITMEZ); birden cok ag varsa dogru olani secer."""
        ip = ""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            ip = ""
        if not ip or ip.startswith("127."):
            return ""
        return f"http://{ip}:{self.port}/m?k={self.token}"

    def open_pairing(self, seconds: float = 120.0) -> float:
        """Uzantinin anahtari otomatik alabilecegi pencereyi ac."""
        _Handler.pair_until = time.time() + seconds
        return _Handler.pair_until

    @property
    def son_eslesme(self) -> float:
        return _Handler.son_eslesme
