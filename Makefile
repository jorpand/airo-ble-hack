# Atajos del proyecto. `make help` a ver la lista.
#
# El repositorio tiene dos partes (Python y la web de React), asi que los
# comandos estaban repetidos en el README, en CONTRIBUTING y en la CI. Aqui
# estan todos en un sitio.

PYTHON  ?= python3
VENV    ?= .venv
VPY     := $(VENV)/bin/python
VPIP    := $(VENV)/bin/pip
NPM     ?= npm

#: El puerto de la API web. El proxy de Vite apunta aqui.
PORT    ?= 8100

.DEFAULT_GOAL := help
.PHONY: help install test test-py test-web lint web web-dev web-gen run console scratch clean

help: ## Muestra esta ayuda
	@echo "AIRO — atajos del proyecto:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: PORT=$(PORT) VENV=$(VENV)"

install: ## Crea el venv e instala la libreria con los extras de desarrollo
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VPIP) install --upgrade pip
	$(VPIP) install -e ".[dev]"
	cd web && $(NPM) ci

test: test-py test-web ## Pasa toda la suite (Python + web)

test-py: ## Pasa los tests de Python
	$(VPY) -m pytest -q

test-web: ## Pasa los tests de la interfaz
	cd web && $(NPM) test

lint: ## Ruff + los hooks de pre-commit
	$(VPY) -m ruff check --select=E9,F63,F7,F82 .
	$(VPY) -m pre_commit run --all-files

web: ## Compila la interfaz (npm ci + npm run build)
	cd web && $(NPM) ci && $(NPM) run build

web-dev: ## Arranca Vite en el 5173, para tocar la interfaz
	cd web && $(NPM) run dev

web-gen: ## Regenera web/src/servos.js desde airo_ble/protocol.py
	$(VPY) tools/gen_servos.py

run: ## Arranca la API web con la interfaz
	$(VPY) -m uvicorn airo_ble.api.main:app --port $(PORT)

console: ## Arranca la consola interactiva
	$(VPY) -m airo_ble.console

scratch: ## Arranca el puente para el plugin de Scratch
	$(VPY) -m airo_ble.server

clean: ## Borra las caches y la build de la web
	find . -name "__pycache__" -type d -not -path "./.venv/*" -not -path "./web/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache web/dist
