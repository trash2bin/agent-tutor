#!/bin/bash
set -e

echo "🚀 Starting E2E Strict Multi-tenancy Test"

# Cleanup
lsof -ti :8084,8083 | xargs kill -9 || true
rm -rf .data/logs/e2e_test.log

# 1. Prepare Bases
echo "📦 Materializing scenario databases..."
./scripts/dev.sh db materialize sqlite-testseed --force
./scripts/dev.sh db materialize shop --force

# 2. Setup Configs
mkdir -p specs/test_tenants
cp data-service/testdata/scenarios/sqlite-testseed/config.json specs/test_tenants/university.json
cp data-service/testdata/scenarios/shop/config.json specs/test_tenants/shop.json

# Fix DSNs to absolute paths
sed -i '' 's|"dsn": "data.db"|"dsn": "/Users/ivan/code/agent-tutor/data-service/testdata/scenarios/sqlite-testseed/data.db"|' specs/test_tenants/university.json
sed -i '' 's|"dsn": "data.db"|"dsn": "/Users/ivan/code/agent-tutor/data-service/testdata/scenarios/shop/data.db"|' specs/test_tenants/shop.json

# 3. Start data-service
echo "🌐 Starting data-service..."
export PORT=8084
export ADMIN_TOKEN="e2e-secret-token"
nohup ./data-service/bin/data-service --config specs/test_tenants/university.json > .data/logs/e2e_test.log 2>&1 &
DATA_PID=$!
sleep 5

# 4. Add shop tenant via Admin API
echo "🏢 Adding shop tenant..."
curl -s -X POST http://127.0.0.1:8084/admin/tenants \
  -H "Authorization: Bearer e2e-secret-token" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"shop\",
    \"config\": $(cat specs/test_tenants/shop.json | jq -c '.'),
    \"config_path\": \"specs/test_tenants/shop.json\"
  }" > /dev/null

# 5. Start mcp-gateway
echo "🌉 Starting mcp-gateway..."
export BOOTSTRAP_TENANT_ID="default"
export DATA_SERVICE_URL=http://127.0.0.1:8084
export MCP_PORT=8083
nohup ./mcp-gateway/mcp-gateway --config specs/test_tenants/university.json > .data/logs/e2e_mcp.log 2>&1 &
MCP_PID=$!
sleep 5

# ==== Formatting helpers ====
C_RESET="\033[0m"
C_DIM="\033[2m"
C_GREEN="\033[32m"
C_RED="\033[31m"
C_CYAN="\033[36m"
C_YELLOW="\033[33m"

MAX_BODY_CHARS=500

do_request() {
  local url="$1"
  shift
  local response
  response=$(curl -s -w "\n__HTTP_CODE__:%{http_code}" "$@" "$url")
  HTTP_BODY=$(echo "$response" | sed -e '$d')
  HTTP_CODE=$(echo "$response" | tail -n1 | sed -e 's/__HTTP_CODE__://')
}

print_test_result() {
  local name="$1"       # e.g. "T1: No Tenant"
  local expected="$2"   # e.g. "404"
  local method="${3:-GET}"
  local url="$4"

  echo ""
  echo -e "${C_DIM}────────────────────────────────────────────────────────${C_RESET}"
  echo -e "${C_CYAN}${name}${C_RESET}  ${C_DIM}${method} ${url}${C_RESET}"

  # Pretty-print body if it's JSON, otherwise show raw (truncated)
  local pretty
  if command -v jq >/dev/null 2>&1 && pretty=$(echo "$HTTP_BODY" | jq . 2>/dev/null); then
    body_to_show="$pretty"
  else
    body_to_show="$HTTP_BODY"
  fi

  if [ ${#body_to_show} -gt $MAX_BODY_CHARS ]; then
    body_to_show="${body_to_show:0:$MAX_BODY_CHARS}
${C_DIM}... [truncated, ${#body_to_show} chars total]${C_RESET}"
  fi

  if [ -z "$HTTP_BODY" ]; then
    echo -e "${C_DIM}  (empty body)${C_RESET}"
  else
    echo "$body_to_show" | sed 's/^/  /'
  fi

  if [ "$HTTP_CODE" == "$expected" ]; then
    echo -e "${C_GREEN}✅ PASS${C_RESET} — status ${HTTP_CODE} (expected ${expected})"
  else
    echo -e "${C_RED}❌ FAIL${C_RESET} — status ${HTTP_CODE} (expected ${expected})"
    kill "$DATA_PID" "$MCP_PID" 2>/dev/null || true
    exit 1
  fi
}

# ==== Verification Phase ====
echo -e "\n${C_YELLOW}🧪 Verifying Isolation...${C_RESET}"

do_request "http://127.0.0.1:8084/students"
print_test_result "T1: No Tenant → /students" "404" "GET" "http://127.0.0.1:8084/students"

do_request "http://127.0.0.1:8084/students" -H "X-Tenant-ID: default"
print_test_result "T2: Uni Tenant → /students" "200" "GET" "http://127.0.0.1:8084/students (X-Tenant-ID: default)"

do_request "http://127.0.0.1:8084/products" -H "X-Tenant-ID: default"
print_test_result "T3: Uni Tenant → /products" "404" "GET" "http://127.0.0.1:8084/products (X-Tenant-ID: default)"

do_request "http://127.0.0.1:8084/products" -H "X-Tenant-ID: shop"
print_test_result "T4: Shop Tenant → /products" "200" "GET" "http://127.0.0.1:8084/products (X-Tenant-ID: shop)"

do_request "http://127.0.0.1:8084/students" -H "X-Tenant-ID: shop"
print_test_result "T5: Shop Tenant → /students" "404" "GET" "http://127.0.0.1:8084/students (X-Tenant-ID: shop)"

do_request "http://127.0.0.1:8083/mcp/manifest" -H "X-Tenant-ID: default"
print_test_result "T6: MCP Uni Manifest" "200" "GET" "http://127.0.0.1:8083/mcp/manifest (X-Tenant-ID: default)"

do_request "http://127.0.0.1:8083/mcp/manifest" -H "X-Tenant-ID: shop"
print_test_result "T6: MCP Shop Manifest" "200" "GET" "http://127.0.0.1:8083/mcp/manifest (X-Tenant-ID: shop)"

echo ""
echo -e "${C_DIM}────────────────────────────────────────────────────────${C_RESET}"
echo -e "\n${C_GREEN}🎉 ALL TESTS PASSED! System is strictly multi-tenant.${C_RESET}"

# Cleanup
kill $DATA_PID $MCP_PID
