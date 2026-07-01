#!/bin/bash
# Integration test for Multi-tenancy isolation and dynamic tool resolution.
#
# This script verifies that:
# 1. data-service can handle different database schemas for different tenants.
# 2. mcp-gateway dynamically resolves tool paths based on the tenant's manifest.
# 3. Data from one tenant does not leak to another.

set -euo pipefail

# --- Configuration ---
export ADMIN_TOKEN="secret"
DATA_PORT=8084
MCP_PORT=8083
BASE_URL="http://127.0.0.1:$DATA_PORT"
MCP_URL="http://127.0.0.1:$MCP_PORT"

# Database paths
DB_UNI="tenant_uni.db"
DB_SHOP="data-service/testdata/scenarios/shop/data.db"

cleanup() {
  echo "🧹 Cleaning up..."
  rm -f "$DB_UNI"
}
trap cleanup EXIT

echo "🚀 Starting Multi-tenancy Dynamic Tooling Test..."

# 1. Ensure services are running
until curl -sf "$BASE_URL/health" > /dev/null; do
  echo "⏳ Waiting for data-service..."
  sleep 2
done

# 2. Prepare University DB
echo "🔨 Seeding University DB..."
(cd data-service && DB_PATH=../$DB_UNI go run ./cmd/seed-cli/ --seed-path ../specs/fixtures/seed.json)

# 3. Register Tenants
echo "🔑 Registering Tenants..."

# Tenant A: University (Students)
curl -s -X POST "$BASE_URL/admin/tenants" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"id\": \"tenant-uni\", \"config\": {\"data_source\": {\"driver\": \"sqlite\", \"dsn\": \"$DB_UNI\"}, \"entities\": [{\"name\": \"student\", \"table\": \"students\", \"id_column\": \"id\", \"fields\": [{\"name\": \"name\", \"column\": \"name\", \"type\": \"string\"}]}], \"endpoints\": [{\"method\": \"GET\", \"path\": \"/students\", \"op\": \"list\", \"entity\": \"student\"}]}}" > /dev/null

# Tenant B: Shop (Products)
curl -s -X POST "$BASE_URL/admin/tenants" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"id\": \"tenant-shop\", \"config\": {\"data_source\": {\"driver\": \"sqlite\", \"dsn\": \"$DB_SHOP\"}, \"entities\": [{\"name\": \"product\", \"table\": \"products\", \"id_column\": \"id\", \"fields\": [{\"name\": \"name\", \"column\": \"name\", \"type\": \"string\"}]}], \"endpoints\": [{\"method\": \"GET\", \"path\": \"/products\", \"op\": \"list\", \"entity\": \"product\"}]}}" > /dev/null

# 4. Verification
echo "🧪 Verifying Isolation and Dynamic Resolution..."

# Test University
RESP_UNI=$(curl -s -X POST "$MCP_URL/tools/call" -H "X-Tenant-ID: tenant-uni" -d '{"name": "list_student", "arguments": {}}')
if echo "$RESP_UNI" | grep -q "result"; then
  echo "  ✅ University: list_student resolved and returned data."
else
  echo "  ❌ University: tool call failed!"
  echo "$RESP_UNI"
  exit 1
fi

# Test Shop
RESP_SHOP=$(curl -s -X POST "$MCP_URL/tools/call" -H "X-Tenant-ID: tenant-shop" -d '{"name": "list_product", "arguments": {}}')
if echo "$RESP_SHOP" | grep -q "result"; then
  echo "  ✅ Shop: list_product resolved and returned data."
else
  echo "  ❌ Shop: tool call failed!"
  echo "$RESP_SHOP"
  exit 1
fi

# Test Cross-Call (Should fail)
RESP_CROSS=$(curl -s -X POST "$MCP_URL/tools/call" -H "X-Tenant-ID: tenant-shop" -d '{"name": "list_student", "arguments": {}}')
if echo "$RESP_CROSS" | grep -q "not found"; then
  echo "  ✅ Isolation: Shop tenant cannot call University tools."
else
  echo "  ❌ Isolation: Shop tenant accessed University tools!"
  exit 1
fi

echo "🎉 ALL DYNAMIC TOOLING TESTS PASSED!"
