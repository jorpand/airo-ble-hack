"""El puente BLE del ESP32-S3: HTTP por un lado, el robot por otro.

Este modulo tiene la logica del puente (las rutas y el mantenimiento de la
conexion). El arranque esta en `main.py`, para que este se pueda importar en
los tests sin levantar el servidor.

Las rutas:

| Ruta | Que hace |
|---|---|
| `GET /salud` | "pong": para comprobar que el puente vive |
| `GET /estado` | estado de la conexion con el robot |
| `GET /escanear` | lo que se ve por BLE ahora mismo |
| `POST /escribir` | escribe el cuerpo (bytes crudos) en el robot |
| `POST /conectar` | busca el robot y se conecta |
| `POST /desconectar` | cierra la conexion |

El puente **no sabe nada del protocolo AIRO**: recibe bytes crudos y los
escribe en la characteristic `FFF1`. El paquete de 20 bytes lo construye
`airo_ble/protocol.py` en el portatil (ver `docs/plan-esp32.md`).
"""

import asyncio

import ble_robot
import http_srv

#: Puerto del servidor HTTP del puente.
PUERTO = 8080

#: Como se llama el puente en la red.
HOSTNAME = "airo-bridge"

#: Cada cuanto se reenvia el ultimo paquete al robot (milisegundos).
#:
#: La app oficial refresca cada 50 ms, asi que se copia ese ritmo.
REFRESCO_MS = 50

#: Cuantos reenvios seguidos pueden fallar antes de dejar de reenviar.
FALLOS_MAX = 3

#: Cuanto escanea la ruta `/escanear` (milisegundos).
#:
#: Es corto a proposito: la ruta tiene que responder rapido y el escaneo
#: largo lo hace la tarea de fondo.
ESCANEO_MS = 3000

#: Cuanto espera la ruta `/conectar` a que la tarea de fondo pille al robot
#: (milisegundos). El robot se anuncia a ratos, asi que esto es un rato.
ESPERA_CONEXION_MS = 30000


class Puente:
    """El puente: une el HTTP con el BLE."""

    def __init__(self):
        self.cliente = ble_robot.ClienteAiro()

    # -- Rutas -------------------------------------------------------------

    async def r_salud(self, peticion):
        """Comprobar que el puente vive."""
        return 200, {"ok": True, "servidor": "airo-bridge"}

    async def r_estado(self, peticion):
        """Como esta la conexion con el robot."""
        return 200, self.cliente.estado()

    async def r_escanear(self, peticion):
        """Lo que se ve por BLE ahora mismo."""
        vistos = await self.cliente.escanear(ESCANEO_MS)
        dispositivos = [
            {"mac": ble_robot.mac(addr), "nombre": nombre, "rssi": rssi}
            for addr, (_t, nombre, rssi) in vistos.items()
        ]
        return 200, {"dispositivos": dispositivos}

    async def r_escribir(self, peticion):
        """Escribe el cuerpo (bytes crudos) en la characteristic del robot."""
        datos = peticion.cuerpo
        if not datos:
            return 400, {"error": "cuerpo vacio"}
        ok = await self.cliente.escribir(datos)
        if not ok:
            return 409, {"error": self.cliente.error or "no se pudo escribir"}
        return 200, {"ok": True, "bytes": len(datos)}

    async def r_conectar(self, peticion):
        """Espera a que el robot este conectado.

        OJO: esta ruta **no escanea**. El escaneo lo hace la tarea de fondo
        (`mantener_conexion`), que esta siempre mirando por el robot: si
        esta ruta escaneara tambien, las dos cosas se pelearian por el radio
        (NimBLE no admite dos escaneos a la vez y contesta `EALREADY`).

        Asi que aqui solo se espera a que la tarea de fondo lo pille.
        """
        if self.cliente.conn >= 0:
            return 200, {"ok": True, "mac": self.cliente.mac_robot, "ya_conectado": True}
        ok = await ble_robot.esperar_hasta(
            lambda: self.cliente.conn >= 0, ESPERA_CONEXION_MS
        )
        if not ok:
            return 409, {"ok": False, "error": "no se encuentra el robot"}
        return 200, {"ok": True, "mac": self.cliente.mac_robot}

    async def r_desconectar(self, peticion):
        """Cierra la conexion con el robot."""
        self.cliente.desconectar()
        return 200, {"ok": True}

    def rutas(self):
        """La tabla de rutas del servidor."""
        return {
            ("GET", "/salud"): self.r_salud,
            ("GET", "/estado"): self.r_estado,
            ("GET", "/escanear"): self.r_escanear,
            ("POST", "/escribir"): self.r_escribir,
            ("POST", "/conectar"): self.r_conectar,
            ("POST", "/desconectar"): self.r_desconectar,
        }

    # -- Mantenimiento -----------------------------------------------------

    async def mantener_conexion(self):
        """Se conecta al robot en cuanto aparece y se reconecta si se cae."""
        while True:
            if self.cliente.conn < 0:
                addr, addr_type = await self.cliente.buscar_robot(
                    15000, 5000, sondear=False
                )
                if addr is not None and addr_type is not None:
                    print("robot encontrado, conectando...")
                    if await self.cliente.conectar(addr, addr_type, 25000, 20000):
                        if await self.cliente.descubrir(15000):
                            print(f"conectado al robot ({self.cliente.mac_robot})")
                        else:
                            print(f"sin FFF0: {self.cliente.error}")
                            self.cliente.desconectar()
                    else:
                        print(f"no se pudo conectar: {self.cliente.error}")
            await asyncio.sleep(2)

    async def refrescar(self):
        """Reenvia el ultimo paquete cada 50 ms, como la app oficial.

        El firmware del robot devuelve los brazos al reposo si deja de
        recibir paquetes, asi que el paquete se reenvia sin parar. Lo hace
        la placa y no el portatil: mandar 20 peticiones HTTP por segundo
        seria mucho trafico para tan poca informacion (y el portatil solo
        tiene que mandar el paquete cuando **cambia**).

        Si el robot no contesta tres veces seguidas, se deja de reenviar
        (el error se ve en /estado) hasta que llegue un paquete nuevo.
        """
        while True:
            await asyncio.sleep(REFRESCO_MS / 1000)
            if self.cliente.conn < 0 or not self.cliente.ultimo:
                continue
            if self.cliente.fallos >= FALLOS_MAX:
                continue
            if not await self.cliente.refrescar():
                print(f"reenvio fallido: {self.cliente.error}")


async def servir():
    """Levanta el servidor HTTP del puente. No vuelve nunca."""
    puente = Puente()
    await http_srv.servir("0.0.0.0", PUERTO, puente.rutas())
