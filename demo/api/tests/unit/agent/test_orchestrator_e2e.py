"""E2E тесты для LLMAgent: проверяет pipeline без реальной LLM.

Цель: убедиться что tool result корректно попадает в messages и
передаётся в следующий turn LLM. Без участия реальной модели —
фейковый LLMClient имитирует: сначала вызов tool, потом финальный ответ.

Что ловим:
- tool_call из LLM проходит через orchestrator
- orchestrator вызывает mcp_client.call_tool с правильными args
- mcp_client.call_tool возвращает данные
- данные добавляются в messages как role='tool'
- данные передаются в СЛЕДУЮЩИЙ вызов stream_completion

Также покрыт базовый сценарий: LLM возвращает финальный ответ без tool calls.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demo.api.agent.orchestrator import LLMAgent
from demo.api.agent.mcp_client import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_iter_final(final_val):
    yield (None, final_val)


# ---------------------------------------------------------------------------
# Fake components
# ---------------------------------------------------------------------------

class _FakeLLM:
    """Fake LLM client который воспроизводит сценарий:
    1. Первый turn: вызывает tool find_student_by_name
    2. Второй turn: генерирует финальный ответ с данными из tool_result
    """

    def __init__(self, tool_data: str) -> None:
        self.tool_data = tool_data
        self.call_history: list[dict[str, Any]] = []
        self.call_count = 0
        self.last_final_message: dict[str, Any] | None = None

    async def stream_completion(self, messages, tools=None):
        self.call_history.append(list(messages))  # snapshot
        self.call_count += 1

        if self.call_count == 1:
            # Первый turn: вызываем tool
            yield (
                None,
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_test_001",
                            "type": "function",
                            "function": {
                                "name": "find_student_by_name",
                                "arguments": json.dumps(
                                    {"name": "Уварова Анжела Павловна"}
                                ),
                            },
                        }
                    ],
                },
            )
        else:
            # Второй turn: финальный ответ
            # Имитируем что модель прочитала tool_result и использует данные.
            yield (
                None,
                {
                    "role": "assistant",
                    "content": f"Нашёл студента: {self.tool_data}",
                },
            )

    async def get_final_message(self, messages):
        for ch in "Извините, не удалось получить ответ.":
            yield ch


class _FakeMCP:
    """Fake MCP client с настоящим worker'ом — но быстрым."""

    def __init__(self, tool_data: str) -> None:
        self.tool_data = tool_data

    @asynccontextmanager
    async def get_session(self):
        yield AsyncMock()

    async def list_tools(self, session):
        return [
            {
                "type": "function",
                "function": {
                    "name": "find_student_by_name",
                    "description": "Найти студента по ФИО",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            }
        ]

    async def call_tool(self, session, name, arguments) -> ToolResult:
        # Имитируем реальный MCPClient.call_tool → ToolResult.
        try:
            parsed = json.loads(self.tool_data)
            if isinstance(parsed, (dict, list)):
                flat = json.dumps(parsed, ensure_ascii=False)
                return ToolResult(
                    tool_content=flat,
                    reminder=f"Инструмент {name} вернул данные: {flat[:200]}. ОБЯЗАТЕЛЬНО покажи эти данные пользователю.",
                    ok=True,
                )
        except json.JSONDecodeError:
            pass
        wrapper = {"ok": True, "data": self.tool_data}
        return ToolResult(
            tool_content=json.dumps(wrapper, ensure_ascii=False),
            reminder=f"Инструмент {name} вернул данные. ОБЯЗАТЕЛЬНО покажи эти данные пользователю.",
            ok=True,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_agent_stream_events_basic():
    """Базовый сценарий: LLM возвращает финальный ответ без tool calls."""
    mock_llm_client = MagicMock()
    mock_mcp_client = MagicMock()
    mock_conv_manager = MagicMock()

    # side_effect гарантирует свежий генератор на каждый вызов
    mock_llm_client.stream_completion = MagicMock(
        side_effect=lambda *a, **kw: _async_iter_final(
            {"role": "assistant", "content": "Hello"}
        )
    )
    mock_llm_client.last_final_message = None

    @asynccontextmanager
    async def mock_get_session():
        yield AsyncMock()

    mock_mcp_client.get_session = mock_get_session
    mock_mcp_client.list_tools = AsyncMock(return_value=[])

    mock_conv_manager.normalize_session_id.return_value = "default"
    mock_conv_manager.get_history_messages.return_value = []
    mock_conv_manager.aget_history_messages = AsyncMock(return_value=[])
    mock_conv_manager.aremember_turn = AsyncMock(return_value=None)

    with patch("demo.api.agent.orchestrator.backlog"):
        agent = LLMAgent(
            llm_client=mock_llm_client,
            mcp_client=mock_mcp_client,
            conversation_manager=mock_conv_manager,
        )

        events = []
        async for event in agent.stream_events("Hello", session_id="default"):
            events.append(event)

        assert any(e.type == "final" for e in events)


@pytest.mark.asyncio
async def test_tool_result_appears_in_next_turn_messages():
    """Tool result из первого turn'а ДОЛЖЕН попасть в messages второго turn'а."""
    STUDENT_JSON = '{"course": 3, "full_name": "Уварова Анжела Павловна", "id": "474ebc19"}'

    fake_llm = _FakeLLM(tool_data=STUDENT_JSON)
    fake_mcp = _FakeMCP(tool_data=STUDENT_JSON)

    conv = MagicMock()
    conv.normalize_session_id.return_value = "test-session"
    conv.get_history_messages.return_value = []
    conv.aget_history_messages = AsyncMock(return_value=[])
    conv.aremember_turn = AsyncMock(return_value=None)

    with patch("demo.api.agent.orchestrator.backlog"):
        agent = LLMAgent(
            llm_client=fake_llm,
            mcp_client=fake_mcp,
            conversation_manager=conv,
        )

        events = []
        async for event in agent.stream_events(
            "найди студента Уварова Анжела Павловна",
            session_id="test-session",
        ):
            events.append(event)

    assert fake_llm.call_count == 2, f"expected 2 LLM calls, got {fake_llm.call_count}"

    second_turn_messages = fake_llm.call_history[1]
    tool_messages = [m for m in second_turn_messages if m.get("role") == "tool"]
    assert len(tool_messages) >= 1, (
        f"no tool message in second turn: {second_turn_messages}"
    )

    tool_content = tool_messages[0]["content"]
    assert "Уварова Анжела Павловна" in tool_content, (
        f"student name not in tool_result: {tool_content}"
    )
    assert "474ebc19" in tool_content, f"student id not in tool_result: {tool_content}"

    assistant_with_tools = [
        m for m in second_turn_messages
        if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    assert len(assistant_with_tools) >= 1, "no assistant tool_calls in history"

    final_events = [e for e in events if e.type == "final"]
    assert len(final_events) == 1, f"expected 1 final event, got {len(final_events)}"

    final_data = final_events[0].data
    final_text = final_data.get("content", final_data.get("text", ""))
    assert "Уварова Анжела Павловна" in final_text, (
        f"student name not in final text: {final_text}"
    )


@pytest.mark.asyncio
async def test_tool_result_full_pipeline_messages():
    """Полный pipeline: проверяем каждый messages на каждом turn'е."""
    STUDENT_JSON = '{"course": 3, "full_name": "Тестов Тест", "id": "test-id-123"}'

    fake_llm = _FakeLLM(tool_data=STUDENT_JSON)
    fake_mcp = _FakeMCP(tool_data=STUDENT_JSON)

    conv = MagicMock()
    conv.normalize_session_id.return_value = "test-session"
    conv.get_history_messages.return_value = []
    conv.aget_history_messages = AsyncMock(return_value=[])
    conv.aremember_turn = AsyncMock(return_value=None)

    with patch("demo.api.agent.orchestrator.backlog"):
        agent = LLMAgent(
            llm_client=fake_llm,
            mcp_client=fake_mcp,
            conversation_manager=conv,
        )

        events = []
        async for event in agent.stream_events(
            "найди студента Тестов Тест", session_id="test-session"
        ):
            events.append(event)

    second_msgs = fake_llm.call_history[1]
    has_tool = any(
        m.get("role") == "tool" and "test-id-123" in m.get("content", "")
        for m in second_msgs
    )
    has_reminder = any(
        m.get("role") == "system" and "вернул данные" in m.get("content", "")
        for m in second_msgs
    )

    assert has_tool, f"no tool msg with student id in turn 2: {second_msgs}"
    assert has_reminder, "post-tool reminder missing in turn 2 messages"
