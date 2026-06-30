#!/bin/bash
# Comprehensive Integration Test for Multi-tenancy
# 
# This script verifies the full lifecycle of multi-tenancy:
# 1. Seeding separate databases for different tenants.
# 2. Dynamically adding tenants via Admin API.
# 3. Verifying strict data isolation between tenants.
# 4. Testing Admin API lifecycle (list, delete).
# 5. Validating security (ADMIN_TOKEN).
#
# Usage: ./scripts/integration-multi-tenancy.sh

set -euo pipefail

# --- Configuration ---
export ADMIN_TOKEN="secret"
DATA_PORT=8084
BASE_URL="http://127.0.0.1:$DATA_PORT"
SEED_PATH="specs/fixtures/seed.json"

# Temporary DB files for tenants
DB_A="tenant_a.db"
DB_B="tenant_b.db"

# Cleanup function to be called on exit
cleanup() {
  echo "🧹 Cleaning up temporary files..."
  rm -f "$DB_A" "$DB_B"
}
trap cleanup EXIT

echo "🚀 Starting Multi-tenancy Integration Test..."

# 1. Ensure services are running
echo "⏳ Checking if data-service is healthy..."
until curl -sf "$BASE_URL/health" > /dev/null; do
  echo "  Waiting for data-service on :$DATA_PORT..."
  sleep 2
done
echo "✅ data-service is online."

# 2. Prepare Seed Data
# We create two separate SQLite files and seed them.
echo "🔨 Seeding temporary databases..."
DB_PATH="$DB_A" go run data-service/cmd/seed-cli/ --seed-path "$SEED_PATH" > /dev/null 2>&1
DB_PATH="$DB_B" go run data-service/cmd/seed-cli/ --seed-path "$SEED_PATH" > /dev/null 2>&1

# To make isolation verification easy, we'll modify one student in each DB
# using sqlite3 CLI. If sqlite3 is not installed, we'll rely on the fact 
# that seed.json is deterministic, but modifying one record is safer.
if command -v sqlite3 >/dev/null 2>&1; then
  echo "📝 Marking students for isolation check..."
  sqlite3 "$DB_A" "UPDATE students SET name = 'Isolation-Alice' WHERE id = 1;"
  sqlite3 "$DB_B" "UPDATE students SET name = 'Isolation-Bob' WHERE id = 1;"
else
  echo "⚠️  sqlite3 CLI not found, using default seed data (less precise isolation check)."
fi

# 3. Register Tenants via Admin API
echo "🔑 Registering tenants via Admin API..."

# Create Tenant A
curl -s -X POST "$BASE_URL/admin/tenants" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"id\": \"tenant-a\", \"config\": {\"data_source\": {\"driver\": \"sqlite\", \"dsn\": \"$DB_A\"}}}" > /dev/null

# Create Tenant B
curl -s -X POST "$BASE_URL/admin/tenants" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"id\": \"tenant-b\", \"config\": {\"data_source\": {\"driver\": \"sqlite\", \"dsn\": \"$DB_B\"}}}" > /dev/null

echo "✅ Tenants registered."

# 4. Verification Phase
echo "🧪 Verifying Data Isolation..."

# Check Tenant A
RESP_A=$(curl -s -H "X-Tenant-ID: tenant-a" "$BASE_URL/students")
if echo "$RESP_A" | grep -q "Isolation-Alice" && ! echo "$RESP_A" | grep -q "Isolation-Bob"; then
  echo "  ✅ Tenant A: Found Alice, didn't find Bob. (PASS)"
else
  echo "  ❌ Tenant A: Isolation check failed!"
  echo "     Response: $RESP_A"
  exit 1
fi

# Check Tenant B
RESP_B=$(curl -s -H "X-Tenant-ID: tenant-b" "$BASE_URL/students")
if echo "$RESP_B" | grep -q "Isolation-Bob" && ! echo "$RESP_B" | grep -q "Isolation-Alice"; then
  echo "  ✅ Tenant B: Found Bob, didn't find Alice. (PASS)"
else
  echo "  ❌ Tenant B: Isolation check failed!"
  echo "     Response: $RESP_B"
  exit 1
fi

# Check Default Tenant (should not have Alice or Bob)
RESP_DEF=$(curl -s "$BASE_URL/students")
if ! echo "$RESP_DEF" | grep -q "Isolation-Alice" && ! echo "$RESP_DEF" | grep -q "Isolation-Bob"; then
  echo "  ✅ Default Tenant: No leaked data from A or B. (PASS)"
else
  echo "  ❌ Default Tenant: Found leaked data!"
  exit 1
fi

echo "🧪 Verifying Admin Lifecycle..."

# List Tenants
LIST=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/admin/tenants")
if echo "$LIST" | grep -q "tenant-a" && echo "$LIST" | grep -q "tenant-b"; then
  echo "  ✅ Tenant List: Both tenants present. (PASS)"
else
  echo "  ❌ Tenant List: Missing tenants!"
  exit 1
fi

# Delete Tenant A
curl -s -X DELETE "$BASE_URL/admin/tenants/tenant-a" \
     -H "Authorization: Bearer $ADMIN_TOKEN" > /dev/null

# Verify Tenant A is gone
STATUS_A=$(curl -s -o /dev/null -w "%{http_code}" -H "X-Tenant-ID: tenant-a" "$BASE_URL/students")
if [ "$STATUS_A" = "404" ]; then
  echo "  ✅ Deletion: Tenant A correctly removed (404). (PASS)"
else
  echo "  ❌ Deletion: Tenant A still accessible! Status: $STATUS_A"
  exit 1
fi

echo "🧪 Verifying Security..."

# Invalid Token
STATUS_AUTH=$(curl -s -o /dev/null -w "%{http_code}" \
     -H "Authorization: Bearer wrong-token" "$BASE_URL/admin/tenants")
if [ "$STATUS_AUTH" = "401" ]; then
  echo "  ✅ Auth: Invalid token rejected (401). (PASS)"
else
  echo "  ❌ Auth: Invalid token allowed! Status: $STATUS_AUTH"
  exit 1
fi

# Invalid Tenant ID
STATUS_GHOST=$(curl -s -o /dev/null -w "%{http_code}" \
     -H "X-Tenant-ID: ghost-tenant" "$BASE_URL/students")
if [ "$STATUS_GHOST" = "404" ]; then
  echo "  ✅ Routing: Invalid tenant ID rejected (404). (PASS)"
else
  echo "  ❌ Routing: Invalid tenant ID not handled! Status: $STATUS_GHOST"
  exit 1
fi

echo ""
echo "🎉 ALL INTEGRATION TESTS PASSED!"
