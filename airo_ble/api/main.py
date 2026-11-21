"""
API del robot Clementoni AIRO (FastAPI).

Sirve la interfaz web (React) y una API JSON para programs.

    uvicorn airo_ble.api.main:app --reload --port 8100

O directamente:

    python3 -m airo_ble.api.main
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from airo_ble.session import NIVELES

from . import guardado as almacen
from .models import (
    Bloque,
    DescripcionBloque,
    Estado,
    FuncionGuardada,
    Guardado,
    PeticionBloque,
    PeticionGuardarFuncion,
    PeticionGuardarPrograma,
    PeticionMover,
    PeticionPrograma,
    Programa,
    ProgramaGuardado,
    RespuestaDuracion,
    RespuestaEjecucion,
)
from .service import (
    CATALOGO,
    FuncionDesconocida,
    ProgramaDemasiadoLarga,
    RobotService,
    Traductor,
)

#: Donde vive la interfaz web compilada. Solo existe en un checkout del repo
#: (en el paquete instalado no hay `web/`), asi que se comprueba antes de
#: montarla.
#:
#: Se puede cambiar con la variable de entorno `AIRO_WEB_DIR`, por si la
#: interfaz esta compilada en otro sitio (un despliegue, una copia...).
WEB_DIR = Path(
    os.environ.get("AIRO_WEB_DIR") or (Path(__file__).resolve().parents[2] / "web" / "dist")
).expanduser()

servicio = RobotService()


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado de la API.

    Esto sustituye a los `@app.on_event("startup"/"shutdown")`, que FastAPI
    ya no recomienda (salen depreados). Con el lifespan el apagado tambien
    **cancela la tarea** que reintenta la conexion en segundo plano: antes
    esa tarea se creaba sin guardar la referencia y se quedaba viva para
    siempre.
    """
    # no bloquea: si el robot esta dormido, la interfaz sigue funcionando
    tarea = asyncio.create_task(_conectar_en_segundo_plano())
    try:
        yield
    finally:
        tarea.cancel()
        # `return_exceptions=True` captura el CancelledError del hijo, pero
        # si se cancela a NOSOTROS el CancelledError se propaga igual
        await asyncio.gather(tarea, return_exceptions=True)
        await servicio.desconectar()


app = FastAPI(
    title="AIRO",
    description="Control del robot Clementoni AIRO",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _conectar_en_segundo_plano() -> None:
    """Conecta con el robot y, si no esta, reintenta cada 10 s.

    El modulo BLE del robot se duerme: encenderlo deberia bastar para que
    la interfaz se conecte sola.
    """
    while True:
        try:
            await servicio.conectar()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[api] todavia no: {exc}", flush=True)
            print("[api] reintento en 10 s (enciende el robot)", flush=True)
            await asyncio.sleep(10)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@app.get("/api/estado", response_model=Estado)
async def estado() -> Estado:
    """Como esta el robot ahora mismo."""
    return Estado(**servicio.estado())


@app.get("/api/bloques", response_model=list[DescripcionBloque])
async def bloques() -> list[DescripcionBloque]:
    """Los bloques disponibles, con su nombre bonito y sus opciones."""
    return [DescripcionBloque(**b) for b in CATALOGO]


@app.get("/api/niveles")
async def niveles() -> dict[str, Any]:
    """Los tres niveles de velocidad del robot, con su nombre de niño."""
    return {"niveles": NIVELES, "maximo_segundos": 30.0}


@app.post("/api/programa", response_model=RespuestaEjecucion)
async def ejecuta_programa(peticion: PeticionPrograma) -> RespuestaEjecucion:
    """Ejecuta un programa entero (una lista de bloques).

    Las funciones que usa el programa van en `peticion.funciones` (por id):
    el bloque "llamada" es solo una referencia y aqui se despliega.
    """
    try:
        resultado = await servicio.ejecutar(peticion.programa, peticion.funciones)
    except ProgramaDemasiadoLarga as exc:
        return RespuestaEjecucion(ok=False, mensaje=str(exc))
    except FuncionDesconocida as exc:
        return RespuestaEjecucion(ok=False, mensaje=str(exc))
    return RespuestaEjecucion(
        ok=True,
        mensaje=f"Vamos con {peticion.programa.nombre}!",
        pasos=resultado.pasos,
        duracion=resultado.duracion,
        cola=resultado.cola,
    )


@app.post("/api/bloque", response_model=RespuestaEjecucion)
async def ejecuta_bloque(peticion: PeticionBloque) -> RespuestaEjecucion:
    """Ejecuta un solo bloque (para probar cosas quickly)."""
    try:
        resultado = await servicio.ejecutar_bloque(peticion.bloque)
    except ProgramaDemasiadoLarga as exc:
        return RespuestaEjecucion(ok=False, mensaje=str(exc))
    return RespuestaEjecucion(
        ok=True,
        mensaje="Listo",
        pasos=resultado.pasos,
        duracion=resultado.duracion,
        cola=resultado.cola,
    )


@app.post("/api/duracion", response_model=RespuestaDuracion)
async def duracion(peticion: PeticionPrograma) -> RespuestaDuracion:
    """Cuanto va a durar un programa, sin ejecutarlo.

    La interfaz lo pregunta antes de darle a "Vamos": asi el niño sabe si
    va a esperar medio segundo o un minuto. Devuelve tambien la duracion de
    cada bloque, para poder ponerla debajo de cada bloque.
    """
    try:
        resultado = servicio.duracion(peticion.programa, peticion.funciones)
    except ProgramaDemasiadoLarga as exc:
        return RespuestaDuracion(ok=False, mensaje=str(exc))
    except FuncionDesconocida as exc:
        return RespuestaDuracion(ok=False, mensaje=str(exc))
    return RespuestaDuracion(
        ok=True,
        duracion=resultado.duracion,
        pasos=resultado.pasos,
        bloques=list(resultado.detalle),
    )


# ---------------------------------------------------------------------------
# El guardado: los programas y las funciones
# ---------------------------------------------------------------------------


@app.get("/api/guardado", response_model=Guardado)
async def ver_guardado() -> Guardado:
    """Todo lo que hay guardado: los programas y las funciones."""
    datos = almacen.leer()
    return Guardado(
        programas=[ProgramaGuardado(**p) for p in datos["programas"]],
        funciones=[FuncionGuardada(**f) for f in datos["funciones"]],
    )


@app.post("/api/guardado/programa", response_model=ProgramaGuardado)
async def guarda_programa(peticion: PeticionGuardarPrograma) -> ProgramaGuardado:
    """Guarda un programa (si tiene id, lo actualiza)."""
    try:
        datos = almacen.guardar_programa(
            peticion.id,
            peticion.nombre,
            [b.model_dump() for b in peticion.bloques],
        )
    except almacen.ErrorGuardado as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ProgramaGuardado(**datos)


@app.delete("/api/guardado/programa/{id_programa}", response_model=RespuestaEjecucion)
async def borra_programa(id_programa: str) -> RespuestaEjecucion:
    """Borra un programa guardado."""
    try:
        borrado = almacen.borrar_programa(id_programa)
    except almacen.ErrorGuardado as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RespuestaEjecucion(
        ok=borrado,
        mensaje="Programa borrado." if borrado else "Ese programa no estaba guardado.",
    )


@app.post("/api/guardado/funcion", response_model=FuncionGuardada)
async def guarda_funcion(peticion: PeticionGuardarFuncion) -> FuncionGuardada:
    """Guarda una funcion (si tiene id, la actualiza)."""
    try:
        datos = almacen.guardar_funcion(
            peticion.id,
            peticion.nombre,
            [b.model_dump() for b in peticion.bloques],
        )
    except almacen.ErrorGuardado as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FuncionGuardada(**datos)


@app.delete("/api/guardado/funcion/{id_funcion}", response_model=RespuestaEjecucion)
async def borra_funcion(id_funcion: str) -> RespuestaEjecucion:
    """Borra una funcion guardada."""
    try:
        borrado = almacen.borrar_funcion(id_funcion)
    except almacen.ErrorGuardado as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RespuestaEjecucion(
        ok=borrado,
        mensaje="Función borrada." if borrado else "Esa función no estaba guardada.",
    )


@app.post("/api/mover", response_model=RespuestaEjecucion)
async def mover(peticion: PeticionMover) -> RespuestaEjecucion:
    """Mueve las ruedas un rato (para el control manual).

    Al acabar el rato el robot se para solo. Con `segundos=0` las ruedas se
    quedan girando hasta que se llame a `/api/parar` (movimiento sostenido).
    """
    try:
        await servicio.sesion.mover(
            izquierda=peticion.izquierda,
            derecha=peticion.derecha,
            segundos=peticion.segundos,
        )
    finally:
        if peticion.segundos > 0:
            # sin esto el robot se iba tobaleando: la velocidad se queda
            # puesta y el refresco la sigue mandando
            await servicio.sesion.parar()
    return RespuestaEjecucion(ok=True, mensaje="Ok")


@app.post("/api/parar", response_model=RespuestaEjecucion)
async def parar() -> RespuestaEjecucion:
    """Para el robot y el programa en curso."""
    await servicio.detener()
    return RespuestaEjecucion(ok=True, mensaje="Parado")


@app.post("/api/conectar", response_model=RespuestaEjecucion)
async def conectar() -> RespuestaEjecucion:
    """Intenta conectar con el robot."""
    try:
        await servicio.conectar()
    except Exception as exc:
        return RespuestaEjecucion(ok=False, mensaje=str(exc))
    return RespuestaEjecucion(ok=True, mensaje="Conectado")


@app.post("/api/desconectar", response_model=RespuestaEjecucion)
async def desconectar() -> RespuestaEjecucion:
    await servicio.desconectar()
    return RespuestaEjecucion(ok=True, mensaje="Desconectado")


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    """Envia el estado del robot en vivo (para la animacion de la interfaz)."""
    await ws.accept()
    try:
        while True:
            await ws.send_json(servicio.estado())
            await asyncio.sleep(0.25)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except Exception:
        with contextlib.suppress(Exception):
            await ws.close()


# ---------------------------------------------------------------------------
# La interfaz web (React compilada)
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> Any:
    if (WEB_DIR / "index.html").exists():
        return FileResponse(WEB_DIR / "index.html")
    return JSONResponse(
        {
            "ok": False,
            "mensaje": (
                "La interfaz web no esta compilada. "
                "Haz: cd web && npm ci && npm run build"
            ),
            "api": "/docs",
        },
    )


if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "airo_ble.api.main:app",
        host="127.0.0.1",
        port=8100,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
