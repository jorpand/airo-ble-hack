"""
Tests del servidor para Scratch (sin robot: no se toca el BLE).

Se comprueba que los comandos que llegan por HTTP se traducen bien al
estado del robot (ruedas, LED y brazos).

Ejecutar: python3 tests/test_server.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.server import AiroService  # noqa: E402
from airo_ble.protocol import Joint, Led  # noqa: E402


async def escenario() -> None:
    servicio = AiroService(None, connect_robot=False)
    servicio.thread.start()
    servicio.ready.set()
    await asyncio.sleep(0.1)

    # ruedas
    r = servicio.call({"type": "move", "left": 2, "right": -1})
    assert r["ok"], r
    cmd = servicio.robot.command
    assert cmd.left_speed == 2.0 and cmd.right_speed == -1.0

    r = servicio.call({"type": "stop"})
    assert r["ok"], r
    assert cmd.left_speed == 0.0 and cmd.right_speed == 0.0

    # LED
    r = servicio.call({"type": "led", "mode": "flash"})
    assert r["ok"], r
    assert cmd.led is Led.FLASH

    # brazo derecho (el original de ARM_POSES)
    r = servicio.call({"type": "arm", "side": "derecho", "pose": "arriba"})
    assert r["ok"], r
    assert cmd.servos[Joint.RIGHT_SHOULDER] == -60.0
    assert cmd.servos[Joint.RIGHT_ARM] == 170.0
    assert Joint.LEFT_SHOULDER not in cmd.servos

    # brazo izquierdo (el espejo)
    r = servicio.call({"type": "arm", "side": "izquierdo", "pose": "arriba"})
    assert r["ok"], r
    assert cmd.servos[Joint.LEFT_SHOULDER] == -60.0
    assert cmd.servos[Joint.LEFT_ARM] == 170.0

    # articulacion suelta
    r = servicio.call({"type": "pose", "joint": "left_arm", "angle": 30})
    assert r["ok"], r
    assert cmd.servos[Joint.LEFT_ARM] == 30.0

    # articulacion desconocida
    r = servicio.call({"type": "pose", "joint": "patita", "angle": 30})
    assert not r["ok"], r

    # comando desconocido
    r = servicio.call({"type": "inventado"})
    assert not r["ok"], r

    # el estado que ve Scratch
    estado = servicio.status()
    assert estado["led"] == "flash"
    assert "brazos" in estado


def main() -> int:
    try:
        asyncio.run(escenario())
    except AssertionError as exc:
        print(f"  FAIL test_server: {exc}")
        return 1
    print("  OK   test_server (comandos HTTP -> estado del robot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
