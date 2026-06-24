# Тестирование системы Agent-Tutor

Тесты расположены в директориях каждого сервиса:

| Сервис | Тесты |
|---|---|
| `rag/` | `rag/tests/` |
| `mcp_server/` | `mcp_server/tests/` |
| `demo/api/` | `demo/api/tests/` |
| `db/` | `db/tests/` |

## Запуск

```bash
# Все тесты (из корня проекта)
uv run pytest

# Тесты конкретного сервиса
uv run pytest rag/tests/
uv run pytest mcp_server/tests/
uv run pytest demo/api/tests/
uv run pytest db/tests/

# С покрытием
uv run pytest --cov --cov-fail-under=40
```

Shared fixtures (`temp_dir`, `test_db`, `mock_embedding`, `rag_config`) — в корневом `conftest.py`.
