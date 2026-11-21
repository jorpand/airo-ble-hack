"""
Tests de los brazos: que lado se mueve y, sobre todo, **que bytes salen**.

Estos tests fijan los bytes EXACTOS de cada pose y cada lado. Son la red de
seguridad del renombrado del enum `Joint` (tarea 2.8 del plan, y otra vez en
la 2.9 cuando se comprobo con el robot delante que los nombres fisicos estaban
cambiados): si ese cambio mueve un solo byte, el robot mueve un brazo al reves
y estos tests saltan.

Tambien comprueban que las tres entradas (consola, sesion de la API y puente
de Scratch) mueven los brazos **igual**. Antes cada una tenia su propia
copia de la logica de "izquierda" y se contradecian:

  - la sesion no entendia "ambos" y solo movia un brazo,
  - el servidor de Scratch no entendia "left" y movia el brazo derecho.

Ejecutar: python3 -m pytest tests/test_arms.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.arms import (  # noqa: E402
    LADOS,
    BrazoError,
    resolver_brazo,
    resolver_lado,
)
from airo_ble.client import AiroRobot  # noqa: E402
from airo_ble.console import CALIBRATION_DEFAULT, Console  # noqa: E402
from airo_ble.protocol import (  # noqa: E402
    JOINT_NAMES,
    Command,
    Joint,
    encode_servo,
)
from airo_ble.session import RobotSession  # noqa: E402
from airo_ble.server import AiroService  # noqa: E402

#: Byte del paquete de cada articulacion.
#:
#: El enum `Joint` usa los nombres FISICOS (los de la guia): byte 6 = hombro
#: derecho, 7 = codo derecho, 8 = codo izquierdo, 9 = hombro izquierdo.
BYTE_DE: dict[Joint, int] = {
    Joint.RIGHT_SHOULDER: 6,
    Joint.RIGHT_ARM: 7,
    Joint.LEFT_ARM: 8,
    Joint.LEFT_SHOULDER: 9,
}

#: Bytes que DEBEN salir por cada pose, indexados por byte del paquete.
#:
#: Se escriben a mano (no se recalculan con `encode_servo`) a proposito: si
#: alguien cambia el enum o el escalado, este test dice exactamente que byte
#: se ha movido. El conjunto de 4 bytes de cada pose NO ha cambiado nunca: lo
#: unico que se ha movido es el nombre fisico de cada byte (verificado con el
#: robot delante: el byte 6 es el hombro DERECHO del robot).
BYTES_ESPERADOS: dict[str, dict[int, int]] = {
    "arriba": {6: 13, 7: 0, 8: 40, 9: 27},
    "abajo": {6: 29, 7: 23, 8: 17, 9: 11},
    "medio": {6: 20, 7: 20, 8: 20, 9: 20},
    "golpe": {6: 13, 7: 23, 8: 17, 9: 27},
    "guardia": {6: 13, 7: 9, 8: 31, 9: 27},
}

#: Que bytes del paquete escribe cada lado (los de su brazo fisico).
BYTES_DE_CADA_LADO: dict[str, tuple[int, ...]] = {
    "izquierdo": (9, 8),
    "derecho": (6, 7),
}


def bytes_de(movimientos: dict[Joint, float]) -> dict[int, int]:
    """Los bytes que salen de un mapa articulacion -> angulo."""
    comando = Command()
    for joint, angle in movimientos.items():
        comando.set_joint(joint, angle)
    paquete = comando.to_bytes()
    return {BYTE_DE[joint]: paquete[BYTE_DE[joint]] for joint in movimientos}


# ---------------------------------------------------------------------------
# 1. Los bytes de cada pose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pose", sorted(BYTES_ESPERADOS))
@pytest.mark.parametrize("lado", ("derecho", "izquierdo"))
def test_los_bytes_de_cada_pose_no_cambian(pose: str, lado: str) -> None:
    """Cada lado escribe sus bytes, con los valores de siempre."""
    movimientos = resolver_brazo(lado, pose)
    esperado = {
        byte: BYTES_ESPERADOS[pose][byte]
        for byte in BYTES_DE_CADA_LADO[lado]
    }
    assert bytes_de(movimientos) == esperado


@pytest.mark.parametrize("pose", sorted(BYTES_ESPERADOS))
def test_los_dos_lados_juntos_son_los_cuatro_bytes(pose: str) -> None:
    """"ambos" = los cuatro bytes de la pose."""
    movimientos = resolver_brazo("ambos", pose)
    assert bytes_de(movimientos) == BYTES_ESPERADOS[pose]


@pytest.mark.parametrize("pose", sorted(BYTES_ESPERADOS))
def test_los_lados_son_simetricos(pose: str) -> None:
    """Los dos lados se espejan: sus bytes suman 40 (= 2 x centro)."""
    for byte_izq, byte_der in ((9, 6), (8, 7)):
        a = bytes_de(resolver_brazo("izquierdo", pose))[byte_izq]
        b = bytes_de(resolver_brazo("derecho", pose))[byte_der]
        assert a + b == 40, f"{pose}: bytes {a} y {b} no son simetricos"


def test_el_protocolo_no_se_mueve() -> None:
    """Byte -> signo y limites: esto no lo puede tocar un renombrado."""
    from airo_ble.protocol import SERVO_LIMITS, SERVO_SIGN

    esperado = {
        6: (+1, (-60, 77)),
        7: (-1, (-25, 170)),
        8: (+1, (-25, 170)),
        9: (-1, (-60, 77)),
    }
    for joint, byte in BYTE_DE.items():
        assert SERVO_SIGN[joint] == esperado[byte][0], f"signo de {joint.name}"
        assert SERVO_LIMITS[joint] == esperado[byte][1], f"limites de {joint.name}"


# ---------------------------------------------------------------------------
# 2. El vocabulario de "lado"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nombre,lado",
    [
        ("izq", "izquierdo"),
        ("izquierda", "izquierdo"),
        ("izquierdo", "izquierdo"),
        ("left", "izquierdo"),
        ("der", "derecho"),
        ("derecha", "derecho"),
        ("derecho", "derecho"),
        ("right", "derecho"),
    ],
)
def test_los_dos_vocabularios_dicen_lo_mismo(nombre: str, lado: str) -> None:
    assert resolver_lado(nombre) == (lado,)


@pytest.mark.parametrize("nombre", ("ambos", "both", "dos"))
def test_ambos_son_los_dos_lados(nombre: str) -> None:
    assert resolver_lado(nombre) == ("derecho", "izquierdo")


def test_un_lado_desconocido_falla() -> None:
    with pytest.raises(BrazoError):
        resolver_lado("medio")


def test_una_pose_desconocida_falla() -> None:
    with pytest.raises(BrazoError):
        resolver_brazo("ambos", "bailar")


def test_brazoerror_es_un_valueerror() -> None:
    """Por compatibilidad con el codigo viejo, que lanzaba `ValueError`."""
    assert issubclass(BrazoError, ValueError)


def test_todos_los_lados_estan_cubiertos() -> None:
    """No hay articulaciones huerfanas: "ambos" cubre las cuatro."""
    assert set(resolver_brazo("ambos", "medio")) == set(Joint)


# ---------------------------------------------------------------------------
# 3. Las tres entradas se cien entre si
# ---------------------------------------------------------------------------


def _bytes_de_consola(lado: str, pose: str) -> dict[int, int]:
    console = Console(AiroRobot(), dry_run=True, echo=False, keepalive=False)
    asyncio.run(console.execute(f"brazo {lado} {pose}"))
    return bytes_de(
        {j: console.robot.command.servos[j] for j in Joint if j in console.robot.command.servos}
    )


def _bytes_de_sesion(lado: str, pose: str) -> dict[int, int]:
    sesion = RobotSession()
    asyncio.run(sesion.brazo(lado, pose))
    return bytes_de(
        {j: sesion.robot.command.servos[j] for j in Joint if j in sesion.robot.command.servos}
    )


def _bytes_de_scratch(side: str, pose: str) -> dict[int, int]:
    servicio = AiroService(address=None, connect_robot=False)
    asyncio.run(servicio._apply({"type": "arm", "side": side, "pose": pose}))
    return bytes_de(
        {
            j: servicio.robot.command.servos[j]
            for j in Joint
            if j in servicio.robot.command.servos
        }
    )


@pytest.mark.parametrize("pose", sorted(BYTES_ESPERADOS))
def test_las_tres_entradas_mueven_lo_mismo(pose: str) -> None:
    """Consola, API y Scratch tienen que mover los brazos igual.

    Este es el test que fija el bug de fondo: antes cada entrada tenia su
    propia copia de la logica de "lado" y se contradecian entre si.
    """
    for lado_es, lado_en in (("der", "derecho"), ("izq", "izquierdo")):
        esperado = {
            byte: BYTES_ESPERADOS[pose][byte]
            for byte in BYTES_DE_CADA_LADO[lado_en]
        }
        assert _bytes_de_consola(lado_es, pose) == esperado
        assert _bytes_de_sesion(lado_es, pose) == esperado
        assert _bytes_de_scratch(lado_es, pose) == esperado


def test_la_web_mueve_los_cuatro_brazos_con_ambos() -> None:
    """El bloque "ambos" de la web tiene que mover los cuatro."""
    sesion = RobotSession()
    asyncio.run(sesion.brazo("ambos", "arriba"))
    assert set(sesion.robot.command.servos) == set(Joint)
    assert bytes_de(sesion.robot.command.servos) == BYTES_ESPERADOS["arriba"]


def test_scratch_left_mueve_el_lado_izquierdo() -> None:
    """El bloque de Scratch usa "left": tiene que ser el izquierdo."""
    servicio = AiroService(address=None, connect_robot=False)
    asyncio.run(servicio._apply({"type": "arm", "side": "left", "pose": "arriba"}))
    esperado = {
        byte: BYTES_ESPERADOS["arriba"][byte]
        for byte in BYTES_DE_CADA_LADO["izquierdo"]
    }
    assert bytes_de(servicio.robot.command.servos) == esperado


def test_scratch_ambos_mueve_los_cuatro() -> None:
    servicio = AiroService(address=None, connect_robot=False)
    asyncio.run(servicio._apply({"type": "arm", "side": "ambos", "pose": "arriba"}))
    assert bytes_de(servicio.robot.command.servos) == BYTES_ESPERADOS["arriba"]


def test_un_lado_malo_en_scratch_da_error() -> None:
    servicio = AiroService(address=None, connect_robot=False)
    respuesta = asyncio.run(servicio._apply({"type": "arm", "side": "medio", "pose": "arriba"}))
    assert respuesta["ok"] is False
    assert "Lado desconocido" in respuesta["error"]


def test_una_pose_mala_en_scratch_da_error() -> None:
    servicio = AiroService(address=None, connect_robot=False)
    respuesta = asyncio.run(servicio._apply({"type": "arm", "side": "left", "pose": "bailar"}))
    assert respuesta["ok"] is False
    assert "Posición desconocida" in respuesta["error"]


def test_los_lados_conocidos_no_se_pisan() -> None:
    """Ninguna entrada escribe una articulacion que no toca."""
    assert set(LADOS) >= {"izq", "izquierda", "left", "der", "derecha", "right", "ambos"}


# ---------------------------------------------------------------------------
# 4. La calibracion se carga igual en todas las entradas
# ---------------------------------------------------------------------------


def test_la_sesion_carga_la_calibracion() -> None:
    """La API tiene que cargar `calibration.json` como la consola.

    Antes solo lo hacian la consola y el puente de Scratch, asi que el mismo
    bloque de la web movia el hombro izquierdo a un byte distinto que el
    mismo comando en la consola.
    """
    sesion = RobotSession()
    assert sesion._cargar_calibracion()

    datos = json.loads(CALIBRATION_DEFAULT.read_text())
    for nombre, byte in (datos.get("neutral") or {}).items():
        assert sesion.robot.command.neutral[JOINT_NAMES[nombre]] == byte
    for nombre, offset in (datos.get("offsets") or {}).items():
        assert sesion.robot.command.offsets[JOINT_NAMES[nombre]] == offset


def test_la_web_y_la_consola_calibran_igual() -> None:
    """La consola y la API tienen que dejar los brazos en el mismo sitio."""
    sesion = RobotSession()
    sesion._cargar_calibracion()

    consola = Console(AiroRobot(), dry_run=True, echo=False, keepalive=False)
    consola.load_calibration()

    for joint in Joint:
        assert sesion.robot.command.neutral.get(joint) == (
            consola.robot.command.neutral.get(joint)
        ), f"el cero de {joint.name} no es el mismo en la web y en la consola"
        assert sesion.robot.command.offsets.get(joint) == (
            consola.robot.command.offsets.get(joint)
        ), f"el offset de {joint.name} no es el mismo en la web y en la consola"


def test_la_calibracion_cambia_el_byte_del_hombro_izquierdo() -> None:
    """Esto es lo que hacia que la web y la consola se notasen distintas.

    El `left_shoulder` (byte 9) tiene su cero en el byte 16 (no en el 20), asi
    que ese hombro sale en el byte 23 en vez del 27: los dos lados dejan de
    sumar 40. Es el unico `neutral` que no es 20, y por eso el unico que
    hace que las dos formulas de `encode_servo` difieran.
    """
    sesion = RobotSession()
    sesion._cargar_calibracion()
    comandos = sesion.robot.command

    # el cero en el 16 es el del hombro izquierdo (byte 9)
    assert comandos.neutral[Joint.LEFT_SHOULDER] == 16
    assert comandos.neutral[Joint.RIGHT_SHOULDER] == 20

    # sin calibrar, ese hombro sale en el byte 27
    assert (
        encode_servo(Joint.LEFT_SHOULDER, -60.0) == 27
    ), "esto deberia ser el byte sin calibrar"
    # calibrado, sale en el 23
    comandos.set_joint(Joint.LEFT_SHOULDER, -60.0)
    assert comandos.servo_byte(Joint.LEFT_SHOULDER) == 23
    assert comandos.servo_byte(Joint.LEFT_SHOULDER) == encode_servo(
        Joint.LEFT_SHOULDER, -60.0, neutral=16
    )


def test_el_cero_de_la_calibracion_no_se_mueve_de_byte() -> None:
    """El byte 9 es el que tiene el cero en 16, antes y despues del renombrado."""
    sesion = RobotSession()
    sesion._cargar_calibracion()
    comandos = sesion.robot.command
    por_byte = {BYTE_DE[j]: comandos.neutral.get(j) for j in Joint}
    assert por_byte == {6: 20, 7: 20, 8: 20, 9: 16}
