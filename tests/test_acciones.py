"""
Tests del modelo de acciones: duracion, movimiento lento (rampa), alcance,
paradas implicitas y la cola de programas.

Son las reglas que pidio el usuario al rehacer el modelo de acciones:

  1. cada accion dura **al menos un segundo** (si no, los movimientos se
     confunden y uno se come al siguiente),
  2. un movimiento **lento** es el servo persiguiendo un destino que viaja
     (rampa), no un salto con una espera detras,
  3. los movimientos terminan **parando**,
  4. los dos brazos se pueden mover **en paralelo** (en el mismo paquete),
  5. cada accion tiene un **alcance** (que articulacion) y un **objetivo**
     (una pose o un angulo exacto),
  6. los programas se **encolan**: pulsar "ejecutar" dos veces no pisa el
     primero.

Ninguno de estos tests necesita robot: todos trabajan con los bytes y los
tiempos, sin BLE.

Ejecutar: python3 -m pytest tests/test_acciones.py -v
"""

from __future__ import annotations

import asyncio
import time

import pytest

from airo_ble.api.models import BloqueBrazo, Programa
from airo_ble.api.service import Traductor
from airo_ble.arms import (
    ESPERA_MINIMA,
    BrazoError,
    duracion_de_accion,
    resolver_brazos,
    resolver_objetivos,
    tiempo_de_viaje,
)
from airo_ble.protocol import Joint
from airo_ble.session import RobotSession, Step

# ---------------------------------------------------------------------------
# 1. La duracion: cada accion dura al menos un segundo
# ---------------------------------------------------------------------------


def test_toda_accion_dura_al_menos_un_segundo() -> None:
    """El suelo de la espera: sin esto los movimientos se confunden."""
    assert ESPERA_MINIMA == 1.0
    # aunque no haya a donde ir
    assert tiempo_de_viaje({}, {}) >= 1.0
    # aunque el movimiento sea de un grado
    assert tiempo_de_viaje({Joint.RIGHT_SHOULDER: 1.0}, {Joint.RIGHT_SHOULDER: 0.0}) >= 1.0


def test_el_viaje_cuanto_mas_largo_mas_tarda() -> None:
    """El servo va a una velocidad fija: 150 grados por segundo."""
    corto = tiempo_de_viaje({Joint.RIGHT_ARM: 10.0}, {Joint.RIGHT_ARM: 0.0})
    largo = tiempo_de_viaje({Joint.RIGHT_ARM: 170.0}, {Joint.RIGHT_ARM: 0.0})
    assert largo > corto
    assert largo == pytest.approx(170.0 / 150.0)


def test_el_tiempo_pedido_manda_sobre_el_viaje() -> None:
    """Un movimiento lento de 3 s dura 3 s, aunque el servo llegue antes."""
    objetivos = resolver_objetivos("derecho", pose="medio")
    assert duracion_de_accion(objetivos, {}, 3.0) == 3.0
    # y "de golpe" (0) dura lo que tarde el servo
    assert duracion_de_accion(objetivos, {}, 0.0) >= 1.0


# ---------------------------------------------------------------------------
# 2. El alcance: que articulacion se mueve y a donde va
# ---------------------------------------------------------------------------


def test_se_puede_mover_solo_el_hombro() -> None:
    objetivos = resolver_objetivos("derecho", pose="arriba", articulacion="hombro")
    assert objetivos == {Joint.RIGHT_SHOULDER: -60.0}


def test_se_puede_mover_solo_el_codo() -> None:
    objetivos = resolver_objetivos("derecho", pose="arriba", articulacion="codo")
    assert objetivos == {Joint.RIGHT_ARM: 170.0}


def test_con_todo_se_mueven_las_dos_articulaciones() -> None:
    objetivos = resolver_objetivos("derecho", pose="arriba")
    assert objetivos == {Joint.RIGHT_SHOULDER: -60.0, Joint.RIGHT_ARM: 170.0}


def test_el_angulo_exacto_manda_sobre_la_pose() -> None:
    """El angulo concreto es el objetivo, y solo mueve esa articulacion."""
    objetivos = resolver_objetivos(
        "derecho", pose="arriba", articulacion="codo", angulo=90.0
    )
    assert objetivos == {Joint.RIGHT_ARM: 90.0}


def test_el_angulo_exacto_necesita_una_sola_articulacion() -> None:
    """Con las dos articulaciones, un angulo no significa nada."""
    with pytest.raises(BrazoError):
        resolver_objetivos("derecho", pose="arriba", articulacion="todo", angulo=45.0)


def test_el_angulo_exacto_se_recorta_a_sus_limites() -> None:
    """No se puede pedir un ángulo fuera de la articulación."""
    objetivos = resolver_objetivos(
        "derecho", articulacion="hombro", angulo=500.0
    )
    assert objetivos == {Joint.RIGHT_SHOULDER: 77.0}  # el tope del hombro


def test_los_dos_brazos_en_paralelo_con_poses_distintas() -> None:
    """Lo que un (lado, pose) no puede expresar: dos lados, dos poses."""
    objetivos = resolver_brazos({"derecho": "arriba", "izquierdo": "abajo"})
    assert objetivos == {
        Joint.RIGHT_SHOULDER: -60.0,
        Joint.RIGHT_ARM: 170.0,
        Joint.LEFT_SHOULDER: 77.0,
        Joint.LEFT_ARM: -25.0,
    }
    # los cuatro en el mismo paquete: eso es el paralelismo
    assert len(objetivos) == 4


def test_un_lado_que_no_aparece_no_se_toca() -> None:
    objetivos = resolver_brazos({"derecho": "arriba"})
    assert Joint.LEFT_SHOULDER not in objetivos
    assert Joint.LEFT_ARM not in objetivos


# ---------------------------------------------------------------------------
# 3. La rampa: el movimiento lento de verdad
# ---------------------------------------------------------------------------


class ComandoEspia:
    """Se queda con todos los angulos que se le piden, en orden."""

    def __init__(self, real) -> None:
        self._real = real
        self.llamadas: list[tuple[Joint, float]] = []

    def set_joint(self, joint: Joint, angulo: float) -> None:
        self.llamadas.append((joint, angulo))
        self._real.set_joint(joint, angulo)

    def __getattr__(self, nombre: str):
        return getattr(self._real, nombre)


def _sesion_con_espia() -> tuple[RobotSession, ComandoEspia]:
    sesion = RobotSession()
    espia = ComandoEspia(sesion.robot.command)
    sesion.robot.command = espia  # type: ignore[assignment]
    return sesion, espia


def test_la_rampa_pasa_por_los_angulos_intermedios() -> None:
    """Un movimiento lento va poco a poco, no de un salto.

    Antes el "movimiento lento" era un salto con una espera detras: el servo
    llegaba de golpe y hacia el resto del tiempo. Ahora el destino viaja.
    """
    sesion, espia = _sesion_con_espia()
    objetivos = resolver_objetivos("derecho", pose="arriba")

    inicio = time.monotonic()
    asyncio.run(sesion._mover_servos(objetivos, 2.0))
    duracion = time.monotonic() - inicio

    angulos = [a for j, a in espia.llamadas if j is Joint.RIGHT_SHOULDER]
    assert len(angulos) > 5, "un movimiento lento no puede ser un solo salto"
    # van hacia el destino (que esta en -60) sin pasarse
    assert angulos == sorted(angulos, reverse=True)
    assert angulos[-1] == pytest.approx(-60.0)
    assert all(a >= -60.0 for a in angulos)
    # y ha durado lo pedido
    assert duracion >= 2.0


def test_la_rampa_llega_al_destino() -> None:
    sesion, espia = _sesion_con_espia()
    objetivos = resolver_objetivos("derecho", pose="abajo")
    asyncio.run(sesion._mover_servos(objetivos, 1.0))
    destino = espia.llamadas[-1]
    assert destino == (Joint.RIGHT_ARM, -25.0) or destino == (Joint.RIGHT_SHOULDER, 77.0)


def test_de_golpe_es_un_solo_salto() -> None:
    """Sin tiempo pedido no hay rampa: el servo va a por el destino."""
    sesion, espia = _sesion_con_espia()
    objetivos = resolver_objetivos("derecho", pose="arriba")
    asyncio.run(sesion._mover_servos(objetivos, 0.0))
    # un angulo por articulacion, sin intermedios
    assert len(espia.llamadas) == len(objetivos)
    assert {a for _, a in espia.llamadas} == {-60.0, 170.0}


def test_los_dos_brazos_van_en_el_mismo_paquete() -> None:
    """El paralelismo: los dos lados se piden a la vez."""
    sesion, espia = _sesion_con_espia()
    objetivos = resolver_brazos({"derecho": "arriba", "izquierdo": "abajo"})
    asyncio.run(sesion._mover_servos(objetivos, 0.0))
    assert len(espia.llamadas) == 4
    # los cuatro son del mismo paso: no hay dos comandos separados
    assert len({j for j, _ in espia.llamadas}) == 4


# ---------------------------------------------------------------------------
# 4. La cola: los programas se ejecutan uno detras de otro
# ---------------------------------------------------------------------------


class SesionEspia(RobotSession):
    """Apunta el orden en que se ejecutan los pasos."""

    def __init__(self) -> None:
        super().__init__()
        self.hechos: list[str] = []

    async def _ejecutar_paso(self, paso: Step) -> None:
        marca = paso.params.get("marca")
        if marca:
            self.hechos.append(marca)
        await super()._ejecutar_paso(paso)


async def test_los_programas_no_se_pisan() -> None:
    """Encolar dos programas: el segundo espera, no cancela al primero.

    Antes `ejecutar()` cancelaba el programa en curso, asi que pulsar
    "ejecutar" dos veces dejaba al robot a mitad de un movimiento.
    """
    sesion = SesionEspia()
    await sesion.ejecutar([Step("espera", {"marca": "a"}, 0.05)])
    await sesion.ejecutar([Step("espera", {"marca": "b"}, 0.05)])
    assert sesion.programas_en_cola == 1, "el segundo deberia estar esperando"

    await asyncio.sleep(0.4)
    assert sesion.hechos == ["a", "b"], "los dos programas tienen que correr, en orden"


async def test_parar_vacia_la_cola() -> None:
    """El boton de parar tambien se lleva los programas que esperaba."""
    sesion = SesionEspia()
    await sesion.ejecutar([Step("espera", {"marca": "a"}, 0.05)])
    await sesion.ejecutar([Step("espera", {"marca": "b"}, 0.05)])
    await sesion.detener_programa()
    assert sesion.programas_en_cola == 0


async def test_el_programa_termina_con_el_robot_parado() -> None:
    """Un programa SIEMPRE acaba parando (el `finally` de la sesion)."""
    sesion = SesionEspia()
    await sesion.ejecutar([Step("mover", {"izquierda": 2.0, "derecha": 2.0}, 0.05)])
    await asyncio.sleep(0.3)
    assert sesion.robot.command.left_speed == 0
    assert sesion.robot.command.right_speed == 0


# ---------------------------------------------------------------------------
# 5. La traduccion de la API
# ---------------------------------------------------------------------------


def test_la_api_simula_la_duracion_del_programa() -> None:
    """La duracion que dice la API es la de verdad: se simula el programa."""
    programa = Programa.model_validate(
        {
            "nombre": "Brazos",
            "bloques": [
                {"id": "1", "tipo": "brazo", "lado": "derecho", "pose": "arriba"},
                {"id": "2", "tipo": "brazo", "lado": "derecho", "pose": "medio"},
            ],
        }
    )
    pasos = Traductor.a_pasos(programa)
    duracion = Traductor.duracion_de(pasos, {})
    # dos acciones de brazo: cada una de al menos un segundo
    assert duracion >= 2.0
    # y la segunda tiene que contar el viaje desde "arriba" hasta "medio"
    assert duracion > 2.0


def test_un_movimiento_lento_dura_lo_pedido() -> None:
    programa = Programa.model_validate(
        {
            "nombre": "Lento",
            "bloques": [
                {
                    "id": "1",
                    "tipo": "brazo",
                    "lado": "derecho",
                    "pose": "arriba",
                    "segundos": 3,
                }
            ],
        }
    )
    pasos = Traductor.a_pasos(programa)
    assert Traductor.duracion_de(pasos, {}) == 3.0


def test_el_bloque_de_brazo_lleva_su_tiempo_y_su_alcance() -> None:
    bloque = BloqueBrazo.model_validate(
        {
            "id": "1",
            "tipo": "brazo",
            "lado": "izquierdo",
            "pose": "guardia",
            "articulacion": "codo",
            "angulo": 45,
            "segundos": 2,
        }
    )
    assert bloque.articulacion == "codo"
    assert bloque.angulo == 45
    assert bloque.segundos == 2


def test_el_angulo_exacto_con_las_dos_articulaciones_se_rechaza() -> None:
    """Se rechaza antes de ejecutar, no a mitad del movimiento."""
    with pytest.raises(ValueError):
        BloqueBrazo.model_validate(
            {
                "id": "1",
                "tipo": "brazo",
                "articulacion": "todo",
                "angulo": 45,
            }
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
