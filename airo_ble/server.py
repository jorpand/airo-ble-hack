#!/usr/bin/env python3
"""
Servidor local para controlar el AIRO desde Scratch (o desde el navegador).

El navegador no puede hablar BLE con el robot, asi que este programa se
encarga: escucha en `localhost` y traduce las peticiones HTTP en comandos
BLE.

    python3 -m airo_ble.server            # http://localhost:8765
    python3 -m airo_ble.server --port 9000
    python3 -m airo_ble.server --no-connect   # arranca sin buscar el robot

Abre http://localhost:8765 en el navegador para ver una pagina de pruebas con
botones para cada comando.

API (JSON):

    POST /api/command   {"type": "move", "left": 1, "right": 0}
                         {"type": "stop"}
                         {"type": "led", "mode": "on|off|flash|fade"}
                         {"type": "pose", "joint": "left_arm", "angle": 30}
                         {"type": "arm", "side": "left|right", "pose": "arriba"}
                         {"type": "arm", "side": "left|right", "joint": "hombro|codo",
                          "angle": 90, "duration": 3}
                         {"type": "kata"}
                         {"type": "reset"}
    GET  /api/status    -> estado actual del robot

El comando "arm" acepta: "side" (que brazo), "pose" (la posicion) o "joint"
(que articulacion: "todo", "hombro" o "codo") + "angle" (el angulo exacto),
y "duration" (los segundos del movimiento: 0 = de golpe, > 0 = lento, en
rampa).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from airo_ble.arms import BrazoError, resolver_brazo, resolver_objetivos
from airo_ble.bridge import crear_robot
from airo_ble.cliente import ClienteRobot
from airo_ble.console import load_calibration
from airo_ble.protocol import JOINT_NAMES, SERVO_CENTER, Joint, Led

DEFAULT_PORT = 8765


class AiroService:
    """Mantiene la conexion BLE y aplica los comandos que le llegan."""

    def __init__(
        self,
        address: str | None,
        scan_timeout: float = 10.0,
        connect_robot: bool = True,
    ) -> None:
        self.address = address
        self.scan_timeout = scan_timeout
        self.connect_robot = connect_robot
        self.robot: ClienteRobot = crear_robot(
            address=address, scan_timeout=scan_timeout
        )
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.ready = threading.Event()
        self.error: str | None = None
        self._kata_task: asyncio.Task[None] | None = None
        #: El movimiento de brazo en curso (lento o de golpe). El candado
        #: serializa los movimientos: si llega otro antes de que termine el
        #: anterior, este espera a que el servo llegue (si no, el servo
        #: cambia de destino a medio camino y el movimiento no se ve).
        self._movimiento_lock = asyncio.Lock()
        self._movimiento_task: asyncio.Task[None] | None = None

    # -- ciclo de vida ----------------------------------------------------

    def start(self) -> None:
        self.thread.start()
        self.ready.wait(timeout=30)

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as exc:  # pragma: no cover
            self.error = str(exc)
        finally:
            self.loop.close()

    async def _main(self) -> None:
        if not self.connect_robot:
            self.ready.set()
            await asyncio.sleep(3600)
            return
        # el modulo BLE del robot se duerme: reintentamos hasta que aparezca
        while True:
            try:
                await self.robot.connect()
                self.error = None
                self.ready.set()
                if load_calibration(self.robot.command):
                    print("[airo] calibracion cargada", flush=True)
                print(f"[airo] conectado a {self.robot.address}", flush=True)
                await self._keepalive()
                return
            except Exception as exc:
                self.error = str(exc)
                print(f"[airo] {exc}", flush=True)
                print("[airo] reintento cada 10 s (enciende el robot)", flush=True)
                await asyncio.sleep(10)

    async def _keepalive(self) -> None:
        """Refresca el paquete sin parar (el firmware devuelve los brazos al
        reposo si deja de recibir) y reconecta si se cae el enlace."""
        while True:
            try:
                await asyncio.sleep(0.05)
                await self.robot.send(self.robot.command)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[airo] se ha cortado la conexion: {exc}", flush=True)
                try:
                    await self.robot.disconnect()
                except Exception:
                    pass
                try:
                    await self.robot.connect()
                    print(f"[airo] reconectado a {self.robot.address}", flush=True)
                except Exception as exc2:
                    print(
                        f"[airo] no se pudo reconectar: {exc2}\n"
                        f"       apaga y enciende el robot y espera unos segundos.",
                        flush=True,
                    )
                    await asyncio.sleep(5)

    # -- comandos ---------------------------------------------------------

    def call(self, comando: dict[str, Any]) -> dict[str, Any]:
        """Aplica un comando (desde cualquier hilo)."""
        if self.loop is None:
            return {"ok": False, "error": "El servidor no esta listo"}
        futuro = asyncio.run_coroutine_threadsafe(self._apply(comando), self.loop)
        try:
            return futuro.result(timeout=10)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _apply(self, comando: dict[str, Any]) -> dict[str, Any]:
        tipo = str(comando.get("type", "")).lower()
        cmd = self.robot.command
        try:
            if tipo == "move":
                izquierda = float(comando.get("left", 0))
                derecha = float(comando.get("right", 0))
                cmd.left_speed = max(-3.0, min(3.0, izquierda))
                cmd.right_speed = max(-3.0, min(3.0, derecha))
            elif tipo == "stop":
                cmd.stop()
            elif tipo == "led":
                cmd.led = Led[str(comando.get("mode", "off")).upper()]
            elif tipo == "pose":
                nombre = str(comando.get("joint", "")).lower().replace("-", "_")
                joint = JOINT_NAMES.get(nombre)
                if joint is None:
                    return {"ok": False, "error": f"Articulación desconocida: {nombre}"}
                cmd.set_joint(joint, float(comando.get("angle", 0)))
            elif tipo == "arm":
                lado = str(comando.get("side", "left")).lower()
                pose = str(comando.get("pose", "") or "").lower()
                articulacion = str(comando.get("joint", "todo") or "todo").lower()
                angulo = comando.get("angle")
                duracion = float(comando.get("duration", 0) or 0)
                try:
                    if not pose and angulo is None:
                        # sin destino: la pose de siempre
                        pose = "medio"
                    objetivos = resolver_objetivos(
                        lado,
                        pose=pose or None,
                        articulacion=articulacion,
                        angulo=angulo,
                    )
                except BrazoError as exc:
                    return {"ok": False, "error": str(exc)}
                except (TypeError, ValueError) as exc:
                    return {"ok": False, "error": f"Destino inválido: {exc}"}
                await self._mover_brazo(objetivos, duracion)
            elif tipo == "kata":
                self._start_kata()
            elif tipo == "reset":
                cmd.stop()
                cmd.servos.clear()
            else:
                return {"ok": False, "error": f"Comando desconocido: {tipo}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if self.robot.is_connected:
            await self.robot.send(cmd)
        return {"ok": True, "estado": self.status()}

    def _start_kata(self) -> None:
        if self._kata_task is not None and not self._kata_task.done():
            self._kata_task.cancel()
        self._kata_task = asyncio.create_task(self._kata())

    async def _mover_brazo(
        self, objetivos: dict[Joint, float], duracion: float
    ) -> None:
        """Mueve el brazo con el modelo de acciones.

        - Sin tiempo ("de golpe"): el destino de una vez y se espera a que
          el servo llegue (con un minimo de un segundo: si se le manda el
          destino nuevo antes de tiempo, el servo cambia de destino a medio
          camino y el movimiento no llega a verse).
        - Con tiempo: **lento**. El destino viaja hasta el servo durante ese
          tiempo. Va en segundo plano (la peticion de Scratch no espera) y
          la rampa la calculan `arms.pasos_rampa()`, los mismos pasos que
          usan la sesion de la API y la consola.

        El candado serializa los movimientos: si llega otro antes de que
        termine este, espera a que el servo llegue.
        """
        from airo_ble.arms import tiempo_de_viaje

        if duracion > 0:
            # El movimiento lento espera a que termine el anterior (si no, se
            # pisan) y sigue en segundo plano.
            if self._movimiento_task is not None and not self._movimiento_task.done():
                try:
                    await self._movimiento_task
                except Exception:
                    pass
            self._movimiento_task = asyncio.create_task(
                self._mover_brazo_lento(objetivos, duracion)
            )
            return

        async with self._movimiento_lock:
            actuales = dict(self.robot.command.servos)
            for joint, angle in objetivos.items():
                self.robot.command.set_joint(joint, angle)
            if self.robot.is_connected:
                # Sin robot no hay servo al que esperar.
                await asyncio.sleep(tiempo_de_viaje(objetivos, actuales))

    async def _mover_brazo_lento(
        self, objetivos: dict[Joint, float], duracion: float
    ) -> None:
        """El movimiento lento: el destino viaja hasta el servo."""
        from airo_ble.arms import PASOS_POR_SEGUNDO, duracion_de_accion, pasos_rampa

        async with self._movimiento_lock:
            actuales = dict(self.robot.command.servos)
            # La rampa dura lo pedido, pero nunca menos que lo que tarda el
            # servo: si no, no llegaria al destino.
            duracion = duracion_de_accion(objetivos, actuales, duracion)
            for paso in pasos_rampa(objetivos, duracion, actuales):
                for joint, angulo in paso.items():
                    self.robot.command.set_joint(joint, angulo)
                await asyncio.sleep(1 / PASOS_POR_SEGUNDO)

    async def _kata(self) -> None:
        from airo_ble.console import KATA

        for comando, duracion in KATA:
            partes = comando.split()
            if not partes:
                continue
            if partes[0] == "led":
                self.robot.command.led = Led[partes[1].upper()]
            elif partes[0] == "brazo":
                lado, pose = partes[1], partes[2]
                for joint, angle in resolver_brazo(lado, pose).items():
                    self.robot.command.set_joint(joint, angle)
            elif partes[0] in ("avanzar", "atras", "izquierda", "derecha"):
                self._move(partes[0], float(partes[1]) if len(partes) > 1 else 1.0)
            elif partes[0] == "parar":
                self.robot.command.stop()
            fin = asyncio.get_running_loop().time() + duracion
            while asyncio.get_running_loop().time() < fin:
                try:
                    await self.robot.send(self.robot.command)
                except Exception:
                    break
                await asyncio.sleep(0.05)
        self.robot.command.stop()

    def _move(self, direccion: str, velocidad: float) -> None:
        cmd = self.robot.command
        if direccion == "avanzar":
            cmd.left_speed = cmd.right_speed = velocidad
        elif direccion == "atras":
            cmd.left_speed = cmd.right_speed = -velocidad
        elif direccion == "izquierda":
            cmd.left_speed, cmd.right_speed = velocidad, -velocidad
        elif direccion == "derecha":
            cmd.left_speed, cmd.right_speed = -velocidad, velocidad

    def stop(self) -> None:
        """Cierra la conexion BLE (para no dejar el robot enganchado)."""
        if self.loop is None:
            return
        try:
            futuro = asyncio.run_coroutine_threadsafe(self._stop(), self.loop)
            futuro.result(timeout=8)
        except Exception:
            pass

    async def _stop(self) -> None:
        if self._kata_task is not None:
            self._kata_task.cancel()
        # parar antes de soltar el BLE: si el servidor se apaga con el robot
        # en marcha, este se queda dando vueltas
        self.robot.command.stop()
        try:
            await self.robot.send(self.robot.command)
        except Exception:
            pass
        try:
            await self.robot.disconnect()
        except Exception:
            pass

    def status(self) -> dict[str, Any]:
        cmd = self.robot.command
        return {
            "conectado": bool(self.robot.is_connected),
            "led": cmd.led.name.lower(),
            "izquierda": cmd.left_speed,
            "derecha": cmd.right_speed,
            "brazos": {
                joint.name.lower(): {
                    "angulo": cmd.servos.get(joint, 0.0),
                    "byte": cmd.servo_byte(joint),
                    # El byte que es "angulo 0" en esta articulacion: sin el,
                    # el hombro derecho (calibrado en 16) no se puede deshacer
                    # el escalado del servo.
                    "neutral": cmd.neutral.get(joint, SERVO_CENTER),
                }
                for joint in Joint
            },
        }


class Handler(BaseHTTPRequestHandler):
    service: AiroService  # se inyecta al crear el servidor

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/status"):
            self._json(self.service.status())
        elif self.path in ("/", "/index.html"):
            self._html()
        elif self.path.startswith("/scratch3_airo/"):
            # la extension de Scratch se carga por URL desde TurboWarp
            self._fichero(self.path[len("/scratch3_airo/"):])
        else:
            self._json({"ok": False, "error": "no encontrado"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/command"):
            self._json({"ok": False, "error": "no encontrado"}, status=404)
            return
        try:
            longitud = int(self.headers.get("Content-Length", 0))
            cuerpo = json.loads(self.rfile.read(longitud) or b"{}")
        except Exception as exc:
            self._json({"ok": False, "error": f"JSON inválido: {exc}"}, status=400)
            return
        self._json(self.service.call(cuerpo))

    def _json(self, datos: Any, status: int = 200) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _fichero(self, nombre: str) -> None:
        """Sirve un fichero de la carpeta scratch3_airo (la extension)."""
        base = Path(__file__).resolve().parent / "scratch3_airo"
        destino = (base / nombre.lstrip("/")).resolve()
        if not str(destino).startswith(str(base)) or not destino.is_file():
            self._json({"ok": False, "error": "no encontrado"}, status=404)
            return
        tipo = {
            ".js": "application/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(destino.suffix, "application/octet-stream")
        cuerpo = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self._cors()
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _html(self) -> None:
        pagina = Path(__file__).resolve().parent / "scratch3_airo" / "test.html"
        if not pagina.exists():
            self._json({"ok": False, "error": "falta test.html"}, status=404)
            return
        cuerpo = pagina.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # silencio: el servidor no debe ensuciar la terminal


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor local del AIRO para Scratch")
    parser.add_argument("--address", default=None, help="MAC del robot")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--scan-timeout", type=float, default=10.0)
    parser.add_argument("--no-connect", action="store_true", help="no buscar el robot al arrancar")
    args = parser.parse_args()

    servicio = AiroService(args.address, args.scan_timeout, connect_robot=not args.no_connect)
    if not args.no_connect:
        print("[airo] buscando el robot...", flush=True)
        servicio.thread.start()
    else:
        servicio.thread.start()
        servicio.ready.set()

    Handler.service = servicio
    servidor = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    servidor.daemon_threads = True

    def cerrar() -> None:
        # cerrar el BLE antes de salir: si no, el robot se queda con el
        # enlace enganchado y no admite conexiones hasta que lo apagues
        print("\n[airo] parando", flush=True)
        servidor.shutdown()
        servicio.stop()

    import signal

    def _senal(_sig: int, _frame: Any) -> None:
        import threading

        threading.Thread(target=cerrar, daemon=True).start()

    signal.signal(signal.SIGINT, _senal)
    signal.signal(signal.SIGTERM, _senal)

    print(f"[airo] servidor en http://localhost:{args.port}", flush=True)
    print(f"[airo] pagina de pruebas en http://localhost:{args.port}/", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        servicio.stop()


if __name__ == "__main__":
    main()
