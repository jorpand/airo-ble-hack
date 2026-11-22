"""Stubs del modulo `machine` de MicroPython (ESP32).

Solo para que pyright pueda comprobar `firmware/esp32/led.py`. No es codigo
del chip: no se copia a la placa.

Lo que usa el firmware es `Pin`, y nada mas (el WS2812 se maneja con el
modulo `neopixel`).
"""

from typing import Any

class Pin:
    IN: int
    OUT: int
    OPEN_DRAIN: int
    PULL_UP: int
    PULL_DOWN: int

    def __init__(
        self,
        id: int,
        mode: int = ...,
        pull: int = ...,
        *,
        value: Any = ...,
        invert: bool = ...,
    ) -> None: ...
    def init(
        self,
        mode: int = ...,
        pull: int = ...,
        *,
        value: Any = ...,
        invert: bool = ...,
    ) -> None: ...
    def value(self, value: Any = ..., /) -> Any: ...
    def on(self) -> None: ...
    def off(self) -> None: ...
    def irq(
        self,
        handler: Any = ...,
        *,
        trigger: int = ...,
        priority: int = ...,
        wake: Any = ...,
        hard: bool = ...,
    ) -> None: ...
