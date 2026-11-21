"""
Tests del robustecimiento del cliente BLE, sin hardware.

Se usa un `bleak` falso (igual que en `test_client.py`) para comprobar:

  - los errores son **verificables por tipo** (`AiroNotConnected`,
    `AiroWriteError`, `AiroConnectionError`, `AiroNotFound`), no solo texto,
  - el escaneo **no crece sin limite** y se queda con el mejor anuncio,
  - el ritmo de escritura se respeta **tambien con envios concurrentes**,
  - `send_raw` se comporta igual que `send` (y respeta `force`),
  - la reconexion limpia el enlace y vuelve a buscar el robot.

Ejecutar: python3 -m pytest tests/test_client_robusto.py -v
"""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

from airo_ble.client import (
    AiroConnectionError,
    AiroError,
    AiroNotConnected,
    AiroNotFound,
    AiroRobot,
    AiroWriteError,
)
from airo_ble.protocol import (
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
    Command,
)

WRITTEN: list[bytes] = []


# ---------------------------------------------------------------------------
# Un bleak falso
# ---------------------------------------------------------------------------


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
    """Cliente falso: `fallar_al_escribir` lo hace colgarse o reventar."""

    def __init__(self, target, timeout=None):
        self.target = target
        self.timeout = timeout
        self.services = FakeServices()
        self.connected = False
        self.fallar_al_escribir = False
        self.escribir_tarda = 0.0

    @property
    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def write_gatt_char(self, characteristic, payload, response=True):
        if self.escribir_tarda:
            await asyncio.sleep(self.escribir_tarda)
        if self.fallar_al_escribir:
            raise OSError("el modulo se ha dormido")
        WRITTEN.append(bytes(payload))
        return True


class FakeAdv:
    def __init__(self, name="AIRo", rssi=-50):
        self.local_name = name
        self.rssi = rssi


class FakeDevice:
    def __init__(self, address="AA:BB:CC:DD:EE:FF", name="AIRo"):
        self.address = address
        self.name = name


class FakeScanner:
    """Escáner que anuncia el robot un par de veces."""

    anuncios = 1
    rssi = -50
    direccion = "AA:BB:CC:DD:EE:FF"

    def __init__(self, detection_callback=None):
        self.detection_callback = detection_callback
        self.arrancado = False

    async def start(self):
        self.arrancado = True
        for _ in range(self.anuncios):
            self.detection_callback(FakeDevice(self.direccion), FakeAdv(rssi=self.rssi))

    async def stop(self):
        self.arrancado = False


def install_fake_bleak() -> None:
    module = types.ModuleType("bleak")
    module.BleakClient = FakeClient
    module.BleakScanner = FakeScanner
    sys.modules["bleak"] = module


@pytest.fixture(autouse=True)
def _bleak_falso():
    install_fake_bleak()
    WRITTEN.clear()
    FakeScanner.anuncios = 1
    FakeScanner.rssi = -50
    yield


# ---------------------------------------------------------------------------
# 1. Errores verificables por tipo
# ---------------------------------------------------------------------------


async def test_enviar_sin_conectar_da_error_tipado() -> None:
    robot = AiroRobot()
    with pytest.raises(AiroNotConnected):
        await robot.send(Command())
    with pytest.raises(AiroNotConnected):
        await robot.send_raw(b"\xa5")


async def test_todos_los_errores_heredan_de_airoerror() -> None:
    """Se pueden distinguir por tipo, sin mirar el mensaje."""
    for error in (
        AiroNotFound,
        AiroNotConnected,
        AiroConnectionError,
        AiroWriteError,
    ):
        assert issubclass(error, AiroError)
    # y sigue siendo un RuntimeError, como antes (nadie rompe por esto)
    assert issubclass(AiroError, RuntimeError)


async def test_un_error_de_escritura_da_airowriteerror() -> None:
    robot = AiroRobot()
    await robot.connect()
    robot._client.fallar_al_escribir = True
    with pytest.raises(AiroWriteError) as exc:
        await robot.send(Command())
    assert "dormido" in str(exc.value)


async def test_una_escritura_colgada_da_timeout_con_mensaje() -> None:
    """El HM-10 duerme: la escritura se cuelga y hay que decir algo util."""
    robot = AiroRobot(write_timeout=0.05)
    await robot.connect()
    robot._client.escribir_tarda = 1.0
    with pytest.raises(AiroWriteError) as exc:
        await robot.send(Command())
    assert "no respondió" in str(exc.value)


async def test_si_no_hay_robot_da_airo_not_found() -> None:
    FakeScanner.anuncios = 0
    robot = AiroRobot(scan_timeout=0.1)
    with pytest.raises(AiroNotFound):
        await robot.connect()


# ---------------------------------------------------------------------------
# 2. El escaneo no crece sin limite
# ---------------------------------------------------------------------------


async def test_el_escaneo_no_crece_sin_limite() -> None:
    """El robot se anuncia muchas veces: solo se guarda uno por direccion."""
    robot = AiroRobot()
    for _ in range(500):
        robot._on_device(FakeDevice(), FakeAdv(rssi=-50))
    assert len(robot._seen) == 1


async def test_se_queda_con_el_anuncio_mas_fuerte() -> None:
    """Con dos anuncios, gana el de mejor RSSI (el mas cercano)."""
    robot = AiroRobot()
    robot._on_device(FakeDevice("AA:BB:CC:DD:EE:FF"), FakeAdv(rssi=-80))
    robot._on_device(FakeDevice("11:22:33:44:55:66"), FakeAdv(rssi=-30))
    mejor = robot._mejor_dispositivo()
    assert mejor.address == "11:22:33:44:55:66"


async def test_un_anuncio_viejo_no_se_usa() -> None:
    """Un anuncio de hace mucho puede ser de un robot ya apagado."""
    robot = AiroRobot()
    robot._on_device(FakeDevice(), FakeAdv(rssi=-50))
    # lo hacemos viejo a proposito
    direccion, (device, rssi, momento) = next(iter(robot._seen.items()))
    robot._seen[direccion] = (device, rssi, momento - 3600)
    assert robot._mejor_dispositivo(max_antiguedad=10) is None
    # pero sin limite de antiguedad sigue estando
    assert robot._mejor_dispositivo() is not None


async def test_el_escaneo_solo_guarda_lo_que_interesa() -> None:
    """Un dispositivo con otro nombre no se guarda."""
    robot = AiroRobot(name="AIRo")
    robot._on_device(FakeDevice(name="Otro"), FakeAdv(name="Otro"))
    assert robot._seen == {}


# ---------------------------------------------------------------------------
# 3. El ritmo de escritura
# ---------------------------------------------------------------------------


async def test_el_ritmo_se_respeta_entre_envios() -> None:
    robot = AiroRobot(min_write_interval=0.05)
    await robot.connect()
    inicio = time.monotonic()
    await robot.send(Command())
    await robot.send(Command())
    await robot.send(Command())
    assert time.monotonic() - inicio >= 0.10  # 2 intervalos


async def test_el_ritmo_se_respeta_con_envios_concurrentes() -> None:
    """El ritmo se aplica DENTRO del lock: dos envios a la vez se separan.

    Antes el `now` se calculaba antes de escribir, asi que dos envios
    concurrentes creian que podia escribir los dos seguidos.
    """
    robot = AiroRobot(min_write_interval=0.05)
    await robot.connect()
    inicio = time.monotonic()
    await asyncio.gather(*(robot.send(Command()) for _ in range(4)))
    assert time.monotonic() - inicio >= 0.15  # 3 intervalos


async def test_force_se_salta_el_ritmo() -> None:
    robot = AiroRobot(min_write_interval=0.5)
    await robot.connect()
    inicio = time.monotonic()
    await robot.send(Command(), force=True)
    await robot.send(Command(), force=True)
    assert time.monotonic() - inicio < 0.3


async def test_el_ritmo_se_cuenta_desde_el_final_de_la_escritura() -> None:
    """`_last_write` se actualiza despues de escribir, no antes."""
    robot = AiroRobot(min_write_interval=0.05)
    await robot.connect()
    robot._client.escribir_tarda = 0.08
    await robot.send(Command())
    # si `_last_write` se hubiera puesto antes de escribir, el siguiente envio
    # no tendria que esperar nada
    inicio = time.monotonic()
    await robot.send(Command())
    assert time.monotonic() - inicio >= 0.04


# ---------------------------------------------------------------------------
# 4. send_raw se comporta como send
# ---------------------------------------------------------------------------


async def test_send_raw_respeta_el_ritmo() -> None:
    """Antes `send_raw` duplicaba el ritmo y no aceptaba `force`."""
    robot = AiroRobot(min_write_interval=0.05)
    await robot.connect()
    inicio = time.monotonic()
    await robot.send_raw(b"\xa5" + b"\x00" * 19)
    await robot.send_raw(b"\xa5" + b"\x00" * 19)
    assert time.monotonic() - inicio >= 0.05


async def test_send_raw_acepta_force() -> None:
    robot = AiroRobot(min_write_interval=0.5)
    await robot.connect()
    inicio = time.monotonic()
    await robot.send_raw(b"\xa5", force=True)
    await robot.send_raw(b"\xa5", force=True)
    assert time.monotonic() - inicio < 0.3


async def test_send_raw_escribe_los_bytes_tales_cuales() -> None:
    robot = AiroRobot()
    await robot.connect()
    await robot.send_raw(b"\xa5\x01\x02")
    assert WRITTEN[-1] == b"\xa5\x01\x02"


# ---------------------------------------------------------------------------
# 5. Reconexion
# ---------------------------------------------------------------------------


async def test_reconectar_cierra_y_vuelve_a_buscar() -> None:
    robot = AiroRobot()
    await robot.connect()
    await robot.reconnect()
    assert robot._client is not None
    assert robot._client.is_connected


async def test_conectar_dos_veces_no_hace_nada() -> None:
    """Conectar sobre un enlace vivo deja el modulo a medias."""
    robot = AiroRobot()
    await robot.connect()
    cliente = robot._client
    await robot.connect()
    assert robot._client is cliente


async def test_el_enlace_se_compueba_al_conectar() -> None:
    """Si bleak "conecta" pero el enlace no queda, hay que avisar."""

    class ClienteColgado(FakeClient):
        @property
        def is_connected(self):
            return False

    module = types.ModuleType("bleak")
    module.BleakClient = ClienteColgado
    module.BleakScanner = FakeScanner
    sys.modules["bleak"] = module

    robot = AiroRobot()
    with pytest.raises(AiroConnectionError):
        await robot.connect()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
