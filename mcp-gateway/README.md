# mcp-gateway

Generic MCP (Model Context Protocol) сервер на Go. Заменил Python-сервер `mcp_server/` (удалён).

**Ключевая фича**: MCP-инструменты **авто-генерируются** из конфига data-service.
Не нужно писать ни строчки кода для новой БД — достаточно запустить `--discover`.

## 🏢 Multi-tenancy и Stateless архитектура

`mcp-gateway` реализован как **stateless динамический шлюз**. Он не хранит статический реестр инструментов при старте, а разрешает их на лету на основе идентификатора тенанта.

### Строгая мультитеннантность (Strict Mode)

Система работает в режиме **строгой изоляции**. Любой запрос к данным или конфигурации требует явного указания тенанта.

1. **X-Tenant-ID**: Основной ключ изоляции. Передается в заголовках каждого запроса. Без этого заголовка (или `?tenant_id=`) запросы возвращают `404 Not Found`.
2. **Bootstrappable Startup**: Поскольку `data-service` больше не имеет «дефолтного» тенанта, `mcp-gateway` использует переменную окружения `BOOTSTRAP_TENANT_ID` для первичной загрузки конфигурации при старте.
3. **Динамический манифест**: При каждом вызове инструментов (`tools/list` или `tools/call`) шлюз запрашивает актуальный манифест конкретного тенанта у `data-service` через `/mcp/manifest`.
4. **Разрешение инструментов**: `toolsCallHandler` сопоставляет имя вызванного инструмента с путем к эндпоинту из полученного манифеста.
5. **Проброс (Propagation)**: Заголовок `X-Tenant-ID` пробрасывается сквозь шлюз в `data-service`, обеспечивая доступ к правильной БД тенанта.

## Два режима генерации инструментов

Инструменты определяются в конфиге тенанта в `data-service`.

### 1. Auto-generated (рекомендуемый)

Конфиг **без** `mcp_tools[]`. Инструменты генерятся из `endpoints`:

```json
{
  "entities": [
    { "name": "products", "table": "products", "id_column": "id", "fields": [...] },
    { "name": "customers", "table": "customers", "id_column": "id", "fields": [...] }
  ],
  "endpoints": [
    { "method": "GET", "path": "/products/{id}", "op": "get_by_id", "entity": "products" },
    { "method": "GET", "path": "/products", "op": "find", "entity": "products",
      "search_field": "name", "query_param": "name" }
  ]
}
```

Автоматически получаете MCP-инструменты:
```
🔧 get_products(id)     → GET /products/{id}
🔧 find_products(name)  → GET /products?name=
```

### 2. Explicit override (для кастомных имён и параметров)

Если нужно другое имя или описание — добавьте `mcp_tools[]` в конфиг тенанта:

```json
{
  "mcp_tools": [
    {
      "name": "search_products_by_name",
      "endpoint": "/products",
      "description": "Поиск товаров по названию",
      "params": [{"name": "name", "type": "string", "required": true}]
    }
  ]
}
```

Explicit тулы перезаписывают auto-generated с тем же именем.

## Схема именования инструментов

| Op в endpoint | Имя инструмента | Пример |
|---|---|---|
| `get_by_id` | `get_{entity}` | `get_student` |
| `find` | `find_{entity}` | `find_student` |
| `list` | `list_{entity}` | `list_students` |
| `builtin_health` | `health` | `health` |
| `builtin_stats` | `stats` | `stats` |
| `custom_query` | `{query_id}` | `student_grades` |

## Архитектура

```
mcp-gateway/
├── cmd/
│   ├── main.go                 # Точка входа: динамический toolsCallHandler, SSE + JSON-RPC
│   ├── mcp_debug.go            # //go:embed playground.html (MCP_DEV)
│   └── playground.html         # Веб-интерфейс для тестирования тулов
├── internal/
│   ├── httpclient/
│   │   └── client.go           # HTTP-клиент к data-service: FetchConfigWithTenant + Call
│   ├── ragclient/
│   │   └── client.go           # HTTP-клиент к RAG: SearchDocuments, ListDocuments, GetRagContext
│   └── tools/
│       └── tools.go            # Статические RAG-тулы
├── Dockerfile
├── go.mod / go.sum
└── README.md
```

## Поток вызова инструмента (Detailed)

1. **Запрос**: Агент шлёт `POST /tools/call` с заголовком `X-Tenant-ID: uni-tenant`.
2. **Манифест**: `mcp-gateway` делает `GET /mcp/manifest` $\rightarrow$ `data-service` с тем же заголовком.
3. **Разрешение**:
   - Ищет инструмент в `endpoints` (по правилам именования).
   - Если не найден $\rightarrow$ ищет в `mcp_tools`.
   - Если не найден $\rightarrow$ проверяет статические RAG-тулы.
4. **Вызов**:
   - Подставляет path-параметры (`{id}`) из аргументов.
   - Выполняет `GET` к `data-service` с заголовком `X-Tenant-ID`.
5. **Ответ**: JSON-ответ от `data-service` оборачивается в MCP-результат и возвращается агенту.

## Запуск

### 1. Запуск сервисов
```bash
# data-service
cd ../data-service
DS_CONFIG=/tmp/myapp-config.json go run ./cmd/server/

# mcp-gateway
cd ../mcp-gateway
DATA_SERVICE_URL=http://127.0.0.1:8084 go run ./cmd/
```

### 2. Регистрация тенантов (Обязательно)
Так как шлюз теперь stateless, тенанты должны быть зарегистрированы в `data-service` перед использованием:
```bash
# Используйте вспомогательный скрипт для локальной разработки
uv run scripts/setup_tenants.py
```

## Dev-режим

```bash
MCP_DEV=true DATA_SERVICE_URL=http://127.0.0.1:8084 go run ./cmd/
```

Доступно:
- `/debug` — MCP Playground: веб-интерфейс для тестирования всех инструментов (требует `X-Tenant-ID` в запросах)
- `/debug/sessions` — активные SSE-сессии
- `/debug/config` — текущий конфиг тенанта (фетчится из `/mcp/manifest`)

## Эндпоинты

| Путь | Метод | Описание | Заголовок |
|---|---|---|---|
| `/health` | GET | Статус сервиса | - |
| `/mcp` | GET | SSE endpoint (streamable HTTP) | `X-Tenant-ID` |
| `/mcp/message` | POST | JSON-RPC сообщения | `X-Tenant-ID` |
| `/tools/list` | GET | Список инструментов тенанта | `X-Tenant-ID` |
| `/tools/call` | POST | Вызов инструмента тенанта | `X-Tenant-ID` |
| `/debug` | GET | MCP Playground (dev) | `X-Tenant-ID` |

## Переменные окружения

| Переменная | Дефолт | Описание |
|---|---|---|
| `BOOTSTRAP_TENANT_ID` | — | ID тенанта для первичной загрузки конфига при старте (обязателен в strict mode) |
| `DATA_SERVICE_URL` | `http://127.0.0.1:8084` | Базовый URL data-service |
| `DATA_SERVICE_TIMEOUT` | `30` | Таймаут HTTP-запроса в секундах |
| `RAG_SERVICE_URL` | `http://127.0.0.1:8082` | Базовый URL RAG-сервиса |
| `MCP_PORT` | `8083` | Порт HTTP |
| `MCP_DEV` | — | Включает debug endpoints + логирование |

## RAG-инструменты (статическая регистрация)

Три RAG-тула доступны всем тенантам:

| Инструмент | RAG-эндпоинт | Описание |
|---|---|---|
| `search_documents` | `POST /search` | Семантический поиск по документам |
| `list_documents` | `POST /documents/list` | Список документов с фильтром по дисциплине |
| `get_rag_context` | `POST /context` | Готовый контекст для ответа LLM |
