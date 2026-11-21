"""
El "cerebro" de la API: traduce los bloques en pasos y los ejecuta con el
robot usando `airo_ble.session.RobotSession` (que es la libreria pura).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from airo_ble.protocol import Joint  # noqa: E402
from airo_ble.session import ESPERA_MINIMA_LED, NIVELES, RobotSession, Step

from .models import (
    Bloque,
    BloqueAtras,
    BloqueAvanza,
    BloqueBrazo,
    BloqueEspera,
    BloqueGira,
    BloqueKata,
    BloqueLlamada,
    BloqueLuz,
    BloquePara,
    BloqueRepetir,
    Funcion,
    Programa,
)

__all__ = [
    "RobotService",
    "Traductor",
    "CATALOGO",
    "MAX_PASOS",
    "MAX_PROFUNDIDAD_FUNCIONES",
    "ProgramaDemasiadoLarga",
    "FuncionDesconocida",
    "Resultado",
]

#: Tope de pasos por programa.
#:
#: Los bloques "repetir" se expanden aquí, antes de ejecutar, y se pueden
#: anidar: tres niveles de "repetir 50" son 125.000 pasos (unas 35 horas de
#: robot) en una sola peticion. Este tope corta la expansion y avisa con un
#: error claro.
MAX_PASOS = 1000

#: Cuantas funciones se pueden llamar dentro de otra funcion. Es el guard
#: contra el bucle infinito: si "saludo" se llama a si mismo, al quinto nivel
#: se corta y se avisa.
MAX_PROFUNDIDAD_FUNCIONES = 5


class ProgramaDemasiadoLarga(ValueError):
    """El programa tiene más pasos de los que se permiten."""


class FuncionDesconocida(ValueError):
    """El programa llama a una funcion que no existe (o se llama a si misma)."""


@dataclass(frozen=True)
class Resultado:
    """Lo que devuelve la ejecucion de un programa o de un bloque."""

    #: Cuantos pasos se han Traducido.
    pasos: int
    #: Cuanto va a durar, en segundos.
    duracion: float
    #: Cuantos programas hay esperando turno (0 = se ejecuta ahora mismo).
    cola: int = 0
    #: La duracion de cada bloque del programa, en el mismo orden (solo si se
    #: pidio el detalle).
    detalle: tuple[float, ...] = ()

#: Como se explica cada bloque en la interfaz (vive en el backend para que la
#: interfaz y la API no se desincronicen).
CATALOGO: list[dict[str, Any]] = [
    {
        "tipo": "avanzar",
        "titulo": "Avanza",
        "icono": "🚗",
        "color": "#4c97ff",
        "descripcion": "El robot va recto hacia delante.",
        "opciones": {"cuanto": ["poquito", "normal", "mucho"]},
    },
    {
        "tipo": "atras",
        "titulo": "Atras",
        "icono": "🔙",
        "color": "#4c97ff",
        "descripcion": "El robot va recto hacia atras.",
        "opciones": {"cuanto": ["poquito", "normal", "mucho"]},
    },
    {
        "tipo": "girar",
        "titulo": "Gira",
        "icono": "🔄",
        "color": "#ffab19",
        "descripcion": "El robot gira sobre si mismo.",
        "opciones": {"hacia": ["izquierda", "derecha"]},
    },
    {
        "tipo": "brazo",
        "titulo": "Mueve el brazo",
        "icono": "🙌",
        "color": "#9966ff",
        "descripcion": "Levanta o baja los brazos del robot.",
        "opciones": {
            "lado": ["derecho", "izquierdo", "ambos"],
            "pose": ["arriba", "abajo", "medio", "golpe", "guardia"],
            # Solo se usa en el modo avanzado de la interfaz: que articulacion
            # se mueve (las dos, solo el hombro o solo el codo).
            "articulacion": ["todo", "hombro", "codo"],
        },
    },
    {
        "tipo": "luz",
        "titulo": "Luz",
        "icono": "💡",
        "color": "#ff6680",
        "descripcion": "Enciende, apaga o hace parpadear la luz azul.",
        "opciones": {"modo": ["encendida", "apagada", "parpadea", "fundido"]},
    },
    {
        "tipo": "espera",
        "titulo": "Espera",
        "icono": "⏳",
        "color": "#cf8b17",
        "descripcion": "El robot se queda quieto un ratito.",
        "opciones": {},
    },
    {
        "tipo": "kata",
        "titulo": "Kata de karate",
        "icono": "🥋",
        "color": "#0fBD8C",
        "descripcion": "El robot hace una coreografia de karate.",
        "opciones": {},
    },
    {
        "tipo": "para",
        "titulo": "Para",
        "icono": "🛑",
        "color": "#5cb1d6",
        "descripcion": "El robot se para en seco.",
        "opciones": {},
    },
    {
        "tipo": "repetir",
        "titulo": "Repite",
        "icono": "🔁",
        "color": "#ffab19",
        "descripcion": "Repite los bloques de dentro las veces que quieras.",
        "opciones": {"veces": ["2", "3", "5", "10"]},
    },
]


class Traductor:
    """Convierte los bloques (Pydantic) en pasos (objetos de la libreria)."""

    @staticmethod
    def a_pasos(
        programa: Programa, funciones: dict[str, Funcion] | None = None
    ) -> list[Step]:
        pasos: list[Step] = []
        for bloque in programa.bloques:
            pasos.extend(Traductor.bloque_a_pasos(bloque, funciones))
            if len(pasos) > MAX_PASOS:
                raise ProgramaDemasiadoLarga(
                    f"El programa tiene más de {MAX_PASOS} pasos. "
                    "Quita repetitions o simplifica los bloques 'repetir'."
                )
        # El programa SIEMPRE termina con el robot parado. Sin esto, un
        # programa que acaba en "avanzar" deja al robot andando solo (lo
        # mismo que hace el kata de la app oficial: "avanzar 2" y luego
        # "parar").
        pasos.append(Step("parar", {}))
        return pasos

    @staticmethod
    def simular(
        pasos: list[Step], actuales: dict[Joint, float] | None = None
    ) -> tuple[float, dict[Joint, float]]:
        """Simula los pasos: cuanto duran y donde quedan los brazos.

        Devuelve el total de segundos y el estado de los brazos al terminar
        (para poder simular un bloque detras de otro).
        """
        from airo_ble.arms import duracion_de_accion, objetivos_de_paso
        from airo_ble.console import KATA

        total = 0.0
        estado: dict[Joint, float] = dict(actuales or {})
        for paso in pasos:
            if paso.kind == "kata":
                total += sum(d for _, d in KATA)
            elif paso.kind == "brazo":
                objetivos = objetivos_de_paso(paso.params)
                pedido = float(paso.params.get("segundos") or paso.duracion or 0.0)
                total += duracion_de_accion(objetivos, estado, pedido)
                estado.update(objetivos)
            else:
                total += paso.duracion
        return total, estado

    @staticmethod
    def duracion_de(
        pasos: list[Step], actuales: dict[Joint, float] | None = None
    ) -> float:
        """Cuanto va a durar el programa, en segundos.

        Esto **simula** el programa en vez de sumar duraciones a ciegas: los
        brazos no duran lo que les digas, sino lo que tarde el servo en
        llegar a donde le has pedido, y eso depende de donde estuviera antes.
        La interfaz lo usa para saber cuando ha terminado en vez de
        adivinarlo con un tiempo fijo por delante.
        """
        return Traductor.simular(pasos, actuales)[0]

    @staticmethod
    def duracion_por_bloque(
        programa: Programa,
        actuales: dict[Joint, float] | None = None,
        funciones: dict[str, Funcion] | None = None,
    ) -> tuple[float, list[float]]:
        """La duracion de cada bloque y la del programa entero.

        Los bloques se simulan **uno detras de otro** (igual que se ejecutan):
        el segundo brazo tarda menos si el primero ya ha dejado el servo
        cerca. Asi el detalle que ve el niño suma el total.
        """
        total = 0.0
        detalle: list[float] = []
        estado = dict(actuales or {})
        for bloque in programa.bloques:
            pasos = Traductor.bloque_a_pasos(bloque, funciones)
            duracion, estado = Traductor.simular(pasos, estado)
            total += duracion
            detalle.append(duracion)
        return total, detalle

    @staticmethod
    def bloque_a_pasos(
        bloque: Bloque,
        funciones: dict[str, Funcion] | None = None,
        profundidad: int = 0,
    ) -> list[Step]:
        funciones = funciones or {}
        if isinstance(bloque, BloqueAvanza):
            v = NIVELES[bloque.cuanto]
            return [
                Step("mover", {"izquierda": v, "derecha": v}, bloque.segundos),
                Step("parar", {}),
            ]
        if isinstance(bloque, BloqueAtras):
            v = NIVELES[bloque.cuanto]
            return [
                Step("mover", {"izquierda": -v, "derecha": -v}, bloque.segundos),
                Step("parar", {}),
            ]
        if isinstance(bloque, BloqueGira):
            v = NIVELES["normal"]
            izq, der = (v, -v) if bloque.hacia == "izquierda" else (-v, v)
            return [
                Step("mover", {"izquierda": izq, "derecha": der}, bloque.segundos),
                Step("parar", {}),
            ]
        if isinstance(bloque, BloqueBrazo):
            # `segundos` = 0 es "de golpe"; con valor es un movimiento lento,
            # en rampa, durante ese tiempo. `articulacion` acota el
            # movimiento a una sola articulacion y `angulo` manda sobre la
            # pose si viene.
            return [
                Step(
                    "brazo",
                    {
                        "lado": bloque.lado,
                        "pose": bloque.pose,
                        "articulacion": bloque.articulacion,
                        "angulo": bloque.angulo,
                        "segundos": bloque.segundos,
                    },
                    bloque.segundos,
                )
            ]
        if isinstance(bloque, BloqueLuz):
            modo = {
                "encendida": "on",
                "apagada": "off",
                "parpadea": "flash",
                "fundido": "fade",
            }[bloque.modo]
            # La luz necesita su tiempo: el firmware interpola el
            # flash/fade a partir de los paquetes, y sin espera no se ve.
            return [Step("luz", {"modo": modo}, ESPERA_MINIMA_LED)]
        if isinstance(bloque, BloqueEspera):
            return [Step("espera", {}, bloque.segundos)]
        if isinstance(bloque, BloqueKata):
            return [Step("kata", {})]
        if isinstance(bloque, BloquePara):
            return [Step("parar", {})]
        if isinstance(bloque, BloqueRepetir):
            # OJO: los "repetir" se expanden aqui y se pueden anidar, asi que
            # el tope se comprueba DENTRO del bucle. Si se comprobase al
            # final, tres niveles de "repetir 50" llegarian a construir
            # 125.000 pasos antes de decir que no.
            pasos: list[Step] = []
            for _ in range(bloque.veces):
                for interno in bloque.bloques:
                    pasos.extend(
                        Traductor.bloque_a_pasos(interno, funciones, profundidad)
                    )
                    if len(pasos) > MAX_PASOS:
                        raise ProgramaDemasiadoLarga(
                            f"El bloque 'repetir' genera más de {MAX_PASOS} "
                            "pasos. Quita repeticiones o quita el anidamiento."
                        )
            return pasos
        if isinstance(bloque, BloqueLlamada):
            # Una llamada es una REFERENCIA: aqui se despliega la funcion
            # (sus bloques) en el sitio de la llamada. Si editas la funcion
            # despues, todos los programas que la usan cambian.
            funcion = funciones.get(bloque.funcion)
            if funcion is None:
                raise FuncionDesconocida(
                    f"El programa llama a la función «{bloque.funcion}», "
                    "pero esa función no existe (¿la has borrado?)."
                )
            if profundidad >= MAX_PROFUNDIDAD_FUNCIONES:
                raise FuncionDesconocida(
                    f"La función «{funcion.nombre}» se llama a sí misma "
                    f"({profundidad + 1} niveles). Quita alguna llamada."
                )
            pasos: list[Step] = []
            for interno in funcion.bloques:
                pasos.extend(
                    Traductor.bloque_a_pasos(interno, funciones, profundidad + 1)
                )
                if len(pasos) > MAX_PASOS:
                    raise ProgramaDemasiadoLarga(
                        f"La función «{funcion.nombre}» genera más de "
                        f"{MAX_PASOS} pasos."
                    )
            return pasos
        raise ValueError(f"Bloque desconocido: {bloque}")


class RobotService:
    """Envoltorio con la sesion del robot para la API."""

    def __init__(self, address: str | None = None) -> None:
        self.sesion = RobotSession(address=address)
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Un lock por event loop (los tests usan uno distinto en cada caso)."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    async def conectar(self) -> None:
        async with self._get_lock():
            if self.sesion.conectado:
                return
            await self.sesion.conectar()

    async def desconectar(self) -> None:
        async with self._get_lock():
            await self.sesion.desconectar()

    async def ejecutar(
        self, programa: Programa, funciones: dict[str, Funcion] | None = None
    ) -> Resultado:
        pasos = Traductor.a_pasos(programa, funciones)
        duracion = Traductor.duracion_de(pasos, self.sesion.angulos_actuales())
        await self.sesion.ejecutar(pasos)
        return Resultado(
            pasos=len(pasos), duracion=duracion, cola=self.sesion.programas_en_cola
        )

    async def ejecutar_bloque(self, bloque: Bloque) -> Resultado:
        pasos = Traductor.bloque_a_pasos(bloque)
        duracion = Traductor.duracion_de(pasos, self.sesion.angulos_actuales())
        await self.sesion.ejecutar(pasos)
        return Resultado(
            pasos=len(pasos), duracion=duracion, cola=self.sesion.programas_en_cola
        )

    def duracion(
        self, programa: Programa, funciones: dict[str, Funcion] | None = None
    ) -> Resultado:
        """Cuanto va a durar el programa, **sin ejecutarlo**.

        La interfaz lo pregunta antes de darle a "Vamos" para que el niño sepa
        si va a esperar medio segundo o un minuto. No hace falta que el robot
        este conectado: sin conexion se simula desde la pose neutra.
        """
        pasos = Traductor.a_pasos(programa, funciones)
        total, detalle = Traductor.duracion_por_bloque(
            programa, self.sesion.angulos_actuales(), funciones
        )
        return Resultado(
            pasos=len(pasos), duracion=total, cola=0, detalle=tuple(detalle)
        )

    async def detener(self) -> None:
        await self.sesion.detener_programa()

    def estado(self) -> dict[str, Any]:
        return self.sesion.estado()
