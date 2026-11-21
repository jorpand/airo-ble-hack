// La logica de los bloques, suelta del React.
//
// Todo lo que se puede decidir sin pintar nada vive aqui: los tiempos, los
// valores por defecto de cada bloque y el texto del resumen. Asi se puede
// probar con vitest (que no tiene navegador) y la interfaz solo se ocupa de
// pintar.

// Cuanto tiempo es "un ratito", "un segundo"... (para los niños).
export const TIEMPOS = [
  { valor: 0.5, texto: 'un instante' },
  { valor: 1, texto: 'un segundo' },
  { valor: 2, texto: 'dos segundos' },
  { valor: 3, texto: 'tres segundos' },
  { valor: 5, texto: 'cinco segundos' },
  { valor: 8, texto: 'un buen rato' },
];

// Los brazos tienen una opcion mas: "de golpe" (0 segundos). El servo va a
// su velocidad y se para en el destino; cualquier otro valor es un
// movimiento lento, en rampa, durante ese tiempo.
export const TIEMPOS_BRAZO = [
  { valor: 0, texto: 'de golpe' },
  { valor: 0.5, texto: 'medio segundo' },
  { valor: 1, texto: 'un segundo' },
  { valor: 2, texto: 'dos segundos' },
  { valor: 3, texto: 'tres segundos' },
  { valor: 5, texto: 'cinco segundos' },
  { valor: 8, texto: 'un buen rato' },
];

// Que articulacion se puede mover: las dos, solo el hombro o solo el codo.
export const ARTICULACIONES = ['todo', 'hombro', 'codo'];

// El rango de cada articulacion, en los angulos de la app (los de las poses:
// el hombro va de -60 arriba a 77 abajo, el codo de -25 abajo a 170 arriba).
export const RANGOS = {
  hombro: { min: -60, max: 77 },
  codo: { min: -25, max: 170 },
};

let contador = 0;
const nuevoId = () => `${Date.now()}-${contador++}`;

// El texto de un tiempo: "de golpe", "un segundo"...
export function tiempoBonito(segundos, tipo) {
  if (segundos === 0) return 'de golpe';
  const lista = tipo === 'brazo' ? TIEMPOS_BRAZO : TIEMPOS;
  const t = lista.find((x) => x.valor === segundos);
  return t ? t.texto : `${segundos} segundos`;
}

// Los tiempos que se pueden elegir para un bloque.
export function tiemposDe(bloque) {
  return bloque && bloque.tipo === 'brazo' ? TIEMPOS_BRAZO : TIEMPOS;
}

// La posicion del tiempo en el deslizador (para no saltarse valores).
export function indiceDeTiempo(bloque, valor) {
  const tiempos = tiemposDe(bloque);
  const i = tiempos.findIndex((t) => t.valor === valor);
  return i < 0 ? 0 : i;
}

// Un bloque nuevo, con sus valores por defecto.
export function bloqueNuevo(tipo) {
  const base = { id: nuevoId(), tipo };
  if (tipo === 'avanzar' || tipo === 'atras') {
    Object.assign(base, { cuanto: 'normal', segundos: 1 });
  } else if (tipo === 'girar') {
    Object.assign(base, { hacia: 'izquierda', segundos: 1 });
  } else if (tipo === 'brazo') {
    // "de golpe" (0): el servo va a su velocidad. En el modo avanzado se
    // puede elegir el tiempo (movimiento lento) y la articulacion.
    Object.assign(base, {
      lado: 'derecho',
      pose: 'arriba',
      articulacion: 'todo',
      segundos: 0,
    });
  } else if (tipo === 'luz') {
    Object.assign(base, { modo: 'encendida' });
  } else if (tipo === 'espera') {
    Object.assign(base, { segundos: 1 });
  } else if (tipo === 'repetir') {
    Object.assign(base, { veces: 2, bloques: [] });
  }
  return base;
}

// El texto que resume lo que hace un bloque (lo que sale en "Lo que va a
// hacer").
export function resumenDeBloque(bloque, catalogo = [], funciones = []) {
  // Una llamada es una referencia: el texto dice a que funcion llama.
  if (bloque.tipo === 'llamada') {
    const nombre = nombreDeFuncion(bloque.funcion, funciones);
    return nombre ? `Llama a «${nombre}»` : 'Llama a una función que no existe';
  }
  const info = catalogo.find((c) => c.tipo === bloque.tipo);
  const partes = [];
  if (bloque.lado && bloque.pose) partes.push(`${bloque.lado} ${bloque.pose}`);
  if (bloque.articulacion && bloque.articulacion !== 'todo') {
    partes.push(`solo el ${bloque.articulacion}`);
  }
  if (bloque.angulo !== undefined && bloque.angulo !== null) {
    partes.push(`a ${bloque.angulo}°`);
  }
  if (bloque.cuanto) partes.push(`(${bloque.cuanto})`);
  if (bloque.hacia) partes.push(bloque.hacia);
  if (bloque.modo) partes.push(bloque.modo);

  // El tiempo va al final: asi se lee "Mueve el brazo derecho arriba un
  // segundo" y no "un segundo Mueve el brazo...".
  if (bloque.segundos !== undefined) {
    partes.push(tiempoBonito(bloque.segundos, bloque.tipo));
  }
  return [info ? info.titulo : bloque.tipo, ...partes].join(' ');
}

// Cambia la articulacion de un bloque de brazo.
//
// Con "todo" se mueven las dos (hombro y codo) y el destino es una pose, asi
// que el angulo exacto se borra: un solo angulo para las dos articulaciones
// no significaria nada.
export function conArticulacion(bloque, articulacion) {
  const limpio = { ...bloque, articulacion };
  if (articulacion === 'todo') {
    delete limpio.angulo;
  }
  return limpio;
}

// Elige entre ir "a la pose" o "a un angulo exacto".
export function conModoObjetivo(bloque, modo) {
  if (modo === 'angulo') {
    return {
      ...bloque,
      angulo: bloque.angulo ?? anguloPorDefecto(bloque.articulacion),
    };
  }
  const limpio = { ...bloque };
  delete limpio.angulo;
  return limpio;
}

// Como se llama el modo de objetivo de un bloque.
export function modoObjetivo(bloque) {
  return bloque.angulo === undefined || bloque.angulo === null ? 'pose' : 'angulo';
}

// El rango de una articulacion (o null si no se puede elegir angulo).
export function rangoDe(articulacion) {
  return RANGOS[articulacion] || null;
}

// Un angulo razonable para empezar: el de la pose "medio" (0 grados).
export function anguloPorDefecto(articulacion) {
  const rango = RANGOS[articulacion];
  if (!rango) return 0;
  return Math.min(Math.max(0, rango.min), rango.max);
}

// --- las funciones ----------------------------------------------------------

// Un bloque que llama a una funcion guardada.
//
// Es una **referencia**: el bloque solo lleva el id de la funcion, no sus
// pasos. Asi, si despues editas la funcion, todos los programas que la usan
// ejecutan la version nueva (el backend la despliega al ejecutar).
export function bloqueLlamada(idFuncion) {
  return { id: nuevoId(), tipo: 'llamada', funcion: idFuncion };
}

// El nombre de una funcion guardada (o null si no existe).
export function nombreDeFuncion(id, funciones = []) {
  const f = (funciones || []).find((x) => x.id === id);
  return f ? f.nombre : null;
}

// El mapa de funciones que viaja **con** el programa al backend (por id),
// porque el backend necesita los bloques para desplegar las llamadas.
export function funcionesPara(mapa = {}) {
  const salida = {};
  for (const [id, f] of Object.entries(mapa || {})) {
    salida[id] = { id, nombre: f.nombre, bloques: f.bloques || [] };
  }
  return salida;
}

// --- el historial (para deshacer) -------------------------------------------

//: Cuantos estados se guardan. Suficiente para volver atras un rato sin que
//: la memoria se dispare.
export const LIMITE_HISTORIAL = 60;

// Un historial vacio, con el programa que hay ahora mismo.
export function historialNuevo(estado = []) {
  return { pasado: [], presente: estado, futuro: [], continuo: false };
}

// Aplica un cambio nuevo.
//
// `continuo` sirve para los deslizadores: al arrastrar el tiempo se disparan
// muchos cambios seguidos, y si cada uno guardara un estado habria que pulsar
// Ctrl+Z quince veces. Con `continuo` los cambios seguidos se funden en uno
// solo (mientras el anterior tambien fue continuo).
export function historialAplica(historial, estado, opciones = {}) {
  const continuo = Boolean(opciones.continuo);
  const fusiona = continuo && historial.continuo;
  const pasado = fusiona ? historial.pasado : [...historial.pasado, historial.presente];
  return {
    pasado: pasado.slice(-LIMITE_HISTORIAL),
    presente: estado,
    futuro: [],
    continuo,
  };
}

// Vuelve al estado anterior.
export function historialDeshace(historial) {
  if (!historial.pasado.length) return historial;
  const anterior = historial.pasado[historial.pasado.length - 1];
  return {
    pasado: historial.pasado.slice(0, -1),
    presente: anterior,
    futuro: [historial.presente, ...historial.futuro],
    continuo: false,
  };
}

// --- el arbol de bloques (arrastrar y soltar) -------------------------------

// Quita un bloque de donde este (raiz o dentro de un "repetir") y devuelve
// la lista nueva. Si no lo encuentra, devuelve la lista sin cambios.
export function quitarEnArbol(bloques, id) {
  let quitado = false;
  const nuevo = [];
  for (const b of bloques) {
    if (b.id === id) {
      quitado = true;
      continue;
    }
    if (b.bloques && b.bloques.length) {
      const hijos = quitarEnArbol(b.bloques, id);
      if (hijos !== b.bloques) {
        quitado = true;
        nuevo.push({ ...b, bloques: hijos });
        continue;
      }
    }
    nuevo.push(b);
  }
  return quitado ? nuevo : bloques;
}

// Inserta un bloque en la lista. `padreId` es el "repetir" que lo contiene
// (null = la lista de arriba del todo) y `indice` la posicion.
//
// Busca el "repetir" RECORRIENDO el arbol entero: un "repetir" puede estar
// dentro de otro "repetir", y hay que poder meter bloques en el de dentro.
// (Antes solo miraba el primer nivel, asi que en un "repetir" de dentro no
// se metia nada y daba la sensacion de que no funcionaba.)
//
// Si no encuentra el "repetir", devuelve la lista **tal cual** (para que el
// que llama pueda saber que no ha cambiado nada).
export function insertarEnArbol(bloques, padreId, indice, bloque) {
  if (padreId === null || padreId === undefined) {
    const pos = Math.max(0, Math.min(indice, bloques.length));
    return [...bloques.slice(0, pos), bloque, ...bloques.slice(pos)];
  }
  const meter = (lista) => {
    let cambiado = false;
    const salida = lista.map((b) => {
      if (b.id === padreId) {
        cambiado = true;
        const hijos = [...(b.bloques || [])];
        const pos = Math.max(0, Math.min(indice, hijos.length));
        return { ...b, bloques: [...hijos.slice(0, pos), bloque, ...hijos.slice(pos)] };
      }
      if (b.bloques && b.bloques.length) {
        const [hijos, haCambiado] = meter(b.bloques);
        if (haCambiado) {
          cambiado = true;
          return { ...b, bloques: hijos };
        }
      }
      return b;
    });
    return [cambiado ? salida : lista, cambiado];
  };
  const [nueva, puesto] = meter(bloques);
  return puesto ? nueva : bloques;
}

// Donde esta un bloque: el bloque, la lista que lo contiene (el id del
// "repetir" o null si esta en la raiz) y su posicion en esa lista.
export function localizarBloque(bloques, id, padreId = null) {
  const i = bloques.findIndex((b) => b.id === id);
  if (i >= 0) return { bloque: bloques[i], padreId, indice: i };
  for (const b of bloques) {
    if (b.bloques && b.bloques.length) {
      const r = localizarBloque(b.bloques, id, b.id);
      if (r) return r;
    }
  }
  return null;
}

// Mueve un bloque a otra posicion (o a otra lista, entrando o saliendo de un
// "repetir"). Devuelve la lista nueva.
//
// `indiceDestino` es la posicion en la lista de destino **tal y como se ve
// antes de quitar el bloque**: al quitarlo, las posiciones se corren solas y
// el bloque acaba justo donde se queria.
export function moverBloque(bloques, id, padreDestino, indiceDestino) {
  const origen = localizarBloque(bloques, id);
  if (!origen) return bloques;
  const bloque = origen.bloque;
  const sinBloque = quitarEnArbol(bloques, id);
  return insertarEnArbol(sinBloque, padreDestino, indiceDestino, bloque);
}

// --- la duracion ------------------------------------------------------------

// Cuanto dura el kata de karate (la suma de sus pasos). Es el unico bloque
// que no se puede calcular solo: el backend lo tiene en `airo_ble.console`.
export const DURACION_KATA = 17.9;

// Una estimacion rapida, para cuando el servidor no contesta (por ejemplo si
// la interfaz esta abierta sin robot). El backend dice la verdad; esto solo
// es para tener algo puesto.
export function estimarDuracion(bloques, funciones = []) {
  let total = 0;
  for (const b of bloques || []) {
    if (b.tipo === 'repetir') {
      total += (b.veces || 1) * estimarDuracion(b.bloques || [], funciones);
    } else if (b.tipo === 'llamada') {
      // Una llamada dura lo que dura la funcion llamada.
      const f = (funciones || []).find((x) => x.id === b.funcion);
      total += f ? estimarDuracion(f.bloques || [], funciones) : 0;
    } else if (b.tipo === 'kata') {
      total += DURACION_KATA;
    } else if (b.tipo === 'luz') {
      total += 0.4;
    } else if (b.tipo === 'para') {
      total += 0;
    } else if (b.tipo === 'brazo') {
      // De golpe: el servo tarda lo que tarde en llegar (al menos 1 s).
      // Con tiempo: el movimiento lento dura ese tiempo.
      total += Math.max(b.segundos || 0, 1);
    } else {
      total += b.segundos ?? 1;
    }
  }
  return total;
}

// La duracion en texto: "0,5 s", "12,3 s", "1 min 05 s".
export function formatoDuracion(segundos) {
  if (segundos === null || segundos === undefined || Number.isNaN(segundos)) {
    return '—';
  }
  const s = Math.max(0, Math.round(segundos * 10) / 10);
  if (s < 60) return `${String(s).replace('.', ',')} s`;
  const min = Math.floor(s / 60);
  const resto = Math.round(s - min * 60);
  return `${min} min ${String(resto).padStart(2, '0')} s`;
}

// --- el programa de ejemplo -------------------------------------------------

// Un bloque con valores concretos (parte del bloque por defecto).
function bloqueDe(tipo, valores) {
  return { ...bloqueNuevo(tipo), ...valores };
}

// Un programa que funciona a la primera, para ver como queda todo.
// Saludar con los dos brazos, saludar con la luz, dar un paso y volver.
export function programaDeEjemplo() {
  return [
    bloqueDe('luz', { modo: 'parpadea' }),
    bloqueDe('brazo', { lado: 'derecho', pose: 'arriba' }),
    bloqueDe('brazo', { lado: 'izquierdo', pose: 'arriba' }),
    bloqueDe('espera', { segundos: 1 }),
    bloqueDe('repetir', {
      veces: 2,
      bloques: [
        bloqueDe('brazo', { lado: 'derecho', pose: 'golpe' }),
        bloqueDe('brazo', { lado: 'derecho', pose: 'guardia' }),
      ],
    }),
    bloqueDe('girar', { hacia: 'derecha', segundos: 1 }),
    bloqueDe('avanzar', { cuanto: 'normal', segundos: 1 }),
    bloqueDe('luz', { modo: 'apagada' }),
  ];
}
