#!/usr/bin/env python3
"""Indexa TODOS los metodos de dump.cs -> TSV (clase, metodo, rva, offset, firma)."""
import re

lines = open("/workspace/airo/rev/dump/dump.cs", encoding="utf-8", errors="replace").read().split("\n")
cls = None
rows = []
for i, l in enumerate(lines):
    mc = re.match(r"\s*(?:public|internal|private|protected)?\s*(?:sealed |abstract |static |partial )*class (\w+)", l)
    if mc:
        cls = mc.group(1)
    if "// RVA:" not in l:
        continue
    rva = re.search(r"RVA: (0x[0-9A-Fa-f]+)", l)
    off = re.search(r"Offset: (0x[0-9A-Fa-f]+)", l)
    if not (rva and off):
        continue
    sig = ""
    for j in range(i + 1, min(len(lines), i + 6)):
        s = lines[j].strip()
        if not s or s.startswith("//"):
            continue
        sig = s
        break
    if sig and "(" in sig:
        name = re.sub(r"^[^(]*?(\w+)\s*\(.*$", r"\1", sig)
        rows.append((cls or "?", name, rva.group(1), off.group(1), sig))

rows.sort(key=lambda r: int(r[2], 16))
with open("/workspace/airo/rev/all_methods.tsv", "w") as f:
    for r in rows:
        f.write("\t".join(r) + "\n")
print(f"indexados {len(rows)} metodos")
