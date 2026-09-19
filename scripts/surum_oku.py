# -*- coding: utf-8 -*-
"""core/surum.py icindeki SURUM'u stdout'a yazdirir (tek satir).

Release hatti ve CI betikleri seklinde inline `python -c "<regex>"` yazmaz:
Windows PowerShell 5.1 tirnak/is kaçış farkliliklari yuzunden ayni regex'i
surekli bozuyordu. Bu dosya herkes icin TEK ve dogru kaynai olur.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __name__ == "__main__":
    kok = Path(__file__).resolve().parent.parent
    metin = (kok / "core" / "surum.py").read_text(encoding="utf-8")
    eslesme = re.search(r'SURUM = "([0-9.]+)"', metin)
    if not eslesme:
        print("surum.py icinde SURUM bulunamadi", file=sys.stderr)
        sys.exit(3)
    print(eslesme.group(1))