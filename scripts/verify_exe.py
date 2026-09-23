"""Verify the Python modules embedded in a PyInstaller executable."""
from __future__ import annotations

import argparse
import marshal
import types
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


def nested_code(root: types.CodeType):
    stack = [root]
    while stack:
        code = stack.pop()
        yield code
        stack.extend(
            item for item in code.co_consts if isinstance(item, types.CodeType)
        )


def load_carchive_module(reader: CArchiveReader, name: str) -> types.CodeType:
    try:
        return marshal.loads(reader.extract(name))
    except (KeyError, ValueError, EOFError, TypeError) as exc:
        raise RuntimeError(f"embedded module missing or invalid: {name}") from exc


def verify(exe: Path, expected_version: str) -> None:
    reader = CArchiveReader(str(exe))
    app = load_carchive_module(reader, "app")
    pyz = reader.open_embedded_archive("PYZ.pyz")
    try:
        surum = pyz.extract("core.surum")
    except (KeyError, ValueError, EOFError, TypeError) as exc:
        raise RuntimeError("embedded module missing or invalid: core.surum") from exc

    if expected_version not in {
        value
        for code in nested_code(surum)
        for value in code.co_consts
        if isinstance(value, str)
    }:
        raise RuntimeError(
            f"embedded core.surum does not contain expected version {expected_version}"
        )

    controls = [code for code in nested_code(app) if code.co_name == "control"]
    if not controls:
        raise RuntimeError("embedded app module has no control method")
    control = controls[0]
    if not {"isinstance", "dict", "bool"}.issubset(control.co_names):
        raise RuntimeError("embedded app.control lacks delete_files normalization")
    if "delete_files" not in control.co_consts:
        raise RuntimeError("embedded app.control lacks delete_files handling")

    print(f"embedded EXE OK: {exe} (version {expected_version})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        verify(args.exe, args.version)
    except (OSError, RuntimeError, KeyError) as exc:
        print(f"GATE HATA: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
