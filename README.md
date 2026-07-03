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
`data-service` использует динамический `TenantStore` (in-memory реестр конфигов и соединений с БД), а `mcp-gateway` работает как stateless-прокси, разрешая инструменты на лету из манифеста текущего тенанта.

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
uv run agent-db e2e-full                           # все три уровня (data + mcp + chat)

# RAG утилиты
uv run agent-rag-ingest import ~/Documents/lecture.pdf -d <discipline-id>
uv run agent-rag-ingest search "квантовые вычисления"
uv run agent-rag-docgen generate -d <discipline-id>

# Генерация сидов
uv run agent-seedgen --students 80
```

## Разработка

```bash
# Python
uv run pytest                     # 130 тестов
uv run ruff check .
uv run ruff format .

# Go
go test ./data-service/... ./mcp-gateway/...       # 274 тестов в 14 пакетах
go build ./data-service/cmd/server/
go build ./mcp-gateway/cmd/

# E2E тесты (agent-db CLI)
uv run agent-db e2e --tenants default,shop    # полный e2e: materialize → register tenants → proxy + SSE chat
uv run agent-db e2e-data                      # изоляция данных (8 тестов)
uv run agent-db e2e-mcp                       # MCP инструменты (3 теста)
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
