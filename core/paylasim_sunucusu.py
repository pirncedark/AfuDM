"""Internetten paylasim icin yalnizca token'li dosya akis sunucusu."""
from __future__ import annotations

import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class _PaylasimHandler(BaseHTTPRequestHandler):
    shares: dict[str, dict] = {}

    def log_message(self, _format: str, *_args) -> None:
        return

    def _send_error(self) -> None:
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve(self, head_only: bool) -> None:
        parsed = urlsplit(self.path)
        if parsed.path.startswith("/s/"):
            token = parsed.path[3:]
            # Token tek segment olmali; URL'den hicbir dosya yolu kabul edilmez.
            if not token or "/" in token or token not in self.shares:
                self._send_error()
                return
            kayit = self.shares[token]
            try:
                path = Path(kayit["path"])
                if not path.is_file():
                    self._send_error()
                    return
                size = path.stat().st_size
            except (OSError, TypeError, ValueError):
                self._send_error()
                return

            start, end, partial = 0, max(size - 1, 0), False
            range_header = self.headers.get("Range", "")
            if range_header:
                if not range_header.startswith("bytes=") or "," in range_header:
                    self._send_error()
                    return
                spec = range_header[6:].strip()
                try:
                    left, right = spec.split("-", 1)
                    if not left:
                        length = int(right)
                        start = max(size - length, 0)
                    else:
                        start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                    if start < 0 or start > end or start >= size:
                        raise ValueError
                    partial = True
                except (ValueError, TypeError):
                    self._send_error()
                    return

            length = max(0, end - start + 1)
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head_only or not length:
                return
            try:
                with path.open("rb") as stream:
                    stream.seek(start)
                    remaining = length
                    while remaining:
                        chunk = stream.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except OSError:
                return
            return
        self._send_error()

    def do_GET(self) -> None:  # noqa: N802
        self._serve(False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(True)


class PaylasimSunucusu:
    """127.0.0.1'de rastgele portta, sadece /s/<token> dinler."""

    def __init__(self, shares: dict[str, dict]):
        self.shares = shares
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1]) if self.httpd else 0

    def start(self) -> int:
        if self.httpd:
            return self.port
        _PaylasimHandler.shares = self.shares
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _PaylasimHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self) -> None:
        httpd, thread = self.httpd, self.thread
        self.httpd = None
        self.thread = None
        if not httpd:
            return
        httpd.shutdown()
        httpd.server_close()
        if thread:
            thread.join(timeout=2)
