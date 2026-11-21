# Cómo colaborar en airo-ble

Cliente BLE del robot **Clementoni AIRO** en Python, con interfaz web en
React y un plugin de Scratch. Todo el detalle del protocolo está en
[`GUIA-PROGRAMAR-AIRO.md`](GUIA-PROGRAMAR-AIRO.md).

## Puesta en marcha

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # la libreria + la API + los tests
```

La interfaz web se compila aparte (la build no se versiona):

```bash
cd web && npm ci && npm run build
```

## Antes de abrir un PR

```bash
pytest -q                    # 194 tests
cd web && npm test           # 95 tests
pre-commit run --all-files   # formato, sintaxis y secretos
```

Ojo: `pre-commit` **no** deja hacer commit directamente en `main` (hook
`no-commit-to-branch`). Trabaja en una rama y abre un PR.

## Dónde está cada cosa

| Ruta | Qué es |
|---|---|
| `airo_ble/` | la libreria instalable (`pip install .`) |
| `airo_ble/api/` | backend FastAPI: traduce bloques a pasos y mueve el robot |
| `airo_ble/scratch3_airo/` | la extensión de Scratch (TurboWarp) |
| `web/src/` | la interfaz React (Vite) |
| `tests/` | los tests de Python |
| `analisis/` | scripts del reversing del APK (el volcado no se versiona) |
| `example/` | ejemplos sueltos |

## Lo que **no** se versiona

Está todo en el `.gitignore`, pero por si acaso:

- `.venv*`, `node_modules/`, `__pycache__/`, caches de pytest/ruff/vite.
- `web/dist/`: es la build de Vite. Se regenera con `npm run build`.
- `evidencia/`: el desensamblado y las capturas. Son material de trabajo, no
  fuente. La explicación de cada byte vive en la guía.
- `analisis/*.txt` y `analisis/*.tsv`: volcados generados (unos 19 MB). Los
  scripts `.py` sí están en el repo.

## Reglas de estilo

- Comentarios y documentación **en español**, igual que el resto del repo.
- Nada de reformateo masivo: el estilo actual es el que hay.
- `ruff` solo comprueba errores que rompen el código (sintaxis, nombres
  indefinidos). No se usa como formateador.
- Si tocas el protocolo, actualiza la guía y añade el test que lo demuestra.

## Reportar un problema

Abre una issue con: versión de Python, sistema operativo, qué comando
ejecutaste y la salida completa (con `--dry-run` si el robot molesta).
