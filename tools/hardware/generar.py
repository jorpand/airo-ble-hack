#!/usr/bin/env python3
"""Genera `docs/desensamblado/` con el desensamblado de los metodos clave.

Es el script que produjo los 18 ficheros `.asm` que prueban cada byte del
protocolo (y el `RESUMEN.md` que los resume).

Necesita la libreria de reversing (`tools/rev/disasm.py`) y el binario
desensamblado. Ver `docs/protocolo.md` § 3 para la cadena completa.

    python3 tools/hardware/generar.py --rev-dir ~/airo/rev
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
#: Donde esta `disasm.py` (la libreria de reversing).
TOOLS_REV = RAIZ / "tools" / "rev"
#: Donde se escriben los `.asm` y el `RESUMEN.md`.
SALIDA = RAIZ / "docs" / "desensamblado"

sys.path.insert(0, str(TOOLS_REV))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rev-dir",
        type=Path,
        default=Path(os.environ.get("AIRO_REV_DIR") or TOOLS_REV),
        help="carpeta de trabajo del reversing (donde esta il2cpp/ y dump/)",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=SALIDA,
        help="donde escribir los .asm (por defecto docs/desensamblado/)",
    )
    return parser.parse_args()


args = _args()
os.environ["AIRO_REV_DIR"] = str(args.rev_dir)

import disasm as D  # noqa: E402

OUT = args.salida
OUT.mkdir(parents=True, exist_ok=True)

METHODS = {
    "RobotStatus.ctor": (0x1FBDE74, "asigna el array: new byte[0x14] = 20 bytes"),
    "RobotStatus.SetFixedBytes": (0x1FBF968, "cabecera 0xA5 en data[0] y cola fija en data[10..19]"),
    "RobotStatus.set_LeftMotorSpeed": (0x1FBC8B4, "data[4]=direccion izq, data[5]=magnitud"),
    "RobotStatus.set_RightMotorSpeed": (0x1FBCA9C, "data[2]=direccion der, data[3]=magnitud"),
    "RobotStatus.set_LedBlue": (0x1FBCBC4, "data[1]=estado del LED"),
    "RobotStatus.set_ServoMotorOneAngle": (0x1FBCCE0, "data[6]=servo1"),
    "RobotStatus.set_ServoMotorTwoAngle": (0x1FBCF58, "data[7]=servo2"),
    "RobotStatus.set_ServoMotorThreeAngle": (0x1FBD25C, "data[8]=servo3"),
    "RobotStatus.set_ServoMotorFourAngle": (0x1FBD560, "data[9]=servo4"),
    "RobotStatus.set_LeftArmOffset": (0x1FBD6F0, "offset -> campo float, no byte del paquete"),
    "BleRobot.SetLeftMotorSpeed": (0x1FBC7C8, "redondeo Math.Round (banker's) antes de pasar el int"),
    "BleRobot.SetBlueLed": (0x1FBCB9C, "LED por enum"),
    "BleRobot.FixedUpdate": (0x1FBC688, "envio periodico del paquete + contador packageIdx"),
    "BleRobot.ResetStatus": (0x1FBBC04, "servos a 0"),
    "AiroControl.set_RightShoulderAngle": (0x1FB645C, "hombro derecho -> SetFirstServoMotor"),
    "AiroControl.set_RightArmAngle": (0x1FB649C, "brazo derecho -> SetSecondServoMotor"),
    "AiroControl.set_LeftArmAngle": (0x1FB641C, "brazo izquierdo -> SetThirdServoMotor"),
    "AiroControl.set_LeftShoulderAngle": (0x1FB63DC, "hombro izquierdo -> SetFourthServoMotor"),
}

index = ["# Evidencia — de donde sale cada byte del protocolo\n",
         "Desensamblado de `libil2cpp.so` (arm64-v8a) del APK oficial de AIRO.",
         "Las direcciones son RVAs del binario; el `Offset` de fichero es RVA - 0x4000.\n",
         "| Fichero | Método | Qué demuestra |", "|---|---|---|"]

for name, (rva, note) in METHODS.items():
    # corta en el primer 'ret' (con un minimo), no en la siguiente RVA:
    # algunos metodos son diminutos y la siguiente RVA cae dentro del cuerpo real
    path = OUT / (name.replace(".", "_") + ".asm")
    with open(path, "w") as f:
        f.write(f"# {name}\n# RVA 0x{rva:x} (file 0x{rva-0x4000:x})\n# {note}\n\n")
        n = 0
        for ins in D.md.disasm(D.so[rva - 0x4000:rva - 0x4000 + 0x400], rva):
            f.write(f"0x{ins.address:08x}  {ins.mnemonic:8s} {ins.op_str}\n")
            n += 1
            if ins.mnemonic == "ret" and n >= 8:
                break
    index.append(f"| `{path.name}` | `{name}` | {note} |")

(OUT / "RESUMEN.md").write_text("\n".join(index) + "\n", encoding="utf-8")
print(f"evidencia generada en {OUT}: {len(METHODS)} ficheros")
