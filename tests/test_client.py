"""
Test del cliente con un BLE simulado.

Inyecta un `bleak` falso en `sys.modules` para comprobar, sin hardware, que:
  - el escaneo encuentra el robot por su nombre 'AIRo',
  - se localiza servicio FFF0 / characteristic FFF1,
  - cada comando produce exactamente 20 bytes por characteristic,
  - el LED, las ruedas y los servos acaban en los bytes correctos.

Ejecutar: python3 tests/test_client.py
"""

from __future__ import annotations

import asyncio
import sys
import types

from airo_ble.protocol import (
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
    Joint,
    Led,
    encode_servo,
)

WRITTEN: list[bytes] = []


class FakeCharacteristic:
    uuid = WRITE_CHARACTERISTIC_UUID


class FakeService:
    uuid = SERVICE_UUID

    def get_characteristic(self, uuid):
        return FakeCharacteristic() if str(uuid).upper() == WRITE_CHARACTERISTIC_UUID else None


class FakeServices:
    def get_service(self, uuid):
        return FakeService() if str(uuid).upper() == SERVICE_UUID else None

    def __iter__(self):
        return iter([FakeService()])


class FakeClient:
    def __init__(self, target, timeout=None):
        self.target = target
        self.timeout = timeout
        self.services = FakeServices()
        self.connected = False

    @property
    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def write_gatt_char(self, characteristic, data, response=None):
        assert isinstance(characteristic, FakeCharacteristic)
        assert len(data) == 20, f"el paquete debe tener 20 bytes, tiene {len(data)}"
        assert response is True, "la app escribe con respuesta"
        WRITTEN.append(bytes(data))


class FakeDevice:
    address = "AA:BB:CC:DD:EE:FF"
    name = "AIRo"


class FakeAdv:
    local_name = "AIRo"
    rssi = -50
    service_uuids = [SERVICE_UUID]


class FakeScanner:
    """Escáner simulado: llama al callback como hace bleak 3.x."""

    def __init__(self, detection_callback=None, **kwargs):
        self.detection_callback = detection_callback

    async def start(self):
        if self.detection_callback is not None:
            self.detection_callback(FakeDevice(), FakeAdv())

    async def stop(self):
        pass


def install_fake_bleak() -> None:
    module = types.ModuleType("bleak")
    setattr(module, "BleakClient", FakeClient)
    setattr(module, "BleakScanner", FakeScanner)
    sys.modules["bleak"] = module


async def test_scenario() -> None:
    install_fake_bleak()
    from airo_ble import AiroRobot

    async with AiroRobot() as robot:
        await robot.drive(left=1.0, right=-1.0)
        await robot.led(Led.FLASH)
        await robot.servo(Joint.LEFT_ARM, 30)
        await robot.stop()

    # 5 escrituras: 4 comandos + el paquete de parada que se manda al desconectar
    assert len(WRITTEN) == 5, f"se esperaban 5 escrituras, hubo {len(WRITTEN)}"

    # 1) ruedas + (led por defecto off)
    p = WRITTEN[0]
    assert p[0] == 0xA5
    assert p[1] == 0            # LED off
    # rueda izquierda fisica (bytes 2-3) = adelante, vel 1
    assert (p[2], p[3]) == (1, 1)
    # rueda derecha fisica (bytes 4-5) = atras, vel 1
    assert (p[4], p[5]) == (1, 1)

    # 2) LED flash, ruedas intactas
    p = WRITTEN[1]
    assert p[1] == 2

    # 3) codo izquierdo = 30 grados -> byte 8 = encode_servo(LEFT_ARM, 30)
    p = WRITTEN[2]
    assert p[8] == encode_servo(Joint.LEFT_ARM, 30)

    # 4) stop explicito: ruedas a 0 pero el servo se mantiene
    p = WRITTEN[3]
    assert (p[2], p[3], p[4], p[5]) == (0, 0, 0, 0)
    assert p[8] == encode_servo(Joint.LEFT_ARM, 30)

    # 5) parada automatico al desconectar
    p = WRITTEN[4]
    assert (p[2], p[3], p[4], p[5]) == (0, 0, 0, 0)

    # la cola fija se mantiene en todos los paquetes
    for packet in WRITTEN:
        assert packet[10:] == bytes((5, 22, 39, 56, 73, 90, 107, 124, 141, 158))


def main() -> int:
    install_fake_bleak()
    asyncio.run(test_scenario())
    print("  OK   test_client (BLE simulado): 5 escrituras de 20 bytes correctas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
