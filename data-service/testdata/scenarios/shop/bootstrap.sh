#!/usr/bin/env bash
# bootstrap.sh — генерация data.db для сценария 'shop'.
#
# Запускается materializer'ом data-service, если в сценарии
# нет seed.json и data.db отсутствует (или передан --materialize --force).
#
# Стратегия: используем утилиту create_shop_db.py из testdata/scripts/,
# подложив SHOP_DB с путём к нужному data.db. Подробности — в
# data-service/README.md § "Сценарии — фабрика тестовых БД" и
# data-service/testdata/scripts/foreign_db_pipeline.py.

set -euo pipefail

# PWD = директория сценария (data-service/testdata/scenarios/shop)
SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_SERVICE_DIR="$(cd "$SCENARIO_DIR/../../.." && pwd)"

# Куда положить итоговую БД: data-service/.../scenarios/shop/data.db
TARGET_DB="$SCENARIO_DIR/data.db"

# Скрипт-генератор БД (создаёт "магазин" с 6 таблицами + sample-данные)
GENERATOR="$DATA_SERVICE_DIR/testdata/scripts/create_shop_db.py"

# Запускаем
echo "  generating shop database → $TARGET_DB"
SHOP_DB="$TARGET_DB" uv run --project "$DATA_SERVICE_DIR/../.." \
  -- python "$GENERATOR"

echo "  ✅ $TARGET_DB создан"

# Финальная проверка: data.db должен существовать
if [ ! -f "$TARGET_DB" ]; then
  echo "❌ bootstrap.sh: $TARGET_DB не создан" >&2
  exit 1
fi
