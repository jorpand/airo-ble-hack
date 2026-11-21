"""Muestra en el terminal lo que dice la placa ESP32-S3 por el puerto serie.

Sirve para ver el arranque del puente (si se conecta a la WiFi, si encuentra
al robot, que dice el servidor HTTP) y para seguirlo mientras trabaja.

    python tools/firmware/logs.py --port /dev/ttyACM0

Ojo: al abrir el puerto serie la placa se reinicia (el USB nativo reinicia con
el DTR), asi que esto **empieza** con el log de arranque. Eso es lo que
interesa: el log del arranque es el que dice si la WiFi y el BLE van bien.
"""

from __future__ import annotations

import argparse
import sys
import time

import serial


def _reiniciar(serie: serial.Serial) -> None:
    """Reinicia la placa con la secuencia DTR/RTS (la de esptool).

    Con el USB nativo, abrir el puerto NO reinicia la placa, asi que sin esto
    no se ve el log de arranque (que es el interesante: si entra la WiFi, si
    encuentra al robot...).
    """
    serie.setDTR(False)  # IO0 en alto: modo normal, no de arranque
    serie.setRTS(True)  # EN en bajo: la placa se reinicia
    time.sleep(0.1)
    serie.setRTS(False)  # EN en alto: la placa arranca
    time.sleep(0.2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Log de la placa por el puerto serie")
    parser.add_argument("--port", default=None, help="el puerto (por defecto, el primero)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--segundos", type=float, default=0.0, help="0 = hasta Ctrl+C")
    parser.add_argument(
        "--reset", action="store_true", help="reinicia la placa antes de escuchar"
    )
    args = parser.parse_args()

    puerto = args.port
    if not puerto:
        import glob

        lista = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        if not lista:
            print("No se encuentra la placa (¿esta enchufada?)", file=sys.stderr)
            return 1
        puerto = lista[0]

    print(f"Escuchando {puerto} a {args.baud} baudios (Ctrl+C para salir)...", flush=True)
    try:
        with serial.Serial(puerto, args.baud, timeout=1) as serie:
            if args.reset:
                print("(reiniciando la placa)", flush=True)
                _reiniciar(serie)
            limite = time.monotonic() + args.segundos if args.segundos else None
            while limite is None or time.monotonic() < limite:
                linea = serie.readline()
                if linea:
                    sys.stdout.write(linea.decode("utf-8", "replace"))
                    sys.stdout.flush()
    except KeyboardInterrupt:
        print("", flush=True)
    except serial.SerialException as exc:
        print(f"No se pudo abrir {puerto}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
