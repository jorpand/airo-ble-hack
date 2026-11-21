#!/usr/bin/env python3
"""Escanea libil2cpp.so buscando todas las llamadas (BL) a una RVA concreta.

La cadena completa esta en `docs/protocolo.md` § 3.

    python3 tools/rev/find_callers.py --rev-dir ~/airo/rev 0x1fbc8xx
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rev-dir",
        type=Path,
        default=Path(os.environ.get("AIRO_REV_DIR") or Path(__file__).resolve().parent),
        help="carpeta de trabajo del reversing",
    )
    parser.add_argument("--so", type=Path, default=None, help="libil2cpp.so")
    parser.add_argument("--script", type=Path, default=None, help="el script.json del dump")
    parser.add_argument("rvas", nargs="*", help="las RVAs a buscar (en hexadecimal)")
    return parser.parse_known_args(argv)[0]


args = _args(sys.argv[1:])
REV = args.rev_dir
SO = args.so or (REV / "il2cpp" / "lib" / "arm64-v8a" / "libil2cpp.so")
SCRIPT = args.script or (REV / "dump" / "script.json")

if not SO.exists():
    raise SystemExit(
        f"no encuentro la libreria: {SO}\n"
        "  ver docs/protocolo.md § 3 (o pasa --so / --rev-dir)"
    )

so = open(SO, "rb").read()
sc = json.load(open(SCRIPT))
method_by_addr = {}
for m in sc.get("ScriptMethod", []):
    a = m.get("Address")
    if a is None:
        continue
    a = int(str(a), 0) if isinstance(a, str) else int(a)
    method_by_addr[a] = m.get("Name", "")

# RVA <-> file offset: el segmento de texto tiene vaddr = offset + 0x4000
out = subprocess.run(["readelf", "-l", str(SO)], capture_output=True, text=True).stdout
delta = 0x4000  # segmento R E: Offset 0x1bd2a10 -> VirtAddr 0x1bd6a10
print(f"# delta vaddr-offset = 0x{delta:x}")

targets = {int(a, 16) for a in args.rvas}
print(f"# buscando llamadas a: {[hex(t) for t in targets]}")

n = len(so) // 4
hits = {}
for i in range(n):
    w = struct.unpack_from("<I", so, i * 4)[0]
    if (w & 0xFC000000) != 0x94000000:
        continue
    imm26 = w & 0x03FFFFFF
    if imm26 & 0x02000000:
        imm26 -= 0x04000000
    file_off = i * 4
    rva = file_off + delta
    tgt = rva + (imm26 << 2)
    if tgt in targets:
        hits.setdefault(tgt, []).append(rva)

for tgt, callers in hits.items():
    print(f"\n### target 0x{tgt:x}  ({method_by_addr.get(tgt, '?')})")
    for c in callers:
        print(f"    llamado desde RVA 0x{c:x}  -> {method_by_addr.get(c, '?')}")
