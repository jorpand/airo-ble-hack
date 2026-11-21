#!/usr/bin/env python3
"""
Consola interactiva para el Clementoni AIRO.

    python3 airo_console.py                       # busca el robot 'AIRo'
    python3 airo_console.py --address AA:BB:...   # MAC concreta
    python3 airo_console.py --dry-run             # no conecta, solo simula
    python3 airo_console.py --exec "avanzar 2" --exec "parar"

Es un atajo a `python3 -m airo_ble.console`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from airo_ble.console import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
