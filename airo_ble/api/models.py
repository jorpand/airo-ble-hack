"""
Modelos Pydantic de la API: los bloques del robot, en lenguaje de niño.

La idea es que nadie tenga que saber qué es un byte, un grado o una velocidad:
solo "avanza", "gira a la izquierda", "levanta el brazo", "un segundo", etc.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------


class BloqueBase(BaseModel):
    """Datos comunes a todos los bloques."""

    id: str = Field(default="", description="Identificador unico del bloque")


class BloqueAvanza(BloqueBase):
    """Avanza recto."""

    tipo: Literal["avanzar"] = "avanzar"
    cuanto: Literal["poquito", "normal", "mucho"] = "normal"
    segundos: float = Field(default=1.0, ge=0.2, le=30.0)


class BloqueAtras(BloqueBase):
    """Avanza hacia atras."""

    tipo: Literal["atras"] = "atras"
    cuanto: Literal["poquito", "normal", "mucho"] = "normal"
    segundos: float = Field(default=1.0, ge=0.2, le=30.0)


class BloqueGira(BloqueBase):
    """Gira sobre si mismo."""

    tipo: Literal["girar"] = "girar"
    hacia: Literal["izquierda", "derecha"] = "izquierda"
    segundos: float = Field(default=1.0, ge=0.2, le=30.0)


class BloqueBrazo(BloqueBase):
    """Mueve un brazo.

    `segundos` es opcional: si no se pone, el brazo va "de golpe" y se
    espera lo que tarde el servo en llegar. Si se pone, el movimiento es
    **lento**: el destino va viajando hasta el servo durante ese tiempo.

    `articulacion` acota el movimiento a una sola articulacion ("hombro" o
    "codo"); con "todo" se mueven las dos, como en las poses.
    `angulo`, si se pone, manda sobre la pose: es un angulo concreto de la
    app (los mismos grados que usan las poses).
    """

    tipo: Literal["brazo"] = "brazo"
    lado: Literal["izquierdo", "derecho", "ambos"] = "derecho"
    pose: Literal["arriba", "abajo", "medio", "golpe", "guardia"] = "arriba"
    #: Que articulacion se mueve: las dos, solo el hombro o solo el codo.
    articulacion: Literal["todo", "hombro", "codo"] = "todo"
    #: Un angulo concreto (grados de la app). Si se pone, manda sobre la pose.
    angulo: float | None = Field(default=None, ge=-60.0, le=170.0)
    #: 0 = de golpe. Cualquier otro valor = movimiento lento en rampa.
    segundos: float = Field(default=0.0, ge=0.0, le=30.0)

    @model_validator(mode="after")
    def _el_angulo_exacto_necesita_una_articulacion(self) -> BloqueBrazo:
        """Un solo angulo para las dos articulaciones no significa nada.

        Sin esta comprobacion el backend aceptaria el bloque y fallaria
        justo al ejecutarlo (con el brazo a medio camino). Aqui se rechaza
        antes, con un 422 y un mensaje claro.
        """
        if self.angulo is not None and self.articulacion == "todo":
            raise ValueError(
                "El ángulo exacto necesita una sola articulación "
                "(hombro o codo); con 'todo' se usa una pose."
            )
        return self


class BloqueLuz(BloqueBase):
    """Enciende, apaga o hace parpadear la luz."""

    tipo: Literal["luz"] = "luz"
    modo: Literal["encendida", "apagada", "parpadea", "fundido"] = "encendida"


class BloqueEspera(BloqueBase):
    """Espera sin hacer nada."""

    tipo: Literal["espera"] = "espera"
    segundos: float = Field(default=1.0, ge=0.2, le=30.0)


class BloqueKata(BloqueBase):
    """La coreografia de karate."""

    tipo: Literal["kata"] = "kata"


class BloquePara(BloqueBase):
    """Para el robot en seco."""

    tipo: Literal["para"] = "para"


class BloqueRepetir(BloqueBase):
    """Repite los bloques de dentro varias veces."""

    tipo: Literal["repetir"] = "repetir"
    veces: int = Field(default=2, ge=1, le=50)
    bloques: list[Bloque] = Field(default_factory=list)


class BloqueLlamada(BloqueBase):
    """Llama a una funcion guardada.

    Es una **referencia**: el bloque no lleva los pasos dentro, solo el id de
    la funcion. Asi, si editas la funcion despues, todos los programas que la
    usan ejecutan la version nueva. El backend la despliega (expande sus
    bloques) al traducir el programa a pasos.
    """

    tipo: Literal["llamada"] = "llamada"
    #: El id de la funcion a la que llama (no el nombre: asi se puede
    #: renombrar la funcion sin romper los programas que la usan).
    funcion: str


Bloque = Annotated[
    BloqueAvanza
    | BloqueAtras
    | BloqueGira
    | BloqueBrazo
    | BloqueLuz
    | BloqueEspera
    | BloqueKata
    | BloquePara
    | BloqueRepetir
    | BloqueLlamada,
    Field(discriminator="tipo"),
]

BloqueRepetir.model_rebuild()


# ---------------------------------------------------------------------------
# Programas y peticiones
# ---------------------------------------------------------------------------


class Programa(BaseModel):
    """La lista de bloques que va a ejecutar el robot."""

    nombre: str = "Mi programa"
    bloques: list[Bloque] = Field(default_factory=list)


class Funcion(BaseModel):
    """Una funcion: un trozo de bloques con nombre que se puede reutilizar.

    Se guarda en el disco (ver `api/guardado.py`) y se llama desde un
    programa con un bloque `llamada`.
    """

    id: str = Field(default="", description="Identificador unico de la funcion")
    nombre: str = "Mi funcion"
    bloques: list[Bloque] = Field(default_factory=list)


class ProgramaGuardado(BaseModel):
    """Un programa guardado en el disco."""

    id: str
    nombre: str
    bloques: list[Bloque] = Field(default_factory=list)
    creado: str = ""
    modificado: str = ""


class FuncionGuardada(BaseModel):
    """Una funcion guardada en el disco."""

    id: str
    nombre: str
    bloques: list[Bloque] = Field(default_factory=list)
    creado: str = ""
    modificado: str = ""


class Guardado(BaseModel):
    """Todo lo que hay guardado: los programas y las funciones."""

    programas: list[ProgramaGuardado] = Field(default_factory=list)
    funciones: list[FuncionGuardada] = Field(default_factory=list)


class PeticionGuardarPrograma(BaseModel):
    """Guardar (o actualizar) un programa."""

    id: str = ""
    nombre: str = "Mi programa"
    bloques: list[Bloque] = Field(default_factory=list)


class PeticionGuardarFuncion(BaseModel):
    """Guardar (o actualizar) una funcion."""

    id: str = ""
    nombre: str = "Mi funcion"
    bloques: list[Bloque] = Field(default_factory=list)


class PeticionPrograma(BaseModel):
    programa: Programa
    #: Las funciones que usa el programa, por id. Se mandan **con** el
    #: programa porque una llamada es solo una referencia: el backend necesita
    #: los bloques de la funcion para desplegarla.
    funciones: dict[str, Funcion] = Field(default_factory=dict)


class PeticionBloque(BaseModel):
    """Un bloque suelto (para probar uno sin hacer un programa entero)."""

    bloque: Bloque


class PeticionMover(BaseModel):
    izquierda: float = Field(default=0.0, ge=-3.0, le=3.0)
    derecha: float = Field(default=0.0, ge=-3.0, le=3.0)
    segundos: float = Field(default=1.0, ge=0.0, le=60.0)


# ---------------------------------------------------------------------------
# Respuestas
# ---------------------------------------------------------------------------


class Estado(BaseModel):
    conectado: bool
    accion: str | None = None
    error: str | None = None
    luz: str = "off"
    ruedas: dict[str, float] = Field(default_factory=dict)
    brazos: dict[str, dict[str, float]] = Field(default_factory=dict)
    #: Cuantos programas hay esperando turno (0 = se esta ejecutando el
    #: ultimo). Los programas se ejecutan uno detras de otro.
    cola: int = 0


class RespuestaEjecucion(BaseModel):
    ok: bool = True
    mensaje: str = ""
    pasos: int = 0
    #: Cuanto va a durar el programa, en segundos. La interfaz lo usa para
    #: saber cuando ha terminado en vez de adivinarlo con un tiempo fijo.
    duracion: float = 0.0
    #: Cuantos programas hay esperando turno. Los programas se ejecutan uno
    #: detras de otro: pulsar "ejecutar" dos veces ya no corta el primero.
    cola: int = 0


class RespuestaDuracion(BaseModel):
    """Cuanto va a durar un programa, sin ejecutarlo."""

    ok: bool = True
    mensaje: str = ""
    #: La duracion total, en segundos.
    duracion: float = 0.0
    #: Cuantos pasos genera el programa (los "repetir" ya estan expandidos).
    pasos: int = 0
    #: La duracion de cada bloque, en el mismo orden que el programa. Asi la
    #: interfaz puede decir cuanto dura cada bloque y no solo el total.
    bloques: list[float] = Field(default_factory=list)


class DescripcionBloque(BaseModel):
    """Como se explica un bloque en la interfaz (viene del backend)."""

    tipo: str
    titulo: str
    icono: str
    color: str
    descripcion: str
    opciones: dict[str, list[str]] = Field(default_factory=dict)
