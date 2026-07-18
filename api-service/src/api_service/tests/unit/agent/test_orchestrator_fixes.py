"""Tests for orchestrator fixes: handler restoration and schema caching.

See: AGENTS.md audit — _run_turn handler mutation (needs contextmanager restore)
and _build_schema_message (needs per-tenant cache).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from api_service.agent.orchestrator import LLMAgent
from api_service.agent.types import AgentEvent


# ── Shared fakes ─────────────────────────────────────────────────────────────


class FakeLLMClient:
    """Minimal fake LLM client for handler tests."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.model = "test-model"
        self.api_base = "http://test"
        self.enable_thinking = False
        self.last_usage: dict[str, int] | None = {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8,
        }
        self.last_cost: float = 0.0005

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tenant_ids: list[str] | None = None,
    ) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
        yield ("ok", None)
        yield (None, {"role": "assistant", "content": "ok"})

    async def stream_answer(
        self, user_message: str, system_prompt: str | None = None
    ) -> AsyncIterator[str]:
        yield "ok"


class FakeMCPClient:
    """Mock MCP client with controllable session schema."""

    def __init__(self, schema: dict | None = None):
        self.schema = schema

    @contextlib.asynccontextmanager
    async def get_session(self, tenant_ids=None):
        proxy = AsyncMock()
        proxy.tenant_ids = tenant_ids or []
        proxy.list_tools = AsyncMock(return_value=[])
        proxy.call_tool = AsyncMock()
        proxy.get_schema = AsyncMock(return_value=self.schema)
        yield proxy

    async def list_tools(self, session):
        return []

    async def call_tool(self, session, name: str, arguments: dict[str, Any]):
        return None

    async def get_display_name(self, tenant_ids, tool_name):
        return tool_name

    async def close(self):
        pass


@pytest.fixture
def conv_manager():
    """Conversation manager mock."""
    mgr = AsyncMock()
    mgr.normalize_session_id = lambda x: x

    lock_mock = AsyncMock()
    lock_mock.__aenter__ = AsyncMock()
    lock_mock.__aexit__ = AsyncMock(return_value=None)
    mgr.get_session_lock = AsyncMock(return_value=lock_mock)

    mgr.load_history = AsyncMock(return_value=[])
    mgr.aremember_turn = AsyncMock()
    mgr.aget_history_messages = AsyncMock(return_value=[])
    return mgr


# ── Test A: handler restoration ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handler_restored_after_custom_llm(conv_manager):
    """After stream_events with custom llm_client, handlers revert to defaults.

    This test FAILS before the fix because _run_turn mutates self._llm_handler
    and self._fallback_handler without restoring them.

    After the fix (contextmanager), handlers should be restored in finally.
    """
    default_llm = FakeLLMClient(name="default")
    custom_llm = FakeLLMClient(name="custom")
    mcp = FakeMCPClient(schema=None)  # no schema, no _build_schema_message call
    agent = LLMAgent(
        llm_client=default_llm, mcp_client=mcp, conversation_manager=conv_manager
    )

    # Sanity: default handler uses default_llm
    assert agent._llm_handler._llm is default_llm, (
        f"Expected default handler, got {agent._llm_handler._llm}"
    )

    # Call stream_events with custom LLM
    events: list[AgentEvent] = []
    async for event in agent.stream_events(
        "hello", session_id="test-handler", llm_client=custom_llm
    ):
        events.append(event)

    # AFTER the call, handlers MUST be restored to defaults
    assert agent._llm_handler._llm is default_llm, (
        f"Handler NOT restored after custom LLM call. "
        f"Expected default ({id(default_llm)}), "
        f"got {agent._llm_handler._llm} ({id(agent._llm_handler._llm)})"
    )
    assert agent._fallback_handler._llm is default_llm, (
        "Fallback handler NOT restored after custom LLM call"
    )

    # Verify no errors from the call
    errors = [e for e in events if e.type == "error"]
    assert len(errors) == 0, f"Unexpected errors: {errors}"


@pytest.mark.asyncio
async def test_handler_not_affected_without_custom_llm(conv_manager):
    """Without custom llm, default handlers stay unchanged."""
    llm = FakeLLMClient(name="default")
    mcp = FakeMCPClient(schema=None)
    agent = LLMAgent(llm_client=llm, mcp_client=mcp, conversation_manager=conv_manager)

    orig_llm_handler = agent._llm_handler
    orig_fallback_handler = agent._fallback_handler

    async for _ in agent.stream_events("test", session_id="test-default"):
        pass

    assert agent._llm_handler is orig_llm_handler, "LLM handler identity changed"
    assert agent._fallback_handler is orig_fallback_handler, (
        "Fallback handler identity changed"
    )
    assert agent._llm_handler._llm is llm, "LLM reference changed"


@pytest.mark.asyncio
async def test_handler_restored_even_on_inner_error(conv_manager):
    """If _run_turn encounters an error, handlers still restored by contextmanager finally.

    _run_turn catches Exception and yields AgentEvent("error"), so
    we don't expect a raised exception — just check handlers are restored.
    """
    default_llm = FakeLLMClient(name="default")
    custom_llm = FakeLLMClient(name="custom")

    # MCP that raises (simulates data-service error during session open)
    class BrokenMCP(FakeMCPClient):
        @contextlib.asynccontextmanager
        async def get_session(self, tenant_ids=None):
            raise RuntimeError("data-service unreachable")

    agent = LLMAgent(
        llm_client=default_llm,
        mcp_client=BrokenMCP(),
        conversation_manager=conv_manager,
    )

    events: list[AgentEvent] = []
    async for event in agent.stream_events(
        "hello", session_id="test-error", llm_client=custom_llm
    ):
        events.append(event)

    # Should have an error event
    errors = [e for e in events if e.type == "error"]
    assert len(errors) > 0, f"Expected error events, got {[e.type for e in events]}"

    # Even after error, handlers restored
    assert agent._llm_handler._llm is default_llm, (
        f"Handler NOT restored after error. Got {agent._llm_handler._llm}"
    )


# ── Test B: schema cache ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_schema_cached_per_tenant(conv_manager):
    """_build_schema_message is called only once per tenant across turns.

    This test FAILS before the fix because _build_schema_message is called
    on every _run_turn without caching.
    """
    # Monkey-patch _build_schema_message with a counting wrapper
    import api_service.agent.orchestrator as orch

    original = orch._build_schema_message
    call_count = 0

    def counting_build_schema_message(schema: dict) -> str:
        nonlocal call_count
        call_count += 1
        return original(schema)

    orch._build_schema_message = counting_build_schema_message

    try:
        schema_response = {
            "entities": [
                {
                    "name": "student",
                    "description": "Students info",
                    "search_fields": "name",
                    "filter_fields": [],
                    "relations": [],
                }
            ],
            "workflow_hints": ["Use search for students"],
        }

        llm = FakeLLMClient()
        mcp = FakeMCPClient(schema=schema_response)
        agent = LLMAgent(
            llm_client=llm, mcp_client=mcp, conversation_manager=conv_manager
        )

        # First call with tenant-a → should call _build_schema_message
        async for _ in agent.stream_events(
            "test", session_id="test-cache-1", tenant_ids=["tenant-a"]
        ):
            pass
        assert call_count == 1, (
            f"_build_schema_message called {call_count} times on first turn, expected 1"
        )

        # Second call with SAME tenant → should use cache
        async for _ in agent.stream_events(
            "test2", session_id="test-cache-2", tenant_ids=["tenant-a"]
        ):
            pass
        assert call_count == 1, (
            f"_build_schema_message called {call_count} times total, "
            f"expected 1 (cached). TIP: add self._schema_cache in LLMAgent."
        )

    finally:
        orch._build_schema_message = original


@pytest.mark.asyncio
async def test_schema_cache_different_tenants_not_shared(conv_manager):
    """Different tenant_ids produce different cache entries."""
    import api_service.agent.orchestrator as orch

    original = orch._build_schema_message
    call_count = 0

    def counting_build_schema_message(schema: dict) -> str:
        nonlocal call_count
        call_count += 1
        return original(schema)

    orch._build_schema_message = counting_build_schema_message

    try:
        schema_response = {
            "entities": [
                {
                    "name": "student",
                    "description": "Students",
                    "search_fields": "name",
                    "filter_fields": [],
                    "relations": [],
                }
            ],
            "workflow_hints": [],
        }

        llm = FakeLLMClient()
        mcp = FakeMCPClient(schema=schema_response)
        agent = LLMAgent(
            llm_client=llm, mcp_client=mcp, conversation_manager=conv_manager
        )

        # First: tenant-a
        async for _ in agent.stream_events(
            "test", session_id="test-1", tenant_ids=["tenant-a"]
        ):
            pass
        assert call_count == 1

        # Second: tenant-b (different)
        async for _ in agent.stream_events(
            "test2", session_id="test-2", tenant_ids=["tenant-b"]
        ):
            pass

        # Should be called again for different tenant
        assert call_count == 2, (
            f"_build_schema_message called {call_count} times, "
            f"expected 2 (separate tenants)"
        )
    finally:
        orch._build_schema_message = original
