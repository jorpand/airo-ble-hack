"""
Cliente BLE para el Clementoni AIRO 1.x.

Uso mínimo:

    import asyncio
    from airo_ble import AiroRobot, Joint, Led

    async def main():
        async with AiroRobot() as robot:
            await robot.drive(left=1.0, right=1.0)
            await asyncio.sleep(2)
            await robot.servo(Joint.RIGHT_SHOULDER, 45)
            await robot.led(Led.ON)
            await robot.stop()

    asyncio.run(main())

Requiere `bleak` (Linux: `pip install bleak`; en Windows/Docker usa
`bleak[backend]` con WinRT).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .protocol import (
    ROBOT_NAME,
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
    Command,
    Joint,
    Led,
)

__all__ = [
    "AiroRobot",
    "AiroError",
    "AiroNotFound",
    "AiroNotConnected",
    "AiroConnectionError",
    "AiroWriteError",
]


class AiroError(RuntimeError):
    """Error base del cliente BLE.

    Todos los errores del cliente heredan de aqui (y de `RuntimeError`, como
    antes), asi que se pueden distinguir por tipo sin depender del texto del
    mensaje.
    """


class AiroNotFound(AiroError):
    """No se encontró ningún robot AIRO en el rango de escaneo."""


class AiroNotConnected(AiroError):
    """Se ha pedido enviar algo sin estar conectado."""


class AiroConnectionError(AiroError):
    """No se pudo conectar con el robot."""


class AiroWriteError(AiroError):
    """Falló (o se colgó) la escritura en la characteristic."""


class AiroRobot:
    """Envoltorio async sobre bleak con el protocolo de AIRO."""

    #: Este cliente lleva el enlace BLE el mismo, asi que puede (y debe)
    #: soltar la conexion para reconectar. El cliente del puente no: ahi la
    #: conexion la lleva la placa.
    conexion_gestionada = False

    def __init__(
        self,
        *,
        name: str = ROBOT_NAME,
        address: str | None = None,
        scan_timeout: float = 15.0,
        connect_timeout: float = 30.0,
        connect_retries: int = 3,
        write_with_response: bool = True,
        write_timeout: float = 10.0,
        min_write_interval: float = 0.05,
    ) -> None:
        self.name = name
        self.address = address
        self.scan_timeout = scan_timeout
        self.connect_timeout = connect_timeout
        self.connect_retries = connect_retries
        self.write_with_response = write_with_response
        self.write_timeout = write_timeout
        self.min_write_interval = min_write_interval

        self._client: Any = None
        self._characteristic: Any = None
        self._command = Command()
        self._last_write = 0.0
        self._lock = asyncio.Lock()
        #: Direccion -> (dispositivo, rssi, momento). Es un diccionario y no
        #: una lista porque el robot se anuncia MUCHAS veces por segundo:
        #: con una lista crecia sin limite y `_wait_for_robot` devolvia
        #: siempre el ultimo anuncio (que podia ser de hace medio minuto).
        self._seen: dict[str, tuple[Any, int, float]] = {}

    # -- ciclo de vida ---------------------------------------------------

    async def __aenter__(self) -> AiroRobot:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Si el enlace BLE con el robot está vivo."""
        return self._client is not None and bool(
            getattr(self._client, "is_connected", False)
        )

    async def connect(self) -> None:
        """Escanea, conecta y localiza servicio/characteristic.

        El escaneo se mantiene **activo durante la conexión**: BlueZ borra
        del árbol de D-Bus los dispositivos que ha creado al descubrir si
        paras el descubrimiento antes de conectar, y entonces la conexión
        falla con "device not found".

        El HM-10 del robot además es lento: se duerme, tarda en anunciar y
        BlueZ a veces se queda colgado en el primer intento. Por eso hay
        reintentos y un timeout de conexión holgado.
        """
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError as exc:  # pragma: no cover
            raise AiroError(
                "Falta bleak: pip install bleak  (Linux: sudo apt install python3-bleak)"
            ) from exc

        # si ya estamos conectados, no hay nada que hacer (conectar dos veces
        # sobre el mismo modulo HM-10 deja el enlace a medias)
        if self._client is not None and getattr(self._client, "is_connected", False):
            return

        self._seen = {}
        scanner = BleakScanner(detection_callback=self._on_device)
        await scanner.start()
        try:
            target = await self._wait_for_robot()
            if target is None:
                raise AiroNotFound(
                    f"No se ha encontrado ningún dispositivo anunciado como "
                    f"{self.name!r}. ¿Está encendido y con el LED azul "
                    f"parpadeando? (su módulo BLE se duerme si no hay conexión: "
                    f"apágago y enciéndelo)"
                )

            last_error: Exception | None = None
            for attempt in range(self.connect_retries):
                # en cada intento reescaneamos: si hay que borrar el
                # dispositivo de la cache de BlueZ, hay que redescubrirlo
                if attempt:
                    target = await self._wait_for_robot(reset=True)
                self._client = BleakClient(target, timeout=self.connect_timeout)
                try:
                    await self._client.connect()
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    self._client = None
                    if attempt + 1 < self.connect_retries:
                        if "in progress" in str(exc).lower():
                            # BlueZ tiene una conexion a medias: la cancelamos
                            # borrando el dispositivo de su cache
                            direccion = self.address or str(
                                getattr(target, "address", "") or ""
                            )
                            if direccion:
                                await self._forget_device(direccion)
                            await asyncio.sleep(3.0)
                        else:
                            await asyncio.sleep(2.0)
            if last_error is not None:
                hint = ""
                nombre = type(last_error).__name__
                if nombre == "BleakDeviceNotFoundError":
                    hint = (
                        " El robot parece conectado a otro programa (o con un "
                        "enlace zombi): apágalo, enciéndelo de nuevo y reintenta."
                    )
                elif "in progress" in str(last_error).lower():
                    hint = (
                        " El módulo BLE del robot sigue enganchado con una conexión "
                        "anterior: apaga y enciende el robot y reintenta."
                    )
                elif "not found" in str(last_error):
                    hint = (
                        " BlueZ no tiene el dispositivo en su caché: ejecuta "
                        "`bluetoothctl --timeout 10 scan on` o reinicia el robot."
                    )
                raise AiroConnectionError(
                    f"No se pudo conectar con el robot: {last_error}.{hint}"
                ) from last_error
        finally:
            await scanner.stop()

        # bleak puede "conectar" y quedarse colgado sin avisar: lo
        # comprobamos, porque luego las escrituras fallarian sin saber por que
        cliente = self._client
        if cliente is None or not getattr(cliente, "is_connected", True):
            self._client = None
            raise AiroConnectionError(
                "El enlace BLE se ha establecido pero no ha quedado conectado. "
                "Apaga y enciende el robot e inténtalo de nuevo."
            )

        service = self._find_service()
        if service is None:
            raise AiroConnectionError(
                f"El robot no expone el servicio {SERVICE_UUID}. "
                f"Servicios vistos: {[s.uuid for s in cliente.services]}"
            )
        self._characteristic = self._find_characteristic(service)
        if self._characteristic is None:
            raise AiroConnectionError(
                f"El robot no expone la characteristic {WRITE_CHARACTERISTIC_UUID}. "
                f"Characteristics del servicio: {[c.uuid for c in service.characteristics]}"
            )
        # guarda la MAC real (si nos pasaron la direccion a mano, se corrige)
        self.address = getattr(cliente, "address", self.address)

    async def reconnect(self) -> None:
        """Cierra la conexion y vuelve a conectar.

        El módulo HM-10 del robot se duerme: si el enlace se queda colgado,
        lo que funciona es cerrar bien (que ademas pide a BlueZ que olvide el
        dispositivo) y volver a escanear desde cero.
        """
        await self.disconnect()
        await self.connect()

    def _on_device(self, device: Any, advertisement_data: Any) -> None:
        """Callback del escaneo: guarda los dispositivos que nos interesan.

        Se guarda **uno por direccion** (con su RSSI y el momento de la
        anuncio), no una lista: el robot se anuncia varias veces por segundo y
        la lista crecia sin limite.
        """
        name = getattr(advertisement_data, "local_name", None) or getattr(device, "name", None)
        address = str(getattr(device, "address", "")).lower()
        if name == self.name or (self.address and address == self.address.lower()):
            rssi = getattr(advertisement_data, "rssi", None)
            try:
                rssi = int(rssi) if rssi is not None else -999
            except (TypeError, ValueError):
                rssi = -999
            self._seen[address] = (device, rssi, time.monotonic())

    def _mejor_dispositivo(self, max_antiguedad: float | None = None) -> Any:
        """El dispositivo con mejor RSSI entre los que no son tan viejos.

        A igualdad de RSSI gana el mas reciente. `max_antiguedad` descarta
        los anuncios viejos: un robot que se anuncia hace 30 segundos puede
        haberse apagado ya.
        """
        if not self._seen:
            return None
        ahora = time.monotonic()
        mejor: Any = None
        mejor_clave: tuple[int, float] | None = None
        for device, rssi, momento in self._seen.values():
            if max_antiguedad is not None and ahora - momento > max_antiguedad:
                continue
            clave = (rssi, momento)
            if mejor_clave is None or clave > mejor_clave:
                mejor_clave, mejor = clave, device
        return mejor

    async def _wait_for_robot(self, reset: bool = False) -> Any:
        """Espera a que aparezca el robot en el escaneo.

        `reset=True` olvida lo visto antes (para los reintentos, cuando se ha
        borrado el dispositivo de la cache de BlueZ y hay que redescubrirlo).
        """
        loop = asyncio.get_running_loop()
        if reset:
            self._seen.clear()
        deadline = loop.time() + self.scan_timeout
        while loop.time() < deadline:
            device = self._mejor_dispositivo(max_antiguedad=self.scan_timeout)
            if device is not None:
                return device
            await asyncio.sleep(0.2)
        # no lo hemos visto en el escaneo: si nos han dado una MAC, se intenta
        # igualmente (a lo mejor solo llevaba un momento dormido)
        return self.address

    def _find_service(self) -> Any:
        """Busca el servicio FFF0.

        Hay módulos HM-10 que exponen FFF0/FFF1 con el base UUID estándar de
        Bluetooth (00805f9b34fb) y otros con el base a ceros
        (000000000000). El mismo robot puede usar uno u otro según cómo se
        haya reiniciado, así que se acepta cualquiera de los dos.
        """
        service = self._client.services.get_service(SERVICE_UUID)
        if service is not None:
            return service
        for candidate in self._client.services:
            if str(candidate.uuid).upper().startswith("0000FFF0"):
                return candidate
        return None

    def _find_characteristic(self, service: Any) -> Any:
        """Busca la characteristic FFF1 (la de escritura) en el servicio."""
        characteristic = service.get_characteristic(WRITE_CHARACTERISTIC_UUID)
        if characteristic is not None:
            return characteristic
        for candidate in service.characteristics:
            if str(candidate.uuid).upper().startswith("0000FFF1"):
                return candidate
        return None

    async def disconnect(self) -> None:
        if self._client is not None:
            address = str(getattr(self._client, "address", "") or self.address or "")
            try:
                await self.send(self._command.stop(), force=True)
            except Exception:  # pragma: no cover - el robot ya puede estar fuera de rango
                pass
            try:
                # BlueZ puede quedarse esperando: no queremos bloquear la salida.
                await asyncio.wait_for(self._client.disconnect(), timeout=10)
            except Exception:  # pragma: no cover
                pass
            # Si el enlace sigue vivo, el robot no admitira nuevas conexiones
            # ("Operation already in progress"). Hay que insistir y, si hace
            # falta, olvidarse del dispositivo en BlueZ: asi la siguiente
            # sesion lo redescubre limpio.
            for _ in range(3):
                if self._client is None or not getattr(self._client, "is_connected", False):
                    break
                try:
                    await asyncio.wait_for(self._client.disconnect(), timeout=5)
                except Exception:  # pragma: no cover
                    pass
                await asyncio.sleep(1.0)
            self._client = None
            self._characteristic = None
            if address:
                await self._forget_device(address)

    async def _forget_device(self, address: str) -> None:
        """Pide a BlueZ que olvide el dispositivo (desbloquea el enlace).

        Hay que hablar con el **bus del sistema**: BlueZ vive ahi, no en el
        bus de sesion del usuario.
        """
        try:
            from dbus_fast import BusType, Message
            from dbus_fast.aio import MessageBus
        except ImportError:  # pragma: no cover
            return
        try:
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await bus.call(
                Message(
                    destination="org.bluez",
                    path="/org/bluez/hci0",
                    interface="org.bluez.Adapter1",
                    member="RemoveDevice",
                    signature="o",
                    body=["/org/bluez/hci0/dev_" + address.replace(":", "_").upper()],
                )
            )
            bus.disconnect()
        except Exception as exc:  # pragma: no cover - si falla, no es critico
            print(f"[airo] no se pudo limpiar BlueZ: {exc}", flush=True)

    # -- envío -----------------------------------------------------------

    async def send(self, command: Command, *, force: bool = False) -> bytes:
        """Envía un comando al robot y devuelve los bytes escritos."""
        if self._characteristic is None:
            raise AiroNotConnected("No conectado: llama antes a connect()")
        return await self._escribir(command.to_bytes(), force=force)

    async def send_raw(self, payload: bytes, *, force: bool = False) -> bytes:
        """Escribe bytes tal cual en la characteristic (para depurar)."""
        if self._characteristic is None:
            raise AiroNotConnected("No conectado: llama antes a connect()")
        return await self._escribir(bytes(payload), force=force)

    async def _escribir(self, payload: bytes, *, force: bool = False) -> bytes:
        """La escritura de verdad, con el ritmo y el bloqueo.

        El ritmo (`min_write_interval`) se aplica **dentro** del lock: antes
        se hacia fuera, asi que dos envios concurrentes podian escribir casi a
        la vez (el segundo se habia calculado el `now` antes de que el
        primero escribiera). Y `_last_write` se actualiza **despues** de
        escribir, no antes, para que el intervalo sea real.
        """
        loop = asyncio.get_running_loop()
        async with self._lock:
            if not force:
                espera = self.min_write_interval - (loop.time() - self._last_write)
                if espera > 0:
                    await asyncio.sleep(espera)
            try:
                # `write_gatt_char` es la API estable de bleak (0.19 -> 3.x);
                # en bleak 3.x `characteristic.write_value` ya no existe.
                #
                # Con respuesta, un modulo HM-10 que se duerme puede dejar la
                # escritura colgada para siempre: por eso hay timeout.
                await asyncio.wait_for(
                    self._client.write_gatt_char(
                        self._characteristic,
                        payload,
                        response=self.write_with_response,
                    ),
                    timeout=self.write_timeout,
                )
            except TimeoutError as exc:
                raise AiroWriteError(
                    f"El robot no respondió en {self.write_timeout:g} s al "
                    "escribir. Su módulo BLE se duerme: apaga y enciende el "
                    "robot e inténtalo de nuevo."
                ) from exc
            except Exception as exc:
                raise AiroWriteError(f"No se pudo escribir en el robot: {exc}") from exc
            finally:
                # el ritmo se cuenta desde el final de la escritura, haya
                # terminado bien o mal
                self._last_write = loop.time()
        return payload

    # -- API de alto nivel ----------------------------------------------

    @property
    def command(self) -> Command:
        """El último estado compuesto (para inspeccionarlo)."""
        return self._command

    @command.setter
    def command(self, value: Command) -> None:
        """Sustituye el estado compuesto (por ejemplo, para hacer un reset)."""
        self._command = value

    async def drive(self, *, left: float = 0.0, right: float = 0.0) -> bytes:
        """Mueve las ruedas. Rango útil de velocidad: -3..3 (signo = sentido)."""
        self._command.left_speed = left
        self._command.right_speed = right
        return await self.send(self._command)

    async def servo(self, joint: Joint, angle: float) -> bytes:
        """Mueve una articulación a un ángulo en grados."""
        self._command.set_joint(joint, angle)
        return await self.send(self._command)

    async def servos(self, **angles: float) -> bytes:
        """Mueve varias articulaciones de golpe: `servos(left_arm=30, ...)`.

        Los nombres aceptados son los de `Joint` en minúsculas con guion bajo.
        """
        for key, value in angles.items():
            joint = Joint[key.upper()]
            self._command.set_joint(joint, value)
        return await self.send(self._command)

    async def led(self, mode: Led) -> bytes:
        """Apaga/enciende/parpadea/funde el LED azul."""
        self._command.led = mode
        return await self.send(self._command)

    async def stop(self) -> bytes:
        """Para las ruedas."""
        self._command.stop()
        return await self.send(self._command)

    async def reset(self) -> bytes:
        """Equivalente a `BleRobot.ResetStatus`: servos a 0 y ruedas paradas."""
        self._command = Command()
        return await self.send(self._command, force=True)
