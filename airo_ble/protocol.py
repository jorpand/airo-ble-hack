"""
Protocolo de comandos del robot Clementoni AIRO (versión 1.x).

Reconstruido por ingeniería inversa inversa del APK oficial `it.clementoni.robot.airo`
(Unity + IL2CPP), descompilando `libil2cpp.so` con Il2CppDumper y la capa Java
con jadx. Ver `docs/protocolo.md` para la cadena de evidencia.

Transporte: BLE (HM-10), servicio 0000FFF0, characteristic 0000FFF1, escritura
con respuesta (WRITE_TYPE 0x02).

Este módulo es puro: no depende de bleak ni de hardware, para poder testearlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Final

# --- Constantes del protocolo (extraídas de BleRobot.cs / RobotStatus.cs) --------

SERVICE_UUID: Final[str] = "0000FFF0-0000-1000-8000-00805F9B34FB"
WRITE_CHARACTERISTIC_UUID: Final[str] = "0000FFF1-0000-1000-8000-00805F9B34FB"
ROBOT_NAME: Final[str] = "AIRo"

PACKET_SIZE: Final[int] = 20
MAGIC: Final[int] = 0xA5
MAX_MOTOR_SPEED: Final[int] = 3

#: Bytes 10..19 los fija `RobotStatus.SetFixedBytes()` en el constructor y la
#: app nunca los vuelve a tocar: una rampa fija de 5 a 158 en pasos de 17.
FIXED_TAIL: Final[tuple[int, ...]] = (
    5, 22, 39, 56, 73, 90, 107, 124, 141, 158,
)

#: Índices dentro del paquete de 20 bytes.
IDX_MAGIC: Final[int] = 0
IDX_LED: Final[int] = 1
IDX_RIGHT_DIR: Final[int] = 2
IDX_RIGHT_SPEED: Final[int] = 3
IDX_LEFT_DIR: Final[int] = 4
IDX_LEFT_SPEED: Final[int] = 5
IDX_SERVO_1: Final[int] = 6
IDX_SERVO_2: Final[int] = 7
IDX_SERVO_3: Final[int] = 8
IDX_SERVO_4: Final[int] = 9


class Led(IntEnum):
    """`RobotStatus.LedStatus` — valor crudo que va al byte 1."""

    OFF = 0
    ON = 1
    FLASH = 2
    FADE = 3


class Direction(IntEnum):
    """Dirección de rueda. El firmware no usa un byte de signo: va el signo
    partido en dos campos (dirección + magnitud)."""

    STOP = 0
    FORWARD = 1
    BACKWARD = 2


class Joint(IntEnum):
    """Articulación -> servo que la mueve.

    Los nombres son **del robot físico** (el lado que ves al mirarlo), tal
    como los nombra `docs/protocolo.md` §2.

    Byte del paquete para cada una (ver `_JOINT_TO_INDEX`):

    | Articulación (física) | Byte | En la app oficial |
    |---|---|---|
    | `RIGHT_SHOULDER` | 6 | hombro derecho |
    | `RIGHT_ARM` | 7 | brazo derecho |
    | `LEFT_ARM` | 8 | brazo izquierdo |
    | `LEFT_SHOULDER` | 9 | hombro izquierdo |

    OJO: en los **hombros y los codos**, la app oficial y el robot **coinciden**
    (su "hombro derecho" mueve el hombro derecho de verdad). Lo que sí está
    cruzado son las **ruedas**: el motor "izquierdo" de la app mueve la rueda
    **derecha** del robot. Ver `to_bytes()` para el detalle.

    Estos nombres están verificados con el robot delante (2026-11-10): el
    byte 6 levanta el brazo que está a la **derecha** del robot, mirándolo de
    frente. Antes estaban al revés (ver `docs/protocolo.md` §2).
    """

    RIGHT_SHOULDER = 1
    RIGHT_ARM = 2
    LEFT_ARM = 3
    LEFT_SHOULDER = 4


_JOINT_TO_INDEX: Final[dict[Joint, int]] = {
    Joint.RIGHT_SHOULDER: IDX_SERVO_1,
    Joint.RIGHT_ARM: IDX_SERVO_2,
    Joint.LEFT_ARM: IDX_SERVO_3,
    Joint.LEFT_SHOULDER: IDX_SERVO_4,
}

#: Byte del paquete que lleva cada articulacion (mismo dato que
#: `_JOINT_TO_INDEX`, pero publico). La web lo necesita con el **mismo** origen
#: de la verdad: `tools/gen_servos.py` genera `web/src/servos.js` con esta
#: tabla, para que los numeros no se puedan desincronizar.
JOINT_BYTE: Final[dict[Joint, int]] = dict(_JOINT_TO_INDEX)

#: Nombres en minúsculas para la API de alto nivel (`servos(left_arm=30)`).
JOINT_NAMES: Final[dict[str, Joint]] = {j.name.lower(): j for j in Joint}

# --- Escalado de los servos ---------------------------------------------------
#
# OJO: la app NO manda el ángulo en grados. `RobotStatus.set_ServoMotor*Angle`
# convierte el ángulo a un byte antes de escribirlo en el paquete:
#
#     byte = |170 + signo * (ángulo + offset)| / 8.5      (redondeo banker's)
#
# El firmware trabaja en unidades de 8.5 grados, con el 0 en el byte 20. El
# signo va espejado: el lado izquierdo del robot gira al revés que el derecho.
#
# Evidencia: evidencia/RobotStatus_set_ServoMotor{One,Two,Three,Four}Angle.asm
#   - `cmp w20, #0x4d` / `cmp w20, #0xaa`  -> limites de angulo
#   - `cmn w8, #0x3c` / `cmn w8, #0x19`    -> limite inferior
#   - `add w9, w8, w9` + `add w9, w9, #0xaa` -> angulo + offset + 170
#   - `sub w9, w10, w20`                   -> 170 - angulo - offset
#   - `fmov d1, #8.50000000`               -> division por 8.5
#   - `bic w9, w9, w9, asr #31`            -> valor absoluto

#: Rango mecanico de cada articulacion, en los grados de la app.
SERVO_LIMITS: Final[dict[Joint, tuple[int, int]]] = {
    Joint.RIGHT_SHOULDER: (-60, 77),
    Joint.RIGHT_ARM: (-25, 170),
    Joint.LEFT_ARM: (-25, 170),
    Joint.LEFT_SHOULDER: (-60, 77),
}

#: Sentido de giro de cada servo respecto al angulo de la app. Los dos lados
#: giran en sentidos opuestos (son las mitades de un cuerpo simetrico).
#:
#: Estos signos van **por byte**, no por nombre: byte 6 = +, byte 7 = -,
#: byte 8 = +, byte 9 = -. Es lo que dice el desensamblado
#: (`set_ServoMotor{One,Two,Three,Four}Angle.asm`), y es el unico sitio donde
#: hay que tocarlo si alguna vez cambia el firmware.
SERVO_SIGN: Final[dict[Joint, int]] = {
    Joint.RIGHT_SHOULDER: +1,
    Joint.RIGHT_ARM: -1,
    Joint.LEFT_ARM: +1,
    Joint.LEFT_SHOULDER: -1,
}

#: Desplazamiento que la app suma antes de escalar (0xaa = 170).
SERVO_ORIGIN: Final[float] = 170.0
#: Escala del firmware: un byte = 8.5 grados.
SERVO_SCALE: Final[float] = 8.5
#: Byte que corresponde al angulo 0.
SERVO_CENTER: Final[int] = 20
#: Rango util del byte de servo (el firmware nunca espera mas de 40).
SERVO_BYTE_MAX: Final[int] = 40


def round_half_even(value: float) -> int:
    """Redondeo .NET `Math.Round(double)` = MidpointRounding.ToEven.

    La app usa ese redondeo (no el de Python) tanto para las velocidades como
    para los ángulos de servo, así que hay que imitarlo para no desfasarnos
    medio grado respecto a la app oficial.
    """
    floor = int(value // 1)
    frac = value - floor
    if frac > 0.5:
        return floor + 1
    if frac < 0.5:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def encode_motor(value: float, *, invert: bool = False) -> tuple[Direction, int]:
    """Convierte una velocidad con signo al par (dirección, magnitud).

    Reproduce la cadena real de la app: `BleRobot.SetLeftMotorSpeed(float)`
    redondea con `Math.Round` (banker's) y luego llama a
    `RobotStatus.set_LeftMotorSpeed(int)`, que decide así:

      valor == 0  -> (STOP, 0)
      valor  > 0  -> (FORWARD, min(|v|, 3))
      valor  < 0  -> (BACKWARD, min(|v|, 3))

    El redondeo va ANTES de mirar el signo, así que 0.4 y 0.5 paran el motor
    (0.5 redondea a 0 con redondeo banker's) mientras que 0.6 ya avanza.

    `invert=True` invierte el byte de dirección y es lo que necesita la rueda
    **izquierda**: `set_LeftMotorSpeed` escribe 2 (atrás) para avanzar, porque
    esa rueda va montada al revés en el chasis. Sin invertirlo el robot gira
    sobre sí mismo en lugar de avanzar. Verificado en el robot y en el
    desensamblado (`evidencia/RobotStatus_set_LeftMotorSpeed.asm`:
    `mov w9, #2` en la rama de valor positivo).
    """
    rounded = round_half_even(value)
    if rounded == 0:
        return Direction.STOP, 0
    magnitude = min(abs(rounded), MAX_MOTOR_SPEED)
    direction = Direction.FORWARD if rounded > 0 else Direction.BACKWARD
    if invert:
        direction = (
            Direction.BACKWARD if direction is Direction.FORWARD else Direction.FORWARD
        )
    return direction, magnitude


def encode_servo(
    joint: Joint,
    angle: float,
    offset: float = 0.0,
    neutral: int | None = None,
) -> int:
    """Convierte el angulo de la app al byte que va en el paquete.

    Reproduce `RobotStatus.set_ServoMotor*Angle`:

      1. el angulo se recorta a los limites mecanicos de la articulacion,
      2. se le suma el offset de calibracion (truncado a entero, `fcvtzs`),
      3. se aplica `170 + signo * (angulo + offset)`,
      4. se toma el valor absoluto, se limita a 340 y se divide entre 8.5,
      5. se redondea con `Math.Round` (banker's) y se trunca a entero.

    Ejemplos (sin offset): angulo 0 -> byte 20 en las cuatro articulaciones.

    `neutral` es el byte que se considera "angulo 0". Por defecto es 20 (el
    valor que usa la app), pero se puede cambiar por articulacion para
    adaptar el robot a su posicion de reposo real (ver `Command.neutral`).
    """
    low, high = SERVO_LIMITS[joint]
    clamped = min(max(angle, low), high)
    raw = SERVO_ORIGIN + SERVO_SIGN[joint] * (clamped + int(offset))
    scaled = min(abs(raw), SERVO_ORIGIN * 2) / SERVO_SCALE
    byte = round_half_even(scaled)
    if neutral is not None:
        # el mismo desplazamiento medido desde otro cero:
        # byte = |neutral + signo * (angulo + offset) / 8.5|
        base = float(neutral)
        bruto = base + SERVO_SIGN[joint] * (clamped + int(offset)) / SERVO_SCALE
        byte = round_half_even(abs(bruto))
    return max(0, min(SERVO_BYTE_MAX, byte))


@dataclass
class Command:
    """Estado completo del robot: lo que se envia en cada paquete.

    Cada campo corresponde exactamente a un byte del paquete de 20 bytes.

    `servos` guarda el angulo **de la app** (grados), no el byte final: la
    conversion a byte la hace `encode_servo()` al serializar, que es donde la
    app hace lo mismo.
    """

    led: Led = Led.OFF
    right_speed: float = 0.0
    left_speed: float = 0.0
    #: Angulo pedido por articulacion (grados de la app).
    servos: dict[Joint, float] = field(default_factory=dict)
    #: Bytes crudos por articulacion: tienen prioridad sobre `servos`.
    #: Sirve para experimentally a mano sin pasar por el escalado de la app.
    raw_servos: dict[Joint, int] = field(default_factory=dict)
    #: Byte que se considera "angulo 0" en cada articulacion. Por defecto es
    #: 20 (el valor de la app oficial). Cambiandolo se adapta el robot a su
    #: posicion de reposo real: si colocas los brazos a mano con el robot
    #: apagado y guardas el byte que reproduce esa posicion, ese byte pasa a
    #: ser el "cero" de esa articulacion.
    neutral: dict[Joint, int] = field(default_factory=dict)
    #: Calibracion por articulacion (en grados). La app suma el offset al
    #: angulo antes de enviarlo al servo.
    offsets: dict[Joint, float] = field(default_factory=dict)

    def set_servo(self, joint: Joint, angle: float) -> "Command":
        """Fija el angulo pedido para una articulacion (grados de la app).

        El offset de calibracion se suma al **serializar**, igual que en la
        app (que guarda el offset aparte y lo aplica en
        `set_ServoMotor*Angle`). Asi se puede recalibrar sin volver a mover
        las articulations.
        """
        self.raw_servos.pop(joint, None)
        self.servos[joint] = float(angle)
        return self

    def set_joint(self, joint: Joint, angle: float) -> "Command":
        """Alias de `set_servo` (el offset se aplica al serializar)."""
        return self.set_servo(joint, angle)

    def set_raw_servo(self, joint: Joint, value: int) -> "Command":
        """Manda un byte crudo en esa articulacion (para depurar)."""
        self.servos.pop(joint, None)
        self.raw_servos[joint] = int(value) & 0xFF
        return self

    def servo_byte(self, joint: Joint) -> int:
        """Byte que ira en el paquete para esa articulacion."""
        if joint in self.raw_servos:
            return self.raw_servos[joint] & 0xFF
        offset = self.offsets.get(joint, 0.0)
        neutral = self.neutral.get(joint)
        if joint in self.servos:
            return encode_servo(joint, self.servos[joint], offset, neutral)
        if offset or neutral is not None:
            # una articulacion sin angulo pero con calibracion se mueve
            # igualmente (en la app el angulo esta siempre puesto)
            return encode_servo(joint, 0.0, offset, neutral)
        return SERVO_CENTER
    def stop(self) -> "Command":
        """Para las ruedas sin tocar los servos (como hace `ResetStatus`)."""
        self.right_speed = 0.0
        self.left_speed = 0.0
        return self

    def to_bytes(self) -> bytes:
        """Serializa el comando a los 20 bytes que espera el firmware."""
        buf = bytearray(PACKET_SIZE)
        buf[IDX_MAGIC] = MAGIC
        buf[IDX_LED] = int(self.led)

        # Las ruedas del robot estan cruzadas respecto a la app oficial: el
        # motor "derecho" de la app (bytes 2-3) mueve la rueda IZQUIERDA del
        # robot, y el motor "izquierdo" de la app (bytes 4-5) la DERECHA.
        # Verificado en el hardware. Por eso la rueda derecha necesita el
        # byte de direccion invertido (ver `encode_motor`).
        left_dir, left_mag = encode_motor(self.left_speed)
        buf[IDX_RIGHT_DIR] = int(left_dir)
        buf[IDX_RIGHT_SPEED] = left_mag

        right_dir, right_mag = encode_motor(self.right_speed, invert=True)
        buf[IDX_LEFT_DIR] = int(right_dir)
        buf[IDX_LEFT_SPEED] = right_mag

        # Los servos empiezan en la posicion neutra (byte 20 = angulo 0), que es
        # lo que deja el robot con `ResetStatus`. Ojo: si se dejaran a 0 el
        # firmware los llevaria al tope mecanico y el robot haria un gesto con
        # los brazos al conectar.
        for joint, index in _JOINT_TO_INDEX.items():
            buf[index] = SERVO_CENTER
        for joint, index in _JOINT_TO_INDEX.items():
            if (
                joint in self.raw_servos
                or joint in self.servos
                or joint in self.offsets
                or joint in self.neutral
            ):
                buf[index] = self.servo_byte(joint) & 0xFF
        for i, value in enumerate(FIXED_TAIL, start=10):
            buf[i] = value & 0xFF

        return bytes(buf)

    def describe(self) -> str:
        """Volcado legible del paquete, util para depurar contra un sniffer."""
        b = self.to_bytes()
        lines = [
            f"  [0]  magic          = 0x{b[0]:02X}",
            f"  [1]  led            = {Led(b[1]).name.lower()}",
        ]
        for label, d_idx, s_idx, invert in (
            ("izquierda", IDX_RIGHT_DIR, IDX_RIGHT_SPEED, False),
            ("derecha ", IDX_LEFT_DIR, IDX_LEFT_SPEED, True),
        ):
            direction = Direction(b[d_idx])
            if invert and direction is not Direction.STOP:
                # el byte de la rueda derecha va invertido
                direction = (
                    Direction.BACKWARD if direction is Direction.FORWARD else Direction.FORWARD
                )
            speed = b[s_idx]
            lines.append(
                f"  [{d_idx}] rueda {label} dir = {direction.name.lower()}"
                f"   [{s_idx}] vel = {speed}"
            )
        for joint, index in sorted(_JOINT_TO_INDEX.items(), key=lambda kv: kv[1]):
            if joint in self.raw_servos:
                lines.append(
                    f"  [{index}] {joint.name.lower():15s} = {b[index]} (crudo)"
                )
            elif joint in self.servos:
                lines.append(
                    f"  [{index}] {joint.name.lower():15s} = {b[index]}"
                    f"  (angulo {self.servos[joint]:g})"
                )
        lines.append("  [10..19] fixed tail      = " + ", ".join(str(v) for v in b[10:]))
        lines.append(f"  hex = {b.hex(' ')}")
        return "\n".join(lines)
