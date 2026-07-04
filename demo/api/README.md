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
| `/api/sessions` | GET | Список сессий |
| `/api/sessions/{id}` | GET | История конкретной сессии |
| `/api/backlog` | GET | Список бэклогов |
| `/api/backlog/{id}` | GET | Детали бэклога |

## Переменные окружения

См. `.env.example` в корне проекта. Ключевые для API:

| Переменная | Дефолт | Описание |
|---|---|---|
| `DEMO_API_PORT` | `8081` | Порт API |
| `MCP_SERVICE_URL` | `http://127.0.0.1:8083/mcp` | URL mcp-gateway |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | URL Ollama (LLM) |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Модель Ollama |
| `MISTRAL_API_KEY` | — | Ключ Mistral (альтернатива Ollama) |
| `MISTRAL_MODEL` | `mistral/mistral-small` | Модель Mistral |
| `DEMO_SESSION_DB_PATH` | `./demo_sessions.sqlite` | Путь к БД сессий |
| `BACKLOG_DIR` | `./backlog` | Директория бэклогов |
| `DEMO_HISTORY_TURNS` | `8` | Кол-во ходов в контексте |
| `ENABLE_THINK` | `true` | Включить thinking mode |

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