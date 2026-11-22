"""CLI de línea de comandos para probar el Clementoni AIRO.

    python -m airo_ble.commands scan
    python -m airo_ble.commands drive --left 1 --right 1 --seconds 3
    python -m airo_ble.commands pose --right-shoulder 45 --left-arm -20
    python -m airo_ble.commands led flash

Si el paquete esta instalado, tambien se puede usar el comando `airo`:

    airo scan
    airo drive --left 1 --right 1 --seconds 3

Esta es la CLI de "una vez y listo". La consola interactiva (la que tiene
historial, `ayuda` y autocompletado) esta en `airo_ble/console.py`, que se
instala como `airo-console`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .protocol import JOINT_NAMES, Command, Led


async def cmd_scan(args: argparse.Namespace) -> int:
    """Lista los dispositivos BLE visibles.

    Usa el mismo cliente que todo lo demas: si hay un puente configurado
    (`AIRO_BRIDGE_URL`), el escaneo lo hace la placa (que tiene el radio
    cerca del robot); si no, lo hace el portatil con bleak.
    """
    from .bridge import crear_robot

    robot = crear_robot()
    donde = f"con el puente {robot.url}" if robot.url else "desde el portatil"
    print(f"Escaneando {args.timeout:.0f} s {donde}...")
    datos = await robot.escanear(args.timeout)
    dispositivos = datos.get("dispositivos") or []
    if not dispositivos:
        print("No se ha visto ningún dispositivo BLE.")
        return 1
    for dev in dispositivos:
        print(
            f"  {dev.get('mac', '?'):18s}  {dev.get('nombre', ''):22s}"
            f"  rssi={dev.get('rssi', '?')}"
        )
    return 0


async def cmd_drive(args: argparse.Namespace) -> int:
    from .bridge import crear_robot

    async with crear_robot(address=args.address) as robot:
        await robot.drive(left=args.left, right=args.right)
        print(f"Paquete enviado:\n{robot.command.describe()}")
        try:
            await asyncio.sleep(args.seconds)
        finally:
            await robot.stop()
            print("Parado.")
    return 0


async def cmd_pose(args: argparse.Namespace) -> int:
    from .bridge import crear_robot

    async with crear_robot(address=args.address) as robot:
        for name, value in vars(args).items():
            if name in JOINT_NAMES and value is not None:
                robot.command.set_joint(JOINT_NAMES[name], value)
        await robot.send(robot.command)
        print(f"Paquete enviado:\n{robot.command.describe()}")
    return 0


async def cmd_led(args: argparse.Namespace) -> int:
    from .bridge import crear_robot

    async with crear_robot(address=args.address) as robot:
        await robot.led(Led[args.mode.upper()])
        print(f"Paquete enviado:\n{robot.command.describe()}")
    return 0


async def cmd_dump(args: argparse.Namespace) -> int:
    """Muestra el paquete que se enviaría, sin necesidad de robot."""
    command = Command()
    if args.left or args.right:
        command.left_speed = args.left
        command.right_speed = args.right
    if args.led:
        command.led = Led[args.led.upper()]
    for name in JOINT_NAMES:
        value = getattr(args, name, None)
        if value is not None:
            command.set_joint(JOINT_NAMES[name], value)
    print(command.describe())
    return 0


async def cmd_console(args: argparse.Namespace) -> int:
    """Consola interactiva (atajo a `python -m airo_ble.console`)."""
    from .console import run_console

    return await run_console(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="airo_ble", description="Clementoni AIRO por BLE")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="lista los dispositivos BLE visibles")
    p.add_argument("--timeout", type=float, default=10.0)
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("drive", help="mueve las ruedas")
    p.add_argument("--left", type=float, default=0.0)
    p.add_argument("--right", type=float, default=0.0)
    p.add_argument("--seconds", type=float, default=2.0)
    p.add_argument("--address", default=None)
    p.set_defaults(func=cmd_drive)

    p = sub.add_parser("pose", help="mueve las articulaciones")
    for name in JOINT_NAMES:
        p.add_argument(f"--{name.replace('_', '-')}", type=float, default=None)
    p.add_argument("--address", default=None)
    p.set_defaults(func=cmd_pose)

    p = sub.add_parser("led", help="controla el LED azul")
    p.add_argument("mode", choices=[m.name.lower() for m in Led])
    p.add_argument("--address", default=None)
    p.set_defaults(func=cmd_led)

    p = sub.add_parser("dump", help="muestra el paquete sin conectar (offline)")
    p.add_argument("--left", type=float, default=0.0)
    p.add_argument("--right", type=float, default=0.0)
    p.add_argument("--led", choices=[m.name.lower() for m in Led], default=None)
    for name in JOINT_NAMES:
        p.add_argument(f"--{name.replace('_', '-')}", type=float, default=None)
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("console", help="consola interactiva de comandos")
    p.add_argument("--address", default=None)
    p.add_argument("--scan-timeout", type=float, default=15.0)
    p.add_argument("--no-connect", action="store_true")
    p.add_argument("--no-keepalive", action="store_true")
    p.add_argument("--watchdog", type=float, default=5.0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--exec", action="append", default=[])
    p.set_defaults(func=cmd_console)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
