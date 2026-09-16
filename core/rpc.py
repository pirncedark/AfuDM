"""aria2 JSON-RPC istemcisi. Sadece stdlib kullanir (ek bagimlilik yok)."""
from __future__ import annotations

import itertools
import json
import urllib.error
import urllib.request


class Aria2Error(RuntimeError):
    """aria2 tarafindan donen hata veya baglanti hatasi."""


class Aria2RPC:
    def __init__(self, host: str = "127.0.0.1", port: int = 6810, secret: str = "") -> None:
        self.url = f"http://{host}:{port}/jsonrpc"
        self.token = f"token:{secret}"
        self._ids = itertools.count(1)

    # --- cekirdek ---------------------------------------------------------
    def call(self, method: str, *params, timeout: float = 15.0):
        payload = {
            "jsonrpc": "2.0",
            "id": str(next(self._ids)),
            "method": method,
            "params": [self.token, *params],
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # aria2, JSON-RPC hatalarini HTTP 400 ile dondurur; gercek mesaj
            # govdenin icinde. Govdeyi okumazsak hatanin nedenini kaybederiz.
            raw = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
                message = parsed.get("error", {}).get("message") or raw
            except json.JSONDecodeError:
                message = raw or str(exc)
            raise Aria2Error(f"{method}: {message}") from exc
        except urllib.error.URLError as exc:
            raise Aria2Error(f"aria2 RPC erisilemedi: {exc}") from exc
        if "error" in body:
            raise Aria2Error(body["error"].get("message", "bilinmeyen aria2 hatasi"))
        return body["result"]

    def alive(self) -> bool:
        try:
            self.call("aria2.getVersion", timeout=3)
            return True
        except Aria2Error:
            return False

    # --- indirme ekleme ---------------------------------------------------
    def add_uri(self, uris: list[str], options: dict | None = None) -> str:
        return self.call("aria2.addUri", uris, options or {})

    def add_torrent(self, torrent_b64: str, options: dict | None = None) -> str:
        return self.call("aria2.addTorrent", torrent_b64, [], options or {})

    def add_metalink(self, metalink_b64: str, options: dict | None = None) -> list[str]:
        return self.call("aria2.addMetalink", metalink_b64, options or {})

    # --- kontrol ----------------------------------------------------------
    def pause(self, gid: str, force: bool = False) -> str:
        return self.call("aria2.forcePause" if force else "aria2.pause", gid)

    def unpause(self, gid: str) -> str:
        return self.call("aria2.unpause", gid)

    def remove(self, gid: str, force: bool = False) -> str:
        return self.call("aria2.forceRemove" if force else "aria2.remove", gid)

    def remove_result(self, gid: str) -> str:
        return self.call("aria2.removeDownloadResult", gid)

    def pause_all(self) -> str:
        return self.call("aria2.pauseAll")

    def unpause_all(self) -> str:
        return self.call("aria2.unpauseAll")

    # --- durum ------------------------------------------------------------
    STATUS_KEYS = [
        "gid", "status", "totalLength", "completedLength", "uploadLength",
        "downloadSpeed", "uploadSpeed", "connections", "numSeeders", "seeder",
        "errorCode", "errorMessage", "dir", "files", "bittorrent", "infoHash",
        "numPieces", "pieceLength", "followedBy", "following",
    ]

    def tell_status(self, gid: str, keys: list[str] | None = None) -> dict:
        return self.call("aria2.tellStatus", gid, keys or self.STATUS_KEYS)

    def tell_active(self, keys: list[str] | None = None) -> list[dict]:
        return self.call("aria2.tellActive", keys or self.STATUS_KEYS)

    def tell_waiting(self, offset: int = 0, num: int = 200, keys: list[str] | None = None):
        return self.call("aria2.tellWaiting", offset, num, keys or self.STATUS_KEYS)

    def tell_stopped(self, offset: int = 0, num: int = 200, keys: list[str] | None = None):
        return self.call("aria2.tellStopped", offset, num, keys or self.STATUS_KEYS)

    def global_stat(self) -> dict:
        return self.call("aria2.getGlobalStat")

    def get_peers(self, gid: str) -> list[dict]:
        """Torrent icin canli peer listesi (seed takibi detayi)."""
        return self.call("aria2.getPeers", gid)

    def get_servers(self, gid: str) -> list[dict]:
        """HTTP/FTP indirmesinde parca basina baglanti bilgisi."""
        return self.call("aria2.getServers", gid)

    # --- ayar -------------------------------------------------------------
    def change_option(self, gid: str, options: dict) -> str:
        return self.call("aria2.changeOption", gid, options)

    def change_global_option(self, options: dict) -> str:
        return self.call("aria2.changeGlobalOption", options)

    def get_global_option(self) -> dict:
        return self.call("aria2.getGlobalOption")

    def shutdown(self, force: bool = False) -> str:
        return self.call("aria2.forceShutdown" if force else "aria2.shutdown")

    def save_session(self) -> str:
        return self.call("aria2.saveSession")
