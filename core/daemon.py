"""aria2c surecini yonetir: rastgele token ile baslat, saglik kontrolu, temiz kapat."""
from __future__ import annotations

import atexit
import secrets
import subprocess
import time

from . import netcheck, paths
from .rpc import Aria2RPC

RPC_PORT = 6810
CREATE_NO_WINDOW = 0x08000000  # konsol penceresi acilmasin


def load_or_create_secret() -> str:
    paths.ensure_dirs()
    if paths.SECRET_FILE.exists():
        token = paths.SECRET_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    paths.SECRET_FILE.write_text(token, encoding="utf-8")
    return token


def _args(secret: str, download_dir: str) -> list[str]:
    """IDM'i geride birakan cok parcali indirme + torrent ayarlari."""
    paths.SESSION_FILE.touch(exist_ok=True)
    return [
        str(paths.ARIA2C),
        "--enable-rpc",
        "--rpc-listen-all=false",
        "--rpc-listen-port=%d" % RPC_PORT,
        "--rpc-secret=%s" % secret,
        "--rpc-allow-origin-all=true",
        "--dir=%s" % download_dir,
        # --- hiz: cok parcali indirme ---
        "--max-connection-per-server=16",
        "--split=64",
        "--min-split-size=1M",
        "--max-concurrent-downloads=5",
        "--optimize-concurrent-downloads=true",
        "--disk-cache=64M",
        "--file-allocation=falloc",
        "--continue=true",
        "--always-resume=true",
        "--max-tries=10",
        "--retry-wait=3",
        "--timeout=30",
        "--connect-timeout=15",
        "--auto-file-renaming=true",
        "--allow-overwrite=false",
        "--remote-time=true",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AfuDM/1.0",
        # --- torrent: DHT/PEX/LPD acik, seed takibi icin ---
        "--enable-dht=true",
        "--enable-dht6=false",
        "--dht-listen-port=6881-6899",
        "--listen-port=6891-6900",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-max-peers=100",
        "--bt-request-peer-speed-limit=50M",
        "--bt-detach-seed-only=true",
        "--seed-ratio=1.0",
        "--follow-torrent=true",
        "--bt-save-metadata=true",
        # --- oturum: kapatip acinca kaldigi yerden ---
        "--save-session=%s" % paths.SESSION_FILE,
        "--input-file=%s" % paths.SESSION_FILE,
        "--save-session-interval=15",
        "--auto-save-interval=15",
        "--force-save=true",
        "--log=%s" % paths.ARIA2_LOG,
        "--log-level=warn",
        "--console-log-level=error",
        "--quiet=true",
        "--daemon=false",
        # IPv6 yolu olmayan makinede aria2 AAAA adresini deneyip indirmeyi
        # iptal eder (IPv4'e dusmez) — netcheck bunu calisma aninda olcer.
        *netcheck.aria2_ipv6_args(),
    ]


class Aria2Daemon:
    def __init__(self, download_dir: str | None = None) -> None:
        paths.ensure_dirs()
        self.secret = load_or_create_secret()
        self.download_dir = download_dir or str(paths.default_download_dir())
        self.proc: subprocess.Popen | None = None
        self.rpc = Aria2RPC(port=RPC_PORT, secret=self.secret)

    def start(self, timeout: float = 20.0) -> Aria2RPC:
        if self.rpc.alive():
            # Zaten calisan bir ornek var (ayni token ile) — ona baglan.
            # Onu BIZ baslatmadik: stop() da kapatmamali (baska AfuDM/test
            # kapaninca calisan uygulamanin motoru olmesin).
            return self.rpc
        if not paths.ARIA2C.exists():
            raise FileNotFoundError(f"aria2c.exe bulunamadi: {paths.ARIA2C}")
        self.proc = subprocess.Popen(
            _args(self.secret, self.download_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        atexit.register(self.stop)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.rpc.alive():
                return self.rpc
            if self.proc.poll() is not None:
                raise RuntimeError(
                    "aria2c baslatilamadi (cikis kodu %s). Log: %s"
                    % (self.proc.returncode, paths.ARIA2_LOG)
                )
            time.sleep(0.25)
        raise TimeoutError("aria2c RPC %.0f saniyede yanit vermedi" % timeout)

    def stop(self) -> None:
        if self.proc is None:
            return  # motoru biz baslatmadik
        try:
            if self.rpc.alive():
                self.rpc.save_session()
                self.rpc.shutdown()
        except Exception:
            pass
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
