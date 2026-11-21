"""Ayudas para probar el firmware del ESP32 desde CPython.

El firmware corre en MicroPython, no en CPython, asi que aqui se falsea el
modulo `bluetooth` (que no existe fuera del chip) y se cargan los ficheros
del firmware como si fueran modulos normales.

El doble de `bluetooth.BLE` no es un simple `None`: imita lo que hace la
placa de verdad (incluidas sus rarezas, como avisar de la conexion con el
IRQ 7 en vez de con el 1), asi que se puede probar el flujo entero del
firmware -conectar, descubrir, escribir y refrescar- sin tener el robot
encendido.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

#: Donde vive el firmware.
CARPETA = Path(__file__).resolve().parent.parent / "firmware" / "esp32"

#: Los codigos de evento del IRQ (ver `extmod/modbluetooth.h`).
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6
IRQ_PERIPHERAL_CONNECT = 7
IRQ_PERIPHERAL_DISCONNECT = 8
IRQ_GATTC_SERVICE_RESULT = 9
IRQ_GATTC_CHARACTERISTIC_RESULT = 11
IRQ_GATTC_WRITE_DONE = 17


class UUIDFalso:
    """Imita el UUID de MicroPython: 2 bytes (16 bits) o 16 bytes (128 bits).

    MicroPython no tiene `UUID16` (se hace `UUID(0xFFF0)`) y guarda los
    128 bits en little endian, con el grupo de 16 bits en las posiciones 12 y
    13. Esto es lo que se ha visto en la placa de verdad.
    """

    def __init__(self, valor: int | str) -> None:
        if isinstance(valor, int):
            self.datos = bytes([valor & 0xFF, (valor >> 8) & 0xFF])
        else:
            # El little endian del Bluetooth es el byte a byte del canonico
            # dado la vuelta: 0000fff0-...-00805f9b34fb -> fb349b5f...f0ff0000
            self.datos = bytes.fromhex(valor.replace("-", ""))[::-1]

    def __bytes__(self) -> bytes:
        return self.datos


class BLEFalsa:
    """Un `bluetooth.BLE` de mentira que imita a la placa.

    Guarda todo lo que se le hace (para poder comprobarlo en los tests) y
    avisa de los eventos por el manejador del IRQ, como hace el NimBLE de
    verdad: la conexion se avisa con el IRQ **7** y no con el 1, el
    descubrimiento de servicios y characteristics avisa con el 9 y el 11, y
    la escritura con el 17 (el estado va en la tercera posicion).
    """

    def __init__(self) -> None:
        self.activo = False
        self.manejador: Any = None
        #: Las escrituras que se le han pedido: (conn, handle, datos, modo).
        self.escrituras: list[tuple[int, int, bytes, int]] = []
        #: El ultimo escaneo pedido (None = parado).
        self.escaneo: int | None = None
        #: Las conexiones que se le han pedido.
        self.conexiones: list[tuple[int, bytes]] = []
        #: Si el proximo `gattc_write` tiene que fallar.
        self.fallar_escritura = False
        #: El handle de la characteristic que se "descubre".
        self.handle_characteristic = 5

    # -- API de MicroPython -----------------------------------------------

    def active(self, valor: bool) -> None:
        self.activo = bool(valor)

    def irq(self, handler: Any, **kwargs: Any) -> None:
        # Ojo: en MicroPython esto **sustituye** al manejador anterior.
        self.manejador = handler

    def gap_scan(
        self, ms: int | None, interval: int = 0, window: int = 0, active: bool = True
    ) -> None:
        self.escaneo = ms

    def gap_connect(self, addr_type: int, addr: bytes, scan_ms: int = 0) -> None:
        self.conexiones.append((addr_type, bytes(addr)))
        self._avisar(IRQ_PERIPHERAL_CONNECT, (1,))

    def gap_disconnect(self, conn: int) -> None:
        self._avisar(IRQ_PERIPHERAL_DISCONNECT, (conn,))

    def gattc_discover_services(self, conn: int) -> None:
        self._avisar(IRQ_GATTC_SERVICE_RESULT, (conn, 1, 2, UUIDFalso(0xFFF0)))

    def gattc_discover_characteristics(self, conn: int, inicio: int, fin: int) -> None:
        self._avisar(
            IRQ_GATTC_CHARACTERISTIC_RESULT,
            (conn, fin, self.handle_characteristic, 0, UUIDFalso(0xFFF1)),
        )

    def gattc_write(self, conn: int, handle: int, datos: Any, modo: int = 0) -> None:
        self.escrituras.append((conn, handle, bytes(datos), modo))
        estado = 1 if self.fallar_escritura else 0
        self._avisar(IRQ_GATTC_WRITE_DONE, (conn, handle, estado))

    # -- Internos ---------------------------------------------------------

    def _avisar(self, evento: int, datos: Any) -> None:
        if self.manejador is not None:
            self.manejador(evento, datos)


def poner_bluetooth_falso() -> None:
    """Mete un modulo `bluetooth` falso en `sys.modules` (si no esta ya)."""
    if "bluetooth" in sys.modules:
        return
    falso = types.ModuleType("bluetooth")
    falso.BLE = BLEFalsa  # type: ignore[attr-defined]
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
