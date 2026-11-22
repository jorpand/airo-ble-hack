"""Coherencia del firmware del ESP32-S3.

Estas comprobaciones son de las que se olvidan y luego duelen: el firmware
corre en la placa, no en la CI, asi que si algo se descuadra (una version de
MicroPython que no es la de la placa, un modulo de MicroPython sin stub) no
lo ve nadie hasta que se rompe en la placa.

- La version de MicroPython tiene que ser la misma en `mip.json`, en
  `mise.toml` y en el README del firmware.
- Todo modulo de MicroPython que importe el firmware tiene que tener su stub
  (para que pyright pueda mirarlo).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIRMWARE = RAIZ / "firmware" / "esp32"
STUBS = RAIZ / "firmware" / "stubs"

#: Los modulos que son de la placa y no existen en CPython.
DE_MICROPYTHON = {"bluetooth", "network", "machine", "neopixel"}


def _version_del_firmware() -> str:
    """La version de MicroPython del binario de `mise.toml` (1.29.0)."""
    mise = (RAIZ / "mise.toml").read_text(encoding="utf-8")
    coax = re.search(r"ESP32_GENERIC_S3-SPIRAM_OCT-v([0-9.]+)\.bin", mise)
    assert coax, "no se encuentra el firmware en mise.toml"
    return coax.group(1)


def test_la_version_de_micropython_es_la_misma_en_todos_los_ficheros() -> None:
    """`mip.json`, `mise.toml` y el README tienen que hablar de la misma."""
    version = _version_del_firmware()

    mip = json.loads((FIRMWARE / "mip.json").read_text(encoding="utf-8"))
    requiere = " ".join(mip.get("requires", []))
    assert f"micropython>={version}" in requiere, requiere

    readme = (FIRMWARE / "README.md").read_text(encoding="utf-8")
    assert f"v{version}.bin" in readme, "el README menciona otra version"
    assert f"-v{version}.bin" in readme, "el README menciona otra version"


def test_los_ficheros_del_firmware_no_tienen_tildes() -> None:
    """MicroPython va con UTF-8, pero el ASCII es mas seguro en la placa.

    Los ficheros del firmware se han escrito siempre sin tildes (el codigo en
    UTF-8 se ve raro en la consola de la placa y no gana nada).
    """
    for fichero in sorted(FIRMWARE.glob("*.py")):
        fuente = fichero.read_text(encoding="utf-8")
        sin_acentos = fuente.encode("ascii", "ignore").decode("ascii")
        if sin_acentos != fuente:
            # Solo avisa de los caracteres que no son ASCII (tildes, eñes...).
            raros = {c for c in fuente if ord(c) > 127}
            raise AssertionError(
                f"{fichero.name} tiene caracteres no ASCII: {sorted(raros)}"
            )


def test_todo_modulo_de_micropython_tiene_su_stub() -> None:
    """Los modulos de la placa necesitan stub, o pyright no los ve."""
    sin_stub = []
    for fichero in sorted(FIRMWARE.glob("*.py")):
        fuente = fichero.read_text(encoding="utf-8")
        for linea in fuente.splitlines():
            coincidencia = re.match(r"\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", linea)
            if not coincidencia:
                continue
            modulo = coincidencia.group(1).split(".")[0]
            if modulo in sys.stdlib_module_names:
                continue
            # Los modulos del propio firmware (wifi, puente, ble_robot...)
            if (FIRMWARE / f"{modulo}.py").exists():
                continue
            if not (STUBS / f"{modulo}.pyi").exists():
                sin_stub.append(f"{fichero.name}: {modulo}")
    assert not sin_stub, f"modulos sin stub: {sin_stub}"


def test_los_stubs_cubren_los_modulos_de_la_placa() -> None:
    """Los stubs que existen tienen que estar al día con lo que se usa."""
    assert (STUBS / "bluetooth.pyi").exists()
    assert (STUBS / "network.pyi").exists()
    assert (STUBS / "machine.pyi").exists()
    assert (STUBS / "neopixel.pyi").exists()
    for modulo in sorted(DE_MICROPYTHON):
        assert (STUBS / f"{modulo}.pyi").exists(), modulo
    stub_bluetooth = (STUBS / "bluetooth.pyi").read_text(encoding="utf-8")
    # El firmware usa `gap_scan`, `gap_connect` y las escrituras.
    for metodo in ("gap_scan", "gap_connect", "gattc_write", "gattc_discover_services"):
        assert metodo in stub_bluetooth, metodo
    stub_neopixel = (STUBS / "neopixel.pyi").read_text(encoding="utf-8")
    # El LED usa `NeoPixel`, `fill` y `write`.
    for metodo in ("NeoPixel", "fill", "write"):
        assert metodo in stub_neopixel, metodo
