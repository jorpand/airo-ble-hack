"""
Tests de la duracion estimada (`POST /api/duracion`).

La interfaz la pregunta antes de darle a "Vamos" para que el niño sepa si va
a esperar medio segundo o un minuto. Aqui se comprueba que:

  - el endpoint funciona sin robot (simula el programa),
  - el detalle por bloque suma el total,
  - los "repetir" multiplican,
  - la simulacion tiene en cuenta donde estaban los brazos (el segundo brazo
    tarda menos si el primero ya los ha movido).

Ejecutar: python3 -m pytest tests/test_duracion.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from airo_ble.api.main import app  # noqa: E402
from airo_ble.api.models import Programa  # noqa: E402
from airo_ble.api.service import Traductor  # noqa: E402
from airo_ble.arms import SERVO_VELOCIDAD  # noqa: E402
from airo_ble.protocol import Joint  # noqa: E402


def _programa(bloques: list[dict]) -> Programa:
    return Programa.model_validate({"nombre": "Prueba", "bloques": bloques})


def test_el_endpoint_devuelve_la_duracion_sin_robot() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={"programa": {"nombre": "Prueba", "bloques": [{"tipo": "espera", "segundos": 2}]}},
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["ok"] is True
        assert datos["duracion"] == 2.0
        assert datos["bloques"] == [2.0]


def test_el_detalle_por_bloque_suma_el_total() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Prueba",
                    "bloques": [
                        {"tipo": "espera", "segundos": 2},
                        {"tipo": "luz", "modo": "encendida"},
                        {"tipo": "espera", "segundos": 1},
                    ],
                }
            },
        )
        datos = r.json()
        assert datos["bloques"] == [2.0, 0.4, 1.0]
        assert abs(sum(datos["bloques"]) - datos["duracion"]) < 1e-9


def test_un_programa_vacio_dura_cero() -> None:
    with TestClient(app) as cliente:
        r = cliente.post("/api/duracion", json={"programa": {"nombre": "Vacio", "bloques": []}})
        datos = r.json()
        assert datos["duracion"] == 0.0
        assert datos["bloques"] == []


def test_los_repetir_multiplican_la_duracion() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Repite",
                    "bloques": [
                        {
                            "tipo": "repetir",
                            "veces": 3,
                            "bloques": [{"tipo": "espera", "segundos": 1}],
                        }
                    ],
                }
            },
        )
        datos = r.json()
        assert datos["duracion"] == 3.0


def test_el_brazo_de_golepe_tarda_al_menos_un_segundo() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Brazo",
                    "bloques": [
                        {"tipo": "brazo", "lado": "derecho", "pose": "arriba", "segundos": 0}
                    ],
                }
            },
        )
        # el servo va a su velocidad y hay que esperarle: al menos 1 s
        assert r.json()["duracion"] >= 1.0


def test_el_movimiento_lento_dura_lo_pedido() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Brazo lento",
                    "bloques": [
                        {"tipo": "brazo", "lado": "derecho", "pose": "arriba", "segundos": 4}
                    ],
                }
            },
        )
        assert r.json()["duracion"] == 4.0


def test_la_simulacion_cuenta_donde_estan_los_brazos() -> None:
    """El segundo brazo tarda menos: ya estan donde tenian que estar."""
    programa = _programa(
        [
            {"tipo": "brazo", "lado": "derecho", "pose": "arriba", "segundos": 0},
            {"tipo": "brazo", "lado": "derecho", "pose": "arriba", "segundos": 0},
        ]
    )
    total, detalle = Traductor.duracion_por_bloque(programa)
    assert detalle[0] > detalle[1]
    assert abs(sum(detalle) - total) < 1e-9


def test_la_duracion_del_brazo_depende_del_servo() -> None:
    """Un brazo que tiene que recorrer mucho tarda mas que uno que ya esta."""
    programa = _programa([{"tipo": "brazo", "lado": "derecho", "pose": "arriba", "segundos": 0}])
    # desde el centro el codo tiene que subir hasta 170 grados
    desde_centro, _ = Traductor.duracion_por_bloque(programa)
    # si el codo ya esta arriba, el recorrido es mucho menor
    desde_arriba, _ = Traductor.duracion_por_bloque(
        programa, {Joint.RIGHT_ARM: 170.0}
    )
    assert desde_arriba < desde_centro
    # y nunca menos que la espera minima
    assert desde_arriba >= 1.0
    # el recorrido del codo (170 grados) a 150 grados/segundo son 1,13 s
    assert desde_centro == max(1.0, 170.0 / SERVO_VELOCIDAD)


def test_el_programa_demasiado_largo_avisa() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Largo",
                    "bloques": [
                        {
                            "tipo": "repetir",
                            "veces": 50,
                            "bloques": [
                                {
                                    "tipo": "repetir",
                                    "veces": 50,
                                    "bloques": [
                                        {
                                            "tipo": "repetir",
                                            "veces": 50,
                                            "bloques": [{"tipo": "espera", "segundos": 1}],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["ok"] is False
        assert "pasos" in datos["mensaje"]


def test_los_repetir_anidados_se_multiplican() -> None:
    """Un "repetir" dentro de otro "repetir": 3 x 2 x 1 s = 6 s."""
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Anidado",
                    "bloques": [
                        {
                            "tipo": "repetir",
                            "veces": 3,
                            "bloques": [
                                {
                                    "tipo": "repetir",
                                    "veces": 2,
                                    "bloques": [{"tipo": "espera", "segundos": 1}],
                                }
                            ],
                        }
                    ],
                }
            },
        )
        datos = r.json()
        assert datos["ok"] is True
        assert datos["duracion"] == 6.0
        # 6 esperas + el "parar" del final
        assert datos["pasos"] == 7
