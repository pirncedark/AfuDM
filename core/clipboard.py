"""Pano izleme (Windows, ctypes — ek bagimlilik yok).

Panoya indirilebilir bir link kopyalandiginda arayuzde ekleme penceresini
acmak icin kullanilir. Ayni link tekrar tekrar sorulmaz.
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

CF_UNICODETEXT = 13

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalLock.restype = wintypes.LPVOID


def read_text() -> str:
    """Panodaki metni don; metin yoksa bos string."""
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.c_wchar_p(pointer).value or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def looks_downloadable(text: str, extensions: str) -> bool:
    text = (text or "").strip()
    if not text or "\n" in text or len(text) > 2048:
        return False
    lowered = text.lower()
    if lowered.startswith("magnet:"):
        return True
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return False
    path = lowered.split("?")[0]
    exts = tuple("." + e.strip().lstrip(".") for e in extensions.split(",") if e.strip())
    if exts and path.endswith(exts):
        return True
    video_hints = (
        "youtube.com/watch", "youtu.be/", "instagram.com/", "tiktok.com/",
        "vimeo.com/", "twitter.com/", "x.com/", "facebook.com/", "twitch.tv/",
    )
    return any(hint in lowered for hint in video_hints)


class ClipboardWatcher(threading.Thread):
    def __init__(self, on_link, is_enabled, get_extensions, interval: float = 1.0) -> None:
        super().__init__(daemon=True)
        self.on_link = on_link
        self.is_enabled = is_enabled
        self.get_extensions = get_extensions
        self.interval = interval
        self._seen = ""
        self._stop = threading.Event()

    def prime(self) -> None:
        """Acilista panoda duran linki hemen sormasin."""
        self._seen = read_text().strip()

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            if not self.is_enabled():
                continue
            try:
                text = read_text().strip()
            except OSError:
                continue
            if not text or text == self._seen:
                continue
            self._seen = text
            if looks_downloadable(text, self.get_extensions()):
                try:
                    self.on_link(text)
                except Exception:
                    pass

    def stop(self) -> None:
        self._stop.set()


def wait_for_clipboard(timeout: float = 2.0) -> str:
    """Testlerde kullanilan yardimci: pano dolana kadar bekle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = read_text()
        if text:
            return text
        time.sleep(0.1)
    return ""
