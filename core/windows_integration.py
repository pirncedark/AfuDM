"""Geri alinabilir, kullanici kapsami Windows entegrasyonlari.

Yalniz HKCU\\Software\\Classes altinda AfuDM'e ait adlar yazilir. Bir ad
zaten varsa, tum deger/agaci uygulama veritabanindaki `winint_backup_*`
ayarinda saklanir; kaldirma yalniz bu yedegi geri yukler.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import winreg
from pathlib import Path
from typing import Any

from . import paths

ROOT = r"Software\\Classes"
ITEMS = {
    "context": r"*\\shell\\AfuDM.Download",
    "protocol": "afudm",
    "afup": ".afup",
}


def _command() -> str:
    exe = paths.BASE / "AfuDM.exe"
    if exe.exists():
        return f'"{exe}" "%1"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    return f'"{pythonw}" "{paths.BASE / "app.py"}" "%1"'


def _delete_tree(path: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try: child = winreg.EnumKey(key, 0)
                except OSError: break
                _delete_tree(path + "\\" + child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


def _dump(path: str) -> dict | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            values = []
            i = 0
            while True:
                try:
                    name, value, typ = winreg.EnumValue(key, i); i += 1
                    values.append([name, value, typ])
                except OSError: break
            children = {}
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i); i += 1
                    children[name] = _dump(path + "\\" + name)
                except OSError: break
            return {"values": values, "children": children}
    except OSError:
        return None


def _restore(path: str, tree: dict) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        for name, value, typ in tree.get("values", []):
            winreg.SetValueEx(key, name, 0, typ, value)
    for name, child in tree.get("children", {}).items():
        _restore(path + "\\" + name, child or {})


class WindowsIntegration:
    def __init__(self, store) -> None:
        self.store = store
        self.scan: dict[str, Any] = {"state": "idle", "path": "", "detail": ""}
        self._scan_lock = threading.Lock()

    def _path(self, ident: str) -> str: return ROOT + "\\" + ITEMS[ident]
    def _backup_key(self, ident: str) -> str: return "winint_backup_" + ident

    def _backup_once(self, ident: str) -> None:
        key = self._backup_key(ident)
        if self.store.get(key, None) is not None: return
        backup = {"tree": _dump(self._path(ident))}
        if ident == "afup": backup["progid"] = _dump(ROOT + r"\\AfuDM.afup")
        self.store.set(key, backup)

    def _write(self, ident: str) -> None:
        self._backup_once(ident)
        path = self._path(ident)
        _delete_tree(path)
        if ident == "context":
            _restore(path, {"values": [["", "AfuDM ile indir", winreg.REG_SZ], ["Icon", str(paths.BASE / "ui" / "afudm.ico"), winreg.REG_SZ]], "children": {"command": {"values": [["", _command(), winreg.REG_SZ]], "children": {}}}})
        elif ident == "protocol":
            _restore(path, {"values": [["", "URL:AfuDM Download", winreg.REG_SZ], ["URL Protocol", "", winreg.REG_SZ]], "children": {"shell": {"values": [], "children": {"open": {"values": [], "children": {"command": {"values": [["", _command(), winreg.REG_SZ]], "children": {}}}}}}}})
        else:
            progid = "AfuDM.afup"
            _restore(path, {"values": [["", progid, winreg.REG_SZ]], "children": {"OpenWithProgids": {"values": [[progid, "", winreg.REG_SZ]], "children": {}}}})
            _restore(ROOT + "\\" + progid, {"values": [["", "AfuDM paket dosyasi", winreg.REG_SZ]], "children": {"shell": {"values": [], "children": {"open": {"values": [], "children": {"command": {"values": [["", _command(), winreg.REG_SZ]], "children": {}}}}}}}})

    def _remove(self, ident: str) -> None:
        backup = self.store.get(self._backup_key(ident), None)
        if backup is None: return
        _delete_tree(self._path(ident))
        if ident == "afup":
            progid_path = ROOT + r"\\AfuDM.afup"
            _delete_tree(progid_path)
            if isinstance(backup, dict) and backup.get("progid"):
                _restore(progid_path, backup["progid"])
        tree = backup.get("tree") if isinstance(backup, dict) else None
        if tree: _restore(self._path(ident), tree)
        self.store.set(self._backup_key(ident), None)

    def _registered(self, ident: str) -> bool:
        cmd = _command()
        try:
            if ident == "context":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._path(ident) + "\\command") as k: return winreg.QueryValueEx(k, "")[0] == cmd
            if ident == "protocol":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._path(ident) + "\\shell\\open\\command") as k: return winreg.QueryValueEx(k, "")[0] == cmd
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ROOT + r"\\.afup") as k: return winreg.QueryValueEx(k, "")[0] == "AfuDM.afup"
        except OSError: return False

    def status(self) -> dict:
        entries = {name: {"registered": self._registered(name), "scope": "current_user"} for name in ITEMS}
        entries["torrent"] = {"registered": False, "scope": "current_user"}
        return {"ok": True, "integrations": entries, "scan": dict(self.scan), "service": {"supported": False, "state": "unavailable", "reason": "Windows service host is not packaged in this build."}}

    def apply(self, ident: str) -> dict:
        if ident not in ITEMS: raise ValueError("bilinmeyen Windows entegrasyonu")
        self._write(ident)
        return self.status()

    def remove(self, ident: str) -> dict:
        if ident not in ITEMS: raise ValueError("bilinmeyen Windows entegrasyonu")
        self._remove(ident)
        return self.status()

    def test(self, ident: str) -> dict:
        if ident not in ITEMS: raise ValueError("bilinmeyen Windows entegrasyonu")
        return {"ok": self._registered(ident), "registered": self._registered(ident), "status": self.status()}

    def scan_file(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.is_file(): raise ValueError("taranacak indirilen dosya bulunamadi")
        if not self._scan_lock.acquire(blocking=False): return {"ok": True, "already_running": True, "scan": dict(self.scan)}
        self.scan = {"state": "running", "path": str(path), "detail": ""}
        def work():
            try:
                program = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Windows Defender" / "MpCmdRun.exe"
                if not program.exists():
                    self.scan = {"state": "unavailable", "path": str(path), "detail": "Microsoft Defender command-line tool was not found."}; return
                result = subprocess.run([str(program), "-Scan", "-ScanType", "3", "-File", str(path)], capture_output=True, text=True, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.scan = {"state": "clean" if result.returncode == 0 else "warning", "path": str(path), "detail": (result.stderr or result.stdout or "Defender returned a non-zero result.")[:300]}
            except Exception as exc: self.scan = {"state": "error", "path": str(path), "detail": str(exc)[:300]}
            finally: self._scan_lock.release()
        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "scan": dict(self.scan)}
