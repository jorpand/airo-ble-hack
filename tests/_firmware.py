"""Ayudas para probar el firmware del ESP32 desde CPython.

El firmware corre en MicroPython, no en CPython, asi que aqui se falsea el
modulo `bluetooth` (que no existe fuera del chip) y se cargan los ficheros
del firmware como si fueran modulos normales.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

#: Donde vive el firmware.
CARPETA = Path(__file__).resolve().parent.parent / "firmware" / "esp32"


def poner_bluetooth_falso() -> None:
    """Mete un modulo `bluetooth` falso en `sys.modules` (si no esta ya)."""
    if "bluetooth" in sys.modules:
        return
    falso = types.ModuleType("bluetooth")
    falso.BLE = lambda: None  # type: ignore[attr-defined]
    for nombre in (
        "_IRQ_SCAN_RESULT",
        "_IRQ_CENTRAL_CONNECT",
        "_IRQ_CENTRAL_DISCONNECT",
        "_IRQ_PERIPHERAL_CONNECT",
        "_IRQ_PERIPHERAL_DISCONNECT",
        "_IRQ_GATTC_SERVICE_RESULT",
        "_IRQ_GATTC_CHARACTERISTIC_RESULT",
        "_IRQ_GATTC_WRITE_DONE",
    ):
        setattr(falso, nombre, 0)
    sys.modules["bluetooth"] = falso


def cargar(nombre: str) -> Any:
    """Carga un modulo del firmware (por ejemplo, `ble_robot` o `spike`)."""
    poner_bluetooth_falso()
    carpeta = str(CARPETA)
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)
    spec = importlib.util.spec_from_file_location(
        f"airo_fw_{nombre}", CARPETA / f"{nombre}.py"
    )
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo
