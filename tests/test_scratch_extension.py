"""
Tests de la extension de Scratch (`airo_ble/scratch3_airo/airo.js`).

Scratch llama a los metodos de la extension **en el orden de los argumentos
del bloque**, no en el que pone el metodo. Si no coinciden, los bloques
mueven el robot con los valores cruzados (y sin querer, en silencio).

Este test comprueba que los dos ordenes son el mismo, para todos los
bloques. Es el vigilante del bloque del brazo, que se rompio una vez
(hombro y lado cambiados de sitio).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

EXTENSION = (
    Path(__file__).resolve().parent.parent / "airo_ble" / "scratch3_airo" / "airo.js"
)


def _codigo() -> str:
    return EXTENSION.read_text(encoding="utf-8")


def _contenido(codigo: str, inicio: int) -> tuple[str, int]:
    """El contenido del objeto que empieza en `inicio` (la "{") y donde acaba."""
    nivel = 0
    for j in range(inicio, len(codigo)):
        if codigo[j] == "{":
            nivel += 1
        elif codigo[j] == "}":
            nivel -= 1
            if nivel == 0:
                return codigo[inicio + 1 : j], j
    raise ValueError("no se cierra el objeto")


def _claves(contenido: str) -> list[str]:
    """Las claves de primer nivel de un objeto de JavaScript."""
    claves: list[str] = []
    nivel = 0
    for trozo in re.finditer(r"([A-Za-z_]\w*)\s*:|([{}])", contenido):
        if trozo.group(2) == "{":
            nivel += 1
        elif trozo.group(2) == "}":
            nivel -= 1
        elif nivel == 0 and trozo.group(1):
            claves.append(trozo.group(1))
    return claves


def _bloques(codigo: str) -> dict[str, list[str]]:
    """Los bloques de la extension: opcode -> argumentos, en orden.

    Se recorre la lista de bloques mirando los llaves de cada objeto (los
    argumentos van dentro, asi que no vale con un `split` tonto).
    """
    inicio = codigo.index("blocks: [")
    nivel = 0
    i = codigo.index("[", inicio)
    while i < len(codigo):
        if codigo[i] == "[":
            nivel += 1
        elif codigo[i] == "]":
            nivel -= 1
            if nivel == 0:
                break
        i += 1
    fin = i
    bloques: dict[str, list[str]] = {}
    i = codigo.index("{", inicio)
    while i < fin:
        objeto, j = _contenido(codigo, i)
        opcode = re.search(r"opcode:\s*'([^']+)'", objeto)
        if opcode:
            argumentos = re.search(r"arguments:\s*\{", objeto)
            claves: list[str] = []
            if argumentos:
                interior, _fin = _contenido(codigo, i + argumentos.end())
                claves = _claves(interior)
            bloques[opcode.group(1)] = claves
        i = codigo.find("{", j + 1)
    return bloques


def _metodos(codigo: str) -> dict[str, list[str]]:
    """Los metodos de la clase: nombre -> parametros, en orden."""
    metodos: dict[str, list[str]] = {}
    for nombre, parametros in re.findall(
        r"^\s{4}(?:async\s+)?(\w+)\(([^)]*)\)\s*\{", codigo, re.MULTILINE
    ):
        lista = [p.strip() for p in parametros.split(",") if p.strip()]
        metodos[nombre] = lista
    return metodos


@pytest.fixture(scope="module")
def bloques() -> dict[str, list[str]]:
    return _bloques(_codigo())


@pytest.fixture(scope="module")
def metodos() -> dict[str, list[str]]:
    return _metodos(_codigo())


def test_la_extension_tiene_bloques(bloques: dict[str, list[str]]) -> None:
    """Hay bloques y son los que se esperan."""
    for opcode in ("moveForward", "moveBackward", "turnLeft", "stop", "setArm", "kata"):
        assert opcode in bloques, opcode


def test_cada_bloque_tiene_su_metodo(
    bloques: dict[str, list[str]], metodos: dict[str, list[str]]
) -> None:
    """Todo bloque con opcode tiene su metodo (si no, Scratch no hace nada)."""
    sin_metodo = [op for op in bloques if op not in metodos]
    assert not sin_metodo, f"bloques sin metodo: {sin_metodo}"


def test_el_orden_de_los_argumentos_es_el_del_metodo(
    bloques: dict[str, list[str]], metodos: dict[str, list[str]]
) -> None:
    """Scratch pasa los argumentos en el orden del bloque: el metodo debe
    tenerlos en ese mismo orden (si no, van cruzados)."""
    cruzados = []
    for opcode, argumentos in bloques.items():
        if opcode not in metodos:
            continue
        esperados = [a.lower() for a in argumentos]
        if metodos[opcode] != esperados:
            cruzados.append(
                f"{opcode}: bloque {argumentos} vs metodo {metodos[opcode]}"
            )
    assert not cruzados, f"argumentos cruzados: {cruzados}"


def test_los_bloques_de_accion_esperan_al_servidor() -> None:
    """Los bloques de accion tienen que esperar la respuesta.

    Si no, Scratch da el bloque por hecho antes de que el comando llegue al
    servidor y el orden de los comandos se pierde.
    """
    codigo = _codigo()
    for opcode in ("moveForward", "stop", "setArm", "setArmJoint", "kata", "reset"):
        patron = rf"^\s{{4}}async\s+{opcode}\("
        assert re.search(patron, codigo, re.MULTILINE), opcode


def test_la_extension_no_habla_ble_directo() -> None:
    """Los bloques van al servidor local, que es el que habla con el robot."""
    codigo = _codigo()
    assert "bluetooth" not in codigo.lower()
    assert "/api/command" in codigo
    assert "/api/status" in codigo
