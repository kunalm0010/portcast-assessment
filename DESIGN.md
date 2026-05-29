# DESIGN.md — Distributed Rate Limiter

## 1. System Architecture Overview

A distributed rate limiter is required for a public API that runs on multiple instances. Limits must apply **per client** and **per route**, and the same quota must hold no matter which instance handles the request.

**Launch scope:** 
~5,000 clients, ~40 routes, ~3,000 requests per second on average, ~15,000 at peak, and bursty traffic (for example ~100 requests in one second, then idle). The limiter must add less than **10 ms** of latency per request. Three client tiers exist: `free`, `standard`, and `enterprise`.

**High-level flow:**

1. A client sends a request with a client identifier (for example `X-Client-Id`).
2. A load balancer sends the request to any API instance.
3. **Middleware** runs before route handlers: it resolves the client tier and route, then checks the limit.
4. A single **Redis** call (Lua script) updates shared token state and returns allow or deny.
5. If allowed, the handler runs. If denied, the API returns **429**. If the limiter cannot run, the API returns **503** (fail-closed; see §4).

**Components:**

| Component | Role |
|-----------|------|
| Load balancer | Distributes traffic across instances; health checks remove failed instances |
| API instances (8 in production, 2 in this repo) | Stateless; middleware enforces limits on every request |
| `rate_limiter` package | Token bucket logic, config loading, Redis access, circuit breaker |
| Redis primary | Shared counter state for all instances |
| Redis replica | Async copy for failover; not used for limit checks at launch |
| Config files (`limits.yaml`, `clients.yaml`) | Tier defaults, route overrides, client → tier mapping |

**Diagram:** *(add architecture diagram here: client → nginx → api-1 / api-2 → middleware → Redis primary)*

**Production vs this repo:** Production uses eight API instances behind a load balancer. This repository uses two instances and nginx to prove that limits are global across instances, without running eight containers locally. The design pattern is the same.

### 1.1 Code map

Evaluators can use this table to navigate the implementation. More detail on libraries is in the [README](../README.md).

| Path | Responsibility |
|------|----------------|
| `app/main.py` | FastAPI application and sample routes |
| `app/middleware.py` | Middleware: client id, route key, 400 / 429 / 503 |
| `rate_limiter/limiter.py` | Single entry `allow(client_id, route)` |
| `rate_limiter/redis_store.py` | Redis pool; runs `lua/token_bucket.lua` |
| `rate_limiter/circuit.py` | Circuit breaker for fail-closed behavior |
| `rate_limiter/config.py` | Loads YAML; resolves tier → route → client override |
| `rate_limiter/factory.py` | Builds limiter from environment variables |
| `configs/limits.yaml` | Tier defaults and route overrides |
| `configs/clients.yaml` | Client tier mapping and optional overrides |
| `nginx/nginx.conf` | Round-robin to `api-1` and `api-2` |
| `docker-compose.yml` | Redis, replica, two APIs, nginx on port 8080 |

### 1.2 How to run

**Full stack (single command):**

```bash
docker compose up --build
```

Then:

```bash
curl -H "X-Client-Id: client-free-1" http://localhost:8080/v1/demo
```

| Service | Port | Notes |
|---------|------|-------|
| nginx (load balancer) | 8080 | Use this for load tests and cross-instance checks |
| Redis primary | 6379 | Shared limit state |
| Redis replica | — | Async replica of primary; app writes to primary only |
| api-1 / api-2 | internal 8000 | Not exposed directly; traffic goes through nginx |

**Tests:**

```bash
pip install ".[dev]"
docker compose up -d redis
REDIS_URL=redis://localhost:6379/1 pytest -q
```

Or: `make test-unit` and `make test-integration` (see README).

**Load tests (k6 installed):**

```bash
docker compose up --build -d
./scripts/run_load.sh baseline
./scripts/run_load.sh burst
./scripts/run_load.sh cross_instance
```

Set `BASE_URL` if needed (default `http://localhost:8080`).

---

## 2. Integration Shape & Strategy

Rate limiting is applied in **middleware** that runs on every request before business logic. A small shared Python package (`rate_limiter`) holds the core logic; middleware calls into it. The package is not exposed as a separate network service.

### Chosen approach

| Piece | Role |
|-------|------|
| Middleware | Reads client id and route, calls the limiter, returns 429 or 503 or passes the request through |
| `rate_limiter` package | Token bucket, Redis Lua script, config load, circuit breaker |

Config changes can be applied at the middleware layer (reload YAML or redeploy instances) without updating many downstream services separately.

### Rejected options

| Option | Reason for rejection |
|--------|----------------------|
| **Sidecar** | An extra container and network hop per service; higher latency and more operations when many microservices exist |
| **Dedicated rate-limit microservice** | Every request needs an extra RPC before the API; middleware plus one Redis call is simpler and faster |
| **Library only, embedded in each microservice** | Fleet-wide limits still need shared Redis, but each service must be redeployed to change limits or library version; risk of inconsistent behavior across instances |
| **In-memory limiting per instance** | Does not meet the requirement; quotas would not be shared across the fleet |

A library is still used, but only as implementation code called from middleware—not as the sole integration point in every service independently.

---

## 3. Rate Limiting Algorithm

### Selected algorithm: token bucket

Each limit is keyed as `rl:{client_id}:{route_template}` (method + path template, not unbounded URLs).

| Algorithm | Outcome | Reason |
|-----------|---------|--------|
| Fixed window | Rejected | Allows extra traffic at window boundaries; clients can be blocked for the rest of the window after a burst |
| Sliding window log | Rejected | Stores many timestamps per key; high memory and CPU at 15k RPS |
| **Token bucket** | **Selected** | Steady `rate_per_sec` plus `burst` capacity; fits “many requests in one second, then idle” |
| Leaky bucket | Rejected | Smooths traffic too aggressively for bursty API clients |

### Redis + Lua implementation

- All instances are stateless; **Redis primary** holds tokens and last refill time per key.
- Each check runs as **one Lua script** on Redis: compute refill from elapsed time, subtract one token if available, save state, return `allowed`, `remaining`, `reset_at`.
- One round-trip per request keeps latency low and avoids race conditions when many instances hit the same client at once.
- Connection pooling and a **2–5 ms** client timeout are used so a slow Redis does not block the API for hundreds of milliseconds.

### Capacity at launch

Only active `(client, route)` pairs use memory. A conservative estimate is ~2 KB per key. At launch (~5k clients × 40 routes), worst-case memory is on the order of **~400 MB** if every pair were active; at 50k clients the upper bound is on the order of **~4 GB**. A single Redis instance with 8–16 GB RAM is sufficient for launch; cluster mode is not required for memory alone.

A **replica** is deployed for high availability. The application reads and writes **only the primary**. The replica is for failover, not for serving limit checks (async lag could allow incorrect counts).

### Quota model

Limits are defined in YAML, not hardcoded.

**Resolution order:** tier default → route override → client override.

| Tier | rate/sec | burst | Notes |
|------|----------|-------|-------|
| free | 10 | 20 | Low steady rate; burst is 2× rate |
| standard | 50 | 100 | Mid tier |
| enterprise | 100 | 200 | Matches ~100 req/s burst described in the brief |

Example route overrides (top or expensive routes):

| Route | free (rate/burst) | standard | enterprise |
|-------|-------------------|----------|------------|
| default | tier default | tier default | tier default |
| `GET /v1/search` | 5 / 10 | 25 / 50 | 80 / 160 |
| `POST /v1/reports` | 2 / 4 | 10 / 20 | 40 / 80 |

Optional per-client overrides can raise limits for specific enterprise tenants on specific routes without changing the enterprise tier for everyone.

Config is loaded at startup and reloaded on an interval or signal. During rollout, instances may briefly use different limits; that is accepted in favor of keeping the API available.

### In-memory fallback

An in-memory limiter inside middleware when Redis is down is **not** used. It would enforce different quotas per instance and would break fleet-wide consistency.

---

## 4. Failure Semantics

When Redis cannot be reached or does not respond in time, the system uses **fail-closed** behavior: requests are **rejected** rather than allowed through without a limit check. This protects the API from overload and abuse when limits cannot be enforced.

> **Note:** Fail-closed means traffic is blocked when the limiter is unhealthy—not “fail-open,” which would allow unlimited traffic during an outage.

### HTTP responses

| Condition | Status | Behavior |
|-----------|--------|----------|
| Over quota | **429** | `Retry-After`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` where applicable |
| Redis error, timeout, or open circuit breaker | **503** | Client should retry with backoff |
| Missing or invalid client id | **400** or **401** | Rejected before Redis is called |

### Circuit breaker

A circuit breaker runs **per API process** to avoid hammering Redis when it is failing.

| Stage | Behavior |
|-------|----------|
| Closed (normal) | Each request calls Redis with a short timeout |
| Open | After repeated failures (for example ~5 in 10 seconds), Redis is skipped; **503** is returned immediately |
| Half-open | After a cooldown (for example ~30 seconds), one probe request tests Redis |
| Closed again | After several successful probes (for example 3), normal operation resumes |

While the circuit is open, no Redis calls are made. That keeps response time low and reduces load on a struggling Redis.

### Code layout

| Module | Responsibility |
|--------|----------------|
| `app/middleware.py` | Invoke limiter; map results to 429 / 503 |
| `rate_limiter/limiter.py` | Timeouts, breaker, orchestration |
| `rate_limiter/redis_store.py` | Connection pool, Lua `EVAL` |
| `rate_limiter/circuit.py` | Breaker state machine |

### Redis failover

On primary failure, infrastructure may promote the replica. Applications reconnect to the new primary. Counters may reset briefly; a short period of possible over-admission is accepted compared to having no limits during an outage.

### Monitoring before sharding

At launch, metrics should include Redis memory, CPU, command latency, limiter latency, allow/deny counts, breaker state, and hot keys. If a single client or route dominates, **config overrides** are adjusted first. **Redis Cluster** is considered only if metrics show sustained CPU or latency problems after tuning.

---

## 5. Load Test Results & Bottlenecks

Load tests use **k6** scripts under `load/scenarios/`. **Measured numbers should be pasted here after running against a live stack** (`docker compose up --build`, then `./scripts/run_load.sh <scenario>`).

### Automated tests (implemented)

| Test file | What it checks |
|-----------|----------------|
| `tests/unit/test_circuit.py` | Circuit opens, half-open, closes |
| `tests/unit/test_config.py` | Tier, route, and client override resolution |
| `tests/integration/test_redis_limiter.py` | Token bucket burst and separate client keys |
| `tests/integration/test_distributed_consistency.py` | Two limiter instances share one Redis quota |
| `tests/integration/test_fail_closed.py` | 503 path when Redis is unreachable; breaker opens |
| `tests/integration/test_middleware.py` | HTTP 400 / 429 / health bypass |

Integration tests require Redis (`REDIS_URL`, default database `1` for isolation).

### Planned load scenarios

| Scenario | Target | What it validates |
|----------|--------|-------------------|
| Baseline | ~3k RPS, mixed clients and routes | Steady-state latency and 429 rate |
| Peak | ~15k RPS | Middleware and Redis under peak fleet load |
| Burst | One client, ~100 RPS for 1s then idle | Token bucket burst and refill |
| Concurrent | Many clients in parallel | Lua atomicity, no double counting |
| Cross-instance | Traffic through load balancer to two APIs | One global quota, not 2× per instance |
| Hot routes | ~80% traffic on five routes | Route overrides |
| Redis failure | Primary stopped or delayed | Fail-closed 503 and circuit breaker |

| k6 script | File |
|-----------|------|
| Baseline mixed traffic | `load/scenarios/baseline.js` |
| Single-client burst | `load/scenarios/burst.js` |
| Cross-instance via nginx | `load/scenarios/cross_instance.js` |

### Metrics to report

- Achieved RPS vs target  
- Limiter latency p50, p95, p99  
- End-to-end p99  
- Share of 429 vs 503  
- Redis CPU and memory  
- First point of failure (for example p99 > 10 ms, error spike, Redis saturation)

### Results (fill after run)

```
# Example — replace with real output
# Scenario: baseline.js
# RPS achieved:
# http_req_duration p99:
# 429 rate:
# 503 rate:
```

### Expected bottlenecks (before tests)

| Failure mode | Expected behavior |
|--------------|-------------------|
| Redis primary unavailable | **503** on affected requests; no silent unlimited traffic |
| Redis slow | Risk of exceeding 10 ms budget; mitigated by timeout and circuit breaker |
| Redis failover | Short 503 window or counter reset; possible brief over-admission |
| Single API instance down | No quota impact; load balancer routes to other instances |
| Hot Redis key | Latency on one key; mitigated by per-client overrides, then sharding if needed |
| Too few API instances at 15k RPS | CPU or connection limits on instances; scale out (stateless) |
| Config rollout | Short period where instances may enforce slightly different limits |

---

## 6. Future Scalability (12-Month Horizon)

Growth is expected from ~5,000 to ~50,000 clients. The launch design should not be over-built on day one, but the path to scale should be clear.

| Area | At launch | At ~12 months |
|------|-----------|---------------|
| Clients | ~5k | ~50k |
| Redis | One primary + one replica | **Redis Cluster** if CPU, latency, or ops metrics require it; memory alone can still fit on one large node (~4 GB upper-bound estimate for all active keys) |
| API instances | 8 behind load balancer; autoscaling on CPU, RPS, or latency | Larger autoscaled fleet; instances remain stateless |
| Config | YAML files, reload on interval or deploy | **etcd** or **ZooKeeper**: gateways watch a key and swap config in memory without redeploying all services |
| Hot clients / routes | Route and client overrides in config | Monitoring-driven overrides; shard Redis only if hot keys remain after tuning |
| Regions | Single region | Optional regional Redis and routing if latency requires it |
| Ingress | Middleware in the API process | Optional managed ingress (for example AWS API Gateway with a custom authorizer) still backed by Redis |

**Sharding approach (if needed):** Keys `rl:{client_id}:{route}` spread across cluster slots naturally. Hash tags are avoided unless a specific hot-key problem requires them. Regional shards are a product decision (per-region vs global quota).

**Config without redeploy (etcd / ZooKeeper):** A new limit document is written to a watched path. Each middleware instance reloads an in-memory snapshot when the watch fires. Redis token state is unchanged; new rates and bursts apply on the next refill.

---

## 7. AI Assistance Disclosure

| Human decisions | AI-assisted work |
|-----------------|------------------|
| Middleware as the integration point (not sidecar, not a separate rate-limit service, not library-only per microservice) | Document structure aligned to the assignment outline |
| Redis as shared state; token bucket algorithm; rejected alternatives | Wording and tables for readability |
| Fail-closed semantics and circuit breaker approach | — |
| Tier, route, and client quota values and rationale | — |
| Single Redis + replica at launch; monitoring before sharding | — |
| Two API instances + load balancer in repo vs eight in production | — |
| Rejection of per-instance memory limits and in-memory fallback when Redis is down | — |

| Implementation code and tests | AI-assisted |
| README code map and run commands | AI-assisted |
| Load-test numeric results | To be recorded by running k6 after deploy |
