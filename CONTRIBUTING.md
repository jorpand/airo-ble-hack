# Cómo colaborar en airo-ble

Cliente BLE del robot **Clementoni AIRO** en Python, con interfaz web en
React y un plugin de Scratch. Todo el detalle del protocolo está en
[`docs/protocolo.md`](docs/protocolo.md).

## Puesta en marcha

```bash
make install     # crea el venv, instala la libreria + la API + los tests
```

O a mano:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd web && npm ci
```

La interfaz web se compila aparte (la build no se versiona):

```bash
make web         # = cd web && npm ci && npm run build
```

## Antes de abrir un PR

```bash
make test        # pytest + vitest
make lint        # ruff + los hooks de pre-commit
```

| Qué | Cuántos |
|---|---|
| `pytest` | 196 tests de Python |
| `npm test` | 95 tests de la interfaz |

Ojo: `pre-commit` **no** deja hacer commit directamente en `main` (hook
`no-commit-to-branch`). Trabaja en una rama y abre un PR.

## Dónde está cada cosa

| Ruta | Qué es |
|---|---|
| `airo_ble/` | la libreria instalable (`pip install .`) |
| `airo_ble/protocol.py` | **la fuente de la verdad** del protocolo |
| `airo_ble/api/` | backend FastAPI: traduce bloques a pasos y mueve el robot |
| `airo_ble/commands.py` | la CLI de una vez (`airo scan`, `airo drive`…) |
| `airo_ble/console.py` | la consola interactiva (`airo-console`) |
| `airo_ble/scratch3_airo/` | la extensión de Scratch (TurboWarp) |
| `web/src/` | la interfaz React (Vite) |
| `web/src/servos.js` | **generado**: no se edita a mano |
| `tests/` | los tests de Python |
| `docs/protocolo.md` | la guía del protocolo |
| `docs/desensamblado/` | los `.asm` que prueban cada byte |
| `tools/gen_servos.py` | genera `web/src/servos.js` |
| `tools/rev/` | scripts del reversing del APK |
| `tools/hardware/` | scripts de medición con el robot |

## La fuente de la verdad

`airo_ble/protocol.py` tiene los números del protocolo (el byte de cada servo,
su signo, sus límites, el escalado de 8,5 grados). La web los necesita
también, así que **se generan**:

```bash
make web-gen      # regenera web/src/servos.js
```

Si tocas `protocol.py` y no regeneras, `tests/test_web_angulos.py` falla. No
edites `web/src/servos.js` a mano: se sobrescribe.

## Lo que **no** se versiona

Está todo en el `.gitignore`, pero por si acaso:

- `.venv*`, `node_modules/`, `__pycache__/`, caches de pytest/ruff/vite.
- `web/dist/`: es la build de Vite. Se regenera con `make web`.
- `tools/rev/*.txt` y `*.tsv`: los volcados generados (~19 MB). Los scripts
  que los producen sí están.
- `evidencia/`: las capturas y el material de trabajo del reversing. El
  desensamblado que sí se publica está en `docs/desensamblado/`.

## Reglas de estilo

- Comentarios y documentación **en español**, igual que el resto del repo.
- Nada de reformateo masivo: el estilo actual es el que hay.
- `ruff` solo comprueba errores que rompen el código (sintaxis, nombres
  indefinidos). No se usa como formateador.
- Si tocas el protocolo, actualiza la guía y añade el test que lo demuestra.

## Reportar un problema

Abre una issue con: versión de Python, sistema operativo, qué comando
ejecutaste y la salida completa (con `--dry-run` si el robot molesta).
