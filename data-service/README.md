# Data Service

HTTP-сервис доступа к произвольной БД через config-driven REST API. Написан на Go.

**Архитектура:** сервис читает JSON-конфиг, на его основе строит эндпоинты и query builder.
Никакого захардкоженного знания о домене — вся семантика в конфиге.

## Принципиальная схема

```
                    ┌──────────────────┐
                    │   config.json    │  ← ручной / --discover
                    │  (entities,      │
                    │   endpoints,     │
                    │   custom queries)│
                    └──────┬───────────┘
                           ▼
data-service ──JSON-конфиг──▶ chi-роутер ──▶ runtime handlers
   │                                              │
   │  ┌─────────────────────────────────┐         │
   ├──│ Introspect (sqlite_master /     │         │
   │  │  information_schema)            │         ▼
   │  └────────┬────────────────────────┘      query_builder
   │           │                                (SELECT + prepared)
   ▼           ▼                                    │
[клиентская БД]                                      ▼
(SQLite / PG)                                  database/sql
```

## Чем отличается от предыдущей версии

| Было (хардкод) | Стало (config-driven) |
|---|---|
| SQL-запросы в `internal/repository/` | SQL в `config.example.json` (`custom_queries`) |
| 7 Go-структур в `internal/models/` | 1 generic `Entity{Fields}` |
| 6 domain-хендлеров в `internal/handlers/` | 6 runtime-хендлеров (generic: `get_by_id`, `find`, `list`, `custom_query`) |
| `/openapi.json` зашит `//go:embed` | **Runtime-генерация** на каждый запрос |
| Конфиг пишется руками | `--discover` / `GET /admin/discover` / `POST /admin/config/rewrite` |
| Только university-схема | **Любая БД** — конфиг описывает что угодно |

## Быстрый старт

```bash
# 1. Собрать
cd data-service && go build -o bin/data-service ./cmd/server/

# 2. Сгенерировать конфиг из существующей БД
DB_PATH=../university.db ./bin/data-service --discover > ../specs/config.generated.json

# 3. Запустить
./bin/data-service --config ../specs/config.generated.json

# 4. Проверить
curl http://127.0.0.1:8084/students/ | head -c 200
```

## Архитектура

```
cmd/server/main.go            ← точка входа, graceful shutdown, флаги
  │
  ├── --discover              ← прочитать схему БД → вывести config.json в stdout
  ├── --config <path>         ← путь к config.json (по умолчанию $DS_CONFIG или specs/config.example.json)
  ├── --materialize <dir>     ← dev-only: создать БД из сценария (config.json + seed.json)
  ├── --force                 ← разрешить перезапись при --materialize
  └── DS_DISCOVER=true        ← env-вариант --discover

internal/
├── config/                    ← загрузка, валидация, envsubst
│   ├── loader.go              ← Load(path) → *Config
│   ├── validate.go            ← JSON Schema validation
│   ├── types.go               ← Config, Entity, Endpoint, CustomQuery, ...
│   ├── envsubst.go            ← ${ENV:-default} подстановка
│   └── store.go               ← FileStore / DbStore (фаза 3.7+)
│
├── datasource/                ← адаптеры БД
│   ├── adapter.go             ← Adapter interface {Connect, Introspect, ...}
│   ├── sqlite_adapter.go      ← SQLite (modernc.org/sqlite)
│   ├── postgres_adapter.go    ← PostgreSQL (pgx/v5)
│   └── registry.go            ← реестр драйверов
│
├── runtime/                   ← generic query builder + хендлеры
│   ├── types.go               ← Entity, CustomQuery, AdapterSubset
│   ├── query_builder.go       ← BuildGetByID, BuildFind, BuildList, BuildCustomQuery
│   ├── response_mapper.go     ← MapRow, MapCustomQueryRow, MapRows
│   ├── entity_resolver.go     ← Resolve(entityName) → Entity
│   ├── converter.go           ← Config → runtime types
│   └── handlers/              ← generic HTTP-хендлеры
│       ├── get_by_id.go       ← GET /{entity}/{id}
│       ├── find.go            ← GET /{entity}?search=...
│       ├── list.go            ← GET /{entity} (fallback)
│       ├── custom_query.go    ← произвольный SELECT из конфига
│       ├── health.go          ← GET /health
│       ├── stats.go           ← GET /stats
│       ├── context.go         ← Context {DB, Builder, Resolver, ...}
│       └── default.go         ← 404, 405
│
├── configgen/                 ← генерация конфига из интроспекции
│   └── configgen.go           ← Generate(schema, ds) → *Config
│
├── openapigen/                ← runtime-генерация OpenAPI
│   └── openapigen.go          ← Generate(cfg, host, title, version, hasAdmin) → spec
│
├── server/                    ← HTTP-сервер
│   ├── server.go              ← middleware (recovery, request ID, structured logging)
│   ├── endpoint_builder.go    ← NewRouterFromConfig + discover/rewrite handlers
│   ├── scenario_test_helpers_test.go ← хелперы для тестов на сценариях
│   └── swagger.go             ← /docs (Swagger UI), /openapi.json (runtime)
│
├── seedgen/                   ← dev-only: фабрика тестовых БД
│   ├── seedgen.go             ← Load, Apply, ApplyWithDDL + типы Group/Student/Teacher/... (dev-only)
│   ├── config_schema.go       ← GenerateDDL(entities, driver) — CREATE TABLE из конфига
│   ├── materialize.go         ← Materialize(ctx, adapter, cfg, seed, baseDir, force)
│   └── testdata.go            ← TestSeed (legacy фикстура)
│
├── testdata/scenarios/        ← самодостаточные сценарии (config.json + seed.json)
│   ├── sqlite-testseed/       ← SQLite сценарий
│   └── postgres-testseed/     ← PostgreSQL сценарий (те же данные)
│
├── tests/
│   └── integration/
│       └── test_with_faker.py ← faker seed → PG → data-service → HTTP-проверки
│
└── db/                        ← legacy connector (только для тестов)
    └── connector.go           ← DB interface + New()
```

## API

### Пользовательские эндпоинты (из конфига)

Эндпоинты определяются в `config.json` → `endpoints[]`. Типовой набор:

| Метод | Путь | Описание | Тип |
|---|---|---|---|
| GET | `/health` | Статус сервиса и БД | builtin |
| GET | `/stats` | Количество записей во всех сущностях | builtin |
| GET | `/{entity}/{id}` | Одна запись по ID | `get_by_id` |
| GET | `/{entity}?field=...` | Поиск по полю или список всех | `find` |
| GET | `/{entity}/{id}/...` | Произвольные связанные данные | `custom_query` |

Точный список — в `/openapi.json` живого сервиса или в `specs/config.example.json`.

### Админские эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/discover` | Прочитать схему БД, сгенерировать и отдать конфиг |
| GET | `/admin/discover?raw=true` | То же, но чистый JSON (можно сохранить в файл) |
| POST | `/admin/config/rewrite` | Прочитать схему, сгенерировать, **сохранить в config-файл** |

> Админские эндпоинты доступны только если адаптер данных передан в роутер.

### Системные

| Путь | Описание |
|---|---|
| `/docs` | Swagger UI |
| `/openapi.json` | OpenAPI 3.1.0 — **runtime-генерация из текущего конфига** |

## Конфигурация

### Формат

Конфиг — JSON, валидируется по `specs/config.schema.json`. Ключевые секции:

```jsonc
{
  "version": 1,
  "data_source": {
    "driver": "sqlite",                    // sqlite | postgres
    "dsn": "${DB_PATH:-university.db}",    // поддержка ${ENV}
    "pool_size": 10,
    "read_only": true
  },
  "entities": [                            // описание таблиц
    {
      "name": "student",                   // публичное имя
      "table": "students",                 // имя в БД
      "id_column": "id",
      "fields": [
        { "name": "full_name", "column": "name", "type": "string" },
        { "name": "course",   "column": "course", "type": "int" }
      ]
    }
  ],
  "endpoints": [                           // какие эндпоинты публикуем
    { "method": "GET", "path": "/students/{id}", "op": "get_by_id", "entity": "student" },
    { "method": "GET", "path": "/students", "op": "find", "entity": "student", "search_field": "full_name" },
    { "method": "GET", "path": "/students/{id}/grades", "op": "custom_query", "query_id": "student_grades" }
  ],
  "custom_queries": {                      // whitelist SELECT-запросов
    "student_grades": {
      "sql": "SELECT g.id, g.grade, d.name AS discipline_name FROM grades g LEFT JOIN disciplines d ON d.id = g.discipline_id WHERE g.student_id = ?",
      "params": ["id"],
      "result_mapping": { "id": {"type": "string"}, "grade": {"type": "string"}, "discipline_name": {"type": "string"} },
      "max_rows": 500
    }
  },
  "stats": {
    "counters": [{ "name": "students", "entity": "student" }]
  }
}
```

### Генерация конфига (--discover)

Если подключиться к БД — конфиг можно сгенерировать автоматически:

```bash
# CLI
./data-service/bin/data-service --discover > config.json

# Env
DS_DISCOVER=true ./data-service/bin/data-service > config.json

# HTTP (на живом сервисе)
curl http://localhost:8084/admin/discover?raw=true > config.json

# HTTP — переписать конфиг на диске (сохраняется в тот же путь что и текущий)
curl -X POST http://localhost:8084/admin/config/rewrite
```

Генерируется:
- Entities для каждой таблицы (колонки, PK, типы)
- `get_by_id` для таблиц с одной PK
- `find` для таблиц с name-полем
- `/health`, `/stats`

Не генерируется (дописывается руками):
- `custom_queries` (JOIN'ы, вложенные объекты)
- `params` для path/query параметров
- MCP tools

### Пример: смена БД

```bash
# PostgreSQL
cat > pg-config.json << 'EOF'
{
  "version": 1,
  "data_source": {
    "driver": "postgres",
    "dsn": "postgres://user:pass@host:5432/mydb?sslmode=disable",
    "pool_size": 25
  }
}
EOF

# Сгенерировать entities из реальной схемы
DS_CONFIG=pg-config.json ./data-service/bin/data-service --discover > full-config.json

# Запустить
./data-service/bin/data-service --config full-config.json
```

## Ключевые принципы безопасности

1. **Подготовленные выражения** — все параметры через `?`/`$1`, никогда не конкатенируются
2. **Whitelist операций** — только SELECT, обязателен `max_rows` для custom_query
3. **Чужая БД — read-only** — data-service не пишет в клиентскую БД
4. **Read-only режим** — `read_only: true` по умолчанию, принудительно
5. **Валидация конфига** — JSON Schema (`specs/config.schema.json`) при загрузке

## Запуск

```bash
# Из корня проекта
# Сборка
cd data-service && go build -o bin/data-service ./cmd/server/

# Dev (SQLite)
./bin/data-service

# Dev (PostgreSQL)
DATABASE_URL=postgresql://... ./bin/data-service --config pg-config.json

# Seed-режим (dev-only, залить тестовые данные — legacy)
./bin/data-service --seed

# Сценарии (dev-only, создать БД из config.json + seed.json)
./bin/data-service --materialize testdata/scenarios/sqlite-testseed
./bin/data-service --materialize testdata/scenarios/sqlite-testseed --force  # пересоздать
./bin/data-service --config testdata/scenarios/sqlite-testseed/config.json   # запустить сервер

# Управление сценариями через dev-скрипт (см. scripts/dev.sh db help)
cd .. && ./scripts/dev.sh db list                       # список сценариев
./scripts/dev.sh db materialize big-testseed --force   # пересоздать большой сценарий
./scripts/dev.sh db serve shop                         # foreground data-service на сценарии
./scripts/dev.sh db test sqlite-testseed               # прогнать Go-тесты на сценарии
./scripts/dev.sh db drop shop                          # удалить материализованную БД

# Кастомный порт
PORT=8085 ./bin/data-service
```

### Переменные окружения

| Переменная | Дефолт | Описание |
|---|---|---|
| `DS_CONFIG` | `specs/config.example.json` | Путь к конфигу |
| `PORT` | `8084` | Порт HTTP |
| `LOG_LEVEL` | `info` | `info` или `debug` |
| `DS_DISCOVER` | — | Включить режим --discover (генерировать конфиг из БД и выйти) |
| `DB_DRIVER` | `sqlite` | Для --seed режима |
| `DB_PATH` | `university.db` | Для --seed режима |
| `DATABASE_URL` | — | Для --seed режима (PostgreSQL) |
| `CONFIG_SCHEMA` | `specs/config.schema.json` | Путь к JSON Schema |

### Docker

```bash
docker build -t agent-tutor-data -f data-service/Dockerfile .
docker run -p 8084:8084 -v $(pwd)/config.json:/config.json \
  -e DS_CONFIG=/config.json agent-tutor-data
```

## Сценарии — фабрика тестовых БД

Сценарий — самодостаточная пара `config.json` + `seed.json`, из которой data-service
может создать и наполнить реальную базу данных. Это позволяет **воспроизводимо**
тестировать сервис на разных БД с одинаковым набором данных.

### 🚀 Шпаргалка — как менять БД

Запустить с готовой БД, пересоздать её, переключиться на другую СУБД или собрать новый сценарий — все команды в одном месте.

```bash
# ── 1. Запустить data-service с готовой БД из сценария ──
# (после --materialize один раз, дальше просто читаем ту же БД)
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --config testdata/scenarios/sqlite-testseed/config.json
# → http://127.0.0.1:8084/health → {"db":"ok","status":"ok"}

# ── 2. Пересоздать БД из сценария (force-mode) ──
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --materialize testdata/scenarios/sqlite-testseed --force
# ⚠️ --force удаляет файл SQLite и пишет заново. Для PG используй DROP SCHEMA вручную (см. ниже).

# ── 3. Переключиться на другую СУБД (SQLite → PostgreSQL) ──
# a) поднять PG
docker compose up -d db
# b) материализовать сценарий в PG
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --materialize testdata/scenarios/postgres-testseed --force
# c) запустить сервер с тем же config.json (он сам выберет драйвер по data_source.driver)
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --config testdata/scenarios/postgres-testseed/config.json

# ── 4. Создать новый сценарий с нуля ──
cp -r testdata/scenarios/sqlite-testseed testdata/scenarios/my-scenario
# Поправить config.json (driver/dsn/entities) и (опц.) seed.json
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --materialize testdata/scenarios/my-scenario --force

# ── 5. Иностранная БД (--discover → автоконфиг → сценарий) ──
# "any DB → auto-REST": подсунуть свою SQLite и data-service сам сгенерит config.json
DB_PATH=testdata/scripts/shop.db ./bin/data-service --discover > testdata/scenarios/my/config.json
# дальше — пункт 2 со своим сценарием

# ── 6. force для PostgreSQL вручную ──
# --force пока только для SQLite. Для PG сначала чистим схему:
docker exec agent-tutor-db-1 psql -U tutor -d agent_tutor \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public"
# затем materialize (без --force):
CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go run ./cmd/server/ --materialize testdata/scenarios/postgres-testseed
```

**Точки входа, которые стоит запомнить**:

| Что | Где |
|---|---|
| Корневая директория сценариев | `data-service/testdata/scenarios/` |
| Готовые сценарии | `sqlite-testseed/` (SQLite), `postgres-testseed/` (PG), `shop/` (сторонняя БД) |
| DDL-генератор (entities → CREATE TABLE) | `internal/seedgen/config_schema.go` |
| Оркестратор фабрики | `internal/seedgen/materialize.go` |
| CLI-флаг сервиса | `cmd/server/main.go` → `--materialize`, `--force` |
| Интеграционный тест с PG | `tests/integration/test_with_faker.py` |
| Автогенерация из сторонней БД | `testdata/scripts/foreign_db_pipeline.py` |
| config-schema (нужна `CONFIG_SCHEMA` env) | `../specs/config.schema.json` (относительно `data-service/`) |

**Если коротко — три команды, которые покрывают 90% случаев**:

```bash
# 1) Создать/пересоздать БД из сценария
CONFIG_SCHEMA=$PWD/../specs/config.schema.json go run ./cmd/server/ --materialize testdata/scenarios/<name> [--force]

# 2) Запустить сервер с этой БД
CONFIG_SCHEMA=$PWD/../specs/config.schema.json go run ./cmd/server/ --config testdata/scenarios/<name>/config.json

# 3) Прогнать Go-тесты на сценарии (in-memory)
go test ./internal/server/... -run TestScenario -v
```

Подробное описание внутренностей — ниже.

### Мотивация

Раньше тесты были привязаны к одному хардкодному конфигу `testConfig()` и SQLite.
Это делало невозможным:

- Прогнать те же тесты на PostgreSQL
- Создать вариации данных (другие студенты, группы, расписание)
- Воспроизвести баг на production-схеме

Теперь любой сценарий — это просто директория с двумя JSON-файлами. Создать новый —
скопировать директорию и поправить `config.json`/`seed.json`.

### Структура сценария

```
testdata/scenarios/<имя-сценария>/
├── config.json    ← конфиг data-service (entities + endpoints + custom_queries)
└── seed.json      ← данные (группы, студенты, преподаватели, дисциплины, ...)
```

Сценарий ничего не знает о Go-коде и не требует компиляции при изменении —
вся логика создания БД зашита в data-service.

### Как это работает — полный цикл `--materialize`

Команда `--materialize <директория-сценария>` проходит 5 шагов:

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. config.Load("config.json")                                       │
│     → *Config с entities, endpoints, custom_queries, data_source     │
│                                                                      │
│  2. seedgen.Load("seed.json")                                        │
│     → *Seed с groups, students, teachers, disciplines, schedule,     │
│       grades                                                         │
│                                                                      │
│  3. seedgen.GenerateDDL(cfg.Entities, cfg.DataSource.Driver)         │
│     → "CREATE TABLE groups (...); CREATE TABLE students (...); ..."  │
│       SQLite:  TEXT / INTEGER                                        │
│       PG:      TEXT / INTEGER (тот же диалект для базовых типов)     │
│                                                                      │
│  4. adapter.Connect(cfg.DataSource.DSN)                              │
│     → *sql.DB (SQLite или PostgreSQL)                                │
│                                                                      │
│  5. seedgen.ApplyWithDDL(ctx, db, ddl, seed, placeholderFn)          │
│     ├── Exec(DDL) → создание таблиц                                  │
│     └── INSERT groups → INSERT students → INSERT teachers → ...      │
│         (плейсхолдеры: ? для SQLite, $1,$2 для PostgreSQL)           │
└──────────────────────────────────────────────────────────────────────┘
```

```go
// Materialize — главная функция фабрики
func Materialize(
    ctx context.Context,
    adapter datasource.Adapter,  // sqlite или postgres адаптер
    cfg *config.Config,          // полный конфиг (entities + endpoints + ...)
    seed *Seed,                  // данные для вставки
    baseDir string,              // откуда резолвить относительный DSN
    force bool,                  // пересоздать если уже существует
) error
```

### Placeholder-агностик: один код — SQLite и PostgreSQL

Функция `ApplyWithDDL` принимает `PlaceholderFunc` — функцию, которая по индексу
возвращает плейсхолдер:

```go
// SQLite:     INSERT INTO students VALUES (?, ?, ?, ?)
// PostgreSQL: INSERT INTO students VALUES ($1, $2, $3, $4)
type PlaceholderFunc func(index int) string

func SQLitePlaceholder(_ int) string   { return "?" }
func PostgresPlaceholder(index int) string { return fmt.Sprintf("$%d", index) }
```

Каждый `INSERT` формируется через `fmt.Sprintf("... VALUES (%s, %s, %s)", ph(1), ph(2), ph(3))`.
Выбор функции — по `driver` из конфига:

```go
phFn := seedgen.SQLitePlaceholder
if cfg.DataSource.Driver == "postgres" {
    phFn = seedgen.PostgresPlaceholder
}
seedgen.ApplyWithDDL(ctx, conn, ddl, seed, phFn)
```

### DDL из конфига: зачем GenerateDDL

Раньше DDL для seed был захардкожен в `seedgen.schemaDDL` — SQLite-специфичный SQL,
завязанный на конкретные имена таблиц. Теперь `GenerateDDL` берёт `config.Entity[]`
и генерирует `CREATE TABLE` под конкретный драйвер:

```
config.Entity{Name:"students", Table:"students", Fields:[...]}  →
  CREATE TABLE students (id TEXT PRIMARY KEY, name TEXT, group_id TEXT, ...)
```

Это делает сценарий полностью самодостаточным — ему не нужно, чтобы Go-код знал схему.
Таблицы создаются ровно те, что описаны в `config.json`.

### Готовые сценарии

| Сценарий | Драйвер | DSN | Данные | Назначение |
|---|---|---|---|---|
| `sqlite-testseed` | `sqlite` | `data.db` | 2/2/1/3/2/3 (13 entities) | Базовый смоук-сценарий |
| `postgres-testseed` | `postgres` | `postgresql://tutor:tutor@127.0.0.1:5432/agent_tutor?sslmode=disable` | те же данные | Тот же сценарий на PG (для cross-driver сравнения) |
| `big-testseed` | `sqlite` | `data.db` | 25/500/30/25/100/4000 (4680 entities) | Нагрузочный: латентность, pagination, concurrent reads |
| `shop` | `sqlite` | `data.db` | онлайн-магазин (categories/products/customers/orders/order_items/reviews), 17 endpoints | Сторонняя БД с 6 FK-lookups (custom_queries) |

Разница между конфигами сценариев — только `driver`, `dsn` и SQL в `custom_queries`:

```
                                SQLite                              PostgreSQL
──────────────────────────────────────────────────────────────────────────────────
student_disciplines   json_each(lessons_json)            jsonb_array_elements(lessons_json::jsonb)
student_grades        ?-плейсхолдеры                     $1-плейсхолдеры
teacher_schedule      sqlite-специфичные функции          pg-совместимые функции
```

> ⚠️ **Legacy-различие**: SQLite отдаёт `lessons_json` (сырая JSON-строка), PostgreSQL — раскрытый массив `lessons`.
> Тесты учитывают это (см. раздел [Тестирование](#тестирование)).

### Как создать новый сценарий

```bash
# 1. Скопировать существующий
cp -r testdata/scenarios/sqlite-testseed testdata/scenarios/my-scenario

# 2. Поправить config.json:
#    - data_source.driver (sqlite или postgres)
#    - data_source.dsn
#    - entities и endpoints (добавить/убрать/переименовать)
#    - custom_queries под целевой диалект SQL (главное различие между БД)

# 3. (Опционально) Сгенерировать новый seed.json:
#    cd ../.. && uv run agent-seedgen --students 80 --grades 200 --seed 42
#    cp specs/fixtures/seed.json data-service/testdata/scenarios/my-scenario/

# 4. Создать БД
go run ./cmd/server/ --materialize testdata/scenarios/my-scenario

# 5. Запустить сервер
go run ./cmd/server/ --config testdata/scenarios/my-scenario/config.json
```

### Использование в тестах

Тестовые хелперы в `internal/server/scenario_test_helpers_test.go` загружают сценарий
в in-memory SQLite (для unit-тестов) или реальную БД (для integration-тестов):

```go
// Загрузить сценарий в in-memory SQLite, создать DDL + seed
func loadScenario(t *testing.T, dir string) (*config.Config, *seedgen.Seed)

// Загрузить сценарий и собрать chi-роутер для httptest
func buildTestRouter(
    t *testing.T,
    dir string,
    adapter datasource.Adapter,  // nil = in-memory SQLite
) (*config.Config, http.Handler)
```

```go
// Пример: прогнать сценарий на in-memory SQLite и проверить все эндпоинты
func TestScenario_SqliteTestseed(t *testing.T) {
    cfg, router := buildTestRouter(t,
        "../../testdata/scenarios/sqlite-testseed", nil)

    // Обычные httptest.NewRecorder() + router.ServeHTTP
    // Проверка /health, /students/s1, /students/s1/grades, ...
}
```

### Equivalence-тесты (SQLite vs PostgreSQL)

Оба сценария используют один `seed.json` — можно проверить, что SQLite и PostgreSQL
возвращают идентичные данные для одних и тех же эндпоинтов:

```go
func TestEquivalence_SqliteVsPostgres(t *testing.T) {
    // 1. Поднять PG-контейнер (docker compose up -d db)
    // 2. materialize оба сценария
    // 3. Пройтись по всем эндпоинтам → сравнить JSON-ответы
}
```

### Ручная проверка

```bash
# SQLite
go run ./cmd/server/ --materialize testdata/scenarios/sqlite-testseed
go run ./cmd/server/ --config testdata/scenarios/sqlite-testseed/config.json

# PostgreSQL (нужен docker compose up -d db из корня проекта)
go run ./cmd/server/ --materialize testdata/scenarios/postgres-testseed
go run ./cmd/server/ --config testdata/scenarios/postgres-testseed/config.json

# Проверка эндпоинтов (идентична для обоих драйверов)
curl http://127.0.0.1:8084/health
curl http://127.0.0.1:8084/students/s1
curl http://127.0.0.1:8084/students/s1/grades
curl http://127.0.0.1:8084/students/s1/disciplines
curl http://127.0.0.1:8084/groups/g1/schedule
curl http://127.0.0.1:8084/stats
```

Результат для обоих драйверов **идентичен**:

```
health:         {"db":"ok","status":"ok"}
student s1:     {"full_name":"Иван Петров Иванович","course":2,"group_id":"g1"}
grades s1:      [{"grade":"4","discipline_name":"Базы данных"}, ...]   (2 шт)
disciplines s1: [{"id":"d1","name":"Базы данных"}, ...]               (3 шт)
schedule g1:    [{day:"Понедельник",...}, {day:"Вторник",...}]        (2 шт)
stats:          {"students":2,"teachers":1,"disciplines":3,"grades":3,"schedule":2}
```

### Интеграционный тест с faker (Python)

`tests/integration/test_with_faker.py` — end-to-end тест, который:
генерирует случайный seed через Faker → материализует в PostgreSQL (Docker) →
поднимает data-service → проверяет все эндпоинты.

Это «кривой косой скрипт» — не pytest, не testify, не красивый. Но он
**единственный** проверяет, что сценарий + data-service + PostgreSQL работают
на случайных данных, а не только на фиксированном `TestSeed`.

#### Pipeline теста (12 проверок)

```
1. Проверить что PostgreSQL жив (docker exec pg_isready)
2. Сгенерировать случайный seed.json через faker
   - Группы:      fake.bothify("??-###") → "АБ-435"
   - Студенты:    fake.last_name() + first_name() + middle_name() → "Иванов Пётр Сергеевич"
   - Преподаватели: то же что студенты, но female
   - Дисциплины:  стабильный набор из 10 (d1..d10)
   - Расписание:  2-4 пары в день, случайные аудитории 100-500
   - Оценки:      каждому студенту по n_grades случайных оценок (3/4/5) со случайными датами
3. Создать временную директорию с config.json (из postgres-testseed) + seed.json
4. Дропнуть схему в PG → материалнуть через --materialize
5. Поднять data-service на :18084
6. 12 проверок:
   - /health         — 200, status=ok
   - /stats          — counts > 0
   - /disciplines    — count совпадает с сгенерированным
   - /teachers?name= — поиск первого преподавателя по ФИО, full_name совпадает
   - /openapi.json   — OpenAPI 3.1.0
   - /docs           — Swagger UI HTML
   - /students/s1    — полное имя совпадает с seed
   - /students/s1/grades — список непустой
   - /students/nonexistent — 404
   - /grades         — 1-80 записей (max_rows из конфига)
   - /schedule       — count совпадает
   - /students       — count совпадает
7. SIGTERM серверу, atexit cleanup
```

#### Запуск

```bash
docker compose up -d db                                              # один раз
uv run python data-service/tests/integration/test_with_faker.py       # дефолт: 10 студентов, 50 оценок

# Кастомный размер
uv run python data-service/tests/integration/test_with_faker.py --students 100 --grades 500
uv run python data-service/tests/integration/test_with_faker.py --seed 42 --students 5 --teachers 2
```

#### Что покрывает и что нет

| Покрыто | Не покрыто |
|---|---|
| PG + faker seed → все эндпоинты | SQLite с faker seed (можно добавить флаг `--driver sqlite`) |
| Детерминированные сиды (`--seed`) | Непредсказуемые коллизии ID |
| `max_rows` (проверяется косвенно: 300 grades → 80 в ответе) | `find` с несуществующим именем — **было** бы покрыто, но `urlopen` без ошибки 404 (работает через httptest в Go-тестах) |
| `read_only=false` для materialize | `read_only=true` для production-режима |

#### Почему faker, а не agent-seedgen

`agent-seedgen` — утилита, живущая в `rag/fixtures/`. У неё свои зависимости
и она генерит `specs/fixtures/seed.json`. Интеграционный тест генерит seed
прямо в памяти — без записи в `specs/fixtures/`, без лишних вызовов uv.

При этом сам `seed.json` валиден — его можно скормить `seed-cli`:

```bash
uv run python data-service/tests/integration/test_with_faker.py --seed 42 --students 20 --out /tmp/seed.json
# ... затем
cd data-service && go run ./cmd/seed-cli/ --seed-path /tmp/seed.json
```

### Добавление новой БД (например MySQL)

1. Реализовать `datasource.Adapter` для нового драйвера
2. Зарегистрировать в `datasource/registry.go`
3. Если плейсхолдеры отличаются от `?` и `$1` — добавить новый `PlaceholderFunc`
4. Создать сценарий `testdata/scenarios/mysql-testseed/` с подходящим `custom_queries`
5. `--materialize` + тесты

Вся логика обработки запросов (`runtime/`, `server/`, `openapigen/`) не меняется —
она работает через `database/sql` и не зависит от драйвера.

## Тестирование

### Быстрый запуск

```bash
# Все Go-тесты (178+ в 5 пакетах)
go test ./internal/... -count=1

# Только unit-тесты runtime/configgen/datasource
go test ./internal/configgen/... ./internal/runtime/... ./internal/datasource/...

# Сценарии (in-memory SQLite)
go test ./internal/server/... -run TestScenario -v

# Интеграционный тест (faker + PostgreSQL в Docker)
docker compose up -d db
uv run python data-service/tests/integration/test_with_faker.py
uv run python data-service/tests/integration/test_with_faker.py --students 50 --grades 200
```

### Тестовая инфраструктура сценариев

Все сценарии покрываются Go-тестами в `internal/server/`:

| Тест | Сценарий | Что проверяет |
|---|---|---|
| `TestScenario_SqliteTestseed` | sqlite-testseed | Базовый смоук (8 subtests: health, students, grades, teachers, disciplines, stats, openapi, custom_query) |
| `TestScenario_Shop` | shop | Сторонняя БД + get_by_id для каждой entity + 6 custom_queries + 404 |
| `TestScenario_BigTestseed` | big-testseed | Большой набор данных: 500 студентов, 4000 оценок, латентность, пагинация, no-panic |
| `TestEdgeCases_*` | sqlite-testseed | Malformed inputs: длинные ID, unicode, спецсимволы, POST вместо GET, 100 параллельных |
| `TestCustomQueries_Shop_*` | shop | Позитив+негатив на все 6 FK-lookups (пустые результаты для несуществующих id) |
| `TestConcurrency_*` | sqlite-testseed | Heavy load (500 reqs/20 goroutines) на file-based SQLite с WAL; проверка server-alive после burst |
| `Benchmark*` | big-testseed | 8 бенчмарков: GetByID, Find, CustomQuery (grades/schedule/all), Health, OpenAPI generation |
| `FuzzEndpoints`, `FuzzQueryParams` | sqlite-testseed | Random-path/param fuzzers |

### Запуск отдельных категорий

```bash
# Только большие тесты (big-testseed + edge + custom + concurrency)
cd data-service && CONFIG_SCHEMA=$PWD/../specs/config.schema.json \
  go test ./internal/server/... -run "TestScenario_BigTestseed|TestEdgeCases|TestCustomQueries|TestConcurrency" -v

# Только бенчмарки
cd data-service && go test -bench=. -benchtime=10s -run=NONE ./internal/server/... | grep ns/op

# Только fuzzing
cd data-service && go test -fuzz=FuzzQueryParams -fuzztime=30s ./internal/server/...

# Только cross-driver parity (нужен docker compose up -d db)
docker compose up -d db
cd data-service && AGENT_TUTOR_TEST_PG=1 go test ./internal/server/... -run TestCrossDriver -v
```

### Документированные поведения (НЕ баги)

| Поведение | Где | Когда |
|---|---|---|
| `GET /students?name=` (пустая строка) возвращает ВСЕ записи, не 404 | `TestEdgeCases_QueryParams/empty_name_query` | by design: пустой фильтр игнорируется |
| In-memory SQLite при 100+ параллельных запросах отдаёт ~89% 5xx (SQLITE_BUSY) | `TestEdgeCases_DuplicateInsertions/100_concurrent_same_no_panic` | by design: используйте file-based SQLite + WAL или PG для concurrency |
| SQLite отдаёт `lessons_json` (JSON-строка), PG — раскрытый массив `lessons` | cross-driver parity test | legacy, не исправлено (требует переписывать custom_queries на два диалекта) |
| URL длиной >64KB возвращает 5xx на in-memory | `TestEdgeCases_QueryParams/very_long_query` | middleware лимит URL — TODO для production |

Python-тесты (MCP, API, Web) стучатся к data-service по HTTP и не знают о его внутренней архитектуре.

## Roadmap

Полный план и мотивация — в `doc/NEW_ROADMAP.md`. Ниже статус фаз, касающихся data-service.

### Выполнено ✅

| Фаза | Содержание | Отклонения |
|---|---|---|
| 3.0 | JSON Schema конфига + Adapter interface | — |
| 3.1 | Postgres driver (`pgx/v5`) + introspector | `lib/pq` отвергнут |
| 3.2 | Config loader + Query/Endpoint builder | Конфиг в `agent-tutor-go/config/` (общий модуль); `RUNTIME_MODE` не понадобился |
| 3.3 | Удаление domain-кода (`repository/`, `handlers/`, `models/`, `schema.sql`) | — |
| 3.4 | MCP-сервер на Go, инструменты из конфига, обязательный `/mcp/manifest` | Runtime source of truth |
| 3.5 | Generic SDK контракты (`Entity` вместо доменных моделей) | Старые `contracts/` удалены без deprecation |

### Предстоит ❌

| Фаза | Содержание | Оценка |
|---|---|---|
| 3.6 | Generic Web UI (рендер по схеме endpoint'а) | 2–3 недели |
| 3.7 | Multi-tenancy, admin API, hot reload конфига | 2 недели |
| 3.8 | Generic fixtures (`agent-seedgen` для любого конфига) | опционально, 1–2 недели |
| 3.9 | UI-конфигуратор | отдельный roadmap |

### Открытые вопросы (см. `doc/NEW_ROADMAP.md` §14)

- **Q3** — Версионирование конфигов: platform-БД или git?
- **Q4** — Multi-tenancy: `X-Tenant-ID` или multi-instance?
- **Q7** — Объединять data-service + mcp-gateway? (после 3.7)
- **Q9** — Web получает метаданные через `/mcp/manifest` или `/entities`?
- **Q10** — Local fallback `config.json` в mcp-gateway?
