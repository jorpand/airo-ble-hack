"""
Tests de seguridad: el robot nunca debe quedarse moviendo solo.

Estos tests cubren los arreglos de la "Fase 1" del plan de mejoras:

  1. el watchdog de la consola tiene que **parar** las ruedas (no solo
     reenviar el paquete con la misma velocidad),
  2. un programa que termina tiene que dejar el robot parado,
  3. desconectar (web, API o Scratch) tiene que parar el robot antes de
     soltar el BLE,
  4. `/api/mover` con tiempo tiene que parar al acabar.

Ninguno de ellos necesita hardware: se usa el modo `--dry-run` de la
consola y la sesion sin conexion (los `send` fallan y se ignoran).

Ejecutar: python3 -m pytest tests/test_safety.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.client import AiroRobot  # noqa: E402
from airo_ble.console import Console  # noqa: E402
from airo_ble.session import RobotSession, Step  # noqa: E402
from airo_ble.api.main import app, servicio  # noqa: E402
from airo_ble.api.models import Programa  # noqa: E402
from airo_ble.api.service import Traductor  # noqa: E402
from airo_ble.server import AiroService  # noqa: E402


# ---------------------------------------------------------------------------
# 1. El watchdog tiene que parar las ruedas
# ---------------------------------------------------------------------------


class RobotFalso(AiroRobot):
    """Un robot sin BLE que se traga los envios.

    El keepalive no arranca en modo `--dry-run` (no tiene sentido refrescar
    sin conexion), asi que para probar el bucle hace falta un robot que
    acepte los envios.
    """

    def __init__(self) -> None:
        super().__init__()
        self.enviados: list[bytes] = []

    async def send(self, command, *, force: bool = False) -> bytes:  # type: ignore[override]
        payload = command.to_bytes()
        self.enviados.append(payload)
        return payload

    async def send_raw(self, payload: bytes) -> bytes:  # type: ignore[override]
        return bytes(payload)


async def test_el_watchdog_para_las_ruedas() -> None:
    """Sin ordenes recientes, el watchdog deja las ruedas a cero.

    Antes solo reenviaba el paquete con la misma velocidad, asi que el robot
    se quedaba dando vueltas indefinidamente.
    """
    robot = RobotFalso()
    console = Console(
        robot,
        dry_run=False,
        echo=False,
        watchdog=0.05,
        keepalive_interval=0.01,
    )
    robot.command.left_speed = 2.0
    robot.command.right_speed = 2.0

    await console.start_keepalive()
    # se simula que hace rato que no se escribe nada
    console._last_input = 0.0
    await asyncio.sleep(0.15)
    await console.stop_keepalive()

    assert robot.command.left_speed == 0.0
    assert robot.command.right_speed == 0.0


async def test_el_watchdog_manda_el_paquete_a_cero() -> None:
    """El paquete que sale despues del watchdog lleva velocidad 0."""
    robot = RobotFalso()
    console = Console(
        robot,
        dry_run=False,
        echo=False,
        watchdog=0.05,
        keepalive_interval=0.01,
    )
    robot.command.left_speed = 2.0
    await console.start_keepalive()
    console._last_input = 0.0
    await asyncio.sleep(0.15)
    await console.stop_keepalive()

    assert robot.enviados, "no se mando ningun paquete"
    # los bytes 2-5 son las velocidades: todos a cero
    assert robot.enviados[-1][2:6] == b"\x00\x00\x00\x00"


async def test_el_watchdog_no_toca_las_ruedas_si_no_mueven() -> None:
    """Si las ruedas ya estan paradas, el watchdog no molesta."""
    robot = RobotFalso()
    console = Console(
        robot, dry_run=False, echo=False, watchdog=0.05, keepalive_interval=0.01
    )
    await console.start_keepalive()
    console._last_input = 0.0
    await asyncio.sleep(0.1)
    await console.stop_keepalive()
    assert (robot.command.left_speed, robot.command.right_speed) == (0.0, 0.0)


async def test_el_watchdog_no_para_mientras_hay_un_comando_en_marcha() -> None:
    """La kata dura ~20 s: el watchdog no debe parar las ruedas a mitad.

    El watchdog mide el tiempo desde la ultima orden escrita, asi que sin
    este control pararia el robot en mitad de la coreografia.
    """
    robot = RobotFalso()
    console = Console(
        robot, dry_run=False, echo=False, watchdog=0.05, keepalive_interval=0.01
    )

    async def _cmd_dormir(args: list[str]) -> str:
        await asyncio.sleep(0.3)
        return "done"

    console._cmd_dormir = _cmd_dormir  # type: ignore[attr-defined]
    robot.command.left_speed = 2.0

    await console.start_keepalive()
    console._last_input = 0.0
    tarea = asyncio.create_task(console.execute("dormir"))
    await asyncio.sleep(0.2)  # el comando sigue en marcha
    await console.stop_keepalive()
    await tarea

    assert robot.command.left_speed == 2.0  # no lo ha parado
    assert console._en_ejecucion == 0


async def test_parar_manda_el_paquete_con_velocidad_cero() -> None:
    """`parar` deja el estado a 0 y avisa de inmediato."""
    robot = RobotFalso()
    console = Console(robot, dry_run=False, echo=False, keepalive=False)
    robot.command.left_speed = 2.0
    robot.command.right_speed = -1.0
    await console.parar()
    assert (robot.command.left_speed, robot.command.right_speed) == (0.0, 0.0)
    assert robot.enviados[-1][2:6] == b"\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# 2. Un programa que termina deja el robot parado
# ---------------------------------------------------------------------------


async def test_el_programa_termina_con_el_robot_parado() -> None:
    sesion = RobotSession()
    await sesion._ejecutar(
        [Step("mover", {"izquierda": 2.0, "derecha": 2.0}, 0.01)]
    )
    cmd = sesion.robot.command
    assert cmd.left_speed == 0.0
    assert cmd.right_speed == 0.0


async def test_el_programa_para_tambien_si_falla() -> None:
    """Si un paso peta, el robot tampoco se queda moviendo."""
    sesion = RobotSession()
    await sesion._ejecutar(
        [
            Step("mover", {"izquierda": 2.0, "derecha": 2.0}, 0.01),
            Step("inventado", {}),
        ]
    )
    cmd = sesion.robot.command
    assert cmd.left_speed == 0.0
    assert cmd.right_speed == 0.0
    assert sesion.error  # el error se guarda


async def test_parar_el_programa_deja_el_robot_parado() -> None:
    """Cancelar un programa en marcha también para las ruedas."""
    sesion = RobotSession()
    sesion.robot.command.left_speed = 2.0
    await sesion.detener_programa()
    assert sesion.robot.command.left_speed == 0.0


# ---------------------------------------------------------------------------
# 3. Desconectar tiene que parar el robot
# ---------------------------------------------------------------------------


async def test_desconectar_para_el_robot() -> None:
    sesion = RobotSession()
    sesion.robot.command.left_speed = 2.0
    sesion.robot.command.right_speed = 2.0
    await sesion.desconectar()
    cmd = sesion.robot.command
    assert cmd.left_speed == 0.0
    assert cmd.right_speed == 0.0


async def test_el_servidor_de_scratch_para_el_robot_al_apagarse() -> None:
    """Si apagas el servidor con el robot en marcha, este se para."""
    servicio_scratch = AiroService(address=None, connect_robot=False)
    servicio_scratch.robot.command.left_speed = 2.0
    servicio_scratch.robot.command.right_speed = -2.0
    await servicio_scratch._stop()
    cmd = servicio_scratch.robot.command
    assert cmd.left_speed == 0.0
    assert cmd.right_speed == 0.0


# ---------------------------------------------------------------------------
# 4. La API: /api/mover para al acabar
# ---------------------------------------------------------------------------


def test_mover_deja_el_robot_parado() -> None:
    """Un movimiento con tiempo no puede dejar al robot dando vueltas."""
    from fastapi.testclient import TestClient

    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/mover", json={"izquierda": 2, "derecha": 2, "segundos": 0.2}
        )
        assert r.status_code == 200
        cmd = servicio.sesion.robot.command
        assert cmd.left_speed == 0.0
        assert cmd.right_speed == 0.0


def test_mover_sin_tiempo_deja_las_ruedas_puestas() -> None:
    """`segundos=0` es movimiento sostenido: se para con /api/parar."""
    from fastapi.testclient import TestClient

    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/mover", json={"izquierda": 1, "derecha": 1, "segundos": 0}
        )
        assert r.status_code == 200
        cmd = servicio.sesion.robot.command
        assert cmd.left_speed == 1.0
        # y se para cuando se le dice
        cliente.post("/api/parar")
        assert cmd.left_speed == 0.0


# ---------------------------------------------------------------------------
# 5. La duracion real del programa (para la interfaz)
# ---------------------------------------------------------------------------


def test_la_duracion_del_programa_se_suma_bien() -> None:
    programa = Programa.model_validate(
        {
            "nombre": "Prueba",
            "bloques": [
                {"id": "1", "tipo": "avanzar", "segundos": 2},
                {"id": "2", "tipo": "girar", "segundos": 1},
                {"id": "3", "tipo": "espera", "segundos": 0.5},
                {"id": "4", "tipo": "luz", "modo": "encendida"},
                {
                    "id": "5",
                    "tipo": "repetir",
                    "veces": 2,
                    "bloques": [{"id": "6", "tipo": "espera", "segundos": 0.5}],
                },
            ],
        }
    )
    pasos = Traductor.a_pasos(programa)
    # avanzar 2 + girar 1 + espera 0,5 + luz 0,4 + repetir(2 x 0,5) = 4,9
    # (la luz espera 0,4 s: sin espera el flash no llega a verse)
    assert Traductor.duracion_de(pasos) == pytest.approx(4.9)


def test_la_respuesta_dice_cuanto_dura() -> None:
    """La interfaz necesita la duracion para no adivinarla."""
    from fastapi.testclient import TestClient

    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/programa",
            json={
                "programa": {
                    "nombre": "Mini",
                    "bloques": [
                        {"id": "1", "tipo": "avanzar", "segundos": 2},
                        {"id": "2", "tipo": "espera", "segundos": 1},
                    ],
                }
            },
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["duracion"] == pytest.approx(3.0)
        assert datos["pasos"] == 4  # avanzar(mover+parar) + espera + parar final


def test_la_kata_dura_lo_que_dice_durar() -> None:
    """El bloque de kata también tiene duracion (no 0)."""
    from airo_ble.api.models import BloqueKata
    from airo_ble.console import KATA

    pasos = Traductor.bloque_a_pasos(BloqueKata())
    esperado = sum(d for _, d in KATA)
    assert Traductor.duracion_de(pasos) == pytest.approx(esperado)
    assert esperado > 0
