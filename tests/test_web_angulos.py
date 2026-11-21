"""
El mapeo de angulos de la web tiene que ser **el mismo** que el de la libreria.

La web usa `web/src/servos.js`, que esta **generado** desde
`airo_ble/protocol.py` por `tools/gen_servos.py`. Antes ese fichero estaba
escrito a mano y las dos copias se separaron: la web usaba una formula fija
(`((byte - 20) / 20) * 60`) para las cuatro articulaciones, con errores de
hasta 230 grados en los codos.

Estos tests miran las dos caras del problema:

  - **que el fichero generado esta al dia**: si alguien cambia `protocol.py`
    y no regenera, este test falla (no hace falta node para verlo),
  - **que el JS y la libreria dicen lo mismo**: byte a byte, para los cuatro
    brazos y todo su rango mecanico,
  - **que el estado que manda la API lleva el "cero" (neutral) de cada
    articulacion**, que es lo que necesita el JS para deshacer el escalado.

Los dos ultimos necesitan `node`; si no esta instalado, se saltan.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from airo_ble.console import CALIBRATION_DEFAULT
from airo_ble.protocol import (
    SERVO_CENTER,
    SERVO_SCALE,
    Joint,
    encode_servo,
)
from airo_ble.session import RobotSession

RAIZ = Path(__file__).resolve().parent.parent
MODULO_JS = RAIZ / "web" / "src" / "servos.js"
GENERADOR = RAIZ / "tools" / "gen_servos.py"


def _ruta_node() -> str | None:
    """Ruta del `node`, o None si no hay (los tests se saltan entonces)."""
    return shutil.which("node")


def _node() -> str:
    """La ruta del `node`. Los tests que la usan ya se han saltado si no hay."""
    node = _ruta_node()
    assert node is not None, "hace falta node"
    return node


#: Un byte son 8,5 grados: al deshacer el escalado no se puede saber mas.
MEDIO_BYTE = SERVO_SCALE / 2


def test_el_fichero_generado_esta_al_dia() -> None:
    """`web/src/servos.js` tiene que estar generado desde `protocol.py`.

    Este es el test que evita que las dos implementaciones se separen otra
    vez: si se toca `protocol.py` y no se regenera el JS, aqui falla.
    """
    assert MODULO_JS.exists(), (
        f"falta {MODULO_JS}: se genera con `python3 tools/gen_servos.py`"
    )
    resultado = subprocess.run(
        [sys.executable, str(GENERADOR), "--check"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultado.returncode == 0, (
        "web/src/servos.js esta desactualizado:\n"
        f"{resultado.stdout}{resultado.stderr}\n"
        "  regenera con: python3 tools/gen_servos.py"
    )


def _neutrals() -> dict[str, int]:
    """Los ceros de la calibracion que trae el paquete."""
    datos = json.loads(CALIBRATION_DEFAULT.read_text())
    neutral = dict(datos.get("neutral") or {})
    for joint in Joint:
        neutral.setdefault(joint.name.lower(), SERVO_CENTER)
    return neutral


def _bytes_de_js(tmp_path: Path, neutral: dict[str, int]) -> dict[str, dict[int, int]]:
    """Le pide a node el byte que el JS calcula para cada angulo.

    Devuelve `{articulacion: {angulo: byte}}`.
    """
    script = tmp_path / "mapeo.mjs"
    script.write_text(
        f"""
import {{ anguloAByte, ARTICULACIONES }} from 'file://{MODULO_JS}';

const neutral = {json.dumps(neutral)};
const salida = {{}};
for (const [nombre, a] of Object.entries(ARTICULACIONES)) {{
  const bytes = {{}};
  for (let angulo = a.min; angulo <= a.max; angulo += 1) {{
    bytes[angulo] = anguloAByte(nombre, angulo, neutral[nombre]);
  }}
  salida[nombre] = bytes;
}}
console.log(JSON.stringify(salida));
"""
    )
    salida = subprocess.run(
        [_node(), str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(salida.stdout)


def _angulos_de_js(tmp_path: Path, neutral: dict[str, int]) -> dict[str, dict[str, float]]:
    """Le pide a node el angulo que el JS deduce de cada byte."""
    script = tmp_path / "inverso.mjs"
    script.write_text(
        f"""
import {{ byteAAngulo, ARTICULACIONES }} from 'file://{MODULO_JS}';

const neutral = {json.dumps(neutral)};
const salida = {{}};
for (const [nombre, a] of Object.entries(ARTICULACIONES)) {{
  const angulos = {{}};
  for (let byte = 0; byte <= 40; byte += 1) {{
    angulos[byte] = byteAAngulo(nombre, byte, neutral[nombre]);
  }}
  salida[nombre] = angulos;
}}
console.log(JSON.stringify(salida));
"""
    )
    salida = subprocess.run(
        [_node(), str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(salida.stdout)


@pytest.mark.skipif(_ruta_node() is None, reason="hace falta node")
def test_el_js_calcula_el_mismo_byte_que_la_libreria(tmp_path: Path) -> None:
    """Byte a byte, para los cuatro brazos y todo su rango mecanico."""
    neutral = _neutrals()
    bytes_js = _bytes_de_js(tmp_path, neutral)

    for joint in Joint:
        nombre = joint.name.lower()
        assert nombre in bytes_js, f"el JS no conoce la articulacion {nombre}"
        for angulo, byte in bytes_js[nombre].items():
            esperado = encode_servo(joint, float(angulo), neutral=neutral[nombre])
            assert byte == esperado, (
                f"{nombre}: el JS saca el byte {byte} para el angulo {angulo} "
                f"y la libreria {esperado}"
            )


@pytest.mark.skipif(_ruta_node() is None, reason="hace falta node")
def test_el_js_deduce_el_mismo_angulo_que_la_libreria(tmp_path: Path) -> None:
    """Deshaciendo el byte, los dos dan el mismo angulo (con +-4,25 grados)."""
    neutral = _neutrals()
    angulos_js = _angulos_de_js(tmp_path, neutral)
    bytes_js = _bytes_de_js(tmp_path, neutral)

    for joint in Joint:
        nombre = joint.name.lower()
        for angulo, byte_js in bytes_js[nombre].items():
            byte_python = encode_servo(joint, float(angulo), neutral=neutral[nombre])
            assert byte_js == byte_python
            angulo_js = angulos_js[nombre][str(byte_js)]
            assert abs(angulo_js - float(angulo)) <= MEDIO_BYTE, (
                f"{nombre}: del byte {byte_js} el JS deduce {angulo_js} "
                f"y deberia ser {angulo} (+-{MEDIO_BYTE})"
            )


@pytest.mark.skipif(_ruta_node() is None, reason="hace falta node")
def test_el_js_redondea_como_la_libreria(tmp_path: Path) -> None:
    """El JS usa el redondeo a la par (banker's) de .NET, como Python.

    En los empates, Python va al par mas cercano y `Math.round` de JavaScript
    siempre hacia arriba: con un byte de diferencia la web dibujaria una pose
    que el robot no tiene.
    """
    script = tmp_path / "redondeo.mjs"
    script.write_text(
        f"""
import {{ roundHalfEven }} from 'file://{MODULO_JS}';
console.log(JSON.stringify([0.5, 1.5, 2.5, 3.5, 20.5, 21.5].map(roundHalfEven)));
"""
    )
    salida = subprocess.run(
        [_node(), str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert json.loads(salida.stdout) == [0, 2, 2, 4, 20, 22]


def test_el_estado_manda_el_cero_de_cada_articulacion() -> None:
    """La web necesita el `neutral` para deshacer el escalado del servo.

    Sin el, el hombro derecho (calibrado en 16, no en 20) se dibujaria con
    unos 34 grados de error.
    """
    sesion = RobotSession()
    estado = sesion.estado()

    for joint in Joint:
        nombre = joint.name.lower()
        assert nombre in estado["brazos"]
        assert "angulo" in estado["brazos"][nombre]
        assert "byte" in estado["brazos"][nombre]
        assert estado["brazos"][nombre]["neutral"] == sesion.robot.command.neutral.get(
            joint, SERVO_CENTER
        )


def test_el_estado_avisa_del_hombro_izquierdo_calibrado_en_16() -> None:
    """El hombro izquierdo (byte 9) viene con el cero en 16.

    Es el unico `neutral` que no es 20, y por eso el unico que hace que las
    dos formulas de `encode_servo` difieran.
    """
    sesion = RobotSession()
    neutral = sesion.estado()["brazos"]["left_shoulder"]["neutral"]
    assert neutral == 16, (
        "el hombro izquierdo deberia venir con el cero en 16; si ha cambiado, "
        "la calibracion del paquete ha cambiado y hay que mirarlo"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
