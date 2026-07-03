# AGENTS.md — Технический паспорт проекта для AI-агентов

Этот документ является основной точкой входа для AI-агента. Он содержит архитектурный контекст, карту навигации и операционные инструкции, необходимые для внесения изменений в код без потери целостности системы.

## 🎯 1. О проекте и видении
**Проект**: Платформа для развертывания AI-агентов над произвольными базами данных клиентов.
**Текущий вектор**: Трансформация из доменного решения (один вуз) в **Generic B2B SaaS**.

**Ключевая идея**: Клиент подключает свою БД $\rightarrow$ Платформа интроспектирует схему $\rightarrow$ Автоматически генерируется REST API и MCP-инструменты $\rightarrow$ AI-агент получает доступ к данным без написания кода под каждую БД.

### 🔄 Архитектурный Pipeline (Как это работает)
Путь запроса от пользователя до данных:
`User Request` $\rightarrow$ `demo-web` (проксирует `X-Tenant-ID`) $\rightarrow$ `demo-api` (формирует Persona агента и системный промпт) $\rightarrow$ `mcp-gateway` (динамически запрашивает манифест инструментов из data-service для конкретного TenantID) $\rightarrow$ `data-service` (роутит запрос в конкретную БД клиента через `TenantStore` $\rightarrow$ generic query builder $\rightarrow$ SQL $\rightarrow$ DB).

---

## 🛠️ 2. Карта сервисов и навигация
Каждый сервис независим и общается по HTTP. Для детального изучения архитектуры каждого модуля используйте ссылки ниже.

| Сервис | Порт | Ответственность | Документация (Кликабельно) |
|---|---|---|---|
| **Data-service** (Go) | `:8084` | Generic CRUD/Query прокси. Интроспекция БД, генерация API. | [data-service/README.md](data-service/README.md) |
| **MCP-gateway** (Go) | `:8083` | MCP сервер (SSE/JSON-RPC). Динамическая генерация инструментов из data-service. | [mcp-gateway/README.md](mcp-gateway/README.md) |
| **RAG** (Python) | `:8082` | Поиск по документам (ChromaDB), чанкинг, эмбеддинги. | [rag/README.md](rag/README.md) |
| **API** (Python) | `:8081` | Оркестратор агента, LiteLLM, управление сессиями и бэклогом. | [demo/api/agent/AGENT_WORKFLOW.md](demo/api/agent/AGENT_WORKFLOW.md) |
| **Web** (Python) | `:8080` | UI-интерфейс + reverse-proxy. Проксирует `X-Tenant-ID` в data-service/API/RAG. Поддерживает маршруты `/api/tenant/{tenant_id}/...` для явного указания тенанта и `/api/data/*` для прямого доступа к данным. | [demo/web/README.md](demo/web/README.md) |
| **SDK** (Python) | — | Общие Pydantic-модели (`Entity`) и клиенты для сервисов. | [agent-tutor-sdk/README.md](agent-tutor-sdk/README.md) |

### 🚩 Глобальные документы

**UI**: tenant selector в интерфейсе (`app.js`) — переключение между tenant'ами через выпадающий список.
- **Стратегия и План**: [doc/NEW_ROADMAP.md](doc/NEW_ROADMAP.md) — текущие фазы, карта хардкода и целевое состояние SaaS.
- **Конфигурация**: [.env.example](.env.example) — все 180+ переменных окружения.
- **Схема БД/API**: [specs/config.example.json](specs/config.example.json) — Source of Truth для структуры данных.

### 🌐 Web Service — Multi-Tenancy Architecture

Web-сервис (`demo/web/server.py`) — тонкий reverse-proxy с поддержкой multi-tenancy:

**Два режима маршрутизации:**

1. **Стандартный (через заголовок `X-Tenant-ID`):**
   ```
   Browser → GET /api/data/students (X-Tenant-ID: tenant-a)
          → web:8080
          → data-service:8084/students (X-Tenant-ID: tenant-a)
   ```

2. **Явный tenant в URL (демо-режим):**
   ```
   Browser → GET /api/tenant/tenant-a/data/students
          → web:8080
          → data-service:8084/students (X-Tenant-ID: tenant-a)
   ```

**Ключевые маршруты:**
- `GET /api/manifest` → data-service `/mcp/manifest` (с tenant)
- `GET /api/data/{entity}` → data-service `/{entity}` (students, teachers, disciplines...)
- `GET /api/data/stats` → data-service `/stats`
- `GET /api/rag/documents` → rag-service `/documents/list`
- `GET/POST /api/chat` → api-service `/api/chat` (SSE)
- `GET/POST /api/tenant/{tenant_id}/{path:path}` — универсальный маршрут:
  - `data/{entity}` → data-service
  - `rag/{path}` → rag-service
  - `api/{path}` / `chat` → api-service (SSE для chat)

**Реализация в `proxy_tenant_api`:**
```python
@app.api_route("/api/tenant/{tenant_id}/{path:path}")
async def proxy_tenant_api(request, tenant_id, path):
    request.state.tenant_id = tenant_id  # сохраняем для _get_proxy_headers
    if path.startswith("data/"):
        return await _proxy_to_data_service(request, f"/{path.replace('data/', '', 1)}")
    elif path.startswith("rag/"):
        return await _proxy_to_rag(request, "/documents/list", method="POST", json_body={})
    else:
        api_path = path.replace("api/", "", 1) if path.startswith("api/") else f"api/{path}"
        return await _proxy_to_api(request, f"/{api_path}", stream=(path=="chat" and is_post))
```

**Headers forwarding в `_get_proxy_headers`:**
```python
tenant_id = request.headers.get("X-Tenant-ID")
if not tenant_id and hasattr(request.state, "tenant_id"):
    tenant_id = request.state.tenant_id
if tenant_id:
    headers["X-Tenant-ID"] = tenant_id
```

**Тесты:**
```bash
uv run pytest demo/web/tests/unit/test_proxy.py -v  # 26 тестов включая TestTenantRoutingProxy
uv run agent-db e2e-full                             # полный e2e пайплайн
```

---

## 🚀 3. Эксплуатация и разработка (Manual)

### 🛠️ Нативный запуск: `scripts/dev.sh`
Скрипт `dev.sh` — основная точка управления в среде Mac/Linux.

**Управление сервисами:**
- `./scripts/dev.sh start` — поднять весь стек в правильном порядке (data $\rightarrow$ rag $\rightarrow$ mcp $\rightarrow$ api $\rightarrow$ web).
- `./scripts/dev.sh stop` / `restart` / `status` — управление жизненным циклом.
- `./scripts/dev.sh logs {service|all}` — просмотр логов из `.data/logs/`.

### 🐳 Docker-запуск
Если нативная среда недоступна или требуется изоляция:
- `docker compose up -d` — запуск всех 5 сервисов в Dev-режиме.
- `docker compose --profile prod up -d` — запуск с Caddy (HTTPS через Let's Encrypt) для Production.
- `docker compose build` — пересборка образов после изменений в Dockerfile.
- **Тома**: Данные хранятся в `./.data/` (БД, индексы ChromaDB, кэш моделей).

### 🗄️ Работа с данными и сценариями (Критично для тестов)
Сервис `data-service` поддерживает фабрику тестовых БД через CLI-утилиту `agent-db`.
- `uv run agent-db scenario list` — список сценариев (`sqlite-testseed`, `big-testseed`, `shop`...).
- `uv run agent-db materialize <name>` — создать/пересоздать БД из сценария.
- `uv run agent-db tenant register <name>` — зарегистрировать тенанта.
- `uv run agent-db tenant list` — список активных тенантов.
- `uv run agent-db e2e --tenants default,shop` — полный E2E: materialize + register + proxy + SSE chat.
- `uv run agent-db e2e-data` — детерминированные тесты изоляции данных и admin API.
- `uv run agent-db e2e-mcp` — детерминированные тесты MCP-инструментов.
- `uv run agent-db e2e-full` — все три уровня (data + mcp + chat).

---

## 🧪 4. Регрессионное тестирование
Перед коммитом или после правок **обязательно** проверить следующие уровни:

### 1. Python Unit/Integration тесты
```bash
uv run pytest rag/tests/            # Проверка индексации и поиска RAG
uv run pytest demo/api/tests/       # Проверка оркестрации агента и MCP-клиента
uv run pytest demo/web/tests/       # Проверка проксирования запросов
uv run pytest agent-tutor-sdk/tests/ # Проверка generic-моделей Entity
```

> Примечание: 10 тестов MCP-клиента и оркестратора помечены `@pytest.mark.skip` — ожидают переписывания под новый MCP SDK протокол.

### 2. Go Unit/Integration тесты
```bash
go test ./data-service/... ./mcp-gateway/...  # 274 тестов в 14 пакетах
```

### 3. Сквозные интеграционные скрипты
- `uv run agent-db e2e-data` — изоляция данных между tenant'ами (8 детерминированных тестов).
- `uv run agent-db e2e-mcp` — динамические MCP-инструменты (3 детерминированных теста).
- `uv run agent-db e2e-full` — все три уровня: data + mcp + SSE chat.

---

## 🧠 5. Использование Knowledge Graph (Graphify)

Проект содержит граф зависимостей (`graphify-out/`). **Не читай код вслепую — используй граф.**

**Алгоритм работы для агента:**
1. **Ориентирование**: Вместо `grep` используй `graphify_explain({ concept: "ClassName" })`, чтобы увидеть всех, кто вызывает этот класс и от кого он зависит.
2. **Трассировка**: Чтобы понять, как данные текут от API до БД, используй `graphify_path({ from: "APIHandler", to: "DatabaseAdapter" })`.
3. **Поиск**: Используй `graphify_query({ question: "...", mode: "bfs" })` для поиска взаимосвязей в архитектуре.
4. **Обновление**: После внесения правок в код выполни `graphify_update({ path: "." })`, чтобы граф оставался актуальным.

---

## ⚠️ 6. Важные ограничения и правила
- **Никакого SQL в Python**: Весь доступ к университетским данным идет ТОЛЬКО через HTTP-запросы к `data-service`.
- **Generic-подход**: При добавлении новых полей или сущностей не хардкодь их в коде, наша цель оформить по-максимум рабочий generic подход без прямой правки конфигов (это будет задача из ui).
- **Stateless**: Сервисы не должны хранить состояние сессии локально (кроме кэша сессий в SQLite), чтобы обеспечить масштабируемость.
