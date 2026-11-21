// Los angulos de los brazos del robot: como se convierte el byte del servo en
// angulos y al reves, y como se dibuja cada brazo en pantalla.
//
// La parte que habla del **protocolo** (el byte de cada servo, su signo, sus
// limites y el escalado de 8,5 grados) **ya no esta escrita aqui**: sale
// generada de `airo_ble/protocol.py` a `web/src/servos.js` con
// `tools/gen_servos.py`.
//
// Antes estaba duplicada a mano y ya se separo una vez: la web usaba una
// formula unica que se equivocaba en hasta 230 grados en los codos. Ahora la
// libreria es la unica fuente de la verdad y el test
// `tests/test_web_angulos.py` comprueba byte a byte que las dos siguen
// diciendo lo mismo.
//
// Aqui solo queda lo que es **dibujo**: como se coloca cada brazo en la
// pantalla. Eso no lo conoce Python.

import {
  ARTICULACIONES,
  NOMBRES,
  SERVO_BYTE_MAX,
  SERVO_CENTER,
  SERVO_ORIGIN,
  SERVO_SCALE,
  anguloAByte,
  byteAAngulo,
  limitarAngulo,
} from './servos.js';

// Se re-exportan para que el resto de la web siga importando de aqui.
export {
  ARTICULACIONES,
  NOMBRES,
  SERVO_BYTE_MAX,
  SERVO_CENTER,
  SERVO_ORIGIN,
  SERVO_SCALE,
  anguloAByte,
  byteAAngulo,
  limitarAngulo,
};

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
