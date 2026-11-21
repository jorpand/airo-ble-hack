"""
Tests de la API web (FastAPI + Pydantic), sin robot.

Se usa el cliente de prueba de FastAPI con el servicio sin BLE: lo que se
comprueba es que los bloques se traducen bien a los pasos de la libreria y
que un programa abuse no se traga el servidor.

Ejecutar: python3 -m pytest tests/test_api.py -v
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from airo_ble.api.main import app
from airo_ble.api.models import Programa
from airo_ble.api.service import (
    MAX_PASOS,
    ProgramaDemasiadoLarga,
    Traductor,
)


def test_catalogo_de_bloques() -> None:
    with TestClient(app) as cliente:
        r = cliente.get("/api/bloques")
        assert r.status_code == 200
        bloques = r.json()
        tipos = {b["tipo"] for b in bloques}
        assert {"avanzar", "girar", "brazo", "luz", "kata", "repetir"} <= tipos
        for b in bloques:
            assert b["titulo"] and b["icono"] and b["descripcion"]


def test_estado() -> None:
    with TestClient(app) as cliente:
        r = cliente.get("/api/estado")
        assert r.status_code == 200
        estado = r.json()
        assert "conectado" in estado
        assert "brazos" in estado


def test_traduccion_de_bloques() -> None:
    programa = Programa.model_validate(
        {
            "nombre": "Prueba",
            "bloques": [
                {"id": "1", "tipo": "avanzar", "cuanto": "mucho", "segundos": 2},
                {"id": "2", "tipo": "girar", "hacia": "izquierda", "segundos": 1},
                {"id": "3", "tipo": "luz", "modo": "parpadea"},
                {"id": "4", "tipo": "brazo", "lado": "derecho", "pose": "arriba"},
                {
                    "id": "5",
                    "tipo": "repetir",
                    "veces": 2,
                    "bloques": [{"id": "6", "tipo": "espera", "segundos": 0.5}],
                },
            ],
        }
    )
    pasos = Traductor.a_pasos(programa)
    # avanzar x2 (mover+parar), girar x2 (mover+parar), luz x1, brazo x1,
    # repetir(2) = 2 esperas, y el parar final del programa = 9
    assert len(pasos) == 9
    assert pasos[0].kind == "mover"
    assert pasos[0].params["izquierda"] == 3.0  # "mucho" = 3
    assert pasos[0].duracion == 2
    assert pasos[1].kind == "parar"
    assert pasos[2].params["izquierda"] == 2.0
    assert pasos[2].params["derecha"] == -2.0
    assert pasos[4].kind == "luz"
    assert pasos[4].params["modo"] == "flash"
    # el orden real es: mover, parar, mover, parar, luz, brazo, espera, espera, parar
    assert pasos[5].kind == "brazo"
    assert pasos[5].params["lado"] == "derecho"
    assert pasos[6].kind == "espera"
    assert pasos[7].kind == "espera"
    assert pasos[-1].kind == "parar", "el programa siempre termina parando"


def test_cada_movimiento_termina_parando() -> None:
    """Sin esto el robot se queda andando durante los bloques siguientes."""
    programa = Programa.model_validate(
        {
            "nombre": "Prueba",
            "bloques": [{"id": "1", "tipo": "avanzar", "segundos": 2}],
        }
    )
    pasos = Traductor.a_pasos(programa)
    assert [p.kind for p in pasos] == ["mover", "parar", "parar"]


def test_programa_se_acepta() -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/programa",
            json={
                "programa": {
                    "nombre": "Mini",
                    "bloques": [{"id": "1", "tipo": "luz", "modo": "encendida"}],
                }
            },
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_bloque_desconocido_da_error() -> None:
    with TestClient(app) as cliente:
        r = cliente.post("/api/programa", json={"programa": {"bloques": [{"tipo": "nada"}]}})
        assert r.status_code == 422  # validacion de pydantic


# ---------------------------------------------------------------------------
# El tope de pasos: los "repetir" se pueden anidar y se expanden aqui
# ---------------------------------------------------------------------------


def _programa_anidado(veces: int = 50) -> Programa:
    """Tres niveles de 'repetir' anidados."""
    return Programa.model_validate(
        {
            "nombre": "Explosion",
            "bloques": [
                {
                    "id": "1",
                    "tipo": "repetir",
                    "veces": veces,
                    "bloques": [
                        {
                            "id": "2",
                            "tipo": "repetir",
                            "veces": veces,
                            "bloques": [
                                {
                                    "id": "3",
                                    "tipo": "repetir",
                                    "veces": veces,
                                    "bloques": [
                                        {"id": "4", "tipo": "avanzar", "segundos": 1}
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def test_los_repetir_anidados_no_explotan() -> None:
    """Tres 'repetir 50' serian 125.000 pasos: tienen que cortarse.

    Sin el tope, una sola peticion HTTP pedia al robot que condujera
    unas 35 horas.
    """
    with pytest.raises(ProgramaDemasiadoLarga):
        Traductor.a_pasos(_programa_anidado())


def test_el_tope_corta_antes_de_construir_todos_los_pasos() -> None:
    """El corte tiene que ser rapido: no vale construir 125.000 pasos."""
    import time

    t0 = time.time()
    with pytest.raises(ProgramaDemasiadoLarga):
        Traductor.a_pasos(_programa_anidado())
    assert time.time() - t0 < 1.0


def test_el_error_dice_cuanto_pasa() -> None:
    with pytest.raises(ProgramaDemasiadoLarga) as exc:
        Traductor.a_pasos(_programa_anidado())
    assert str(MAX_PASOS) in str(exc.value)


def test_un_programa_normal_no_pasa_el_tope() -> None:
    programa = Programa.model_validate(
        {
            "nombre": "Normal",
            "bloques": [
                {"id": "1", "tipo": "avanzar", "segundos": 2},
                {
                    "id": "2",
                    "tipo": "repetir",
                    "veces": 3,
                    "bloques": [{"id": "3", "tipo": "espera", "segundos": 0.5}],
                },
            ],
        }
    )
    assert len(Traductor.a_pasos(programa)) == 6


def test_la_api_devuelve_el_error_del_tope() -> None:
    """La API tiene que contestar con un error claro, no con un 500."""
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/programa",
            json={"programa": _programa_anidado().model_dump()},
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["ok"] is False
        assert "pasos" in datos["mensaje"]


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallidos = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
        except AssertionError as exc:
            fallidos += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - fallidos}/{len(tests)} tests OK")
    return 1 if fallidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
