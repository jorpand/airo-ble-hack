/**
 * Extension de Scratch 3 para el robot Clementoni AIRO.
 *
 * Los bloques no hablan BLE (el navegador no puede): llaman a un servidor
 * local en Python (`airo_server.py`) que se encarga.
 *
 * Como cargarlo en TurboWarp:
 *   Editar -> Custom Extension -> Extension URL (o pegar este fichero).
 *
 *   python3 airo_server.py        ->  http://localhost:8765
 */

// Puertos donde puede estar el puente. El 8765 es el de por defecto, pero en
// esta maquina lo ocupa `mantra-ble`, asi que se prueban varios y se usa el
// primero que conteste CON NUESTRO estado (otro programa puede contestar un
// 200 en /api/status sin ser el nuestro).
const API_PORTS = [8765, 8766, 8767, 8768];

let apiBase = null;

/** Devuelve la base del puente (http://localhost:PUERTO) o null. */
async function puente() {
    if (apiBase) return apiBase;
    for (const puerto of API_PORTS) {
        const base = `http://localhost:${puerto}`;
        try {
            const resp = await fetch(`${base}/api/status`);
            if (!resp.ok) continue;
            const datos = await resp.json();
            // tiene que ser NUESTRO servidor: el estado del AIRO trae los
            // brazos y las velocidades de las ruedas.
            if (datos && datos.brazos && datos.izquierda !== undefined) {
                apiBase = base;
                return apiBase;
            }
        } catch (e) {
            // este puerto no contesta: se prueba el siguiente
        }
    }
    return null;
}

class AIRO extends Scratch3Extension {
    constructor() {
        super('AIRO');
        this.info = this.getInfo();
    }

    getInfo() {
        return {
            id: 'airo',
            name: 'AIRO',
            color1: '#ff6680',
            color2: '#ff4d6d',
            color3: '#ff3355',
            blocks: [
                // --- movimiento ---
                {
                    opcode: 'moveForward',
                    blockType: CommandBlock,
                    text: 'mover el AIRO hacia delante con velocidad [SPEED]',
                    arguments: {
                        SPEED: {type: ArgumentType.NUMBER, defaultValue: 1}
                    }
                },
                {
                    opcode: 'moveBackward',
                    blockType: CommandBlock,
                    text: 'mover el AIRO hacia atras con velocidad [SPEED]',
                    arguments: {
                        SPEED: {type: ArgumentType.NUMBER, defaultValue: 1}
                    }
                },
                {
                    opcode: 'turnLeft',
                    blockType: CommandBlock,
                    text: 'girar el AIRO a la izquierda con velocidad [SPEED]',
                    arguments: {
                        SPEED: {type: ArgumentType.NUMBER, defaultValue: 1}
                    }
                },
                {
                    opcode: 'turnRight',
                    blockType: CommandBlock,
                    text: 'girar el AIRO a la derecha con velocidad [SPEED]',
                    arguments: {
                        SPEED: {type: ArgumentType.NUMBER, defaultValue: 1}
                    }
                },
                {
                    opcode: 'stop',
                    blockType: CommandBlock,
                    text: 'parar el AIRO'
                },
                {
                    opcode: 'wait',
                    blockType: CommandBlock,
                    text: 'esperar [SECONDS] segundos',
                    arguments: {
                        SECONDS: {type: ArgumentType.NUMBER, defaultValue: 1}
                    }
                },

                // --- luz ---
                {
                    opcode: 'setLed',
                    blockType: CommandBlock,
                    text: 'poner la luz del AIRO en [MODE]',
                    arguments: {
                        MODE: {type: ArgumentType.STRING, menu: 'ledMode', defaultValue: 'on'}
                    }
                },

                // --- brazos ---
                {
                    opcode: 'setArm',
                    blockType: CommandBlock,
                    text: 'poner el brazo [SIDE] en posicion [POSE]',
                    arguments: {
                        SIDE: {type: ArgumentType.STRING, menu: 'armSide', defaultValue: 'izquierdo'},
                        POSE: {type: ArgumentType.STRING, menu: 'armPose', defaultValue: 'arriba'}
                    }
                },
                {
                    opcode: 'setArmJoint',
                    blockType: CommandBlock,
                    text: 'poner el [JOINT] del brazo [SIDE] a [ANGLE] grados (en [SECS] segundos)',
                    arguments: {
                        JOINT: {type: ArgumentType.STRING, menu: 'armJoint', defaultValue: 'hombro'},
                        SIDE: {type: ArgumentType.STRING, menu: 'armSide', defaultValue: 'izquierdo'},
                        ANGLE: {type: ArgumentType.NUMBER, defaultValue: 0},
                        SECS: {type: ArgumentType.NUMBER, defaultValue: 0}
                    }
                },
                {
                    opcode: 'setJoint',
                    blockType: CommandBlock,
                    text: 'mover la articulacion [JOINT] a [ANGLE] grados',
                    arguments: {
                        JOINT: {type: ArgumentType.STRING, menu: 'joints', defaultValue: 'left_arm'},
                        ANGLE: {type: ArgumentType.NUMBER, defaultValue: 0}
                    }
                },
                {
                    opcode: 'kata',
                    blockType: CommandBlock,
                    text: 'hacer una kata de karate'
                },
                {
                    opcode: 'reset',
                    blockType: CommandBlock,
                    text: 'resetear el AIRO (brazos al reposo y parar)'
                },

                // --- estado ---
                {
                    opcode: 'status',
                    blockType: ReporterBlock,
                    text: 'estado del AIRO'
                },
                {
                    opcode: 'isConnected',
                    blockType: BooleanBlock,
                    text: '¿el AIRO esta conectado?'
                }
            ],
            menus: {
                ledMode: ['on', 'off', 'flash', 'fade'],
                armSide: ['izquierdo', 'derecho'],
                armPose: ['arriba', 'abajo', 'medio', 'golpe', 'guardia'],
                armJoint: ['hombro', 'codo'],
                joints: ['left_shoulder', 'left_arm', 'right_shoulder', 'right_arm']
            }
        };
    }

    // --- utilidades ---

    async send(cmd) {
        const base = await puente();
        if (!base) {
            console.warn(
                '[AIRO] no se pudo contactar con el servidor local. ' +
                '¿Esta arrancado "python3 airo_server.py"?'
            );
            return {ok: false, error: 'sin servidor local'};
        }
        try {
            const resp = await fetch(base + '/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(cmd)
            });
            const data = await resp.json();
            if (!data.ok) {
                console.warn('[AIRO]', data.error);
            }
            return data;
        } catch (err) {
            console.warn(
                '[AIRO] no se pudo contactar con el servidor local. ' +
                '¿Esta arrancado "python3 airo_server.py"?',
                err
            );
            return {ok: false, error: String(err)};
        }
    }

    async getStatus() {
        const base = await puente();
        if (!base) return {conectado: false, error: 'sin servidor local'};
        try {
            const resp = await fetch(base + '/api/status');
            return await resp.json();
        } catch (err) {
            return {conectado: false, error: String(err)};
        }
    }

    // --- bloques ---

    moveForward(speed) {
        this.send({type: 'move', left: speed, right: speed});
    }

    moveBackward(speed) {
        this.send({type: 'move', left: -speed, right: -speed});
    }

    turnLeft(speed) {
        this.send({type: 'move', left: speed, right: -speed});
    }

    turnRight(speed) {
        this.send({type: 'move', left: -speed, right: speed});
    }

    stop() {
        this.send({type: 'stop'});
    }

    wait(seconds) {
        return new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }

    setLed(mode) {
        this.send({type: 'led', mode: mode});
    }

    setArm(side, pose) {
        this.send({type: 'arm', side: side, pose: pose});
    }

    // Mueve una articulacion del brazo a un angulo exacto. Con "secs" a 0
    // va de golpe; con un tiempo, el movimiento es lento (el destino va
    // viajando hasta el servo).
    setArmJoint(side, joint, angle, secs) {
        this.send({
            type: 'arm',
            side: side,
            joint: joint,
            angle: angle,
            duration: secs > 0 ? secs : 0
        });
    }

    setJoint(joint, angle) {
        this.send({type: 'pose', joint: joint, angle: angle});
    }

    kata() {
        this.send({type: 'kata'});
    }

    reset() {
        this.send({type: 'reset'});
    }

    async status() {
        const data = await this.getStatus();
        return data.conectado
            ? 'conectado | luz: ' + data.led + ' | ruedas: ' + data.izquierda + '/' + data.derecha
            : 'sin conexion';
    }

    async isConnected() {
        const data = await this.getStatus();
        return Boolean(data.conectado);
    }
}

Scratch.vm.registerExtension(new AIRO());
