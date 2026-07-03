# Web Service (demo-web)

FastAPI reverse-proxy для multi-tenant архитектуры agent-tutor.

## Роль в системе

`demo-web` — тонкий reverse-proxy, который:
- Обслуживает статический фронтенд (HTML/JS/CSS)
- Проксирует API-запросы к `demo-api:8081` (агент, чат, сессии)
- Проксирует данные напрямую в `data-service:8084` (обход demo/api для снижения latency)
- Проксирует RAG-запросы в `rag:8082` (документы)
- Пробрасывает `X-Tenant-ID` для multi-tenancy изоляции

## Multi-Tenancy поддержка

### Заголовок X-Tenant-ID

Основной механизм идентификации тенанта — HTTP заголовок `X-Tenant-ID`:
```bash
curl -H "X-Tenant-ID: school-a" http://localhost:8080/api/data/students
```

### Два режима маршрутизации

#### 1. Стандартный прокси (с заголовком)

Запросы приходят с `X-Tenant-ID` в заголовке:
```
Browser → /api/data/students (X-Tenant-ID: tenant-a)
       → web:8080
       → data-service:8084/students (X-Tenant-ID: tenant-a)
```

#### 2. Явный tenant в URL (демо-режим)

Для удобства тестирования и демонстрации:
```
Browser → /api/tenant/school-a/data/students
       → web:8080
       → data-service:8084/students (X-Tenant-ID: school-a)
```

## Маршруты

### Статические файлы
- `GET /` — индекс.html
- `GET /static/{path}` — статические ассеты

### Health
- `GET /health` — статус web-сервиса

### Data Service (прямой прокси)
- `GET /api/manifest` — манифест инструментов из data-service
- `GET /api/data/stats` — статистика данных
- `GET /api/data/{entity}` — проксирование к data-service (students, teachers, disciplines и т.д.)

### RAG Service
- `GET /api/rag/documents` — список документов

### API Service (через demo/api)
- `GET /api/health` — health-check API
- `GET /api/backlog` — модель бэклога
- `GET /api/session/history` — история сессий
- `POST /api/chat` — SSE-стриминг чата с агентом

### Tenant Routing (демо-режим)
- `GET|POST|... /api/tenant/{tenant_id}/{path:path}` — универсальный маршрут с tenant в URL:
  - `/api/tenant/{tenant}/data/{entity}` → data-service
  - `/api/tenant/{tenant}/rag/{path}` → rag-service
  - `/api/tenant/{tenant}/api/{path}` → api-service (с SSE для chat)

## Как работает X-Tenant-ID

### Proxy functions

В `server.py` есть три основные proxy-функции:

```python
async def _proxy_to_api(request, api_path, stream=False)
  # Проксирует в demo-api
  # Headers: X-Tenant-ID из request.headers ИЛИ request.state.tenant_id

async def _proxy_to_data_service(request, data_path)
  # Проксирует напрямую в data-service
  # Headers: X-Tenant-ID из request.headers ИЛИ request.state.tenant_id

async def _proxy_to_rag(request, rag_path, method="GET", json_body=None)
  # Проксирует в rag-service
  # Headers: X-Tenant-ID из request.headers ИЛИ request.state.tenant_id
```

### Логика tenant_id в proxy_tenant_api

```python
@app.api_route("/api/tenant/{tenant_id}/{path:path}")
async def proxy_tenant_api(request, tenant_id, path):
    # 1. Сохраняем tenant_id в request.state
    request.state.tenant_id = tenant_id

    # 2. Определяем целевой сервис по префиксу path
    if path.startswith("data/"):
        return await _proxy_to_data_service(request, f"/{path.replace('data/', '', 1)}")
    elif path.startswith("rag/"):
        # Специальный case: rag/documents → POST /documents/list
        return await _proxy_to_rag(request, "/documents/list", method="POST", json_body={})
    else:
        # API service
        api_path = path.replace("api/", "", 1) if path.startswith("api/") else f"api/{path}"
        return await _proxy_to_api(request, f"/{api_path}", stream=is_sse)
```

### Заголовки в _get_proxy_headers

```python
async def _get_proxy_headers(request):
    headers = {
        "user-agent": ...,
        "accept": ...,
        # ... другие заголовки
    }

    # X-Tenant-ID: сначала из HTTP заголовка, затем из request.state
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id and hasattr(request.state, "tenant_id"):
        tenant_id = request.state.tenant_id
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    return headers
```

## Конфигурация

### Environment Variables

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `DEMO_API_HOST` | `127.0.0.1` | Хост API сервиса |
| `DEMO_API_PORT` | `8081` | Порт API сервиса |
| `DEMO_WEB_HOST` | `127.0.0.1` | Хост web сервиса |
| `DEMO_WEB_PORT` | `8080` | Порт web сервиса |
| `WEB_ORIGIN` | `*` | CORS origin |
| `API_BEARER_TOKEN` | — | Опциональный bearer token для API |

### Docker Compose

В `docker-compose.yml` web-сервис запускается с переменными:
```yaml
environment:
  - DEMO_API_HOST=api
  - DEMO_API_PORT=8081
```

## Запуск

### Нативный (Mac/Linux)
```bash
# Через dev.sh
./scripts/dev.sh start

# Или напрямую
uv run --package demo-web python -m demo.web.server
```

### Docker
```bash
docker compose up -d web
```

## Тестирование

### Unit-тесты
```bash
uv run pytest demo/web/tests/unit/test_proxy.py -v   # 26 тестов (включая TestTenantRoutingProxy)
```

### E2E-тесты
```bash
# Полный пайплайн: materialize БД → register tenants → proxy check → SSE chat
uv run agent-db e2e --tenants default,shop

# Только data isolation + admin API (8 тестов)
uv run agent-db e2e-data

# Только MCP dynamic tool resolution (3 теста)
uv run agent-db e2e-mcp

# Все три уровня разом
uv run agent-db e2e-full
```

### Интеграционные тесты
```bash
# Все 274 Go-теста (data-service + mcp-gateway)
go test ./data-service/... ./mcp-gateway/... -count=1
```

## Ключевые особенности

1. **Stateless** — не хранит состояние сессий локально (кроме кэша в SQLite через demo/api)
2. **Multi-tenant aware** — корректно пробрасывает X-Tenant-ID во все downstream сервисы
3. **SSE proxy** — поддерживает streaming для chat endpoint
4. **Correlation ID** — пробрасывает x-correlation-id для трейсинга
5. **Bearer token** — пробрасывает Authorization если настроен

## Ограничения

- Нет прямого доступа к БД (только через data-service)
- Не выполняет бизнес-логику (только проксирование)
- Read-only проксирование в data-service (мутации через API)
