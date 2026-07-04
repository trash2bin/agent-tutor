#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.data/logs"

cleanup() {
  if [ "${STARTED:-0}" = "1" ]; then
    "$PROJECT_ROOT/scripts/dev.sh" stop >/dev/null 2>&1 || true
  fi
}

tail_logs() {
  echo
  echo "===== LOG TAILS ====="
  for svc in data mcp api web rag; do
    local file="$LOG_DIR/$svc.log"
    if [ -f "$file" ]; then
      echo
      echo "--- $svc ---"
      tail -n 40 "$file" || true
    fi
  done
}

wait_for() {
  local name="$1"
  local url="$2"
  local tries="${3:-60}"
  local sleep_s="${4:-1}"

  echo "Waiting for $name: $url"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "  OK: $name"
      return 0
    fi
    sleep "$sleep_s"
  done

  echo "  FAIL: $name did not become ready"
  return 1
}

check_json_response() {
  local name="$1"
  local url="$2"
  local header="${3:-}"

  local tmp
  tmp="$(mktemp)"
  if [ -n "$header" ]; then
    curl -fsS -H "$header" "$url" > "$tmp"
  else
    curl -fsS "$url" > "$tmp"
  fi

  python3 - "$name" "$tmp" <<'PY'
import json, sys
name = sys.argv[1]
path = sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"{name}: JSON OK")
if name == "data-service manifest":
    print(f"  entities: {len(data.get('entities', []))}")
elif name == "mcp-gateway config":
    if isinstance(data, dict):
        print(f"  keys: {', '.join(sorted(list(data.keys()))[:10])}")
PY
  rm -f "$tmp"
}

run() {
  trap cleanup EXIT

  if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
  fi

  echo "Stopping any existing services..."
  "$PROJECT_ROOT/scripts/dev.sh" stop >/dev/null 2>&1 || true

  echo "Starting services..."
  STARTED=1
  "$PROJECT_ROOT/scripts/dev.sh" start

  wait_for "data-service /health" "http://127.0.0.1:8084/health"
  wait_for "mcp-gateway /health" "http://127.0.0.1:8083/health"
  wait_for "api /health" "http://127.0.0.1:8081/health"
  wait_for "web /" "http://127.0.0.1:8080/"

  echo
  echo "Checking data-service endpoints..."
  check_json_response "data-service health" "http://127.0.0.1:8084/health"
  check_json_response "data-service manifest" "http://127.0.0.1:8084/mcp/manifest" "X-Tenant-ID: default"
  if [ -n "${ADMIN_TOKEN:-}" ]; then
    check_json_response "data-service admin tenants" "http://127.0.0.1:8084/admin/tenants" "Authorization: Bearer ${ADMIN_TOKEN}"
  else
    echo "Skipping admin check: ADMIN_TOKEN not set"
  fi

  echo
  echo "Checking mcp-gateway endpoints..."
  check_json_response "mcp-gateway config" "http://127.0.0.1:8083/debug/config" "X-Tenant-ID: default"

  tmp="$(mktemp)"
  curl -fsS -H 'X-Tenant-ID: default' -H 'Content-Type: application/json' \
    -X POST "http://127.0.0.1:8083/mcp/message" \
    --data '{"jsonrpc":"2.0","id":"1","method":"tools/list","params":{}}' > "$tmp"
  python3 - "$tmp" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
tools = data.get("result", {}).get("tools", [])
print(f"mcp-gateway tools/list: {len(tools)} tools")
if not tools:
    raise SystemExit("mcp-gateway tools/list returned empty tools array")
PY
  rm -f "$tmp"

  echo
  echo "Running e2e..."
  uv run agent-db e2e --tenants default,shop

  echo
  echo "All checks passed."
}

if run; then
  exit 0
else
  rc=$?
  tail_logs
  exit "$rc"
fi
