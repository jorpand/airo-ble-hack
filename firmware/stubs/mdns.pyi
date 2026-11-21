"""Stubs del modulo `mdns` de la micropython-lib.

Solo para que pyright pueda comprobar `firmware/esp32/wifi.py`. No es codigo
del chip: no se copia a la placa (el modulo va en el `mip.json`).
"""

from typing import Any

def register(hostname: str, ip: Any = ..., /) -> None: ...
