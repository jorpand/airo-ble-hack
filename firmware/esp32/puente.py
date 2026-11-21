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
        vistos = await self.cliente.escanear(5000)
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
        """Busca el robot y se conecta."""
        if self.cliente.conn >= 0:
            return 200, {"ok": True, "mac": self.cliente.mac_robot, "ya_conectado": True}
        addr, addr_type = await self.cliente.buscar_robot(20000, 5000, sondear=False)
        if addr is None or addr_type is None:
            return 409, {"ok": False, "error": "no se encuentra el robot"}
        if not await self.cliente.conectar(addr, addr_type, 25000, 20000):
            return 409, {"ok": False, "error": self.cliente.error}
        if not await self.cliente.descubrir(15000):
            self.cliente.desconectar()
            return 409, {"ok": False, "error": self.cliente.error}
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


async def servir():
    """Levanta el servidor HTTP del puente. No vuelve nunca."""
    puente = Puente()
    await http_srv.servir("0.0.0.0", PUERTO, puente.rutas())
