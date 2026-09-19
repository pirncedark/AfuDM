"""CLI yardim metinleri — AGSIZ, her parser alt komutunu otomatik dener."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import afuadm  # noqa: E402


def _alt_komutlar() -> list[str]:
    parser = afuadm.komutlar_ayirici()
    action = next(a for a in parser._actions if getattr(a, "choices", None))
    return sorted(action.choices)


def main() -> int:
    kok = Path(__file__).resolve().parent.parent
    failed: list[str] = []
    for komut in _alt_komutlar():
        result = subprocess.run(
            [sys.executable, "afuadm.py", komut, "--help"], cwd=kok,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        ok = result.returncode == 0
        print(f"  [{'GECTI' if ok else 'BASARISIZ'}] {komut} --help")
        if not ok:
            failed.append(f"{komut}: {result.stderr.strip() or result.stdout.strip()}")
    if failed:
        print("BASARISIZ: " + " | ".join(failed))
        return 1
    print(f"OK: {len(_alt_komutlar())} alt komut yardimi calisti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
