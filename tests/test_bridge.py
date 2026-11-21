"""Tests del puente BLE (el ESP32-S3 y el cliente de Python).

Estos tests **no necesitan ni la placa ni el robot**: levantan el servidor
HTTP del firmware de verdad (`firmware/esp32/http_srv.py` y `puente.py`, con
un BLE de mentira) y lo hablan con el cliente de verdad (`airo_ble.bridge`).

Eso es justo lo que hay que comprobar: que las dos mitades del contrato
coinciden. Los caminos (`/salud`, `/estado`, `/escanear`, `/escribir`,
`/conectar`, `/desconectar`), los codigos de error (409) y el cuerpo (bytes
crudos, no JSON) tienen que encajar, porque si no encajan solo se ve cuando
el robot esta delante y a hundredos de kilometros.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from _firmware import cargar

from airo_ble.api.service import RobotService
from airo_ble.bridge import PUENTE_ENV, BridgeRobot, crear_robot, url_del_puente
from airo_ble.client import (
    AiroConnectionError,
    AiroNotConnected,
    AiroNotFound,
)
from airo_ble.protocol import Command, Led
from airo_ble.session import RobotSession


class ClienteFalso:
    """El cliente BLE del robot, pero de mentira (para la placa)."""

    def __init__(self, conectado: bool = True) -> None:
        self.conn = 1 if conectado else -1
        self.caracteristica = 5
        self.ultimo = b""
        self.fallos = 0
        self.error = ""
        self.paquetes = 0
        self.mac_robot = "64:E0:39:2D:90:80"
        self.nombre_robot = "AIRo"
        self.rssi = -60
        self.servicio = (1, 2)
        #: Los paquetes que le han llegado.
        self.recibidos: list[bytes] = []
        #: Cuantas veces le han pedido escanear.
        self.escaneos = 0

    async def buscar_robot(self, timeout_ms: int = 0, paso_ms: int = 0, sondear: bool = True):
        if self.conn >= 0:
            return b"\x64\xe0\x39\x2d\x90\x80", 0
        return None, None

    async def conectar(self, addr: Any, addr_type: int = 0, timeout_ms: int = 0, scan_ms: int = 0):
        self.conn = 1
        return True

    async def descubrir(self, timeout_ms: int = 0) -> bool:
        return self.conn >= 0

    async def escribir(self, datos: Any, con_respuesta: bool = True, timeout_ms: int = 0) -> bool:
        if self.conn < 0:
            self.error = "no hay conexion"
            return False
        self.recibidos.append(bytes(datos))
        self.ultimo = bytes(datos)
        self.paquetes += 1
        return True

    def desconectar(self) -> None:
        self.conn = -1

    async def escanear(self, ms: int = 0) -> dict[Any, Any]:
        self.escaneos += 1
        return {b"\x64\xe0\x39\x2d\x90\x80": (0, "AIRo", -60)}

    def estado(self) -> dict[str, Any]:
        return {
            "conectado": self.conn >= 0,
            "mac": self.mac_robot,
            "nombre": self.nombre_robot,
            "rssi": self.rssi,
            "paquetes": self.paquetes,
            "ultimo_error": self.error or None,
            "servicio": [1, 2],
            "characteristic": self.caracteristica,
            "bytes_guardados": len(self.ultimo),
            "fallos": self.fallos,
        }


@pytest.fixture
async def puente(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Levanta el servidor HTTP del firmware en un puerto libre.

    Devuelve (url, cliente_falso): el cliente es el BLE de mentira, para
    poder ver que le llega al robot.
    """
    http_srv = cargar("http_srv")
    modulo_puente = cargar("puente")
    # Los tiempos de la placa se acortan para que los tests no tarden: en la
    # placa real `/conectar` espera 30 s a que el robot aparezca.
    monkeypatch.setattr(modulo_puente, "ESPERA_CONEXION_MS", 300)
    monkeypatch.setattr(modulo_puente, "ESCANEO_MS", 50)
    cliente = ClienteFalso()
    p = modulo_puente.Puente()
    p.cliente = cliente
    servidor = await asyncio.start_server(
        lambda r, w: http_srv._atender(r, w, p.rutas()),
        "127.0.0.1",
        0,
    )
    puerto = servidor.sockets[0].getsockname()[1]
    tarea = asyncio.create_task(servidor.serve_forever())
    try:
        yield f"http://127.0.0.1:{puerto}", cliente
    finally:
        tarea.cancel()
        servidor.close()
        await servidor.wait_closed()


# --- La configuracion ----------------------------------------------------------


def test_sin_variable_no_hay_puente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PUENTE_ENV, raising=False)
    assert url_del_puente() is None


def test_la_variable_apunta_al_puente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PUENTE_ENV, "http://airo-bridge.local:8080")
    assert url_del_puente() == "http://airo-bridge.local:8080"


def test_la_variable_vacia_no_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PUENTE_ENV, "   ")
    assert url_del_puente() is None


def test_con_variable_se_crea_el_cliente_del_puente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PUENTE_ENV, "http://airo-bridge.local:8080")
    assert isinstance(crear_robot(), BridgeRobot)


def test_sin_variable_se_crea_el_cliente_ble(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PUENTE_ENV, raising=False)
    robot = crear_robot()
    assert not isinstance(robot, BridgeRobot)


def test_la_sesion_usa_el_puente(monkeypatch: pytest.MonkeyPatch) -> None:
    """La sesion es el cliente del API web: tiene que hablar con el puente."""
    monkeypatch.setenv(PUENTE_ENV, "http://airo-bridge.local:8080")
    assert isinstance(RobotSession().robot, BridgeRobot)


# --- El cliente contra el servidor del firmware --------------------------------


async def test_el_cliente_habla_con_el_puente(puente: Any) -> None:
    """Las rutas del firmware y las del cliente tienen que encajar."""
    url, _cliente = puente
    robot = BridgeRobot(url)

    assert (await robot.salud())["ok"] is True

    estado = await robot.estado()
    assert estado["conectado"] is True
    assert estado["mac"] == "64:E0:39:2D:90:80"

    dispositivos = (await robot.escanear())["dispositivos"]
    assert dispositivos[0]["mac"] == "64:E0:39:2D:90:80"
    assert dispositivos[0]["nombre"] == "AIRo"


async def test_lo_que_manda_el_cliente_llega_al_robot(puente: Any) -> None:
    """Los bytes son los de `protocol.py`, sin tocar."""
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()

    comando = Command(right_speed=0.6, left_speed=0.6)
    await robot.send(comando)

    assert cliente.recibidos == [comando.to_bytes()]
    assert len(cliente.recibidos[0]) == 20


async def test_el_cliente_se_conecta(puente: Any) -> None:
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()
    assert robot.is_connected is True
    assert robot.address == "64:E0:39:2D:90:80"


async def test_sin_robot_no_se_conecta(puente: Any) -> None:
    """Si el puente no encuentra al robot, se avisa con `AiroNotFound`."""
    url, cliente = puente
    cliente.conn = -1
    robot = BridgeRobot(url)
    with pytest.raises(AiroNotFound):
        await robot.connect()


async def test_conectar_espera_al_robot(puente: Any) -> None:
    """La ruta `/conectar` espera a que la tarea de fondo pille al robot."""
    url, cliente = puente
    cliente.conn = -1

    async def aparece_dentro_de_un_rato() -> None:
        await asyncio.sleep(0.1)
        cliente.conn = 1

    tarea = asyncio.create_task(aparece_dentro_de_un_rato())
    robot = BridgeRobot(url)
    await robot.connect()
    await tarea
    assert robot.is_connected is True


async def test_la_ruta_de_conectar_no_escanea(puente: Any) -> None:
    """La ruta no escanea: el escaneo lo hace la tarea de fondo.

    Si las dos escanearan a la vez, NimBLE contestaria `EALREADY` (solo se
    admite un escaneo a la vez).
    """
    url, cliente = puente
    cliente.conn = -1
    robot = BridgeRobot(url)
    with pytest.raises(AiroNotFound):
        await robot.connect()
    assert cliente.escaneos == 0


async def test_escribir_sin_conexion_avisa(puente: Any) -> None:
    """Escribir sin robot conectado es un error claro, no un silencio."""
    url, cliente = puente
    cliente.conn = -1
    robot = BridgeRobot(url)
    with pytest.raises(AiroNotConnected):
        await robot.send(Command())


async def test_el_puente_que_no_responde_avisa() -> None:
    """Un puente apagado (o una IP equivocada) da un error entendible."""
    robot = BridgeRobot("http://127.0.0.1:9", timeout=1.0)
    with pytest.raises(AiroConnectionError):
        await robot.salud()


async def test_el_mismo_paquete_no_se_manda_dos_veces(puente: Any) -> None:
    """La placa reenvia sola el paquete: no hay que mandarlo cada 50 ms."""
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()

    comando = Command(right_speed=0.6, left_speed=0.6)
    await robot.send(comando)
    await robot.send(comando)
    await robot.send(comando)

    assert len(cliente.recibidos) == 1


async def test_un_paquete_distinto_si_se_manda(puente: Any) -> None:
    """Cuando el comando cambia, el paquete nuevo si que se manda."""
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()

    await robot.send(Command(right_speed=0.6, left_speed=0.6))
    await robot.send(Command(right_speed=0.6, left_speed=0.6))
    await robot.send(Command(left_speed=0.3, right_speed=0.3))

    assert len(cliente.recibidos) == 2


async def test_con_force_el_paquete_siempre_se_manda(puente: Any) -> None:
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()

    await robot.send(Command())
    await robot.send(Command(), force=True)

    assert len(cliente.recibidos) == 2


async def test_los_atajos_mueven_el_robot(puente: Any) -> None:
    """Los atajos (`drive`, `led`, `stop`...) funcionan igual que con BLE."""
    url, cliente = puente
    robot = BridgeRobot(url)
    await robot.connect()

    await robot.drive(left=1.0, right=1.0)
    await robot.led(Led.ON)
    await robot.stop()

    assert len(cliente.recibidos) == 3
    # parar manda las ruedas a cero
    assert cliente.recibidos[-1][2:6] == b"\x00\x00\x00\x00"


# --- El lado de la placa --------------------------------------------------------


async def test_la_placa_reenvia_el_paquete() -> None:
    """La tarea de refresco de la placa reenvía el último paquete.

    Es lo que hace que el robot no se duerma: el firmware del robot quiere
    paquetes seguidos, y quien los manda ahora es la placa, no el portátil.
    """
    ble = cargar("ble_robot")
    modulo_puente = cargar("puente")

    cliente = ble.ClienteAiro()
    await cliente.conectar(b"\x64\xe0\x39\x2d\x90\x80", 0, 2000, 100)
    await cliente.descubrir(1000)
    await cliente.escribir(b"\xa5\x01")
    assert len(cliente.ble.escrituras) == 1

    p = modulo_puente.Puente()
    p.cliente = cliente
    tarea = asyncio.create_task(p.refrescar())
    try:
        await asyncio.sleep(0.15)
    finally:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass

    # el refresco ha mandando el mismo paquete mas de una vez
    assert len(cliente.ble.escrituras) > 1
    assert all(e[2] == b"\xa5\x01" for e in cliente.ble.escrituras)


# --- La cadena entera: sesion y API -> puente -> placa -------------------------


async def test_la_sesion_habla_con_el_puente(
    puente: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La sesion (lo que usa la API web) habla con el puente, no con el BLE."""
    url, cliente = puente
    monkeypatch.setenv(PUENTE_ENV, url)

    sesion = RobotSession()
    assert isinstance(sesion.robot, BridgeRobot)
    await sesion.conectar()
    try:
        assert sesion.estado()["conectado"] is True
    finally:
        await sesion.desconectar()


async def test_mover_llega_al_robot_como_20_bytes(
    puente: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un "avanzar" de la sesion llega a la placa como un paquete de 20 bytes.

    Es la cadena completa: la sesion construye el comando, el puente lo
    serializa y lo manda, y la placa lo escribe en el robot.
    """
    url, cliente = puente
    monkeypatch.setenv(PUENTE_ENV, url)

    sesion = RobotSession()
    await sesion.conectar()
    try:
        await sesion.mover(izquierda=1.0, derecha=1.0)
        await asyncio.sleep(0.2)
    finally:
        await sesion.desconectar()

    assert cliente.recibidos, "no llego ningun paquete"
    # el paquete de avanzar: el de la rueda izquierda es [2]=1 y [3]=1
    assert len(cliente.recibidos[0]) == 20
    assert cliente.recibidos[0][:2] == b"\xa5\x00"


async def test_la_api_habla_con_el_puente(
    puente: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La API web (que es lo que ve el niño) va al puente si lo hay."""
    url, cliente = puente
    monkeypatch.setenv(PUENTE_ENV, url)

    servicio = RobotService()
    await servicio.conectar()
    try:
        estado = servicio.estado()
        assert estado["conectado"] is True
        assert estado["luz"] == "off"
    finally:
        await servicio.desconectar()
