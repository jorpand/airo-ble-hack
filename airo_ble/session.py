"""
Sesión del robot: conexión BLE, refresco continuo y ejecución de programas.

Esto es lo que usan la consola, el servidor de Scratch y la API web, para que
la lógica de hablar con el robot vivan **en un solo sitio** y la librería
`airo_ble` siga siendo importable desde cualquier proyecto (sin dependencias
de web ni de interfaz).

    from airo_ble.session import RobotSession

    sesion = RobotSession()
    await sesion.conectar()
    await sesion.mover(izquierda=2, derecha=2, segundos=2)
    await sesion.desconectar()
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .bridge import BridgeRobot, crear_robot
from .client import AiroRobot
from .protocol import SERVO_CENTER, Joint, Led

__all__ = [
    "RobotSession",
    "Step",
    "POSE_NATURAL",
    "NIVELES",
    "ESPERA_MINIMA_LED",
]


#: Cuanto se queda un cambio de luz antes de dar el siguiente paso.
#:
#: El firmware interpola el `flash`/`fade` a partir de los paquetes que
#: llegan, asi que un cambio de luz sin tiempo no llega a verse. El kata de
#: la app oficial usa 0,4 s.
ESPERA_MINIMA_LED = 0.4



#: Cuanto se mueve el robot: la app solo tiene tres niveles de velocidad.
NIVELES: dict[str, float] = {"poquito": 1.0, "normal": 2.0, "mucho": 3.0}

#: Poses de los brazos, en lenguaje natural (sin grados para el usuario).
POSE_NATURAL: dict[str, str] = {
    "arriba": "arriba",
    "abajo": "abajo",
    "medio": "medio",
    "golpe": "golpe",
    "guardia": "guardia",
    "saludo": "arriba",
}

#: Traduccion de los nombres naturales a los de `airo_ble.protocol`.
_ARTICULACIONES: dict[str, Joint] = {
    "izquierdo": Joint.LEFT_SHOULDER,
    "derecho": Joint.RIGHT_SHOULDER,
    "brazo_izquierdo": Joint.LEFT_ARM,
    "brazo_derecho": Joint.RIGHT_ARM,
}


@dataclass
class Step:
    """Un paso de un programa.

    `kind` es lo que hay que hacer y `duracion` cuánto tiempo (en segundos).

    Ojo con lo que significa `duracion` segun el paso: en `mover` es el
    tiempo que se anda, en `espera` el que se espera y en `luz` lo que se
    queda la luz. En `brazo` es el **tiempo pedido** para el movimiento: 0
    significa "de golpe" (y entonces la sesion espera lo que tarde el servo
    en llegar) y cualquier otro valor es un movimiento lento, en rampa,
    durante ese tiempo.
    """

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    duracion: float = 0.0


class RobotSession:
    """Mantiene la conexion con el robot y ejecuta programas."""

    def __init__(
        self,
        address: str | None = None,
        scan_timeout: float = 10.0,
        refresco: float = 0.05,
        espera_reconexion: float = 5.0,
    ) -> None:
        #: El cliente del robot: el puente del ESP32-S3 si hay uno
        #: configurado (`AIRO_BRIDGE_URL`), si no el BLE de siempre.
        self.robot: AiroRobot | BridgeRobot = crear_robot(
            address=address, scan_timeout=scan_timeout
        )
        self.refresco = refresco
        #: Segundos entre intentos de reconexion cuando se cae el enlace.
        self.espera_reconexion = espera_reconexion
        self.conectado = False
        self.accion_actual: str | None = None
        self.error: str | None = None
        self._tarea_refresco: asyncio.Task[None] | None = None
        self._tarea_programa: asyncio.Task[None] | None = None
        #: Programas esperando turno. Se ejecutan uno detras de otro: antes
        #: el segundo cancelaba al primero y el robot se quedaba a mitad.
        self._cola: asyncio.Queue[list[Step]] = asyncio.Queue()
        #: Quantos programas hay en la cola todavia sin empezar (el que se
        #: esta ejecutando ya no cuenta: esta corriendo, no esperando).
        self._pendientes = 0
        self._avisos: list[Any] = []
        # La calibracion es del comando, no de la conexion: se carga ya para
        # que el estado sea el mismo este el robot conectado o no (la interfaz
        # web muestra los bytes de los brazos aunque este apagado).
        self._cargar_calibracion()

    # -- ciclo de vida ----------------------------------------------------

    async def conectar(self) -> None:
        await self.robot.connect()
        self.conectado = True
        self.error = None
        self._cargar_calibracion()
        self._tarea_refresco = asyncio.create_task(self._refrescar())

    def _cargar_calibracion(self) -> bool:
        """Carga `calibration.json` (offsets y ceros) en el comando.

        Sin esto la web moveria los brazos de forma distinta que la consola:
        la consola y el puente de Scratch cargaban la calibracion y la API no.
        El hombro izquierdo (byte 9) va calibrado con el cero en 16, no en 20:
        sin cargarlo, la web mandaba un byte distinto que la consola para ese
        hombro.
        """
        from .console import load_calibration

        try:
            return bool(load_calibration(self.robot.command))
        except Exception:
            return False

    async def desconectar(self) -> None:
        await self._parar_tareas()
        await self._parar_robot()
        try:
            await self.robot.disconnect()
        except Exception:
            pass
        self.conectado = False

    async def _parar_robot(self) -> None:
        """Manda las ruedas a velocidad 0 (si se puede) antes de soltar el BLE.

        Sin esto, al apagar la web o el servidor con el robot en marcha, este
        se queda dando vueltas: el firmware no se apaga solo al perder el
        enlace.
        """
        self.robot.command.stop()
        try:
            await self.robot.send(self.robot.command)
        except Exception:
            pass  # sin conexion no hay nada que enviar

    async def _parar_tareas(self) -> None:
        for tarea in (self._tarea_programa, self._tarea_refresco):
            if tarea is not None and not tarea.done():
                tarea.cancel()
                try:
                    await tarea
                except (asyncio.CancelledError, Exception):
                    pass
        self._tarea_programa = None
        self._tarea_refresco = None

    async def _refrescar(self) -> None:
        """Refresca el paquete sin parar.

        El firmware devuelve los brazos a su posicion de reposo si deja de
        recibir paquetes, asi que esto no es opcional. Si el enlace se cae,
        se intenta reconectar solo (el cliente se autorrepara: borra el
        dispositivo de la cache de BlueZ y reintenta).
        """
        while True:
            try:
                await asyncio.sleep(self.refresco)
                await self.robot.send(self.robot.command)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = str(exc)
                self.conectado = False
                await self._reconectar()

    async def _reconectar(self) -> None:
        """Reintenta la conexion hasta que el robot vuelva.

        Solo desconecta **una vez** (antes del bucle): antes se llamaba a
        `disconnect()` en cada intento, lo que dejaba el cliente en un
        estado inconsistente entre reintentos. Y guarda el error **mas
        reciente**: antes se tragaba la excepcion nueva con un `continue`, de
        modo que la interfaz se quedaba mostrando el primer error para
        siempre (util cuando el robot esta apagado y cambia el motivo).
        """
        try:
            await self.robot.disconnect()
        except Exception:
            pass
        while True:
            await asyncio.sleep(self.espera_reconexion)
            try:
                await self.robot.connect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = str(exc)
                continue
            self.conectado = True
            self.error = None
            return

    # -- acciones ---------------------------------------------------------

    async def mover(
        self,
        izquierda: float = 0.0,
        derecha: float = 0.0,
        segundos: float = 0.0,
    ) -> None:
        """Mueve las ruedas. `segundos` = 0 significa 'hasta que se pare'."""
        self.robot.command.left_speed = izquierda
        self.robot.command.right_speed = derecha
        self.accion_actual = "moviendo"
        if segundos:
            await asyncio.sleep(segundos)

    async def parar(self) -> None:
        self.robot.command.stop()
        self.accion_actual = "parado"

    async def luz(self, modo: str) -> None:
        self.robot.command.led = Led[str(modo).upper()]
        self.accion_actual = "luz"

    async def brazo(
        self,
        lado: str,
        pose: str,
        segundos: float = 0.0,
        articulacion: str = "todo",
        angulo: float | None = None,
    ) -> None:
        """Mueve uno o los dos brazos.

        `segundos` > 0 = **movimiento lento**: el destino va viajando hasta el
        servo durante ese tiempo (rampa), asi que el brazo se ve subir poco a
        poco. `segundos` == 0 = de golpe: el servo va a su velocidad y se
        queda en el destino, y aqui se espera lo que tarda en llegar.

        `articulacion` ("todo", "hombro" o "codo") dice que articulacion se
        mueve, y `angulo` (si se pasa) manda sobre la pose: es un angulo
        concreto de la app.

        La espera no es un adorno: si se le manda el destino nuevo antes de
        tiempo, el servo cambia de destino a medio camino y el primer
        movimiento no llega a verse nunca.
        """
        from .arms import resolver_objetivos

        objetivos = resolver_objetivos(
            lado, pose=pose, articulacion=articulacion, angulo=angulo
        )
        lento = " lento" if segundos > 0 else ""
        self.accion_actual = f"brazo {lado} {pose}{lento}"
        await self._mover_servos(objetivos, segundos)

    async def _mover_servos(
        self, objetivos: dict[Joint, float], segundos: float = 0.0
    ) -> None:
        """Mueve las articulaciones a sus destinos y espera lo necesario."""
        if not objetivos:
            return
        from .arms import duracion_de_accion

        duracion = duracion_de_accion(objetivos, self.angulos_actuales(), segundos)
        if segundos > 0:
            await self._rampa(objetivos, duracion)
            return
        for joint, angulo in objetivos.items():
            self.robot.command.set_joint(joint, angulo)
        await asyncio.sleep(duracion)

    async def _rampa(self, objetivos: dict[Joint, float], duracion: float) -> None:
        """Movimiento lento: el destino viaja y el servo lo sigue.

        El servo no sabe que le estan dando una rampa: simplemente va
        persiguiendo un destino que se mueve. El tope de lo fino que se
        puede poner lo marca la resolucion del byte (uno son 8,5 grados), asi
        que un movimiento muy lento se ve a escalones.

        Los pasos los calcula `arms.pasos_rampa()`, que comparten tambien la
        consola y el puente de Scratch.
        """
        from .arms import PASOS_POR_SEGUNDO, pasos_rampa

        for paso in pasos_rampa(objetivos, duracion, self.angulos_actuales()):
            for joint, angulo in paso.items():
                self.robot.command.set_joint(joint, angulo)
            await asyncio.sleep(1 / PASOS_POR_SEGUNDO)

    def angulos_actuales(self) -> dict[Joint, float]:
        """El ultimo angulo pedido para cada articulacion.

        Es de donde "sale" el servo ahora mismo, y por tanto lo que
        determina cuanto tarda en llegar a su destino.
        """
        return dict(self.robot.command.servos)

    async def esperar(self, segundos: float) -> None:
        self.accion_actual = "esperando"
        await asyncio.sleep(segundos)

    async def kata(self) -> None:
        """La coreografia de karate."""
        from .console import KATA

        self.accion_actual = "kata"
        for comando, duracion in KATA:
            partes = comando.split()
            if not partes:
                continue
            if partes[0] == "led":
                self.robot.command.led = Led[partes[1].upper()]
            elif partes[0] == "brazo":
                await self.brazo(partes[1], partes[2])
            elif partes[0] in ("avanzar", "atras", "izquierda", "derecha"):
                await self.mover_una_vez(partes[0], float(partes[1]) if len(partes) > 1 else 1.0)
            elif partes[0] == "parar":
                await self.parar()
            await asyncio.sleep(duracion)
        await self.parar()

    async def mover_una_vez(self, direccion: str, velocidad: float) -> None:
        if direccion == "avanzar":
            await self.mover(velocidad, velocidad)
        elif direccion == "atras":
            await self.mover(-velocidad, -velocidad)
        elif direccion == "izquierda":
            await self.mover(velocidad, -velocidad)
        elif direccion == "derecha":
            await self.mover(-velocidad, velocidad)

    # -- programas --------------------------------------------------------

    async def ejecutar(self, pasos: Iterable[Step]) -> None:
        """Encola un programa: los programas se ejecutan uno detras de otro.

        Antes esto **cancelaba** el programa que estaba corriendo, asi que
        pulsar "ejecutar" dos veces dejaba al robot a mitad de un movimiento.
        Ahora el segundo programa espera al primero.
        """
        self._pendientes += 1
        self._cola.put_nowait(list(pasos))
        self._asegurar_trabajador()
        # Un `await 0` para que el trabajador recoja el programa recien
        # encolado: si no, la cuenta de la cola incluiria el programa que
        # ya esta empezando a correr.
        await asyncio.sleep(0)

    def _asegurar_trabajador(self) -> None:
        if self._tarea_programa is None or self._tarea_programa.done():
            self._tarea_programa = asyncio.create_task(self._trabajador())

    async def _trabajador(self) -> None:
        """Ejecuta los programas de la cola, uno tras otro."""
        while True:
            pasos = await self._cola.get()
            self._pendientes = max(0, self._pendientes - 1)
            try:
                await self._ejecutar(pasos)
            finally:
                self._cola.task_done()

    @property
    def programas_en_cola(self) -> int:
        """Cuantos programas estan esperando turno (sin contar el que corre)."""
        return self._pendientes

    async def _parar_programa(self) -> None:
        """Cancela el programa en curso y vacia la cola de los que esperaba."""
        self._vaciar_cola()
        if self._tarea_programa is not None and not self._tarea_programa.done():
            self._tarea_programa.cancel()
            try:
                await self._tarea_programa
            except (asyncio.CancelledError, Exception):
                pass
        self._tarea_programa = None

    def _vaciar_cola(self) -> None:
        while not self._cola.empty():
            self._cola.get_nowait()
            self._cola.task_done()
        self._pendientes = 0

    async def _ejecutar(self, pasos: Iterable[Step]) -> None:
        try:
            for paso in pasos:
                await self._ejecutar_paso(paso)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
        finally:
            # Un programa termina SIEMPRE con el robot parado. Antes solo se
            # paraba si habia un error, y el refresco seguia mandando la
            # velocidad: el robot se quedaba conduciendo solo.
            await self.parar()

    async def _ejecutar_paso(self, paso: Step) -> None:
        params = paso.params
        if paso.kind == "mover":
            await self.mover(
                izquierda=float(params.get("izquierda", 0.0)),
                derecha=float(params.get("derecha", 0.0)),
            )
        elif paso.kind == "parar":
            await self.parar()
        elif paso.kind == "luz":
            await self.luz(str(params.get("modo", "off")))
        elif paso.kind == "brazo":
            # El brazo se gestiona aqui: su duracion depende de lo que tarde
            # el servo en llegar, y se duerme dentro (no al final del paso).
            await self._ejecutar_brazo(paso)
            return
        elif paso.kind == "kata":
            await self.kata()
            return
        elif paso.kind == "espera":
            await self.esperar(paso.duracion)
            return
        else:
            raise ValueError(f"Paso desconocido: {paso.kind}")
        if paso.duracion:
            await asyncio.sleep(paso.duracion)

    async def detener_programa(self) -> None:
        await self._parar_programa()
        await self.parar()

    async def _ejecutar_brazo(self, paso: Step) -> None:
        """Mueve los brazos del paso: de golpe o en rampa (movimiento lento)."""
        from .arms import objetivos_de_paso

        objetivos = objetivos_de_paso(paso.params)
        segundos = float(paso.params.get("segundos") or paso.duracion or 0.0)
        lado = paso.params.get("lado", "ambos")
        pose = paso.params.get("pose", "medio")
        lento = " lento" if segundos > 0 else ""
        self.accion_actual = f"brazo {lado} {pose}{lento}"
        if objetivos:
            await self._mover_servos(objetivos, segundos)

    # -- estado -----------------------------------------------------------

    def estado(self) -> dict[str, Any]:
        cmd = self.robot.command
        return {
            "conectado": bool(self.conectado and self.robot.is_connected),
            # Si se habla con el robot a traves del puente del ESP32-S3, se
            # dice cual es: asi se sabe de un vistazo por donde van las cosas.
            "puente": self.robot.url if isinstance(self.robot, BridgeRobot) else None,
            "accion": self.accion_actual,
            "error": self.error,
            "luz": cmd.led.name.lower(),
            "ruedas": {"izquierda": cmd.left_speed, "derecha": cmd.right_speed},
            # Cuantos programas hay esperando turno. Los programas se ejecutan
            # uno detras de otro: este numero es el que la interfaz muestra
            # para que se vea que nadie se ha pisado.
            "cola": self.programas_en_cola,
            "brazos": {
                joint.name.lower(): {
                    "angulo": cmd.servos.get(joint, 0.0),
                    "byte": cmd.servo_byte(joint),
                    # El byte que es "angulo 0" en esta articulacion. Lo
                    # necesita la web para deshacer el escalado del servo: sin
                    # el, el hombro derecho (que viene calibrado en 16, no en
                    # 20) se dibujaria con ~34 grados de error.
                    "neutral": cmd.neutral.get(joint, SERVO_CENTER),
                }
                for joint in Joint
            },
        }
