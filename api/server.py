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
import os
import secrets
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core import models, paths
from core.hata import hata_json


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
        pass


def _zamanla(s) -> float | None:
    """Eski adres geriye donuk uyumlnaktadir; tek kaynak `parse_time_spec`."""
    return models.parse_time_spec(s)


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

    # --- yardimcilar ------------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:  # konsolu kirletmesin
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
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

    def _authorized(self, query: dict) -> bool:
        header = self.headers.get("X-AfuDM-Token", "")
        supplied = header or (query.get("token", [""])[0])
        return bool(self.token) and secrets.compare_digest(supplied, self.token)

    def _sayfa_gonder(self, yol) -> None:
        """Tek dosyalik arayuzu gonder (telefon icin; CSS/JS iceride gomulu)."""
        try:
            govde = yol.read_bytes()
        except OSError:
            self._hata(404, "SAYFA_YOK", "sayfa bulunamadi")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

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
        if parsed.path in ("/m", "/m/"):
            # Telefon arayuzu. Sayfanin KENDISI anahtarsiz gelir (bos kabuk);
            # icindeki her API cagrisi anahtari basliga koyar. Anahtar adres
            # cubugundan (?k=) gelir ve telefonda saklanir.
            self._sayfa_gonder(paths.UI / "mobil.html")
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
        if not self._authorized(query):
            self._hata(401, "GECERSIZ_TOKEN", "gecersiz token")
            return
        if parsed.path == "/snapshot":
            self._send(200, {"ok": True, **self.manager.snapshot()})
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
        elif parsed.path == "/capabilities":
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
                ],
                "sinirlar": {
                    "kaynak": models.SOURCE_MAX,
                    "baslik": models.TITLE_MAX,
                    "user_agent": models.USER_AGENT_MAX,
                    "ozel_baslik": models.HEADER_COUNT_MAX,
                    "proxy": models.PROXY_MAX,
                },
            })
        else:
            self._hata(404, "BILINMEYEN_YOL", "bilinmeyen yol")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self._authorized(query):
            self._hata(401, "GECERSIZ_TOKEN", "gecersiz token")
            return
        data = self._body()
        try:
            if parsed.path == "/add":
                url = data.get("url") or data.get("source") or ""
                if (data.get("interactive") and _Handler.on_ask and url.strip()
                        and self.manager.store.get("kaydetme_penceresi")):
                    kimlik = _Handler.on_ask(data)
                    self._send(200, {"ok": True, "pending": True, "id": kimlik})
                    return
                hedef = data.get("dest_dir")
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
                    "audio_only": bool(data.get("audio_only")),
                    "playlist": bool(data.get("playlist")),
                    "headers": data.get("headers") or {},
                    "filename": data.get("filename") or None,
                    "cookies": data.get("cookies"),
                    "user_agent": data.get("user_agent") or None,
                    "title": data.get("title") or None,
                    "start_at": data.get("start_at"),
                    "proxy": data.get("proxy"),
                    "checksum": data.get("checksum"),
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
                    self.manager.remove(gid, bool(data.get("delete_files")))
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
            elif parsed.path == "/settings":
                self._send(200, {"ok": True, "settings": self.manager.update_settings(data)})
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
        _Handler.token = self.token
        self.port = port
        # lan=True: telefon baglanabilsin diye yerel aga ac (bkz. modul basligi)
        self.lan = lan
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> int:
        last_error: Exception | None = None
        adres = "0.0.0.0" if self.lan else "127.0.0.1"
        for port in range(self.port, self.port + 10):
            try:
                self.httpd = _ExclusiveServer((adres, port), _Handler)
                self.port = port
                break
            except OSError as exc:
                last_error = exc
        if self.httpd is None:
            raise RuntimeError(f"API portu acilamadi: {last_error}")
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # Uzantinin okuyabilmesi icin port + token'i dosyaya yaz.
        endpoint = paths.DATA / "api_endpoint.json"
        endpoint.write_text(
            json.dumps({"port": self.port, "token": self.token}, indent=1),
            encoding="utf-8",
        )
        _dosya_iznini_kisitla(endpoint)
        return self.port

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

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
