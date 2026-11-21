"""Arranque del puente BLE del ESP32-S3.

Este es el programa que vive en la placa. Hace cuatro cosas:

1. Se conecta a la WiFi (las credenciales estan en `/wifi.json`, en la placa).
2. Levanta un servidor HTTP minimo (las rutas estan en `puente.py`).
3. Mantiene la conexion BLE con el robot: se conecta en cuanto aparece y se
   vuelve a conectar si se cae (el modulo HM-10 se duerme).
4. Reenvia el ultimo paquete cada 50 ms, para que el robot no se duerma.

Como se arranca:

    mpremote connect /dev/ttyUSB0 run main.py
"""

import asyncio

import puente
import wifi


async def main():
    """Arranca el puente."""
    ip = wifi.conectar()
    if ip:
        wifi.publicar_nombre(puente.HOSTNAME)
    loop = asyncio.get_event_loop()
    b = puente.Puente()
    loop.create_task(b.mantener_conexion())
    loop.create_task(b.refrescar())
    await puente.http_srv.servir("0.0.0.0", puente.PUERTO, b.rutas())


#: El punto de entrada: en MicroPython se usa el event loop a mano.
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
