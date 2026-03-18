PYTHON ?= python3
VENV_DIR ?= .venv
VENV_BIN := $(VENV_DIR)/bin
VENV_PYTHON := $(VENV_BIN)/python
APP_PORT ?= 8000

.PHONY: help venv api frontend dev env

help:
	@echo "Available targets:"
	@echo "  make venv     - create virtualenv and install backend requirements"
	@echo "  make api      - run FastAPI backend with uvicorn (reload)"
	@echo "  make frontend - start frontend dev server (Vite) in meterface/"
	@echo "  make dev      - run backend and frontend together for local dev"

venv:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_BIN)/pip install -r requirements.txt

api:
	@echo "Using APP_PORT=$(APP_PORT)"
	$(VENV_PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $(APP_PORT) --reload

frontend:
	cd meterface && npm install && npm run dev

dev:
	@echo "Using APP_PORT=$(APP_PORT)"
	$(VENV_PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $(APP_PORT) --reload &
	cd meterface && npm install && npm run dev

env:
	@if [ ! -f .env ] && [ -f .env.example ]; then \
	  cp .env.example .env; \
	  echo "Created .env from .env.example; please edit it."; \
	fi
