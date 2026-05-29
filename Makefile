PYTHON ?= python3
COMPOSE ?= docker compose
REDIS_TEST_URL ?= redis://localhost:6379/1

.PHONY: setup up down logs test test-unit test-integration load load-baseline load-burst

setup:
	$(PYTHON) -m pip install ".[dev]"

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f api-1 api-2 nginx redis

test-unit:
	PYTHONPATH=. pytest tests/unit -q

test-integration:
	PYTHONPATH=. REDIS_URL=$(REDIS_TEST_URL) pytest tests/integration -m integration -q

test: test-unit test-integration

test-all: up
	@echo "Waiting for Redis..."
	@sleep 3
	$(MAKE) test-integration
	$(MAKE) test-unit

run-api:
	REDIS_URL=redis://localhost:6379/0 uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

load-baseline:
	k6 run load/scenarios/baseline.js

load-burst:
	k6 run load/scenarios/burst.js

load:
	$(MAKE) load-baseline
