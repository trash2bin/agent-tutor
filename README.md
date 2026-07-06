# agent-tutor

LLM-агент для университетского ассистента. Даёт языковой модели доступ к учебным данным (студенты, расписание, оценки, материалы) через MCP-инструменты и семантический поиск по документам.

Пять независимых HTTP-сервисов на двух языках + CLI-утилиты. Работает с Ollama, Mistral, OpenAI и любым провайдером через LiteLLM.

## Архитектура

```
                  HTTP (JSON Schema / X-Tenant-ID)
mcp-gateway:8083 ──────────→ data-service:8084 (Go) ──SQL──→ БД (SQLite/PG)
    │  HTTP (OpenAPI / X-Tenant-ID)
    └──────────────────────→ rag:8082 ──────────────→ ChromaDB

web:8080 ─┬→ api:8081 ─→ mcp-gateway:8083 ─→ data-service (инструменты)
          │                                └→ rag (документы)
          ├→ data-service:8084 (данные для UI)
          └→ rag:8082 (список документов для UI)
```

**Multi-tenancy**: Система поддерживает полную изоляцию данных и инструментов через заголовок `X-Tenant-ID`.

**Одиночный tenant** (классический режим):
```
X-Tenant-ID: tenant-a  →  инструменты: [list_students, get_grade, ...]
```
`data-service` использует динамический `TenantStore` (in-memory реестр конфигов и соединений с БД), а `mcp-gateway` работает как stateless-прокси, разрешая инструменты на лету из манифеста текущего тенанта.

**Composite multi-tenant** (новое):
Одна SSE сессия может обслуживать несколько tenant'ов одновременно. Инструменты получают префикс `{tenantID}__`:

```
X-Tenant-ID: tenant-a,tenant-b  →  инструменты: [tenant-a__list_students, tenant-b__list_products]
```

Каждый инструмент жёстко зафиксирован за своим tenant'ом через замыкание (closure) — подмена заголовка X-Tenant-ID в POST-запросе не меняет маршрутизацию.

Подробнее: [mcp-gateway/README.md](mcp-gateway/README.md) → раздел "Composite Multi-Tenant Mode".

### Composite Multi-Tenant

С версии 0.3.0 mcp-gateway поддерживает **composite multi-tenant mode**: одна SSE сессия может обслуживать несколько tenant'ов одновременно.

```
# Один tenant (backward compat, без префикса)
X-Tenant-ID: tenant-a  →  tools: [list_students, get_student]

# Несколько tenant'ов (composite, с префиксом {tenantID}__)
X-Tenant-ID: tenant-a,tenant-b  →  tools: [tenant-a__list_students, tenant-b__list_products]
```

**Как это работает:**
1. Клиент передаёт `X-Tenant-ID: tenant-a,tenant-b` (comma-separated)
2. mcp-gateway парсит список через `resolveTenantIDs()` → `["tenant-a", "tenant-b"]`
3. Если tenant'ов > 1: создаётся `CompositeMCPServer`, который аггрегирует инструменты от всех tenant'ов
4. Каждый инструмент получает префикс `{tenantID}__` для избежания конфликтов имён
5. При вызове `tenant-a__list_students` хендлер направляет запрос в data-service с `X-Tenant-ID: tenant-a`
6. Backward compat: один tenant = без префикса (поведение не изменилось)

**Где используется:** `api-service` (оркестратор агента) передаёт `tenant_ids: list[str]` в MCPClient, который формирует comma-separated заголовок. SSE сессия открывается одна, инструменты возвращаются от всех tenant'ов.

| Сервис | Стек | Порт | Назначение |
|---|---|---|---|
| `data-service` | **Go** (chi, modernc/sqlite) | 8084 | Доступ к БД университета. Multi-tenant: динамический `TenantStore` (конфиг $\rightarrow$ БД $\rightarrow$ роутер). Сценарии БД (`testdata/scenarios/`) — фабрика тестовых баз |
| `mcp-gateway` | **Go** (chi, mcp-go) | 8083 | Stateless MCP-сервер. Инструменты разрешаются динамически из `data-service` на основе `X-Tenant-ID` |
| `rag` | FastAPI (Python) | 8082 | Поиск по документам (ChromaDB + SQLite/PostgreSQL) |
| `api` | FastAPI + LiteLLM (Python) | 8081 | Оркестратор агента, динамические промпты под тенанта, MCP-клиент, SSE-стриминг |
| `web` | FastAPI (Python) | 8080 | UI + reverse-proxy. Проксирует `X-Tenant-ID` в data-service/API/RAG. Поддерживает маршруты `/api/tenant/{tenant_id}/...` для явного указания тенанта |

База данных: **SQLite** (по умолчанию) или **PostgreSQL** (через `DATABASE_URL`).
Векторный индекс: **ChromaDB**. Embeddings: **Sentence Transformers** (локально).

## Быстрый старт

```bash
git clone https://github.com/trash2bin/agent-tutor
cd agent-tutor
uv sync

# Установить Go (для data-service и mcp-gateway)
brew install go    # macOS
# или: https://go.dev/dl/

# Запустить все 5 сервисов (Mac / нативный)
./scripts/dev.sh start

# Проверить статус
./scripts/dev.sh status

# Открыть в браузере
open http://127.0.0.1:8080
```

По умолчанию агент ожидает Ollama на `http://127.0.0.1:11434` с моделью `qwen2.5:0.5b`.
Другие провайдеры — через переменные окружения (см. `.env.example`):

```bash
# Mistral
MISTRAL_API_KEY=<token> MISTRAL_MODEL=mistral-medium ./scripts/dev.sh restart

# OpenAI
OPENAI_API_KEY=<token> ./scripts/dev.sh restart
```

### Docker

```bash
docker compose up -d                              # 5 сервисов
docker compose --profile prod up -d               # + Caddy (HTTPS)
```

## Тестовая база

```bash
# 1. Сгенерировать seed-данные (Python + faker)
uv run agent-seedgen --students 80

# 2. Залить в SQLite (Go data-service)
cd data-service && go run ./cmd/seed-cli/ --seed-path ../specs/fixtures/seed.json

# 3. Запустить всё
./scripts/dev.sh start
```

## CLI (Управление данными и тестами)

```bash
# Управление БД и тенантами (единый инструмент)
uv run agent-db materialize university --force    # создать БД из сценария
uv run agent-db tenant register university         # зарегистрировать тенанта в API
uv run agent-db tenant list                        # список активных тенантов
uv run agent-db e2e --tenants default,shop         # полный E2E тест (materialize -> register -> proxy -> chat)
uv run agent-db e2e-data                           # изоляция данных (8 детерминированных тестов)
uv run agent-db e2e-mcp                            # MCP инструменты (3 детерминированных теста)
uv run agent-db e2e-mcp-composite                  # composite MCP multi-tenant тест (3 теста, один SSE канал на несколько tenant'ов)
uv run agent-db e2e-full                           # все три уровня (data + mcp + chat)

# RAG утилиты
uv run agent-rag-ingest import ~/Documents/lecture.pdf -d <discipline-id>
uv run agent-rag-ingest search "квантовые вычисления"
uv run agent-rag-docgen generate -d <discipline-id>

# Генерация сидов
uv run agent-seedgen --students 80
```

## Безопасность (Tenant Isolation)

Система обеспечивает изоляцию данных и инструментов на трёх уровнях:

### 1. Data-service (уровень БД)
`TenantStore` хранит изолированные конфиги и подключения к БД для каждого tenant'а. Каждый tenant имеет свою БД (SQLite файл или PG схему). Запрос к data-service с `X-Tenant-ID: tenant-a` гарантированно идёт только к БД tenant-a.

### 2. mcp-gateway (уровень инструментов)
Каждый MCP-инструмент регистрируется с tenantID в замыкании (closure). Даже если клиент откроет SSE сессию с `X-Tenant-ID: tenant-a,tenant-b`, вызов инструмента `tenant-a__list_students` пойдёт строго в data-service с `X-Tenant-ID: tenant-a`. Инструменты tenant-c не существуют в этой сессии, если tenant-c не был указан в заголовке.

### 3. api-service (уровень потребителя)
Список tenant'ов определяется заголовком `X-Tenant-ID` от web-прокси и передаётся как `tenant_ids: list[str]` через orchestrator в MCPClient. Если tenant не указан в заголовке, его данные и инструменты недоступны.

### Верификация

Все тесты на изоляцию продолжают проходить (см. CLI раздел):
```bash
uv run agent-db e2e-data         # data-level: tenant-a не видит БД tenant-b
uv run agent-db e2e-mcp          # tool-level: tenant-shop не может вызвать list_student tenant-uni
uv run agent-db e2e-mcp-composite # composite: инструменты tenant-uni и tenant-shop префиксованы и роутятся строго в свои data-service
```

Никаких cross-tenant утечек данных или инструментов.

## Разработка

```bash
# Python
uv run pytest                     # 130 тестов
uv run ruff check .
uv run ruff format .

# Go
go test ./data-service/... ./mcp-gateway/...       # 424 тестов в 16 пакетах
go build ./data-service/cmd/server/
go build ./mcp-gateway/cmd/

# E2E тесты (agent-db CLI)
uv run agent-db e2e --tenants default,shop    # полный e2e: materialize → register tenants → proxy + SSE chat
uv run agent-db e2e-data                      # изоляция данных (8 тестов)
uv run agent-db e2e-mcp                       # MCP инструменты (3 теста)
uv run agent-db e2e-mcp-composite             # composite multi-tenant (3 теста)
uv run agent-db e2e-full                      # все три уровня
```

## Структура

```
├── data-service/    Go-доступ к БД университета (:8084), config-driven
├── mcp-gateway/     MCP-сервер (Go, :8083), auto-gen инструментов из конфига
├── rag/             RAG HTTP-сервис (Python, :8082) + CLI-утилиты
├── agent-tutor-sdk/ Контрактные Pydantic-модели + HTTP-клиенты
├── demo/api/        API-сервер + агент (FastAPI, :8081)
├���─ demo/web/        Веб-интерфейс (FastAPI, :8080), reverse-proxy
├── specs/           OpenAPI-спецификации + JSON Schema конфига
├── scripts/         dev.sh (запуск всех сервисов)
└── doc/             NEW_ROADMAP.md, планы
```

## Документация

- **AGENTS.md** — детали для разработчиков и AI-агентов
- **data-service/README.md** — архитектура config-driven Go-сервиса
- **mcp-gateway/README.md** — устройство MCP-сервера
- **doc/NEW_ROADMAP.md** — план развития

## Стек

**Python 3.12+** · **Go 1.24+** · uv · FastAPI · mcp-go · LiteLLM · ChromaDB · Sentence Transformers · SQLite · PostgreSQL · pytest · ruff · Docker
