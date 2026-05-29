#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m pip install -e ".[dev]" -q

echo "==> Unit tests"
pytest tests/unit -q

echo "==> Integration tests (requires Redis at ${REDIS_URL:-redis://localhost:6379/1})"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/1}" pytest tests/integration -m integration -q
