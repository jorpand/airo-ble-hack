# AIRO

Control del robot **Clementoni AIRO** por Bluetooth Low Energy, con:

- 🐍 una **librería** (`airo_ble`) que habla el idioma del robot, sin dependencias raras,
- 🖥️ una **consola** de texto para trastear,
- 🎨 una **interfaz web** (React + FastAPI) para programar al robot en bloques, pensada para niños,
- 🥋 una **kata de karate**,
- 🧩 un **plugin de Scratch**.

El análisis del protocolo (qué significa cada byte) está en
[`docs/protocolo.md`](docs/protocolo.md).

---

## Instalación

El entorno de desarrollo lo pone **[mise](https://mise.jdx.dev)**: las
versiones de Python y Node, el venv y los comandos, todo en `mise.toml`.

```bash
mise install      # descarga Python 3.14 y Node 22
mise run setup    # crea el venv e instala el proyecto
```

A partir de ahi, todo con `mise run ...` (ver [Desarrollo](#desarrollo)).

Sin mise, a mano:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

En Linux hace falta soporte de BlueZ: `sudo apt install python3-bleak bluez`.

## La librería (importable desde cualquier proyecto)

```python
import asyncio
from airo_ble import AiroRobot, Joint, Led

async def main():
    async with AiroRobot() as robot:          # busca el robot 'AIRo'
        await robot.drive(left=1.0, right=1.0)
        await asyncio.sleep(2)
        await robot.servo(Joint.RIGHT_SHOULDER, 30)
        await robot.led(Led.FLASH)
        await robot.stop()

asyncio.run(main())
```

O con la sesión (que mantiene la conexión y refresca el paquete, que hace
falta para que los brazos no se bajen solos):

```python
from airo_ble.session import RobotSession

sesion = RobotSession()
await sesion.conectar()
await sesion.mover(izquierda=2, derecha=2, segundos=2)
await sesion.desconectar()
```

`airo_ble` **no depende de nada de web**: se puede instalar en un script, en
otro proyecto o en un servidor sin llevar la interfaz encima.

## La consola

```bash
python3 -m airo_ble.console
```

```
airo> ayuda                 # la lista de comandos
airo> avanzar 2             # las ruedas
airo> izquierda 1          # girar
airo> led flash            # la luz azul
airo> brazo izq arriba     # los brazos (sin angulos ni bytes)
airo> kata                 # la coreografia de karate
airo> calib                # calibrar (ver la guia)
airo> historial            # historial con flechas arriba/abajo
```

## La interfaz web (para niños)

```bash
python3 -m uvicorn airo_ble.api.main:app --port 8100
# y la interfaz compilada (la build no se versiona, hay que generarla):
cd web && npm ci && npm run build
```

La API sirve la interfaz desde `web/dist`, así que **hay que compilar la web
antes de abrir el backend**: si `web/dist` no existe, la API funciona pero no
muestra la interfaz.

Abre <http://localhost:8100> y verás tres columnas:

1. **Elige los bloques** — toca uno y se añade a tu programa.
2. **Tu programa** — orden, opciones ("poquito / normal / mucho", "un
   instante / un segundo / dos segundos…") y un **¡Vamos!** enorme.
3. **Mira al robot** — un robot dibujado que se mueve con el estado real.

Sin grados, sin bytes y sin palabras raras: solo "avanza", "gira a la
izquierda", "levanta el brazo", "un segundo".

En la cabecera hay dos modos:

- **normal**: lo de siempre (lado y pose del brazo).
- **avanzado**: además, el **tiempo** del movimiento (de golpe o lento en
  rampa durante X segundos), **qué articulación** mover (hombro, codo o las
  dos) y el **ángulo exacto** de destino.

Los programas se ejecutan uno detrás de otro (cola FIFO): pulsar "¡Vamos!"
dos veces no pisa el primero, y cada movimiento termina parando.

Y además:

- **Arrastrar y soltar**: los bloques se arrastran desde la paleta al
  programa (también dentro de un "repetir") y se reordenan con el asa ⠿.
- **Deshacer** (botón o <kbd>Ctrl</kbd>+<kbd>Z</kbd>) y **Vaciar**.
- **Ejemplo**: un botón que carga un programa que funciona a la primera.
- **Duración estimada**: cuánto va a durar el programa (y cada bloque) antes
  de darle a "¡Vamos!".
- **Atajos**: <kbd>Ctrl</kbd>+<kbd>Enter</kbd> ejecutar, <kbd>Esc</kbd> parar,
  <kbd>Alt</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd> mover el bloque seleccionado.

### Guardar programas y funciones

La cuarta columna ("4 · Guardado") guarda todo en el **servidor**, en
`~/.airo/guardado.json` (se cambia con `AIRO_GUARDADO`):

- **Programas**: el programa entero con su nombre ("Guardar" lo actualiza,
  "Guardar como" crea una copia).
- **Funciones**: un trozo de bloques con nombre. Se marcan en el programa
  (clic, y clic+Mayúsculas para varios), se guardan con un nombre y se
  arrastran al programa para usarlas.

Las llamadas son **referencias**: si editas una función, todos los programas
que la usan cambian. El backend las despliega al ejecutar (y corta el bucle
infinito si una función se llama a sí misma).

El API de esto:

| Ruta | Que hace |
|---|---|
| `GET /api/guardado` | lo guardado (programas y funciones) |
| `POST /api/guardado/programa` | guarda o actualiza un programa |
| `DELETE /api/guardado/programa/{id}` | borra un programa |
| `POST /api/guardado/funcion` | guarda o actualiza una función |
| `DELETE /api/guardado/funcion/{id}` | borra una función |

## Plugin de Scratch

```bash
python3 -m airo_ble.server      # http://localhost:8765
```

La extensión (`airo_ble/scratch3_airo/airo.js`) se carga en TurboWarp como
"Custom Extension". Ver
[`airo_ble/scratch3_airo/README.md`](airo_ble/scratch3_airo/README.md).

## Estructura

```
airo/
├── airo_ble/            # LA LIBRERIA (todo lo instalable vive aqui)
│   ├── protocol.py      # el protocolo de 20 bytes (LA fuente de la verdad)
│   ├── client.py        # cliente BLE
│   ├── session.py       # conexión + ejecución de programas
│   ├── console.py       # la consola interactiva
│   ├── commands.py      # la CLI de una vez (scan, drive, pose, led)
│   ├── arms.py          # las poses de los brazos y qué lado se mueve
│   ├── server.py        # servidor para el plugin de Scratch
│   ├── api/             # backend FastAPI + Pydantic
│   │   ├── models.py    # los bloques (en lenguaje de niño)
│   │   ├── service.py   # traducción bloque -> pasos
│   │   └── main.py      # la aplicación
│   ├── scratch3_airo/   # extensión de Scratch + página de pruebas
│   └── calibration.json # calibración por defecto de los brazos
├── web/                 # interfaz React (Vite)
│   └── src/             # el código de la interfaz
├── tests/               # tests del protocolo, la consola y el servidor
├── docs/
│   ├── protocolo.md     # la guia del protocolo (qué significa cada byte)
│   ├── plan-mejoras.md  # el log de trabajo (histórico)
│   └── desensamblado/   # los .asm que prueban cada byte
├── tools/
│   ├── gen_servos.py    # genera web/src/servos.js desde protocol.py
│   ├── rev/             # scripts de ingeniería inversa
│   └── hardware/        # scripts de medición con el robot
├── mise.toml            # el entorno local: versiones, venv y tareas
└── pyproject.toml       # las dependencias, los scripts y la config de ruff/pyright
```

Todo lo que se instala (`pip install .`) está dentro de `airo_ble/`, así que
no se cuela ningún módulo suelto en `site-packages`. La calibración que
guardes con `calib guardar` va a
`~/.config/airo-ble/calibration.json` (la que viene con el paquete es solo
el valor por defecto).

### Una sola fuente de la verdad

Los números del protocolo (el byte de cada servo, su signo, sus límites y el
escalado de 8,5 grados) están **una sola vez**, en `airo_ble/protocol.py`.
De ahí se genera `web/src/servos.js` con `tools/gen_servos.py`, así que la
web y la librería no pueden desincronizarse. El test
`tests/test_web_angulos.py` lo comprueba byte a byte.

Antes los dos estaban escritos a mano y se separaron: la web usaba una
fórmula fija que se equivocaba en hasta 230 grados en los codos.

### Qué no está en el repo

- `web/dist/`: la build de Vite. Se regenera con `mise run web`.
- `tools/rev/*.txt` y `tools/rev/*.tsv`: los volcados generados del APK
  (~19 MB). Los scripts que los producen sí están.
- `evidencia/`: la carpeta de trabajo local, donde se capturan las pruebas.
  Lo que **sí** se publica está en [`docs/desensamblado/`](docs/desensamblado/).
- Entornos virtuales, `node_modules/` y caches de herramientas.

## Tests

```bash
mise run test            # pytest + vitest
```

O por separado:

```bash
pytest -q                # toda la suite de Python
cd web && npm test       # los tests de la interfaz
```

O uno a uno:

```bash
python3 tests/test_protocol.py   # 24 tests del protocolo
python3 tests/test_client.py     # cliente con un BLE simulado
python3 tests/test_console.py    # 10 tests de la consola
python3 tests/test_server.py     # el servidor
```

## Desarrollo

Todo el ciclo local pasa por **mise**. `mise tasks` lista las tareas:

| Comando | Qué hace |
|---|---|
| `mise run setup` | crea el venv e instala la librería con los extras de desarrollo |
| `mise run test` | `pytest` + `vitest` |
| `mise run test-py` / `test-web` | solo una de las dos suites |
| `mise run types` | comprueba los tipos con **pyright** |
| `mise run lint` | `ruff` + los hooks de pre-commit |
| `mise run fix` | solo ruff, que **arregla** lo que puede |
| `mise run web` | compila la interfaz (`npm ci` + `npm run build`) |
| `mise run web-dev` | arranca Vite en el 5173 (para tocar la interfaz) |
| `mise run web-gen` | regenera `web/src/servos.js` desde `protocol.py` |
| `mise run run` | arranca la API web en el 8100 |
| `mise run console` | la consola interactiva |
| `mise run scratch` | el puente para el plugin de Scratch |
| `mise run clean` | borra las caches y la build |

Las versiones (Python 3.14, Node 22) están en `mise.toml`, y **la CI usa el
mismo fichero**: no puede haber una diferencia entre lo que se prueba aquí y
lo que se prueba allí.

### Los tipos

El paquete viene con `py.typed` y se comprueba con
[pyright](https://github.com/microsoft/pyright) en modo `standard`, con
avisos de deprecaciones:

```bash
mise run types
```

La configuración está en `[tool.pyright]` de `pyproject.toml`.

### Los hooks

```bash
mise run setup            # instala pre-commit
pre-commit install        # se ejecuta antes de cada commit
```

Revisan formato, sintaxis (**ruff**), **tipos** (pyright), ficheros grandes,
conflictos de merge y **secretos** (gitleaks).

Ruff no solo avisa: **arregla**. Deja los imports ordenados, quita lo que no
se usa y moderniza la sintaxis (las reglas están en `[tool.ruff.lint]` de
`pyproject.toml`). Si un hook toca ficheros, el commit se para: los vuelves
a anadir (`git add -u`) y ya está.

Para colaborar, mira [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Cosas que conviene saber

- El módulo BLE del robot **se duerme**: si lleva un rato sin conexión hay que
  apagarlo y encenderlo.
- El firmware **devuelve los brazos a su reposo** si dejas de mandar
  paquetes, así que la librería refresca sola.
- Las ruedas del robot están **cruzadas** respecto a la app oficial (ver la
  guía): la API habla en términos físicos, no te preocupes. Los **brazos no**
  están cruzados: ahí la app y el robot coinciden.
