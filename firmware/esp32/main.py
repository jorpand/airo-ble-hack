"""Spike del puente BLE: el ESP32-S3 habla con el robot AIRO.

Esto es la Fase 0 del plan (`docs/plan-esp32.md`): comprobar, con la placa
delante, que un ESP32-S3 con MicroPython puede

  1. ver al robot en el escaneo (se anuncia como `AIRo`),
  2. conectarse y descubrir el servicio `FFF0` y la characteristic `FFF1`,
  3. escribir el paquete de 20 bytes y que el robot se mueva.

De momento el ESP32 **no sabe nada del protocolo**: solo escribe bytes. Los
paquetes de prueba van a pelo en este archivo, calculados con
`airo_ble/protocol.py` (ver el comentario de cada uno).

API de MicroPython: la de bajo nivel (`BLE.gattc_*`), la de MicroPython 1.24
en adelante. Documentacion:
https://docs.micropython.org/en/latest/library/bluetooth.html

Como ejecutar:

    mpremote connect /dev/ttyUSB0 run main.py

o, si lo copiaste antes al chip:

    mpremote connect /dev/ttyUSB0 exec main.py
"""

import time

import bluetooth

#: El robot se anuncia con este nombre (con la "o" en minuscula).
NOMBRE_ROBOT = "AIRo"

#: Servicio y characteristic del robot, en su forma corta de 16 bits. Se
#: busca por la forma corta a proposito: el base UUID del robot puede cambiar
#: entre `0000fff0-...-00805f9b34fb` y `0000fff0-...-000000000000` segun como
#: se haya reiniciado el modulo (ver `docs/protocolo.md`).
UUID_SERVICIO = 0xFFF0
UUID_CHARACTERISTIC = 0xFFF1

#: Espera maxima de cada paso, en milisegundos.
TIMEOUT_MS = 10000

#: Cada cuanto se mira si ya ha pasado algo (milisegundos).
PASO_MS = 50

# --- Paquetes de prueba -------------------------------------------------------
#
# Calculados con `airo_ble/protocol.py` (la fuente de la verdad). No se
# calculan aqui porque este firmware, en su papel de puente, no deberia
# conocer el protocolo: solo mandar bytes.
#
# Parar (ruedas quietas, brazos en el centro):
PAQUETE_PARAR = bytes(
    [
        0xA5,  # [0] magic
        0x00,  # [1] led off
        0x00,  # [2] rueda izquierda: direccion stop
        0x00,  # [3] rueda izquierda: velocidad 0
        0x00,  # [4] rueda derecha: direccion stop
        0x00,  # [5] rueda derecha: velocidad 0
        0x14,  # [6] hombro derecho: centro
        0x14,  # [7] brazo derecho: centro
        0x14,  # [8] brazo izquierdo: centro
        0x14,  # [9] hombro izquierdo: centro
        0x05,  # [10..19] cola fija del firmware
        0x16,
        0x27,
        0x38,
        0x49,
        0x5A,
        0x6B,
        0x7C,
        0x8D,
        0x9E,
    ]
)

#: Avanzar despacio (velocidad 0,6 -> magnitud 1, la mas baja que hay).
#:
#: Ojo con las ruedas: los bytes [2]-[3] son la rueda **izquierda** del robot
#: y van sin invertir, mientras que [4]-[5] son la **derecha** y van invertidos
#: (la rueda derecha esta montada al reves en el chasis). Asi que avanzar son
#: los dos: [2]=1 [3]=1 (izquierda) y [4]=2 [5]=1 (derecha, invertida).
PAQUETE_ADELANTE = bytes(
    [
        0xA5,  # [0] magic
        0x00,  # [1] led off
        0x01,  # [2] rueda izquierda: adelante
        0x01,  # [3] rueda izquierda: velocidad 1
        0x02,  # [4] rueda derecha: atras (invertido = adelante)
        0x01,  # [5] rueda derecha: velocidad 1
        0x14,  # [6] hombro derecho: centro
        0x14,  # [7] brazo derecho: centro
        0x14,  # [8] brazo izquierdo: centro
        0x14,  # [9] hombro izquierdo: centro
        0x05,  # [10..19] cola fija del firmware
        0x16,
        0x27,
        0x38,
        0x49,
        0x5A,
        0x6B,
        0x7C,
        0x8D,
        0x9E,
    ]
)


def nombre_de_adv(adv_data):
    """Saca el nombre del dispositivo de los datos de advertising.

    Los datos son una secuencia de estructuras AD: [longitud][tipo][datos].
    La longitud cuenta el byte del tipo, asi que la estructura ocupa
    `1 + longitud` bytes en total y los datos van de `i+2` a `i+1+longitud`.
    Los tipos 0x08 (nombre corto) y 0x09 (nombre completo) son los que nos
    interesan.
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

    El stack puede devolver el UUID de 16 bits o el de 128 bits (con el base
    del robot, que es el que cambia). Comparamos solo la parte corta, que es
    la misma en los dos casos.
    """
    texto = str(uuid).lower().replace("-", "")
    corto_hex = f"{corto:04x}"
    return texto.startswith("0000" + corto_hex) or texto.startswith(corto_hex)


def _mac(addr):
    """Un byte sucio (6 bytes) a 'AA:BB:CC:DD:EE:FF'."""
    return ":".join(f"{b:02X}" for b in addr)


def _esperar(ms):
    """Espera `ms` milisegundos."""
    time.sleep(ms / 1000)


def _esperar_hasta(condicion, timeout_ms):
    """Espera a que `condicion()` sea verdad. True si se cumplio a tiempo."""
    pasos = max(1, timeout_ms // PASO_MS)
    for _ in range(pasos):
        if condicion():
            return True
        time.sleep(PASO_MS / 1000)
    return bool(condicion())


class ClienteAiro:
    """Lo justo para hablar con el robot: escanear, conectar y escribir."""

    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        # Sin `None`: en MicroPython `int | None` no existe, y con centinelas
        # el chequeo queda mas claro. -1 = no hay conexion ni respuesta,
        # 0 = no hay handle, (0, 0) = no hay servicio.
        self.conn = -1
        self.servicio = (0, 0)
        self.caracteristica = 0
        self.escrito = -1
        self.vistos: dict = {}
        self.error = ""

    # -- IRQ ---------------------------------------------------------------
    #
    # El manejador se ejecuta en la tarea del BLE: aqui no se duerme ni se
    # imprime nada, solo se guarda el estado. Lo que espera, espera fuera.

    def _irq(self, event, data):
        if event == bluetooth._IRQ_SCAN_RESULT:
            addr_type, addr, _adv_type, rssi, adv_data = data
            self.vistos[addr] = (addr_type, nombre_de_adv(adv_data), rssi)
        elif event == bluetooth._IRQ_CENTRAL_CONNECT:
            self.conn = data[0]
        elif event == bluetooth._IRQ_CENTRAL_DISCONNECT:
            self.conn = -1
            self.servicio = (0, 0)
            self.caracteristica = 0
        elif event == bluetooth._IRQ_GATTC_SERVICE_RESULT:
            uuid, inicio, fin = data
            if es_uuid(uuid, UUID_SERVICIO):
                self.servicio = (inicio, fin)
        elif event == bluetooth._IRQ_GATTC_CHARACTERISTIC_RESULT:
            uuid, handle, _props = data
            if es_uuid(uuid, UUID_CHARACTERISTIC):
                self.caracteristica = handle
        elif event == bluetooth._IRQ_GATTC_WRITE_DONE:
            self.escrito = data[1]

    # -- Pasos -------------------------------------------------------------

    def escanear(self, ms=5000):
        """Escanea `ms` milisegundos y devuelve lo que se ha visto.

        Devuelve un diccionario: direccion -> (tipo, nombre, rssi).

        Ojo: `gap_scan` acepta sus argumentos **por posicion**
        (duracion, intervalo, ventana, activo). El escaneo activo es el que
        trae el nombre del dispositivo en la respuesta del scan.
        """
        self.vistos = {}
        self.ble.gap_scan(ms, 1280000, 11250, True)
        _esperar(ms + 500)
        return self.vistos

    def buscar_robot(self, ms=5000):
        """Escanea hasta encontrar al robot por su nombre."""
        vistos = self.escanear(ms)
        for addr, (addr_type, nombre, rssi) in vistos.items():
            if nombre == NOMBRE_ROBOT:
                return addr, addr_type, rssi
        return None, None, None

    def conectar(self, addr, addr_type=0, timeout_ms=TIMEOUT_MS):
        """Conecta con el robot. Devuelve True si lo consigue."""
        self.conn = -1
        self.ble.gap_connect(addr_type, addr, 0)
        if _esperar_hasta(lambda: self.conn >= 0, timeout_ms):
            return True
        self.error = "no se pudo conectar"
        return False

    def descubrir(self, timeout_ms=TIMEOUT_MS):
        """Descubre el servicio FFF0 y la characteristic FFF1."""
        conn = self.conn
        if conn < 0:
            self.error = "no hay conexion"
            return False

        self.servicio = (0, 0)
        self.caracteristica = 0
        self.ble.gattc_discover_services(conn, bluetooth.UUID16(UUID_SERVICIO))
        if not _esperar_hasta(lambda: self.servicio != (0, 0), timeout_ms):
            self.error = "no se encontro el servicio FFF0"
            return False

        inicio, fin = self.servicio
        self.ble.gattc_discover_characteristics(
            conn, inicio, fin, bluetooth.UUID16(UUID_CHARACTERISTIC)
        )
        if not _esperar_hasta(lambda: self.caracteristica != 0, timeout_ms):
            self.error = "no se encontro la characteristic FFF1"
            return False
        return True

    def escribir(self, datos, con_respuesta=True):
        """Escribe los bytes en FFF1. Devuelve True si el robot lo confirma."""
        conn = self.conn
        handle = self.caracteristica
        if conn < 0 or handle == 0:
            self.error = "no hay conexion"
            return False
        self.escrito = -1
        modo = 1 if con_respuesta else 0
        self.ble.gattc_write(conn, handle, datos, modo)
        if not _esperar_hasta(lambda: self.escrito >= 0, TIMEOUT_MS):
            self.error = "la escritura no tuvo respuesta"
            return False
        if self.escrito != 0:
            self.error = f"el robot contesto con error {self.escrito}"
            return False
        return True

    def desconectar(self):
        """Cierra la conexion BLE."""
        if self.conn >= 0:
            self.ble.gap_disconnect(self.conn)


def main():
    """Ejecuta el spike entero. Devuelve 0 si todo va bien."""
    print("=== SPIKE: ESP32-S3 -> robot AIRO ===")
    cliente = ClienteAiro()

    print("1. Escaneando 5 s...")
    vistos = cliente.escanear(5000)
    if not vistos:
        print("   no se ha visto nada por BLE")
        print("   ¿esta el robot encendido? ¿el BT del chip enganchado?")
        return 1
    for addr, (_addr_type, nombre, rssi) in vistos.items():
        print(f"   {_mac(addr)}  {nombre or '?'}  rssi={rssi}")

    addr, addr_type, _rssi = cliente.buscar_robot(5000)
    if addr is None or addr_type is None:
        print(f"   no aparece ningun dispositivo llamado {NOMBRE_ROBOT}")
        return 1
    print(f"2. Conectando con {_mac(addr)} ({NOMBRE_ROBOT})...")
    if not cliente.conectar(addr, addr_type):
        print(f"   fallo: {cliente.error}")
        return 1
    print(f"   conectado (handle {cliente.conn})")

    print("3. Descubriendo FFF0/FFF1...")
    if not cliente.descubrir():
        print(f"   fallo: {cliente.error}")
        return 1
    print(f"   servicio {cliente.servicio}, characteristic handle {cliente.caracteristica}")

    print("4. Escribiendo el paquete de parar...")
    if not cliente.escribir(PAQUETE_PARAR):
        print(f"   fallo: {cliente.error}")
        return 1
    print("   ok (write con respuesta)")

    print("5. Escribiendo el paquete de avanzar (1 s)...")
    if cliente.escribir(PAQUETE_ADELANTE):
        print("   ok: el robot deberia estar avanzando")
    else:
        print(f"   fallo: {cliente.error}")
    _esperar(1000)
    cliente.escribir(PAQUETE_PARAR)
    print("   parado")

    print("=== SPIKE OK ===")
    print("La placa se queda conectada; Ctrl+C para salir.")
    while True:
        _esperar(1000)
        if cliente.conn < 0:
            print("se ha desconectado el robot")


if __name__ == "__main__":
    main()
