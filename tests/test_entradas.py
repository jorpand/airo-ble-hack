"""
Tests de las dos entradas que quedaban atrasadas: la **consola** y el
**puente de Scratch**.

Las tres entradas (la API web, la consola y Scratch) tienen que entender el
**mismo modelo de acciones**:

  - una pose, o una articulacion a un angulo exacto,
  - de golpe (0 segundos) o lento (rampa) durante X segundos,
  - y los bytes que salen tienen que ser los de siempre para la sintaxis
    vieja (`brazo der arriba`).

Ejecutar: python3 -m pytest tests/test_entradas.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.arms import resolver_objetivos  # noqa: E402
from airo_ble.client import AiroRobot  # noqa: E402
from airo_ble.console import Console, ConsoleError  # noqa: E402
from airo_ble.protocol import Command, Joint  # noqa: E402
from airo_ble.server import AiroService  # noqa: E402

#: Byte de cada articulacion en el paquete (guia § 2).
BYTE = {
    Joint.RIGHT_SHOULDER: 6,
    Joint.RIGHT_ARM: 7,
    Joint.LEFT_ARM: 8,
    Joint.LEFT_SHOULDER: 9,
}


def bytes_de(movimientos: dict[Joint, float]) -> dict[int, int]:
    """Los bytes que salen de un mapa articulacion -> angulo."""
    comando = Command()
    for joint, angle in movimientos.items():
        comando.set_joint(joint, angle)
    paquete = comando.to_bytes()
    return {BYTE[joint]: paquete[BYTE[joint]] for joint in movimientos}


class ComandoEspia:
    """Apunta cada angulo que se le pide al comando, en orden."""

    def __init__(self, real: Command) -> None:
        self._real = real
        self.llamadas: list[tuple[Joint, float]] = []

    def set_joint(self, joint: Joint, angulo: float) -> None:
        self.llamadas.append((joint, angulo))
        self._real.set_joint(joint, angulo)

    def __getattr__(self, nombre: str):
        return getattr(self._real, nombre)


def consola() -> Console:
    return Console(AiroRobot(), dry_run=True, echo=False, keepalive=False)


def ejecutar(linea: str) -> Console:
    c = consola()
    asyncio.run(c.execute(linea))
    return c


def servicio() -> AiroService:
    return AiroService(address=None, connect_robot=False)


# ---------------------------------------------------------------------------
# 1. La consola
# ---------------------------------------------------------------------------


def test_la_consola_mueve_la_pose_como_siempre() -> None:
    """La sintaxis vieja no cambia: los bytes son los de siempre."""
    c = ejecutar("brazo der arriba")
    assert bytes_de(c.robot.command.servos) == {6: 13, 7: 0}


def test_la_consola_acepta_el_tiempo_de_la_pose() -> None:
    """`brazo der arriba 3` es la misma pose, pero lenta."""
    c = ejecutar("brazo der arriba 3")
    assert bytes_de(c.robot.command.servos) == {6: 13, 7: 0}


def test_la_consola_mueve_una_sola_articulacion() -> None:
    """`brazo der codo 90`: solo el codo (byte 7)."""
    c = ejecutar("brazo der codo 90")
    assert set(c.robot.command.servos) == {Joint.RIGHT_ARM}
    esperado = bytes_de(resolver_objetivos("derecho", articulacion="codo", angulo=90.0))
    assert bytes_de(c.robot.command.servos) == esperado


def test_la_consola_recorta_el_angulo_a_sus_limites() -> None:
    """El hombro no llega mas alla de 77 grados."""
    c = ejecutar("brazo der hombro 500")
    assert c.robot.command.servos[Joint.RIGHT_SHOULDER] == 77.0


def test_la_consola_da_error_si_no_entiende_el_destino() -> None:
    with pytest.raises(ConsoleError):
        ejecutar("brazo der bailando")
    with pytest.raises(ConsoleError):
        ejecutar("brazo der codo")  # falta el angulo
    with pytest.raises(ConsoleError):
        ejecutar("brazo")  # falta el lado y la pose


def test_el_movimiento_lento_de_la_consola_es_una_rampa() -> None:
    """El destino va viajando, no es un salto con una espera detras."""
    c = consola()
    espia = ComandoEspia(c.robot.command)
    c.robot.command = espia  # type: ignore[assignment]
    asyncio.run(c.execute("brazo der arriba 1"))

    angulos = [a for j, a in espia.llamadas if j is Joint.RIGHT_SHOULDER]
    assert len(angulos) > 5, "un movimiento lento no puede ser un solo salto"
    assert angulos == sorted(angulos, reverse=True)
    assert angulos[-1] == pytest.approx(-60.0)


# ---------------------------------------------------------------------------
# 2. El puente de Scratch
# ---------------------------------------------------------------------------


def test_scratch_mueve_la_pose_como_siempre() -> None:
    s = servicio()
    respuesta = asyncio.run(s._apply({"type": "arm", "side": "left", "pose": "arriba"}))
    assert respuesta["ok"] is True
    assert bytes_de(s.robot.command.servos) == {8: 40, 9: 27}


def test_scratch_mueve_una_sola_articulacion() -> None:
    """`joint` + `angle`: solo ese brazo y solo esa articulacion."""
    s = servicio()
    respuesta = asyncio.run(
        s._apply(
            {"type": "arm", "side": "left", "joint": "codo", "angle": 90}
        )
    )
    assert respuesta["ok"] is True
    assert set(s.robot.command.servos) == {Joint.LEFT_ARM}
    assert s.robot.command.servos[Joint.LEFT_ARM] == 90.0


def test_scratch_rechaza_el_angulo_con_las_dos_articulaciones() -> None:
    """Un angulo para hombro y codo no significa nada: se rechaza."""
    s = servicio()
    respuesta = asyncio.run(
        s._apply({"type": "arm", "side": "left", "joint": "todo", "angle": 90})
    )
    assert respuesta["ok"] is False
    assert "articulación" in respuesta["error"]


def test_scratch_rechaza_un_lado_malo() -> None:
    s = servicio()
    respuesta = asyncio.run(s._apply({"type": "arm", "side": "medio", "pose": "arriba"}))
    assert respuesta["ok"] is False
    assert "Lado desconocido" in respuesta["error"]


def test_el_movimiento_lento_de_scratch_es_una_rampa() -> None:
    """Con `duration`, el destino viaja (y va en segundo plano)."""

    async def _escena():
        s = servicio()
        espia = ComandoEspia(s.robot.command)
        s.robot.command = espia  # type: ignore[assignment]
        # OJO: todo en el MISMO bucle de eventos. El movimiento lento sigue
        # en segundo plano, asi que si el bucle se cierra al terminar la
        # peticion, la tarea muere con el.
        await s._apply(
            {"type": "arm", "side": "right", "pose": "arriba", "duration": 1}
        )
        await asyncio.sleep(1.6)
        return espia

    espia = asyncio.run(_escena())
    angulos = [a for j, a in espia.llamadas if j is Joint.RIGHT_SHOULDER]
    assert len(angulos) > 5, "un movimiento lento no puede ser un solo salto"
    assert angulos == sorted(angulos, reverse=True)
    assert angulos[-1] == pytest.approx(-60.0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
