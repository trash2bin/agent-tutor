#!/usr/bin/env bash
# bootstrap.sh — диагностическая версия

set -euo pipefail

echo "--- DEBUG START ---"
echo "CWD: $(pwd)"
echo "SCRIPT_PATH: $0"
echo "DATA_SERVICE_DIR: ${DATA_SERVICE_DIR:-NOT SET}"
echo "SHOP_DB: ${SHOP_DB:-NOT SET}"
echo "PROJECT_ROOT: ${PROJECT_ROOT:-NOT SET}"
echo "--- DEBUG END ---"

# Если переменные не заданы, пробуем вычислить их (fallback)
S_DIR="$(cd "$(dirname "$0")" && pwd)"
DS_DIR="${DATA_SERVICE_DIR:-$(cd "$S_DIR/../../.." && pwd)}"
T_DB="${SHOP_DB:-$S_DIR/data.db}"

GENERATOR="$DS_DIR/testdata/scripts/create_shop_db.py"
echo "DEBUG: Target Generator Path: $GENERATOR"

if [ ! -f "$GENERATOR" ]; then
  echo "❌ Error: Generator script not found at $GENERATOR" >&2
  exit 1
fi

echo "  generating shop database → $T_DB"
P_ROOT="$(cd "$DS_DIR/.." && pwd)"
SHOP_DB="$T_DB" uv run --project "$P_ROOT" -- python "$GENERATOR"

echo "  ✅ $T_DB создан"
