#!/usr/bin/env python3
"""Desensambla metodos IL2CPP y anota strings literales y llamadas."""
import json
import re
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

SO = "/workspace/airo/rev/il2cpp/lib/arm64-v8a/libil2cpp.so"
DUMP = "/workspace/airo/rev/dump"
LIT = f"{DUMP}/stringliteral.json"
SCRIPT = f"{DUMP}/script.json"

so = open(SO, "rb").read()

# --- mapa de literales: address -> string ---
lit_by_addr = {}
raw = json.load(open(LIT))
if isinstance(raw, dict):
    items = raw.items()
else:
    items = [(None, v) for v in raw]
for k, v in items:
    if isinstance(v, dict):
        addr = v.get("address") or v.get("dataAddress")
        val = v.get("value") or v.get("string") or ""
    else:
        addr, val = k, v
    if addr is None:
        continue
    try:
        lit_by_addr[int(str(addr), 0) if isinstance(addr, str) else int(addr)] = val
    except Exception:
        pass
print(f"# literales: {len(lit_by_addr)}", file=sys.stderr)

# --- mapa de metodos: address -> nombre (para BL) ---
method_by_addr = {}
try:
    sc = json.load(open(SCRIPT))
    for m in sc.get("ScriptMethod", []):
        a = m.get("Address")
        n = m.get("Name") or ""
        if a is None:
            continue
        a = int(str(a), 0) if isinstance(a, str) else int(a)
        method_by_addr[a + 0x4000] = n  # script.json usa offsets de fichero
except Exception as e:
    print(f"# aviso script.json: {e}", file=sys.stderr)
print(f"# metodos en script.json: {len(method_by_addr)}", file=sys.stderr)

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = False


SORTED_RVAS = sorted(method_by_addr.keys()) if method_by_addr else []


def next_method_rva(rva):
    import bisect
    i = bisect.bisect_right(SORTED_RVAS, rva)
    return SORTED_RVAS[i] if i < len(SORTED_RVAS) else None


def disasm(off, rva, size=0x200, max_ins=140):
    # los bytes se leen del offset de fichero, pero capstone debe usar el RVA
    # como direccion base (los literales y ADRP+ADD viven en el espacio RVA)
    code = so[off:off + size]
    out = []
    stop = next_method_rva(rva)
    for ins in md.disasm(code, rva):
        out.append(ins)
        if len(out) >= max_ins:
            break
        if stop and ins.address >= stop:
            out.pop()
            break
        # corte heuristico: siguiente RVA conocido
    return out


def annotate(ins, prev):
    t = ins.mnemonic + " " + ins.op_str
    ann = []
    # resolver ADRP/ADD -> literal
    if ins.mnemonic == "adrp":
        try:
            imm = int(ins.op_str.split("#")[1], 0)
            page = (ins.address & ~0xFFF) + imm
            ann.append(f"page=0x{page:x}")
            prev = page
        except Exception:
            prev = None
    elif ins.mnemonic == "add" and prev is not None and "x" in ins.op_str:
        m = re.search(r"#(0x[0-9a-f]+)", ins.op_str)
        if m:
            addr = prev + int(m.group(1), 0)
            ann.append(f"->0x{addr:x}")
            if addr in lit_by_addr:
                ann.append(f"STR={lit_by_addr[addr]!r}")
            prev = addr
        else:
            prev = None
    else:
        prev = None
    # BL -> nombre de metodo
    if ins.mnemonic in ("bl", "b"):
        m = re.match(r"(0x[0-9a-f]+)", ins.op_str)
        if m:
            tgt = int(m.group(1), 0)
            if tgt in method_by_addr:
                nm = method_by_addr[tgt]
                nm = nm.split("::")[-1] if "::" in nm else nm
                ann.append(f"CALL {nm}")
    return ann, prev


def show(title, off, rva, size=0x200, max_ins=140):
    print(f"\n{'='*90}\n# {title}   RVA 0x{rva:x} / file 0x{off:x}\n{'='*90}")
    prev = None
    for ins in disasm(off, rva, size, max_ins):
        ann, prev = annotate(ins, prev)
        line = f"0x{ins.address:08x}  {ins.mnemonic:8s} {ins.op_str}"
        if ann:
            line += "    ; " + "  ".join(ann)
        print(line)


if __name__ == "__main__":
    import csv
    targets = []
    with open("/workspace/airo/rev/methods.tsv") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 4 and row[2].startswith("0x"):
                targets.append((row[0] + "." + row[1], int(row[3], 16), int(row[2], 16)))
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for name, off, rva in targets:
        if only and not any(o.lower() in name.lower() for o in only):
            continue
        show(name, off, rva)
