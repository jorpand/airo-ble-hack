"""
El sitio donde se guardan los programas y las funciones: un archivo JSON.

El archivo vive en `~/.airo/guardado.json` (se puede cambiar con la variable
de entorno `AIRO_GUARDADO`). Es un solo archivo con dos listas:

```json
{
  "programas": [{"id": "a1b2c3d4", "nombre": "Mi programa", "bloques": [...]}],
  "funciones": [{"id": "e5f6g7h8", "nombre": "Saludo", "bloques": [...]}]
}
```

Decisiones:

- Se escribe **de forma atomica** (a un temporal y luego se renombra), asi un
  corte de luz a mitad de escritura no deja el archivo hecho pedazos.
- Si el archivo esta corrupto o no se puede escribir, **no se rompe la
  interfaz**: se avisa con un mensaje y se sigue trabajando en memoria.
- Un `Lock` de hilo protege las lecturas y las escrituras (la API es
  asincrona, pero el archivo se toca de forma sincrona y rapida).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "ruta_guardado",
    "leer",
    "guardar_programa",
    "borrar_programa",
    "guardar_funcion",
    "borrar_funcion",
    "ErrorGuardado",
]

#: Donde se guarda todo por defecto.
RUTA_POR_DEFECTO = Path.home() / ".airo" / "guardado.json"

#: Protege el archivo: las operaciones son de leer-todo, cambiar y escribir.
_candado = threading.Lock()


class ErrorGuardado(RuntimeError):
    """No se ha podido guardar (por ejemplo, el disco esta lleno)."""


def ruta_guardado() -> Path:
    """El archivo donde se guarda todo."""
    return Path(os.environ.get("AIRO_GUARDADO", RUTA_POR_DEFECTO)).expanduser()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer_crudo() -> dict[str, Any]:
    """Lee el archivo. Si no esta o esta roto, devuelve las listas vacias."""
    ruta = ruta_guardado()
    if not ruta.exists():
        return {"programas": [], "funciones": []}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"programas": [], "funciones": []}
    if not isinstance(datos, dict):
        return {"programas": [], "funciones": []}
    if not isinstance(datos.get("programas"), list):
        datos["programas"] = []
    if not isinstance(datos.get("funciones"), list):
        datos["funciones"] = []
    return datos


def _escribir_crudo(datos: dict[str, Any]) -> None:
    """Escribe el archivo de forma atomica."""
    ruta = ruta_guardado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(ruta)
    except OSError as exc:
        raise ErrorGuardado(f"No se ha podido guardar: {exc}") from exc


def leer() -> dict[str, list[dict[str, Any]]]:
    """Todo lo guardado: `{"programas": [...], "funciones": [...]}`."""
    with _candado:
        return _leer_crudo()


def _guardar(
    lista: str, id: str, nombre: str, bloques: list[dict[str, Any]]
) -> dict[str, Any]:
    """Guarda o actualiza una entrada de una de las dos listas."""
    with _candado:
        datos = _leer_crudo()
        ahora = _ahora()
        if id:
            for entrada in datos[lista]:
                if entrada.get("id") == id:
                    entrada["nombre"] = nombre
                    entrada["bloques"] = bloques
                    entrada["modificado"] = ahora
                    _escribir_crudo(datos)
                    return entrada
        nuevo = {
            "id": id or uuid.uuid4().hex[:8],
            "nombre": nombre,
            "bloques": bloques,
            "creado": ahora,
            "modificado": ahora,
        }
        datos[lista].append(nuevo)
        _escribir_crudo(datos)
        return nuevo


def guardar_programa(
    id: str, nombre: str, bloques: list[dict[str, Any]]
) -> dict[str, Any]:
    """Guarda un programa (o lo actualiza si ya tiene id)."""
    return _guardar("programas", id, nombre, bloques)


def borrar_programa(id: str) -> bool:
    """Borra un programa. Devuelve si estaba."""
    with _candado:
        datos = _leer_crudo()
        antes = len(datos["programas"])
        datos["programas"] = [p for p in datos["programas"] if p.get("id") != id]
        if len(datos["programas"]) == antes:
            return False
        _escribir_crudo(datos)
        return True


def guardar_funcion(
    id: str, nombre: str, bloques: list[dict[str, Any]]
) -> dict[str, Any]:
    """Guarda una funcion (o la actualiza si ya tiene id)."""
    return _guardar("funciones", id, nombre, bloques)


def borrar_funcion(id: str) -> bool:
    """Borra una funcion. Devuelve si estaba."""
    with _candado:
        datos = _leer_crudo()
        antes = len(datos["funciones"])
        datos["funciones"] = [f for f in datos["funciones"] if f.get("id") != id]
        if len(datos["funciones"]) == antes:
            return False
        _escribir_crudo(datos)
        return True
