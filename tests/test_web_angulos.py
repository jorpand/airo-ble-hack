"""
El mapeo de angulos de la web tiene que ser **el mismo** que el de la libreria.

La web dibuja el robot en `web/src/angulos.js`, que es un espejo de
`airo_ble/protocol.py`. Si los dos se separan, la interfaz enseña una pose que
el robot no esta haciendo: antes de este modulo la web usaba una formula fija
(`((byte - 20) / 20) * 60`) para las cuatro articulaciones, con errores de
hasta 230 grados en los codos.

Estos testscontrastan las dos implementaciones articulation por articulation y
angulo por angulo:

  - el byte que calcula el JS tiene que ser **exactamente** el que calcula
    `encode_servo()`,
  - al deshacer ese byte, el angulo del JS tiene que ser el de Python (con el
    error propio del byte, que son 8,5 grados),
  - el estado que manda la API tiene que llevar el "cero" (neutral) de cada
    articulacion, que es lo que necesita el JS para deshacer el escalado.

Si no hay `node` instalado, los tests se saltan (no se pueden ejecutar).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.console import CALIBRATION_DEFAULT  # noqa: E402
from airo_ble.protocol import (  # noqa: E402
    SERVO_CENTER,
    SERVO_SCALE,
    Joint,
    encode_servo,
)
from airo_ble.session import RobotSession  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MODULO_JS = RAIZ / "web" / "src" / "angulos.js"

#: Un byte son 8,5 grados: al deshacer el escalado no se puede saber mas.
MEDIO_BYTE = SERVO_SCALE / 2


def _node() -> str | None:
    """Ruta del `node`, o None si no hay (los tests se saltan entonces)."""
    node = shutil.which("node")
    if node:
        return node
    for candidato in ("/home/jordi/.local/bin/node", "/usr/local/bin/node"):
        if Path(candidato).exists():
            return candidato
    return None


pytestmark = pytest.mark.skipif(
    _node() is None or not MODULO_JS.exists(),
    reason="hace falta node y el modulo web/src/angulos.js",
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


def _angulos_de_js(tmp_path: Path, neutral: dict[str, int]) -> dict[str, dict[int, float]]:
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
