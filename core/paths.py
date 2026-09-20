"""Proje yollari — TAMAMEN PORTABLE.

Her sey uygulama klasorunun icinde kalir: motorlar engine/, veritabani data/,
indirmeler downloads/. Sisteme, kayit defterine veya AppData'ya hicbir sey
yazilmaz; klasoru USB'ye kopyalayip baska makinede calistirabilirsin.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _base() -> Path:
    # PyInstaller ile paketlenmisse exe'nin yaninda, degilse proje kokunde.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE = _base()
ENGINE = BASE / "engine"
DATA = BASE / "data"
UI = BASE / "ui"
EXTENSION = BASE / "extension"
DOWNLOADS = BASE / "downloads"
# v2.0 Plugin Platform: eklenti dosyalari ve guncelleme yedegi (portable kalir)
PLUGINS = BASE / "plugins"
PLUGIN_YEDEK = DATA / "eklenti_yedek"

ARIA2C = ENGINE / "aria2c.exe"
DB_PATH = DATA / "afudm.db"
SESSION_FILE = DATA / "aria2.session"
ARIA2_LOG = DATA / "aria2.log"
SECRET_FILE = DATA / "rpc_secret.txt"
API_TOKEN_FILE = DATA / "api_token.txt"
TRACKERS_CACHE = DATA / "trackers.txt"


def _bundled_or_system(name: str) -> str:
    """Once engine/ icindeki gomulu ikiliyi kullan; yoksa sistemdekine dus."""
    local = ENGINE / name
    if local.exists():
        return str(local)
    from shutil import which

    found = which(Path(name).stem)
    return found or str(local)


def ytdlp_exe() -> str:
    return _bundled_or_system("yt-dlp.exe")


def ffmpeg_exe() -> str:
    return _bundled_or_system("ffmpeg.exe")


def ffmpeg_dir() -> str:
    """yt-dlp'ye --ffmpeg-location olarak verilecek klasor."""
    if (ENGINE / "ffmpeg.exe").exists():
        return str(ENGINE)
    return str(Path(ffmpeg_exe()).parent)


def default_download_dir() -> Path:
    """Portable davranis: indirmeler uygulama klasorunun icine gider."""
    return DOWNLOADS


def user_downloads_dir() -> Path:
    """Kullanici isterse ayarlardan secebilecegi Windows Indirilenler klasoru."""
    profile = os.environ.get("USERPROFILE")
    return Path(profile) / "Downloads" if profile else DOWNLOADS


def ensure_dirs() -> None:
    for folder in (DATA, DOWNLOADS, PLUGINS):
        folder.mkdir(parents=True, exist_ok=True)
