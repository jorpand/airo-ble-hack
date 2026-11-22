"""
La interfaz común de los clientes del robot.

Hay dos formas de hablar con el robot, y **se usan igual**:

- `airo_ble.client.AiroRobot`: BLE directo, con `bleak` (el portátil tiene
  Bluetooth).
- `airo_ble.bridge.BridgeRobot`: a través del puente del ESP32-S3 (el
  portátil no necesita Bluetooth; la placa, que está al lado del robot,
  habla BLE).

Los dos tienen los mismos métodos, los mismos errores y el mismo ciclo de
vida:

| | `AiroRobot` (BLE) | `BridgeRobot` (ESP32) |
|---|---|---|
| `connect()` | busca el robot, conecta y descubre `FFF0`/`FFF1` | lo mismo, pero lo hace la placa |
| `disconnect()` | cierra el enlace BLE | le dice a la placa que lo cierre |
| `send()` | escribe los 20 bytes con respuesta | se los manda a la placa por HTTP |
| `send_raw()` | escribe bytes tal cual | igual, por HTTP |
| `drive`, `servo`, `servos`, `led`, `stop` | atajos sobre `command` | los mismos |

Los errores son los mismos tipos en los dos casos (`AiroNotFound`,
`AiroConnectionError`, `AiroNotConnected`, `AiroWriteError`), así que el
código que llama al robot no tiene que saber por dónde va.

Esta clase base está para que los dos no se separen sin que se note: el test
`tests/test_bridge.py` compara sus interfaces y falla si uno tiene un método
que el otro no.
"""

from __future__ import annotations

from typing import Any

from .protocol import Command, Joint, Led

__all__ = ["ClienteRobot"]


class ClienteRobot:
    """Lo que tienen en común todos los clientes del robot.

    Lo que cambia entre unos y otros (cómo se habla con el robot) se
    implementa en los hijos; lo que no cambia (los atajos, el ciclo de vida)
    vive aquí.
    """

    #: Si el enlace BLE lo lleva **otro** (la placa del puente), el cliente
    #: no debe soltar la conexión cuando algo falla: se la arrancaría de las
    #: manos a quien la tiene (la placa, que ya la ha establecido).
    conexion_gestionada = False

    #: La URL del puente, si el enlace lo lleva otro. Vacío si el cliente
    #: habla BLE directamente. Sirve para que el estado diga por dónde van
    #: las cosas sin tener que preguntar de qué tipo es el cliente.
    url = ""

    def __init__(self) -> None:
        #: El comando con el que se construyen los bytes. Quien lo usa
        #: cambia sus campos y lo manda.
        self.command = Command()
        #: La MAC del robot (o la URL del puente, si aun no se ha conectado).
        #: `None` = todavia no se sabe (se busca por nombre).
        self.address: str | None = None

    # -- lo que implementa cada uno ---------------------------------------

    @property
    def is_connected(self) -> bool:
        """Si el robot está conectado ahora mismo."""
        raise NotImplementedError

    async def connect(self) -> None:
        """Conecta con el robot (lo busca si hace falta).

        Raises:
            AiroNotFound: si no aparece ningún robot.
            AiroConnectionError: si se encuentra pero no se puede conectar.
        """
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Cierra la conexión con el robot."""
        raise NotImplementedError

    async def reconnect(self) -> None:
        """Cierra la conexión y vuelve a conectar."""
        await self.disconnect()
        await self.connect()

    async def send(self, command: Command, *, force: bool = False) -> bytes:
        """Manda un comando al robot y devuelve los bytes escritos.

        Raises:
            AiroNotConnected: si no hay conexión.
            AiroWriteError: si el robot no acepta el paquete.
        """
        raise NotImplementedError

    async def send_raw(self, payload: bytes, *, force: bool = False) -> bytes:
        """Escribe bytes tal cual (para depurar)."""
        raise NotImplementedError

    async def escanear(self, timeout: float = 10.0) -> dict[str, Any]:
        """Escanea y devuelve lo que se ve.

        Returns:
            `{"dispositivos": [{"mac": str, "nombre": str, "rssi": int}]}`
        """
        raise NotImplementedError

    async def estado(self) -> dict[str, Any]:
        """El estado de la conexión con el robot."""
        raise NotImplementedError

    async def salud(self) -> dict[str, Any]:
        """Comprueba que el cliente vive (no que el robot esté)."""
        raise NotImplementedError

    # -- los atajos (los mismos para todos) --------------------------------

    async def drive(self, *, left: float = 0.0, right: float = 0.0) -> bytes:
        """Mueve las ruedas. Rango útil de velocidad: -3..3 (signo = sentido)."""
        self.command.left_speed = left
        self.command.right_speed = right
        return await self.send(self.command)

    async def servo(self, joint: Joint, angle: float) -> bytes:
        """Mueve una articulación a un ángulo en grados."""
        self.command.set_joint(joint, angle)
        return await self.send(self.command)

    async def servos(self, **angles: float) -> bytes:
        """Mueve varias articulaciones de golpe: `servos(left_arm=30, ...)`."""
        for key, value in angles.items():
            self.command.set_joint(Joint[key.upper()], value)
        return await self.send(self.command)

    async def led(self, mode: Led) -> bytes:
        """Apaga/enciende/parpadea/funde el LED azul."""
        self.command.led = mode
        return await self.send(self.command)

    async def stop(self) -> bytes:
        """Para las ruedas."""
        self.command.stop()
        return await self.send(self.command)

    async def reset(self) -> bytes:
        """Equivalente a `BleRobot.ResetStatus`: servos a 0 y ruedas paradas."""
        self.command = Command()
        return await self.send(self.command, force=True)

    # -- el contexto asíncrono ---------------------------------------------

    async def __aenter__(self) -> ClienteRobot:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()
