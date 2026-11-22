"""
Tests del servidor para Scratch (sin robot: no se toca el BLE).

Se comprueba que los comandos que llegan por HTTP se traducen bien al
estado del robot (ruedas, LED y brazos), y tambien el camino que usan los
bloques de Scratch: el orden de los argumentos y las respuestas.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from airo_ble.protocol import Joint, Led
from airo_ble.server import AiroService


@pytest.fixture(scope="module")
def servicio() -> Any:
    """El servidor de Scratch, arrancado sin buscar el robot."""
    svc = AiroService(None, connect_robot=False)
    svc.thread.start()
    svc.ready.set()
    # La conexion vive en otro hilo: hay que darle un turno.
    asyncio.run(asyncio.sleep(0.1))
    return svc


def test_las_ruedas_mueven_el_robot(servicio: Any) -> None:
    """El comando "move" pone las ruedas."""
    r = servicio.call({"type": "move", "left": 2, "right": -1})
    assert r["ok"], r
    cmd = servicio.robot.command
    assert cmd.left_speed == 2.0 and cmd.right_speed == -1.0

    r = servicio.call({"type": "stop"})
    assert r["ok"], r
    assert cmd.left_speed == 0.0 and cmd.right_speed == 0.0


def test_la_luz_del_robot(servicio: Any) -> None:
    """El comando "led" cambia el LED azul del robot."""
    r = servicio.call({"type": "led", "mode": "flash"})
    assert r["ok"], r
    assert servicio.robot.command.led is Led.FLASH


def test_el_brazo_derecho(servicio: Any) -> None:
    """El brazo derecho es el original de ARM_POSES."""
    r = servicio.call({"type": "arm", "side": "derecho", "pose": "arriba"})
    assert r["ok"], r
    cmd = servicio.robot.command
    assert cmd.servos[Joint.RIGHT_SHOULDER] == -60.0
    assert cmd.servos[Joint.RIGHT_ARM] == 170.0
    assert Joint.LEFT_SHOULDER not in cmd.servos


def test_el_brazo_izquierdo_es_el_espejo(servicio: Any) -> None:
    """El brazo izquierdo es el espejo del derecho."""
    r = servicio.call({"type": "arm", "side": "izquierdo", "pose": "arriba"})
    assert r["ok"], r
    cmd = servicio.robot.command
    assert cmd.servos[Joint.LEFT_SHOULDER] == -60.0
    assert cmd.servos[Joint.LEFT_ARM] == 170.0


def test_una_articulacion_suelta(servicio: Any) -> None:
    """El comando "pose" mueve una articulacion concreta."""
    r = servicio.call({"type": "pose", "joint": "left_arm", "angle": 30})
    assert r["ok"], r
    assert servicio.robot.command.servos[Joint.LEFT_ARM] == 30.0


def test_una_articulacion_desconocida_falla(servicio: Any) -> None:
    """Una articulacion que no existe se rechaza (con su error)."""
    r = servicio.call({"type": "pose", "joint": "patita", "angle": 30})
    assert not r["ok"], r


def test_un_comando_desconocido_falla(servicio: Any) -> None:
    """Un comando que el servidor no entiende se rechaza."""
    r = servicio.call({"type": "inventado"})
    assert not r["ok"], r


def test_el_estado_que_ve_scratch(servicio: Any) -> None:
    """El estado tiene lo que la extension y los bloques necesitan."""
    servicio.call({"type": "led", "mode": "flash"})
    estado = servicio.status()
    assert estado["led"] == "flash"
    assert "brazos" in estado
    assert "conectado" in estado
    assert estado["izquierda"] == 0.0


def test_el_brazo_con_angulo_exacto(servicio: Any) -> None:
    """Una articulacion a un angulo exacto (lo que manda el bloque)."""
    r = servicio.call(
        {"type": "arm", "side": "izquierdo", "joint": "codo", "angle": 45}
    )
    assert r["ok"], r
    # El codo izquierdo es el espejo del derecho.
    assert servicio.robot.command.servos[Joint.LEFT_ARM] == 45.0


def test_el_brazo_con_angulo_necesita_una_articulacion(servicio: Any) -> None:
    """Un angulo exacto con "todo" no significa nada: se rechaza."""
    r = servicio.call(
        {"type": "arm", "side": "izquierdo", "joint": "todo", "angle": 45}
    )
    assert not r["ok"], r
