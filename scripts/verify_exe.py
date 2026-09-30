"""Verify the Python modules embedded in a PyInstaller executable."""
from __future__ import annotations

import argparse
import marshal
import types
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # PyInstaller yalniz exe dogrularken gerekir; CI testleri onsuz koşar
    from PyInstaller.archive.readers import CArchiveReader

REQUIRED_ASSETS = (
    "ui/download.html",
    "ui/download.js",
    "extension/download-handoff.js",
)


def verify_assets(reader: "CArchiveReader") -> None:
    names = {name.replace("\\", "/") for name in reader.toc}
    missing = [name for name in REQUIRED_ASSETS if name not in names]
    if missing:
        raise RuntimeError("embedded assets missing: " + ", ".join(missing))
    for name in REQUIRED_ASSETS:
        archive_name = next(key for key in reader.toc if key.replace("\\", "/") == name)
        if not reader.extract(archive_name):
            raise RuntimeError(f"embedded asset empty: {name}")


def nested_code(root: types.CodeType):
    stack = [root]
    while stack:
        code = stack.pop()
        yield code
        stack.extend(
            item for item in code.co_consts if isinstance(item, types.CodeType)
        )


def load_carchive_module(reader: "CArchiveReader", name: str) -> types.CodeType:
    try:
        return marshal.loads(reader.extract(name))
    except (KeyError, ValueError, EOFError, TypeError) as exc:
        raise RuntimeError(f"embedded module missing or invalid: {name}") from exc


def verify_headless(pyz, app: types.CodeType) -> None:
    """Verify the packaged headless entry without launching a live service."""
    try:
        headless = pyz.extract("headless")
    except (KeyError, ValueError, EOFError, TypeError) as exc:
        raise RuntimeError("embedded module missing or invalid: headless") from exc
    codes = list(nested_code(headless))
    if not any(code.co_name == "calistir" for code in codes):
        raise RuntimeError("embedded headless entry missing: calistir")
    if any("webview" in code.co_names for code in codes):
        raise RuntimeError("embedded headless imports webview")
    if not any("--headless" in code.co_consts and "headless" in code.co_names
               for code in nested_code(app)):
        raise RuntimeError("embedded app lacks --headless dispatch")


def verify(exe: Path, expected_version: str, headless: bool = False) -> None:
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(exe))
    verify_assets(reader)
    app = load_carchive_module(reader, "app")
    pyz = reader.open_embedded_archive("PYZ.pyz")
    if headless:
        verify_headless(pyz, app)
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
    parser.add_argument("--headless", action="store_true", help="Check embedded headless entry without starting it")
    args = parser.parse_args()
    try:
        verify(args.exe, args.version, headless=args.headless)
    except (OSError, RuntimeError, KeyError) as exc:
        print(f"GATE HATA: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
