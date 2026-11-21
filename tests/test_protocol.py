"""
Tests del protocolo AIRO.

Los valores esperados NO están inventados: son los que salen del desensamblado
de `RobotStatus.SetFixedBytes`, `set_LeftMotorSpeed`, `set_RightMotorSpeed`,
`set_LedBlue` y `set_ServoMotor*Angle` (ver ../evidencia/).

Ejecutar:  python3 tests/test_protocol.py      (o pytest)
"""

from __future__ import annotations

from airo_ble.protocol import (
    FIXED_TAIL,
    IDX_LED,
    IDX_LEFT_DIR,
    IDX_LEFT_SPEED,
    IDX_RIGHT_DIR,
    IDX_RIGHT_SPEED,
    IDX_SERVO_1,
    IDX_SERVO_2,
    IDX_SERVO_3,
    IDX_SERVO_4,
    MAGIC,
    PACKET_SIZE,
    SERVO_CENTER,
    Command,
    Direction,
    Joint,
    Led,
    encode_motor,
    encode_servo,
    round_half_even,
)


def test_packet_size():
    assert PACKET_SIZE == 20
    assert len(Command().to_bytes()) == 20


def test_magic_header():
    # SetFixedBytes: mov w9, #0xa5 ; strb w9, [x8, #0x20]  -> data[0]
    assert Command().to_bytes()[0] == MAGIC == 0xA5


def test_fixed_tail():
    # SetFixedBytes escribe data[10..19] con 5,22,39,56,73,90,107,124,141,158
    assert FIXED_TAIL == (5, 22, 39, 56, 73, 90, 107, 124, 141, 158)
    assert Command().to_bytes()[10:] == bytes(FIXED_TAIL)


def test_led_byte():
    # set_LedBlue: strb w1, [x8, #0x21] -> data[1]
    assert Command(led=Led.FLASH).to_bytes()[IDX_LED] == 2
    assert Command(led=Led.FADE).to_bytes()[IDX_LED] == 3


def test_servos_default_to_the_neutral_position():
    # Si los servos se dejaran a 0 el firmware los llevaria al tope mecanico
    # y el robot haria un gesto con los brazos al conectar. El byte neutro es
    # el 20 (angulo 0), que es lo que deja el robot con `ResetStatus`.
    b = Command().to_bytes()
    assert b[6:10] == bytes([20, 20, 20, 20])
    assert b[IDX_SERVO_1] == SERVO_CENTER


def test_motor_stop():
    # valor == 0 -> command[dir]=0 y command[speed]=0
    direction, magnitude = encode_motor(0.0)
    assert (direction, magnitude) == (Direction.STOP, 0)
    b = Command(left_speed=0.0, right_speed=0.0).to_bytes()
    assert b[IDX_LEFT_DIR] == 0 and b[IDX_LEFT_SPEED] == 0
    assert b[IDX_RIGHT_DIR] == 0 and b[IDX_RIGHT_SPEED] == 0


def test_motor_forward_and_backward():
    # valor > 0 -> dir 1 ; valor < 0 -> dir 2 ; magnitud = min(abs(v), 3)
    assert encode_motor(1.0) == (Direction.FORWARD, 1)
    assert encode_motor(-1.0) == (Direction.BACKWARD, 1)
    assert encode_motor(3.0) == (Direction.FORWARD, 3)
    assert encode_motor(-3.0) == (Direction.BACKWARD, 3)
    assert encode_motor(9.0) == (Direction.FORWARD, 3)   # saturado
    assert encode_motor(-9.0) == (Direction.BACKWARD, 3)


def test_motor_positions():
    # El byte 2-3 es el motor "derecho" de la app (rueda izquierda del robot)
    # y el 4-5 el "izquierdo" de la app (rueda derecha del robot).
    b = Command(left_speed=2.0, right_speed=-1.0).to_bytes()
    # rueda izquierda fisica (bytes 2-3) = adelante, vel 2
    assert (b[IDX_RIGHT_DIR], b[IDX_RIGHT_SPEED]) == (1, 2)
    # rueda derecha fisica (bytes 4-5) = atras, vel 1
    assert (b[IDX_LEFT_DIR], b[IDX_LEFT_SPEED]) == (1, 1)


def test_the_wheels_are_crossed():
    # El robot tiene las ruedas cruzadas respecto a la app: el byte de la
    # rueda derecha va invertido. Sin esto el robot gira sobre si mismo.
    assert encode_motor(1.0, invert=True) == (Direction.BACKWARD, 1)
    assert encode_motor(-1.0, invert=True) == (Direction.FORWARD, 1)
    assert encode_motor(0.0, invert=True) == (Direction.STOP, 0)
    # Las dos ruedas fisicas hacia delante
    b = Command(left_speed=1.0, right_speed=1.0).to_bytes()
    assert (b[IDX_RIGHT_DIR], b[IDX_RIGHT_SPEED]) == (1, 1)
    assert (b[IDX_LEFT_DIR], b[IDX_LEFT_SPEED]) == (2, 1)
    # Girar a la izquierda = rueda izquierda adelante y derecha atras
    b = Command(left_speed=1.0, right_speed=-1.0).to_bytes()
    assert (b[IDX_RIGHT_DIR], b[IDX_RIGHT_SPEED]) == (1, 1)
    assert (b[IDX_LEFT_DIR], b[IDX_LEFT_SPEED]) == (1, 1)


def test_bankers_rounding():
    # La app usa Math.Round(double) de .NET = MidpointRounding.ToEven
    assert round_half_even(0.5) == 0
    assert round_half_even(1.5) == 2
    assert round_half_even(2.5) == 2
    assert round_half_even(-0.5) == 0
    assert round_half_even(-1.5) == -2
    assert round_half_even(3.7) == 4
    assert round_half_even(-3.7) == -4


def test_rounding_feeds_the_motor():
    # 1.5 -> 2 (no 1), y -1.5 -> -2
    assert encode_motor(1.5) == (Direction.FORWARD, 2)
    assert encode_motor(-1.5) == (Direction.BACKWARD, 2)
    # 0.5 -> 0 (round-half-even) -> parado
    assert encode_motor(0.5) == (Direction.STOP, 0)


def test_servo_indices():
    # Los nombres del enum son los FISICOS (los de la guia): el byte 6 es el
    # hombro derecho de verdad: el byte 6. En los hombros y los codos la app
    # oficial y el robot coinciden (su "hombro derecho" es este byte 6).
    c = Command()
    c.set_servo(Joint.RIGHT_SHOULDER, 10)
    c.set_servo(Joint.RIGHT_ARM, 20)
    c.set_servo(Joint.LEFT_ARM, 30)
    c.set_servo(Joint.LEFT_SHOULDER, 40)
    b = c.to_bytes()
    assert b[IDX_SERVO_1] == encode_servo(Joint.RIGHT_SHOULDER, 10)
    assert b[IDX_SERVO_2] == encode_servo(Joint.RIGHT_ARM, 20)
    assert b[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 30)
    assert b[IDX_SERVO_4] == encode_servo(Joint.LEFT_SHOULDER, 40)


def test_servo_zero_is_the_center_byte():
    # La app manda |170 + signo*angulo| / 8.5 -> el angulo 0 es el byte 20
    for joint in Joint:
        assert encode_servo(joint, 0) == 20


def test_servo_scaling():
    # hombro derecho -> byte 6: (170 + angulo) / 8.5
    assert encode_servo(Joint.RIGHT_SHOULDER, 0) == 20
    assert encode_servo(Joint.RIGHT_SHOULDER, 77) == 29   # 247 / 8.5 = 29.05
    assert encode_servo(Joint.RIGHT_SHOULDER, -60) == 13  # 110 / 8.5 = 12.94
    # hombro izquierdo -> byte 9: (170 - angulo) / 8.5
    assert encode_servo(Joint.LEFT_SHOULDER, 77) == 11    # 93 / 8.5 = 10.94
    assert encode_servo(Joint.LEFT_SHOULDER, -60) == 27   # 230 / 8.5 = 27.05
    # codo derecho -> byte 7: (170 - angulo) / 8.5
    assert encode_servo(Joint.RIGHT_ARM, 170) == 0
    assert encode_servo(Joint.RIGHT_ARM, -25) == 23        # 195 / 8.5 = 22.94
    # codo izquierdo -> byte 8: (170 + angulo) / 8.5
    assert encode_servo(Joint.LEFT_ARM, 170) == 40         # 340 / 8.5 = 40
    assert encode_servo(Joint.LEFT_ARM, -25) == 17         # 145 / 8.5 = 17.05


def test_servo_angles_are_clamped_to_the_mechanical_limits():
    # La app recorta el angulo antes de escalarlo (cmp w20, #0x4d / #0xaa)
    assert encode_servo(Joint.RIGHT_SHOULDER, 500) == encode_servo(Joint.RIGHT_SHOULDER, 77)
    assert encode_servo(Joint.RIGHT_SHOULDER, -500) == encode_servo(Joint.RIGHT_SHOULDER, -60)
    assert encode_servo(Joint.LEFT_ARM, 500) == encode_servo(Joint.LEFT_ARM, 170)
    assert encode_servo(Joint.LEFT_ARM, -500) == encode_servo(Joint.LEFT_ARM, -25)


def test_offsets_are_added_before_sending():
    # La app suma el offset (truncado a entero) al angulo antes de escalar.
    c = Command()
    c.offsets[Joint.LEFT_ARM] = 5.0
    c.set_joint(Joint.LEFT_ARM, 30.0)
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 30.0 + 5.0)


def test_offsets_are_applied_at_serialization_time():
    # Como en la app: el offset se guarda aparte y se suma al enviar, asi que
    # recalibrar no obliga a volver a mover las articulaciones.
    c = Command()
    c.set_joint(Joint.LEFT_ARM, 30.0)
    sin_offset = c.to_bytes()[IDX_SERVO_3]
    c.offsets[Joint.LEFT_ARM] = 17.0
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 47.0)
    assert c.to_bytes()[IDX_SERVO_3] != sin_offset


def test_offset_is_truncated_like_the_app():
    # La app guarda el offset como float pero lo trunca a entero al aplicarlo
    # (`fcvtzs` en set_ServoMotor*Angle).
    c = Command()
    c.offsets[Joint.LEFT_ARM] = 2.9
    c.set_joint(Joint.LEFT_ARM, 30.0)
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 32.0)


def test_offset_moves_a_joint_without_angle():
    # Una articulacion sin angulo pero con calibracion tambien se mueve: asi
    # el calibrado se ve al instante en el robot.
    c = Command()
    assert c.to_bytes()[IDX_SERVO_3] == SERVO_CENTER
    c.offsets[Joint.LEFT_ARM] = 17.0
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 0.0, 17.0)
    assert c.to_bytes()[IDX_SERVO_3] != SERVO_CENTER


def test_neutral_is_the_zero_of_a_joint():
    # El "cero" de una articulacion (el byte que corresponde al angulo 0) se
    # puede cambiar para adaptar el robot a su posicion de reposo.
    c = Command()
    c.neutral[Joint.LEFT_ARM] = 25
    assert c.to_bytes()[IDX_SERVO_3] == 25
    c.set_servo(Joint.LEFT_ARM, 17.0)
    assert c.to_bytes()[IDX_SERVO_3] == 27   # 25 + 17/8.5 = 2 bytes
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 17.0, 0.0, 25)


def test_neutral_without_neutral_is_the_app_default():
    c = Command()
    assert c.to_bytes()[IDX_SERVO_3] == SERVO_CENTER
    assert encode_servo(Joint.LEFT_ARM, 0.0) == SERVO_CENTER


def test_raw_servo_overrides_the_angle():
    c = Command()
    c.set_servo(Joint.LEFT_ARM, 30)
    c.set_raw_servo(Joint.LEFT_ARM, 7)
    assert c.to_bytes()[IDX_SERVO_3] == 7


def test_golden_packet():
    """Paquete completo, byte a byte, contra el layout del firmware."""
    c = Command(led=Led.ON, right_speed=1.0, left_speed=-2.0)
    c.set_servo(Joint.RIGHT_SHOULDER, 5)
    c.set_servo(Joint.RIGHT_ARM, 22)
    c.set_servo(Joint.LEFT_ARM, 39)
    c.set_servo(Joint.LEFT_SHOULDER, 56)
    expected = bytes([
        0xA5,              # 0  magic
        0x01,              # 1  led = on
        0x02, 0x02,        # 2-3  motor "derecho" de la app = rueda izquierda: atras, vel 2
        0x02, 0x01,        # 4-5  motor "izquierdo" de la app = rueda derecha: adelante, vel 1
        0x15,              # 6  hombro derecho           (175/8.5 = 20.6)
        0x11,              # 7  codo derecho             (148/8.5 = 17.4)
        0x19,              # 8  codo izquierdo        (209/8.5 = 24.6)
        0x0D,              # 9  hombro izquierdo         (114/8.5 = 13.4)
        0x05, 0x16, 0x27, 0x38, 0x49, 0x5A, 0x6B, 0x7C, 0x8D, 0x9E,  # 10-19 fijos
    ])
    assert c.to_bytes() == expected


def test_stop_does_not_clear_servos():
    c = Command()
    c.set_servo(Joint.LEFT_ARM, 77)
    c.stop()
    assert c.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 77)
    assert c.to_bytes()[IDX_RIGHT_SPEED] == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests OK")
    raise SystemExit(1 if failed else 0)
