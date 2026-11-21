"""
Prueba de los "repetir" anidados (un "repetir" dentro de otro "repetir") en
el navegador de verdad: se montan con la interfaz (clics y arrastres) y se
comprueba que la duracion que dice la pantalla es la correcta.

Ejecutar:
    .venv-3.14/bin/python tools/hardware/probar_repetir.py
"""

from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8100"


def main() -> int:
    informe: dict[str, object] = {}

    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        pagina = navegador.new_page(viewport={"width": 1440, "height": 1400})
        pagina.goto(URL, wait_until="networkidle")

        # --- un "repetir" de 3 veces en el programa
        pagina.locator(".bloque-paleta").filter(has_text="Repite").click()
        pagina.wait_for_timeout(300)
        repetir = pagina.locator(".programa-lista > .bloque").first
        # poner "3 veces"
        repetir.locator(".chips .chip").filter(has_text="3").first.click()
        pagina.wait_for_timeout(300)

        # --- dentro, un "repetir" de 2 veces (con la mini paleta)
        repetir.locator(".mini-bloque[title='Repite']").click()
        pagina.wait_for_timeout(400)
        interior = pagina.locator(".dentro > .bloque").first
        interior.locator(".chips .chip").filter(has_text="2").first.click()
        pagina.wait_for_timeout(300)

        # --- y dentro de ese, una "Espera" de 1 segundo
        interior.locator(".mini-bloque[title='Espera']").click()
        pagina.wait_for_timeout(700)

        informe["estructura"] = {
            "repetir": pagina.locator(".programa-lista > .bloque").count(),
            "dentro_del_repetir": pagina.locator(".dentro > .bloque").count(),
            "dentro_del_repetir_de_dentro": pagina.locator(".dentro .dentro > .bloque").count(),
        }
        pagina.screenshot(path="evidencia/interfaz/despues_repetir_anidado.png")
        informe["duracion_en_pantalla"] = pagina.locator(".duracion").inner_text()

        # --- la duracion correcta: 3 x 2 x 1 s = 6 s
        # el tiempo de la "Espera" se pone con el deslizador (con el teclado,
        # que es como se mueve un range input)
        espera = pagina.locator(".dentro .dentro .bloque").first
        informe["tiempo_inicial"] = espera.locator(".opcion-etiqueta").inner_text()
        espera.locator("input.deslizador").focus()
        espera.locator("input.deslizador").press("ArrowRight")
        espera.locator("input.deslizador").press("ArrowRight")
        pagina.wait_for_timeout(900)
        informe["duracion_con_espera_de_3s"] = pagina.locator(".duracion").inner_text()

        # --- y ahora una de 8 segundos: 3 x 2 x 8 = 48 s
        for _ in range(3):
            espera.locator("input.deslizador").press("ArrowRight")
        pagina.wait_for_timeout(900)
        informe["duracion_con_espera_de_8s"] = pagina.locator(".duracion").inner_text()

        # --- mover un bloque del repetir de dentro a la raiz (por el asa)
        zona_raiz = pagina.locator(".programa-lista > .zona-soltar").last
        pagina.locator(".dentro .dentro .bloque .agarre").first.drag_to(zona_raiz)
        pagina.wait_for_timeout(600)
        informe["tras_mover"] = {
            "raiz": pagina.locator(".programa-lista > .bloque").count(),
            "dentro": pagina.locator(".dentro > .bloque").count(),
            "dentro_del_dentro": pagina.locator(".dentro .dentro > .bloque").count(),
        }
        pagina.wait_for_timeout(800)
        informe["duracion_tras_mover"] = pagina.locator(".duracion").inner_text()

        navegador.close()

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
