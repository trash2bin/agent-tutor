# RAG Service

Сервис поиска по документам (ChromaDB), чанкинг, эмбеддинги.

## Роль в системе

`rag` — векторный поиск по документам:
- Импорт документов (PDF, TXT, MD, DOCX)
- Чанкинг (рекурсивный / sentence-based)
- Эмбеддинги (sentence-transformers)
- Векторное хранение (ChromaDB)
- Семантический поиск + контекст для LLM

## Эндпоинты

| Путь | Метод | Описание |
|---|---|---|
| `/health` | GET | Статус сервиса |
| `/search` | POST | Семантический поиск |
| `/context` | POST | Готовый контекст для LLM |
| `/documents/list` | POST | Список документов с фильтром |
| `/documents/import` | POST | Импорт документа/директории |
| `/documents/{id}` | DELETE | Удаление документа |

## Переменные окружения

| Переменная | Дефолт | Описание |
|---|---|---|
| `RAG_PORT` | `8082` | Порт |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Директория ChromaDB |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Модель эмбеддингов |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` / `cuda` / `mps` |
| `CHUNK_SIZE` | `512` | Размер чанка |
| `CHUNK_OVERLAP` | `50` | Перекрытие чанков |
| `MAX_CHUNKS_PER_QUERY` | `10` | Лимит чанков в поиске |

## Запуск

```bash
# Из корня проекта
cd /project/root
uv run python -m rag.service

# Или через Docker
docker compose up -d rag
```

## Тестирование

```bash
uv run pytest rag/tests/ -v   # 51 тест
```

---

## 🔧 Troubleshooting

| Симптом | Причина | Фикс |
|---|---|---|
| `ChromaDB: collection not found` | Не импортированы документы | `curl -X POST http://127.0.0.1:8082/documents/import -d '{"path":"./docs"}'` |
| `Embedding model not found` / OOM | Недостаточно RAM / не та модель | Меньшая модель: `EMBEDDING_MODEL=intfloat/multilingual-e5-small` |
| `CUDA out of memory` | GPU память переполнена | `EMBEDDING_DEVICE=cpu` или уменьшите `CHUNK_SIZE` |
| `sqlite3.OperationalError: database is locked` | ChromaDB.lock от прошлого запуска | `pkill -f rag.service && rm -f chroma_db/*.lock` |
| Поиск возвращает пусто / нерелевантно | Нет документов / плохой chunking | Проверить `/documents/list`, настроить `CHUNK_SIZE/OVERLAP` |
| 500 на `/search` | ChromaDB не запущен / путь неверен | `ls -la chroma_db/`, проверить `CHROMA_PERSIST_DIR` |

### Быстрый smoke-тест
```bash
# 1. Health
curl -s http://127.0.0.1:8082/health

# 2. Импорт тестового документа
curl -s -X POST http://127.0.0.1:8082/documents/import \
  -H "Content-Type: application/json" \
  -d '{"path": "./specs/fixtures"}'

# 3. Поиск
curl -s -X POST http://127.0.0.1:8082/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 3}' | jq .

# 4. Контекст для LLM
curl -s -X POST http://127.0.0.1:8082/context \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}' | jq .
```

### Логи
- Ручное запуск: stdout/stderr терминала
- Через `dev.sh`: `.data/logs/rag.log`