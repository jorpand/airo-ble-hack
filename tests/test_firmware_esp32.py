"""Tests del firmware del ESP32 (la parte que se puede probar sin placa).

El firmware corre en MicroPython, no en CPython, asi que aqui se falsea el
modulo `bluetooth` (que no existe fuera del chip) y se importan las funciones
puras del cliente BLE: el parseo del nombre del advertising, la comparacion
de UUIDs y, lo mas importante, **los bytes de los paquetes de prueba**.

Ese ultimo es el que protege la regla de "una sola fuente de la verdad": si
alguien cambia `airo_ble/protocol.py`, los bytes del firmware tienen que cambiar
con el, o el ESP32 moveria el robot de otra manera que el portatil.
"""

from __future__ import annotations

from typing import Any

import pytest
from _firmware import CARPETA, UUIDFalso, cargar

from airo_ble.protocol import Command


@pytest.fixture(scope="module")
def ble() -> Any:
    return cargar("ble_robot")


@pytest.fixture(scope="module")
def spike() -> Any:
    return cargar("spike")


# --- Los bytes ---------------------------------------------------------------


def test_el_paquete_de_parar_es_el_de_protocol_py(spike: Any) -> None:
    """El paquete de parar del firmware es el que genera `protocol.py`."""
    assert spike.PAQUETE_PARAR == Command().to_bytes()


def test_el_paquete_de_avanzar_es_el_de_protocol_py(spike: Any) -> None:
    """El paquete de avanzar del firmware es el que genera `protocol.py`."""
    assert spike.PAQUETE_ADELANTE == Command(right_speed=0.6, left_speed=0.6).to_bytes()


def test_los_paquetes_miden_20_bytes(spike: Any) -> None:
    """20 bytes: caben justos en el MTU minimo (23 bytes ATT -> 20 de payload)."""
    assert len(spike.PAQUETE_PARAR) == 20
    assert len(spike.PAQUETE_ADELANTE) == 20


# --- El nombre del advertising ------------------------------------------------


def test_nombre_de_adv_lee_el_nombre_completo(ble: Any) -> None:
    """Estructura AD: [longitud][tipo][datos], con la longitud contando el tipo."""
    # 0x06 = 1 (tipo) + 5 (datos "AIRo\\0")
    adv = bytes([0x06, 0x09]) + b"AIRo\x00"
    assert ble.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_quita_el_null_final(ble: Any) -> None:
    """El nombre viene en C (con su \\0): sin quitarlo, el robot no aparece."""
    adv = bytes([0x06, 0x09]) + b"AIRo\x00"
    assert ble.nombre_de_adv(adv) == "AIRo"
    assert "\x00" not in ble.nombre_de_adv(adv)


def test_nombre_de_adv_lee_el_nombre_corto(ble: Any) -> None:
    # 0x05 = 1 (tipo) + 4 (datos "AIRo")
    adv = bytes([0x05, 0x08]) + b"AIRo"
    assert ble.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_salta_otros_tipos(ble: Any) -> None:
    """Un tipo que no es de nombre se salta entero (longitud + tipo + datos)."""
    # 0x03 = 1 (tipo) + 2 (datos), luego el nombre: 0x05 = 1 + 4
    adv = bytes([0x03, 0x02, 0x01, 0x06, 0x05, 0x09]) + b"AIRo"
    assert ble.nombre_de_adv(adv) == "AIRo"


def test_nombre_de_adv_sin_nombre(ble: Any) -> None:
    assert ble.nombre_de_adv(bytes([0x02, 0x01, 0x06])) == ""


# --- Los UUID ------------------------------------------------------------------


def test_es_uuid_con_16_bits(ble: Any) -> None:
    """MicroPython guarda el UUID de 16 bits como dos bytes."""
    assert ble.es_uuid(UUIDFalso(0xFFF0), 0xFFF0)
    assert not ble.es_uuid(UUIDFalso(0xFFF0), 0xFFF1)


def test_es_uuid_con_128_bits_y_base_estandar(ble: Any) -> None:
    """El base UUID que usa el robot normalmente."""
    uuid = UUIDFalso("0000fff1-0000-1000-8000-00805f9b34fb")
    assert ble.es_uuid(uuid, 0xFFF1)


def test_es_uuid_con_128_bits_y_base_de_ceros(ble: Any) -> None:
    """El otro base UUID: el del modulo cuando se reinicia de otra manera."""
    uuid = UUIDFalso("0000fff1-0000-1000-8000-000000000000")
    assert ble.es_uuid(uuid, 0xFFF1)


def test_es_uuid_no_confunde_otros_servicios(ble: Any) -> None:
    assert not ble.es_uuid(UUIDFalso(0xFFF2), 0xFFF1)
    assert not ble.es_uuid(UUIDFalso("0000180f-0000-1000-8000-00805f9b34fb"), 0xFFF1)


# --- Varios ---------------------------------------------------------------------


def test_mac_se_formatea(ble: Any) -> None:
    assert ble.mac(b"\xaa\xbb\xcc\xdd\xee\xff") == "AA:BB:CC:DD:EE:FF"


# --- El flujo entero, con un BLE de mentira ---------------------------------


async def test_el_cliente_conecta_descubre_y_escribe(ble: Any) -> None:
    """Conectar, descubrir FFF0/FFF1 y escribir: el camino completo.

    El doble de `bluetooth` avisa de la conexion con el IRQ **7** (no con
    el 1, como haria un central de verdad). Si el firmware volviera al 1,
    este test se caeria: es la vigilancia de esa rareza.
    """
    cliente = ble.ClienteAiro()
    assert await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    assert cliente.conn >= 0
    assert await cliente.descubrir(1000)
    assert cliente.servicio == (1, 2)
    assert cliente.caracteristica == 5
    assert await cliente.escribir(b"\xa5\x00")
    assert cliente.ble.escrituras[-1][2] == b"\xa5\x00"


async def test_el_refresco_reenvia_el_ultimo_paquete(ble: Any) -> None:
    """La placa reenvia sola el ultimo paquete (el robot los quiere seguidos)."""
    cliente = ble.ClienteAiro()
    await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    await cliente.descubrir(1000)
    await cliente.escribir(b"\xa5\x01")
    assert len(cliente.ble.escrituras) == 1
    assert await cliente.refrescar()
    assert len(cliente.ble.escrituras) == 2
    # y es el mismo paquete
    assert cliente.ble.escrituras[-1][2] == b"\xa5\x01"


async def test_el_refresco_no_hace_nada_si_no_hay_paquete(ble: Any) -> None:
    """Sin paquete guardado no hay nada que reenviar."""
    cliente = ble.ClienteAiro()
    await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    await cliente.descubrir(1000)
    assert not await cliente.refrescar()
    assert cliente.ble.escrituras == []


async def test_el_refresco_cuenta_los_fallos(ble: Any) -> None:
    """Si el robot no contesta, el refresco se da por fallido."""
    cliente = ble.ClienteAiro()
    await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    await cliente.descubrir(1000)
    await cliente.escribir(b"\xa5\x01")
    cliente.ble.fallar_escritura = True
    assert not await cliente.refrescar()
    assert cliente.fallos == 1


async def test_el_estado_dice_cuantos_bytes_guarda(ble: Any) -> None:
    """El estado del puente enseña el ultimo paquete guardado."""
    cliente = ble.ClienteAiro()
    await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    await cliente.descubrir(1000)
    await cliente.escribir(b"\xa5\x01\x02")
    estado = cliente.estado()
    assert estado["bytes_guardados"] == 3
    assert estado["conectado"] is True


# --- Las rarezas de la API, vigiladas --------------------------------------------


def test_el_firmware_no_usa_uuid16() -> None:
    """MicroPython no tiene `UUID16`: el UUID de 16 bits es `UUID(0x...)`."""
    for nombre in ("ble_robot.py", "puente.py", "main.py", "spike.py"):
        fuente = (CARPETA / nombre).read_text(encoding="utf-8")
        assert "UUID16(" not in fuente, nombre


def test_el_firmware_no_usa_las_constantes_irq() -> None:
    """Las constantes `_IRQ_*` no existen: los eventos van numerados."""
    for nombre in ("ble_robot.py", "puente.py", "main.py", "spike.py"):
        fuente = (CARPETA / nombre).read_text(encoding="utf-8")
        assert "bluetooth._IRQ_" not in fuente, nombre
