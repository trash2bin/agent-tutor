# AGENTS.md

Управление проектом для разработчиков и AI-агентов.

## Проект

- Полноценный агент с разделёнными сервисами: `mcp`, `rag`, `api`, `web` как long-running сервисы, и CLI-утилиты `agent-ingest`, `agent-generate` как one-shot команды.
- Управление зависимостями и запуском — через `uv` и `pyproject.toml`.
- Все сервисы запускаются независимо и общаются друг с другом по HTTP.
- CLI для документов и генерации: `agent-ingest` (RAG-документы), `agent-generate` (генерация материалов). Детали в `fixtures/README.md`
- База данных: **SQLite** (по умолчанию) или **PostgreSQL** (через `DATABASE_URL`). Абстракция в `db/connector.py`.

## Базовые команды

```bash
uv sync
uv run agent-tutor              # MCP-сервер (порт 8083, HTTP-транспорт)
uv run agent-rag                # RAG HTTP-сервис (порт 8082)
uv run agent-chat-api           # API сервер с агентом (порт 8081)
uv run agent-demo-web           # Веб-сервер (порт 8080)
uv run agent-ingest --help      # CLI для работы с RAG-документами
uv run agent-generate --help    # CLI для генерации учебных материалов
uv run pytest                   # Запуск тестов (unit и integration)
```

После изменений в логике API или RAG — запускай тесты для проверки регрессий.

## Способы запуска

| Способ | Платформа | Команда |
|---|---|---|
| **Нативный** (через `uv`) | Mac (Apple Silicon), Linux, наверное и Windows | `./scripts/dev.sh start` |
| **Docker** | Linux / предпрод / прод | `docker compose up -d` |
| **Docker + HTTPS** | Прод | `docker compose --profile prod up -d` |

Код сервисов один и тот же, разница только в оркестрации.

### 🖥️ Нативный запуск (Mac)

**Скрипт**: `scripts/dev.sh` — поднимает все 4 long-running сервиса в фоне, ждёт `/health` каждого.

```bash
./scripts/dev.sh start         # Поднять все сервисы
./scripts/dev.sh status        # Проверить статус
./scripts/dev.sh logs api      # tail -f .data/logs/api.log
./scripts/dev.sh logs all      # tail -f всех сразу
./scripts/dev.sh stop          # Остановить всё
./scripts/dev.sh restart       # Перезапустить
```

Логи: `.data/logs/{rag,mcp,api,web}.log`. PID-файлы: `.data/pids/*.pid`. `.env` грузится автоматически.

**Порядок ожидания**: `rag → mcp → api → web` (каждый ждёт `/health` предыдущего, таймаут 60с).

### 🐳 Docker-запуск (Linux / предпрод / прод)

**Файлы контейнеризации**:

| Файл | Назначение |
|---|---|
| `rag/Dockerfile` | Образ RAG-сервиса |
| `mcp_server/Dockerfile` | Образ MCP-сервера |
| `demo/api/Dockerfile` | Образ API-сервера |
| `demo/web/Dockerfile` | Образ WEB-сервера |
| `tools/Dockerfile` | Образ CLI-утилит (agent-ingest, agent-generate, backup) |
| `docker-compose.yml` | Оркестрация: 7 сервисов, healthchecks, volumes |
| `Caddyfile` | HTTPS-прокси через Caddy (профиль prod) |
| `.env.example` | Полный список переменных с дефолтами |
| `.dockerignore` | Исключения для Docker build |

```bash
# Dev-режим: 4 long-running сервиса
docker compose up -d

# Prod-режим: + Caddy (HTTPS через Let's Encrypt)
docker compose --profile prod up -d

# CLI-утилиты (one-shot)
docker compose --profile tools run --rm agent agent-ingest list
docker compose --profile tools run --rm agent agent-generate generate -d "cs-101"

# Бэкапы SQLite каждые 6 часов
docker compose --profile cron up -d

# Сборка образов
docker compose build
```

**Healthchecks**: `rag` (start_period=120s — cold start embedding), `mcp` → ждёт `rag`, `api` → ждёт `mcp`, `web` → ждёт `api`.

**Тома (в `./.data/`)**:

| Том | Контейнер-путь | Содержимое |
|---|---|---|
| `app_data` | `/data/app` | `university.db`, `demo_sessions.sqlite`, `backlog/` |
| `rag_data` | `/data/rag` | `chroma_db/` |
| `hf_cache` | `/home/app/.cache/huggingface` | embedding-модели |
| `pg_data` | `/var/lib/postgresql/data` | PostgreSQL-данные |
| `backups` | `/data/backups` | `.db.gz` снапшоты |

### 🐘 PostgreSQL (опционально, вместо SQLite)

По умолчанию — SQLite (`university.db`). Для PostgreSQL задай `DATABASE_URL`:

```bash
# Локальный PostgreSQL через Docker
docker compose up -d db

# Запуск сервисов с PostgreSQL
DATABASE_URL=postgresql://tutor:tutor@127.0.0.1:5432/agent_tutor ./scripts/dev.sh start

# Или через .env
echo 'DATABASE_URL=postgresql://tutor:tutor@127.0.0.1:5432/agent_tutor' >> .env
```

**Важно**: сессии чата (`demo_sessions.sqlite`) пока на SQLite — это кэш, а не основные данные.

### 🧪 Запуск по одному (ручная отладка)

```bash
# Терминал 1: RAG
RAG_PORT=8082 uv run python -m rag.service

# Терминал 2: MCP
RAG_SERVICE_URL=http://127.0.0.1:8082 MCP_PORT=8083 uv run python -m mcp_server.server

# Терминал 3: API
MCP_SERVICE_URL=http://127.0.0.1:8083/mcp DEMO_API_PORT=8081 uv run python -m demo.api.server

# Терминал 4: WEB
DEMO_API_HOST=127.0.0.1 DEMO_API_PORT=8081 DEMO_WEB_PORT=8080 uv run python -m demo.web.server
```

## Структура проекта

```
agent-tutor/
├── mcp_server/              # MCP-сервер (FastMCP, HTTP :8083)
│   ├── server.py
│   └── tools/
│       ├── student.py
│       ├── disciplines.py
│       ├── grades.py
│       ├── teacher.py
│       └── rag.py           # Фасад → RagClient
├── rag/                     # RAG HTTP-сервис (FastAPI, :8082)
│   ├── service.py           # /health /search /context /documents/*
│   ├── client.py            # HTTP-клиент для MCP и других сервисов
│   ├── pipeline.py          # парсинг → чанкинг → embedding → ChromaDB
│   ├── embeddings.py        # SentenceTransformerEmbedding
│   ├── vector_store.py      # ChromaDBVectorStore
│   ├── repository.py        # CRUD документов в SQLite/PostgreSQL
│   ├── parser.py            # DocumentParser (PDF, DOCX, TXT, MD, HTML)
│   ├── chunker.py           # TextChunker (semantic, recursive, sentence)
│   ├── models.py            # Pydantic-модели домена
│   ├── interfaces.py        # EmbeddingProtocol, VectorStoreProtocol
│   ├── config.py            # RagConfig из env
│   └── http_models.py       # Pydantic DTO для HTTP-контракта
├── db/                      # Абстракция БД (SQLite / PostgreSQL)
│   ├── connector.py         # Connector, SqliteConnector, PostgresConnector
│   ├── connection.py        # Реэкспорт для обратной совместимости
│   ├── database.py          # Фасад Database с CRUD
│   ├── schema.py            # DDL для обеих БД (идемпотентный)
│   ├── fixtures.py          # Загрузчик test-data / fixtures.json
│   └── models.py            # Pydantic-модели (реэкспорт из rag.models)
├── demo/
│   ├── settings.py          # Все env-переменные demo-части
│   ├── api/
│   │   ├── server.py        # FastAPI — /health /api/data /api/chat /api/backlog
│   │   ├── http_models.py   # Pydantic DTO для API
│   │   ├── backlog.py       # JSONL-бэклог взаимодействий с моделью
│   │   ├── data.py          # Репозиторий данных для демо
│   │   ├── sessions.py      # Хранилище сессий (SQLite)
│   │   └── agent/
│   │       ├── orchestrator.py  # Оркестратор агента
│   │       ├── llm_client.py    # Клиент LiteLLM
│   │       ├── mcp_client.py    # HTTP-клиент к MCP
│   │       ├── tool_parser.py   # Парсер вызовов инструментов
│   │       ├── types.py         # Типы событий SSE
│   │       └── conversation.py  # Управление историей диалога
│   └── web/
│       ├── server.py        # FastAPI reverse-proxy + SSE-прокси + статика
│       └── static/          # HTML/CSS/JS
├── fixtures/
│   ├── generate.py          # Генератор fixtures.json (Faker)
│   ├── ingest.py            # CLI agent-ingest
│   └── document_generator.py  # Генерация материалов через Ollama
├── scripts/
│   ├── dev.sh               # Нативный запуск всех сервисов
│   ├── backup.py            # Бэкап SQLite
│   └── init-db.sql          # Инициализация PostgreSQL
├── tests/
│   ├── conftest.py
│   ├── unit/                # rag/, db/, tools/, demo/
│   └── integration/         # rag/ (e2e-тесты)
├── doc/                     # ROADMAP.md, TASK.md
├── docker-compose.yml
├── Dockerfile               # Корневой Dockerfile (не используется — каждый сервис свой)
├── Caddyfile                # HTTPS-прокси для prod-профиля
├── .env.example             # Все переменные окружения
└── fixtures.json            # Тестовые данные
```

## Инструменты MCP-сервера

Модель может вызывать инструменты для доступа к данным об учебном процессе:

| Инструмент | Что делает |
|---|---|
| `get_student(student_id)` | Карточка студента |
| `find_student_by_name(name)` | Поиск студента по ФИО |
| `get_schedule(group_id, day?)` | Расписание группы, опционально по дню |
| `get_disciplines(student_id)` | Дисциплины студента через его группу |
| `get_materials(discipline_id, type?)` | Список файлов по дисциплине |
| `search_materials(query, discipline_id?)` | Поиск по содержимому материалов |
| `get_student_grades(student_id, discipline_id?)` | Оценки студента, опционально по одной дисциплине |
| `get_teacher_by_name(name)` | Поиск преподавателя |
| `get_teacher_schedule(teacher_name, day?)` | Расписание преподавателя |
| `list_documents(discipline_id?)` | Список документов в RAG-индексе |
| `search_documents(query, discipline_id?, limit?)` | Поиск релевантных фрагментов документов |
| `get_rag_context(query, discipline_id?, limit?)` | Готовый контекст для ответа по документам |

> `import_document` доступен только через CLI `agent-ingest`, не через MCP.

## Демо-часть

**API сервер** (`demo/api/server.py`) — обрабатывает запросы к LLM-провайдерам через LiteLLM и MCP-серверу, обеспечивает вызов инструментов и управление контекстом агента.  
**Веб-сервер** (`demo/web/server.py`) — отдаёт статические файлы интерфейса и проксирует запросы к API (reverse-proxy + SSE-прокси).

Ядро агента — `demo/api/agent/`:
- `orchestrator.py` — оркестратор: вызов моделей, подключение к MCP, рекурсивные вызовы, стриминг
- `llm_client.py` — клиент для работы с LLM через LiteLLM
- `mcp_client.py` — HTTP-клиент для MCP-сервера
- `tool_parser.py` — парсер вызовов инструментов (native + JSON-форматы)
- `types.py` — типы SSE-событий
- `conversation.py` — управление памятью диалога

### Ключевые особенности агента

- **LiteLLM**: единый клиент для Ollama, OpenAI, Mistral, Anthropic, Groq и др.
- **Режим мышления**: `reasoning_content` через `ENABLE_THINK=true`
- **Стриминг SSE**: события `token`, `tool_call`, `tool_result`, `final`, `error`
- **Память сессий**: `DEMO_HISTORY_TURNS` последних ходов (по умолчанию 8), ограничение `DEMO_HISTORY_CONTENT_CHARS` (6000)
- **Бэклог**: JSONL-файлы всех запросов/ответов/инструментов/токенов/таймингов в `./backlog/`

## Архитектура RAG

Пакет `rag/` не зависит от `db/` — циклическая зависимость разорвана.  
`DocumentRepository` принимает сырой `sqlite3.Connection` / `psycopg.Connection`.

RAG — отдельный HTTP-сервис (`rag/service.py` на FastAPI, порт 8082) с HTTP-клиентом (`rag/client.py`).

- `rag/interfaces.py` — протоколы `EmbeddingProtocol`, `VectorStoreProtocol`
- `rag/embeddings.py` → `SentenceTransformerEmbedding`
- `rag/vector_store.py` → `ChromaDBVectorStore`
- `rag/pipeline.py` — оркестрация парсинг → чанкинг → сохранение
- `rag/repository.py` — CRUD документов
- `rag/service.py` — эндпоинты: `/health`, `/search`, `/context`, `/documents/*`
- `rag/http_models.py` — Pydantic-модели HTTP-контракта

### Стандартизация API (OpenAPI/Swagger)

Все HTTP-сервисы (`rag`, `api`, `web`) на FastAPI со Swagger UI:
- RAG: `http://127.0.0.1:8082/docs`
- API: `http://127.0.0.1:8081/docs`
- Web: `http://127.0.0.1:8080/docs`

При изменении API обновляй Pydantic-модели в `rag/http_models.py` и `demo/api/http_models.py`.

## Документы и RAG

RAG-слой работает через SQLite/PostgreSQL + ChromaDB:

1. `agent-ingest import <file>` — читает PDF / DOCX / TXT / MD / HTML
2. Текст разбивается на чанки (`RAG_CHUNKER_TYPE`: `semantic`, `recursive`, `sentence`)
3. Для каждого чанка считается embedding (`paraphrase-multilingual-MiniLM-L12-v2`)
4. Векторы → ChromaDB, метаданные → SQLite/PostgreSQL
5. `search_documents` — поиск ближайших фрагментов по cosine similarity
6. `get_rag_context` — готовый контекст с инструкцией для модели

```bash
uv run agent-ingest import ./lectures/lec01.pdf -d "cs-101" -t "Лекция 1: Введение"
uv run agent-ingest list
uv run agent-ingest search "быстрая сортировка" -n 3
uv run agent-ingest delete --document-id <id>
```

> `agent-ingest` принудительно выставляет `RAG_LOCAL_FILES_ONLY=1` — embedding-модель должна быть в локальном кэше.

## Генерация материалов

```bash
uv run agent-generate generate -d <discipline-id>   # Материалы одной дисциплины
uv run agent-generate generate-all                   # Всех дисциплин
uv run agent-ingest clear-generated                  # Удалить сгенерированное
```

Требует Ollama. Проверка: `curl ${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags`.

## Важные переменные окружения

| Переменная | Дефолт | Описание |
|---|---|---|
| `DATABASE_URL` | (пусто → SQLite) | `postgresql://user:pass@host:port/dbname` |
| `DB_PATH` | `./university.db` | Путь к SQLite |
| `CHROMA_PATH` | `./chroma_db` | Папка ChromaDB |
| `RAG_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | HF-id или локальный путь |
| `RAG_SERVICE_URL` | `http://127.0.0.1:8082` | URL RAG-сервиса |
| `MCP_SERVICE_URL` | `http://127.0.0.1:8083/mcp` | URL MCP-сервиса |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Адрес Ollama |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Модель Ollama |
| `MISTRAL_API_KEY` | — | Ключ Mistral API |
| `DEMO_REQUEST_TIMEOUT` | `600` | Таймаут turn агента (сек) |
| `BACKLOG_DIR` | `./backlog/` | Папка JSONL-бэклога |
| `ENABLE_THINK` | `true` | Режим мышления |

Полный список — в `.env.example`.

## Пример запроса к модели

```json
{
  "tool_name": "find_student_by_name",
  "parameters": {
    "name": "Иван Петров Иванович"
  }
}
```

Пример вопроса пользователя:
```
Какие материалы доступны студенту Ивану Петрову Ивановичу по его дисциплинам?
```

## Текущее состояние

Проект на стадии **pre-prod прототипа**. **Выполнены этапы 0–2 из ROADMAP**:

- **Этап 0** (0.0–0.5): Разделение на 4 независимых HTTP-сервиса, FastAPI, CLI-утилиты, HTTP-транспорт MCP
- **Этап 1**: Тестовая инфраструктура (84% покрытие, 109 тестов, ruff, OpenAPI/Swagger)
- **Этап 2**: Контейнеризация (5 Dockerfile'ов, docker-compose с 7 сервисами, Caddy, healthchecks, backup)

Работает:
- MCP-сервер (FastMCP, HTTP-транспорт, `/health` endpoint)
- RAG HTTP-сервис (FastAPI, ChromaDB + SQLite/PostgreSQL)
- API-сервер с агентом (FastAPI, LiteLLM, SSE-стриминг, память сессий, бэклог)
- Веб-интерфейс (FastAPI, reverse-proxy, SSE-прокси)
- База: SQLite (по умолчанию) или PostgreSQL (через `DATABASE_URL`)
- `db/connector.py` — абстракция над SQLite/PostgreSQL
- `scripts/dev.sh` — нативный запуск всех сервисов
- Docker: 5 образов, docker-compose, Caddy, backup-сервис, healthchecks
- 109 тестов, 84% покрытие, ruff чисто
- OpenAPI/Swagger у всех HTTP-сервисов

## Осторожность

- Не удаляй `university.db`, `chroma_db/`, `generated_materials/` без явной необходимости.
- **Не удаляй `./backlog/`** — там истории чатов и трассировки взаимодействий с моделью.
- В рабочем дереве могут быть пользовательские изменения. Не откатывай без просьбы.
- Не коммить изменения без прямой просьбы пользователя.
