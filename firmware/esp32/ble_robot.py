"""Cliente BLE del robot AIRO para MicroPython (ESP32-S3).

Es la parte que habla con el robot: escanear, conectar, descubrir `FFF0`/`FFF1`
y escribir bytes en la characteristic `FFF1`.

Este modulo **no sabe nada del protocolo AIRO**: solo escribe los bytes que le
manden. El paquete de 20 bytes lo construye `airo_ble/protocol.py` en el
portatil (ver `docs/plan-esp32.md`).

Las rarezas de la API de `bluetooth` en MicroPython estan todas anotadas aqui
y en el README del firmware, porque ninguna sale en la documentacion:

- Las constantes `_IRQ_*` no existen: los eventos van numerados.
- `gap_connect` avisa de la conexion con el IRQ 7, no con el 1.
- `gap_scan(None)` para el escaneo; `gap_scan(0)` lo deja para siempre.
- El robot registra el servicio con su UUID de 128 bits: hay que descubrir
  todo y filtrar despues.
- `bluetooth.UUID16` no existe: es `bluetooth.UUID(0xFFF0)`.
"""

import asyncio

import bluetooth

#: El robot se anuncia con este nombre (con la "o" en minuscula).
NOMBRE_ROBOT = "AIRo"

#: Servicio y characteristic del robot, en su forma corta de 16 bits.
UUID_SERVICIO = 0xFFF0
UUID_CHARACTERISTIC = 0xFFF1

#: Espera maxima de cada paso, en milisegundos.
TIMEOUT_MS = 10000

#: Cada cuanto se mira si ya ha pasado algo (milisegundos).
PASO_MS = 50

# --- Codigos de evento del IRQ ------------------------------------------------
#
# MicroPython **no expone** las constantes `_IRQ_*` en el modulo `bluetooth`
# (ni en 1.26 ni en 1.29): hay que usar los numeros. Estos son los de
# `extmod/modbluetooth.h`:
#
#     1 CENTRAL_CONNECT        2 CENTRAL_DISCONNECT
#     5 SCAN_RESULT            6 SCAN_DONE
#     7 PERIPHERAL_CONNECT     8 PERIPHERAL_DISCONNECT
#     9 GATTC_SERVICE_RESULT  10 GATTC_SERVICE_DONE
#    11 GATTC_CHARACTERISTIC_RESULT  12 GATTC_CHARACTERISTIC_DONE
#    17 GATTC_WRITE_DONE
#
# Ojo con 7 y 8: en el port NimBLE, `gap_connect` (que actua como central)
# entrega sus eventos por el callback "peripheral", asi que una conexion
# HECHA se avisa con el 7 y un fallo con el 8. Se escuchan los dos por si
# acaso.
#
# Y los DATOS de cada evento:
#
#     SCAN_RESULT            (addr_type, addr, adv_type, rssi, adv_data)
#     GATTC_SERVICE_RESULT   (conn_handle, inicio, fin, uuid)
#     GATTC_CHARACTERISTIC   (conn_handle, fin, handle, props, uuid)
#     GATTC_WRITE_DONE       (conn_handle, value_handle, status)
#
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6
IRQ_PERIPHERAL_CONNECT = 7
IRQ_PERIPHERAL_DISCONNECT = 8
IRQ_GATTC_SERVICE_RESULT = 9
IRQ_GATTC_CHARACTERISTIC_RESULT = 11
IRQ_GATTC_WRITE_DONE = 17


def nombre_de_adv(adv_data):
    """Saca el nombre del dispositivo de los datos de advertising.

    Los datos son una secuencia de estructuras AD: [longitud][tipo][datos].
    La longitud cuenta el byte del tipo, asi que la estructura ocupa
    `1 + longitud` bytes y los datos van de `i+2` a `i+1+longitud`. Los tipos
    0x08 (nombre corto) y 0x09 (nombre completo) son los que nos interesan.
    """
    i = 0
    total = len(adv_data)
    while i + 1 < total:
        longitud = adv_data[i]
        tipo = adv_data[i + 1]
        if tipo in (0x08, 0x09):
            # El nombre suele venir con un \0 al final (nombre en C): se quita,
            # que si no el robot no se encuentra nunca.
            nombre = adv_data[i + 2 : i + 1 + longitud].decode("utf-8", "ignore")
            return nombre.strip("\x00")
        i += 1 + longitud
    return ""


def es_uuid(uuid, corto):
    """True si `uuid` es el UUID de 16 bits `corto` (en cualquiera de sus formas).

    MicroPython imprime los UUID como `UUID(0xfff0)` (16 bits) o como
    `UUID('0000fff0-0000-1000-8000-00805f9b34fb')` (128 bits). El base UUID
    del robot puede ser uno u otro (ver `docs/protocolo.md`), asi que se
    compara la parte corta, que es la misma en los dos casos.

    Se usa el buffer del UUID (no su forma escrita) porque en la version de
    128 bits el grupo de 16 bits va en las posiciones 12 y 13 (little endian).
    """
    datos = bytes(uuid)
    if len(datos) == 2:
        return (datos[0] | (datos[1] << 8)) == corto
    if len(datos) >= 14:
        return (datos[12] | (datos[13] << 8)) == corto
    return False


def mac(addr):
    """Un byte sucio (6 bytes) a 'AA:BB:CC:DD:EE:FF'."""
    return ":".join(f"{b:02X}" for b in addr)


async def esperar_hasta(condicion, timeout_ms):
    """Espera a que `condicion()` sea verdad. True si se cumplio a tiempo."""
    pasos = max(1, timeout_ms // PASO_MS)
    for _ in range(pasos):
        if condicion():
            return True
        await asyncio.sleep(PASO_MS / 1000)
    return bool(condicion())


class ClienteAiro:
    """Lo justo para hablar con el robot: escanear, conectar y escribir."""

    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        self.conn = -1
        self.servicio = (0, 0)
        self.caracteristica = 0
        self.escrito = -1
        self.servicios = []
        self.caracteristicas = []
        self.vistos = {}
        self.error = ""
        self.paquetes = 0
        self.mac_robot = ""
        self.nombre_robot = ""
        self.rssi = 0
        #: El ultimo paquete escrito. El puente lo reenvia solo: el robot
        #: quiere paquetes seguidos y no tiene sentido ir por HTTP 20 veces
        #: por segundo.
        self.ultimo = b""
        #: Cuantas veces seguidas ha fallado el reenvio.
        self.fallos = 0
        #: El BLE no admite dos escaneos a la vez (contesta `EALREADY`), y
        #: el puente escanea en segundo plano mientras tambien atiende por
        #: HTTP. Este candado serializa esas operaciones.
        self.lock = asyncio.Lock()

    # -- IRQ ---------------------------------------------------------------
    #
    # El manejador se ejecuta en la tarea del BLE: aqui no se duerme ni se
    # imprime nada, solo se guarda el estado. Lo que espera, espera fuera.

    def _irq(self, event, data):
        if event == IRQ_SCAN_RESULT:
            addr_type, addr, _adv_type, rssi, adv_data = data
            # `addr` y `adv_data` llegan como memoryview: se copian a bytes
            # (el memoryview no tiene `.decode` y la clave del diccionario
            # tiene que sobrevivir al reusable buffer).
            self.vistos[bytes(addr)] = (addr_type, nombre_de_adv(bytes(adv_data)), rssi)
        elif event == IRQ_CENTRAL_CONNECT or event == IRQ_PERIPHERAL_CONNECT:
            self.conn = data[0]
        elif event == IRQ_CENTRAL_DISCONNECT or event == IRQ_PERIPHERAL_DISCONNECT:
            self.conn = -1
            self.servicio = (0, 0)
            self.caracteristica = 0
        elif event == IRQ_GATTC_SERVICE_RESULT:
            # (conn_handle, inicio, fin, uuid)
            _conn, inicio, fin, uuid = data
            self.servicios.append((uuid, inicio, fin))
            if es_uuid(uuid, UUID_SERVICIO):
                self.servicio = (inicio, fin)
        elif event == IRQ_GATTC_CHARACTERISTIC_RESULT:
            # (conn_handle, fin, handle, props, uuid)
            _conn, _fin, handle, _props, uuid = data
            self.caracteristicas.append((uuid, handle))
            if es_uuid(uuid, UUID_CHARACTERISTIC):
                self.caracteristica = handle
        elif event == IRQ_GATTC_WRITE_DONE:
            # (conn_handle, value_handle, status)
            self.escrito = data[2]

    # -- Pasos -------------------------------------------------------------

    async def escanear(self, ms=5000):
        """Escanea `ms` milisegundos y devuelve lo que se ha visto.

        Devuelve un diccionario: direccion -> (tipo, nombre, rssi).

        El candado es importante: el BLE no admite dos escaneos a la vez
        (contesta `EALREADY`) y el puente escanea en segundo plano mientras
        tambien atiende peticiones por HTTP.
        """
        async with self.lock:
            self.vistos = {}
            try:
                self.ble.gap_scan(ms, 1280000, 11250, True)
            except OSError as exc:
                self.error = f"no se pudo escanear ({exc})"
                return self.vistos
            await asyncio.sleep((ms + 500) / 1000)
            # El escaneo se para antes de conectar: NimBLE no deja conectar
            # con un descubrimiento en marcha y devuelve `EALREADY`.
            self.ble.gap_scan(None)
            await asyncio.sleep(0.3)
            return self.vistos

    async def buscar_robot(self, timeout_ms=30000, paso_ms=5000, sondear=True):
        """Busca al robot y devuelve (direccion, tipo) o (None, None).

        Primero por su nombre (`AIRo`). Si no aparece y `sondear` esta a
        True, se prueban los candidatos uno a uno: se conecta con ellos y se
        mira si tienen el servicio `FFF0`.
        """
        gastado = 0
        self.vistos = {}
        while gastado < timeout_ms:
            vistos = await self.escanear(paso_ms)
            for addr, (addr_type, nombre, rssi) in vistos.items():
                if nombre == NOMBRE_ROBOT:
                    self.nombre_robot = nombre
                    self.rssi = rssi
                    return addr, addr_type
            gastado += paso_ms + 800
        if not sondear:
            return None, None
        for addr, (addr_type, _nombre, _rssi) in list(self.vistos.items()):
            if await self.sonda_servicio(addr, addr_type):
                return addr, addr_type
        return None, None

    async def sonda_servicio(self, addr, addr_type, timeout_ms=4000):
        """Conecta con un candidato y mira si tiene el servicio FFF0."""
        if not await self.conectar(addr, addr_type, timeout_ms):
            return False
        self.servicios = []
        self.servicio = (0, 0)
        self.ble.gattc_discover_services(self.conn)
        encontrado = await esperar_hasta(lambda: self.servicio != (0, 0), timeout_ms)
        self.desconectar()
        await asyncio.sleep(0.3)
        return encontrado

    async def conectar(self, addr, addr_type=0, timeout_ms=TIMEOUT_MS, scan_ms=2000):
        """Conecta con el robot. Devuelve True si lo consigue.

        `scan_ms` es la ventana del escaneo con lista blanca que hace NimBLE
        antes de mandar la peticion de conexion. El HM-10 solo anuncia a
        ratos, asi que conviene darle margen (15-20 s).

        Si ya habia una conexion con ese robot, NimBLE contesta `EIO`
        ("already connected"): se cierra antes de intentar nada.

        El candado serializa esta operacion con los escaneos: si hay un
        descubrimiento en marcha, NimBLE contesta `EALREADY`.
        """
        async with self.lock:
            if self.conn >= 0:
                self.desconectar()
                await asyncio.sleep(0.3)
            self.conn = -1
            try:
                self.ble.gap_connect(addr_type, addr, scan_ms)
            except OSError as exc:
                self.error = f"no se pudo conectar ({exc})"
                return False
            if await esperar_hasta(lambda: self.conn >= 0, timeout_ms):
                self.mac_robot = mac(addr)
                self.error = ""
                return True
            self.error = "no se pudo conectar"
            return False

    async def descubrir(self, timeout_ms=TIMEOUT_MS):
        """Descubre el servicio FFF0 y la characteristic FFF1.

        Se descubren **todos** los servicios y characteristics, sin filtrar:
        el robot registra el servicio con su UUID de 128 bits (el base puede
        ser `...-00805f9b34fb` o `...-000000000000`), no con la forma corta
        de 16 bits, asi que pedir solo `UUID(0xFFF0)` no devuelve nada.
        Luego se filtra aqui con `es_uuid()`.
        """
        conn = self.conn
        if conn < 0:
            self.error = "no hay conexion"
            return False

        self.servicios = []
        self.caracteristicas = []
        self.servicio = (0, 0)
        self.caracteristica = 0
        self.ble.gattc_discover_services(conn)
        if not await esperar_hasta(lambda: self.servicio != (0, 0), timeout_ms):
            self.error = f"no se encontro el servicio FFF0 (hay: {self.lista_servicios()})"
            return False

        inicio, fin = self.servicio
        self.ble.gattc_discover_characteristics(conn, inicio, fin)
        if not await esperar_hasta(lambda: self.caracteristica != 0, timeout_ms):
            self.error = (
                f"no se encontro la characteristic FFF1 (hay: {self.lista_chars()})"
            )
            return False
        return True

    async def escribir(self, datos, con_respuesta=True, timeout_ms=TIMEOUT_MS):
        """Escribe los bytes en FFF1. Devuelve True si el robot lo confirma."""
        conn = self.conn
        handle = self.caracteristica
        if conn < 0 or handle == 0:
            self.error = "no hay conexion"
            return False
        self.escrito = -1
        modo = 1 if con_respuesta else 0
        self.ble.gattc_write(conn, handle, datos, modo)
        if not await esperar_hasta(lambda: self.escrito >= 0, timeout_ms):
            self.error = "la escritura no tuvo respuesta"
            return False
        if self.escrito != 0:
            self.error = f"el robot contesto con error {self.escrito}"
            return False
        self.paquetes += 1
        self.ultimo = bytes(datos)
        self.fallos = 0
        return True

    async def refrescar(self, timeout_ms=500):
        """Reenvia el ultimo paquete (el que el robot tiene guardado).

        El firmware del robot devuelve los brazos al reposo si deja de
        recibir paquetes, asi que el paquete se reenvia sin parar. Esto lo
        hace el ESP32 y no el portatil: mandar 20 peticiones HTTP por
        segundo seria mucho trafico para tan poca informacion.

        Devuelve True si se ha reenviado bien.
        """
        conn = self.conn
        handle = self.caracteristica
        if conn < 0 or handle == 0 or not self.ultimo:
            return False
        self.escrito = -1
        try:
            self.ble.gattc_write(conn, handle, self.ultimo, 1)
        except Exception as exc:  # pragma: no cover - depende del hardware
            self.fallos += 1
            self.error = f"no se pudo reenviar ({exc})"
            return False
        if not await esperar_hasta(lambda: self.escrito >= 0, timeout_ms):
            self.fallos += 1
            self.error = "el reenvio no tuvo respuesta"
            return False
        if self.escrito != 0:
            self.fallos += 1
            self.error = f"el robot contesto con error {self.escrito}"
            return False
        self.fallos = 0
        return True

    def desconectar(self):
        """Cierra la conexion BLE."""
        if self.conn >= 0:
            self.ble.gap_disconnect(self.conn)
            self.conn = -1

    # -- Informacion -------------------------------------------------------

    def lista_servicios(self):
        """Los servicios encontrados, para depurar."""
        return ", ".join(str(uuid) for (uuid, _i, _f) in self.servicios) or "ninguno"

    def lista_chars(self):
        """Las characteristics encontradas, para depurar."""
        return ", ".join(str(uuid) for (uuid, _h) in self.caracteristicas) or "ninguna"

    def estado(self):
        """El estado del puente, en JSON."""
        return {
            "conectado": self.conn >= 0,
            "mac": self.mac_robot,
            "nombre": self.nombre_robot or NOMBRE_ROBOT,
            "rssi": self.rssi,
            "paquetes": self.paquetes,
            "ultimo_error": self.error or None,
            "servicio": list(self.servicio),
            "characteristic": self.caracteristica,
            # Cuantos bytes tiene guardados el ultimo paquete y cuantos
            # reenvios seguidos han fallado (el puente deja de reenviar si
            # el robot no contesta).
            "bytes_guardados": len(self.ultimo),
            "fallos": self.fallos,
        }
