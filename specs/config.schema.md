# data-service config — руководство

> Companion doc для [`config.schema.json`](./config.schema.json).
> Schema — формальный источник правды. Этот документ — пояснения
> и примеры для людей.

## Что это

JSON-конфиг, который описывает:

1. **К какой БД подключаться** (`data_source`).
2. **Какие сущности извлекать** из этой БД (`entities[]`).
3. **Какие REST endpoints публиковать** (`endpoints[]`).
4. **Какие MCP-инструменты отдавать агенту** (`mcp_tools[]`).
5. **Какой SQL whitelist разрешён** для escape-hatch запросов (`custom_queries`).
6. **Multi-tenancy настройки** (`auth`).

data-service загружает конфиг при старте (фаза 3.0+), валидирует по
`config.schema.json`, и работает по нему. Никакой доменной семантики
в Go-коде нет.

## Минимальный жизнеспособный конфиг

```jsonc
{
  "version": 1,
  "data_source": {
    "driver": "sqlite",
    "dsn": "university.db"
  },
  "entities": [
    {
      "name": "customer",
      "table": "customers",
      "id_column": "id",
      "fields": [
        { "name": "id",    "column": "id",    "type": "string" },
        { "name": "email", "column": "email", "type": "string" }
      ]
    }
  ],
  "endpoints": [
    { "method": "GET", "path": "/customers/{id}", "op": "get_by_id", "entity": "customer" },
    { "method": "GET", "path": "/health",         "op": "builtin_health" }
  ]
}
```

После старта data-service автоматически отдаёт:

- `GET /customers/{id}` — карточка клиента по ID
- `GET /health` — статус сервиса и БД

И регистрирует MCP-инструменты (если указаны в `mcp_tools[]`).

## Подстановка переменных окружения

В любых строковых полях конфига можно использовать `${ENV_VAR}` и
`${ENV_VAR:-default}`:

```jsonc
"dsn": "${DB_DSN:-university.db}"
"dsn": "postgres://user:${DB_PASSWORD}@host:5432/db"
```

Подстановка происходит **до** валидации схемой.

## Операции endpoint'ов

| `op`               | Что делает                                       | Требует          |
|--------------------|--------------------------------------------------|------------------|
| `builtin_health`   | `/health` (статус сервиса + БД)                  | —                |
| `builtin_stats`    | `/stats` (счётчики по entities)                  | `stats` блок     |
| `get_by_id`        | Запись по `id_column` через path `{id}`          | `entity`         |
| `find`             | Поиск по `search_field` через query-параметр    | `entity`, `search_field` |
| `list`             | Список всех записей entity                       | `entity`         |
| `custom_query`     | Whitelist SQL из `custom_queries[query_id]`      | `query_id`       |

## SQL Whitelist

`custom_queries` — единственное место, где в конфиге встречается
произвольный SQL. Жёсткие ограничения:

- Только `SELECT` (regex `^\s*SELECT\b`).
- Без `;` — никаких multiple statements.
- `?` placeholder'ы для всех user-input.
- Обязательный `max_rows` (1..10000) — защита от over-fetch.
- `result_mapping` — JSON Schema типы для каждой колонки результата.

Пример:

```jsonc
"student_grades": {
  "sql": "SELECT g.id, g.grade FROM grades g WHERE g.student_id = ?",
  "params": ["id"],
  "result_mapping": {
    "id":    { "type": "string" },
    "grade": { "type": "string" }
  },
  "max_rows": 500
}
```

Адаптер автоматически заменит `?` на нативный placeholder СУБД
(`?` для SQLite, `$1` для PostgreSQL и т.д.).

## Маппинг имён

**Публичные имена** (`name` в entities, fields, endpoints) — то, что
видят потребители (HTTP API, MCP, UI). Желательно snake_case.

**Колонки БД** (`column` в fields) — то, что лежит в БД. Может
совпадать с name, но не обязательно.

Это разделение позволяет переименовать публичное API без миграции БД
и наоборот.

## Отношения между сущностями

`relations[]` — это **документация**, а не JOIN'ы. JOIN'ы не
строятся автоматически (иначе N+1 и непредсказуемые запросы).
Для JOIN'ов используйте `custom_queries` и пишите SQL явно.

## Multi-tenancy (фаза 3.7)

```jsonc
"auth": {
  "strategy": "header",
  "tenant_header": "X-Tenant-ID",
  "row_filters": [
    {
      "entity": "customer",
      "where": "tenant_id = :tenant_id"
    }
  ]
}
```

data-service автоматически добавит `AND tenant_id = ?` ко всем
запросам к entity `customer`, подставив значение из заголовка.

## Валидация

```bash
# Через Python jsonschema:
uv run python -c "
import json, jsonschema
schema = json.load(open('specs/config.schema.json'))
cfg = json.load(open('my_config.json'))
jsonschema.Draft202012Validator(schema).validate(cfg)
print('OK')
"
```

В фазе 3.2 data-service будет валидировать конфиг сам при старте
и при reload.

## Версионирование

`version: 1` — текущая версия. При будущих несовместимых изменениях
схемы значение инкрементируется, и data-service откажется грузить
конфиг неподдерживаемой версии с понятным сообщением.
