"""Cloudflare quick tunnel surecunun guvenli yasam dongusu."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from typing import Callable, Any

CREATE_NO_WINDOW = 0x08000000
_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)


class TunnelError(RuntimeError):
    pass


class TunnelManager:
    def __init__(self, executable: str, *, popen_factory: Callable[..., Any] | None = None,
                 timeout: float = 30.0):
        self.executable = executable
        self.timeout = timeout
        self._popen = popen_factory or subprocess.Popen
        self._process: Any = None
        self._url = ""
        self._port = 0
        self._lock = threading.RLock()
        self._watcher: threading.Thread | None = None
        self._retry_used = False
        self.launch_count = 0
        self.error = ""

    @property
    def active(self) -> bool:
        return self._process is not None and self._url != ""

    @property
    def url(self) -> str:
        return self._url

    def _launch(self, port: int) -> Any:
        flags = CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = self._popen(
            [self.executable, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            bufsize=1, creationflags=flags,
        )
        self.launch_count += 1
        return proc

    def _read_url(self, proc: Any) -> str:
        lines: queue.Queue[str] = queue.Queue()

        def reader() -> None:
            try:
                for line in proc.stdout:
                    lines.put(str(line))
            except (OSError, TypeError):
                return

        threading.Thread(target=reader, daemon=True).start()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                match = _URL.search(lines.get(timeout=min(0.1, max(0.01, deadline - time.monotonic()))))
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if match:
                return match.group(0)
        raise TunnelError("Cloudflare tunnel 30 saniye icinde internet linki vermedi")

    def _start_once(self, port: int) -> str:
        proc = self._launch(port)
        try:
            url = self._read_url(proc)
        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            raise
        self._process, self._port, self._url = proc, port, url
        return url

    def start(self, port: int) -> str:
        with self._lock:
            if self.active and self._port == int(port):
                return self._url
            self.stop()
            self._retry_used = False
            self.error = ""
            last: Exception | None = None
            for _attempt in range(2):
                try:
                    url = self._start_once(int(port))
                    self._watcher = threading.Thread(target=self._watch, daemon=True)
                    self._watcher.start()
                    return url
                except Exception as exc:
                    last = exc
            self.error = str(last or "Cloudflare tüneli başlatılamadı")
            raise TunnelError(self.error)

    def _watch(self) -> None:
        while self._process is not None:
            proc = self._process
            if proc.poll() is None:
                time.sleep(0.1)
                continue
            with self._lock:
                if self._process is not proc:
                    return
                if self._retry_used:
                    self.error = "Cloudflare tunnel beklenmedik sekilde kapandi"
                    self._process = None
                    self._url = ""
                    return
                self._retry_used = True
                port = self._port
                self._process = None
                self._url = ""
                try:
                    self._start_once(port)
                    self._watcher = threading.Thread(target=self._watch, daemon=True)
                    self._watcher.start()
                except Exception as exc:
                    self.error = f"Cloudflare tunnel yeniden baslatilamadi: {exc}"
                    self._process = None
                    self._url = ""
            return

    def stop(self) -> None:
        with self._lock:
            proc = self._process
            self._process = None
            self._url = ""
            self._port = 0
        if not proc:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
