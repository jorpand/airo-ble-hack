# Cómo colaborar en airo-ble

Cliente BLE del robot **Clementoni AIRO** en Python, con interfaz web en
React y un plugin de Scratch. Todo el detalle del protocolo está en
[`docs/protocolo.md`](docs/protocolo.md).

## Puesta en marcha

El entorno lo pone [mise](https://mise.jdx.dev): las versiones (Python 3.14
y Node 22), el venv y los comandos, todo en `mise.toml`.

```bash
mise install     # descarga Python 3.14 y Node 22
mise run setup   # crea el venv, instala la libreria + la API + los tests
```

Sin mise, a mano:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd web && npm ci
```

La interfaz web se compila aparte (la build no se versiona):

```bash
mise run web     # = cd web && npm ci && npm run build
```

## Antes de abrir un PR

```bash
mise run test    # pytest + vitest
mise run lint    # ruff + los hooks de pre-commit
mise run types   # pyright
mise run fix     # ruff arreglando lo que puede
```

| Qué | Cuántos |
|---|---|
| `pytest` | 196 tests de Python |
| `npm test` | 95 tests de la interfaz |
| `pyright` | 0 errores (modo `standard`) |

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
mise run web-gen   # regenera web/src/servos.js
```

Si tocas `protocol.py` y no regeneras, `tests/test_web_angulos.py` falla. No
edites `web/src/servos.js` a mano: se sobrescribe.

## Lo que **no** se versiona

Está todo en el `.gitignore`, pero por si acaso:

- `.venv*`, `node_modules/`, `__pycache__/`, caches de pytest/ruff/vite.
- `web/dist/`: es la build de Vite. Se regenera con `mise run web`.
- `tools/rev/*.txt` y `*.tsv`: los volcados generados (~19 MB). Los scripts
  que los producen sí están.
- `evidencia/`: las capturas y el material de trabajo del reversing. El
  desensamblado que sí se publica está en `docs/desensamblado/`.

## Los tipos

El paquete lleva `py.typed` y se comprueba con **pyright** en modo
`standard` (configuración en `[tool.pyright]` de `pyproject.toml`):

```bash
mise run types
```

Los hooks de pre-commit tambien lo comprueban, asi que un error de tipos
salta antes del commit. Si pyright se queja de algo que no puedes cambiar
(una libreria de terceros sin stubs), se desactiva **en esa linea**, con un
comentario que explique por que.

## Reglas de estilo

- Comentarios y documentación **en español**, igual que el resto del repo.
- **Ruff arregla, no solo avisa.** Las reglas están en `[tool.ruff.lint]`
  (`E`, `F`, `W`, `I`, `UP`, `B`, `C4`): imports ordenados, nada de imports
  sin usar, sintaxis moderna para Python 3.11+ y los bugs que no son de
  sintaxis. `ruff check` las aplica solo, así que casi nunca hay que
  escribir nada a mano.
- No hay formateador de estilo (nada de black): ruff **no** reordena el
  código ni toca los comentarios. El estilo del repo es el que hay.
- Si tocas el protocolo, actualiza la guía y añade el test que lo demuestra.

### Cuando ruff y pyright se contradicen

Ruff y pyright a veces piden cosas incompatibles (por ejemplo, ruff quiere
`setattr(x, "a", v)` y pyright no deja asignar atributos a un `ModuleType`).
Cuando pase, se resuelve **en esa linea**, con un comentario que explique el
por qué. Lo ideal es que no haga falta.

## Reportar un problema

Abre una issue con: versión de Python, sistema operativo, qué comando
ejecutaste y la salida completa (con `--dry-run` si el robot molesta).
