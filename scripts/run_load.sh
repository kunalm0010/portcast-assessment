#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_URL="${BASE_URL:-http://localhost:8080}"
export BASE_URL

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 is not installed. See https://grafana.com/docs/k6/latest/set-up/install-k6/"
  exit 1
fi

SCENARIO="${1:-baseline}"
k6 run "load/scenarios/${SCENARIO}.js"
