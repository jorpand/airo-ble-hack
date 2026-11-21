"""
Capturas de la interfaz web del robot AIRO (despues de las mejoras) y
comprobacion de que arrastrar, deshacer y el ejemplo funcionan de verdad.

Se usa Playwright con el Chromium de ~/.cache/ms-playwright.

Ejecutar:
    .venv-3.14/bin/python tools/hardware/capturar_interfaz.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "evidencia" / "interfaz"
URL = "http://127.0.0.1:8100"

#: Los tres tamaños que se miran: escritorio, tablet y movil.
TAMANOS = {
    "escritorio": (1440, 1050),
    "tablet": (820, 1180),
    "movil": (390, 844),
}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    informe: dict[str, object] = {}

    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        for nombre, (ancho, alto) in TAMANOS.items():
            pagina = navegador.new_page(viewport={"width": ancho, "height": alto})
            pagina.goto(URL, wait_until="networkidle")

            # 1) la pagina recien abierta
            pagina.screenshot(path=str(DESTINO / f"despues_{nombre}.png"))

            # 2) con el programa de ejemplo cargado (boton "Ejemplo")
            pagina.get_by_role("button", name="Ejemplo").click()
            pagina.wait_for_timeout(900)
            pagina.screenshot(path=str(DESTINO / f"despues_{nombre}_ejemplo.png"))

            if nombre == "escritorio":
                # 3) el boton de deshacer funciona
                antes = pagina.locator(".bloque").count()
                pagina.get_by_role("button", name="Deshacer").click()
                pagina.wait_for_timeout(300)
                despues = pagina.locator(".bloque").count()
                informe["deshacer"] = {"antes": antes, "despues": despues}

                # y se vuelve a hacer con Ctrl+Z
                pagina.keyboard.press("Control+z")
                pagina.wait_for_timeout(300)
                informe["ctrl_z"] = {"bloques": pagina.locator(".bloque").count()}

                # 4) arrastrar un bloque de la paleta al programa
                pagina.get_by_role("button", name="Ejemplo").click()
                pagina.wait_for_timeout(500)
                antes = pagina.locator(".bloque").count()
                origen = pagina.locator(".bloque-paleta").first
                destino = pagina.locator(".programa-lista > .zona-soltar").first
                origen.drag_to(destino)
                pagina.wait_for_timeout(400)
                despues = pagina.locator(".bloque").count()
                informe["arrastrar"] = {"antes": antes, "despues": despues}
                pagina.screenshot(path=str(DESTINO / "despues_escritorio_arrastre.png"))

                # 4b) arrastrar un bloque que ya esta en el programa (reordenar)
                titulos = pagina.locator(".programa-lista > .bloque .bloque-titulo")
                orden_antes = titulos.all_inner_texts()
                pagina.locator(".programa-lista > .bloque").first.locator(".agarre").drag_to(
                    pagina.locator(".programa-lista > .zona-soltar").nth(1)
                )
                pagina.wait_for_timeout(400)
                orden_despues = pagina.locator(
                    ".programa-lista > .bloque .bloque-titulo"
                ).all_inner_texts()
                informe["reordenar"] = {"antes": orden_antes, "despues": orden_despues}

                # 4c) arrastrar un bloque DENTRO de un "repetir" (en una pagina
                #     alta, para que la paleta y el "repetir" esten a la vez)
                pagina_alta = navegador.new_page(viewport={"width": 1440, "height": 2400})
                pagina_alta.goto(URL, wait_until="networkidle")
                pagina_alta.get_by_role("button", name="Ejemplo").click()
                pagina_alta.wait_for_timeout(600)
                dentro_antes = pagina_alta.locator(".dentro > .bloque").count()
                pagina_alta.locator(".bloque-paleta").first.drag_to(
                    pagina_alta.locator(".dentro > .zona-soltar").first
                )
                pagina_alta.wait_for_timeout(400)
                dentro_despues = pagina_alta.locator(".dentro > .bloque").count()
                informe["arrastrar_dentro_de_repetir"] = {
                    "antes": dentro_antes,
                    "despues": dentro_despues,
                }
                pagina_alta.close()

                # 5) el boton de ejecutar esta ahi y la duracion se ve
                informe["duracion"] = pagina.locator(".duracion").inner_text()
                informe["botones"] = pagina.locator(".programa-botones .boton").count()
                informe["asa_de_arrastrar"] = pagina.locator(".agarre").count()
                informe["zonas_de_soltar"] = pagina.locator(".zona-soltar").count()

                # 6) el texto de la cabecera cabe en la pantalla
                caja = pagina.locator(".cabecera").bounding_box()
                informe["cabecera"] = caja

            pagina.close()
        navegador.close()

    print(json.dumps(informe, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
