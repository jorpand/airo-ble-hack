#!/usr/bin/env python3
"""Indexa TODOS los metodos de dump.cs -> TSV (clase, metodo, rva, offset, firma).

La cadena completa esta en `docs/protocolo.md` § 3.

    python3 tools/rev/index_all.py --rev-dir ~/airo/rev
    python3 tools/rev/index_all.py --dump ~/airo/rev/dump/dump.cs --salida metodos.tsv
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rev-dir",
        type=Path,
        default=Path(os.environ.get("AIRO_REV_DIR") or Path(__file__).resolve().parent),
        help="carpeta de trabajo del reversing (donde esta dump/)",
    )
    parser.add_argument(
        "--dump",
        type=Path,
        default=None,
        help="el dump.cs (por defecto: <rev-dir>/dump/dump.cs)",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="el TSV de salida (por defecto: <rev-dir>/all_methods.tsv)",
    )
    return parser.parse_args()


args = _args()
DUMP = args.dump or (args.rev_dir / "dump" / "dump.cs")
SALIDA = args.salida or (args.rev_dir / "all_methods.tsv")

if not DUMP.exists():
    raise SystemExit(
        f"no encuentro el dump.cs: {DUMP}\n"
        "  generalo con Il2CppDumper (ver docs/protocolo.md § 3) "
        "o pasa --dump / --rev-dir"
    )

lines = open(DUMP, encoding="utf-8", errors="replace").read().split("\n")
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
SALIDA.parent.mkdir(parents=True, exist_ok=True)
with open(SALIDA, "w") as f:
    for r in rows:
        f.write("\t".join(r) + "\n")
print(f"indexados {len(rows)} metodos en {SALIDA}")
