#!/usr/bin/env python3
"""
Compara en el robot real: movimiento LENTO (rampa) frente a DE GOLPE.

    # 1. Enciende el robot (power cycle)
    # 2. Camara mirando al robot (los brazos tienen que verse)
    # 3. En otra terminal, una foto cada 0,15 s recortando al robot:
    #    while true; do ffmpeg -f v4l2 -video_size 1280x720 -i /dev/video0 \
    #      -frames:v 1 -vf "crop=380:210:470:505" -y /tmp/cmp/f$(date +%s%N).jpg; \
    #      sleep 0.15; done
    # 4. python3 tools/hardware/comparar_lento_vs_golpe.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.arms import resolver_objetivos  # noqa: E402
from airo_ble.session import RobotSession  # noqa: E402


async def main() -> int:
    sesion = RobotSession(scan_timeout=60.0)
    print("Conectando...")
    try:
        await sesion.conectar()
    except Exception as exc:
        print(f"NO SE PUDO CONECTAR: {exc}")
        return 1
    print("Conectado.\n")

    objetivos = resolver_objetivos("derecho", pose="arriba")

    print("A) De golpe: de 'medio' a 'arriba'")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(5.0)
    t0 = time.monotonic()
    await sesion.brazo("derecho", "arriba")
    print(f"   destino mandado a los {t0:.2f} s")
    await asyncio.sleep(6.0)

    print("\nB) Lento (rampa de 4 s): de 'medio' a 'arriba'")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(5.0)
    t1 = time.monotonic()
    await sesion._mover_servos(objetivos, 4.0)
    print(f"   rampa mandada a los {t1:.2f} s (tarda 4 s)")
    await asyncio.sleep(6.0)

    await sesion.desconectar()
    print("\nFin. En las fotos: el brazo llega mucho mas tarde en el caso B.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
