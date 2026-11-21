#!/usr/bin/env python3
"""
Medida final y sin ambiguedad: cuando llega de verdad el brazo en cada caso.

Imprime la hora de reloj (la misma que la de las fotos) en cada momento
clave, para poder alinear las fotos con los comandos sin suposiciones:

    # 1. Enciende el robot
    # 2. Camara mirando al robot
    # 3. En otra terminal:
    #    i=0; while [ $i -lt 200 ]; do i=$((i+1)); ffmpeg -f v4l2 \
    #      -video_size 1280x720 -i /dev/video0 -frames:v 1 \
    #      -vf "crop=380:210:470:505" -y /tmp/cmp/f$(printf %03d $i).jpg; \
    #      sleep 0.1; done
    # 4. python3 tools/hardware/medida_final.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.arms import resolver_objetivos  # noqa: E402
from airo_ble.session import RobotSession  # noqa: E402


def marca(texto: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)


async def main() -> int:
    sesion = RobotSession(scan_timeout=60.0)
    marca("conectando...")
    try:
        await sesion.conectar()
    except Exception as exc:
        marca(f"NO SE PUDO CONECTAR: {exc}")
        return 1
    marca("conectado")
    objetivos = resolver_objetivos("derecho", pose="arriba")

    marca("A) a 'medio' (espera 6 s)")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(6.0)

    marca("B) DE GOLPE a 'arriba'")
    await sesion.brazo("derecho", "arriba")
    await asyncio.sleep(8.0)

    marca("C) a 'medio' (espera 6 s)")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(6.0)

    marca("D) LENTO (rampa de 4 s) a 'arriba'")
    await sesion._mover_servos(objetivos, 4.0)
    await asyncio.sleep(8.0)

    marca("fin")
    await sesion.desconectar()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
