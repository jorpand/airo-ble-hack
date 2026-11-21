"""
Prueba de punta a punta del guardado (programas y funciones) con el
navegador de verdad: marcar bloques, guardarlos como funcion, usarla,
editarla y comprobar que el programa guardado sobrevive a recargar la
pagina.

Ejecutar:
    .venv-3.14/bin/python tools/hardware/probar_guardado.py
"""

from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8100"


def main() -> int:
    informe: dict[str, object] = {}

    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        pagina = navegador.new_page(viewport={"width": 1680, "height": 1100})
        pagina.goto(URL, wait_until="networkidle")

        # --- 1) un programa de ejemplo
        pagina.get_by_role("button", name="Ejemplo").click()
        pagina.wait_for_timeout(700)
        bloques = pagina.locator(".programa-lista > .bloque")
        informe["bloques_del_ejemplo"] = bloques.count()

        # --- 2) marcar los tres primeros (clic y Mayusculas)
        cabeceras = pagina.locator(".programa-lista > .bloque .bloque-cabecera")
        cabeceras.nth(0).click()
        cabeceras.nth(2).click(modifiers=["Shift"])
        pagina.wait_for_timeout(300)
        marcados = pagina.locator(".bloque-seleccionado").count()
        informe["marcados"] = marcados

        # --- 3) guardarlo como funcion
        pagina.get_by_label("Nombre de la función").fill("Saludo")
        pagina.get_by_role("button", name="Guardar como función").click()
        pagina.wait_for_timeout(700)
        informe["funciones_en_la_lista"] = pagina.locator(".lista-guardados li").count()
        nombres = pagina.locator(".guardado-seccion").nth(1).locator(".guardado-nombre")
        informe["nombre_de_la_funcion"] = nombres.first.inner_text()

        # --- 4) usarla en el programa (una llamada)
        pagina.get_by_role("button", name="Usar").first.click()
        pagina.wait_for_timeout(900)
        llamadas = pagina.locator(".programa-lista > .bloque .bloque-titulo")
        informe["llamadas_en_el_programa"] = [
            t for t in llamadas.all_inner_texts() if "Saludo" in t
        ]
        informe["resumen"] = pagina.locator(".resumen p").inner_text()

        # --- 5) editarla: anadir un bloque mas a la funcion
        pagina.get_by_role("button", name="Editar").first.click()
        pagina.wait_for_timeout(500)
        informe["editando"] = pagina.locator(".programa-cabecera h2").inner_text()
        pagina.locator(".bloque-paleta").filter(has_text="Luz").first.click()
        pagina.wait_for_timeout(700)
        pagina.get_by_role("button", name="Guardar función").click()
        pagina.wait_for_timeout(700)

        # --- 6) guardar el programa completo
        pagina.get_by_label("Nombre del programa").fill("Mi programa bueno")
        pagina.get_by_role("button", name="💾 Guardar").click()
        pagina.wait_for_timeout(700)
        programas = pagina.locator(".guardado-seccion").nth(0).locator(".guardado-nombre")
        informe["programas_guardados"] = programas.all_inner_texts()

        # --- 7) recargar: sigue todo ahi (se guarda en el servidor)
        pagina.reload(wait_until="networkidle")
        pagina.wait_for_timeout(800)
        programas = pagina.locator(".guardado-seccion").nth(0).locator(".guardado-nombre")
        funciones = pagina.locator(".guardado-seccion").nth(1).locator(".guardado-nombre")
        informe["tras_recargar"] = {
            "programas": programas.all_inner_texts(),
            "funciones": funciones.all_inner_texts(),
        }

        # --- 8) cargar el programa guardado
        pagina.get_by_role("button", name="Cargar").first.click()
        pagina.wait_for_timeout(900)
        informe["bloques_al_cargar"] = pagina.locator(".programa-lista > .bloque").count()
        pagina.screenshot(path="evidencia/interfaz/despues_escritorio_guardado.png")

        navegador.close()

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
