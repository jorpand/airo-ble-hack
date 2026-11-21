#!/usr/bin/env python3
"""Genera `web/src/servos.js` desde `airo_ble/protocol.py`.

La web necesita los mismos numeros que la libreria (el byte de cada servo, su
signo, sus limites y el escalado). Antes estaban **escritos a mano** en
`web/src/angulos.js`, y esa duplicacion yaromo una vez: la web usaba una
formula unica que se equivocaba en hasta 230 grados en los codos.

Ahora `aio_ble/protocol.py` es la **unica fuente de la verdad** y este script
la traduce a JavaScript:

    python3 tools/gen_servos.py            # regenera el fichero
    python3 tools/gen_servos.py --check    # solo comprueba que esta al dia

El test `tests/test_web_angulos.py` llama a `--check`, asi que si alguien
toca `protocol.py` y no regenera, la CI se pone roja.

Lo que NO va aqui: el dibujo del robot (los grados de pantalla, que solo le
importan a la interfaz). Eso sigue en `web/src/angulos.js`, a mano.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: Raiz del repositorio (este script vive en tools/).
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from airo_ble.protocol import (  # noqa: E402
    JOINT_BYTE,
    SERVO_BYTE_MAX,
    SERVO_CENTER,
    SERVO_LIMITS,
    SERVO_ORIGIN,
    SERVO_SCALE,
    SERVO_SIGN,
    Joint,
)

#: Donde se escribe el fichero generado.
DESTINO = RAIZ / "web" / "src" / "servos.js"

#: De que lado del robot esta cada articulacion. Se deduce del nombre
#: (RIGHT_/LEFT_), que ya es la nomenclatura fisica de la guia.
LADO_POR_PREFIJO = {"RIGHT": "der", "LEFT": "izq"}


def _lado(joint: Joint) -> str:
    prefijo = joint.name.split("_", 1)[0]
    try:
        return LADO_POR_PREFIJO[prefijo]
    except KeyError:  # pragma: no cover - solo si se anade una articulacion
        raise SystemExit(
            f"no se sabe que lado es {joint.name}: anadelo a LADO_POR_PREFIJO"
        ) from None


def _nombre_js(joint: Joint) -> str:
    """`Joint.RIGHT_SHOULDER` -> `right_shoulder`."""
    return joint.name.lower()


def _num(valor: float | int) -> str:
    """Un numero para JavaScript: `170.0` se escribe `170`."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def generar() -> str:
    """Devuelve el contenido del fichero generado."""
    filas = []
    for joint in Joint:
        minimo, maximo = SERVO_LIMITS[joint]
        filas.append(
            "  {nombre}: {{ byte: {byte}, signo: {signo}, min: {minimo}, "
            "max: {maximo}, lado: '{lado}' }},".format(
                nombre=_nombre_js(joint),
                byte=JOINT_BYTE[joint],
                signo=SERVO_SIGN[joint],
                minimo=minimo,
                maximo=maximo,
                lado=_lado(joint),
            )
        )

    tabla = "\n".join(filas)

    return f"""// ---------------------------------------------------------------------------
// GENERADO: NO EDITAR A MANO.
//
// Este fichero sale de `airo_ble/protocol.py` (la fuente de la verdad) con:
//
//     python3 tools/gen_servos.py         # o `mise run web-gen`
//     python3 tools/gen_servos.py --check # solo comprueba que esta al dia
//
// Si lo tocas a mano, el test `tests/test_web_angulos.py` falla.
// ---------------------------------------------------------------------------

/** Grados de origen del escalado del servo (0xaa en el desensamblado). */
export const SERVO_ORIGIN = {_num(SERVO_ORIGIN)};

/** Un byte del servo son {SERVO_SCALE} grados. */
export const SERVO_SCALE = {SERVO_SCALE};

/** Byte que la app oficial considera "angulo 0". */
export const SERVO_CENTER = {SERVO_CENTER};

/** Rango util del byte de servo (el firmware nunca espera mas de {SERVO_BYTE_MAX}). */
export const SERVO_BYTE_MAX = {SERVO_BYTE_MAX};

/**
 * Las cuatro articulaciones del robot.
 *
 * Los nombres son los FISICOS (los de la guia): `right_shoulder` es el hombro
 * derecho de verdad, que va en el byte 6 del paquete.
 *
 * | articulacion (fisica) | byte | signo | limites     |
 * |---|---|---|---|
{_tabla_markdown()}
 */
export const ARTICULACIONES = {{
{tabla}
}};

/** Los nombres de las articulaciones, en el orden del enum de Python. */
export const NOMBRES = Object.keys(ARTICULACIONES);

/**
 * Redondeo .NET `Math.Round(double)` = MidpointRounding.ToEven.
 *
 * Es el mismo redondeo que usa `airo_ble.protocol.round_half_even()`: en los
 * empates va al par mas cercano, no siempre hacia arriba. Importa porque el
 * byte del servo es un numero entero y un redondeo distinto ensenaria a la
 * web una pose que el robot no tiene.
 */
export function roundHalfEven(value) {{
  const floor = Math.floor(value);
  const frac = value - floor;
  if (frac > 0.5) return floor + 1;
  if (frac < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}}

/**
 * Recorta un angulo a los limites mecanicos de la articulacion.
 */
export function limitarAngulo(nombre, angulo) {{
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return 0;
  const recortado = Math.min(Math.max(angulo, a.min), a.max);
  // -0 y 0 son el mismo angulo, pero no son el mismo numero: sin esto el
  // "angulo 0" sale como -0 y ensucia las comparaciones.
  return recortado === 0 ? 0 : recortado;
}}

/**
 * Convierte el byte del servo en el angulo de la articulacion.
 *
 * Es la inversa de `anguloAByte()`. Como el byte solo guarda {SERVO_SCALE} grados, el
 * angulo que sale tiene un error de hasta +-{SERVO_SCALE / 2} grados: es lo mejor que se puede
 * sacar del byte.
 */
export function byteAAngulo(nombre, byte, neutral = SERVO_CENTER) {{
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(byte)) return 0;
  const angulo = a.signo * (byte - neutral) * SERVO_SCALE;
  return limitarAngulo(nombre, angulo);
}}

/**
 * Convierte un angulo de la articulacion en el byte del servo.
 *
 * Es el espejo de `encode_servo()` de `airo_ble/protocol.py` (con `neutral`):
 *
 *     byte = |neutral + signo * angulo / {SERVO_SCALE}|
 */
export function anguloAByte(nombre, angulo, neutral = SERVO_CENTER) {{
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return SERVO_CENTER;
  const bruto = neutral + (a.signo * limitarAngulo(nombre, angulo)) / SERVO_SCALE;
  const byte = roundHalfEven(Math.abs(bruto));
  return Math.min(Math.max(byte, 0), SERVO_BYTE_MAX);
}}
"""


def _tabla_markdown() -> str:
    """La tabla de la articulaciones en markdown, para el comentario."""
    filas = []
    for joint in Joint:
        minimo, maximo = SERVO_LIMITS[joint]
        filas.append(
            f" * | `{_nombre_js(joint)}` | {JOINT_BYTE[joint]} | "
            f"{SERVO_SIGN[joint]:+d} | {minimo} .. {maximo} |"
        )
    return "\n".join(filas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="no escribir: solo comprobar que el fichero esta al dia",
    )
    args = parser.parse_args(argv)

    contenido = generar()

    if args.check:
        if not DESTINO.exists():
            print(f"FALTA: {DESTINO} no existe (generalo con --check sin este flag)")
            return 1
        actual = DESTINO.read_text(encoding="utf-8")
        if actual != contenido:
            print(
                f"DESACTUALIZADO: {DESTINO} no coincide con protocol.py\n"
                f"  regenera con: python3 tools/gen_servos.py"
            )
            return 1
        print(f"OK: {DESTINO.relative_to(RAIZ)} esta al dia")
        return 0

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(contenido, encoding="utf-8")
    print(f"Escrito {DESTINO.relative_to(RAIZ)} ({len(contenido)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
