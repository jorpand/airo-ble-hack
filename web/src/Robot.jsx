import React from 'react';
import { anguloDeEstado, rotacionCodo, rotacionHombro } from './angulos.js';

// El robot dibujado con CSS: se mueve solo con el estado que llega del servidor.
export default function Robot({ estado, corriendo }) {
  const luz = estado?.luz ?? 'off';

  // El estado trae los cuatro angulos del servo (hombro y codo de cada lado).
  // Los angulos se sacan con el mapeo de `angulos.js`, que es el espejo de
  // `airo_ble/protocol.py`: cada articulacion tiene su signo y sus limites.
  const hombroDer = anguloDeEstado(estado, 'right_shoulder');
  const codoDer = anguloDeEstado(estado, 'right_arm');
  const hombroIzq = anguloDeEstado(estado, 'left_shoulder');
  const codoIzq = anguloDeEstado(estado, 'left_arm');

  const moviendo = estado?.accion === 'moviendo' || corriendo;
  const girandoIzq = moviendo && (estado?.ruedas?.izquierda ?? 0) > 0 && (estado?.ruedas?.derecha ?? 0) < 0;
  const girandoDer = moviendo && (estado?.ruedas?.izquierda ?? 0) < 0 && (estado?.ruedas?.derecha ?? 0) > 0;

  return (
    <div className={`robot ${moviendo ? 'robot-moviendo' : ''}`}>
      <div className="robot-escena">
        <div className={`robot-cuerpo ${girandoIzq ? 'robot-gira-izq' : ''} ${girandoDer ? 'robot-gira-der' : ''}`}>
          <div className={`robot-luz robot-luz-${luz}`} />
          <div className="robot-cara">
            <div className="robot-ojo robot-ojo-izq" />
            <div className="robot-ojo robot-ojo-der" />
            <div className="robot-boca" />
          </div>
          <div
            className="robot-brazo robot-brazo-der"
            style={{ transform: `rotate(${rotacionHombro('right_shoulder', hombroDer)}deg)` }}
          >
            <div
              className="robot-antebrazo"
              style={{ transform: `translateX(-50%) rotate(${rotacionCodo('right_arm', codoDer)}deg)` }}
            />
          </div>
          <div
            className="robot-brazo robot-brazo-izq"
            style={{ transform: `rotate(${rotacionHombro('left_shoulder', hombroIzq)}deg)` }}
          >
            <div
              className="robot-antebrazo"
              style={{ transform: `translateX(-50%) rotate(${rotacionCodo('left_arm', codoIzq)}deg)` }}
            />
          </div>
          <div className="robot-pie robot-pie-izq" />
          <div className="robot-pie robot-pie-der" />
        </div>
        <div className="robot-sombra" />
      </div>
    </div>
  );
}
