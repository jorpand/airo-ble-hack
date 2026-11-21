"""
Comprueba que la duracion que dice la API es la duracion real.

Se lanza un programa que **no mueve el robot** (luz + espera) y se mide con
el reloj cuanto tarda de verdad (el estado pasa de "esperando" a "parado").
Se compara con lo que dice `POST /api/duracion`.

Ejecutar:
    .venv-3.14/bin/python tools/hardware/medir_duracion.py
"""

from __future__ import annotations

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8100"


def pedir(ruta: str, datos: dict | None = None) -> dict:
    cuerpo = None if datos is None else json.dumps(datos).encode()
    peticion = urllib.request.Request(
        BASE + ruta,
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST" if cuerpo else "GET",
    )
    with urllib.request.urlopen(peticion, timeout=10) as r:
        return json.loads(r.read().decode())


def main() -> None:
    programa = {
        "nombre": "Medir",
        "bloques": [
            {"tipo": "luz", "modo": "parpadea"},
            {"tipo": "espera", "segundos": 3},
        ],
    }

    estado = pedir("/api/estado")
    if not estado.get("conectado"):
        print("El robot no esta conectado: no se puede medir.")
        return

    estimations = pedir("/api/duracion", {"programa": programa})
    print(f"Lo que dice la API:  {estimations['duracion']:.2f} s "
          f"(por bloque: {estimations['bloques']})")

    # Se espera a que el robot este parado antes de empezar la medida.
    while pedir("/api/estado").get("accion") not in (None, "parado"):
        time.sleep(0.05)

    inicio = time.monotonic()
    pedir("/api/programa", {"programa": programa})

    # Se mira el estado hasta que el robot vuelve a estar parado.
    while True:
        actual = pedir("/api/estado")
        if actual.get("accion") == "parado":
            break
        time.sleep(0.02)
    real = time.monotonic() - inicio

    print(f"Lo que tarda de verdad: {real:.2f} s")
    diferencia = abs(real - estimations["duracion"])
    print(f"Diferencia: {diferencia:.2f} s "
          f"({'OK' if diferencia < 0.25 else 'AVISO'})")


if __name__ == "__main__":
    main()
