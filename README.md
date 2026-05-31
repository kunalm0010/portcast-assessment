# Distributed Rate Limiter

Distributed per-client, per-route rate limiting for a horizontally scaled API. Full design rationale is in [`DESIGN.md`](DESIGN.md).

## Quick start (one command)

```bash
docker compose up --build
```

| Endpoint | URL |
|----------|-----|
| Load-balanced API | http://localhost:8080 |
| Health | http://localhost:8080/health |

Example request:

```bash
curl -s -H "X-Client-Id: client-free-1" http://localhost:8080/v1/demo -v
```
See more routes and clients in the /configs directory yaml files

## Libraries and why they were chosen

| Library | Role |
|---------|------|
| **FastAPI** | HTTP API and middleware hook for rate limiting on every request |
| **Uvicorn** | ASGI server for local and container runs |
| **redis-py** | Connection pool and Lua `EVAL` against Redis primary |
| **PyYAML** | Load tier, route, and client limits from config files |
| **Pydantic** | Used by FastAPI for request/response typing |
| **pytest** + **httpx** | Unit and integration tests (httpx via Starlette `TestClient`) |

No ORM or SQL database: limits are enforced in Redis on the hot path.

See [`DESIGN.md`](DESIGN.md) for architecture, failure semantics, and load-test plan.

## Code map (where to look)

| Path | Purpose |
|------|---------|
| [`app/main.py`](app/main.py) | FastAPI app, routes, wires middleware |
| [`app/middleware.py`](app/middleware.py) | Rate limit middleware → 400 / 429 / 503 |
| [`rate_limiter/limiter.py`](rate_limiter/limiter.py) | Orchestrates config + Redis + circuit breaker |
| [`rate_limiter/redis_store.py`](rate_limiter/redis_store.py) | Redis pool and token-bucket Lua script |
| [`rate_limiter/lua/token_bucket.lua`](rate_limiter/lua/token_bucket.lua) | Atomic token bucket in Redis |
| [`rate_limiter/circuit.py`](rate_limiter/circuit.py) | Fail-closed circuit breaker (per process) |
| [`rate_limiter/config.py`](rate_limiter/config.py) | YAML config load and policy resolution |
| [`rate_limiter/factory.py`](rate_limiter/factory.py) | Build limiter from environment variables |
| [`configs/limits.yaml`](configs/limits.yaml) | Tier and route limits |
| [`configs/clients.yaml`](configs/clients.yaml) | Client → tier and per-client overrides |
| [`nginx/nginx.conf`](nginx/nginx.conf) | Load balancer across `api-1` and `api-2` |
| [`docker-compose.yml`](docker-compose.yml) | Redis, replica, two APIs, nginx |
| [`tests/unit/`](tests/unit/) | Circuit breaker, config resolution |
| [`tests/integration/`](tests/integration/) | Redis, cross-instance, fail-closed, middleware |
| [`load/scenarios/`](load/scenarios/) | k6 load scripts (baseline, burst, cross_instance, concurrent, hot_routes, peak) |
| [`load/common.js`](load/common.js) | Shared clients/routes aligned with configs |

## Common commands

```bash
# Install dependencies (Python 3.11+ recommended)
make setup
# or: pip install ".[dev]"

# Start full stack
make up

# Tests (unit always; integration needs Redis on localhost:6379/1)
make test-unit
docker compose up -d redis
make test-integration

# Logs
make logs

# Tear down
make down

# Load tests (requires k6: https://grafana.com/docs/k6/latest/set-up/install-k6/)
docker compose up --build -d
make load-baseline      # 200 RPS mixed clients/routes, 30s
make load-burst         # 100 RPS single enterprise client, 2s
make load-cross_instance # 50 RPS via nginx; proves global quota
make load-concurrent    # 30 VUs, multiple clients/routes
make load-hot_routes    # 150 RPS, 80% on top 5 routes
make load-peak          # ramp 100→300→600 RPS
make load-all           # run every scenario

# Or via script (writes load/results/<scenario>.json):
./scripts/run_load.sh baseline
BASE_URL=http://localhost:8080 ./scripts/run_load.sh peak
```

See [`DESIGN.md` §6](DESIGN.md#6-load-test-results--bottlenecks) for scenario descriptions and measured results.
```

## Environment variables

Copy [`.env.example`](.env.example). Important variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis primary |
| `CONFIG_DIR` | `./configs` | Directory with `limits.yaml` and `clients.yaml` |
| `REDIS_TIMEOUT_MS` | `5` (50 in Docker) | Redis socket timeout |
| `INSTANCE_NAME` | `local` | Shown on `/health` |

## Repository layout

```text
app/                 # FastAPI app + middleware
rate_limiter/        # Core limiter package + Lua script
configs/             # limits.yaml, clients.yaml
nginx/               # Load balancer config
tests/unit/          # No Redis required
tests/integration/   # Requires Redis
load/scenarios/      # k6 scripts
DESIGN.md            # Design document
```
