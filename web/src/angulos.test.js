import { describe, expect, it } from 'vitest';
import {
  ARTICULACIONES,
  GIRO_CODO,
  GIRO_HOMBRO,
  NOMBRES,
  SERVO_CENTER,
  SERVO_SCALE,
  anguloAByte,
  anguloDeEstado,
  byteAAngulo,
  limitarAngulo,
  rotacionCodo,
  rotacionHombro,
} from './angulos.js';

// Un byte son 8,5 grados: al deshacer el escalado el angulo tiene un error de
// hasta medio byte.
const TOLERANCIA = SERVO_SCALE / 2;

// La calibracion que trae el paquete: el hombro izquierdo (byte 9) tiene el
// cero en 16, no en 20.
const NEUTRAL = {
  right_shoulder: 20,
  right_arm: 20,
  left_arm: 20,
  left_shoulder: 16,
};

// Los bytes de la tabla de poses de la guia (§ 5.0.1), con los nombres
// FISICOS de las articulaciones.
const POSES = [
  { pose: 'arriba', hombro: -60, codo: 170 },
  { pose: 'golpe', hombro: -60, codo: -25 },
  { pose: 'guardia', hombro: -60, codo: 90 },
  { pose: 'abajo', hombro: 77, codo: -25 },
  { pose: 'medio', hombro: 0, codo: 0 },
];

// Byte que sale en cada articulacion para cada pose (guia § 5.0.1).
const BYTES_DE_LAS_POSES = {
  arriba: { right_shoulder: 13, left_shoulder: 23, right_arm: 0, left_arm: 40 },
  golpe: { right_shoulder: 13, left_shoulder: 23, right_arm: 23, left_arm: 17 },
  guardia: { right_shoulder: 13, left_shoulder: 23, right_arm: 9, left_arm: 31 },
  abajo: { right_shoulder: 29, left_shoulder: 7, right_arm: 23, left_arm: 17 },
  medio: { right_shoulder: 20, left_shoulder: 16, right_arm: 20, left_arm: 20 },
};

describe('la tabla de articulaciones', () => {
  it('tiene las cuatro, con el byte del paquete', () => {
    expect(NOMBRES.sort()).toEqual(
      ['left_arm', 'left_shoulder', 'right_arm', 'right_shoulder'],
    );
    expect(ARTICULACIONES.right_shoulder.byte).toBe(6);
    expect(ARTICULACIONES.right_arm.byte).toBe(7);
    expect(ARTICULACIONES.left_arm.byte).toBe(8);
    expect(ARTICULACIONES.left_shoulder.byte).toBe(9);
  });

  it('mantiene los signos y los limites de protocol.py', () => {
    expect(ARTICULACIONES.right_shoulder.signo).toBe(1);
    expect(ARTICULACIONES.right_arm.signo).toBe(-1);
    expect(ARTICULACIONES.left_arm.signo).toBe(1);
    expect(ARTICULACIONES.left_shoulder.signo).toBe(-1);

    expect(ARTICULACIONES.right_shoulder.min).toBe(-60);
    expect(ARTICULACIONES.right_shoulder.max).toBe(77);
    expect(ARTICULACIONES.right_arm.min).toBe(-25);
    expect(ARTICULACIONES.right_arm.max).toBe(170);
    expect(ARTICULACIONES.left_arm.min).toBe(-25);
    expect(ARTICULACIONES.left_arm.max).toBe(170);
    expect(ARTICULACIONES.left_shoulder.min).toBe(-60);
    expect(ARTICULACIONES.left_shoulder.max).toBe(77);
  });

  it('el lado de cada articulacion es el del robot', () => {
    // Verificado con el robot delante: el byte 6 es el hombro DERECHO.
    expect(ARTICULACIONES.right_shoulder.lado).toBe('der');
    expect(ARTICULACIONES.right_arm.lado).toBe('der');
    expect(ARTICULACIONES.left_arm.lado).toBe('izq');
    expect(ARTICULACIONES.left_shoulder.lado).toBe('izq');
  });
});

describe('angulo -> byte', () => {
  it.each(POSES)('sale el byte de la guia en la pose $pose', ({ pose, hombro, codo }) => {
    const esperado = BYTES_DE_LAS_POSES[pose];
    expect(anguloAByte('right_shoulder', hombro, NEUTRAL.right_shoulder)).toBe(
      esperado.right_shoulder,
    );
    expect(anguloAByte('left_shoulder', hombro, NEUTRAL.left_shoulder)).toBe(
      esperado.left_shoulder,
    );
    expect(anguloAByte('right_arm', codo, NEUTRAL.right_arm)).toBe(esperado.right_arm);
    expect(anguloAByte('left_arm', codo, NEUTRAL.left_arm)).toBe(esperado.left_arm);
  });

  it('el angulo 0 es el byte 20 sin calibrar', () => {
    for (const nombre of NOMBRES) {
      expect(anguloAByte(nombre, 0)).toBe(SERVO_CENTER);
    }
  });

  it('con el neutral 16 el hombro izquierdo no sale en 20', () => {
    expect(anguloAByte('left_shoulder', 0, 16)).toBe(16);
    expect(anguloAByte('left_shoulder', 0, 20)).toBe(20);
  });

  it('recorta a los limites mecanicos', () => {
    expect(anguloAByte('right_shoulder', -500)).toBe(
      anguloAByte('right_shoulder', -60),
    );
    expect(anguloAByte('right_shoulder', 500)).toBe(
      anguloAByte('right_shoulder', 77),
    );
    expect(anguloAByte('right_arm', 500)).toBe(anguloAByte('right_arm', 170));
    expect(anguloAByte('left_arm', -500)).toBe(anguloAByte('left_arm', -25));
  });

  it('el byte siempre cabe en 0..40', () => {
    for (const nombre of NOMBRES) {
      for (let angulo = -200; angulo <= 200; angulo += 1) {
        const byte = anguloAByte(nombre, angulo);
        expect(byte).toBeGreaterThanOrEqual(0);
        expect(byte).toBeLessThanOrEqual(40);
      }
    }
  });
});

describe('byte -> angulo', () => {
  it.each(POSES)('deshace el byte de la guia en la pose $pose', ({ pose, hombro, codo }) => {
    const bytes = BYTES_DE_LAS_POSES[pose];
    expect(
      Math.abs(
        byteAAngulo('right_shoulder', bytes.right_shoulder, NEUTRAL.right_shoulder) - hombro,
      ),
    ).toBeLessThanOrEqual(TOLERANCIA);
    expect(
      Math.abs(
        byteAAngulo('left_shoulder', bytes.left_shoulder, NEUTRAL.left_shoulder) - hombro,
      ),
    ).toBeLessThanOrEqual(TOLERANCIA);
    expect(Math.abs(byteAAngulo('right_arm', bytes.right_arm, NEUTRAL.right_arm) - codo)).toBeLessThanOrEqual(
      TOLERANCIA,
    );
    expect(Math.abs(byteAAngulo('left_arm', bytes.left_arm, NEUTRAL.left_arm) - codo)).toBeLessThanOrEqual(
      TOLERANCIA,
    );
  });

  it('sin calibrar el byte 20 es el angulo 0 en las cuatro', () => {
    for (const nombre of NOMBRES) {
      expect(byteAAngulo(nombre, SERVO_CENTER)).toBe(0);
    }
  });

  it('el hombro izquierdo calibrado en 16 tiene el cero en el byte 16', () => {
    expect(byteAAngulo('left_shoulder', 16, 16)).toBe(0);
    // sin conocer el neutral, el mismo byte parece otro angulo
    expect(byteAAngulo('left_shoulder', 16, 20)).toBe(34);
  });

  it('la ida y la vuelta no se van mas de medio byte', () => {
    for (const nombre of NOMBRES) {
      const neutral = NEUTRAL[nombre];
      const min = ARTICULACIONES[nombre].min;
      const max = ARTICULACIONES[nombre].max;
      for (let angulo = min; angulo <= max; angulo += 1) {
        const byte = anguloAByte(nombre, angulo, neutral);
        const vuelta = byteAAngulo(nombre, byte, neutral);
        expect(Math.abs(vuelta - angulo)).toBeLessThanOrEqual(TOLERANCIA);
      }
    }
  });

  it('recorta al limite cuando el byte se sale', () => {
    expect(limitarAngulo('right_shoulder', -500)).toBe(-60);
    expect(limitarAngulo('right_shoulder', 500)).toBe(77);
    expect(limitarAngulo('right_arm', 500)).toBe(170);
  });
});

describe('el espejo de los dos lados', () => {
  it('los bytes de un lado y del otro suman los dos ceros', () => {
    // El lado izquierdo es el espejo del derecho: los bytes son simetricos
    // alrededor del cero de cada brazo, asi que los dos suman lo mismo
    // siempre.
    for (const par of [
      ['left_shoulder', 'right_shoulder'],
      ['left_arm', 'right_arm'],
    ]) {
      const [izq, der] = par;
      for (let angulo = -60; angulo <= 170; angulo += 1) {
        const suma =
          anguloAByte(izq, angulo, NEUTRAL[izq]) + anguloAByte(der, angulo, NEUTRAL[der]);
        expect(suma).toBe(NEUTRAL[izq] + NEUTRAL[der]);
      }
    }
  });

  it('los signos de los codos son opuestos a los de los hombros', () => {
    expect(ARTICULACIONES.right_shoulder.signo).toBe(
      -ARTICULACIONES.left_shoulder.signo,
    );
    expect(ARTICULACIONES.right_arm.signo).toBe(-ARTICULACIONES.left_arm.signo);
  });
});

describe('el angulo que se dibuja', () => {
  it('prefiere el angulo que manda el servidor', () => {
    const estado = {
      brazos: {
        left_shoulder: { angulo: -60, byte: 23, neutral: 16 },
        left_arm: { angulo: 170, byte: 40, neutral: 20 },
      },
    };
    expect(anguloDeEstado(estado, 'left_shoulder')).toBe(-60);
    expect(anguloDeEstado(estado, 'left_arm')).toBe(170);
  });

  it('si no hay angulo, lo deduce del byte con su neutral', () => {
    const estado = {
      brazos: {
        left_shoulder: { byte: 23, neutral: 16 },
        left_arm: { byte: 40, neutral: 20 },
      },
    };
    expect(
      Math.abs(anguloDeEstado(estado, 'left_shoulder') + 60),
    ).toBeLessThanOrEqual(TOLERANCIA);
    expect(Math.abs(anguloDeEstado(estado, 'left_arm') - 170)).toBeLessThanOrEqual(
      TOLERANCIA,
    );
  });

  it('sin estado no peta y dibuja el brazo quieto', () => {
    expect(anguloDeEstado(undefined, 'right_shoulder')).toBe(0);
    expect(anguloDeEstado({}, 'right_arm')).toBe(0);
    expect(anguloDeEstado({ brazos: {} }, 'right_arm')).toBe(0);
  });

  it('no se sale de los limites mecanicos', () => {
    const estado = { brazos: { right_arm: { angulo: 900 } } };
    expect(anguloDeEstado(estado, 'right_arm')).toBe(170);
  });
});

describe('el dibujo en la pantalla', () => {
  it('el hombro abajo cuelga y el hombro arriba esta en vertical', () => {
    // El robot se dibuja de frente: su brazo derecho sale a la izquierda de
    // la pantalla, y ahi un giro positivo lleva la punta hacia la izquierda.
    expect(rotacionHombro('right_shoulder', 77)).toBeCloseTo(0, 6);
    expect(rotacionHombro('right_shoulder', -60)).toBeCloseTo(GIRO_HOMBRO, 6);
    expect(rotacionHombro('left_shoulder', 77)).toBeCloseTo(0, 6);
    expect(rotacionHombro('left_shoulder', -60)).toBeCloseTo(-GIRO_HOMBRO, 6);
  });

  it('en la pose medio los brazos salen hacia fuera, no cruzados', () => {
    // Como en el robot de verdad: los dos brazos open hacia los lados.
    expect(rotacionHombro('right_shoulder', 0)).toBeCloseTo(101.17, 1);
    expect(rotacionHombro('left_shoulder', 0)).toBeCloseTo(-101.17, 1);
  });

  it('el lado izquierdo se dibuja al reves del derecho', () => {
    for (const angulo of [-60, -25, 0, 77, 170]) {
      expect(rotacionHombro('left_shoulder', angulo)).toBeCloseTo(
        -rotacionHombro('right_shoulder', angulo),
        6,
      );
      expect(rotacionCodo('left_arm', angulo)).toBeCloseTo(
        -rotacionCodo('right_arm', angulo),
        6,
      );
    }
  });

  it('el codo recto va alineado con el brazo y el plegado da la vuelta', () => {
    expect(rotacionCodo('right_arm', -25)).toBeCloseTo(0, 6);
    expect(rotacionCodo('right_arm', 170)).toBeCloseTo(-GIRO_CODO, 6);
    expect(rotacionCodo('left_arm', -25)).toBeCloseTo(0, 6);
    expect(rotacionCodo('left_arm', 170)).toBeCloseTo(GIRO_CODO, 6);
  });

  it('las rotaciones del codo no dependen del hombro', () => {
    expect(rotacionCodo('right_arm', 0)).toBeCloseTo(-23.08, 1);
  });
});
