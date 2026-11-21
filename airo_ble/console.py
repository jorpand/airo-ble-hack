"""
Consola interactiva para mandar comandos al Clementoni AIRO por BLE.

    python -m airo_ble.console            # busca el robot por su nombre 'AIRo'
    python -m airo_ble.console --address AA:BB:CC:DD:EE:FF
    python -m airo_ble.console --dry-run   # no conecta: solo muestra los paquetes

La consola mantiene la conexion abierta y el estado del robot (LED, ruedas y
angulos de las articulaciones) entre comandos. Ademas refresca el paquete cada
50 ms, igual que hace la app oficial, y para las ruedas si dejas de escribir
durante `--watchdog` segundos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import signal
import sys
from pathlib import Path

try:  # edicion de linea + historial con las flechas (Unix)
    import readline
except ImportError:  # pragma: no cover - Windows
    readline = None  # type: ignore[assignment]

from .arms import (
    ARM_POSES,
    ARTICULACIONES,
    BrazoError,
    resolver_objetivos,
)
from .bridge import BridgeRobot, crear_robot
from .client import AiroNotFound, AiroRobot
from .protocol import (
    JOINT_NAMES,
    SERVO_BYTE_MAX,
    SERVO_CENTER,
    SERVO_LIMITS,
    SERVO_SCALE,
    Command,
    Joint,
    Led,
)

__all__ = ["ARM_POSES", "Console", "ConsoleError", "main"]


#: Fichero donde se guarda el historial entre sesiones.
HISTORY_FILE = Path.home() / ".airo_history"

#: Calibracion **del usuario**: es la que crea `calib guardar`.
#:
#: Vive en la carpeta de configuracion del usuario y no dentro del paquete,
#: por dos razones: sobrevive a las actualizaciones y no necesita permisos
#: de escritura en `site-packages`.
CALIBRATION_FILE = Path.home() / ".config" / "airo-ble" / "calibration.json"

#: Calibracion que viene **con el paquete** (y la de un checkout del repo).
#: Se usa si el usuario no ha guardado ninguna la suya.
CALIBRATION_DEFAULT = Path(__file__).resolve().parent / "calibration.json"


def calibration_path() -> Path:
    """Ruta del fichero de calibracion del usuario (donde se guarda)."""
    return CALIBRATION_FILE


def load_calibration(command: Command) -> bool:
    """Carga los offsets y ceros guardados en el `Command`. True si habia.

    Se busca primero la calibracion del usuario y, si no hay, la que viene
    con el paquete. Antes esto miraba solo un fichero en la raiz del repo,
    que al instalar el paquete no existia: la calibracion se perdia en
    silencio y los brazos movian distinto segun por donde se mandara la
    orden.
    """
    for ruta in (CALIBRATION_FILE, CALIBRATION_DEFAULT):
        if not ruta.exists():
            continue
        try:
            datos = json.loads(ruta.read_text())
        except Exception:
            continue
        if "offsets" not in datos:  # formato antiguo (solo offsets)
            datos = {"offsets": datos, "neutral": {}}
        command.offsets.clear()
        command.neutral.clear()
        for nombre, valor in (datos.get("offsets") or {}).items():
            try:
                command.offsets[resolve_joint(nombre)] = float(valor)
            except ConsoleError:
                continue
        for nombre, valor in (datos.get("neutral") or {}).items():
            try:
                command.neutral[resolve_joint(nombre)] = int(valor)
            except ConsoleError:
                continue
        return True
    return False


def save_calibration(command: Command) -> Path:
    """Guarda los offsets y ceros del `Command` en el fichero del usuario."""
    datos = {
        "offsets": {j.name.lower(): command.offsets[j] for j in command.offsets},
        "neutral": {j.name.lower(): command.neutral[j] for j in command.neutral},
    }
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(json.dumps(datos, indent=2) + "\n")
    return CALIBRATION_FILE


#: Atajos para las articulaciones, ademas de los nombres canonicos
#: (`right_shoulder`, `right_arm`, `left_arm`, `left_shoulder`).
JOINT_ALIASES: dict[str, Joint] = {
    "r_shoulder": Joint.RIGHT_SHOULDER,
    "r_sh": Joint.RIGHT_SHOULDER,
    "r_arm": Joint.RIGHT_ARM,
    "l_shoulder": Joint.LEFT_SHOULDER,
    "l_sh": Joint.LEFT_SHOULDER,
    "l_arm": Joint.LEFT_ARM,
    "hombro_der": Joint.RIGHT_SHOULDER,
    "hombro_izq": Joint.LEFT_SHOULDER,
    "brazo_der": Joint.RIGHT_ARM,
    "brazo_izq": Joint.LEFT_ARM,
}


def resolve_joint(name: str) -> Joint:
    """Traduce el nombre de una articulacion (con o sin alias) a `Joint`."""
    key = name.strip().lower().replace("-", "_")
    if key in JOINT_NAMES:
        return JOINT_NAMES[key]
    if key in JOINT_ALIASES:
        return JOINT_ALIASES[key]
    raise ConsoleError(
        f"Articulación desconocida: {name!r}. "
        f"Valores: {', '.join(sorted(JOINT_NAMES))}"
    )


#: Poses de los brazos, en ángulos de la app.
#:
#: La tabla vive en `airo_ble.arms` (junto con la lógica de qué lado se
#: mueve), porque la consola, la sesión y el servidor de Scratch tienen que
#: entenderlo **igual**. Se re-exporta aquí por comodidad.
#:
#: El lado canónico es el de los bytes 6 (hombro) y 7 (codo); el otro lado es
#: su espejo (bytes 9 y 8) con los signos cambiados. Estas poses son las que
#: se han verificado en el robot: hombro -60 + codo 170 = brazo arriba;
#: hombro +77 + codo -25 = abierto.

#: Coreografia del kata de karate: (comando, duracion en segundos).
KATA: tuple[tuple[str, float], ...] = (
    ("led on", 0.4),
    ("brazo ambos guardia", 1.4),
    ("izquierda 1", 1.1),          # giro de preparacion
    ("parar", 0.4),
    ("brazo der golpe", 0.7),      # gyaku-zuki
    ("brazo der guardia", 0.5),
    ("brazo izq golpe", 0.7),      # hidari-zuki
    ("brazo izq guardia", 0.5),
    ("avanzar 2", 1.2),            # paso adelante
    ("parar", 0.4),
    ("derecha 1", 1.1),            # giro al otro lado
    ("parar", 0.4),
    ("brazo ambos abajo", 0.8),    # gedan-barai
    ("atras 2", 1.2),              # paso atras
    ("parar", 0.4),
    ("brazo ambos arriba", 0.9),   # jodan
    ("led flash", 0.3),
    ("izquierda 1", 2.7),          # vuelta completa
    ("parar", 0.5),
    ("brazo ambos medio", 0.9),
    ("brazo ambos guardia", 1.0),
    ("led off", 0.4),
)



class ConsoleError(Exception):
    """El comando no se entiende o no se puede ejecutar."""


HELP = """
Comandos (se pueden encadenar con ';')                      Alias en ingles
  ayuda                                                help
  conectar [MAC]      conectar al robot (por defecto 'AIRo')   connect
  desconectar                                         disconnect
  reconectar [MAC]   cerrar y volver a conectar                  reconnect
  escanear            lista los dispositivos BLE que se ven    scan
  avanzar [v]        ambas ruedas hacia delante (v: -3..3)    forward
  atras [v]          ambas ruedas hacia atras                  backward
  izquierda [v]      gira sobre si mismo a la izquierda         left
  derecha [v]        gira sobre si mismo a la derecha           right
  ruedas <izq> <der> velocidades sueltas (-3..3)          wheels
  parar              detiene las ruedas                          stop
  led <off|on|flash|fade>   LED azul                           led
  pose <art> <grado> mueve una articulacion                    servo
  pose <art>=<grado> ...  varias de golpe
  brazo <izq|der|ambos> <arriba|abajo|medio|golpe|guardia>  posicion del brazo
  brazo <izq|der|ambos> <pose> <segundos>   la misma pose, pero LENTA (rampa)
  brazo <izq|der|ambos> <hombro|codo> <grado>  una articulacion a un angulo
  brazo <izq|der|ambos> <hombro|codo> <grado> <seg>   ... y despacio
  kata                kata de karate (pasos, golpes y giros)
  bruto <art> <byte>  byte crudo de servo (experimentos)   raw
  reset              servos a 0 y ruedas paradas                reset
  calibrar           asistente: fija la posicion de reposo de los brazos
  neutro [art] [byte]  byte que se considera 'angulo 0'
  calib [art] [+n]   calibracion de brazos (offset en grados) calibration
  calib guardar|cargar|reset
  estado             estado actual                         state
  historial          comandos recientes            history
  limpiar            limpia la pantalla                   clear
  dump               muestra el paquete sin enviarlo           dump
  hex A5 00 ...      envia un paquete crudo                    hex
  salir              desconecta y sale                     quit

Articulaciones: right_shoulder, right_arm, left_arm, left_shoulder
                (alias: r_sh, r_arm, l_sh, l_arm)
                Son los nombres FISICOS (los de la guia): el byte 6 es el
                hombro derecho y el 9 el hombro izquierdo.
""".strip()


class Console:
    """Bucle de lectura y ejecucion de comandos sobre un `AiroRobot`."""

    def __init__(
        self,
        robot: AiroRobot | BridgeRobot,
        *,
        keepalive: bool = True,
        keepalive_interval: float = 0.05,
        watchdog: float = 5.0,
        dry_run: bool = False,
        echo: bool = True,
    ) -> None:
        self.robot = robot
        self.keepalive = keepalive
        self.keepalive_interval = keepalive_interval
        self.watchdog = watchdog
        self.dry_run = dry_run
        self.echo = echo
        self._task: asyncio.Task[None] | None = None
        self._last_input = 0.0
        self._en_ejecucion = 0
        self._reconnecting = False
        self._offsets: dict[Joint, float] = {}
        self._neutral: dict[Joint, int] = {}
        #: Si es False, el comando "brazo" no espera a que el servo llegue.
        #: La kata lo desactiva porque ya tiene sus propios tiempos: si no,
        #: cada paso de la kata tardaria un segundo mas.
        self._esperar_brazo = True

    # -- ciclo de vida ----------------------------------------------------

    async def connect(self, address: str | None = None) -> None:
        if self.dry_run:
            self.robot.address = address or "(sin conectar)"
            return
        if address:
            self.robot.address = address
        await self.robot.connect()
        self.load_calibration()

    def load_calibration(self) -> bool:
        """Carga la calibracion guardada (si existe). Devuelve True si la hay.

        Busca primero la del usuario y luego la que viene con el paquete,
        igual que hace `load_calibration()`.
        """
        try:
            return bool(load_calibration(self.robot.command))
        except Exception:  # pragma: no cover - fichero corrupto
            return False

    async def disconnect(self) -> None:
        await self.stop_keepalive()
        if not self.dry_run:
            await self.robot.disconnect()

    async def start_keepalive(self) -> None:
        """Refresca el paquete cada 50 ms, como la app oficial.

        El firmware parece necesitar el refresco continuo para el LED
        `flash`/`fade` y para mantener las ruedas en marcha.
        """
        if not self.keepalive or self.dry_run or self._task is not None:
            return
        self._last_input = asyncio.get_running_loop().time()
        self._task = asyncio.create_task(self._keepalive_loop())

    async def stop_keepalive(self) -> None:
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _reconnect(self) -> bool:
        """Vuelve a conectar si el modulo se ha caido. True si lo consigue."""
        if self.dry_run or self._reconnecting:
            return False
        self._reconnecting = True
        try:
            await self.disconnect()
            await self.connect(self.robot.address)
            return True
        except Exception as exc:
            print(f"\n[!] no se pudo reconectar: {exc}", flush=True)
            return False
        finally:
            self._reconnecting = False

    async def _keepalive_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                await asyncio.sleep(self.keepalive_interval)
                idle = loop.time() - self._last_input
                if self.watchdog and idle > self.watchdog and self._moving():
                    if self._en_ejecucion:
                        # hay un comando en marcha (p.ej. la kata, que dura
                        # ~20 s): el watchdog espera a que termine
                        self._last_input = loop.time()
                    else:
                        # OJO: hay que parar de verdad. Antes solo se reenviaba
                        # el paquete con la misma velocidad, asi que el robot
                        # se quedaba dando vueltas indefinidamente.
                        await self.parar()
                        print(
                            f"\n[!] {self.watchdog:g} s sin comandos: ruedas paradas.",
                            flush=True,
                        )
                elif self._needs_refresh():
                    # el keepalive es silencioso: si no, cada ~200 ms llenaria
                    # la terminal de hex y no se podria usar
                    await self._send(echo=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - red caida
                print(f"\n[!] se ha cortado la conexion: {exc}", flush=True)
                if await self._reconnect():
                    print(f"[*] reconectado a {self.robot.address}", flush=True)

    def _moving(self) -> bool:
        cmd = self.robot.command
        return bool(cmd.left_speed or cmd.right_speed)

    async def parar(self) -> None:
        """Para las ruedas y manda el paquete con velocidad 0.

        Se manda en el acto: esperar al siguiente refresco del keepalive
        dejaria al robot moviendo medio segundo mas. Si el envio falla, el
        estado local ya queda a 0 y el keepalive lo reintentara.
        """
        self.robot.command.stop()
        try:
            await self._send(echo=False)
        except Exception as exc:  # pragma: no cover - red caida
            print(f"\n[!] no se pudo mandar la parada: {exc}", flush=True)

    def _needs_refresh(self) -> bool:
        """Siempre hay que refrescar: el firmware devuelve los servos a su
        posicion de reposo en cuanto deja de recibir paquetes (verificado en
        el robot: a los pocos segundos de dejar de enviar, los brazos se
        bajan solos). La app oficial manda el suyo cada 50 ms sin parar, y
        por eso el LED en 'flash' tambien parpadea.

        Ojo: el refresco manda el estado **actual** del comando, asi que
        despues de `parar()` sigue refrescando (para que los brazos se
        queden donde estan) pero con las ruedas a cero.
        """
        return True

    # -- envio ------------------------------------------------------------

    async def _send(self, *, force: bool = False, echo: bool | None = None) -> bytes:
        payload = self.robot.command.to_bytes()
        if not self.dry_run:
            try:
                await self.robot.send(self.robot.command, force=force)
            except Exception as exc:
                # el modulo HM-10 se cae solo de vez en cuando: reconectamos
                print(f"\n[!] se ha cortado la conexión ({exc}), reconectando...", flush=True)
                if not await self._reconnect():
                    raise
                await self.robot.send(self.robot.command, force=force)
        if echo if echo is not None else self.echo:
            print(f"  -> {payload.hex(' ')}")
        return payload

    # -- ejecucion de comandos --------------------------------------------

    async def execute(self, line: str) -> str:
        """Ejecuta una linea de la consola (puede encadenar con ';').

        Devuelve el texto que hay que mostrarle al usuario (vacio si el
        comando no produce salida).
        """
        output = ""
        # un comando puede tardar mucho (la kata dura ~20 s): mientras se
        # ejecuta, el watchdog no debe parar las ruedas por debajo
        self._en_ejecucion += 1
        try:
            for chunk in line.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                # cualquier comando cuenta como actividad: el watchdog no debe
                # parar las ruedas mientras se esta ejecutando una coreografia
                self._last_input = asyncio.get_running_loop().time()
                try:
                    words = shlex.split(chunk)
                except ValueError as exc:
                    raise ConsoleError(f"No se pudo interpretar la linea: {exc}") from exc
                if not words:
                    continue
                name, args = words[0].lower(), words[1:]
                handler = getattr(self, f"_cmd_{name}", None)
                if handler is None:
                    raise ConsoleError(f"Comando desconocido: {name!r} (escribe 'ayuda')")
                result = handler(args)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    output = result if not output else f"{output}\n{result}"
        finally:
            self._en_ejecucion -= 1
        return output

    # -- comandos ---------------------------------------------------------

    def _cmd_ayuda(self, args: list[str]) -> str:
        return HELP

    def _cmd_help(self, args: list[str]) -> str:
        return HELP

    async def _cmd_conectar(self, args: list[str]) -> str:
        if self.dry_run:
            raise ConsoleError("En --dry-run no se puede conectar")
        if self.robot.is_connected:
            return "Ya estas conectado."
        address = args[0] if args else None
        await self.connect(address)
        await self.start_keepalive()
        return f"Conectado a {self.robot.address}."

    async def _cmd_connect(self, args: list[str]) -> str:
        return await self._cmd_conectar(args)

    async def _cmd_desconectar(self, args: list[str]) -> str:
        await self.disconnect()
        return "Desconectado."

    async def _cmd_disconnect(self, args: list[str]) -> str:
        return await self._cmd_desconectar(args)

    async def _cmd_reconectar(self, args: list[str]) -> str:
        """Cierra y vuelve a abrir la conexion (util si el modulo se duerme)."""
        await self.disconnect()
        address = args[0] if args else self.robot.address
        await self.connect(address)
        await self.start_keepalive()
        return f"Reconectado a {self.robot.address}."

    async def _cmd_reconnect(self, args: list[str]) -> str:
        return await self._cmd_reconectar(args)

    async def _cmd_escanear(self, args: list[str]) -> str:
        from bleak import BleakScanner

        found = await BleakScanner.discover(timeout=10.0, return_adv=True)
        lines = []
        for value in found.values():
            dev, adv = value if isinstance(value, tuple) else (value, None)
            name = getattr(adv, "local_name", None) or getattr(dev, "name", None) or "(sin nombre)"
            rssi = getattr(adv, "rssi", "?")
            lines.append(f"  {dev.address}  {name:22s}  rssi={rssi}")
        return "\n".join(lines) if lines else "No se ha visto ningun dispositivo BLE."

    async def _cmd_scan(self, args: list[str]) -> str:
        return await self._cmd_escanear(args)

    # movimiento

    def _cmd_avanzar(self, args: list[str]) -> str:
        return self._drive(args, left=1.0, right=1.0)

    def _cmd_forward(self, args: list[str]) -> str:
        return self._cmd_avanzar(args)

    def _cmd_atras(self, args: list[str]) -> str:
        return self._drive(args, left=-1.0, right=-1.0)

    def _cmd_backward(self, args: list[str]) -> str:
        return self._cmd_atras(args)

    def _cmd_izquierda(self, args: list[str]) -> str:
        return self._drive(args, left=1.0, right=-1.0)

    def _cmd_left(self, args: list[str]) -> str:
        return self._cmd_izquierda(args)

    def _cmd_derecha(self, args: list[str]) -> str:
        return self._drive(args, left=-1.0, right=1.0)

    def _cmd_right(self, args: list[str]) -> str:
        return self._cmd_derecha(args)

    def _cmd_ruedas(self, args: list[str]) -> str:
        if len(args) != 2:
            raise ConsoleError("Uso: ruedas <izquierda> <derecha>")
        left, right = self._speed(args[0]), self._speed(args[1])
        self.robot.command.left_speed = left
        self.robot.command.right_speed = right
        return f"Ruedas: izquierda {left:g}, derecha {right:g}"

    def _cmd_wheels(self, args: list[str]) -> str:
        return self._cmd_ruedas(args)

    async def _cmd_parar(self, args: list[str]) -> str:
        await self.parar()
        return "Ruedas paradas."

    async def _cmd_stop(self, args: list[str]) -> str:
        return await self._cmd_parar(args)

    def _drive(self, args: list[str], *, left: float, right: float) -> str:
        speed = self._speed(args[0]) if args else 1.0
        self.robot.command.left_speed = left * abs(speed)
        self.robot.command.right_speed = right * abs(speed)
        return (
            f"Ruedas: izquierda {self.robot.command.left_speed:g}, "
            f"derecha {self.robot.command.right_speed:g}"
        )

    @staticmethod
    def _speed(text: str) -> float:
        try:
            value = float(text)
        except ValueError as exc:
            raise ConsoleError(f"Velocidad invalida: {text!r}") from exc
        if not -3.0 <= value <= 3.0:
            raise ConsoleError(f"La velocidad va de -3 a 3 (no {value:g})")
        return value

    # LED

    def _cmd_led(self, args: list[str]) -> str:
        if not args:
            raise ConsoleError("Uso: led <off|on|flash|fade>")
        try:
            mode = Led[args[0].upper()]
        except KeyError as exc:
            raise ConsoleError(
                f"LED desconocido: {args[0]!r} (off, on, flash, fade)"
            ) from exc
        self.robot.command.led = mode
        return f"LED: {mode.name.lower()}"

    # articulaciones

    def _cmd_pose(self, args: list[str]) -> str:
        if not args:
            raise ConsoleError("Uso: pose <articulacion> <grado>  (o  pose art=grado ...)")
        pairs: list[tuple[Joint, float]] = []
        if all("=" in arg for arg in args):
            # forma articulacion=grado articulacion=grado
            for arg in args:
                name, _, value = arg.partition("=")
                joint = resolve_joint(name)
                pairs.append((joint, self._angle(joint, value)))
        else:
            # forma articulacion grado [articulacion grado ...]
            if len(args) % 2 != 0:
                raise ConsoleError(
                    "Uso: pose <articulacion> <grado>  (o  pose art=grado art=grado)"
                )
            for name, value in zip(args[0::2], args[1::2], strict=False):
                joint = resolve_joint(name)
                pairs.append((joint, self._angle(joint, value)))
        for joint, angle in pairs:
            self.robot.command.set_joint(joint, angle)
        return ", ".join(
            f"{joint.name.lower()}={angle:g} (byte {self.robot.command.servo_byte(joint)})"
            for joint, angle in pairs
        )

    def _cmd_servo(self, args: list[str]) -> str:
        return self._cmd_pose(args)

    async def _cmd_brazo(self, args: list[str]) -> str:
        """Mueve el brazo: a una pose o a un ángulo de una articulación.

        brazo <izq|der|ambos> <arriba|abajo|medio|golpe|guardia> [segundos]
        brazo <izq|der|ambos> <hombro|codo> <grado> [segundos]

        El tiempo (segundos) es opcional: sin el, el brazo va "de golpe" (el
        servo a su velocidad). Con el, el movimiento es **lento**: el destino
        va viajando hasta el servo durante ese tiempo.
        """
        if len(args) < 2:
            raise ConsoleError(
                "Uso: brazo <izq|der|ambos> <"
                + "|".join(ARM_POSES)
                + "> [segundos]\n"
                "     brazo <izq|der|ambos> <hombro|codo> <grado> [segundos]"
            )
        lado = args[0].lower()
        destino = args[1].lower()
        segundos = 0.0
        try:
            if destino in ARTICULACIONES and destino != "todo":
                if len(args) < 3:
                    raise ConsoleError(
                        f"Falta el ángulo: brazo {lado} {destino} <grado> [segundos]"
                    )
                angulo = float(args[2])
                if len(args) > 3:
                    segundos = float(args[3])
                objetivos = resolver_objetivos(
                    lado, articulacion=destino, angulo=angulo
                )
                etiqueta = f"el {destino} a {angulo:g}°"
            elif destino in ARM_POSES:
                if len(args) > 2:
                    segundos = float(args[2])
                objetivos = resolver_objetivos(lado, pose=destino)
                etiqueta = f"la posición '{destino}'"
            else:
                raise ConsoleError(
                    f"Destino desconocido: {destino!r}. Usa una pose ("
                    + "|".join(ARM_POSES)
                    + ") o una articulación (hombro|codo)."
                )
        except BrazoError as exc:
            raise ConsoleError(str(exc)) from exc
        except ValueError as exc:
            raise ConsoleError(f"No se pudo leer el número: {exc}") from exc

        await self._mover_brazo(objetivos, segundos)
        lento = f" en {segundos:g} s" if segundos > 0 else ""
        return f"Brazo(s) {lado} en {etiqueta}{lento}"

    async def _mover_brazo(
        self, objetivos: dict[Joint, float], segundos: float
    ) -> None:
        """Mueve el brazo y espera lo necesario.

        Sin tiempo es un salto al destino (y se espera lo que tarde el servo
        en llegar, con un minimo de un segundo: si se le manda el destino
        nuevo antes de tiempo, el servo cambia de destino a medio camino y el
        movimiento no llega a verse).

        Con tiempo es una **rampa**: el destino viaja hasta el servo. La
        rampa la calculan `arms.pasos_rampa()`, los mismos pasos que usa la
        sesion de la API y el puente de Scratch.
        """
        from .arms import PASOS_POR_SEGUNDO, duracion_de_accion, pasos_rampa, tiempo_de_viaje

        if not objetivos:
            return
        actuales = dict(self.robot.command.servos)
        if segundos > 0:
            # La rampa dura lo pedido, pero nunca menos que lo que tarda el
            # servo: si no, no llegaria al destino.
            duracion = duracion_de_accion(objetivos, actuales, segundos)
            for paso in pasos_rampa(objetivos, duracion, actuales):
                for joint, angulo in paso.items():
                    self.robot.command.set_joint(joint, angulo)
                await asyncio.sleep(1 / PASOS_POR_SEGUNDO)
            return

        espera = tiempo_de_viaje(objetivos, actuales)
        for joint, angle in objetivos.items():
            self.robot.command.set_joint(joint, angle)
        if self._esperar_brazo and not self.dry_run:
            await asyncio.sleep(espera)

    async def _cmd_kata(self, args: list[str]) -> str:
        """Kata de karate: coreografia de pasos, golpes y giros."""
        loop = asyncio.get_running_loop()
        inicio = loop.time()
        print(f"  [{1:2d}/{len(KATA)}] {KATA[0][0]}", flush=True)
        # La kata ya tiene sus propios tiempos: si el comando "brazo" esperase
        # ademas a que el servo llegue, cada paso tardaria un segundo mas.
        self._esperar_brazo = False
        try:
            for numero, (comando, duracion) in enumerate(KATA, start=1):
                if numero > 1:
                    print(f"  [{numero:2d}/{len(KATA)}] {comando}", flush=True)
                await self.execute(comando)
                fin = loop.time() + duracion
                while loop.time() < fin:
                    await self._send(echo=False)
                    await asyncio.sleep(0.05)
        finally:
            self._esperar_brazo = True
        await self.execute("parar")
        return f"Kata terminada en {loop.time() - inicio:.0f} s"

    def _cmd_limpiar(self, args: list[str]) -> str:
        """Limpia la pantalla."""
        print("\033[2J\033[H", end="")
        return ""

    def _cmd_clear(self, args: list[str]) -> str:
        return self._cmd_limpiar(args)

    async def _cmd_calibrar(self, args: list[str]) -> str:
        """Asistente: fija la posicion de reposo de cada articulacion.

        Coloca el brazo en la posicion que quieres que sea el "cero" (puedes
        hacerlo con el robot apagado y marcando donde se queda) y despues
        ajustalo byte a byte hasta que te cuadre.
        """
        if args:
            joints = [resolve_joint(args[0])]
        else:
            joints = list(Joint)

        print("\nColoca los brazos donde quieras y ajusta con +1 / -1.", flush=True)
        print("  'ok' acepta el byte, 'skip' lo deja como estaba, 'q' sale.", flush=True)

        for joint in joints:
            byte = self.robot.command.neutral.get(joint, SERVO_CENTER)
            print(f"\n== {joint.name.lower()} (byte {byte}) ==", flush=True)
            while True:
                try:
                    entrada = (
                        await asyncio.to_thread(input, "  bra> ")
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return "Calibracion cancelada."
                if entrada in ("q", "salir", "quit"):
                    return "Calibracion cancelada."
                if entrada in ("skip", "saltar"):
                    break
                if entrada in ("ok", "aceptar", ""):
                    self.robot.command.neutral[joint] = byte
                    self.robot.command.raw_servos.pop(joint, None)
                    await self._send()
                    print(
                        f"  -> {joint.name.lower()}: cero en el byte {byte}",
                        flush=True,
                    )
                    break
                if entrada in ("+1", "+", "arriba"):
                    byte = min(SERVO_BYTE_MAX, byte + 1)
                elif entrada in ("-1", "-", "abajo"):
                    byte = max(0, byte - 1)
                else:
                    print("  (usa +1, -1, ok, skip o q)", flush=True)
                    continue
                # movemos el brazo ahi y lo mandamos al robot
                self.robot.command.set_raw_servo(joint, byte)
                await self._send()
                print(f"  byte {byte}", flush=True)
        return "Calibracion terminada: 'calib guardar' para conservarla."

    def _cmd_neutro(self, args: list[str]) -> str:
        """Muestra (o fija) el byte que se considera 'angulo 0'."""
        if not args:
            lines = []
            for joint in Joint:
                byte = self.robot.command.neutral.get(joint, SERVO_CENTER)
                marca = (
                    "" if joint not in self.robot.command.neutral else "  (calibrado)"
                )
                lines.append(f"  {joint.name.lower():15s}: byte {byte}{marca}")
            return "\n".join(lines)
        joint = resolve_joint(args[0])
        if len(args) < 2:
            raise ConsoleError("Uso: neutro <articulacion> <byte 0-40>")
        try:
            byte = int(args[1])
        except ValueError as exc:
            raise ConsoleError(f"Byte inválido: {args[1]!r}") from exc
        if not 0 <= byte <= SERVO_BYTE_MAX:
            raise ConsoleError(f"El byte va de 0 a {SERVO_BYTE_MAX}")
        self.robot.command.neutral[joint] = byte
        return f"{joint.name.lower()}: cero en el byte {byte}"

    async def _cmd_calib(self, args: list[str]) -> str:
        """Calibrado de los brazos, igual que el asistente de la app oficial.

        `calib`                -> ver los offsets
        `calib <art> <+n>`     -> ajustar el offset de una articulacion
        `calib <art> = <n>`    -> poner el offset a un valor exacto
        `calib guardar|cargar|reset`
        """
        if not args:
            return self._calib_show()

        accion = args[0].lower()
        if accion in ("guardar", "save"):
            return self._calib_save()
        if accion in ("cargar", "load"):
            texto = self._calib_load()
            await self._send()
            return texto
        if accion in ("reset", "reiniciar"):
            self.robot.command.offsets.clear()
            await self._send()
            return "Offsets a cero."

        joint = resolve_joint(args[0])
        if len(args) < 2:
            raise ConsoleError("Uso: calib <articulacion> <+n | = n>")
        # admite "calib art = 5" (shlex parte el "=" en tres piezas)
        if args[1] == "=" and len(args) > 2:
            absoluto, valor = True, args[2]
        else:
            absoluto, valor = args[1].startswith("="), args[1]
        valor = valor.replace("=", "").strip()
        try:
            cantidad = float(valor)
        except ValueError as exc:
            raise ConsoleError(f"Número inválido: {valor!r}") from exc
        if absoluto:
            self.robot.command.offsets[joint] = cantidad
        else:
            self.robot.command.offsets[joint] = (
                self.robot.command.offsets.get(joint, 0.0) + cantidad
            )
        # reenviamos el paquete para que el robot refleje la calibracion ya
        await self._send()
        return self._calib_line(joint)

    def _calib_line(self, joint: Joint) -> str:
        """Describe el offset de una articulacion y su efecto en el byte."""
        offset = self.robot.command.offsets.get(joint, 0.0)
        byte = self.robot.command.servo_byte(joint)
        texto = f"{joint.name.lower()}: offset {offset:+g} grados -> byte {byte}"
        # un byte son 8.5 grados: si el offset es pequeño no se ve nada
        if abs(offset) < SERVO_SCALE / 2 and offset:
            texto += " (casi no se nota: 1 byte = 8.5 grados)"
        return texto

    def _calib_show(self) -> str:
        offsets = self.robot.command.offsets
        neutral = self.robot.command.neutral
        if not offsets and not neutral:
            return "Sin calibracion (offsets a 0 y ceros en el byte 20)."
        lines = []
        for joint in Joint:
            if joint in offsets or joint in neutral:
                off = offsets.get(joint, 0.0)
                cero = neutral.get(joint, SERVO_CENTER)
                lines.append(
                    f"  {joint.name.lower():15s}: offset {off:+g} grados, cero byte {cero}"
                )
        return "\n".join(lines)

    def _calib_path(self) -> Path:
        return calibration_path()

    def _calib_save(self) -> str:
        self._offsets = dict(self.robot.command.offsets)
        self._neutral = dict(self.robot.command.neutral)
        ruta = save_calibration(self.robot.command)
        return f"Calibracion guardada en {ruta}"

    def _calib_load(self) -> str:
        if not load_calibration(self.robot.command):
            return (
                f"No hay fichero de calibracion "
                f"({CALIBRATION_FILE} ni {CALIBRATION_DEFAULT})"
            )
        self._offsets = dict(self.robot.command.offsets)
        self._neutral = dict(self.robot.command.neutral)
        return self._calib_show()

    def _cmd_bruto(self, args: list[str]) -> str:
        """Envia un byte crudo en una articulacion (experimentos)."""
        if len(args) != 2:
            raise ConsoleError("Uso: bruto <articulacion> <byte 0-255>")
        joint = resolve_joint(args[0])
        try:
            value = int(args[1])
        except ValueError as exc:
            raise ConsoleError(f"Byte invalido: {args[1]!r}") from exc
        if not 0 <= value <= 255:
            raise ConsoleError("El byte va de 0 a 255")
        self.robot.command.set_raw_servo(joint, value)
        return f"{joint.name.lower()}: byte crudo {value}"

    def _cmd_raw(self, args: list[str]) -> str:
        return self._cmd_bruto(args)

    @staticmethod
    def _angle(joint: Joint, text: str) -> float:
        try:
            value = float(text)
        except ValueError as exc:
            raise ConsoleError(f"Angulo invalido: {text!r}") from exc
        low, high = SERVO_LIMITS[joint]
        if not low <= value <= high:
            raise ConsoleError(
                f"{joint.name.lower()}: el rango util es {low}..{high} grados "
                f"(has pedido {value:g})"
            )
        return value

    # estado

    def _cmd_reset(self, args: list[str]) -> str:
        # se conserva la calibracion (offsets y ceros)
        self.robot.command = Command()
        self.robot.command.offsets.update(self._offsets)
        self.robot.command.neutral.update(self._neutral)
        return "Servos a 0 y ruedas paradas (se conserva la calibracion)."

    def _cmd_estado(self, args: list[str]) -> str:
        cmd = self.robot.command
        lines = [
            f"  LED       : {cmd.led.name.lower()}",
            f"  ruedas    : izquierda {cmd.left_speed:g}  derecha {cmd.right_speed:g}",
        ]
        for joint in Joint:
            if joint in cmd.raw_servos:
                lines.append(
                    f"  {joint.name.lower():15s}: byte {cmd.raw_servos[joint]} (crudo)"
                )
            elif joint in cmd.servos:
                lines.append(
                    f"  {joint.name.lower():15s}: {cmd.servos[joint]:g} grados"
                    f"  ->  byte {cmd.servo_byte(joint)}"
                )
            else:
                lines.append(f"  {joint.name.lower():15s}: sin mover")
        return "\n".join(lines)

    def _cmd_state(self, args: list[str]) -> str:
        return self._cmd_estado(args)

    def _cmd_dump(self, args: list[str]) -> str:
        return self.robot.command.describe()

    async def _cmd_hex(self, args: list[str]) -> str:
        """Envia un paquete crudo escrito en hexadecimal."""
        try:
            payload = bytes(int(token, 16) for token in args)
        except ValueError as exc:
            raise ConsoleError(f"Bytes invalidos: {exc}") from exc
        if not payload:
            raise ConsoleError("Uso: hex A5 00 00 ...")
        if self.dry_run:
            print(f"  -> {payload.hex(' ')}")
        else:
            await self.robot.send_raw(payload)
            print(f"  -> {payload.hex(' ')}")
        return f"Enviados {len(payload)} bytes."

    # -- bucle principal --------------------------------------------------

    async def run(self) -> None:
        print(HELP)
        print()
        loop = asyncio.get_running_loop()
        ctrl_c = 0
        self._load_history()
        try:
            while True:
                self._last_input = loop.time()
                try:
                    line = await asyncio.to_thread(input, "airo> ")
                    ctrl_c = 0
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    ctrl_c += 1
                    if ctrl_c >= 2:
                        print("\n[*] Saliendo (doble Ctrl-C).")
                        break
                    print("(vuelve a pulsar Ctrl-C para salir, o escribe 'salir')")
                    continue
                line = line.strip()
                if not line:
                    continue
                if line.lower() in ("salir", "quit", "exit"):
                    break
                try:
                    result = await self.execute(line)
                except ConsoleError as exc:
                    print(f"  !! {exc}")
                    continue
                except AiroNotFound as exc:
                    print(f"  !! {exc}")
                    continue
                except Exception as exc:
                    print(f"  !! {type(exc).__name__}: {exc}")
                    continue
                if result:
                    print(result)
                await self._send()
        finally:
            self._save_history()

    # -- historial --------------------------------------------------------

    def _load_history(self) -> None:
        """Activa el historial de readline (flechas arriba/abajo) y carga el fichero."""
        if readline is None:  # pragma: no cover - Windows
            return
        try:
            readline.set_history_length(2000)
            if HISTORY_FILE.exists():
                readline.read_history_file(str(HISTORY_FILE))
        except Exception:  # pragma: no cover
            pass

    def _save_history(self) -> None:
        if readline is None:  # pragma: no cover - Windows
            return
        try:
            readline.write_history_file(str(HISTORY_FILE))
        except Exception:  # pragma: no cover
            pass

    def _cmd_historial(self, args: list[str]) -> str:
        """Muestra los comandos recientes (las flechas los recuperan)."""
        if readline is None:  # pragma: no cover - Windows
            return "El historial no está disponible en esta plataforma."
        total = readline.get_current_history_length()
        lineas = [
            readline.get_history_item(i) for i in range(1, total + 1)
        ]
        if not lineas:
            return "Historial vacío."
        return "\n".join(f"{i:4d}  {texto}" for i, texto in enumerate(lineas, 1))

    async def run_once(self, line: str) -> None:
        """Ejecuta una sola linea (modo --exec)."""
        result = await self.execute(line)
        if result:
            print(result)
        await self._send()


async def _shutdown(console: Console) -> None:
    """Para el robot y cierra la conexion antes de morir."""
    print("\n[*] Cerrando...", flush=True)
    # primero a velocidad 0: si el proceso muere con las ruedas en marcha,
    # el robot se queda dando vueltas sin que nadie lo pare
    try:
        await console.parar()
    except Exception:
        pass
    try:
        await console.disconnect()
    except Exception:
        pass
    os._exit(0)


async def run_console(args: argparse.Namespace) -> int:
    robot = crear_robot(address=args.address, scan_timeout=args.scan_timeout)
    console = Console(
        robot,
        keepalive=not args.no_keepalive,
        watchdog=args.watchdog,
        dry_run=args.dry_run,
        echo=not args.quiet,
    )

    # Si matan el proceso (SIGTERM) hay que cerrar el BLE: si no, el robot se
    # queda "conectado" y no admite nuevas conexiones hasta que se apague.
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(_shutdown(console)))
    except (NotImplementedError, RuntimeError):  # pragma: no cover - Windows
        pass

    try:
        if not args.dry_run and not args.no_connect:
            await console.connect(args.address)
            await console.start_keepalive()
            print(f"Conectado a {robot.address}. Escribe 'ayuda' para la lista de comandos.")
        elif args.dry_run:
            print("Modo --dry-run: no se conecta a nada, solo se muestran los paquetes.")
        else:
            print("Arrancando sin conectar. Usa 'conectar' para buscar el robot.")
        print()
    except AiroNotFound as exc:
        print(f"No se encontro el robot: {exc}")
        return 1
    except Exception as exc:
        print(f"No se pudo conectar: {exc}")
        return 1

    try:
        if args.exec:
            for line in args.exec:
                await console.run_once(line)
            return 0
        await console.run()
        return 0
    finally:
        try:
            await console.disconnect()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="airo_ble.console",
        description="Consola interactiva para mandar comandos al Clementoni AIRO",
    )
    parser.add_argument(
        "--address", default=None, help="MAC del robot (por defecto se busca 'AIRo')"
    )
    parser.add_argument("--scan-timeout", type=float, default=15.0)
    parser.add_argument("--no-connect", action="store_true", help="no conectar al arrancar")
    parser.add_argument(
        "--no-keepalive", action="store_true", help="no refrescar el paquete cada 50 ms"
    )
    parser.add_argument(
        "--watchdog",
        type=float,
        default=5.0,
        help="segundos sin comandos antes de parar las ruedas (0 = sin limite)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="no conectar: solo mostrar los paquetes"
    )
    parser.add_argument("--quiet", action="store_true", help="no mostrar el hex de cada envio")
    parser.add_argument(
        "--exec",
        action="append",
        default=[],
        help="ejecuta un comando y sale (repetible)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(run_console(args))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
