#!/usr/bin/env python3
"""
Puente para Scratch (atajo a `python3 -m airo_ble.server`).

    python3 airo_server.py                       # http://localhost:8765
    python3 airo_server.py --address AA:BB:...   # MAC concreta
    python3 airo_server.py --no-connect          # arranca sin buscar el robot

El codigo vive en `airo_ble/server.py` para que se instale con el paquete.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from airo_ble.server import main  # noqa: E402

if __name__ == "__main__":
    main()
