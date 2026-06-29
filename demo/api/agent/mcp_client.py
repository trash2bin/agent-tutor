"""MCP (Model Context Protocol) client for tool interaction.

Долгоживущая MCP-сессия с автоматическим переподключением при сбоях.
Не создаёт новое HTTP-соединение на каждый tool call — это дорого по latency.

# Архитектура

Внутри `streamable_http_client` используется `anyio.create_task_group()`,
привязанный к asyncio-task, в которой был вызван `__aenter__`. Закрытие
`__aexit__` из другой task падает с `RuntimeError("cancel scope in a
different task")`. Когда orchestrator падает в середине turn'а,
`get_session()` ловит исключение и зовёт `close()` — task может уже
отличаться от той, что открывала стримы.

Решение: вся работа с MCP-сессией (open, list_tools, call_tool, close)
выполняется в одной выделенной фоновой task `_mcp_worker`. Внешний код
общается через `_SessionProxy`, который посылает `_Request` в очередь
и получает результат через Future. `__aenter__` и `__aexit__` всегда
выполняются в одной task — никаких cross-task проблем с anyio.

# Защита от гонок

- `_lifecycle_lock` — asyncio.Lock, защищает все мутации состояния
  клиента (`_request_queue`, `_worker_task`, `_generation`, `_closing`,
  `_session_users`).
- `_generation` — монотонный счётчик. Каждый `_Request` несёт
  generation_id, с которым он был создан. Worker проверяет совпадение
  и отбрасывает stale-запросы (появившиеся после перезапуска worker'а).
- `_closing` — флаг, чтобы `close()` не запускался параллельно.
- `_session_users` — счётчик активных `get_session()` блоков. `close()`
  ждёт пока счётчик обнулится (с таймаутом), затем посылает "close"
  в очередь. Worker гарантированно закрывает __aexit__ в своей task.
- `_request_queue` имеет `maxsize=QUEUE_MAXSIZE` — backpressure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from demo.settings import settings

logger = logging.getLogger("demo.api.agent.mcp_client")

QUEUE_MAXSIZE = 256
CLOSE_GRACE_SECONDS = 10.0
WORKER_FINISH_TIMEOUT = 5.0
SESSION_DRAIN_TIMEOUT = 5.0


@dataclass(slots=True)
class ToolResult:
    """Pre-built result of an MCP tool call, ready for LLM consumption.

    Разделяет результат на tool_content (для role="tool" message)
    и reminder (для предшествующего role="system" message),
    чтобы маленькие LLM (0.5–1.5B) не игнорировали tool_result.

    Вся логика unwrap nested JSON + null/empty detection — здесь,
    в одном месте. Orchestrator просто вставляет готовые строки в messages.
    """

    tool_content: str   # Содержимое для role="tool" message
    reminder: str       # System-reminder message для модели
    ok: bool = True
    error: str | None = None


@dataclass
class _Request:
    """Запрос к MCP worker'у.

    `generation` фиксирует «эпоху» worker'а: если worker перезапустился
    (generation сменился), старые запросы отбрасываются, чтобы не упасть
    на закрывающейся сессии.
    """

    op: str
    args: dict[str, Any]
    future: asyncio.Future[Any]
    generation: int


class MCPClient:
    """Хранит одно долгоживущее соединение к MCP-серверу.

    Публичный API совместим со старой версией: `get_session()` (async CM),
    `list_tools(session)`, `call_tool(session, name, args)`, `close()`.
    """

    def __init__(self) -> None:
        self._request_queue: asyncio.Queue[_Request] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._generation: int = 0
        self._closing: bool = False
        self._lifecycle_lock = asyncio.Lock()
        # Сколько раз кто-то сейчас находится внутри get_session().
        self._session_users: int = 0

    async def _ensure_worker(self) -> tuple[asyncio.Queue[_Request], int]:
        """Создать worker (если нет) под lifecycle_lock. Возвращает (queue, generation).

        Атомарно: либо создаём нового worker'а, либо возвращаем уже
        существующего. Без lock'а два конкурентных вызова могли бы
        плодить дублирующих worker'ов с разными очередями.

        При _closing=True НЕ создаёт нового worker'а — возвращает
        существующую очередь (close() сам закроет worker через неё).
        """
        async with self._lifecycle_lock:
            # Если closing — не стартуем нового worker'а. Используем
            # существующую очередь (close() отработает через неё) или
            # создаём временную только для этого вызова.
            needs_new = (
                self._worker_task is None
                or self._worker_task.done()
            )
            if needs_new and self._closing:
                # close() в процессе — вернуть заглушку, чтобы caller
                # не повис. Без этого get_session() во время shutdown
                # создал бы нового worker'а в обход close().
                if self._request_queue is None:
                    self._request_queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
                return self._request_queue, self._generation

            if needs_new:
                # Если есть старая queue с pending запросами — дренируем
                # с ошибкой, чтобы calling tasks не висели вечно.
                old_queue = self._request_queue
                if old_queue is not None:
                    while True:
                        try:
                            stale = old_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        if not stale.future.done():
                            stale.future.set_exception(
                                RuntimeError("MCP worker restarted")
                            )
                self._generation += 1
                queue: asyncio.Queue[_Request] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
                self._request_queue = queue
                self._worker_task = asyncio.create_task(
                    self._mcp_worker(queue, self._generation),
                    name=f"mcp-worker-{self._generation}",
                )
            assert self._request_queue is not None
            return self._request_queue, self._generation

    async def _request(self, op: str, args: dict[str, Any]) -> Any:
        """Послать запрос в очередь и дождаться результата.

        Если во время ожидания calling task отменяется — отменяем запрос
        через _Request.future, чтобы worker не обрабатывал его впустую.
        """
        queue, generation = await self._ensure_worker()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        request = _Request(op=op, args=args, future=future, generation=generation)
        try:
            await queue.put(request)
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise
        try:
            return await future
        except asyncio.CancelledError:
            # Calling task отменён — сообщаем worker'у через future.cancel()
            # чтобы он не тратил MCP-вызов на результат, который никому не нужен.
            if not future.done():
                future.cancel()
            raise

    async def _mcp_worker(
        self, queue: asyncio.Queue[_Request], generation: int
    ) -> None:
        """Долгоживущая task: держит MCP-сессию и обрабатывает запросы.

        Все операции с anyio task_group происходят здесь, поэтому нет
        cross-task проблем. Игнорирует запросы от старых generation'ов
        (появились до перезапуска worker'а).
        """
        streams_cm: Any = None
        session_cm: Any = None
        session: ClientSession | None = None
        startup_failed = False

        try:
            logger.info(
                "[MCP] Worker[%d]: opening HTTP session to %s",
                generation,
                settings.mcp_service_url,
            )
            streams_cm = streamable_http_client(
                url=settings.mcp_service_url,
                terminate_on_close=True,
            )
            read, write, _get_session_id = await streams_cm.__aenter__()

            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            await session.initialize()

            session_id = _get_session_id()
            if callable(session_id):
                try:
                    session_id = session_id()
                except Exception:  # noqa: BLE001
                    session_id = None
            logger.info("[MCP] Worker[%d]: session ready (id=%s)", generation, session_id)

            # Главный цикл обработки запросов.
            while True:
                req = await queue.get()
                # Stale-запрос от предыдущего поколения worker'а: отбрасываем.
                if req.generation != generation:
                    if not req.future.done():
                        req.future.cancel()
                    continue
                if req.op == "close":
                    if not req.future.done():
                        req.future.set_result(None)
                    break

                try:
                    result: Any = None
                    if req.op == "list_tools":
                        raw = await session.list_tools()
                        result = [
                            {
                                "type": "function",
                                "function": {
                                    "name": tool.name,
                                    "description": tool.description or "",
                                    "parameters": tool.inputSchema,
                                },
                            }
                            for tool in raw.tools
                        ]
                    elif req.op == "call_tool":
                        raw = await session.call_tool(
                            req.args["name"], req.args["arguments"]
                        )
                        if raw.isError:
                            text = _collect_text(raw)
                            result = {
                                "ok": False,
                                "error": text
                                or f"Error calling tool {req.args['name']}",
                            }
                        else:
                            structured = getattr(raw, "structuredContent", None)
                            if structured is not None:
                                result = {"ok": True, "data": structured}
                            else:
                                result = {"ok": True, "data": _collect_text(raw)}
                    else:
                        if not req.future.done():
                            req.future.set_exception(
                                ValueError(f"Unknown MCP op: {req.op}")
                            )
                        continue

                    if not req.future.done():
                        req.future.set_result(result)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "[MCP] Worker[%d] error during %s", generation, req.op
                    )
                    if not req.future.done():
                        req.future.set_exception(exc)

        except asyncio.CancelledError:
            logger.info("[MCP] Worker[%d] cancelled", generation)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[MCP] Worker[%d] failed to start", generation
            )
            startup_failed = True
            # Дренируем все запросы в очереди с ошибкой, чтобы calling tasks
            # не висели. Помечаем generation'ы — берём всё под текущий.
            await self._drain_queue_with_error(queue, generation, exc)
        finally:
            # Закрываем в той же task, что открывали. anyio cancel_scope
            # видит консистентную task → terminate_session() отрабатывает.
            if session_cm is not None:
                try:
                    await session_cm.__aexit__(None, None, None)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[MCP] Worker[%d] error closing session: %s",
                        generation,
                        exc,
                    )
            if streams_cm is not None:
                try:
                    await streams_cm.__aexit__(None, None, None)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[MCP] Worker[%d] error closing streams: %s",
                        generation,
                        exc,
                    )
            logger.info("[MCP] Worker[%d]: session closed", generation)

            # Если startup упал — следующий _ensure_worker увидит worker_task.done()
            # и поднимет нового. Но если calling task уже послал запрос до этого,
            # запрос висит в очереди навсегда. Дренируем по факту закрытия.
            if startup_failed:
                await self._drain_queue_with_error(
                    queue, generation, RuntimeError("MCP worker exited")
                )

    async def _drain_queue_with_error(
        self,
        queue: asyncio.Queue[_Request],
        generation: int,
        exc: BaseException,
    ) -> None:
        """Завершить все ожидающие в очереди запросы с ошибкой."""
        drained = 0
        while True:
            try:
                req = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if req.generation != generation:
                # Чужое поколение — завершаем предсказуемой ошибкой, не cancel.
                # set_exception ловится except Exception в call_tool.
                if not req.future.done():
                    req.future.set_exception(
                        RuntimeError("stale request from old generation")
                    )
                continue
            if not req.future.done():
                req.future.set_exception(exc)
            drained += 1
        if drained:
            logger.warning(
                "[MCP] Worker[%d] drained %d pending requests after failure",
                generation,
                drained,
            )

    @asynccontextmanager
    async def get_session(self):
        """Async context manager: возвращает _SessionProxy.

        Учитывает _session_users: close() ждёт обнуления перед посылкой
        команды "close" в очередь, чтобы не разрушить worker'а под активным
        пользователем.
        """
        await self._ensure_worker()
        async with self._lifecycle_lock:
            self._session_users += 1
        try:
            proxy = _SessionProxy(self._request)
            yield proxy
        except Exception as exc:
            logger.warning(
                "[MCP] Session error, will reconnect on next call: %s", exc
            )
            raise
        finally:
            async with self._lifecycle_lock:
                self._session_users -= 1
                if self._session_users <= 0:
                    self._session_users = 0

    async def list_tools(self, session: "_SessionProxy") -> list[dict[str, Any]]:
        """List available MCP tools (делегирует в session)."""
        return await session.list_tools()

    async def call_tool(
        self, session: "_SessionProxy", name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """Call an MCP tool and return a pre-built ToolResult for LLM consumption.

        ВСЯ логика работы с результатом — здесь, в одном месте:
        - unwrap nested JSON (MCP-серверы часто встраивают JSON в text content)
        - null/empty detection (tool вернул ok но без данных)
        - reminder generation (подсказка для маленьких LLM не игнорировать result)

        Orchestrator просто вставляет ToolResult.tool_content и ToolResult.reminder
        в messages — без повторного json.loads и анализа.

        Если worker бросает исключение — возвращает ToolResult с ok=False (не raise).
        """
        try:
            payload = await session.call_tool(name, arguments)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[MCP] Exception calling tool %s", name)
            return ToolResult(
                tool_content=json.dumps(
                    {"ok": False, "error": str(exc)}, ensure_ascii=False
                ),
                reminder=f"Инструмент {name} завершился ошибкой.",
                ok=False,
                error=str(exc),
            )

        ok: bool = payload.get("ok", False) if isinstance(payload, dict) else False
        if not ok:
            error_text = (
                payload.get("error", "Unknown error")
                if isinstance(payload, dict)
                else str(payload)
            )
            return ToolResult(
                tool_content=json.dumps(payload, ensure_ascii=False),
                reminder=(
                    f"Инструмент {name} вернул ошибку. "
                    "Не повторяй запрос с теми же аргументами."
                ),
                ok=False,
                error=error_text,
            )

        # --- ok=True: анализируем data для лучшего LLM-представления ---
        data: Any = payload.get("data") if isinstance(payload, dict) else payload

        # Попытка распарсить data как JSON (MCP часто возвращает JSON-строку)
        data_parsed: Any = data
        if isinstance(data, str):
            try:
                data_parsed = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Null/empty: tool отработал, но данных нет
        if data_parsed is None or data_parsed == "null" or data_parsed == "" or data_parsed == []:
            return ToolResult(
                tool_content=json.dumps(payload, ensure_ascii=False),
                reminder=(
                    f"Инструмент {name} вернул пустой результат — "
                    "записи нет, не ищи повторно с теми же аргументами."
                ),
                ok=True,
            )

        # Unwrap inner JSON object/array → плоский JSON для LLM.
        # Критично для маленьких моделей (0.5B): они не справляются
        # с double-escaped nested JSON {"ok":true,"data":"{...}"}.
        if isinstance(data, str):
            try:
                inner = json.loads(data)
                if isinstance(inner, (dict, list)):
                    flat = json.dumps(inner, ensure_ascii=False)
                    preview = flat[:200]
                    return ToolResult(
                        tool_content=flat,
                        reminder=(
                            f"Инструмент {name} вернул данные: {preview}. "
                            "ОБЯЗАТЕЛЬНО покажи эти данные пользователю."
                        ),
                        ok=True,
                    )
            except json.JSONDecodeError:
                pass

        # Fallback: не-JSON данные или сложный payload — оставляем как есть
        tool_content = json.dumps(payload, ensure_ascii=False)
        preview = tool_content[:200]
        return ToolResult(
            tool_content=tool_content,
            reminder=(
                f"Инструмент {name} вернул данные: {preview}. "
                "ОБЯЗАТЕЛЬНО покажи эти данные пользователю."
            ),
            ok=True,
        )

    async def close(self) -> None:
        """Закрыть worker и MCP-сессию. Безопасно вызывать несколько раз.

        Под lifecycle_lock: если есть активные get_session() — ждём их
        выхода (с таймаутом). Затем посылаем "close" в очередь и
        дожидаемся завершения worker'а.
        """
        async with self._lifecycle_lock:
            if self._closing:
                return
            if self._worker_task is None or self._worker_task.done():
                self._request_queue = None
                self._worker_task = None
                return
            self._closing = True
            queue = self._request_queue
            worker = self._worker_task
            users = self._session_users

        # Ждём выхода активных пользователей сессии (если есть).
        if users > 0:
            deadline = asyncio.get_running_loop().time() + SESSION_DRAIN_TIMEOUT
            while True:
                async with self._lifecycle_lock:
                    if self._session_users <= 0:
                        break
                if asyncio.get_running_loop().time() >= deadline:
                    logger.warning(
                        "[MCP] close(): %d active sessions still in use after %.1fs; "
                        "proceeding to close anyway",
                        self._session_users,
                        SESSION_DRAIN_TIMEOUT,
                    )
                    break
                await asyncio.sleep(0.05)

        # Посылаем "close" в очередь.
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        assert queue is not None
        await queue.put(
            _Request(
                op="close", args={}, future=future, generation=self._generation
            )
        )
        try:
            await future
        except Exception as exc:  # noqa: BLE001
            logger.warning("[MCP] Close future raised: %s", exc)

        # Дожидаемся завершения worker'а (он закроет __aexit__ в своей task).
        try:
            await asyncio.wait_for(worker, timeout=WORKER_FINISH_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(
                "[MCP] Worker did not finish in %.1fs; cancelling",
                WORKER_FINISH_TIMEOUT,
            )
            worker.cancel()
            try:
                await worker
            except (asyncio.CancelledError, Exception):
                pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("[MCP] Worker finished with error: %s", exc)

        async with self._lifecycle_lock:
            self._request_queue = None
            self._worker_task = None
            self._closing = False


class _SessionProxy:
    """Прокси над MCP-сессией: посылает запросы в очередь worker'а."""

    def __init__(self, request_fn: Any) -> None:
        self._request_fn = request_fn

    async def list_tools(self) -> list[dict[str, Any]]:
        return await self._request_fn("list_tools", {})

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request_fn(
            "call_tool", {"name": name, "arguments": arguments}
        )


def _collect_text(result: Any) -> str:
    """Extract text content from MCP result.

    Не-текстовый контент (image/audio) сознательно игнорируется —
    LLM-агент всё равно не может его обработать в текущей архитектуре.
    """
    return "\n".join(
        getattr(item, "text", "")
        for item in getattr(result, "content", []) or []
        if getattr(item, "text", None)
    )
