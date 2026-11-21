# AIRO

Control del robot **Clementoni AIRO** por Bluetooth Low Energy, con:

- 🐍 una **librería** (`airo_ble`) que habla el idioma del robot, sin dependencias raras,
- 🖥️ una **consola** de texto para trastear,
- 🎨 una **interfaz web** (React + FastAPI) para programar al robot en bloques, pensada para niños,
- 🥋 una **kata de karate**,
- 🧩 un **plugin de Scratch**.

El análisis del protocolo (qué significa cada byte) está en
[`GUIA-PROGRAMAR-AIRO.md`](GUIA-PROGRAMAR-AIRO.md).

---

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # la libreria
pip install -e ".[api]"     # + la API web (FastAPI)
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
python3 airo_console.py
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
python3 airo_server.py      # http://localhost:8765
```

La extensión (`airo_ble/scratch3_airo/airo.js`) se carga en TurboWarp como
"Custom Extension". Ver
[`airo_ble/scratch3_airo/README.md`](airo_ble/scratch3_airo/README.md).

## Estructura

```
airo/
├── airo_ble/            # LA LIBRERIA (todo lo instalable vive aqui)
│   ├── protocol.py      # el protocolo de 20 bytes
│   ├── client.py        # cliente BLE
│   ├── session.py       # conexión + ejecución de programas
│   ├── console.py       # la consola
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
├── airo_console.py      # atajo a la consola
├── airo_server.py       # atajo al servidor de Scratch
├── tests/               # tests del protocolo, la consola y el servidor
├── analisis/            # scripts del desensamblado del APK
├── example/             # ejemplos sueltos
├── GUIA-PROGRAMAR-AIRO.md
└── PLAN-MEJORAS.md
```

Todo lo que se instala (`pip install .`) está dentro de `airo_ble/`, así que
no se cuela ningún módulo suelto en `site-packages`. La calibración que
guardes con `calib guardar` va a
`~/.config/airo-ble/calibration.json` (la que viene con el paquete es solo
el valor por defecto).

### Qué no está en el repo

- `web/dist/`: la build de Vite. Se regenera con `npm run build`.
- `evidencia/`: el desensamblado y las capturas. Material de trabajo; lo que
  prueba cada byte está en [`GUIA-PROGRAMAR-AIRO.md`](GUIA-PROGRAMAR-AIRO.md).
- `analisis/*.txt` y `analisis/*.tsv`: los volcados generados del APK
  (~19 MB). Los scripts que los producen sí están.
- Entornos virtuales, `node_modules/` y caches de herramientas.

## Tests

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

```bash
pip install pre-commit
pre-commit install            # se ejecuta antes de cada commit
pre-commit run --all-files    # o sobre todo el repo
```

Los hooks revisan formato, sintaxis (ruff), ficheros grandes, conflictos de
merge y **secretos** (gitleaks). La CI de GitHub Actions corre lo mismo:
`pytest`, `npm test` y `pre-commit` en cada push y en cada PR.

Paraplica, mira [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Cosas que conviene saber

- El módulo BLE del robot **se duerme**: si lleva un rato sin conexión hay que
  apagarlo y encenderlo.
- El firmware **devuelve los brazos a su reposo** si dejas de mandar
  paquetes, así que la librería refresca sola.
- Las ruedas del robot están **cruzadas** respecto a la app oficial (ver la
  guía): la API habla en términos físicos, no te preocupes. Los **brazos no**
  están cruzados: ahí la app y el robot coinciden.
