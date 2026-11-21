"""
Tests del guardado (programas y funciones) y de las llamadas a funciones.

Lo que se comprueba:

  - el archivo JSON se escribe, se lee y se borra bien (en un temporal, para
    no tocar el archivo de verdad),
  - una llamada a una funcion **se despliega** al traducir el programa,
  - una llamada a una funcion que no existe avisa en vez de reventar,
  - una funcion que se llama a si misma se corta (guard anti-bucle),
  - la duracion de un programa con llamadas tiene en cuenta lo que dura la
    funcion llamada.

Ejecutar: python3 -m pytest tests/test_guardado.py -v
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from airo_ble.api import guardado as almacen
from airo_ble.api.main import app
from airo_ble.api.models import Funcion, Programa
from airo_ble.api.service import (
    FuncionDesconocida,
    MAX_PROFUNDIDAD_FUNCIONES,
    Traductor,
)


@pytest.fixture()
def archivo(monkeypatch, tmp_path):
    """Apunta el guardado a un archivo temporal."""
    ruta = tmp_path / "guardado.json"
    monkeypatch.setenv("AIRO_GUARDADO", str(ruta))
    return ruta


# --- el archivo -------------------------------------------------------------


def test_se_guarda_un_programa_y_se_uelve_a_leer(archivo) -> None:
    almacen.guardar_programa("", "Mi programa", [{"tipo": "luz", "modo": "encendida"}])
    assert archivo.exists()
    datos = almacen.leer()
    assert len(datos["programas"]) == 1
    assert datos["programas"][0]["nombre"] == "Mi programa"
    assert datos["programas"][0]["id"]


def test_guardar_con_el_mismo_id_actualiza(archivo) -> None:
    guardado = almacen.guardar_programa("", "Uno", [])
    guardado = almacen.guardar_programa(guardado["id"], "Dos", [])
    datos = almacen.leer()
    assert len(datos["programas"]) == 1
    assert datos["programas"][0]["nombre"] == "Dos"


def test_se_borra_un_programa(archivo) -> None:
    guardado = almacen.guardar_programa("", "Uno", [])
    assert almacen.borrar_programa(guardado["id"]) is True
    assert almacen.borrar_programa(guardado["id"]) is False
    assert almacen.leer()["programas"] == []


def test_se_guardan_las_funciones(archivo) -> None:
    almacen.guardar_funcion("", "Saludo", [{"tipo": "luz", "modo": "parpadea"}])
    datos = almacen.leer()
    assert len(datos["funciones"]) == 1
    assert datos["funciones"][0]["nombre"] == "Saludo"
    assert almacen.borrar_funcion(datos["funciones"][0]["id"]) is True


def test_un_archivo_roto_no_rompe_nada(archivo) -> None:
    archivo.write_text("{esto no es json", encoding="utf-8")
    assert almacen.leer() == {"programas": [], "funciones": []}
    # y se puede seguir guardando
    almacen.guardar_programa("", "Uno", [])
    assert len(almacen.leer()["programas"]) == 1


# --- las llamadas -----------------------------------------------------------


def _programa_con_llamada(id_funcion: str) -> Programa:
    return Programa.model_validate(
        {
            "nombre": "Con llamada",
            "bloques": [
                {"tipo": "espera", "segundos": 1},
                {"tipo": "llamada", "funcion": id_funcion},
            ],
        }
    )


def _funcion(bloques: list[dict], id_: str = "f1") -> dict[str, Funcion]:
    return {"f1": Funcion.model_validate({"id": id_, "nombre": "Saludo", "bloques": bloques})}


def test_una_llamada_se_despliega_al_traducir() -> None:
    funciones = _funcion([{"tipo": "espera", "segundos": 2}])
    pasos = Traductor.a_pasos(_programa_con_llamada("f1"), funciones)
    esperas = [p for p in pasos if p.kind == "espera"]
    assert len(esperas) == 2
    assert esperas[0].duracion == 1
    assert esperas[1].duracion == 2


def test_una_llamada_a_una_funcion_que_no_existe_avisa() -> None:
    with pytest.raises(FuncionDesconocida) as exc:
        Traductor.a_pasos(_programa_con_llamada("no-existe"), {})
    assert "no-existe" in str(exc.value)


def test_una_funcion_que_se_llama_a_si_misma_se_corta() -> None:
    # "f1" llama a "f1": sin el guard esto seria un bucle infinito
    funciones = _funcion([{"tipo": "llamada", "funcion": "f1"}])
    with pytest.raises(FuncionDesconocida) as exc:
        Traductor.a_pasos(_programa_con_llamada("f1"), funciones)
    assert "sí misma" in str(exc.value)
    # y el limite son 5 niveles
    assert MAX_PROFUNDIDAD_FUNCIONES == 5


def test_la_duracion_de_una_llamada_cuenta_lo_que_dura_la_funcion() -> None:
    funciones = _funcion([{"tipo": "espera", "segundos": 3}])
    total, detalle = Traductor.duracion_por_bloque(
        _programa_con_llamada("f1"), None, funciones
    )
    assert detalle == [1.0, 3.0]
    assert total == 4.0


# --- los endpoints ----------------------------------------------------------


def test_endpoint_de_guardado(archivo) -> None:
    with TestClient(app) as cliente:
        # guardar un programa
        r = cliente.post(
            "/api/guardado/programa",
            json={
                "nombre": "Mi programa",
                "bloques": [{"tipo": "luz", "modo": "encendida"}],
            },
        )
        assert r.status_code == 200
        guardado = r.json()
        assert guardado["nombre"] == "Mi programa"
        assert guardado["id"]

        # guardar una funcion
        r = cliente.post(
            "/api/guardado/funcion",
            json={"nombre": "Saludo", "bloques": [{"tipo": "espera", "segundos": 1}]},
        )
        assert r.status_code == 200
        funcion = r.json()
        assert funcion["nombre"] == "Saludo"

        # listar todo
        r = cliente.get("/api/guardado")
        assert r.status_code == 200
        datos = r.json()
        assert len(datos["programas"]) == 1
        assert len(datos["funciones"]) == 1

        # borrar la funcion
        r = cliente.delete(f"/api/guardado/funcion/{funcion['id']}")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert len(cliente.get("/api/guardado").json()["funciones"]) == 0

        # borrar el programa
        r = cliente.delete(f"/api/guardado/programa/{guardado['id']}")
        assert r.json()["ok"] is True
        assert len(cliente.get("/api/guardado").json()["programas"]) == 0


def test_el_programa_va_con_sus_funciones(archivo) -> None:
    """El backend necesita las funciones para poder desplegar las llamadas."""
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Con llamada",
                    "bloques": [
                        {"tipo": "llamada", "funcion": "f1"},
                        {"tipo": "espera", "segundos": 1},
                    ],
                },
                "funciones": {
                    "f1": {
                        "id": "f1",
                        "nombre": "Saludo",
                        "bloques": [{"tipo": "espera", "segundos": 2}],
                    }
                },
            },
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["ok"] is True
        assert datos["bloques"] == [2.0, 1.0]
        assert datos["duracion"] == 3.0


def test_una_llamada_sin_funcion_no_rompe_el_servidor(archivo) -> None:
    with TestClient(app) as cliente:
        r = cliente.post(
            "/api/duracion",
            json={
                "programa": {
                    "nombre": "Roto",
                    "bloques": [{"tipo": "llamada", "funcion": "no-existe"}],
                }
            },
        )
        assert r.status_code == 200
        datos = r.json()
        assert datos["ok"] is False
        assert "no-existe" in datos["mensaje"]
