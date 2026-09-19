"""Aria2 JSON-RPC ve torrent yardimcilari icin uyumluluk modulu (bkz. core/rpc.py).

Geriye donuk uyumluluk ve dogrudan erisim icin Aria2RPC ve Aria2Error siniflarini
core/rpc.py uzerinden disa aktarir.
"""
from __future__ import annotations

from .rpc import Aria2Error, Aria2RPC

__all__ = ["Aria2Error", "Aria2RPC"]
