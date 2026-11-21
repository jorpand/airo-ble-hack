"""Tests del firmware del ESP32 (la parte que se puede probar sin placa).

El firmware corre en MicroPython, no en CPython, asi que aqui se falsea el
modulo `bluetooth` (que no existe fuera del chip) y se importan las funciones
puras del spike: el parseo del nombre del advertising, la comparacion de UUIDs
y, lo mas importante, **los bytes de los paquetes de prueba**.

Ese ultimo es el que protege la regla de "una sola fuente de la verdad": si
alguien cambia `airo_ble/protocol.py`, los bytes del firmware tienen que cambiar
con el, o el ESP32 moveria el robot de otra manera que el portatil.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from airo_ble.protocol import Command

RUTA_FIRMWARE = Path(__file__).resolve().parent.parent / "firmware" / "esp32" / "main.py"


def _cargar_firmware() -> Any:
    """Importa `firmware/esp32/main.py` con un modulo `bluetooth` falso."""
    if "bluetooth" not in sys.modules:
        falso = types.ModuleType("bluetooth")
        falso.BLE = lambda: None  # type: ignore[attr-defined]
        falso.UUID16 = lambda valor: valor  # type: ignore[attr-defined]
        for nombre in (
            "_IRQ_SCAN_RESULT",
            "_IRQ_CENTRAL_CONNECT",
            "_IRQ_CENTRAL_DISCONNECT",
            "_IRQ_GATTC_SERVICE_RESULT",
            "_IRQ_GATTC_CHARACTERISTIC_RESULT",
            "_IRQ_GATTC_WRITE_DONE",
        ):
            setattr(falso, nombre, 0)
        sys.modules["bluetooth"] = falso

    spec = importlib.util.spec_from_file_location("airo_firmware_esp32", RUTA_FIRMWARE)
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class UUIDFalso:
    """Imita el UUID de MicroPython: 2 bytes (16 bits) o 16 bytes (128 bits).

    MicroPython 1.26 no tiene `UUID16` (se hace `UUID(0xFFF0)`) y guarda los
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


@pytest.fixture(scope="module")
def firmware() -> Any:
    return _cargar_firmware()


# --- Los bytes ---------------------------------------------------------------


def test_el_paquete_de_parar_es_el_de_protocol_py(firmware: Any) -> None:
    """El paquete de parar del firmware es el que genera `protocol.py`."""
    assert firmware.PAQUETE_PARAR == Command().to_bytes()


def test_el_paquete_de_avanzar_es_el_de_protocol_py(firmware: Any) -> None:
    """El paquete de avanzar del firmware es el que genera `protocol.py`."""
    assert firmware.PAQUETE_ADELANTE == Command(right_speed=0.6, left_speed=0.6).to_bytes()


def test_los_paquetes_miden_20_bytes(firmware: Any) -> None:
    """20 bytes: caben justos en el MTU minimo (23 bytes ATT -> 20 de payload)."""
    assert len(firmware.PAQUETE_PARAR) == 20
    assert len(firmware.PAQUETE_ADELANTE) == 20


# --- El nombre del advertising ------------------------------------------------


def test_nombre_de_adv_lee_el_nombre_completo(firmware: Any) -> None:
    """Estructura AD: [longitud][tipo][datos], con la longitud contando el tipo."""
    # 0x06 = 1 (tipo) + 5 (datos "AIRo\\0")
    adv = bytes([0x06, 0x09]) + b"AIRo\x00"
    assert firmware.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_quita_el_null_final(firmware: Any) -> None:
    """El nombre viene en C (con su \\0): sin quitarlo, el robot no aparece."""
    adv = bytes([0x06, 0x09]) + b"AIRo\x00"
    assert firmware.nombre_de_adv(adv) == "AIRo"
    assert "\x00" not in firmware.nombre_de_adv(adv)


def test_nombre_de_adv_lee_el_nombre_corto(firmware: Any) -> None:
    # 0x05 = 1 (tipo) + 4 (datos "AIRo")
    adv = bytes([0x05, 0x08]) + b"AIRo"
    assert firmware.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_salta_otros_tipos(firmware: Any) -> None:
    """Un tipo que no es de nombre se salta entero (longitud + tipo + datos)."""
    # 0x03 = 1 (tipo) + 2 (datos), luego el nombre: 0x05 = 1 + 4
    adv = bytes([0x03, 0x02, 0x01, 0x06, 0x05, 0x09]) + b"AIRo"
    assert firmware.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_sin_nombre(firmware: Any) -> None:
    assert firmware.nombre_de_adv(bytes([0x02, 0x01, 0x06])) == ""


# --- Los UUID ------------------------------------------------------------------


def test_es_uuid_con_16_bits(firmware: Any) -> None:
    """MicroPython 1.26 guarda el UUID de 16 bits como dos bytes."""
    assert firmware.es_uuid(UUIDFalso(0xFFF0), 0xFFF0)
    assert not firmware.es_uuid(UUIDFalso(0xFFF0), 0xFFF1)


def test_es_uuid_con_128_bits_y_base_estandar(firmware: Any) -> None:
    """El base UUID que usa el robot normalmente."""
    uuid = UUIDFalso("0000fff1-0000-1000-8000-00805f9b34fb")
    assert firmware.es_uuid(uuid, 0xFFF1)


def test_es_uuid_con_128_bits_y_base_de_ceros(firmware: Any) -> None:
    """El otro base UUID: el del modulo cuando se reinicia de otra manera."""
    uuid = UUIDFalso("0000fff1-0000-1000-8000-000000000000")
    assert firmware.es_uuid(uuid, 0xFFF1)


def test_es_uuid_no_confunde_otros_servicios(firmware: Any) -> None:
    assert not firmware.es_uuid(UUIDFalso(0xFFF2), 0xFFF1)
    assert not firmware.es_uuid(UUIDFalso("0000180f-0000-1000-8000-00805f9b34fb"), 0xFFF1)


# --- Varios ---------------------------------------------------------------------


def test_mac_se_formatea(firmware: Any) -> None:
    assert firmware._mac(b"\xaa\xbb\xcc\xdd\xee\xff") == "AA:BB:CC:DD:EE:FF"


def test_el_firmware_no_usa_uuid16() -> None:
    """MicroPython 1.26 no tiene `UUID16`: el UUID de 16 bits es `UUID(0x...)`."""
    fuente = RUTA_FIRMWARE.read_text(encoding="utf-8")
    assert "UUID16" not in fuente


def test_el_firmware_no_usa_las_constantes_irq() -> None:
    """En 1.26 las constantes `_IRQ_*` no existen: los eventos van numerados."""
    fuente = RUTA_FIRMWARE.read_text(encoding="utf-8")
    assert "bluetooth._IRQ_" not in fuente


def test_esperar_hasta_devuelve_true_si_se_cumple(firmware: Any) -> None:
    assert firmware._esperar_hasta(lambda: True, 1000) is True


def test_esperar_hasta_devuelve_false_si_no_se_cumple(firmware: Any) -> None:
    assert firmware._esperar_hasta(lambda: False, 100) is False
