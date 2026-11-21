import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import App, { BloqueEditor } from './main.jsx';
import { bloqueNuevo, conArticulacion, conModoObjetivo } from './bloques.js';

// El catalogo que manda el backend (solo el bloque del brazo, que es el que
// tiene modo avanzado).
const CATALOGO = [
  {
    tipo: 'brazo',
    titulo: 'Mueve el brazo',
    icono: '🙌',
    color: '#9966ff',
    descripcion: 'Levanta o baja los brazos del robot.',
    opciones: {
      lado: ['derecho', 'izquierdo', 'ambos'],
      pose: ['arriba', 'abajo', 'medio', 'golpe', 'guardia'],
      articulacion: ['todo', 'hombro', 'codo'],
    },
  },
];

function pintar(bloque, modo = 'normal') {
  return renderToStaticMarkup(
    <BloqueEditor
      bloque={bloque}
      catalogo={CATALOGO}
      indice={0}
      total={1}
      alCambiar={() => {}}
      alBorrar={() => {}}
      alMover={() => {}}
      alAnadirDentro={() => {}}
      modo={modo}
    />,
  );
}

describe('el bloque del brazo', () => {
  it('en modo normal sale el lado, la pose y el tiempo', () => {
    const html = pintar(bloqueNuevo('brazo'));
    expect(html).toContain('¿Qué brazo?');
    expect(html).toContain('¿Cómo?');
    expect(html).toContain('¿Cuánto tiempo?');
    expect(html).toContain('de golpe');
  });

  it('en modo normal no sale lo avanzado', () => {
    const html = pintar(bloqueNuevo('brazo'));
    expect(html).not.toContain('¿Qué articulación?');
    expect(html).not.toContain('¿A qué ángulo?');
  });

  it('en modo avanzado se puede elegir la articulación', () => {
    const html = pintar(bloqueNuevo('brazo'), 'avanzado');
    expect(html).toContain('¿Qué articulación?');
    expect(html).toContain('hombro');
    expect(html).toContain('codo');
  });

  it('el tiempo se puede elegir en los dos modos', () => {
    expect(pintar(bloqueNuevo('brazo'), 'avanzado')).toContain('¿Cuánto tiempo?');
  });

  it('con una sola articulación sale el ángulo exacto', () => {
    const bloque = conModoObjetivo(conArticulacion(bloqueNuevo('brazo'), 'codo'), 'angulo');
    const html = pintar(bloque, 'avanzado');
    expect(html).toContain('¿Hasta dónde?');
    expect(html).toContain('¿A qué ángulo?');
    expect(html).toContain('type="number"');
    // con el ángulo exacto ya no se eligen las poses
    expect(html).not.toContain('¿Cómo?');
  });

  it('con las dos articulaciones no hay ángulo exacto', () => {
    const html = pintar(bloqueNuevo('brazo'), 'avanzado');
    expect(html).not.toContain('¿Hasta dónde?');
    expect(html).not.toContain('¿A qué ángulo?');
    // pero las poses siguen ahí
    expect(html).toContain('¿Cómo?');
  });

  it('el tiempo del brazo va de 0 (de golpe) a 8 segundos', () => {
    const html = pintar(bloqueNuevo('brazo'));
    // el deslizador tiene 7 posiciones: de golpe, 0.5, 1, 2, 3, 5 y 8
    expect(html).toContain('max="6"');
    expect(html).toContain('value="0"');
  });
});

describe('la aplicacion', () => {
  it('tiene el interruptor de modo normal / avanzado', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('Modo');
    expect(html).toContain('normal');
    expect(html).toContain('avanzado');
  });

  it('el programa vacio lo dice', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('El programa está vacío');
  });
});

describe('el arrastrar y soltar en la interfaz', () => {
  it('cada bloque tiene un asa para arrastrarlo', () => {
    const html = pintar(bloqueNuevo('brazo'));
    expect(html).toContain('class="agarre"');
    expect(html).toContain('draggable="true"');
  });

  it('los botones de subir, bajar y borrar estan en la cabecera del bloque', () => {
    const html = pintar(bloqueNuevo('brazo'));
    // ya no están "sueltos" (position: absolute) encima del deslizador
    expect(html).toContain('bloque-acciones');
    const acciones = html.indexOf('bloque-acciones');
    const deslizador = html.indexOf('class="deslizador"');
    expect(acciones).toBeGreaterThan(-1);
    expect(acciones).toBeLessThan(deslizador);
  });

  it('el bloque muestra cuanto va a durar', () => {
    const html = renderToStaticMarkup(
      <BloqueEditor
        bloque={bloqueNuevo('brazo')}
        catalogo={CATALOGO}
        indice={0}
        total={1}
        alCambiar={() => {}}
        alBorrar={() => {}}
        alMover={() => {}}
        alAnadirDentro={() => {}}
        duracion={2.5}
      />,
    );
    expect(html).toContain('⏱ 2,5 s');
  });
});

describe('la aplicacion y sus botones', () => {
  it('tiene los botones de deshacer, ejemplo y vaciar', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('Deshacer');
    expect(html).toContain('Ejemplo');
    expect(html).toContain('Vaciar');
  });

  it('enseña la duracion estimada y los atajos', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('⏱');
    expect(html).toContain('Atajos');
    expect(html).toContain('deshacer');
  });

  it('el boton de deshacer empieza desactivado (no hay nada que deshacer)', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toMatch(/class="boton boton-chico"[^>]*disabled/);
  });
});

describe('las funciones en la interfaz', () => {
  it('la columna de guardado esta a la derecha', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('4 · Guardado');
    expect(html).toContain('Programas');
    expect(html).toContain('Funciones');
  });

  it('un bloque de llamada enseña el nombre de la funcion', () => {
    const html = renderToStaticMarkup(
      <BloqueEditor
        bloque={{ id: 'c1', tipo: 'llamada', funcion: 'f1' }}
        catalogo={CATALOGO}
        indice={0}
        total={1}
        alCambiar={() => {}}
        alBorrar={() => {}}
        alMover={() => {}}
        alAnadirDentro={() => {}}
        funciones={[{ id: 'f1', nombre: 'Saludo', bloques: [] }]}
      />,
    );
    expect(html).toContain('Saludo');
    expect(html).toContain('Función: Saludo');
    expect(html).toContain('Es una referencia');
  });

  it('si la funcion ya no existe, el bloque avisa', () => {
    const html = renderToStaticMarkup(
      <BloqueEditor
        bloque={{ id: 'c1', tipo: 'llamada', funcion: 'f9' }}
        catalogo={CATALOGO}
        indice={0}
        total={1}
        alCambiar={() => {}}
        alBorrar={() => {}}
        alMover={() => {}}
        alAnadirDentro={() => {}}
        funciones={[]}
      />,
    );
    expect(html).toContain('ya no existe');
  });
});
