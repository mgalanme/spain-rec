.PHONY: setup start start-full stop restart migrate seed ingest recommend test lint clean help

# ── Variables ────────────────────────────────────────────────────────────────
COMPOSE = docker compose -f docker/docker-compose.yml
VENV    = .venv-langchain
PYTHON  = $(shell [ -f $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo $(VENV)/Scripts/python)
UV      = uv

help:
	@echo ""
	@echo "Spain-Rec — available targets:"
	@echo ""
	@echo "  setup        Create virtual environments and install dependencies"
	@echo "  start        Start core infrastructure (kafka, neo4j, postgres, qdrant)"
	@echo "  start-full   Start full stack (adds n8n, redis)"
	@echo "  stop         Stop all services"
	@echo "  restart      Stop and start core profile"
	@echo "  migrate      Run Alembic migrations against PostgreSQL"
	@echo "  seed         Run synthetic data generator"
	@echo "  ingest       Run Kafka consumers to populate graph and vector store"
	@echo "  recommend    Trigger a sample recommendation cycle"
	@echo "  test         Run pytest suite"
	@echo "  lint         Run ruff linter"
	@echo "  clean        Stop containers and remove volumes (destructive)"
	@echo ""

setup:
	$(UV) venv $(VENV) --clear
	UV_PROJECT_ENVIRONMENT=$(VENV) $(UV) sync --extra dev
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env created from .env.example"; fi
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

start:
	$(COMPOSE) --profile core up -d
	@echo "Core services starting. Check status with: docker compose -f docker/docker-compose.yml ps"

start-full:
	$(COMPOSE) --profile full up -d
	@echo "Full stack starting (includes n8n and redis)."

stop:
	$(COMPOSE) --profile full down

restart: stop start

migrate:
	$(PYTHON) -m alembic -c src/db/alembic.ini upgrade head

seed:
	$(PYTHON) data/generator/generate.py

ingest:
	$(PYTHON) src/pipeline/consumer.py

recommend:
	$(PYTHON) src/agents/run.py

test:
	$(VENV)/bin/pytest tests/ -v

lint:
	$(VENV)/bin/ruff check src/ tests/

clean:
	$(COMPOSE) --profile full down --volumes --remove-orphans
	@echo "All containers and volumes removed."
