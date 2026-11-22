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
import led

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
#: Es corto a proposito: la ruta tiene que responder rapido. El escaneo
#: largo lo hace la ruta `/conectar`, que es la que busca al robot.
ESCANEO_MS = 3000

#: Cuanto busca la ruta `/conectar` al robot (milisegundos).
#:
#: El robot se anuncia a ratos, asi que esto es un rato.
ESPERA_BUSQUEDA_MS = 15000

#: Si la placa se conecta al robot **sola**, en cuanto lo ve.
#:
#: Con False (lo normal), el robot se conecta solo cuando alguien lo pide
#: (`POST /conectar`), que es lo que hace el boton "Conectar" de la web: el
#: robot se queda como esta hasta que se le pide. Con True, la placa lo
#: pilla en cuanto aparece y lo mantiene (comodo si el robot se duerme, pero
#: el enlace se queda abierto solo).
AUTO_CONECTAR = False


class Puente:
    """El puente: une el HTTP con el BLE."""

    def __init__(self, auto_conectar=AUTO_CONECTAR, indicador=None):
        self.cliente = ble_robot.ClienteAiro()
        #: Si la placa agarra al robot por su cuenta.
        self.auto_conectar = auto_conectar
        #: La busqueda y la conexion van en un solo candado: si dos
        #: peticiones de "conectar" se pisan, se pelean por el robot.
        self.lock_conexion = asyncio.Lock()
        #: El LED RGB de la placa: el color es el estado del enlace y el
        #: destello es la actividad (trafico de comandos).
        self.led = indicador if indicador is not None else led.Led()
        #: Si se esta buscando al robot (el LED esta en azul).
        self.buscando = False
        self.actualizar_led()

    # -- El LED ------------------------------------------------------------

    def color_led(self):
        """El color que le toca al LED segun el estado del enlace."""
        if self.cliente.conn >= 0:
            return led.VERDE
        if self.buscando:
            return led.AZUL
        return led.ROJO

    def actualizar_led(self):
        """Pone el LED en el color del estado actual."""
        self.led.estado(self.color_led())

    def parpadear(self):
        """Manda parpadear el LED: hay trafico de comandos."""
        self.led.destello()

    # -- Rutas -------------------------------------------------------------

    async def r_salud(self, peticion):
        """Comprobar que el puente vive."""
        return 200, {"ok": True, "servidor": "airo-bridge"}

    async def r_estado(self, peticion):
        """Como esta la conexion con el robot."""
        estado = self.cliente.estado()
        # El color del LED va aqui tambien: desde el portatil se puede ver
        # en que estado esta el puente sin poder ver la placa. Y los
        # parpadeos: cuantos comandos han llegado al puente.
        estado["led"] = led.nombre(self.color_led())
        estado["led_parpadeos"] = self.led.parpadeos
        return 200, estado

    async def r_escanear(self, peticion):
        """Lo que se ve por BLE ahora mismo.

        Acepta `?ms=` para decir cuanto escanea (por defecto, `ESCANEO_MS`).
        """
        ms = ESCANEO_MS
        if "?" in peticion.ruta:
            for parte in peticion.ruta.split("?", 1)[1].split("&"):
                clave, _, valor = parte.partition("=")
                if clave == "ms":
                    try:
                        ms = int(valor)
                    except ValueError:
                        pass
        self.buscando = True
        self.actualizar_led()
        try:
            vistos = await self.cliente.escanear(max(100, min(ms, 30000)))
        finally:
            self.buscando = False
            self.actualizar_led()
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
        # Hay trafico de comandos (se han leido del HTTP y se mandan al
        # robot): el LED parpadea del color que tenga.
        self.parpadear()
        ok = await self.cliente.escribir(datos)
        if not ok:
            return 409, {"error": self.cliente.error or "no se pudo escribir"}
        return 200, {"ok": True, "bytes": len(datos)}

    async def r_conectar(self, peticion):
        """Busca al robot y se conecta (a peticion).

        OJO: esto escanea, conecta y descubre. Con `AUTO_CONECTAR` a False
        la placa **no** agarra al robot por su cuenta: se conecta cuando
        alguien lo pide (el boton "Conectar" de la web, o el propio cliente
        cuando se reconecta).

        Todo el proceso va con un candado, para que dos peticiones de
        "conectar" no se peleen por el robot.
        """
        async with self.lock_conexion:
            if self.cliente.conn >= 0:
                self.actualizar_led()
                return 200, {
                    "ok": True,
                    "mac": self.cliente.mac_robot,
                    "ya_conectado": True,
                }
            # Mientras se busca, el LED esta en azul.
            self.buscando = True
            self.actualizar_led()
            try:
                addr, addr_type = await self.cliente.buscar_robot(
                    ESPERA_BUSQUEDA_MS, 5000, sondear=False
                )
                if addr is None or addr_type is None:
                    return 409, {"ok": False, "error": "no se encuentra el robot"}
                if not await self.cliente.conectar(addr, addr_type, 25000, 20000):
                    return 409, {"ok": False, "error": self.cliente.error}
                if not await self.cliente.descubrir(15000):
                    self.cliente.desconectar()
                    return 409, {"ok": False, "error": self.cliente.error}
                return 200, {"ok": True, "mac": self.cliente.mac_robot}
            finally:
                self.buscando = False
                self.actualizar_led()

    async def r_desconectar(self, peticion):
        """Cierra la conexion con el robot."""
        self.cliente.desconectar()
        self.actualizar_led()
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
        """Se conecta al robot en cuanto aparece y se reconecta si se cae.

        Solo se usa con `AUTO_CONECTAR` a True: si esta a False, el robot se
        conecta solo cuando alguien lo pide.
        """
        while True:
            if self.cliente.conn < 0:
                self.buscando = True
                self.actualizar_led()
                addr, addr_type = await self.cliente.buscar_robot(
                    15000, 5000, sondear=False
                )
                self.buscando = False
                self.actualizar_led()
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
            # El LED va con el estado: si el robot se duerme y se cae el
            # enlace, el LED pasa a rojo solo (sin esperar a una peticion).
            self.actualizar_led()
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
