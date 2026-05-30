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
SCRIPT="load/scenarios/${SCENARIO}.js"
RESULT="load/results/${SCENARIO}.json"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Unknown scenario: ${SCENARIO}"
  echo "Available: baseline burst cross_instance concurrent hot_routes peak"
  exit 1
fi

mkdir -p load/results
echo "Running ${SCENARIO} against ${BASE_URL}..."
k6 run --summary-trend-stats="avg,med,p(90),p(95),p(99),max" --summary-export="${RESULT}" "${SCRIPT}"
