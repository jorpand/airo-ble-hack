import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Robot from './Robot.jsx';
import './styles.css';
import {
  obtenerBloques,
  obtenerEstado,
  obtenerDuracion,
  obtenerGuardado,
  ejecutarPrograma,
  guardarPrograma,
  guardarFuncion,
  borrarPrograma,
  borrarFuncion,
  parar,
  conectar,
  desconectar,
  suscribirEstado,
} from './api.js';
import {
  ARTICULACIONES,
  anguloPorDefecto,
  bloqueLlamada,
  bloqueNuevo,
  conArticulacion,
  conModoObjetivo,
  estimarDuracion,
  formatoDuracion,
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
  rangoDe,
  resumenDeBloque,
  tiempoBonito,
  tiemposDe,
  quitarEnArbol,
} from './bloques.js';

const CUANTOS = [
  { valor: 'poquito', texto: 'poquito' },
  { valor: 'normal', texto: 'normal' },
  { valor: 'mucho', texto: 'mucho' },
];

//: El color de las llamadas a funciones (no estan en el catalogo del
//: backend: no se eligen en la paleta, se arrastran desde "Guardado").
const COLOR_LLAMADA = '#0d9488';

// --- el arrastrar y soltar --------------------------------------------------

// Lo que lleva el raton (o el dedo) mientras se arrastra un bloque.
const ARRASTRE_PALETA = 'paleta';
const ARRASTRE_PROGRAMA = 'programa';
const ARRASTRE_FUNCION = 'funcion';

// Lee lo que lleva el arrastre. Si no se entiende, no es un bloque nuestro.
function leerArrastre(evento) {
  try {
    const texto = evento.dataTransfer?.getData('text/plain');
    if (!texto) return null;
    const datos = JSON.parse(texto);
    if (datos && datos.origen) return datos;
  } catch (e) {
    return null;
  }
  return null;
}

// La franja donde se suelta un bloque. Solo se ve mientras se arrastra.
function ZonaSoltar({ padreId, indice, alSoltar }) {
  const [sobre, setSobre] = useState(false);
  return (
    <div
      className={`zona-soltar ${sobre ? 'zona-soltar-sobre' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        setSobre(true);
      }}
      onDragLeave={() => setSobre(false)}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setSobre(false);
        const datos = leerArrastre(e);
        if (datos && alSoltar) alSoltar(padreId, indice, datos);
      }}
    />
  );
}

// --- Los controles del bloque ---------------------------------------------

// El deslizador del tiempo. Los brazos tienen un valor mas: "de golpe" (0
// segundos), que es el servo a toda velocidad; el resto son movimientos
// lentos, en rampa.
function DeslizadorTiempo({ bloque, alCambiar }) {
  const tiempos = tiemposDe(bloque);
  return (
    <div className="opcion">
      <span className="opcion-etiqueta">
        ¿Cuánto tiempo? ({tiempoBonito(bloque.segundos, bloque.tipo)})
      </span>
      <input
        className="deslizador"
        type="range"
        min="0"
        max={String(tiempos.length - 1)}
        value={String(indiceDeTiempo(bloque, bloque.segundos))}
        onChange={(e) =>
          alCambiar(
            { ...bloque, segundos: tiempos[Number(e.target.value)].valor },
            true,
          )
        }
      />
      <div className="tiempos">
        {tiempos.map((t, i) => (
          <span key={t.valor} className={`tiempo-mini ${i === 0 ? 'tiempo-mini-0' : ''}`}>
            {i === 0 ? '⚡' : ''}
          </span>
        ))}
      </div>
    </div>
  );
}

// El deslizador del angulo (solo en modo avanzado). El rango depende de la
// articulacion: el hombro va de -60 a 77 y el codo de -25 a 170.
function DeslizadorAngulo({ bloque, alCambiar }) {
  const rango = rangoDe(bloque.articulacion);
  if (!rango) return null;
  const angulo = bloque.angulo ?? anguloPorDefecto(bloque.articulacion);
  return (
    <div className="opcion opcion-avanzada">
      <span className="opcion-etiqueta">
        ¿A qué ángulo? ({angulo}°)
        <input
          className="caja-cantidad"
          type="number"
          min={rango.min}
          max={rango.max}
          step="1"
          value={angulo}
          onChange={(e) => alCambiar({ ...bloque, angulo: Number(e.target.value) }, true)}
        />
      </span>
      <input
        className="deslizador"
        type="range"
        min={String(rango.min)}
        max={String(rango.max)}
        step="1"
        value={String(angulo)}
        onChange={(e) => alCambiar({ ...bloque, angulo: Number(e.target.value) }, true)}
      />
      <div className="tiempos">
        <span className="tiempo-mini">{rango.min}°</span>
        <span className="tiempo-mini">{rango.max}°</span>
      </div>
    </div>
  );
}

// --- El bloque de un programa ---------------------------------------------

export function BloqueEditor({
  bloque,
  catalogo,
  indice,
  total,
  alCambiar,
  alBorrar,
  alMover,
  alAnadirDentro,
  alSoltar,
  alEmpezarArrastre,
  duracion,
  seleccionado,
  alSeleccionar,
  funciones = [],
  nivel = 0,
  modo = 'normal',
}) {
  // La llamada a una funcion no esta en el catalogo (no se elige en la
  // paleta: se arrastra desde "Guardado"), asi que se inventa aqui su ficha.
  const esLlamada = bloque.tipo === 'llamada';
  const nombreFuncion = esLlamada ? nombreDeFuncion(bloque.funcion, funciones) : null;
  const info =
    catalogo.find((c) => c.tipo === bloque.tipo) ||
    (esLlamada
      ? {
          tipo: 'llamada',
          titulo: nombreFuncion || 'Función que no existe',
          icono: '⚡',
          color: COLOR_LLAMADA,
          descripcion: 'Llama a una función guardada.',
        }
      : null);
  if (!info) return null;

  const opciones = info.opciones || {};

  const elegir = (clave, valor) => alCambiar({ ...bloque, [clave]: valor });

  // El modo avanzado solo afecta al bloque de brazo: es el unico que puede
  // elegir articulacion y angulo exacto.
  const esBrazo = bloque.tipo === 'brazo';
  const avanzado = esBrazo && modo === 'avanzado';
  const articulacion = bloque.articulacion || 'todo';
  const unaArticulacion = articulacion !== 'todo';
  // Con las dos articulaciones no hay angulo exacto: el destino es una pose.
  const anguloExacto = avanzado && unaArticulacion && modoObjetivo(bloque) === 'angulo';

  // El asa de arrastrar: es lo unico que se puede agarrar (asi el deslizador
  // se puede usar sin que el bloque se mueva).
  const empezarArrastre = (e) => {
    // 'copyMove' (y no 'copy') porque el navegador solo acepta el drop si
    // el efecto que pide el destino esta permitido por el origen.
    e.dataTransfer.effectAllowed = 'copyMove';
    e.dataTransfer.setData(
      'text/plain',
      JSON.stringify({ origen: ARRASTRE_PROGRAMA, id: bloque.id }),
    );
    if (alEmpezarArrastre) alEmpezarArrastre({ origen: ARRASTRE_PROGRAMA, id: bloque.id });
  };

  const hijos = bloque.bloques || [];

  return (
    <div
      className={`bloque ${seleccionado ? 'bloque-seleccionado' : ''}`}
      style={{ background: info.color }}
    >
      <div
        className="bloque-cabecera"
        onClick={(e) => alSeleccionar && alSeleccionar(bloque.id, e.shiftKey)}
        title="Clic para marcar · Mayúsculas para marcar varios"
      >
        <span
          className="agarre"
          draggable
          onDragStart={empezarArrastre}
          title="Arrastra para mover el bloque"
          aria-label="Mover el bloque"
        >
          ⠿
        </span>
        <span className="bloque-icono">{info.icono}</span>
        <span className="bloque-titulo">{info.titulo}</span>
        <span className="bloque-num">{indice + 1}</span>
        <div className="bloque-acciones">
          <button
            className="mini"
            onClick={(e) => {
              e.stopPropagation();
              alMover(-1);
            }}
            disabled={indice === 0}
            title="Subir"
          >
            ▲
          </button>
          <button
            className="mini"
            onClick={(e) => {
              e.stopPropagation();
              alMover(1);
            }}
            disabled={indice === total - 1}
            title="Bajar"
          >
            ▼
          </button>
          <button
            className="mini mini-borrar"
            onClick={(e) => {
              e.stopPropagation();
              alBorrar();
            }}
            title="Borrar"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="bloque-opciones">
        {esLlamada && (
          <div className="opcion">
            <span className="opcion-etiqueta">
              {nombreFuncion ? `Función: ${nombreFuncion}` : '⚠ Esta función ya no existe'}
            </span>
            <p className="nota-bloque">
              {nombreFuncion
                ? 'Es una referencia: si editas la función, este bloque usa la versión nueva.'
                : 'Bórralo, o vuelve a guardarla desde la columna de la derecha.'}
            </p>
          </div>
        )}

        {opciones.cuanto && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿Cuánto?</span>
            <div className="chips">
              {CUANTOS.map((c) => (
                <button
                  key={c.valor}
                  className={`chip ${bloque.cuanto === c.valor ? 'chip-activo' : ''}`}
                  onClick={() => elegir('cuanto', c.valor)}
                >
                  {c.texto}
                </button>
              ))}
            </div>
          </div>
        )}

        {opciones.hacia && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿Hacia dónde?</span>
            <div className="chips">
              {opciones.hacia.map((v) => (
                <button
                  key={v}
                  className={`chip ${bloque.hacia === v ? 'chip-activo' : ''}`}
                  onClick={() => elegir('hacia', v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {opciones.lado && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿Qué brazo?</span>
            <div className="chips">
              {opciones.lado.map((v) => (
                <button
                  key={v}
                  className={`chip ${bloque.lado === v ? 'chip-activo' : ''}`}
                  onClick={() => elegir('lado', v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {opciones.pose && !anguloExacto && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿Cómo?</span>
            <div className="chips">
              {opciones.pose.map((v) => (
                <button
                  key={v}
                  className={`chip ${bloque.pose === v ? 'chip-activo' : ''}`}
                  onClick={() => elegir('pose', v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {avanzado && (
          <div className="opcion opcion-avanzada">
            <span className="opcion-etiqueta">¿Qué articulación?</span>
            <div className="chips">
              {ARTICULACIONES.map((v) => (
                <button
                  key={v}
                  className={`chip ${articulacion === v ? 'chip-activo' : ''}`}
                  onClick={() => alCambiar(conArticulacion(bloque, v))}
                >
                  {v === 'todo' ? 'todo' : v}
                </button>
              ))}
            </div>
          </div>
        )}

        {avanzado && unaArticulacion && (
          <div className="opcion opcion-avanzada">
            <span className="opcion-etiqueta">¿Hasta dónde?</span>
            <div className="chips">
              <button
                className={`chip ${!anguloExacto ? 'chip-activo' : ''}`}
                onClick={() => alCambiar(conModoObjetivo(bloque, 'pose'))}
              >
                a la pose
              </button>
              <button
                className={`chip ${anguloExacto ? 'chip-activo' : ''}`}
                onClick={() => alCambiar(conModoObjetivo(bloque, 'angulo'))}
              >
                a un ángulo
              </button>
            </div>
          </div>
        )}

        {anguloExacto && (
          <DeslizadorAngulo bloque={bloque} alCambiar={alCambiar} />
        )}

        {opciones.modo && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿La luz?</span>
            <div className="chips">
              {opciones.modo.map((v) => (
                <button
                  key={v}
                  className={`chip ${bloque.modo === v ? 'chip-activo' : ''}`}
                  onClick={() => elegir('modo', v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {opciones.veces && (
          <div className="opcion">
            <span className="opcion-etiqueta">¿Cuántas veces?</span>
            <div className="chips">
              {opciones.veces.map((v) => (
                <button
                  key={v}
                  className={`chip ${String(bloque.veces) === v ? 'chip-activo' : ''}`}
                  onClick={() => elegir('veces', parseInt(v, 10))}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {(bloque.segundos !== undefined) && (
          <DeslizadorTiempo bloque={bloque} alCambiar={alCambiar} />
        )}
      </div>

      {bloque.tipo === 'repetir' && (
        <div className="dentro">
          {hijos.map((hijo, i) => (
            <React.Fragment key={hijo.id}>
              <ZonaSoltar padreId={bloque.id} indice={i} alSoltar={alSoltar} />
              <BloqueEditor
                bloque={hijo}
                catalogo={catalogo}
                indice={i}
                total={hijos.length}
                alCambiar={(nuevoHijo, continuo) =>
                  alCambiar(
                    {
                      ...bloque,
                      bloques: (bloque.bloques || []).map((b) =>
                        b.id === nuevoHijo.id ? nuevoHijo : b,
                      ),
                    },
                    continuo,
                  )
                }
                alBorrar={() =>
                  alCambiar({
                    ...bloque,
                    bloques: (bloque.bloques || []).filter((b) => b.id !== hijo.id),
                  })
                }
                alMover={(d) => {
                  const lista = [...(bloque.bloques || [])];
                  const j = i + d;
                  if (j < 0 || j >= lista.length) return;
                  [lista[i], lista[j]] = [lista[j], lista[i]];
                  alCambiar({ ...bloque, bloques: lista });
                }}
                alAnadirDentro={alAnadirDentro}
                alSoltar={alSoltar}
                alEmpezarArrastre={alEmpezarArrastre}
                seleccionado={seleccionado === hijo.id}
                alSeleccionar={alSeleccionar}
                funciones={funciones}
                nivel={nivel + 1}
                modo={modo}
              />
            </React.Fragment>
          ))}
          <ZonaSoltar padreId={bloque.id} indice={hijos.length} alSoltar={alSoltar} />
          <div className="mini-paleta">
            {catalogo.map((c) => (
              <button
                key={c.tipo}
                className="mini-bloque"
                style={{ background: c.color }}
                title={c.titulo}
                onClick={() => alAnadirDentro(bloque, c.tipo)}
              >
                {c.icono}
              </button>
            ))}
          </div>
        </div>
      )}

      {duracion !== undefined && duracion !== null && (
        <div className="bloque-pie">⏱ {formatoDuracion(duracion)}</div>
      )}
    </div>
  );
}

// --- La columna de lo guardado ----------------------------------------------

function ColumnaGuardado({
  guardado,
  nombrePrograma,
  alCambiarNombre,
  alGuardar,
  alGuardarComo,
  alCargar,
  alBorrarPrograma,
  alUsar,
  alEditar,
  alBorrarFuncion,
  alEmpezarArrastre,
}) {
  return (
    <section className="columna guardado">
      <h2>4 · Guardado</h2>
      <p className="pista">
        Los programas y las funciones se guardan en el servidor, así que no se
        pierden al recargar la página.
      </p>

      <div className="guardado-secciones">
        <div className="guardado-seccion">
          <h3>Programas</h3>
          <input
            className="caja-nombre"
            value={nombrePrograma}
            onChange={(e) => alCambiarNombre(e.target.value)}
            placeholder="Nombre del programa"
            aria-label="Nombre del programa"
          />
          <div className="guardar-fila">
            <button className="boton boton-chico" onClick={alGuardar} title="Guardar el programa">
              💾 Guardar
            </button>
            <button
              className="boton boton-chico"
              onClick={alGuardarComo}
              title="Guardar una copia con otro nombre"
            >
              Guardar como
            </button>
          </div>
          {guardado.programas.length === 0 && (
            <p className="pista vacio-guardado">Todavía no hay programas guardados.</p>
          )}
          <ul className="lista-guardados">
            {guardado.programas.map((p) => (
              <li key={p.id}>
                <span className="guardado-nombre" title={`${(p.bloques || []).length} bloques`}>
                  📄 {p.nombre}
                </span>
                <span className="guardado-botones">
                  <button onClick={() => alCargar(p)} title="Cargar este programa">
                    Cargar
                  </button>
                  <button onClick={() => alBorrarPrograma(p)} title="Borrar">
                    ✕
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="guardado-seccion">
          <h3>Funciones</h3>
          <p className="pista">
            Un trozo de bloques con nombre. Márcalo en el programa (clic y
            Mayúsculas) y guárdalo como función; luego arrástralo aquí al
            programa para usarlo.
          </p>
          {guardado.funciones.length === 0 && (
            <p className="pista vacio-guardado">Todavía no hay funciones.</p>
          )}
          <ul className="lista-guardados">
            {guardado.funciones.map((f) => (
              <li
                key={f.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = 'copyMove';
                  e.dataTransfer.setData(
                    'text/plain',
                    JSON.stringify({ origen: ARRASTRE_FUNCION, id: f.id }),
                  );
                  alEmpezarArrastre({ origen: ARRASTRE_FUNCION, id: f.id });
                }}
                title="Arrastra la función al programa para usarla"
              >
                <span className="guardado-nombre">⚡ {f.nombre}</span>
                <span className="guardado-botones">
                  <button onClick={() => alUsar(f)} title="Añadirla al programa">
                    Usar
                  </button>
                  <button onClick={() => alEditar(f)} title="Editar sus bloques">
                    Editar
                  </button>
                  <button onClick={() => alBorrarFuncion(f)} title="Borrar">
                    ✕
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// --- La app ----------------------------------------------------------------

export default function App() {
  const [catalogo, setCatalogo] = useState([]);
  const [historial, setHistorial] = useState(() => historialNuevo([]));
  const [estado, setEstado] = useState(null);
  const [mensaje, setMensaje] = useState('Pulsa un bloque para empezar el programa.');
  const [corriendo, setCorriendo] = useState(false);
  const [duracion, setDuracion] = useState({ total: null, bloques: [], estimado: false });
  const [seleccion, setSeleccion] = useState(null);
  const [rango, setRango] = useState([]);
  const [ancla, setAncla] = useState(null);
  const [arrastrando, setArrastrando] = useState(null);
  const [guardado, setGuardado] = useState({ programas: [], funciones: [] });
  const [editando, setEditando] = useState(null);
  const [nombrePrograma, setNombrePrograma] = useState('');
  const [idPrograma, setIdPrograma] = useState(null);
  const [nombreFuncion, setNombreFuncion] = useState('');
  // El modo de la interfaz: "normal" (lo de siempre) o "avanzado" (donde se
  // puede elegir articulacion y angulo exacto del brazo). Se guarda para
  // que no se pierda al recargar.
  const [modo, setModo] = useState(() => {
    try {
      return localStorage.getItem('airo-modo') === 'avanzado' ? 'avanzado' : 'normal';
    } catch (e) {
      return 'normal';
    }
  });

  // Mientras se edita una funcion, la columna del programa muestra sus
  // bloques; si no, muestra el programa de siempre.
  const bloques = editando ? editando.bloques : historial.presente;

  useEffect(() => {
    try {
      localStorage.setItem('airo-modo', modo);
    } catch (e) {
      // sin localStorage (modo privado) no pasa nada
    }
  }, [modo]);

  useEffect(() => {
    obtenerBloques().then(setCatalogo).catch(() => setMensaje('No se pudo contactar con el servidor.'));
    obtenerEstado().then(setEstado).catch(() => {});
    obtenerGuardado()
      .then((datos) =>
        setGuardado({
          programas: datos.programas || [],
          funciones: datos.funciones || [],
        }),
      )
      .catch(() => setMensaje('No se pudo contactar con el servidor.'));
  }, []);

  useEffect(() => {
    const pararWs = suscribirEstado(
      (nuevo) => setEstado(nuevo),
      () => {},
    );
    return pararWs;
  }, []);

  // Si el arrastre se acaba fuera de la pagina (o el nodo del que se
  // arrastra desaparece al redibujarse), las franjas de soltado se quedan
  // visibles. Esto las limpia siempre.
  useEffect(() => {
    const limpiar = () => setArrastrando(null);
    window.addEventListener('dragend', limpiar);
    window.addEventListener('drop', limpiar);
    return () => {
      window.removeEventListener('dragend', limpiar);
      window.removeEventListener('drop', limpiar);
    };
  }, []);

  // Las funciones que viajan **con** el programa: el backend las necesita
  // para desplegar las llamadas. Mientras se edita una funcion, manda el
  // borrador (aun no guardado).
  const funcionesPayload = useMemo(() => {
    const mapa = {};
    for (const f of guardado.funciones) {
      mapa[f.id] = { id: f.id, nombre: f.nombre, bloques: f.bloques || [] };
    }
    if (editando && mapa[editando.id]) {
      mapa[editando.id] = {
        id: editando.id,
        nombre: editando.nombre,
        bloques: editando.bloques || [],
      };
    }
    return mapa;
  }, [guardado.funciones, editando]);

  // Cuanto va a durar el programa. Se lo pregunta al backend, que lo simula
  // (los brazos tardan lo que tarde el servo). Si el servidor no contesta se
  // usa una estimacion rapida, para no dejar el hueco vacio.
  useEffect(() => {
    if (!bloques.length) {
      setDuracion({ total: null, bloques: [], estimado: false });
      return undefined;
    }
    let cancelado = false;
    const temporizador = setTimeout(() => {
      obtenerDuracion({ nombre: nombrePrograma || 'Mi programa', bloques }, funcionesPayload)
        .then((resp) => {
          if (cancelado) return;
          setDuracion({
            total: resp.duracion,
            bloques: resp.bloques || [],
            estimado: false,
          });
        })
        .catch(() => {
          if (cancelado) return;
          setDuracion({
            total: estimarDuracion(bloques, guardado.funciones),
            bloques: [],
            estimado: true,
          });
        });
    }, 400);
    return () => {
      cancelado = true;
      clearTimeout(temporizador);
    };
  }, [bloques, funcionesPayload]);

  const conectado = estado?.conectado ?? false;
  // Si se habla con el robot a traves del puente del ESP32-S3, su URL. Se
  // enseña en la cabecera para saber de un vistazo por donde van las cosas.
  const puente = estado?.puente ?? null;

  // --- cambiar el programa (todo pasa por aqui, para que se pueda deshacer)

  const aplicar = (nuevo, continuo = false) => {
    if (editando) {
      setEditando({ ...editando, bloques: nuevo });
      return;
    }
    setHistorial((prev) => historialAplica(prev, nuevo, { continuo }));
  };

  // Al pulsar un bloque de la paleta, se añade al programa.
  const anadir = (tipo) => {
    aplicar([...bloques, bloqueNuevo(tipo)]);
    setMensaje('Bloque añadido. ¡Prueba el botón verde!');
  };

  // Un bloque nuevo, con sus valores por defecto (esta en bloques.js).
  const anadirDentro = (repetir, tipo) => {
    const hijo = bloqueNuevo(tipo);
    aplicar(
      insertarEnArbol(bloques, repetir.id, (repetir.bloques || []).length, hijo),
    );
  };

  const cambiar = (bloque, continuo = false) => {
    aplicar(
      bloques.map((b) => (b.id === bloque.id ? bloque : b)),
      continuo,
    );
  };

  const borrar = (id) => {
    // `quitarEnArbol` lo saca de donde este: de la raiz o de dentro de un
    // "repetir" (si esta dentro, el "repetir" se queda sin el).
    const nueva = quitarEnArbol(bloques, id);
    if (nueva === bloques) return;
    aplicar(nueva);
    setSeleccion(null);
    setRango([]);
  };

  const mover = (id, delta) => {
    const i = bloques.findIndex((b) => b.id === id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= bloques.length) return;
    const copia = [...bloques];
    [copia[i], copia[j]] = [copia[j], copia[i]];
    aplicar(copia);
  };

  // --- marcar bloques (para guardar un trozo como funcion)

  const seleccionar = (id, conShift) => {
    if (conShift && ancla) {
      const i = bloques.findIndex((b) => b.id === ancla);
      const j = bloques.findIndex((b) => b.id === id);
      if (i >= 0 && j >= 0) {
        const [a, b] = i < j ? [i, j] : [j, i];
        setRango(bloques.slice(a, b + 1).map((x) => x.id));
        setAncla(null);
        setSeleccion(id);
        return;
      }
    }
    setAncla(id);
    setSeleccion(id);
    setRango([id]);
  };

  const bloquesMarcados = useMemo(
    () => bloques.filter((b) => rango.includes(b.id)),
    [bloques, rango],
  );

  // --- arrastrar y soltar

  const soltar = (padreId, indice, datos) => {
    // Al soltar, se acaba el arrastre: las franjas donde se suelta se
    // esconden. (Ojo: el "dragend" no siempre llega, porque al mover un
    // bloque React redibuja el arbol y el nodo del que se arrastra deja de
    // estar en la pagina.)
    setArrastrando(null);
    if (datos.origen === ARRASTRE_PALETA) {
      const bloque = bloqueNuevo(datos.tipo);
      aplicar(insertarEnArbol(bloques, padreId, indice, bloque));
      setMensaje('Bloque soltado.');
      return;
    }
    if (datos.origen === ARRASTRE_FUNCION) {
      // Una funcion arrastrada al programa es una llamada (una referencia).
      const bloque = bloqueLlamada(datos.id);
      aplicar(insertarEnArbol(bloques, padreId, indice, bloque));
      setMensaje('Función añadida al programa.');
      return;
    }
    if (datos.origen === ARRASTRE_PROGRAMA) {
      const nuevo = moverBloque(bloques, datos.id, padreId, indice);
      if (nuevo !== bloques) aplicar(nuevo);
    }
  };

  // --- deshacer

  const deshacer = () => {
    if (editando) {
      setMensaje('Mientras editas una función no se puede deshacer.');
      return;
    }
    if (!historial.pasado.length) return;
    setHistorial((prev) => historialDeshace(prev));
    setMensaje('Deshecho.');
  };

  const cargarEjemplo = () => {
    aplicar(programaDeEjemplo());
    setIdPrograma(null);
    setNombrePrograma('');
    setMensaje('Este es un programa de ejemplo. ¡Prueba a darle a "Vamos"!');
  };

  const vaciar = () => {
    aplicar([]);
    setSeleccion(null);
    setRango([]);
    setIdPrograma(null);
    setMensaje('Programa vacío.');
  };

  // --- el robot

  const lanzar = async () => {
    if (!conectado) {
      setMensaje('El robot no está conectado. Conéctalo primero.');
      return;
    }
    if (!bloques.length) {
      setMensaje('El programa está vacío. ¡Añade algún bloque!');
      return;
    }
    try {
      setCorriendo(true);
      const resp = await ejecutarPrograma(
        { nombre: nombrePrograma || 'Mi programa', bloques },
        funcionesPayload,
      );
      if (resp && resp.ok === false) {
        setMensaje(resp.mensaje || 'No se pudo lanzar.');
        setCorriendo(false);
        return;
      }
      // Los programas NO se pisan: si hay alguno corriendo, este espera su
      // turno. El backend dice cuantos hay en la cola.
      const enCola = resp?.cola || 0;
      setMensaje(
        enCola > 0
          ? `¡Vamos! Este programa espera su turno (${enCola} en cola).`
          : '¡Vamos! Mira al robot.',
      );
      // el backend dice cuanto va a durar: antes se adivinaba con 1,5 s fijos
      const ms = Math.max(500, (resp?.duracion || 0) * 1000);
      setTimeout(() => setCorriendo(false), ms);
    } catch (e) {
      setMensaje(`No se pudo lanzar: ${e.message}`);
      setCorriendo(false);
    }
  };

  const detener = async () => {
    try {
      await parar();
      setCorriendo(false);
      setMensaje('Parado.');
    } catch (e) {
      setMensaje(`No se pudo parar: ${e.message}`);
    }
  };

  const alternarConexion = async () => {
    try {
      if (conectado) {
        await desconectar();
        setMensaje('Desconectado.');
      } else {
        await conectar();
        setMensaje('¡Conectado!');
      }
    } catch (e) {
      setMensaje(`No se pudo: ${e.message}`);
    }
  };

  // --- el teclado

  const moverSeleccion = (delta) => {
    if (!seleccion) return;
    const origen = localizarBloque(bloques, seleccion);
    if (!origen) return;
    const nuevo = moverBloque(bloques, seleccion, origen.padreId, origen.indice + delta);
    if (nuevo === bloques) return;
    if (editando) setEditando({ ...editando, bloques: nuevo });
    else setHistorial((prev) => historialAplica(prev, nuevo));
  };

  useEffect(() => {
    const alPulsar = (e) => {
      const ctrl = e.ctrlKey || e.metaKey;
      const enCampo =
        document.activeElement &&
        ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);

      if (ctrl && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault();
        deshacer();
        return;
      }
      if (ctrl && e.key === 'Enter') {
        e.preventDefault();
        lanzar();
        return;
      }
      if (e.key === 'Escape') {
        detener();
        return;
      }
      if (enCampo) return;
      if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        e.preventDefault();
        moverSeleccion(e.key === 'ArrowUp' ? -1 : 1);
        return;
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && seleccion) {
        e.preventDefault();
        borrar(seleccion);
      }
    };
    window.addEventListener('keydown', alPulsar);
    return () => window.removeEventListener('keydown', alPulsar);
  });

  // --- el guardado

  const guardarProgramaActual = async (comoNuevo) => {
    const nombre = (nombrePrograma || '').trim() || 'Mi programa';
    const id = comoNuevo ? '' : idPrograma || '';
    try {
      const resp = await guardarPrograma({ id, nombre, bloques });
      setGuardado((g) => ({
        ...g,
        programas: [...g.programas.filter((p) => p.id !== resp.id), resp],
      }));
      setIdPrograma(resp.id);
      setNombrePrograma(resp.nombre);
      setMensaje(`Programa «${resp.nombre}» guardado.`);
    } catch (e) {
      setMensaje(`No se pudo guardar: ${e.message}`);
    }
  };

  const cargarPrograma = (p) => {
    setEditando(null);
    setHistorial((prev) => historialAplica(prev, p.bloques || []));
    setIdPrograma(p.id);
    setNombrePrograma(p.nombre);
    setRango([]);
    setMensaje(`Programa «${p.nombre}» cargado.`);
  };

  const borrarProgramaGuardado = async (p) => {
    if (!window.confirm(`¿Borrar el programa «${p.nombre}»?`)) return;
    try {
      await borrarPrograma(p.id);
      setGuardado((g) => ({
        ...g,
        programas: g.programas.filter((x) => x.id !== p.id),
      }));
      if (idPrograma === p.id) setIdPrograma(null);
      setMensaje(`Programa «${p.nombre}» borrado.`);
    } catch (e) {
      setMensaje(`No se pudo borrar: ${e.message}`);
    }
  };

  const crearFuncion = async () => {
    if (!bloquesMarcados.length) return;
    const nombre = (nombreFuncion || '').trim() || 'Mi función';
    try {
      const resp = await guardarFuncion({ nombre, bloques: bloquesMarcados });
      setGuardado((g) => ({
        ...g,
        funciones: [...g.funciones.filter((f) => f.id !== resp.id), resp],
      }));
      setNombreFuncion('');
      setRango([]);
      setMensaje(`Función «${resp.nombre}» guardada. Ya puedes usarla.`);
    } catch (e) {
      setMensaje(`No se pudo guardar la función: ${e.message}`);
    }
  };

  const editarFuncion = (f) => {
    setEditando({
      id: f.id,
      nombre: f.nombre,
      bloques: JSON.parse(JSON.stringify(f.bloques || [])),
    });
    setRango([]);
    setMensaje(`Editando la función «${f.nombre}».`);
  };

  const guardarEdicion = async () => {
    if (!editando) return;
    try {
      const resp = await guardarFuncion({
        id: editando.id,
        nombre: editando.nombre,
        bloques: editando.bloques,
      });
      setGuardado((g) => ({
        ...g,
        funciones: g.funciones.map((f) => (f.id === resp.id ? resp : f)),
      }));
      setEditando(null);
      setMensaje(
        `Función «${resp.nombre}» guardada. Todos los programas que la usan cambian.`,
      );
    } catch (e) {
      setMensaje(`No se pudo guardar la función: ${e.message}`);
    }
  };

  const cancelarEdicion = () => {
    setEditando(null);
    setMensaje('Edición cancelada.');
  };

  const borrarFuncionGuardada = async (f) => {
    if (!window.confirm(`¿Borrar la función «${f.nombre}»?`)) return;
    try {
      await borrarFuncion(f.id);
      setGuardado((g) => ({
        ...g,
        funciones: g.funciones.filter((x) => x.id !== f.id),
      }));
      if (editando && editando.id === f.id) setEditando(null);
      setMensaje(`Función «${f.nombre}» borrada.`);
    } catch (e) {
      setMensaje(`No se pudo borrar: ${e.message}`);
    }
  };

  const usarFuncion = (f) => {
    aplicar([...bloques, bloqueLlamada(f.id)]);
    setMensaje(`Función «${f.nombre}» añadida al programa.`);
  };

  const resumen = useMemo(() => {
    if (!bloques.length) return 'El programa está vacío';
    return bloques
      .map((b, i) => `${i + 1}. ${resumenDeBloque(b, catalogo, guardado.funciones)}`)
      .join(' → ');
  }, [bloques, catalogo, guardado.funciones]);

  const textoDuracion = !bloques.length
    ? '—'
    : duracion.total === null
      ? 'calculando…'
      : `dura unos ${formatoDuracion(duracion.total)}`;

  return (
    <div
      className={`app ${arrastrando ? 'app-arrastrando' : ''}`}
      onDragEnd={() => setArrastrando(null)}
    >
      <header className="cabecera">
        <div className="cabecera-fila">
          <h1>
            <span className="logo">🤖</span> AIRO
          </h1>
          <div className={`estado ${conectado ? 'estado-ok' : 'estado-fallo'}`}>
            <span className="punto" />
            {conectado ? 'Robot conectado' : 'Robot sin conexión'}
          </div>
          {puente && (
            <div
              className="estado estado-puente"
              title={`El robot se controla a través del puente ${puente}`}
            >
              <span className="punto" />
              vía ESP32
            </div>
          )}
        </div>
        <div className="cabecera-fila cabecera-controles">
          <div className="modo-caja">
            <span className="modo-etiqueta">Modo</span>
            <div className="chips">
              <button
                className={`chip chip-oscuro ${modo === 'normal' ? 'chip-activo' : ''}`}
                onClick={() => setModo('normal')}
                title="Los bloques de siempre: mover el brazo entero a una pose"
              >
                normal
              </button>
              <button
                className={`chip chip-oscuro ${modo === 'avanzado' ? 'chip-activo' : ''}`}
                onClick={() => setModo('avanzado')}
                title="Además: elegir articulación (hombro o codo) y ángulo exacto"
              >
                avanzado
              </button>
            </div>
          </div>
          <button className="boton boton-suave" onClick={alternarConexion}>
            {conectado ? 'Desconectar' : 'Conectar'}
          </button>
        </div>
      </header>

      <main className="tablero">
        <section className="columna paleta">
          <h2>1 · Elige los bloques</h2>
          <p className="pista">Toca un bloque y se añade a tu programa (o arrástralo).</p>
          <div className="lista-bloques">
            {catalogo.map((info) => (
              <button
                key={info.tipo}
                className="bloque-paleta"
                style={{ background: info.color }}
                onClick={() => anadir(info.tipo)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = 'copyMove';
                  e.dataTransfer.setData(
                    'text/plain',
                    JSON.stringify({ origen: ARRASTRE_PALETA, tipo: info.tipo }),
                  );
                  setArrastrando({ origen: ARRASTRE_PALETA, tipo: info.tipo });
                }}
                title={info.descripcion}
              >
                <span className="bloque-icono">{info.icono}</span>
                <span className="bloque-paleta-titulo">{info.titulo}</span>
              </button>
            ))}
          </div>
          <p className="pista pista-modo">
            {modo === 'avanzado'
              ? 'Modo avanzado: en el bloque del brazo puedes elegir el tiempo (movimiento lento), qué articulación mover y el ángulo exacto.'
              : 'Modo normal: en el bloque del brazo eliges el lado y la pose. Puedes cambiar a "avanzado" arriba para mover solo el hombro o el codo.'}
          </p>
        </section>

        <section className="columna programa">
          <div className="programa-cabecera">
            <h2>{editando ? `Editando «${editando.nombre}»` : '2 · Tu programa'}</h2>
            <div className="programa-botones">
              {editando ? (
                <>
                  <button className="boton boton-chico boton-ok" onClick={guardarEdicion}>
                    💾 Guardar función
                  </button>
                  <button className="boton boton-chico" onClick={cancelarEdicion}>
                    Cancelar
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="boton boton-chico"
                    onClick={deshacer}
                    disabled={!historial.pasado.length}
                    title="Deshacer (Ctrl+Z)"
                  >
                    ↩ Deshacer
                  </button>
                  <button className="boton boton-chico" onClick={cargarEjemplo} title="Un programa de ejemplo">
                    💡 Ejemplo
                  </button>
                  <button
                    className="boton boton-chico"
                    onClick={vaciar}
                    disabled={!bloques.length}
                    title="Borrar todo el programa"
                  >
                    🗑 Vaciar
                  </button>
                </>
              )}
            </div>
          </div>
          {editando ? (
            <p className="pista pista-edicion">
              Estás editando una <strong>función</strong>. Lo que guardes aquí lo
              usan todos los programas que la llaman.
            </p>
          ) : (
            <p className="pista">
              El robot los hace en orden, de arriba abajo. Puedes arrastrarlos para
              cambiar el orden.
            </p>
          )}
          <div className="programa-lista">
            {bloques.length === 0 && (
              <div className="vacio">
                <span className="vacio-icono">🧩</span>
                <p>{editando ? 'Esta función está vacía.' : 'Aún no hay bloques.'}</p>
                <p className="pista">
                  {editando
                    ? 'Añade bloques para darle contenido.'
                    : 'Toca uno de la izquierda o pulsa "Ejemplo".'}
                </p>
              </div>
            )}
            {bloques.map((b, i) => (
              <React.Fragment key={b.id}>
                <ZonaSoltar padreId={null} indice={i} alSoltar={soltar} />
                <BloqueEditor
                  bloque={b}
                  catalogo={catalogo}
                  indice={i}
                  total={bloques.length}
                  alCambiar={cambiar}
                  alBorrar={() => borrar(b.id)}
                  alMover={(d) => mover(b.id, d)}
                  alAnadirDentro={anadirDentro}
                  alSoltar={soltar}
                  alEmpezarArrastre={setArrastrando}
                  duracion={duracion.bloques[i]}
                  seleccionado={rango.includes(b.id)}
                  alSeleccionar={seleccionar}
                  funciones={guardado.funciones}
                  modo={modo}
                />
              </React.Fragment>
            ))}
            {bloques.length > 0 && (
              <ZonaSoltar padreId={null} indice={bloques.length} alSoltar={soltar} />
            )}
          </div>

          {!editando && bloquesMarcados.length > 0 && (
            <div className="marcar-barra">
              <span className="marcar-texto">
                {bloquesMarcados.length} bloque
                {bloquesMarcados.length === 1 ? '' : 's'} marcado
                {bloquesMarcados.length === 1 ? '' : 's'}
              </span>
              <input
                className="caja-nombre"
                value={nombreFuncion}
                onChange={(e) => setNombreFuncion(e.target.value)}
                placeholder="Nombre de la función"
                aria-label="Nombre de la función"
              />
              <button className="boton boton-chico boton-ok" onClick={crearFuncion}>
                ⚡ Guardar como función
              </button>
              <button className="boton boton-chico" onClick={() => setRango([])}>
                Quitar
              </button>
            </div>
          )}

          <div className="programa-pie">
            <button className="boton boton-grande" onClick={lanzar} disabled={!conectado}>
              ▶ ¡Vamos!
            </button>
            <button className="boton boton-rojo" onClick={detener}>
              ■ Parar
            </button>
          </div>
          <div className="pie-info">
            <span className="duracion">⏱ {textoDuracion}</span>
            <span className="pista atajos">
              Atajos: <kbd>Ctrl</kbd>+<kbd>Enter</kbd> ejecutar · <kbd>Ctrl</kbd>+<kbd>Z</kbd>{' '}
              deshacer · <kbd>Esc</kbd> parar
            </span>
          </div>
          {(estado?.cola ?? 0) > 0 && (
            <div className="cola">
              ⏳ {estado.cola} programa{estado.cola === 1 ? '' : 's'} esperando
              turno
            </div>
          )}
        </section>

        <section className="columna lateral">
          <h2>3 · Mira al robot</h2>
          <Robot estado={estado} corriendo={corriendo} />
          <div className="resumen">
            <strong>Lo que va a hacer:</strong>
            <p>{resumen}</p>
          </div>
          <div className="avisos">{mensaje}</div>
        </section>

        <ColumnaGuardado
          guardado={guardado}
          nombrePrograma={nombrePrograma}
          alCambiarNombre={setNombrePrograma}
          alGuardar={() => guardarProgramaActual(false)}
          alGuardarComo={() => guardarProgramaActual(true)}
          alCargar={cargarPrograma}
          alBorrarPrograma={borrarProgramaGuardado}
          alUsar={usarFuncion}
          alEditar={editarFuncion}
          alBorrarFuncion={borrarFuncionGuardada}
          alEmpezarArrastre={setArrastrando}
        />
      </main>
    </div>
  );
}

// En el navegador se monta la app; en los tests (node) no, y asi el
// componente se puede renderizar a texto para comprobarlo.
if (typeof document !== 'undefined') {
  const raiz = createRoot(document.getElementById('root'));
  raiz.render(<App />);
}
