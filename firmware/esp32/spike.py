"""Spike de la Fase 0: el ESP32-S3 habla con el robot, a pelo.

Esto es lo primero que se hizo con la placa: comprobar que un ESP32-S3 con
MicroPython puede ver al robot, conectarse, descubrir `FFF0`/`FFF1` y escribir
el paquete de 20 bytes. Sin la API de por medio, sin el portatil.

    mpremote connect /dev/ttyUSB0 run spike.py

Los dos paquetes de prueba estan calculados con `airo_ble/protocol.py` (la
fuente de la verdad) y se han copiado aqui tal cual, porque aqui el firmware
si tiene que saber de que va el paquete (a diferencia del puente, que solo
manda bytes).
"""

import asyncio

import ble_robot

# --- Paquetes de prueba -------------------------------------------------------
#
# Calculados con `airo_ble/protocol.py`:
#
#     Command().to_bytes()                  -> el de parar
#     Command(right_speed=0.6, left_speed=0.6).to_bytes()  -> el de avanzar
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


async def main():
    """Ejecuta el spike entero."""
    print("=== SPIKE: ESP32-S3 -> robot AIRO ===")
    cliente = ble_robot.ClienteAiro()

    print("1. Buscando al robot (hasta 30 s)...")
    addr, addr_type = await cliente.buscar_robot(30000)
    if addr is None or addr_type is None:
        print(f"   no aparece ningun dispositivo llamado {ble_robot.NOMBRE_ROBOT}")
        print("   (ni uno con el servicio FFF0)")
        print("   esta el robot encendido y cerca?")
        return 1
    print(f"2. Conectando con {ble_robot.mac(addr)} ({ble_robot.NOMBRE_ROBOT})...")
    if not await cliente.conectar(addr, addr_type, 25000, 20000):
        print(f"   fallo: {cliente.error}")
        return 1
    print(f"   conectado (handle {cliente.conn})")

    print("3. Descubriendo FFF0/FFF1...")
    if not await cliente.descubrir(15000):
        print(f"   fallo: {cliente.error}")
        return 1
    print(f"   servicio {cliente.servicio}, characteristic handle {cliente.caracteristica}")

    print("4. Escribiendo el paquete de parar...")
    if not await cliente.escribir(PAQUETE_PARAR):
        print(f"   fallo: {cliente.error}")
        return 1
    print("   ok (write con respuesta)")

    print("5. Escribiendo el paquete de avanzar (1 s)...")
    if await cliente.escribir(PAQUETE_ADELANTE):
        print("   ok: el robot deberia estar avanzando")
    else:
        print(f"   fallo: {cliente.error}")
    await asyncio.sleep(1)
    await cliente.escribir(PAQUETE_PARAR)
    print("   parado")

    print("=== SPIKE OK ===")
    print("La placa se queda conectada; Ctrl+C para salir.")
    while True:
        await asyncio.sleep(1)
        if cliente.conn < 0:
            print("se ha desconectado el robot")
            return 1


#: El punto de entrada: en MicroPython se usa el event loop a mano.
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
