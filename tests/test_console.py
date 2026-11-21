"""
Tests de la consola interactiva, sin hardware.

Se usa el modo `--dry-run`: la consola parsea los comandos y compose el
paquete, pero no escribe nada por BLE.

Ejecutar: python3 tests/test_console.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airo_ble.client import AiroRobot  # noqa: E402
from airo_ble.console import Console, ConsoleError, resolve_joint  # noqa: E402
from airo_ble.protocol import (  # noqa: E402
    IDX_LEFT_DIR,
    IDX_LEFT_SPEED,
    IDX_LED,
    IDX_RIGHT_DIR,
    IDX_RIGHT_SPEED,
    IDX_SERVO_1,
    IDX_SERVO_3,
    Joint,
    Led,
    encode_servo,
)


def make_console() -> Console:
    robot = AiroRobot()
    return Console(robot, dry_run=True, echo=False, keepalive=False)


async def test_movement_commands():
    console = make_console()

    await console.execute("avanzar 2")
    cmd = console.robot.command
    assert (cmd.left_speed, cmd.right_speed) == (2.0, 2.0)
    # rueda izquierda fisica (bytes 2-3) = adelante
    assert cmd.to_bytes()[IDX_RIGHT_DIR] == 1 and cmd.to_bytes()[IDX_RIGHT_SPEED] == 2
    # rueda derecha fisica (bytes 4-5) = adelante (byte invertido)
    assert cmd.to_bytes()[IDX_LEFT_DIR] == 2 and cmd.to_bytes()[IDX_LEFT_SPEED] == 2

    await console.execute("atras 1")
    assert console.robot.command.to_bytes()[IDX_RIGHT_DIR] == 2

    await console.execute("izquierda 1")
    cmd = console.robot.command
    assert (cmd.left_speed, cmd.right_speed) == (1.0, -1.0)

    await console.execute("derecha 1")
    cmd = console.robot.command
    assert (cmd.left_speed, cmd.right_speed) == (-1.0, 1.0)

    await console.execute("parar")
    cmd = console.robot.command
    assert (cmd.left_speed, cmd.right_speed) == (0.0, 0.0)
    assert cmd.to_bytes()[IDX_LEFT_DIR] == 0 and cmd.to_bytes()[IDX_RIGHT_DIR] == 0


async def test_speed_limits():
    console = make_console()
    for bad in ("avanzar 4", "avanzar -9"):
        try:
            await console.execute(bad)
        except ConsoleError:
            continue
        raise AssertionError(f"{bad!r} deberia fallar")


async def test_led_command():
    console = make_console()
    await console.execute("led flash")
    assert console.robot.command.led is Led.FLASH
    assert console.robot.command.to_bytes()[IDX_LED] == 2
    try:
        await console.execute("led rainbow")
    except ConsoleError:
        pass
    else:
        raise AssertionError("'led rainbow' deberia fallar")


async def test_pose_command():
    console = make_console()
    await console.execute("pose right_shoulder 30")
    assert console.robot.command.servos[Joint.RIGHT_SHOULDER] == 30
    # el hombro derecho va al byte 6 (los nombres son los fisicos, los de la guia)
    assert console.robot.command.to_bytes()[IDX_SERVO_1] == encode_servo(
        Joint.RIGHT_SHOULDER, 30
    )


async def test_pose_with_equals_and_aliases():
    console = make_console()
    await console.execute("pose l_arm=10 r_sh=20")
    cmd = console.robot.command
    assert cmd.servos[Joint.LEFT_ARM] == 10
    assert cmd.servos[Joint.RIGHT_SHOULDER] == 20
    assert cmd.to_bytes()[IDX_SERVO_3] == encode_servo(Joint.LEFT_ARM, 10)


async def test_pose_rejects_out_of_range_angles():
    console = make_console()
    try:
        await console.execute("pose right_shoulder 200")
    except ConsoleError:
        pass
    else:
        raise AssertionError("un angulo fuera de rango deberia fallar")


async def test_raw_servo_command():
    console = make_console()
    await console.execute("bruto left_arm 7")
    assert console.robot.command.raw_servos[Joint.LEFT_ARM] == 7
    assert console.robot.command.to_bytes()[IDX_SERVO_3] == 7


async def test_chained_commands():
    console = make_console()
    await console.execute("led on; avanzar 1; pose left_arm 15")
    cmd = console.robot.command
    assert cmd.led is Led.ON
    assert cmd.left_speed == 1.0
    assert cmd.servos[Joint.LEFT_ARM] == 15


async def test_unknown_command_raises():
    console = make_console()
    try:
        await console.execute("bailar")
    except ConsoleError:
        pass
    else:
        raise AssertionError("un comando desconocido deberia fallar")


async def test_joint_aliases():
    assert resolve_joint("l_arm") is Joint.LEFT_ARM
    assert resolve_joint("r_shoulder") is Joint.RIGHT_SHOULDER
    assert resolve_joint("left-arm") is Joint.LEFT_ARM
    assert resolve_joint("LEFT_SHOULDER") is Joint.LEFT_SHOULDER


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            if inspect.iscoroutinefunction(t):
                asyncio.run(t())
            else:
                t()
            print(f"  OK   {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
