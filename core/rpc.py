"""aria2 JSON-RPC istemcisi. Sadece stdlib kullanir (ek bagimlilik yok)."""
from __future__ import annotations

import http.client
import itertools
import json
import urllib.error
import urllib.request


class Aria2Error(RuntimeError):
    """aria2 tarafindan donen hata veya baglanti hatasi."""


def _hata_metni(govde) -> str:
    """JSON-RPC govdesinden hata mesajini GUVENLE cikar.

    KUSUR (2026-09-19, port testi ortaya cikardi): `govde["error"].get(...)`
    yaziliyordu. `error` bir METIN olarak gelirse (ya da govde sozluk degilse)
    AttributeError atiyordu — bu bir Aria2Error DEGIL, dolayisiyla
    `except Aria2Error` bekleyen `alive()` ve yoklama dongusu COKUYORDU.
    """
    if not isinstance(govde, dict):
        return ""
    hata = govde.get("error")
    if isinstance(hata, dict):
        return str(hata.get("message") or "")
    return str(hata) if hata else ""


class Aria2RPC:
    def __init__(self, host: str = "127.0.0.1", port: int = 6810, secret: str = "") -> None:
        self.port = port          # hangi porta bagliyiz (tanilama + testler)
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
                message = _hata_metni(parsed) or raw
            except json.JSONDecodeError:
                message = raw or str(exc)
            raise Aria2Error(f"{method}: {message}") from exc
        except urllib.error.URLError as exc:
            raise Aria2Error(f"aria2 RPC erisilemedi: {exc}") from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            # Motor kapanirken baglanti yarida kopar (RemoteDisconnected,
            # ConnectionResetError, zaman asimi) ya da govde bozuk gelir.
            # Bunlar URLError DEGIL; cevrilmezse "except Aria2Error" bekleyen
            # yoklama dongusu coker.
            raise Aria2Error(f"aria2 RPC baglantisi koptu: {exc!r}") from exc
        if not isinstance(body, dict):
            # Govde JSON ama SOZLUK degil (ara sunucu/yanlis port): asagidaki
            # body["error"] / body["result"] TypeError atardi.
            raise Aria2Error(f"beklenmeyen RPC yaniti: {str(body)[:120]}")
        if "error" in body:
            raise Aria2Error(_hata_metni(body) or "bilinmeyen aria2 hatasi")
        if "result" not in body:
            raise Aria2Error(f"RPC yanitinda sonuc yok: {str(body)[:120]}")
        return body["result"]

    def alive(self, timeout: float = 3.0) -> bool:
        try:
            self.call("aria2.getVersion", timeout=timeout)
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

    def change_uri(
        self, gid: str, file_index: int,
        del_uris: list[str], add_uris: list[str], position: int = -1,
    ) -> int:
        """aria2.changeUri — yalnizca waiting/paused/error durumunda calisir.
        Olen (suresi dolan) linki yenilemek icin kullanilir (bkz. renew):
        eski URL listeden cikar, yeni URL sona eklenir, inen baytlar korunur.
        Donus degeri kaldirilan URI sayisidir (0 da basarili olabilir)."""
        return self.call(
            "aria2.changeUri", gid, file_index, del_uris, add_uris, position
        )

    def get_global_option(self) -> dict:
        return self.call("aria2.getGlobalOption")

    def shutdown(self, force: bool = False) -> str:
        return self.call("aria2.forceShutdown" if force else "aria2.shutdown")

    def save_session(self) -> str:
        return self.call("aria2.saveSession")
