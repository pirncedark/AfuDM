"""Yerel HTTP API — SADECE 127.0.0.1, token zorunlu.

Tarayici uzantisi, Telegram kopru scripti veya baska bir araci buradan
AfuDM'e is verir. Dis dunyaya kapali: adres 127.0.0.1'e bagli ve her istek
X-AfuDM-Token (veya ?token=) ile dogrulanir.
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core import paths


def load_or_create_token() -> str:
    paths.ensure_dirs()
    if paths.API_TOKEN_FILE.exists():
        token = paths.API_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    paths.API_TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


class _Handler(BaseHTTPRequestHandler):
    server_version = "AfuDM/1.0"
    manager = None       # calisma aninda atanir
    token = ""
    # Uzantinin anahtari otomatik alabilecegi kisa pencere. Kullanici
    # uygulamadan "Uzantiyi bagla" deyince acilir; suresi dolunca kapanir.
    pair_until = 0.0

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

    def _authorized(self, query: dict) -> bool:
        header = self.headers.get("X-AfuDM-Token", "")
        supplied = header or (query.get("token", [""])[0])
        return bool(self.token) and secrets.compare_digest(supplied, self.token)

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
            self._send(200, {"ok": True, "app": "AfuDM"})
            return
        if parsed.path == "/pair":
            # Anahtari SADECE eslestirme penceresi acikken ver.
            if time.time() < _Handler.pair_until:
                self._send(200, {"ok": True, "token": self.token})
            else:
                self._send(
                    403,
                    {"ok": False, "error": "eslestirme kapali — AfuDM'de "
                                           "Ayarlar > Uzantiyi bagla'ya bas"},
                )
            return
        if not self._authorized(query):
            self._send(401, {"ok": False, "error": "gecersiz token"})
            return
        if parsed.path == "/snapshot":
            self._send(200, {"ok": True, **self.manager.snapshot()})
        elif parsed.path == "/probe":
            url = query.get("url", [""])[0]
            try:
                self._send(200, {"ok": True, "info": self.manager.probe_video(url)})
            except Exception as exc:
                self._send(400, {"ok": False, "error": str(exc)[:400]})
        elif parsed.path == "/peers":
            gid = query.get("gid", [""])[0]
            self._send(200, {"ok": True, "peers": self.manager.peers(gid)})
        else:
            self._send(404, {"ok": False, "error": "bilinmeyen yol"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self._authorized(query):
            self._send(401, {"ok": False, "error": "gecersiz token"})
            return
        data = self._body()
        try:
            if parsed.path == "/add":
                url = data.get("url") or data.get("source") or ""
                result = self.manager.add(
                    url,
                    kind=data.get("kind"),
                    dest_dir=data.get("dest_dir"),
                    quality=data.get("quality"),
                    audio_only=bool(data.get("audio_only")),
                    playlist=bool(data.get("playlist")),
                    headers=data.get("headers") or {},
                    filename=data.get("filename") or None,
                    cookies=data.get("cookies"),
                    user_agent=data.get("user_agent") or None,
                    title=data.get("title") or None,
                )
                self._send(200, {"ok": True, **result})
            elif parsed.path == "/control":
                action = data.get("action", "")
                gid = data.get("gid", "")
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
                else:
                    self._send(400, {"ok": False, "error": "bilinmeyen eylem"})
                    return
                self._send(200, {"ok": True})
            elif parsed.path == "/settings":
                self._send(200, {"ok": True, "settings": self.manager.update_settings(data)})
            else:
                self._send(404, {"ok": False, "error": "bilinmeyen yol"})
        except Exception as exc:
            self._send(400, {"ok": False, "error": str(exc)[:400]})


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
    def __init__(self, manager, port: int = 6811) -> None:
        self.token = load_or_create_token()
        _Handler.manager = manager
        _Handler.token = self.token
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> int:
        last_error: Exception | None = None
        for port in range(self.port, self.port + 10):
            try:
                self.httpd = _ExclusiveServer(("127.0.0.1", port), _Handler)
                self.port = port
                break
            except OSError as exc:
                last_error = exc
        if self.httpd is None:
            raise RuntimeError(f"API portu acilamadi: {last_error}")
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # Uzantinin okuyabilmesi icin port + token'i dosyaya yaz.
        (paths.DATA / "api_endpoint.json").write_text(
            json.dumps({"port": self.port, "token": self.token}, indent=1),
            encoding="utf-8",
        )
        return self.port

    def open_pairing(self, seconds: float = 120.0) -> float:
        """Uzantinin anahtari otomatik alabilecegi pencereyi ac."""
        _Handler.pair_until = time.time() + seconds
        return _Handler.pair_until

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
