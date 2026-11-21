"""Stubs del modulo `bluetooth` de MicroPython.

Solo para que pyright pueda comprobar el firmware del ESP32 (`firmware/esp32/`),
que corre en MicroPython y no en CPython. El API real esta en:

    https://docs.micropython.org/en/latest/library/bluetooth.html

No es codigo del chip: no se copia a la placa ni se importa desde alla.
"""

from collections.abc import Callable
from typing import Any

class UUID:
    uuid: int | bytes
    def __init__(self, value: int | bytes | str, /) -> None: ...
    def __str__(self) -> str: ...

def UUID16(value: int, /) -> UUID: ...

class BLE:
    def active(self, active: bool = ..., /) -> bool: ...
    def irq(self, handler: Callable[[int, Any], None], /) -> None: ...
    def gap_scan(
        self,
        duration_ms: int | None = ...,
        interval_us: int = ...,
        window_us: int = ...,
        active: bool = ...,
        /,
    ) -> None: ...
    def gap_connect(
        self,
        addr_type: int,
        addr: bytes,
        scan_duration_ms: int | None = ...,
        min_conn_interval_us: int | None = ...,
        max_conn_interval_us: int | None = ...,
        /,
    ) -> None: ...
    def gap_disconnect(self, conn_handle: int, /) -> None: ...
    def gattc_discover_services(self, conn_handle: int, uuid: UUID | None = ..., /) -> None: ...
    def gattc_discover_characteristics(
        self, conn_handle: int, start_handle: int, end_handle: int, uuid: UUID | None = ..., /
    ) -> None: ...
    def gattc_write(
        self, conn_handle: int, value_handle: int, data: bytes, mode: int = ..., /
    ) -> None: ...
    def gattc_exchange_mtu(self, conn_handle: int, /) -> None: ...

# OJO: MicroPython 1.26 **no** expone las constantes `_IRQ_*` en este modulo
# (aparecen en versiones posteriores). El firmware usa los numeros de evento
# de `extmod/modbluetooth.h`, definidos en `firmware/esp32/main.py`.
