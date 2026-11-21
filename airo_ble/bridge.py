"""
Cliente del puente BLE del ESP32-S3, desde el portátil.

El puente es un ESP32-S3 con MicroPython que habla con el robot y al que se
le pueden mandar bytes por HTTP (ver `firmware/esp32/` y `docs/plan-esp32.md`).
Este módulo es el otro extremo: habla con ese puente y se comporta como un
`AiroRobot`, de modo que todo lo que usa el cliente BLE directo (la consola,
la API web, el puente de Scratch) puede hablar con el robot a través del
ESP32 sin tocar una sola línea.

Se activa con la variable de entorno `AIRO_BRIDGE_URL`:

    AIRO_BRIDGE_URL=http://airo-bridge.local:8080 python -m airo_ble.console

Sin esa variable, todo sigue yendo por BLE directo como siempre.

La idea es que **el protocolo se queda en el portátil**: el ESP32 no sabe qué
significa un byte, solo los escribe en la characteristic `FFF1`. Los 20 bytes
los sigue construyendo `airo_ble/protocol.py`, que es la única fuente de la
verdad (asi que el ESP32 no se queda obsoleto cuando el protocolo cambie).

El tráfico va con calma a propósito: la placa reenvía sola el último paquete
cada 50 ms (el robot quiere paquetes seguidos), así que aquí solo se manda el
paquete cuando **cambia**, más un latido de seguridad de 1 Hz.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .client import (
    AiroConnectionError,
    AiroError,
    AiroNotConnected,
    AiroNotFound,
    AiroRobot,
    AiroWriteError,
)
from .protocol import Command, Joint, Led

__all__ = [
    "BridgeRobot",
    "PUENTE_ENV",
    "crear_robot",
    "url_del_puente",
]


#: La variable de entorno que apunta al puente.
PUENTE_ENV = "AIRO_BRIDGE_URL"

#: Cuanto se espera a la respuesta del puente, en segundos.
TIMEOUT = 20.0

#: Cuanto se espera a la ruta `/conectar`, en segundos.
#:
#: Conectar es lento a proposito: el modulo BLE del robot se duerme y solo
#: se anuncia unos segundos despues de encenderlo, asi que la placa espera a
#: que aparezca.
TIMEOUT_CONEXION = 60.0

#: Cada cuanto se manda el paquete otra vez aunque no haya cambiado.
#:
#: La placa reenvía sola el último paquete, así que esto no hace falta para
#: que el robot reciba paquetes: es la red de seguridad por si el ESP32 se
#: ha reiniciado y ha perdido el paquete que tenía guardado.
REENVIO_S = 1.0


def url_del_puente() -> str | None:
    """La URL del puente, si la hay. `None` si no hay puente configurado."""
    url = (os.environ.get(PUENTE_ENV) or "").strip()
    return url or None


class BridgeRobot:
    """Habla con el robot a través del puente del ESP32-S3.

    Se usa igual que un `AiroRobot`: tiene `.command`, `.connect()`,
    `.disconnect()` y `.send()`. La diferencia es que no habla BLE: le
    manda los bytes al puente por HTTP y el puente los escribe en el robot.
    """

    def __init__(self, url: str, timeout: float = TIMEOUT) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        #: El comando con el que se construyen los bytes (igual que en
        #: `AiroRobot`): quien lo usa cambia sus campos y lo manda.
        self.command = Command()
        #: La MAC del robot (la dice el puente al conectar). Antes de
        #: conectar, es la URL del puente.
        self.address = self.url
        self._conectado = False
        #: El último paquete mandado y cuándo se mandó (para no repetirlo).
        self._ultimo: bytes | None = None
        self._ultimo_envio = 0.0

    # -- ciclo de vida ----------------------------------------------------

    async def __aenter__(self) -> BridgeRobot:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Si el puente tiene el robot conectado."""
        return self._conectado

    async def connect(self) -> None:
        """Busca el robot y se conecta (a través del puente).

        El puente se encarga de escanear y de reconectar solo: aquí solo se
        le pide que se conecte y se espera a que lo consiga.
        """
        datos = await self._peticion("POST", "/conectar", timeout=TIMEOUT_CONEXION)
        if not datos.get("ok"):
            error = str(datos.get("error") or "no se pudo conectar")
            if "no se encuentra" in error:
                raise AiroNotFound(
                    f"El puente no encuentra al robot: {error}. "
                    "Enciéndelo y mira que tenga el LED azul parpadeando."
                )
            raise AiroConnectionError(f"No se pudo conectar con el robot: {error}")
        self._conectado = True
        mac = str(datos.get("mac") or "")
        if mac:
            self.address = mac

    async def disconnect(self) -> None:
        """Cierra la conexión con el robot (el puente sigue encendido)."""
        try:
            await self._peticion("POST", "/desconectar")
        finally:
            self._conectado = False

    async def reconnect(self) -> None:
        """Cierra la conexión y vuelve a conectar."""
        await self.disconnect()
        await self.connect()

    # -- envio ------------------------------------------------------------

    async def send(self, command: Command | None = None, *, force: bool = False) -> bytes:
        """Manda el paquete al robot y devuelve los bytes escritos.

        Si el paquete es **igual** al último y este se mandó hace poco, no se
        manda nada: la placa ya lo está reenviando sola. Con `force=True` se
        manda siempre (por si acaso).
        """
        cmd = command if command is not None else self.command
        datos = cmd.to_bytes()
        ahora = asyncio.get_running_loop().time()
        if (
            not force
            and datos == self._ultimo
            and (ahora - self._ultimo_envio) < REENVIO_S
        ):
            return datos
        respuesta = await self._peticion("POST", "/escribir", datos)
        if not respuesta.get("ok"):
            # El paquete se da por no entregado: el siguiente intento lo
            # manda otra vez, sin esperar al latido de seguridad.
            self._ultimo = None
            error = str(respuesta.get("error") or "no se pudo escribir")
            if "no hay conexion" in error or "no hay conexión" in error:
                self._conectado = False
                raise AiroNotConnected(
                    "El puente no tiene el robot conectado: "
                    f"{error}. Enciéndelo y espera a que el puente lo pille."
                )
            raise AiroWriteError(f"No se pudo escribir en el robot: {error}")
        self._ultimo = datos
        self._ultimo_envio = ahora
        self._conectado = True
        return datos

    async def send_raw(self, payload: bytes, *, force: bool = False) -> bytes:
        """Escribe bytes tal cual (para depurar)."""
        datos = bytes(payload)
        ahora = asyncio.get_running_loop().time()
        if (
            not force
            and datos == self._ultimo
            and (ahora - self._ultimo_envio) < REENVIO_S
        ):
            return datos
        respuesta = await self._peticion("POST", "/escribir", datos)
        if not respuesta.get("ok"):
            self._ultimo = None
            raise AiroWriteError(
                f"No se pudo escribir en el robot: {respuesta.get('error')}"
            )
        self._ultimo = datos
        self._ultimo_envio = ahora
        return datos

    # -- atajos (los mismos que tiene `AiroRobot`) ------------------------

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

    # -- informacion ------------------------------------------------------

    async def estado(self) -> dict[str, Any]:
        """El estado del puente (conexión, paquetes, errores...)."""
        datos = await self._peticion("GET", "/estado")
        self._conectado = bool(datos.get("conectado"))
        return datos

    async def salud(self) -> dict[str, Any]:
        """Comprueba que el puente vive (no que el robot esté)."""
        return await self._peticion("GET", "/salud")

    async def escanear(self) -> dict[str, Any]:
        """Lo que se ve por BLE ahora mismo."""
        return await self._peticion("GET", "/escanear")

    # -- HTTP -------------------------------------------------------------

    async def _peticion(
        self,
        metodo: str,
        ruta: str,
        cuerpo: bytes | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Llama al puente y devuelve el JSON de la respuesta.

        Los errores del puente (409 con un `{"error": ...}`) se devuelven
        tal cual: quien llama decide si son un error fatal o no.

        La llamada va en un hilo (`urllib` es bloqueante): si se hiciera en
        el event loop, cada peticion al puente pararia toda la API web.
        """
        return await asyncio.to_thread(
            self._peticion_sync, metodo, ruta, cuerpo, timeout
        )

    def _peticion_sync(
        self,
        metodo: str,
        ruta: str,
        cuerpo: bytes | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """La llamada HTTP de verdad (bloqueante)."""
        peticion = urllib.request.Request(f"{self.url}{ruta}", method=metodo)
        if cuerpo is not None:
            peticion.data = cuerpo
            peticion.add_header("Content-Type", "application/octet-stream")
        try:
            with urllib.request.urlopen(
                peticion, timeout=timeout if timeout is not None else self.timeout
            ) as respuesta:
                texto = respuesta.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            # El puente responde 4xx con el error en el cuerpo: se lee igual.
            texto = exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            raise AiroConnectionError(
                f"No se pudo hablar con el puente ({self.url}): {exc.reason}. "
                f"¿Está el ESP32 encendido? ¿{PUENTE_ENV} apunta bien?"
            ) from exc
        except OSError as exc:
            raise AiroConnectionError(
                f"No se pudo hablar con el puente ({self.url}): {exc}"
            ) from exc
        try:
            datos = json.loads(texto) if texto.strip() else {}
        except json.JSONDecodeError as exc:
            raise AiroError(
                f"El puente ({self.url}) respondió algo que no es JSON: {texto[:120]!r}"
            ) from exc
        if not isinstance(datos, dict):
            raise AiroError(f"El puente ({self.url}) respondió una cosa rara: {datos!r}")
        return datos


def crear_robot(
    address: str | None = None,
    scan_timeout: float = 15.0,
    **kwargs: Any,
) -> AiroRobot | BridgeRobot:
    """Crea el cliente del robot.

    Si está `AIRO_BRIDGE_URL`, el cliente habla con el puente del ESP32-S3;
    si no, habla BLE directo como siempre. Es el único punto donde se decide,
    para que la consola, la API web y el puente de Scratch se comporten
    igual sin tocar su código.
    """
    url = url_del_puente()
    if url:
        return BridgeRobot(url)
    return AiroRobot(address=address, scan_timeout=scan_timeout, **kwargs)
