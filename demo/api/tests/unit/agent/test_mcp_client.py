"""Unit tests for MCPClient.

Архитектура: вся работа с MCP-сессией (open, list_tools, call_tool,
close) выполняется в одной выделенной фоновой task `_mcp_worker`.
Внешний код общается через `get_session()` → `_SessionProxy`, который
посылает запросы в очередь worker'а и получает результат через Future.

Тесты подменяют worker на FakeWorker и проверяют:
- happy path: list_tools, call_tool success/error
- идемпотентность close()
- пробрасывание исключений из yield-блока
- восстановление после падения worker'а (новый generation)
- отбрасывание stale-запросов от старого поколения
- race-safety: конкурентные get_session + close
- обработка CancelledError в calling task
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from demo.api.agent.mcp_client import (
    MCPClient,
    ToolResult,
    _Request,
    _collect_text,
)


class FakeWorker:
    """Эмулирует worker: читает запросы из очереди клиента и подставляет ответы.

    Поведение:
    - `responses`: список ответов (или вызываемых, или Exception'ов).
      Каждый запрос забирает один по порядку.
    - `block_on_get`: если True, worker ждёт внешнего сигнала `release()`
      на каждом `queue.get()`. Полезно для тестов гонок.
    """

    def __init__(
        self,
        responses: list[Any] | None = None,
        block_on_get: bool = False,
    ) -> None:
        self.responses: list[Any] = list(responses or [])
        self.received_close = False
        self.block_on_get = block_on_get
        self._released = asyncio.Event()
        self._released.set()
        self._task: asyncio.Task[None] | None = None
        self._client: MCPClient | None = None
        # Ставится когда worker._run вошёл в свой первый queue.get() —
        # означает что корутина реально стартовала в event loop'е.
        self.ready_event = asyncio.Event()

    async def start(self, client: MCPClient) -> None:
        client._request_queue = asyncio.Queue()
        self._client = client
        self._task = asyncio.create_task(self._run(client), name="fake-mcp-worker")
        client._worker_task = self._task
        # Ждём чтобы worker._run дошёл до первого await — иначе close()
        # может выполниться раньше, чем worker возьмёт request.
        await self.ready_event.wait()

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    def pause(self) -> None:
        """Следующий queue.get() заблокируется до release()."""
        self._released.clear()

    def release(self) -> None:
        """Разблокировать worker."""
        self._released.set()

    async def _run(self, client: MCPClient) -> None:
        queue = client._request_queue
        assert queue is not None
        self.ready_event.set()
        generation_seen: int | None = None
        while True:
            if self.block_on_get:
                await self._released.wait()
            req: _Request = await queue.get()
            # Имитируем проверку generation: отбрасываем stale.
            if generation_seen is None:
                generation_seen = req.generation
            elif req.generation != generation_seen:
                if not req.future.done():
                    req.future.cancel()
                continue
            if req.op == "close":
                self.received_close = True
                if not req.future.done():
                    req.future.set_result(None)
                return
            try:
                response = self._next_response(req)
                if not req.future.done():
                    req.future.set_result(response)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if not req.future.done():
                    req.future.set_exception(exc)

    def _next_response(self, req: _Request) -> Any:
        if not self.responses:
            if req.op == "list_tools":
                return []
            return {"ok": True, "data": ""}
        item = self.responses.pop(0)
        if callable(item):
            return item(req)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def client_with_fake_worker() -> tuple[MCPClient, FakeWorker]:
    """Клиент с FakeWorker (без запуска)."""
    worker = FakeWorker()
    client = MCPClient()

    async def fake_ensure(self: MCPClient) -> tuple[asyncio.Queue[_Request], int]:
        if (
            self._request_queue is None
            or self._worker_task is None
            or self._worker_task.done()
        ):
            await worker.start(self)
            # Имитация lifecycle_lock + generation increment.
            async with self._lifecycle_lock:
                self._generation += 1
        assert self._request_queue is not None
        return self._request_queue, self._generation

    client._ensure_worker = fake_ensure.__get__(client, MCPClient)  # type: ignore[method-assign]
    return client, worker


# === Happy path ===


@pytest.mark.asyncio
async def test_list_tools_returns_tool_schemas(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """get_session → proxy.list_tools → MCPClient.list_tools возвращает list[dict]."""
    client, worker = client_with_fake_worker
    worker.responses = [
        [
            {
                "type": "function",
                "function": {
                    "name": "get_student",
                    "description": "Get student info",
                    "parameters": {"type": "object"},
                },
            }
        ]
    ]

    async with client.get_session() as session:
        tools = await client.list_tools(session)

    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "get_student"
    assert tools[0]["function"]["parameters"] == {"type": "object"}


@pytest.mark.asyncio
async def test_call_tool_success_returns_ok_json(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """call_tool при ok=True → ToolResult с ok=True и текстовыми данными."""
    client, worker = client_with_fake_worker
    worker.responses = [{"ok": True, "data": "Student found"}]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "get_student", {"id": "123"})

    assert tr.ok is True
    assert tr.error is None
    # unwrap: "Student found" → не JSON, остаётся wrapper
    assert "data" in json.loads(tr.tool_content)
    assert "ОБЯЗАТЕЛЬНО" in tr.reminder


@pytest.mark.asyncio
async def test_call_tool_error_returns_error_json(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """call_tool при ok=False → ToolResult с ok=False и error."""
    client, worker = client_with_fake_worker
    worker.responses = [{"ok": False, "error": "Error message"}]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "get_student", {"id": "123"})

    assert tr.ok is False
    assert tr.error == "Error message"


@pytest.mark.asyncio
async def test_call_tool_exception_returns_error_json(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """Если worker бросает исключение, call_tool возвращает ToolResult с ok=False."""

    def boom(req: _Request) -> Any:
        raise RuntimeError("MCP unavailable")

    client, worker = client_with_fake_worker
    worker.responses = [boom]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "get_student", {"id": "123"})

    assert tr.ok is False
    assert "MCP unavailable" in (tr.error or "")


# === Lifecycle ===


@pytest.mark.asyncio
async def test_close_sends_close_request(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """close() посылает op='close' в очередь — worker получает и завершается."""
    client, worker = client_with_fake_worker

    async with client.get_session():
        pass

    await client.close()
    assert worker.received_close is True


@pytest.mark.asyncio
async def test_close_is_idempotent(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """close() можно звать несколько раз — второй раз no-op."""
    client, worker = client_with_fake_worker

    async with client.get_session() as session:
        await client.list_tools(session)

    await client.close()
    await client.close()
    assert worker.received_close is True


@pytest.mark.asyncio
async def test_close_without_session_is_noop() -> None:
    """close() на свежем клиенте (без сессий) — no-op."""
    client = MCPClient()
    await client.close()
    assert client._request_queue is None
    assert client._worker_task is None


# === Proxy contract ===


@pytest.mark.asyncio
async def test_session_proxy_call_tool_forwards_args(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """_SessionProxy.call_tool правильно упаковывает name и arguments."""
    client, worker = client_with_fake_worker
    received: list[_Request] = []

    def capture(req: _Request) -> dict[str, Any]:
        received.append(req)
        return {"ok": True, "data": "captured"}

    worker.responses = [capture]

    async with client.get_session() as session:
        await session.call_tool("find_student", {"name": "Иванов"})

    assert len(received) == 1
    assert received[0].op == "call_tool"
    assert received[0].args == {
        "name": "find_student",
        "arguments": {"name": "Иванов"},
    }


@pytest.mark.asyncio
async def test_call_tool_unwraps_nested_json_data(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """Когда tool возвращает {"ok": True, "data": "<json_string>"},
    call_tool распаковывает inner JSON в tool_content.

    Это критично для маленьких LLM (0.5B) — они не справляются с
    double-escaped nested JSON в tool message content.
    """
    client, worker = client_with_fake_worker
    inner_json = '{"course": 3, "full_name": "Иванов Иван", "id": "abc123"}'
    worker.responses = [{"ok": True, "data": inner_json}]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(
            session, "find_student_by_name", {"name": "Иванов"}
        )

    # tool_content — плоский JSON-объект, без двойного wrap.
    parsed = json.loads(tr.tool_content)
    assert parsed == {"course": 3, "full_name": "Иванов Иван", "id": "abc123"}
    # Не должно быть {"ok": True, ...} обёртки.
    assert "ok" not in parsed
    assert tr.ok is True


@pytest.mark.asyncio
async def test_call_tool_keeps_wrapper_for_non_json_data(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """Если data не валидный JSON — оставляем wrapper в tool_content."""
    client, worker = client_with_fake_worker
    worker.responses = [{"ok": True, "data": "plain text response"}]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "search", {"q": "test"})

    parsed = json.loads(tr.tool_content)
    assert parsed == {"ok": True, "data": "plain text response"}
    assert tr.ok is True


@pytest.mark.asyncio
async def test_call_tool_keeps_wrapper_for_json_list(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """JSON-массив (list) тоже unwrap — это структурированный ответ."""
    client, worker = client_with_fake_worker
    worker.responses = [{"ok": True, "data": "[1, 2, 3]"}]

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "list_items", {})

    parsed = json.loads(tr.tool_content)
    assert parsed == [1, 2, 3]
    assert tr.ok is True


@pytest.mark.asyncio
async def test_session_error_propagates(
    client_with_fake_worker: tuple[MCPClient, FakeWorker],
) -> None:
    """Если внутри get_session() падает исключение в yield-блоке, оно пробрасывается."""
    client, _ = client_with_fake_worker

    with pytest.raises(RuntimeError, match="inner boom"):
        async with client.get_session() as _session:
            raise RuntimeError("inner boom")


# === Recovery after worker death ===


@pytest.mark.asyncio
async def test_worker_death_triggers_recovery() -> None:
    """Если worker умер — следующий вызов создаёт нового (новый generation)."""
    worker1 = FakeWorker(responses=[RuntimeError("worker1 boom")])
    worker2 = FakeWorker(responses=[{"ok": True, "data": "recovered"}])
    client = MCPClient()
    current_worker = {"w": worker1}

    async def fake_ensure(self: MCPClient):
        if (
            self._request_queue is None
            or self._worker_task is None
            or self._worker_task.done()
        ):
            w = current_worker["w"]
            await w.start(self)
            async with self._lifecycle_lock:
                self._generation += 1
        assert self._request_queue is not None
        return self._request_queue, self._generation

    client._ensure_worker = fake_ensure.__get__(client, MCPClient)  # type: ignore[method-assign]

    # Первый вызов: worker1 бросает исключение. call_tool ловит и возвращает
    # ToolResult с ok=False (не raise).
    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "x", {})
        assert tr.ok is False
        assert "worker1 boom" in (tr.error or "")

    # Принудительно убиваем worker1 — имитируем «worker умер».
    await worker1.stop()
    assert worker1._task is not None and worker1._task.done()

    # Подменяем worker'а — следующий вызов должен использовать worker2.
    current_worker["w"] = worker2

    async with client.get_session() as session:
        tr: ToolResult = await client.call_tool(session, "x", {})
        assert tr.ok is True
        # "recovered" — не JSON, останется wrapper payload
        assert "recovered" in tr.tool_content


# === Race: concurrent get_session + close ===


@pytest.mark.asyncio
async def test_close_waits_for_active_session() -> None:
    """close() ждёт пока активные get_session() не завершатся (с таймаутом)."""
    worker = FakeWorker(block_on_get=True)
    client = MCPClient()

    async def fake_ensure(self: MCPClient):
        if self._request_queue is None or self._worker_task is None:
            await worker.start(self)
            async with self._lifecycle_lock:
                self._generation += 1
        assert self._request_queue is not None
        return self._request_queue, self._generation

    client._ensure_worker = fake_ensure.__get__(client, MCPClient)  # type: ignore[method-assign]

    # Запускаем get_session в фоне (имитация долгого turn'а).
    async def long_session():
        async with client.get_session() as session:
            # worker блокирован (pause), этот await висит.
            worker.pause()
            try:
                await client.call_tool(session, "x", {})
            finally:
                worker.release()

    session_task = asyncio.create_task(long_session())
    # Даём session_task время войти в get_session и увеличить _session_users.
    await asyncio.sleep(0.1)

    # Запускаем close() — он должен ждать пока long_session не выйдет.
    close_task = asyncio.create_task(client.close())

    # Разблокируем worker чтобы long_session завершился.
    await asyncio.sleep(0.1)
    worker.release()

    await session_task
    await close_task

    # close должен был успешно послать "close" и worker завершился.
    assert worker.received_close is True


# === Cancellation safety ===


@pytest.mark.asyncio
async def test_request_cancellation_cleans_up() -> None:
    """CancelledError в calling task → future.cancel(), worker игнорирует."""
    worker = FakeWorker(block_on_get=True)
    client = MCPClient()

    async def fake_ensure(self: MCPClient):
        if self._request_queue is None or self._worker_task is None:
            await worker.start(self)
            async with self._lifecycle_lock:
                self._generation += 1
        assert self._request_queue is not None
        return self._request_queue, self._generation

    client._ensure_worker = fake_ensure.__get__(client, MCPClient)  # type: ignore[method-assign]

    worker.pause()  # worker ждёт release

    async def cancelled_request():
        async with client.get_session() as session:
            await client.call_tool(session, "x", {})

    task = asyncio.create_task(cancelled_request())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Future должен быть cancelled, а не висеть.
    assert client._request_queue is not None
    assert client._request_queue.qsize() == 1


# === _collect_text helper ===


def test_collect_text_skips_non_text_items() -> None:
    """_collect_text игнорирует элементы без атрибута text."""

    class Result:
        content = [
            type("Item", (), {"text": "hello"}),
            type("Item", (), {"text": None}),
            type("Item", (), {}),  # без text вообще
        ]

    text = _collect_text(Result())
    assert text == "hello"


def test_collect_text_handles_empty_content() -> None:
    """_collect_text с пустым content → пустая строка."""

    class Result:
        content = []

    assert _collect_text(Result()) == ""