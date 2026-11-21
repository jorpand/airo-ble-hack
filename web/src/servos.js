// ---------------------------------------------------------------------------
// GENERADO: NO EDITAR A MANO.
//
// Este fichero sale de `airo_ble/protocol.py` (la fuente de la verdad) con:
//
//     python3 tools/gen_servos.py         # o `make web-gen`
//     python3 tools/gen_servos.py --check # solo comprueba que esta al dia
//
// Si lo tocas a mano, el test `tests/test_web_angulos.py` falla.
// ---------------------------------------------------------------------------

/** Grados de origen del escalado del servo (0xaa en el desensamblado). */
export const SERVO_ORIGIN = 170;

/** Un byte del servo son 8.5 grados. */
export const SERVO_SCALE = 8.5;

/** Byte que la app oficial considera "angulo 0". */
export const SERVO_CENTER = 20;

/** Rango util del byte de servo (el firmware nunca espera mas de 40). */
export const SERVO_BYTE_MAX = 40;

/**
 * Las cuatro articulaciones del robot.
 *
 * Los nombres son los FISICOS (los de la guia): `right_shoulder` es el hombro
 * derecho de verdad, que va en el byte 6 del paquete.
 *
 * | articulacion (fisica) | byte | signo | limites     |
 * |---|---|---|---|
 * | `right_shoulder` | 6 | +1 | -60 .. 77 |
 * | `right_arm` | 7 | -1 | -25 .. 170 |
 * | `left_arm` | 8 | +1 | -25 .. 170 |
 * | `left_shoulder` | 9 | -1 | -60 .. 77 |
 */
export const ARTICULACIONES = {
  right_shoulder: { byte: 6, signo: 1, min: -60, max: 77, lado: 'der' },
  right_arm: { byte: 7, signo: -1, min: -25, max: 170, lado: 'der' },
  left_arm: { byte: 8, signo: 1, min: -25, max: 170, lado: 'izq' },
  left_shoulder: { byte: 9, signo: -1, min: -60, max: 77, lado: 'izq' },
};

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
export function roundHalfEven(value) {
  const floor = Math.floor(value);
  const frac = value - floor;
  if (frac > 0.5) return floor + 1;
  if (frac < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/**
 * Recorta un angulo a los limites mecanicos de la articulacion.
 */
export function limitarAngulo(nombre, angulo) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return 0;
  const recortado = Math.min(Math.max(angulo, a.min), a.max);
  // -0 y 0 son el mismo angulo, pero no son el mismo numero: sin esto el
  // "angulo 0" sale como -0 y ensucia las comparaciones.
  return recortado === 0 ? 0 : recortado;
}

/**
 * Convierte el byte del servo en el angulo de la articulacion.
 *
 * Es la inversa de `anguloAByte()`. Como el byte solo guarda 8.5 grados, el
 * angulo que sale tiene un error de hasta +-4.25 grados: es lo mejor que se puede
 * sacar del byte.
 */
export function byteAAngulo(nombre, byte, neutral = SERVO_CENTER) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(byte)) return 0;
  const angulo = a.signo * (byte - neutral) * SERVO_SCALE;
  return limitarAngulo(nombre, angulo);
}

/**
 * Convierte un angulo de la articulacion en el byte del servo.
 *
 * Es el espejo de `encode_servo()` de `airo_ble/protocol.py` (con `neutral`):
 *
 *     byte = |neutral + signo * angulo / 8.5|
 */
export function anguloAByte(nombre, angulo, neutral = SERVO_CENTER) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return SERVO_CENTER;
  const bruto = neutral + (a.signo * limitarAngulo(nombre, angulo)) / SERVO_SCALE;
  const byte = roundHalfEven(Math.abs(bruto));
  return Math.min(Math.max(byte, 0), SERVO_BYTE_MAX);
}
