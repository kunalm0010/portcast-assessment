PYTHON ?= python3
COMPOSE ?= docker compose
REDIS_TEST_URL ?= redis://localhost:6379/1
BASE_URL ?= http://localhost:8080

.PHONY: setup up down logs test test-unit test-integration load load-all \
	load-baseline load-burst load-cross_instance load-concurrent load-hot_routes load-peak

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
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh baseline

load-burst:
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh burst

load-cross_instance:
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh cross_instance

load-concurrent:
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh concurrent

load-hot_routes:
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh hot_routes

load-peak:
	BASE_URL=$(BASE_URL) ./scripts/run_load.sh peak

load-all: load-baseline load-burst load-cross_instance load-concurrent load-hot_routes load-peak

load:
	$(MAKE) load-baseline
