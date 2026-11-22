"""El LED RGB de la placa (WS2812) dice en que estado esta el puente.

La ESP32-S3-DevKitC-1 lleva un LED RGB **direccionable** (un WS2812):

- revision v1.0: esta en el GPIO48
- revision v1.1: esta en el GPIO38

El chip no dice que revision es la que tenemos delante, asi que se manejan
los dos pines: el que no tenga el LED enganchado no hace nada. Los dos
son GPIOs libres en esta placa (el PSRAM octal usa el GPIO35-37).

Los colores son el estado del enlace:

| Color | Cuando |
|---|---|
| ROJO | no hay nada conectado |
| AZUL | se esta buscando al robot |
| VERDE | el robot esta conectado |

Y cuando hay trafico de comandos, el LED **parpadea** del color que tenga
(ver `Led.destello`).

El destello es un *overlay*: no es un cuarto color, sino que el LED se
apaga y se enciende un par de veces con el color del estado de fondo. Asi
se sigue viendo en que estado esta el enlace mientras hay trafico.
"""

import asyncio

try:
    import neopixel
    from machine import Pin
except ImportError:  # pragma: no cover - placa sin WS2812
    neopixel = None  # type: ignore[assignment]
    Pin = None  # type: ignore[assignment]

#: Pines donde puede estar el LED WS2812 de la placa.
#:
#: Los dos, a proposito: el LED esta en el GPIO48 en las placas v1.0 y en el
#: GPIO38 en las v1.1, y no hay forma de saber cual es. El que no tenga el
#: LED enganchado simplemente no hace nada.
PINES_LED = (48, 38)

#: Brillo de los colores (0-255).
#:
#: A tope ciega: el LED esta al lado de la placa y se ve desde cualquier
#: angulo. Con 40 se distingue bien el color sin molestar.
BRILLO = 40

ROJO = (BRILLO, 0, 0)
AZUL = (0, 0, BRILLO)
VERDE = (0, BRILLO, 0)

#: Los nombres de los colores, para el estado del puente.
NOMBRES = {ROJO: "rojo", AZUL: "azul", VERDE: "verde"}

#: Cada cuanto se repinta el LED (segundos).
PASO = 0.08

#: Cuantos parpadeos hace un destello (cada paso enciende o apaga).
DESTELLOS = 4


def nombre(color):
    """El nombre de un color (para enseyar el estado por HTTP)."""
    return NOMBRES.get(color, "rojo")


class Led:
    """El LED RGB de la placa: el color es el estado, el destello es actividad."""

    def __init__(self, pines=PINES_LED):
        self.pixels = []
        if neopixel is not None and Pin is not None:
            try:
                self.pixels = [
                    neopixel.NeoPixel(Pin(pin, Pin.OUT), 1) for pin in pines
                ]
            except Exception:  # pragma: no cover - depende del hardware
                # Si el WS2812 no esta donde se espera, el puente sigue
                # funcionando igual (solo se pierde el LED).
                self.pixels = []
        #: El color de fondo (el del estado).
        self.color = ROJO
        #: Destellos que quedan por hacer.
        self.destellos = 0
        #: Cuantos destellos se han pedido en total (para verlo por HTTP:
        #: dice cuantos comandos han llegado al puente).
        self.parpadeos = 0
        #: Si el LED esta encendido ahora mismo.
        self.encendido = True
        #: Lo ultimo que se ha pintado (para no repintar lo mismo).
        self.pintado = None
        self._pintar()

    def estado(self, color):
        """Fija el color de fondo (el del estado)."""
        self.color = color

    def destello(self):
        """Manda parpadear el LED del color que tenga."""
        self.destellos = DESTELLOS
        self.parpadeos += 1

    def _pintar(self):
        """Pinta el color (o el apagado) si ha cambiado."""
        valor = self.color if self.encendido else (0, 0, 0)
        if valor == self.pintado:
            return
        for pixel in self.pixels:
            pixel[0] = valor
            pixel.write()
        self.pintado = valor

    def paso(self):
        """Un paso de la animacion: el destello va encendiendo y apagando."""
        if self.destellos > 0:
            self.destellos -= 1
            self.encendido = not self.encendido
        elif not self.encendido:
            # Se acabo el destello: el LED vuelve a su color.
            self.encendido = True
        self._pintar()

    async def animar(self):
        """Repinta el LED: mantiene el color y hace los parpadeos.

        Es una tarea de por vida: la crea `main.py` al arrancar.
        """
        while True:
            await asyncio.sleep(PASO)
            self.paso()
