"""Tests del LED RGB del firmware del ESP32-S3.

El LED de la placa (un WS2812 en el GPIO48 o en el GPIO38, segun la
revision) dice en que estado esta el puente:

- **rojo**: no hay nada conectado
- **azul**: se esta buscando al robot
- **verde**: el robot esta conectado

Y **parpadea del color que tenga** cuando hay trafico de comandos.

Aqui se falsea el modulo `neopixel` (que en CPython no existe) para poder
mirar que colores se escriben en el pixel, y se comprueba que el puente
manda los estados y los destellos que toca.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from _firmware import cargar

# --- Los dobles de la placa ---------------------------------------------------


class PixelFalso:
    """Un WS2812 de mentira: guarda los colores que se le escriben."""

    def __init__(self, pin: Any, n: int) -> None:
        self.pin = pin
        self.n = n
        self.valor = (0, 0, 0)
        #: Todos los colores que se han escrito (uno por `write`).
        self.escrituras: list[tuple[int, ...]] = []

    def __setitem__(self, idx: int, valor: Any) -> None:
        self.valor = tuple(valor)

    def fill(self, valor: Any) -> None:
        self.valor = tuple(valor)

    def write(self) -> None:
        self.escrituras.append(self.valor)


class PinFalso:
    """Un `machine.Pin` de mentira."""

    IN = 1
    OUT = 3

    def __init__(self, id: int, mode: Any = ..., **kwargs: Any) -> None:
        self.id = id
        self.mode = mode


@pytest.fixture
def placa(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mete un `neopixel` y un `machine` falsos y carga el modulo del LED."""
    pixels: list[PixelFalso] = []

    class NeoPixelFalso(PixelFalso):
        def __init__(self, pin: Any, n: int, **kwargs: Any) -> None:
            super().__init__(pin, n)
            pixels.append(self)

    neopixel = types.ModuleType("neopixel")
    neopixel.NeoPixel = NeoPixelFalso  # type: ignore[attr-defined]
    machine = types.ModuleType("machine")
    machine.Pin = PinFalso  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "neopixel", neopixel)
    monkeypatch.setitem(sys.modules, "machine", machine)
    mod = cargar("led")
    return {"mod": mod, "pixels": pixels}


@pytest.fixture
def puente() -> Any:
    return cargar("puente")


@pytest.fixture
def http_srv() -> Any:
    return cargar("http_srv")


class LedFalso:
    """El LED de mentira del puente: solo guarda el color y los destellos."""

    def __init__(self) -> None:
        self.color: Any = None
        self.destellos = 0
        self.parpadeos = 0

    def estado(self, color: Any) -> None:
        self.color = color

    def destello(self) -> None:
        self.destellos += 1
        self.parpadeos += 1


# --- El LED: los colores ------------------------------------------------------


def test_el_led_arranca_en_rojo(placa: dict[str, Any]) -> None:
    """Sin nada conectado, el LED esta en rojo."""
    mod = placa["mod"]
    led = mod.Led()
    assert led.color == mod.ROJO
    assert placa["pixels"][0].escrituras[-1] == mod.ROJO


def test_el_led_pinta_el_color_del_estado(placa: dict[str, Any]) -> None:
    """Cada cambio de estado se pinta en el pixel."""
    mod = placa["mod"]
    led = mod.Led()
    led.estado(mod.VERDE)
    led.paso()
    assert placa["pixels"][0].escrituras[-1] == mod.VERDE


def test_el_led_no_se_repinta_si_no_cambia(placa: dict[str, Any]) -> None:
    """Repintar lo mismo no es escribir otra vez en el WS2812."""
    mod = placa["mod"]
    led = mod.Led()
    pixel = placa["pixels"][0]
    antes = len(pixel.escrituras)
    led.paso()
    led.paso()
    assert len(pixel.escrituras) == antes


def test_el_led_se_enciende_en_los_dos_pines(placa: dict[str, Any]) -> None:
    """Se manejan los dos pines: rev 1.0 (GPIO48) y rev 1.1 (GPIO38).

    El chip no dice que revision es, asi que se encienden los dos: el que
    no tenga el LED enganchado no hace nada.
    """
    mod = placa["mod"]
    mod.Led()
    assert len(placa["pixels"]) == len(mod.PINES_LED) == 2
    assert {p.pin.id for p in placa["pixels"]} == set(mod.PINES_LED)


def test_una_placa_sin_ws2812_no_rompe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si no hay `neopixel` (placa sin LED), el puente sigue funcionando."""
    monkeypatch.delitem(sys.modules, "neopixel", raising=False)
    monkeypatch.delitem(sys.modules, "machine", raising=False)
    mod = cargar("led")
    led = mod.Led()
    assert led.pixels == []
    led.estado(mod.VERDE)
    led.paso()  # no se rompe


# --- El LED: el parpadeo ------------------------------------------------------


def test_el_destello_apaga_el_led_y_lo_devuelve(placa: dict[str, Any]) -> None:
    """El destello es un overlay: apaga y enciende, sin cambiar el color."""
    mod = placa["mod"]
    led = mod.Led()
    led.estado(mod.VERDE)
    led.paso()
    led.destello()
    for _ in range(mod.DESTELLOS):
        led.paso()
    assert (0, 0, 0) in placa["pixels"][0].escrituras
    assert placa["pixels"][0].escrituras[-1] == mod.VERDE
    # El color de fondo sigue siendo el del estado.
    assert led.color == mod.VERDE


def test_el_destello_parpadea_del_color_del_estado(placa: dict[str, Any]) -> None:
    """El LED parpadea del color que tenga, no de otro."""
    mod = placa["mod"]
    led = mod.Led()
    led.estado(mod.AZUL)
    led.paso()
    led.destello()
    led.paso()
    assert placa["pixels"][0].escrituras[-1] == (0, 0, 0)
    led.paso()
    assert placa["pixels"][0].escrituras[-1] == mod.AZUL


def test_el_destello_se_acaba(placa: dict[str, Any]) -> None:
    """Pasados los destellos, el LED se queda con su color, fijo."""
    mod = placa["mod"]
    led = mod.Led()
    led.destello()
    for _ in range(mod.DESTELLOS):
        led.paso()
    assert led.destellos == 0
    assert led.encendido is True
    assert led.color == mod.ROJO


def test_el_led_cuenta_los_destellos(placa: dict[str, Any]) -> None:
    """El contador dice cuantos comandos han llegado al puente."""
    mod = placa["mod"]
    led = mod.Led()
    led.destello()
    led.destello()
    assert led.parpadeos == 2


# --- El puente: los estados ---------------------------------------------------

async def test_el_puente_empieza_en_rojo(puente: Any) -> None:
    """Sin conexion con el robot, el LED esta en rojo."""
    p = puente.Puente(indicador=LedFalso())
    assert p.led.color == puente.led.ROJO


async def test_el_led_pone_verde_cuando_hay_conexion(puente: Any) -> None:
    """Conectado al robot: verde."""
    p = puente.Puente(indicador=LedFalso())
    p.cliente.conn = 1
    p.actualizar_led()
    assert p.led.color == puente.led.VERDE


async def test_el_led_pone_azul_mientras_se_busca(puente: Any) -> None:
    """Buscando al robot: azul."""
    p = puente.Puente(indicador=LedFalso())
    p.buscando = True
    p.actualizar_led()
    assert p.led.color == puente.led.AZUL


async def test_el_led_vuelve_a_rojo_si_no_se_encuentra_el_robot(
    puente: Any, http_srv: Any
) -> None:
    """Al dejar de buscar, el LED vuelve al color del estado (rojo)."""
    p = puente.Puente(indicador=LedFalso())

    async def buscar_falso(*args: Any, **kwargs: Any) -> tuple[None, None]:
        # Mientras se busca, el LED tiene que estar en azul.
        assert p.buscando
        assert p.led.color == puente.led.AZUL
        return None, None

    p.cliente.buscar_robot = buscar_falso
    peticion = http_srv.Peticion("POST", "/conectar", {}, b"")
    codigo, _datos = await p.r_conectar(peticion)
    assert codigo == 409
    assert p.buscando is False
    assert p.led.color == puente.led.ROJO


async def test_el_estado_dice_el_color_del_led(puente: Any, http_srv: Any) -> None:
    """El estado del puente enseña el color del LED (para verlo sin mirar)."""
    p = puente.Puente(indicador=LedFalso())
    peticion = http_srv.Peticion("GET", "/estado", {}, b"")
    codigo, datos = await p.r_estado(peticion)
    assert codigo == 200
    assert datos["led"] == "rojo"
    assert datos["led_parpadeos"] == 0


# --- El puente: el parpadeo ---------------------------------------------------


async def test_escribir_hace_parpadear_el_led(puente: Any, http_srv: Any) -> None:
    """Mandar un comando hace parpadear el LED del color que tenga."""
    p = puente.Puente(indicador=LedFalso())
    peticion = http_srv.Peticion("POST", "/escribir", {}, b"\xa5\x00")
    codigo, _datos = await p.r_escribir(peticion)
    # Sin conexion con el robot, la escritura falla: pero el LED ha
    # parpadeado igual, porque ha habido trafico de comandos.
    assert codigo == 409
    assert p.led.destellos == 1
    assert p.led.parpadeos == 1


async def test_un_cuerpo_vacio_no_hace_parpadear(puente: Any, http_srv: Any) -> None:
    """Un cuerpo vacio no es ningun comando: el LED no parpadea."""
    p = puente.Puente(indicador=LedFalso())
    peticion = http_srv.Peticion("POST", "/escribir", {}, b"")
    codigo, _datos = await p.r_escribir(peticion)
    assert codigo == 400
    assert p.led.destellos == 0
