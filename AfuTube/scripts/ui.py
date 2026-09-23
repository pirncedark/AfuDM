#!/usr/bin/env python3
"""uiautomator dump'tan dugum bulup koordinat verir.
  ui.py tap-text <xml> <metin-parcasi>      -> "x y" (metni iceren ilk dugum)
  ui.py tap-desc <xml> <content-desc>       -> "x y"
  ui.py tap-after <xml> <baslik-parcasi>... -> basliklardan birinden SONRAKI ilk tiklanabilir dugum
  ui.py tap-class <xml> <sinif-parcasi>     -> "x y"
Bulamazsa cikis kodu 1."""
import re, sys, xml.etree.ElementTree as ET

def center(n):
    a = list(map(int, re.findall(r"\d+", n.get("bounds", ""))))
    return f"{(a[0] + a[2]) // 2} {(a[1] + a[3]) // 2}" if len(a) == 4 else None

cmd, path, *args = sys.argv[1:]
nodes = list(ET.parse(path).iter("node"))
hit = None
if cmd == "tap-text":
    hit = next((n for n in nodes if args[0] in n.get("text", "")), None)
elif cmd == "tap-desc":
    hit = next((n for n in nodes if args[0] == n.get("content-desc", "")), None)
elif cmd == "tap-class":
    hit = next((n for n in nodes if args[0] in n.get("class", "")), None)
elif cmd == "tap-after":
    seen = False
    for n in nodes:
        if any(a in n.get("text", "") for a in args):
            seen = True
            continue
        if seen and n.get("clickable") == "true":
            hit = n
            break
if hit is None or center(hit) is None:
    sys.exit(1)
print(center(hit))
