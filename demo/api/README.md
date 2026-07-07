# API Service (demo-api)

Оркестратор LLM-агента с MCP-интеграцией, управлением сессиями и бэклогом.

## Роль в системе

`demo-api` — единственный компонент, который общается с LLM (через LiteLLM). Он:
- Формирует системный промпт + Persona агента
- Управляет MCP-клиентом (подключение к mcp-gateway:8083)
- Хранит историю диалогов (SQLite: `demo_sessions.sqlite`)
- Пишет полный бэклог взаимодействий (JSONL в `backlog/`)
- Проксирует SSE-стрим от агента к Web

## Эндпоинты

| Путь | Метод | Описание |
|---|---|---|
| `/health` | GET | Статус сервиса |
| `/api/chat` | POST | SSE-стрим чата с агентом (требует `X-Tenant-ID`) |
| `/api/chat/{name}` | POST | SSE-чат с именованным агентом (tenant_ids из Agent Store) |
| `/api/sessions` | GET | Список сессий |
| `/api/sessions/{id}` | GET | История конкретной сессии |
| `/api/backlog` | GET | Список бэклогов |
| `/api/backlog/{id}` | GET | Детали бэклога |
| `/api/agents` | POST | Создать агента (Agent Store) |
| `/api/agents` | GET | Список агентов |
| `/api/agents/{name}` | GET | Получить агента |
| `/api/agents/{name}` | PUT | Обновить agentes.update_agent Обновить агента |
| `/api/agents/{name}` | DELETE | Удалить агента |

## Переменные окружения

См. `.env.example` в корне проекта. Ключевые для API:

| Переменная | Дефолт | Описание |
|---|---|---|
| `DEMO_API_HOST` | `127.0.0.1` | Хост API сервера |
| `DEMO_API_PORT` | `8081` | Порт API |
| `DEMO_WEB_HOST` | `127.0.0.1` | Хост Web сервера |
| `DEMO_WEB_PORT` | `8080` | Порт Web |
| `MCP_SERVICE_URL` | `http://127.0.0.1:8083/mcp` | URL mcp-gateway |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | URL Ollama (LLM) |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Модель Ollama |
| `MISTRAL_API_KEY` | — | Ключ Mistral (альтернатива Ollama) |
| `MISTRAL_MODEL` | `mistral/mistral-small` | Модель Mistral |
| `DEMO_SESSION_DB_PATH` | `./demo_sessions.sqlite` | Путь к БД сессий |
| `BACKLOG_DIR` | `./backlog` | Директория бэклогов |
| `BACKLOG_RETENTION_DAYS` | `30` | Дней хранения бэклогов |
| `DEMO_HISTORY_TURNS` | `8` | Кол-во ходов в контексте |
| `DEMO_HISTORY_CONTENT_CHARS` | `6000` | Макс. символов в истории |
| `DEMO_REQUEST_TIMEOUT` | `600` | Таймаут запросов к LLM (сек) |
| `PYTHON_EXECUTABLE` | `python3` | Python для subprocess |
| `ENABLE_THINK` | `true` | Thinking mode |
| `DEMO_DEBUG` | `false` | Debug логирование |
| `AGENT_TEMPERATURE` | `0.5` | Температура генерации |
| `AGENT_MAX_ITERATIONS` | `5` | Макс. итераций тулов за ход |
| `AGENT_MAX_TOKENS_THINKING` | `4096` | Макс. токенов thinking |
| `AGENT_MAX_EMPTY_ROUNDS` | `3` | Макс. пустых раундов thinking |
| `AGENT_MAX_TURN_TOKENS` | `8000` | Макс. токенов за ход (контекст) |

## Запуск

```bash
# Из корня проекта
cd /project/root
uv run python -m demo.api.server

# Или напрямую
uv run --package demo-api python -m uvicorn demo.api.server:app --port 8081
```

## Тестирование

```bash
uv run pytest demo/api/tests/ -v
# 10 тестов MCP-клиента/оркестратора — skip (ожидают новый MCP SDK протокол)
```

---

## 🔧 Troubleshooting

| Симптом | Причина | Фикс |
|---|---|---|
| `Cannot connect to host 127.0.0.1:11434` | Ollama не запущен | `ollama serve` или `docker run -d -p 11434:11434 ollama/ollama` |
| `MISTRAL_API_KEY not set` и Ollama недоступен | Нет LLM бэкенда | Настроить `MISTRAL_API_KEY` или запустить Ollama |
| `MCP connection failed` / 502 | mcp-gateway не запущен на 8083 | `go run ./mcp-gateway/cmd/` |
| 401 на `/api/chat` | Не передан `X-Tenant-ID` | Добавить заголовок `X-Tenant-ID: <tenant-id>` |
| SSE обрывается / нет tool calls | LLM не вызывает инструменты | Проверить системный промпт, capabilities модели, логи `DEMO_DEBUG=1` |
| `demo_sessions.sqlite` locked | Остался процесс от прошлого запуска | `pkill -f "demo.api" && rm -f demo_sessions.sqlite* backlog/*.jsonl` |

### Быстрый smoke-тест
```bash
# 1. Зависимости
lsof -ti:11434  # Ollama
lsof -ti:8083   # mcp-gateway

# 2. Health
curl -s http://127.0.0.1:8081/health

# 3. SSE chat (требует запущенный mcp-gateway + data-service + registered tenant)
curl -N -X POST http://127.0.0.1:8081/api/chat \
  -H "Content-Type: application/json" -H "X-Tenant-ID: default" \
  -d '{"message":"привет","session_id":"test"}' | head -c 300
```

### Логи
- Ручное запуск: stdout/stderr терминала
- Через `dev.sh`: `.data/logs/api.log`
- Debug режим: `DEMO_DEBUG=1 uv run python -m demo.api.server`