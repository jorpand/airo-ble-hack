// Los angulos de los brazos del robot: como se convierte el byte del servo en
// angulos y al reves.
//
// Esto es el espejo de `airo_ble/protocol.py`. El byte que va al servo NO es el
// angulo: es la posicion del servo (un byte = 8,5 grados). Antes la web usaba
// una formula fija para las cuatro articulaciones:
//
//     angulo = ((byte - 20) / 20) * 60
//
// que solo valia para un caso: ademas de no respetar el signo de cada servo,
// daba un error de hasta 230 grados en los codos (que van de -25 a +170) y
// ni siquiera dibujaba el codo.
//
// Lo que hay aqui:
//
//   byte = |neutral + signo * angulo / 8.5|
//   angulo = signo * (byte - neutral) * 8.5
//
// Ojo con las tres cosas que hacen que NO valga una formula unica:
//
//   - el **signo**: los dos lados giran en sentidos opuestos (byte 6 y 8 en un
//     sentido, byte 7 y 9 en el contrario),
//   - el **neutral**: el byte que es "angulo 0" no siempre es el 20. En la
//     calibracion que trae el paquete, el hombro izquierdo tiene el cero en 16,
//   - los **limites**: los hombros van de -60 a 77 y los codos de -25 a 170,
//     cada uno con su rango.
//
// La calibracion (el neutral de cada articulacion) la manda el servidor en el
// estado, en `brazos.<articulacion>.neutral`, asi que aqui no hay ningun
// numero de calibracion escrito: solo el 20 por defecto de la app oficial.

//: Grados de origen del escalado del servo (0xaa en el desensamblado).
export const SERVO_ORIGIN = 170;

//: Un byte del servo son 8,5 grados.
export const SERVO_SCALE = 8.5;

//: Byte que la app oficial considera "angulo 0".
export const SERVO_CENTER = 20;

/**
 * Las cuatro articulaciones del robot.
 *
 * Los nombres son los FISICOS (los de la guia): `right_shoulder` es el hombro
 * derecho de verdad, que va en el byte 6 del paquete. Los signos y los limites
 * son los de `airo_ble/protocol.py`:
 *
 * | articulacion (fisica) | byte | signo | limites     |
 * |---|---|---|---|
 * | `right_shoulder`  |   6 |    +1 | -60 .. 77   |
 * | `right_arm`       |   7 |    -1 | -25 .. 170  |
 * | `left_arm`        |   8 |    +1 | -25 .. 170  |
 * | `left_shoulder`   |   9 |    -1 | -60 .. 77   |
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
 * Es la inversa de `anguloAByte()`. Como el byte solo guarda 8,5 grados, el
 * angulo que sale tiene un error de hasta +-4,25 grados: es lo mejor que se
 * puede sacar del byte.
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
 * Es el espejo de `encode_servo()` de `airo_ble/protocol.py`.
 */
export function anguloAByte(nombre, angulo, neutral = SERVO_CENTER) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return SERVO_CENTER;
  const bruto = neutral + (a.signo * limitarAngulo(nombre, angulo)) / SERVO_SCALE;
  return Math.min(Math.max(Math.round(Math.abs(bruto)), 0), 40);
}

/**
 * El angulo que hay que dibujar de una articulacion, segun el estado.
 *
 * El servidor manda el angulo pedido (`angulo`), que es exacto, y el byte que
 * va al servo (`byte`), que es la posicion real. Se prefiere el angulo y, si
 * no estuviera, se deduce del byte usando el neutral de la calibracion.
 */
export function anguloDeEstado(estado, nombre) {
  const dato = estado?.brazos?.[nombre];
  if (!dato) return 0;
  if (Number.isFinite(dato.angulo)) return limitarAngulo(nombre, dato.angulo);
  if (Number.isFinite(dato.byte)) {
    const neutral = Number.isFinite(dato.neutral) ? dato.neutral : SERVO_CENTER;
    return byteAAngulo(nombre, dato.byte, neutral);
  }
  return 0;
}

// --- Dibujo: del angulo a los grados de pantalla ---------------------------
//
// El robot se dibuja de frente, con los brazos colgando. El hombro (el brazo
// de arriba) gira como un pendolo y el codo (el antebrazo) gira respecto al
// brazo.
//
// El tope mecanico de "abajo" del hombro (+77 grados) es el brazo colgando y el
// de "arriba" (-60 grados) es el brazo en vertical, asi que los 137 grados
// mecanicos se reparten en 180 de pantalla. Del codo, el angulo -25 es el
// antebrazo recto (alineado con el brazo) y el +170 es el codo plegado.
//
// El lado izquierdo se dibuja al reves que el derecho: es el mismo robot
// visto al reves.

/** Grados de pantalla que recorre el hombro (de abajo a arriba). */
export const GIRO_HOMBRO = 180;

/** Grados de pantalla que recorre el codo (de recto a plegado). */
export const GIRO_CODO = 180;

// El robot se dibuja **de frente** (se le ven los ojos), asi que su brazo
// derecho sale a la IZQUIERDA de la pantalla. Y en la pantalla un giro
// positivo lleva la punta del brazo hacia la izquierda.
//
// OJO: esto no es lo mismo que el lado del robot. El `lado` de cada
// articulacion es el fisico; la pantalla es su espejo, porque estamos
// viendo al robot de cara.
const EN_PANTALLA = { der: 'izq', izq: 'der' };

/**
 * Rotacion del brazo (hombro) en la pantalla, en grados de CSS.
 *
 * El angulo maximo (+77, brazo abajo) da 0 (cuelga) y el minimo (-60, brazo
 * arriba) da 180 grados con el brazo en vertical. En los angulos
 * intermedios el brazo sale hacia **fuera** del cuerpo, que es como se ve
 * al robot de verdad en la pose `medio`.
 */
export function rotacionHombro(nombre, angulo) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return 0;
  const escala = GIRO_HOMBRO / (a.max - a.min);
  // 0 con el brazo colgando (tope maximo) y +180 con el brazo arriba.
  const giro = (a.max - limitarAngulo(nombre, angulo)) * escala;
  return EN_PANTALLA[a.lado] === 'izq' ? giro : -giro;
}

/**
 * Rotacion del antebrazo (codo) respecto al brazo, en grados de CSS.
 *
 * El angulo minimo (-25, recto) da 0 y el maximo (+170, plegado) da 180
 * grados de vuelta. El antebrazo se pliega hacia dentro (hacia el cuerpo).
 */
export function rotacionCodo(nombre, angulo) {
  const a = ARTICULACIONES[nombre];
  if (!a || !Number.isFinite(angulo)) return 0;
  const escala = GIRO_CODO / (a.max - a.min);
  // 0 con el antebrazo recto (tope minimo) y +180 con el codo plegado.
  const giro = (limitarAngulo(nombre, angulo) - a.min) * escala;
  return EN_PANTALLA[a.lado] === 'izq' ? -giro : giro;
}
