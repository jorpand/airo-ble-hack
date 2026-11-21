#!/usr/bin/env python3
"""
Verificacion en el robot real del MOVIMIENTO LENTO (rampa).

Comprueba que un brazo no sube de golpe sino que va persiguiendo un destino
que se mueve: se espia el paquete de 20 bytes que sale por BLE y se mira como
evoluciona el byte del hombro (6) y el del codo (7).

    # 1. Enciende el robot (power cycle: el HM-10 se duerme a los ~5 min)
    # 2. (opcional) pon la webcam mirando al robot
    # 3. Ejecuta:
    python3 tools/hardware/verificar_rampa.py

Lo que tiene que verse:

  - el brazo sube **poco a poco** (3 segundos), no de golpe;
  - los bytes del paquete van bajando escalon a escalon (byte 6: 20 -> 13);
  - al final el brazo se queda arriba y quieto.

No toca los bytes del protocolo: solo mira lo que ya sale.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.arms import resolver_objetivos  # noqa: E402
from airo_ble.protocol import Joint  # noqa: E402
from airo_ble.session import RobotSession  # noqa: E402

#: Byte de cada articulacion en el paquete (guia § 2).
BYTE = {
    Joint.RIGHT_SHOULDER: 6,
    Joint.RIGHT_ARM: 7,
    Joint.LEFT_ARM: 8,
    Joint.LEFT_SHOULDER: 9,
}


class EspiaPaquete:
    """Se queda con cada paquete de 20 bytes que sale por el BLE."""

    def __init__(self, robot) -> None:
        self._robot = robot
        self.paquetes: list[tuple[float, bytes]] = []
        # OJO: el original se guarda con otro nombre. Si se llamara
        # `self._escribir`, ese atributo taparia el metodo espia de mas abajo
        # y no se registraria nada.
        self._original = robot._escribir

    async def _escribir(self, payload: bytes, *, force: bool = False) -> bytes:
        self.paquetes.append((time.monotonic(), bytes(payload)))
        return await self._original(payload, force=force)

    def bytes_de(self, byte: int) -> list[int]:
        return [p[byte] for _, p in self.paquetes]


async def main() -> int:
    sesion = RobotSession(scan_timeout=60.0)
    print("Conectando con el robot (tarda hasta 60 s en anunciarse)...")
    try:
        await sesion.conectar()
    except Exception as exc:
        print(f"NO SE PUDO CONECTAR: {exc}")
        print("¿Lo has encendido? El HM-10 necesita un power cycle para despertar.")
        return 1
    print("Conectado.\n")

    espia = EspiaPaquete(sesion.robot)
    sesion.robot._escribir = espia._escribir  # type: ignore[method-assign]

    # 1. A "medio" (todo a 0) y esperamos a que se asiente.
    print("1. Poniendo el brazo derecho en 'medio'...")
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(1.5)

    # 2. El movimiento lento: 4 segundos hasta "arriba".
    print("2. Movimiento LENTO a 'arriba' en 4 segundos (mira el brazo)...")
    espia.paquetes.clear()
    inicio = time.monotonic()
    await sesion._mover_servos(resolver_objetivos("derecho", pose="arriba"), 4.0)
    duracion = time.monotonic() - inicio

    hombro = espia.bytes_de(BYTE[Joint.RIGHT_SHOULDER])
    codo = espia.bytes_de(BYTE[Joint.RIGHT_ARM])
    print(f"   duracion real: {duracion:.2f} s")
    print(f"   byte 6 (hombro der): {hombro}")
    print(f"   byte 7 (codo der):   {codo}")

    distintos = sorted(set(hombro))
    print(f"\n   valores distintos del hombro: {distintos}")
    if len(distintos) > 2:
        print("   OK: el byte va escalon a escalon (movimiento lento de verdad).")
    else:
        print("   AVISO: el byte apenas cambio. Puede que el robot no receive bien.")
    if hombro and hombro[-1] == 13 and codo and codo[-1] == 0:
        print("   OK: el destino final es el de la pose 'arriba' (13 y 0).")
    else:
        print(f"   AVISO: el final no es el esperado (hombro={hombro[-1:]} codo={codo[-1:]}).")

    # 3. Y de golpe, para comparar.
    print("\n3. El mismo destino, pero DE GOLPE...")
    espia.paquetes.clear()
    await sesion.brazo("derecho", "medio")
    await asyncio.sleep(1.5)
    espia.paquetes.clear()
    await sesion.brazo("derecho", "arriba")
    print(f"   byte 6 (hombro der): {espia.bytes_de(BYTE[Joint.RIGHT_SHOULDER])}")
    print("   (de golpe: un solo salto al destino)")

    await sesion.desconectar()
    print("\nFin. El robot queda desconectado y parado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
