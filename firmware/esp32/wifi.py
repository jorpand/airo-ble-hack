"""Conexion a la WiFi para el puente del ESP32-S3.

Las credenciales NO van en el codigo: se leen de `/wifi.json` en la placa
(un fichero que copias desde tu maquina con `mise run firmware-wifi` y que
esta en el .gitignore). Si el fichero no esta, se avisa y se sigue sin red:
el BLE funciona igual, que es lo que importa para el spike.
"""

import json
import time

#: Fichero de configuracion en la placa.
RUTA_CONFIG = "/wifi.json"

#: Cuanto se espera a que se associe la red (ms).
TIMEOUT_MS = 20000


def leer_config(ruta=RUTA_CONFIG):
    """Lee la configuracion de la placa. Devuelve None si no esta."""
    try:
        with open(ruta) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def conectar(ruta=RUTA_CONFIG, verbose=True):
    """Se conecta a la WiFi y devuelve la IP (o None si no puede).

    En un ESP32 con MicroPython: `network.WLAN(network.STA_IF)`.
    """
    config = leer_config(ruta)
    if config is None:
        if verbose:
            print(f"no esta {ruta}: se sigue sin WiFi (el BLE funciona igual)")
        return None

    import network

    ssid = config.get("ssid")
    password = config.get("password")
    hostname = config.get("hostname", "airo-bridge")
    if not ssid:
        if verbose:
            print(f"{ruta} no tiene 'ssid'")
        return None

    # El nombre del host se pone **antes** de activar la WiFi: en el ESP32 el
    # responder de mDNS se inicializa al activar la interfaz y usa el nombre
    # que hay en ese momento. (El `wlan.config(hostname=...)` de despues ya
    # no cambia lo que publica el mDNS: por eso el ESP32 avisa de que se use
    # `network.hostname()`.)
    if hostname:
        try:
            network.hostname(hostname)
        except (OSError, ValueError):  # pragma: no cover - depende del chip
            pass

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        if verbose:
            print(f"ya estaba conectada: {wlan.ifconfig()[0]}")
        return wlan.ifconfig()[0]

    if verbose:
        print(f"conectando a {ssid}...")
    wlan.connect(ssid, password)

    # Se espera en trozos: `time.ticks_ms` no existe en CPython, y aqui el
    # codigo tambien se lee y se prueba en el portatil.
    for _ in range(TIMEOUT_MS // 200):
        if wlan.isconnected():
            break
        time.sleep(0.2)
    else:
        if verbose:
            print("no se pudo conectar a la WiFi")
        return None

    ip = wlan.ifconfig()[0]
    if verbose:
        print(f"conectado a {ssid}, ip {ip}")
    return ip


def publicar_nombre(hostname="airo-bridge", verbose=True):
    """Fija el nombre del host, para que se pueda llamar `X.local`.

    En el ESP32 el **propio port** trae el responder de mDNS: se inicializa
    al activar la interfaz de WiFi y usa el nombre que hay en ese momento.
    Por eso `conectar()` pone el nombre **antes** de activar la interfaz; y
    esto lo vuelve a poner por si ya estaba conectada.

    Ojo: no hace falta (ni conviene) instalar el paquete `mdns` de micropython-lib,
    porque quiere el puerto 5353 y el del port ya lo tiene.
    """
    try:
        import network
    except ImportError:  # pragma: no cover - solo pasa en CPython
        return False
    try:
        network.hostname(hostname)
    except (OSError, ValueError) as exc:  # pragma: no cover - depende del chip
        if verbose:
            print(f"no se pudo fijar el nombre: {exc}")
        return False
    if verbose:
        print(f"nombre: {hostname}.local")
    return True
