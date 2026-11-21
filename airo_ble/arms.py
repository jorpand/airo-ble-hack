"""
Los brazos del robot: las poses y como se decide que se mueve cada lado.

Aqui vive **todo** lo que decide que articulacion se mueve y con que angulo.
Antes de este modulo esa logica estaba duplicada en tres sitios (la consola,
la sesion y el servidor de Scratch) y cada copia entendia "izquierda" de otra
manera:

  - la consola acceptaba "izq"/"der"/"ambos" y hacia bien el espejo,
  - la sesion entendia "izq*"/"left*" y por eso "ambos" solo movia un lado,
  - el servidor de Scratch entendia "i*" y por eso "left" movia el brazo
    equivocado.

Ahora hay una sola fuente de verdad y las tres entradas la comparten.

OJO con los dos vocabularios de "lado":

  - el enum `Joint` de `protocol.py` usa los nombres **fisicos** del robot,
    los de la guia: byte 6 = hombro derecho, byte 7 = codo derecho,
    byte 8 = codo izquierdo, byte 9 = hombro izquierdo. En los hombros y los
    codos la app oficial y el robot **coinciden** (su "hombro derecho" mueve
    el hombro derecho de verdad); lo que si esta cruzado son las ruedas.

Las poses de aqui estan expresadas en el lado canonico **derecho** (el
fisico). El otro lado se obtiene espejando: los MISMOS angulos en la
articulacion simetrica.
"""

from __future__ import annotations

from .protocol import SERVO_LIMITS, Joint

__all__ = [
    "ARM_POSES",
    "LADOS",
    "ARTICULACIONES",
    "BrazoError",
    "PASOS_POR_SEGUNDO",
    "SERVO_VELOCIDAD",
    "ESPERA_MINIMA",
    "duracion_de_accion",
    "objetivos_de_paso",
    "pasos_rampa",
    "resolver_brazo",
    "resolver_brazos",
    "resolver_lado",
    "resolver_objetivos",
    "tiempo_de_viaje",
]


class BrazoError(ValueError):
    """El lado o la pose no existen (hereda de `ValueError` por compat.)."""


#: Velocidad del servo, en grados de la app por segundo.
#:
#: Es una medida del hardware, no del protocolo: el servo recorre su rango
#: entero (195 grados del codo) en poco mas de un segundo. Con esto se
#: calcula cuanto tarda un brazo en llegar a su destino, que es lo que
#: obliga a esperar entre dos movimientos seguidos.
SERVO_VELOCIDAD: float = 150.0

#: Espera minima tras un movimiento, aunque el servo no tenga que ir lejos.
#:
#: Es lo que hace falta para que el servo se asiente antes del siguiente
#: comando: si se le manda el destino nuevo antes de tiempo, el servo cambia
#: de destino a medio camino y el primer movimiento no llega a verse nunca.
#:
#: Son **1 segundo**, no 0,5: con medio segundo los movimientos seguidos se
#: confunden (uno se come al siguiente). La app oficial usa 0,5 s en su kata
#: porque sus poses estan muy separadas; aqui los bloques se encadenan
#: mucho mas.
ESPERA_MINIMA: float = 1.0

#: Escalones de rampa por segundo en un movimiento lento.
#:
#: Uno por refresco del paquete (50 ms), asi que el servo va persiguiendo un
#: destino que se mueve a ritmo de refresco. El tope real lo pone la
#: resolucion del byte: un byte son 8,5 grados, asi que un movimiento muy
#: lento se ve a escalones.
PASOS_POR_SEGUNDO: int = 20



#: Poses de los brazos, en angulos de la app.
#:
#: La tabla define el lado **derecho** (el fisico: hombro derecho y brazo
#: derecho) y el izquierdo se obtiene espejando: los MISMOS angulos en la
#: articulacion simetrica. El signo de cada servo ya invierte el sentido, asi
#: que los dos lados salen simetricos (sus bytes suman 40 = 2 x centro).
#:
#: Estas poses son las que se han verificado en el robot: hombro -60 y codo
#: +170 = brazo arriba; hombro +77 y codo -25 = brazo abierto.
ARM_POSES: dict[str, dict[Joint, float]] = {
    "arriba": {Joint.RIGHT_SHOULDER: -60.0, Joint.RIGHT_ARM: 170.0},
    "abajo": {Joint.RIGHT_SHOULDER: 77.0, Joint.RIGHT_ARM: -25.0},
    "medio": {Joint.RIGHT_SHOULDER: 0.0, Joint.RIGHT_ARM: 0.0},
    "golpe": {Joint.RIGHT_SHOULDER: -60.0, Joint.RIGHT_ARM: -25.0},
    "guardia": {Joint.RIGHT_SHOULDER: -60.0, Joint.RIGHT_ARM: 90.0},
}

#: La articulacion simetrica de cada una: el hombro se espeja con el hombro
#: y el codo con el codo.
_ESPEJO: dict[Joint, Joint] = {
    Joint.RIGHT_SHOULDER: Joint.LEFT_SHOULDER,
    Joint.RIGHT_ARM: Joint.LEFT_ARM,
    Joint.LEFT_SHOULDER: Joint.RIGHT_SHOULDER,
    Joint.LEFT_ARM: Joint.RIGHT_ARM,
}

#: Todos los nombres con los que se puede pedir un lado, y a que lados
#: corresponde. Se aceptan las dos lenguas porque cada entrada tiene su
#: vocabulario: la web usa "izquierda"/"derecha", Scratch usa "left"/"right"
#: y la consola "izq"/"der".
LADOS: dict[str, tuple[str, ...]] = {
    "izq": ("izquierdo",),
    "izquierda": ("izquierdo",),
    "izquierdo": ("izquierdo",),
    "left": ("izquierdo",),
    "l": ("izquierdo",),
    "der": ("derecho",),
    "derecha": ("derecho",),
    "derecho": ("derecho",),
    "right": ("derecho",),
    "r": ("derecho",),
    "ambos": ("derecho", "izquierdo"),
    "both": ("derecho", "izquierdo"),
    "dos": ("derecho", "izquierdo"),
}


def resolver_lado(lado: str) -> tuple[str, ...]:
    """Traduce el nombre de un lado a los lados que hay que mover.

    "izq", "izquierda" y "left" son el mismo lado; "ambos" son los dos.
    """
    clave = str(lado).strip().lower()
    if clave not in LADOS:
        raise BrazoError(
            f"Lado desconocido: {lado!r} ({', '.join(sorted(LADOS))})"
        )
    return LADOS[clave]


def resolver_brazo(lado: str, pose: str) -> dict[Joint, float]:
    """Traduce (lado, pose) en las articulaciones que hay que mover.

    Devuelve el mapa articulacion -> angulo. Para "ambos" devuelve las cuatro
    articulaciones (dos por lado); para un lado concreto, las suyas.
    """
    clave_pose = str(pose).strip().lower()
    if clave_pose not in ARM_POSES:
        raise BrazoError(
            f"Posición desconocida: {pose!r} ({', '.join(ARM_POSES)})"
        )
    resultado: dict[Joint, float] = {}
    for nombre in resolver_lado(lado):
        for joint, angle in ARM_POSES[clave_pose].items():
            if nombre == "izquierdo":
                # El lado izquierdo es el espejo del derecho, pero con el
                # MISMO angulo: el signo de cada servo ya invierte el
                # sentido (por eso el byte sale simetrico).
                joint = _ESPEJO[joint]
            resultado[joint] = angle
    return resultado


def resolver_brazos(mapa: dict[str, str]) -> dict[Joint, float]:
    """Varios lados a la vez, cada uno con su pose.

    `{"derecho": "arriba", "izquierdo": "abajo"}` devuelve las cuatro
    articulaciones: las del derecho con la pose de arriba y las del
    izquierdo con la de abajo. Es la forma de mover los dos brazos a la vez
    **con poses distintas**, que un unico (lado, pose) no puede expresar.

    Un lado que no aparece en el mapa se queda donde estaba: no se toca.
    """
    resultado: dict[Joint, float] = {}
    for lado, pose in mapa.items():
        resultado.update(resolver_brazo(lado, pose))
    return resultado


def objetivos_de_paso(params: dict) -> dict[Joint, float]:
    """Los objetivos de un paso de brazo, venga en la forma que venga.

    Acepta las dos formas:
      - `{"lado": "derecho", "pose": "arriba"}` (un lado, una pose)
      - `{"objetivos": {"derecho": "arriba", "izquierdo": "abajo"}}`
    """
    objetivos = params.get("objetivos")
    if isinstance(objetivos, dict) and objetivos:
        return resolver_brazos({str(k): str(v) for k, v in objetivos.items()})
    return resolver_objetivos(
        str(params.get("lado", "ambos")),
        pose=str(params.get("pose", "medio")) if params.get("pose") else None,
        articulacion=str(params.get("articulacion", "todo")),
        angulo=params.get("angulo"),
    )


#: Que articulaciones mueve una accion de brazo.
ARTICULACIONES: tuple[str, ...] = ("todo", "hombro", "codo")


def _recortar(joint: Joint, angulo: float) -> float:
    """Recorta un angulo a los limites mecanicos de la articulacion."""
    bajo, alto = SERVO_LIMITS[joint]
    return min(max(float(angulo), float(bajo)), float(alto))


def resolver_objetivos(
    lado: str,
    pose: str | None = None,
    articulacion: str = "todo",
    angulo: float | None = None,
) -> dict[Joint, float]:
    """Los objetivos de una accion de brazo, con su alcance.

    - `lado`: "derecho", "izquierdo" o "ambos".
    - `pose`: la pose nombrada ("arriba", "abajo", "medio", ...).
    - `angulo`: si se pasa, **manda sobre la pose**: es un angulo concreto.
    - `articulacion`: que articulaciones se mueven: "todo", "hombro" o "codo".

    Es la version con mas control que `resolver_brazo()` (que es la misma
    cosa con `articulacion="todo"` y la pose). Con un angulo explicito se
    puede mover solo el hombro o solo el codo de un lado, a un angulo
    concreto: los angulos de la app, los mismos que usan las poses.
    """
    clave_articulacion = str(articulacion).strip().lower()
    if clave_articulacion not in ARTICULACIONES:
        raise BrazoError(
            f"Articulación desconocida: {articulacion!r} "
            f"({', '.join(ARTICULACIONES)})"
        )

    if angulo is not None:
        angulo = float(angulo)
        if clave_articulacion == "todo":
            # Un solo angulo para las dos articulaciones no significa nada:
            # el hombro se moveria al angulo del codo (y al reves). Con "todo"
            # el destino son las poses.
            raise BrazoError(
                "El ángulo exacto necesita una sola articulación "
                "(hombro o codo); con 'todo' se usa una pose."
            )
        deltas = {Joint.RIGHT_SHOULDER: angulo, Joint.RIGHT_ARM: angulo}
    else:
        if pose is None:
            raise BrazoError("Hay que decir la pose o el angulo")
        clave_pose = str(pose).strip().lower()
        if clave_pose not in ARM_POSES:
            raise BrazoError(
                f"Posición desconocida: {pose!r} ({', '.join(ARM_POSES)})"
            )
        deltas = dict(ARM_POSES[clave_pose])

    resultado: dict[Joint, float] = {}
    for nombre in resolver_lado(lado):
        for joint, valor in deltas.items():
            if clave_articulacion == "hombro" and joint is not Joint.RIGHT_SHOULDER:
                continue
            if clave_articulacion == "codo" and joint is not Joint.RIGHT_ARM:
                continue
            destino = _ESPEJO[joint] if nombre == "izquierdo" else joint
            resultado[destino] = _recortar(destino, valor)
    return resultado


def tiempo_de_viaje(
    objetivos: dict[Joint, float], actuales: dict[Joint, float] | None = None
) -> float:
    """Cuanto tarda el servo en llegar a su destino.

    Es el peor de los travelos (el servo mas lento manda) y nunca menos de
    `ESPERA_MINIMA`, que es el tiempo que hace falta para que el servo se
    asiente antes del siguiente comando.
    """
    actuales = actuales or {}
    peor = 0.0
    for joint, destino in objetivos.items():
        origen = actuales.get(joint, 0.0)
        peor = max(peor, abs(destino - origen))
    return max(ESPERA_MINIMA, peor / SERVO_VELOCIDAD)


def duracion_de_accion(
    objetivos: dict[Joint, float],
    actuales: dict[Joint, float] | None = None,
    segundos: float = 0.0,
) -> float:
    """Cuanto dura la accion: lo que se pide o lo que tarda el servo.

    Si no se pide nada (`segundos` = 0), la accion dura lo que tarde el
    servo en llegar. Si se pide un tiempo, la accion dura al menos ese
    tiempo (y el movimiento se hace en rampa).
    """
    return max(segundos, tiempo_de_viaje(objetivos, actuales))


def pasos_rampa(
    objetivos: dict[Joint, float],
    duracion: float,
    actuales: dict[Joint, float] | None = None,
):
    """Los pasos de un movimiento lento, uno a uno.

    Cada paso es un mapa `articulacion -> angulo`: el destino va viajando
    hacia el servo, asi que el servo lo va persiguiendo (no sabe que le
    estan dando una rampa, simplemente va a donde le mandan).

    Es un generador para que lo usen **las tres entradas** igual (la sesion
    de la API, la consola y el puente de Scratch): una sola definicion de
    "movimiento lento", sin copias que se desincronicen.
    """
    origen = dict(actuales or {})
    total = max(1, round(duracion * PASOS_POR_SEGUNDO))
    for i in range(1, total + 1):
        t = i / total
        yield {
            joint: origen.get(joint, 0.0) + (destino - origen.get(joint, 0.0)) * t
            for joint, destino in objetivos.items()
        }
