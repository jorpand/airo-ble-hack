#!/usr/bin/env python3
"""
Mede la velocidad REAL del servo con el robot delante de la camara.

El modelo (arms.SERVO_VELOCIDAD = 150 grados/s) es una estimacion. Este
script mide cuanto tarda el brazo de verdad en ir de "medio" a "arriba" con un
movimiento "de golpe", que es lo que decide cuanto hay que esperar entre dos
acciones (si se espera menos, el servo cambia de destino a medio camino y los
movimientos se confunden).

    # 1. Enciende el robot (power cycle)
    # 2. Pon la webcam mirando al brazo
    # 3. En otra terminal, una foto cada 0,35 s:
    #    while true; do ffmpeg -f v4l2 -video_size 640x480 -i /dev/video0 \
    #        -frames:v 1 -y /tmp/vel/f$(date +%s%N).jpg; sleep 0.35; done
    # 4. Ejecuta este script
    python3 tools/hardware/medir_velocidad_servo.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

    print("1. A 'medio' (codo a 0 grados) y esperando a que se asiente...")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(6.0)

    print("2. Ahora 'de golpe' a 'arriba'. Los tiempos de abajo son los del script;")
    print("   las fotos (con la marca de tiempo de cada una) son las del comando de ffmpeg.")
    inicio = time.monotonic()
    await sesion.brazo("derecho", "arriba")
    print(f"   destino mandado a los {inicio - (inicio - inicio):.2f} s del script")

    # Se queda quieto 25 s: el servo sigue persiguiendo el destino mientras
    # nosotros miramos cuando deja de moverse.
    for i in range(25):
        await asyncio.sleep(1.0)
        print(f"   +{i+1:2d} s", flush=True)

    await sesion.desconectar()
    print("\nFin. Mira ahora las fotos: el brazo deja de moverse cuando se queda")
    print("igual dos fotos seguidas (con algo de ruido de la imagen).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
