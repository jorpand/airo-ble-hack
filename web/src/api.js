// Cliente de la API del robot.

const BASE = '';

async function pedir(url, opciones = {}) {
  const resp = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...opciones,
  });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export function obtenerEstado() {
  return pedir('/api/estado');
}

export function obtenerBloques() {
  return pedir('/api/bloques');
}

export function ejecutarPrograma(programa, funciones = {}) {
  return pedir('/api/programa', {
    method: 'POST',
    body: JSON.stringify({ programa, funciones }),
  });
}

export function ejecutarBloque(bloque) {
  return pedir('/api/bloque', {
    method: 'POST',
    body: JSON.stringify({ bloque }),
  });
}

// Cuanto va a durar el programa, sin ejecutarlo. El backend simula el
// programa y dice la verdad (los brazos tardan lo que tarde el servo).
export function obtenerDuracion(programa, funciones = {}) {
  return pedir('/api/duracion', {
    method: 'POST',
    body: JSON.stringify({ programa, funciones }),
  });
}

// --- el guardado (los programas y las funciones) ---------------------------

export function obtenerGuardado() {
  return pedir('/api/guardado');
}

export function guardarPrograma(programa) {
  return pedir('/api/guardado/programa', {
    method: 'POST',
    body: JSON.stringify(programa),
  });
}

export function borrarPrograma(id) {
  return pedir(`/api/guardado/programa/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export function guardarFuncion(funcion) {
  return pedir('/api/guardado/funcion', {
    method: 'POST',
    body: JSON.stringify(funcion),
  });
}

export function borrarFuncion(id) {
  return pedir(`/api/guardado/funcion/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export function parar() {
  return pedir('/api/parar', { method: 'POST' });
}

export function conectar() {
  return pedir('/api/conectar', { method: 'POST' });
}

export function desconectar() {
  return pedir('/api/desconectar', { method: 'POST' });
}

// Websocket con el estado en vivo (reintenta solo si se cae).
export function suscribirEstado(alRecibir, alCaer) {
  let ws = null;
  let cerrado = false;
  let reintento = null;

  const abrir = () => {
    if (cerrado) return;
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        alRecibir(JSON.parse(ev.data));
      } catch (e) {
        // mensaje raro: lo ignoramos
      }
    };
    ws.onclose = () => {
      if (cerrado) return;
      if (alCaer) alCaer();
      reintento = setTimeout(abrir, 2000);
    };
    ws.onerror = () => ws.close();
  };

  abrir();

  return () => {
    cerrado = true;
    if (reintento) clearTimeout(reintento);
    if (ws) ws.close();
  };
}
