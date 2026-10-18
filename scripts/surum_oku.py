# -*- coding: utf-8 -*-
"""rs/Cargo.toml [workspace.package].version degerini stdout'a yazdirir (tek satir).

Release hatti ve CI betikleri inline `python -c` yazmaz; bu dosya tek kaynaktir.
Surum tek kaynagi Rust workspace'tir (release-please da rs/Cargo.toml'i gunceller).
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

if __name__ == "__main__":
    kok = Path(__file__).resolve().parent.parent
    with (kok / "rs" / "Cargo.toml").open("rb") as f:
        surum = tomllib.load(f).get("workspace", {}).get("package", {}).get("version")
    if not surum:
        print("rs/Cargo.toml icinde [workspace.package].version bulunamadi", file=sys.stderr)
        sys.exit(3)
    print(surum)
