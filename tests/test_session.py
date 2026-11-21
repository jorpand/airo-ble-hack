"""
Tests del estado y la reconexion de la `RobotSession`, sin hardware.

Se comprueba lo que pasa cuando el robot **no** esta: que la sesion avise
del error mas reciente (y no del primero) y que no se quede reconectando en
bucle cerrado con un `disconnect()` en cada intento.

Ejecutar: python3 -m pytest tests/test_session.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.protocol import Command  # noqa: E402
from airo_ble.session import RobotSession  # noqa: E402


class RobotFalso:
    """Un robot que falla, y va fallando con mensajes distintos.

    Los mensajes se van gastando de una en uno; cuando se acaba la cola
    se repite el ultimo indefinidamente, asi que el robot no se "recupera"
    solo. Con `funciona = True` empieza a ir bien.
    """

    def __init__(self, errores: list[str]) -> None:
        self.errores = list(errores)
        self.ultimo = self.errores[-1] if self.errores else "fallo"
        self.funciona = False
        self.enviados = 0
        self.conexiones = 0
        self.desconexiones = 0
        self.command = Command()

    def _siguiente_error(self) -> str | None:
        if self.funciona:
            return None
        if self.errores:
            self.ultimo = self.errores.pop(0)
        return self.ultimo

    async def send(self, command, *, force: bool = False) -> bytes:
        self.enviados += 1
        error = self._siguiente_error()
        if error is not None:
            raise RuntimeError(error)
        return b""

    async def connect(self) -> None:
        self.conexiones += 1
        error = self._siguiente_error()
        if error is not None:
            raise RuntimeError(error)

    async def disconnect(self) -> None:
        self.desconexiones += 1


def _sesion_con(robot: RobotFalso, **kwargs) -> RobotSession:
    sesion = RobotSession(**kwargs)
    sesion.robot = robot  # type: ignore[assignment]
    return sesion


async def _parar(tarea: asyncio.Task) -> None:
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass


async def test_el_error_mostrado_es_el_mas_reciente() -> None:
    """La interfaz tiene que ensenar el ultimo error, no el primero.

    Antes el bucle de reconexion se tragaba la excepcion nueva con un
    `continue`, asi que `session.error` se quedaba con el primer error para
    siempre: con el robot apagado no se veia nunca el motivo real.
    """
    robot = RobotFalso(["primer error", "segundo error", "tercer error"])
    sesion = _sesion_con(robot, refresco=0.01, espera_reconexion=0.01)

    tarea = asyncio.create_task(sesion._refrescar())
    await asyncio.sleep(0.1)
    await _parar(tarea)

    assert sesion.error == "tercer error"
    assert sesion.conectado is False


async def test_desconecta_una_sola_vez_entre_intentos() -> None:
    """Antes se llamaba a `disconnect()` en cada reintento."""
    robot = RobotFalso(["e1", "e2", "e3", "e4"])
    sesion = _sesion_con(robot, refresco=0.01, espera_reconexion=0.01)

    tarea = asyncio.create_task(sesion._refrescar())
    await asyncio.sleep(0.1)
    await _parar(tarea)

    assert robot.desconexiones == 1, "deberia desconectar una sola vez"
    assert robot.conexiones >= 2, "deberia reintentar la conexion"


async def test_cuando_vuelve_el_robot_se_limpia_el_error() -> None:
    """Al reconectar, `error` se borra y `conectado` vuelve a ser True."""
    robot = RobotFalso(["fallo inicial", "fallo del reintento"])
    sesion = _sesion_con(robot, refresco=0.01, espera_reconexion=0.01)

    async def _limpiar() -> None:
        await asyncio.sleep(0.08)
        robot.funciona = True

    tarea = asyncio.create_task(sesion._refrescar())
    await _limpiar()
    await asyncio.sleep(0.15)
    await _parar(tarea)

    assert sesion.error is None
    assert sesion.conectado is True


async def test_el_error_de_conectar_se_ve_tambien() -> None:
    """El error de la reconexion (no solo el del envio) se guarda."""
    robot = RobotFalso(["se cayo el enlace", "no se puede conectar"])
    sesion = _sesion_con(robot, refresco=0.01, espera_reconexion=0.01)

    tarea = asyncio.create_task(sesion._refrescar())
    await asyncio.sleep(0.1)
    await _parar(tarea)

    assert sesion.error == "no se puede conectar"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
