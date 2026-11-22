"""Stubs del modulo `neopixel` de MicroPython (ESP32).

Solo para que pyright pueda comprobar `firmware/esp32/led.py`. No es codigo
del chip: no se copia a la placa.

El modulo viene de `micropython-lib` (`drivers/led/neopixel/neopixel.py`) y
lo que usa el firmware es:

    pixel = neopixel.NeoPixel(Pin(pin, Pin.OUT), 1)
    pixel[0] = (r, g, b)
    pixel.write()

En el ESP32 el driver usa `machine.bitstream` (RMT), asi que el WS2812 va a
la velocidad del hardware y no por bit-bang.
"""

from collections.abc import Sequence
from typing import Any

class NeoPixel:
    def __init__(
        self,
        pin: Any,
        n: int,
        bpp: int = ...,
        timing: int = ...,
        brightness: float = ...,
        order: Sequence[int] | None = ...,
    ) -> None: ...
    def __setitem__(self, idx: int, value: Sequence[int]) -> None: ...
    def __getitem__(self, idx: int) -> tuple[int, ...]: ...
    def fill(self, value: Sequence[int]) -> None: ...
    def write(self) -> None: ...
