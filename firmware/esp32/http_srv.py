"""Servidor HTTP minimo para el puente del ESP32-S3.

Sin frameworks: `asyncio.start_server` y a pelo. El puente solo necesita
cuatro o cinco rutas, asi que un servidor entero de HTTP seria overkill
(ademas de MicroPython no hay uvicorn ni ningun framework de esos).

Lo que hace:

- Escucha en un puerto (8080 por defecto).
- Lee la peticion (linea de request + cabeceras + cuerpo).
- Llama al manejador de la ruta y escribe la respuesta.
- Una peticion por conexion y cierra (`Connection: close`).

El cuerpo se entrega como `bytes` crudos, que es lo que necesita el puente:
lo que se manda al robot son bytes, no JSON.
"""

import asyncio
import json

#: Cabeceras de respuesta que se mandan siempre.
_SERVidor = "airo-bridge/1.0 (ESP32-S3)"


class Peticion:
    """Lo que recibe un manejador de ruta."""

    def __init__(self, metodo, ruta, cabeceras, cuerpo):
        self.metodo = metodo
        self.ruta = ruta
        self.cabeceras = cabeceras
        self.cuerpo = cuerpo

    def json(self):
        """El cuerpo interpretado como JSON (o None si no es JSON)."""
        if not self.cuerpo:
            return None
        try:
            return json.loads(self.cuerpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def texto(self):
        """El cuerpo como texto."""
        return self.cuerpo.decode("utf-8", "replace")


def _respuesta(codigo, cuerpo, tipo="application/json"):
    """Arma la respuesta HTTP cruda."""
    if isinstance(cuerpo, str):
        cuerpo = cuerpo.encode("utf-8")
    motivos = {200: "OK", 400: "Bad Request", 404: "Not Found", 409: "Conflict", 500: "Error"}
    motivo = motivos.get(codigo, "Error")
    cabecera = (
        f"HTTP/1.1 {codigo} {motivo}\r\n"
        f"Server: {_SERVidor}\r\n"
        f"Content-Type: {tipo}\r\n"
        f"Content-Length: {len(cuerpo)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    return cabecera.encode("utf-8") + cuerpo


def _json(codigo, datos):
    """Respuesta JSON."""
    return _respuesta(codigo, json.dumps(datos))


async def _atender(reader, writer, rutas):
    """Atiende una conexion: lee la peticion y escribe la respuesta."""
    try:
        # Linea de request: "METODO /ruta HTTP/1.1"
        linea = await reader.readline()
        if not linea:
            return
        partes = linea.decode("utf-8", "replace").split()
        if len(partes) < 2:
            await _escribir(writer, _respuesta(400, '{"error": "peticion invalida"}'))
            return
        metodo, ruta = partes[0].upper(), partes[1]

        # La ruta puede traer parametros ("/escanear?ms=5000"): se buscan
        # con la ruta pelada, pero el manejador recibe la ruta entera para
        # poder leer los parametros.
        ruta_pelada = ruta.split("?", 1)[0]

        # Cabeceras
        cabeceras = {}
        while True:
            linea = await reader.readline()
            if not linea or linea in (b"\r\n", b"\n"):
                break
            if b":" in linea:
                clave, _, valor = linea.decode("utf-8", "replace").partition(":")
                cabeceras[clave.strip().lower()] = valor.strip()

        # Cuerpo
        largo = int(cabeceras.get("content-length", 0) or 0)
        cuerpo = await reader.read(largo) if largo else b""

        manejador = rutas.get((metodo, ruta_pelada))
        if manejador is None:
            await _escribir(writer, _json(404, {"error": f"no hay ruta {metodo} {ruta_pelada}"}))
            return

        peticion = Peticion(metodo, ruta, cabeceras, cuerpo)
        try:
            codigo, datos = await manejador(peticion)
        except Exception as exc:  # pragma: no cover - depende del hardware
            codigo, datos = 500, {"error": str(exc)}
        await _escribir(writer, _json(codigo, datos))
    except Exception as exc:  # pragma: no cover
        try:
            await _escribir(writer, _json(500, {"error": str(exc)}))
        except Exception:
            pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _escribir(writer, datos):
    """Escribe la respuesta y vacia el buffer."""
    try:
        writer.write(datos)
        await writer.drain()
    except Exception:
        pass


async def servir(host, puerto, rutas):
    """Arranca el servidor y se queda esperando. No vuelve nunca.

    `rutas` es un diccionario {(metodo, ruta): manejador}. El manejador
    recibe una `Peticion` y devuelve (codigo, datos) con `datos` ya
    serializable a JSON.
    """
    servidor = await asyncio.start_server(
        lambda r, w: _atender(r, w, rutas),
        host,
        puerto,
    )
    print(f"puente escuchando en http://{host}:{puerto}")
    async with servidor:
        await servidor.wait_closed()
