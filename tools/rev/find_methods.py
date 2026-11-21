#!/usr/bin/env python3
"""Extrae RVA/Offset de metodos concretos desde el dump.cs de Il2CppDumper.

La cadena completa esta en `docs/protocolo.md` § 3. Este script solo necesita
el `dump.cs` que deja Il2CppDumper.

    python3 tools/rev/find_methods.py --rev-dir ~/airo/rev
    python3 tools/rev/find_methods.py --dump ~/airo/rev/dump/dump.cs

Si no se dice nada, se busca en `AIRO_REV_DIR` y, si tampoco esta, en la
carpeta del propio script (donde se dejan los volcados generados).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
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
    return parser.parse_args()


args = _args()
DUMP = args.dump or (args.rev_dir / "dump" / "dump.cs")

if not DUMP.exists():
    raise SystemExit(
        f"no encuentro el dump.cs: {DUMP}\n"
        "  generalo con Il2CppDumper (ver docs/protocolo.md § 3) "
        "o pasa --dump / --rev-dir"
    )

lines = open(DUMP, encoding="utf-8", errors="replace").read().split("\n")

# 1) Reconstruye el estado de "clase actual" recorriendo el fichero
cls = None
methods = []          # (cls, signature, rva, offset)
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
    # la firma es la primera linea no vacia hacia atras que parezca una declaracion
    sig = ""
    for j in range(i - 1, max(-1, i - 8), -1):
        s = lines[j].strip()
        if not s:
            continue
        if "(" in s and ")" in s and not s.startswith("//"):
            sig = s
            break
    if sig:
        methods.append((cls, sig, rva.group(1), off.group(1)))

print(f"# metodos indexados: {len(methods)}", file=sys.stderr)

WANT = {
    "RobotStatus": [".ctor", "SetFixedBytes", "get_BleCommandArray",
                    "set_LeftMotorSpeed", "set_RightMotorSpeed",
                    "set_ServoMotorOneAngle", "set_ServoMotorTwoAngle",
                    "set_ServoMotorThreeAngle", "set_ServoMotorFourAngle",
                    "set_LedBlue", "set_LeftArmOffset", "set_LeftShoulderOffset"],
    "BleRobot": ["SetLeftMotorSpeed", "SetRightMotorSpeed", "SetBlueLed",
                 "SetFirstServoMotor", "SetSecondServoMotor",
                 "ResetStatus", "FixedUpdate", "StartScanning",
                 "OnCharacteristicDiscovered", "OnServiceDiscovered"],
    "RobotCommandsProxy": ["SetBlueLed", "SetLeftWheelSpeed", "SetRightWheelSpeed", "SetArmsAction"],
}

index = {}
for c, meths in WANT.items():
    for meth in meths:
        pat = re.compile(r"(?:^|[\.\s])" + re.escape(meth) + r"\s*\(")
        hit = next((m for m in methods if m[0] == c and pat.search(m[1])), None)
        if hit:
            print(f"{c}\t{meth}\t{hit[2]}\t{hit[3]}\t{hit[1]}")
        else:
            print(f"{c}\t{meth}\tNOT_FOUND\tNOT_FOUND\t-")
