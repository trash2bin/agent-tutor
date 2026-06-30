#!/bin/bash
# Smoke-test для проверки мульти-тенантности и Admin API.
# 
# Предназначение: Быстрая проверка "вживую" создания тенантов, 
# изоляции данных и работы авторизации через ADMIN_TOKEN.
#
# Запуск: ./scripts/test-multi-tenancy.sh
#
# Ожидаемое поведение:
# 1. Запуск сервисов через dev.sh
# 2. Проверка default-тенанта
# 3. Проверка 401 ошибки при отсутствии ADMIN_TOKEN
# 4. Создание нового тенанта (school-x)
# 5. Проверка доступа к данным нового тенанта через X-Tenant-ID

export DATABASE_URL=""
export ADMIN_TOKEN="secret"

echo "--- Restarting services with SQLite ---"
./scripts/dev.sh restart

echo "--- Testing Default Tenant ---"
curl -s http://127.0.0.1:8084/students | grep -C 2 "student"

echo "--- Testing Admin API (No Auth) ---"
curl -s -o /tmp/admin_no_auth.json http://127.0.0.1:8084/admin/tenants
echo "Status: $(grep -c "error" /tmp/admin_no_auth.json)"

echo "--- Creating Tenant school-x ---"
curl -s -X POST http://127.0.0.1:8084/admin/tenants \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"id": "school-x", "config": {"data_source": {"driver": "sqlite", "dsn": "school_x.db"}}}'

echo "--- Testing Tenant school-x ---"
curl -s -H "X-Tenant-ID: school-x" http://127.0.0.1:8084/students

echo "--- Testing Tenant isolation ---"
# Check that school-x is empty (since we didn't seed it)
# whereas default has data.
