import { describe, expect, it } from 'vitest';
import {
  ARTICULACIONES,
  RANGOS,
  TIEMPOS,
  TIEMPOS_BRAZO,
  anguloPorDefecto,
  bloqueLlamada,
  bloqueNuevo,
  conArticulacion,
  conModoObjetivo,
  estimarDuracion,
  formatoDuracion,
  funcionesPara,
  historialAplica,
  historialDeshace,
  historialNuevo,
  indiceDeTiempo,
  insertarEnArbol,
  localizarBloque,
  modoObjetivo,
  moverBloque,
  nombreDeFuncion,
  programaDeEjemplo,
  quitarEnArbol,
  rangoDe,
  resumenDeBloque,
  tiempoBonito,
  tiemposDe,
} from './bloques.js';

describe('los tiempos', () => {
  it('el brazo tiene la opcion "de golpe" y los demas no', () => {
    expect(TIEMPOS_BRAZO[0].valor).toBe(0);
    expect(TIEMPOS_BRAZO[0].texto).toBe('de golpe');
    expect(TIEMPOS.some((t) => t.valor === 0)).toBe(false);
  });

  it('cada bloque usa su lista de tiempos', () => {
    expect(tiemposDe({ tipo: 'brazo' })).toBe(TIEMPOS_BRAZO);
    expect(tiemposDe({ tipo: 'avanzar' })).toBe(TIEMPOS);
  });

  it('el texto de un tiempo es entendible', () => {
    expect(tiempoBonito(0, 'brazo')).toBe('de golpe');
    expect(tiempoBonito(1, 'brazo')).toBe('un segundo');
    expect(tiempoBonito(2, 'avanzar')).toBe('dos segundos');
    expect(tiempoBonito(2.5, 'avanzar')).toBe('2.5 segundos');
  });

  it('el deslizador apunta al tiempo correcto', () => {
    const brazo = { tipo: 'brazo' };
    expect(indiceDeTiempo(brazo, 0)).toBe(0);
    expect(indiceDeTiempo(brazo, 2)).toBe(TIEMPOS_BRAZO.findIndex((t) => t.valor === 2));
    // un valor que no esta en la lista no rompe nada
    expect(indiceDeTiempo(brazo, 3.7)).toBe(0);
  });
});

describe('los bloques nuevos', () => {
  it('el de brazo sale "de golpe" y con las dos articulaciones', () => {
    const brazo = bloqueNuevo('brazo');
    expect(brazo.tipo).toBe('brazo');
    expect(brazo.lado).toBe('derecho');
    expect(brazo.pose).toBe('arriba');
    expect(brazo.articulacion).toBe('todo');
    expect(brazo.segundos).toBe(0);
  });

  it('los de ruedas y espera salen con su tiempo', () => {
    expect(bloqueNuevo('avanzar')).toMatchObject({ cuanto: 'normal', segundos: 1 });
    expect(bloqueNuevo('girar')).toMatchObject({ hacia: 'izquierda', segundos: 1 });
    expect(bloqueNuevo('espera')).toMatchObject({ segundos: 1 });
  });

  it('cada bloque tiene id propio', () => {
    expect(bloqueNuevo('luz').id).not.toBe(bloqueNuevo('luz').id);
  });
});

describe('el alcance de la accion', () => {
  it('se puede elegir una sola articulacion', () => {
    const brazo = bloqueNuevo('brazo');
    expect(conArticulacion(brazo, 'hombro').articulacion).toBe('hombro');
    expect(conArticulacion(brazo, 'codo').articulacion).toBe('codo');
    expect(ARTICULACIONES).toEqual(['todo', 'hombro', 'codo']);
  });

  it('con las dos articulaciones no puede haber angulo exacto', () => {
    const conAngulo = conModoObjetivo(conArticulacion(bloqueNuevo('brazo'), 'hombro'), 'angulo');
    expect(conAngulo.angulo).toBeDefined();
    const vuelto = conArticulacion(conAngulo, 'todo');
    expect(vuelto.angulo).toBeUndefined();
  });

  it('se puede volver a la pose', () => {
    const conAngulo = conModoObjetivo(conArticulacion(bloqueNuevo('brazo'), 'codo'), 'angulo');
    expect(modoObjetivo(conAngulo)).toBe('angulo');
    const conPose = conModoObjetivo(conAngulo, 'pose');
    expect(conPose.angulo).toBeUndefined();
    expect(modoObjetivo(conPose)).toBe('pose');
  });

  it('cada articulacion tiene su rango', () => {
    expect(rangoDe('hombro')).toEqual(RANGOS.hombro);
    expect(rangoDe('codo')).toEqual(RANGOS.codo);
    expect(rangoDe('todo')).toBeNull();
    // el hombro va de -60 (arriba) a 77 (abajo); el codo de -25 a 170
    expect(RANGOS.hombro.min).toBe(-60);
    expect(RANGOS.hombro.max).toBe(77);
    expect(RANGOS.codo.min).toBe(-25);
    expect(RANGOS.codo.max).toBe(170);
  });

  it('el angulo por defecto esta dentro del rango', () => {
    for (const a of ['hombro', 'codo']) {
      const v = anguloPorDefecto(a);
      expect(v).toBeGreaterThanOrEqual(RANGOS[a].min);
      expect(v).toBeLessThanOrEqual(RANGOS[a].max);
    }
  });
});

describe('el resumen del programa', () => {
  const catalogo = [{ tipo: 'brazo', titulo: 'Mueve el brazo' }];

  it('dice si el brazo va de golpe o lento', () => {
    expect(resumenDeBloque(bloqueNuevo('brazo'), catalogo)).toBe(
      'Mueve el brazo derecho arriba de golpe',
    );
    expect(
      resumenDeBloque({ ...bloqueNuevo('brazo'), segundos: 3 }, catalogo),
    ).toBe('Mueve el brazo derecho arriba tres segundos');
  });

  it('dice la articulacion y el angulo cuando toca', () => {
    const bloque = conModoObjetivo(
      conArticulacion(bloqueNuevo('brazo'), 'codo'),
      'angulo',
    );
    const texto = resumenDeBloque({ ...bloque, angulo: 90 }, catalogo);
    expect(texto).toContain('solo el codo');
    expect(texto).toContain('90°');
  });

  it('no dice articulacion cuando son las dos', () => {
    expect(resumenDeBloque(bloqueNuevo('brazo'), catalogo)).not.toContain('solo el');
  });
});

describe('el historial (deshacer)', () => {
  it('guarda el estado anterior y vuelve atras', () => {
    let h = historialNuevo([]);
    h = historialAplica(h, ['a']);
    h = historialAplica(h, ['a', 'b']);
    expect(h.presente).toEqual(['a', 'b']);
    expect(h.pasado.length).toBe(2);

    h = historialDeshace(h);
    expect(h.presente).toEqual(['a']);
    expect(h.pasado.length).toBe(1);

    h = historialDeshace(h);
    expect(h.presente).toEqual([]);
    expect(h.pasado.length).toBe(0);
  });

  it('deshacer cuando no hay nada que deshacer no rompe nada', () => {
    const h = historialNuevo(['a']);
    expect(historialDeshace(h)).toBe(h);
  });

  it('los cambios seguidos del deslizador se funden en uno solo', () => {
    let h = historialNuevo([]);
    h = historialAplica(h, ['a'], { continuo: true });
    h = historialAplica(h, ['a', 'b'], { continuo: true });
    h = historialAplica(h, ['a', 'b', 'c'], { continuo: true });
    // tres arrastres del deslizador = un solo paso atras
    expect(h.pasado.length).toBe(1);
    const vuelta = historialDeshace(h);
    expect(vuelta.presente).toEqual([]);
  });

  it('un cambio normal despues de uno continuo si se guarda aparte', () => {
    let h = historialNuevo([]);
    h = historialAplica(h, ['a'], { continuo: true });
    h = historialAplica(h, ['a', 'b']);
    expect(h.pasado.length).toBe(2);
  });

  it('el historial no crece sin limite', () => {
    let h = historialNuevo([]);
    for (let i = 0; i < 200; i += 1) {
      h = historialAplica(h, [`b${i}`]);
    }
    expect(h.pasado.length).toBeLessThanOrEqual(60);
  });
});

describe('arrastrar y soltar', () => {
  const a = { id: 'a', tipo: 'luz' };
  const b = { id: 'b', tipo: 'luz' };
  const c = { id: 'c', tipo: 'luz' };
  const repetir = { id: 'r', tipo: 'repetir', veces: 2, bloques: [] };

  it('un bloque se puede quitar de la raiz', () => {
    const lista = [a, b, c];
    const nueva = quitarEnArbol(lista, 'b');
    expect(nueva.map((x) => x.id)).toEqual(['a', 'c']);
    // si no esta, la lista no cambia
    expect(quitarEnArbol(lista, 'zzz')).toBe(lista);
  });

  it('un bloque se puede quitar de dentro de un repetir', () => {
    const lista = [{ ...repetir, bloques: [a, b] }, c];
    const nueva = quitarEnArbol(lista, 'a');
    expect(nueva[0].bloques.map((x) => x.id)).toEqual(['b']);
    expect(nueva[1].id).toBe('c');
  });

  it('un bloque se inserta en la posicion indicada', () => {
    const lista = [a, c];
    const nueva = insertarEnArbol(lista, null, 1, b);
    expect(nueva.map((x) => x.id)).toEqual(['a', 'b', 'c']);
  });

  it('un bloque se inserta dentro de un repetir', () => {
    const lista = [repetir];
    const nueva = insertarEnArbol(lista, 'r', 0, a);
    expect(nueva[0].bloques.map((x) => x.id)).toEqual(['a']);
  });

  it('se localiza un bloque y su sitio', () => {
    const lista = [a, { ...repetir, bloques: [b] }];
    expect(localizarBloque(lista, 'b').padreId).toBe('r');
    expect(localizarBloque(lista, 'b').indice).toBe(0);
    expect(localizarBloque(lista, 'a').padreId).toBeNull();
    expect(localizarBloque(lista, 'zzz')).toBeNull();
  });

  it('un bloque se puede reordenar en la misma lista', () => {
    const lista = [a, b, c];
    const nueva = moverBloque(lista, 'a', null, 2);
    expect(nueva.map((x) => x.id)).toEqual(['b', 'c', 'a']);
  });

  it('un bloque se puede mover dentro de un repetir', () => {
    const lista = [{ ...repetir, bloques: [a, b] }];
    const nueva = moverBloque(lista, 'a', 'r', 1);
    expect(nueva[0].bloques.map((x) => x.id)).toEqual(['b', 'a']);
  });

  it('un bloque sale de dentro de un repetir a la raiz', () => {
    const lista = [{ ...repetir, bloques: [a, b] }, c];
    const nueva = moverBloque(lista, 'a', null, 0);
    // el bloque sale y se queda donde se ha soltado (al principio)
    expect(nueva[1].bloques.map((x) => x.id)).toEqual(['b']);
    expect(nueva.map((x) => x.id)).toEqual(['a', 'r', 'c']);
  });
});

describe('la duracion', () => {
  it('se escribe en texto', () => {
    expect(formatoDuracion(0.5)).toBe('0,5 s');
    expect(formatoDuracion(12.34)).toBe('12,3 s');
    expect(formatoDuracion(75)).toBe('1 min 15 s');
    expect(formatoDuracion(null)).toBe('—');
  });

  it('la estimacion rapida cuenta los bloques', () => {
    expect(estimarDuracion([{ tipo: 'espera', segundos: 2 }])).toBe(2);
    // un brazo "de golpe" tarda al menos 1 s (lo que tarda el servo)
    expect(estimarDuracion([{ tipo: 'brazo', segundos: 0 }])).toBe(1);
    // un movimiento lento dura lo que se le pide
    expect(estimarDuracion([{ tipo: 'brazo', segundos: 3 }])).toBe(3);
    // la luz necesita su tiempo
    expect(estimarDuracion([{ tipo: 'luz' }])).toBeCloseTo(0.4);
  });

  it('la estimacion cuenta las repeticiones', () => {
    const bloque = {
      tipo: 'repetir',
      veces: 3,
      bloques: [{ tipo: 'espera', segundos: 1 }],
    };
    expect(estimarDuracion([bloque])).toBe(3);
  });
});

describe('el programa de ejemplo', () => {
  it('tiene bloques de verdad y todos con id', () => {
    const programa = programaDeEjemplo();
    expect(programa.length).toBeGreaterThan(4);
    const ids = programa.map((b) => b.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('incluye un repetir con bloques dentro', () => {
    const repetir = programaDeEjemplo().find((b) => b.tipo === 'repetir');
    expect(repetir).toBeDefined();
    expect(repetir.bloques.length).toBeGreaterThan(0);
    expect(repetir.veces).toBeGreaterThan(0);
  });

  it('no usa angulos con las dos articulaciones', () => {
    for (const b of programaDeEjemplo()) {
      if (b.tipo === 'brazo') {
        expect(b.articulacion).toBe('todo');
        expect(b.angulo).toBeUndefined();
      }
    }
  });
});

describe('las funciones', () => {
  const funciones = [
    { id: 'f1', nombre: 'Saludo', bloques: [{ id: 'x', tipo: 'espera', segundos: 2 }] },
  ];

  it('una llamada es una referencia: lleva el id de la funcion', () => {
    const bloque = bloqueLlamada('f1');
    expect(bloque.tipo).toBe('llamada');
    expect(bloque.funcion).toBe('f1');
    expect(bloque.id).toBeTruthy();
  });

  it('se busca el nombre de la funcion', () => {
    expect(nombreDeFuncion('f1', funciones)).toBe('Saludo');
    expect(nombreDeFuncion('no-existe', funciones)).toBeNull();
  });

  it('las funciones viajan con el programa por id', () => {
    const mapa = funcionesPara({ f1: funciones[0] });
    expect(Object.keys(mapa)).toEqual(['f1']);
    expect(mapa.f1.nombre).toBe('Saludo');
    expect(mapa.f1.bloques.length).toBe(1);
  });

  it('el resumen de una llamada dice a que funcion llama', () => {
    expect(resumenDeBloque(bloqueLlamada('f1'), [], funciones)).toBe('Llama a «Saludo»');
    expect(resumenDeBloque(bloqueLlamada('nope'), [], funciones)).toBe(
      'Llama a una función que no existe',
    );
  });

  it('la duracion de una llamada cuenta lo que dura la funcion', () => {
    const bloque = bloqueLlamada('f1');
    expect(estimarDuracion([bloque], funciones)).toBe(2);
  });

  it('una llamada sin funcion no rompe la estimacion', () => {
    expect(estimarDuracion([bloqueLlamada('nope')], funciones)).toBe(0);
  });
});

describe('los repite anidados', () => {
  const dentro = { id: 'd1', tipo: 'repetir', veces: 2, bloques: [{ id: 'x', tipo: 'espera' }] };
  const repetir = { id: 'r1', tipo: 'repetir', veces: 3, bloques: [dentro] };

  it('un bloque se mete dentro de un repetir que esta dentro de otro', () => {
    const nuevo = insertarEnArbol([repetir], 'd1', 1, { id: 'y', tipo: 'luz' });
    expect(nuevo[0].bloques[0].bloques.map((b) => b.id)).toEqual(['x', 'y']);
  });

  it('si el repetir no existe, la lista no se toca', () => {
    const lista = [repetir];
    expect(insertarEnArbol(lista, 'no-existe', 0, { id: 'z' })).toBe(lista);
  });

  it('un bloque sale de un repetir anidado (a la raiz)', () => {
    const nueva = moverBloque([repetir], 'x', null, 0);
    // el repetir de dentro se queda sin el bloque...
    expect(nueva[1].bloques[0].bloques).toEqual([]);
    // ...y el bloque sale a la raiz
    expect(nueva.map((b) => b.id)).toEqual(['x', 'r1']);
  });

  it('un bloque se reordena dentro de un repetir anidado', () => {
    const repetir2 = {
      id: 'r2',
      tipo: 'repetir',
      veces: 2,
      bloques: [{ id: 'a', tipo: 'espera' }, { id: 'b', tipo: 'espera' }],
    };
    const nueva = moverBloque([repetir2], 'a', 'r2', 1);
    expect(nueva[0].bloques.map((b) => b.id)).toEqual(['b', 'a']);
  });

  it('un repetir dentro de un repetir se borra bien', () => {
    const nueva = quitarEnArbol([repetir], 'd1');
    expect(nueva[0].bloques.map((b) => b.id)).toEqual([]);
  });
});
