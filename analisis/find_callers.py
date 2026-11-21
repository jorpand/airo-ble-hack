#!/usr/bin/env python3
"""Escanea libil2cpp.so buscando todas las llamadas (BL) a una RVA concreta."""
import json
import sys

SO = "/workspace/airo/rev/il2cpp/lib/arm64-v8a/libil2cpp.so"
SCRIPT = "/workspace/airo/rev/dump/script.json"

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
import subprocess
out = subprocess.run(["readelf", "-l", SO], capture_output=True, text=True).stdout
delta = 0x4000  # segmento R E: Offset 0x1bd2a10 -> VirtAddr 0x1bd6a10
print(f"# delta vaddr-offset = 0x{delta:x}")

targets = {int(a, 16) for a in sys.argv[1:]}
print(f"# buscando llamadas a: {[hex(t) for t in targets]}")

import struct
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
