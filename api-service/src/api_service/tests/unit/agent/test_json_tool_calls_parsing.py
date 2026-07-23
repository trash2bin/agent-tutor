"""Regression: LLM returns tool calls as JSON text → pipeline executes them.

Некоторые модели (MiniMax, локальные) не умеют возвращать
структурированные tool_calls через поле ``tool_calls``,
и пишут их как JSON-массив в content.

Раньше LLMStage шёл в `elif response.content:` → эмитил `final`
с голым JSON-текстом, который летел пользователю.

Фикс: парсинг через ToolCallParser.extract_tool_calls().
"""

from __future__ import annotations

import pytest

from api_service.agent.pipeline import Pipeline
from api_service.agent.stages import (
    LLMStage,
    ToolExecutionStage,
)
from api_service.agent.middlewares import (
    SpendingMiddleware,
    BacklogMiddleware,
)

from .helpers import (
    TestLLMProvider,
    TestMCPProvider,
    llm_response,
    make_pipeline_ctx,
    collect_events,
)


class TestJsonToolCallsParsing:
    """LLM возвращает тулы как JSON-текст — пайплайн должен их выполнить."""

    @pytest.mark.asyncio
    async def test_json_array_text_is_executed_as_tool(self):
        """Content=[{"name":"get_product","arguments":{"id":1}}] → tool_executed."""
        llm = TestLLMProvider()
        llm.queue(
            llm_response.text_tool_calls([("get_product", {"id": 1059})]),
            llm_response.final("OK"),
        )

        mcp = TestMCPProvider()
        mcp.add_tool("get_product", {"id": 1059, "name": "OIL-01245", "price": 2500})

        pipeline = Pipeline(
            stages=[LLMStage(), ToolExecutionStage()],
            middlewares=[SpendingMiddleware(), BacklogMiddleware()],
        )
        ctx = await make_pipeline_ctx(llm_provider=llm, mcp_provider=mcp)

        events = await collect_events(pipeline.run(ctx))

        event_types = [t for t, _ in events]

        # ❌ Не должно быть final с голым JSON
        final_events = [(t, d) for t, d in events if t == "final"]
        final_content = ""
        for _, fd in final_events:
            if isinstance(fd, dict):
                final_content = fd.get("content", "")
        assert "Tool Calls" not in final_content, (
            f"JSON-текст тулов улетел в final: {final_content[:300]}"
        )
        assert not final_content.startswith("["), (
            f"JSON-массив тулов улетел в final: {final_content[:300]}"
        )
        assert final_content == "OK", (
            f"После парсинга должен быть нормальный final, а не JSON: {final_content[:200]}"
        )

        # ✅ Должен быть tool_call и tool_result
        assert "tool_call" in event_types, f"Должен быть tool_call: {event_types}"
        assert "tool_result" in event_types, f"Должен быть tool_result: {event_types}"
        # ✅ Проверяем что тул выполнился
        assert len(mcp.call_history) == 1
        assert mcp.call_history[0]["name"] == "get_product"
        assert mcp.call_history[0]["arguments"] == {"id": 1059}

    @pytest.mark.asyncio
    async def test_json_array_text_with_multiple_calls(self):
        """Content=[{...}, {...}] — все тулы выполняются."""
        llm = TestLLMProvider()
        llm.queue(
            llm_response.text_tool_calls(
                [
                    ("get_product", {"id": 1059}),
                    ("get_product", {"id": 1060}),
                ]
            ),
            llm_response.final("OK"),
        )

        mcp = TestMCPProvider()
        mcp.add_tool("get_product", {"id": 0, "name": "placeholder"})

        pipeline = Pipeline(
            stages=[LLMStage(), ToolExecutionStage()],
            middlewares=[SpendingMiddleware(), BacklogMiddleware()],
        )
        ctx = await make_pipeline_ctx(llm_provider=llm, mcp_provider=mcp)
        events = await collect_events(pipeline.run(ctx))

        final_events = [(t, d) for t, d in events if t == "final"]
        final_content = ""
        for _, fd in final_events:
            if isinstance(fd, dict):
                final_content = fd.get("content", "")
        assert "Tool Calls" not in final_content, (
            f"Множественные тулы ушли в final: {final_content[:200]}"
        )
        assert len(mcp.call_history) == 2, (
            f"Должны быть выполнены оба тула: {[h['name'] for h in mcp.call_history]}"
        )
        assert mcp.call_history[0]["arguments"] == {"id": 1059}
        assert mcp.call_history[1]["arguments"] == {"id": 1060}

    @pytest.mark.asyncio
    async def test_text_tool_calls_then_final(self):
        """JSON тул → результат → следующий раунд LLM → финал."""
        llm = TestLLMProvider()
        llm.queue(
            llm_response.text_tool_calls([("get_product", {"id": 1059})]),
            llm_response.final("Castrol OIL-01245 стоит 2500 руб, артикул 1059"),
        )

        mcp = TestMCPProvider()
        mcp.add_tool("get_product", {"id": 1059, "name": "OIL-01245", "price": 2500})

        pipeline = Pipeline(
            stages=[LLMStage(), ToolExecutionStage()],
            middlewares=[SpendingMiddleware(), BacklogMiddleware()],
        )
        ctx = await make_pipeline_ctx(llm_provider=llm, mcp_provider=mcp)
        events = await collect_events(pipeline.run(ctx))

        event_types = [t for t, _ in events]
        assert "tool_call" in event_types, f"Нет tool_call: {event_types}"
        assert "tool_result" in event_types, f"Нет tool_result: {event_types}"
        assert "final" in event_types, f"Нет final: {event_types}"

        # Tool result попал в messages второго вызова
        assert len(llm.call_history) >= 2
        second_call_req = llm.call_history[1]
        tool_msgs = [m for m in second_call_req.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1, (
            f"Tool result должен быть в messages второго вызова. "
            f"Роли: {[m.get('role') for m in second_call_req.messages]}"
        )
        assert "OIL-01245" in tool_msgs[0].get("content", "")

    @pytest.mark.asyncio
    async def test_mixed_then_final(self):
        """Полная имитация виджета — реальный сценарий бага.

        schema → grep → filter (как текст) → финал
        """
        llm = TestLLMProvider()
        llm.queue(
            llm_response.tool_call("schema_catalog_product", {}),
            llm_response.tool_call("grep_catalog_brand", {"pattern": "Castrol"}),
            llm_response.text_tool_calls(
                [
                    ("filter_catalog_product", {"brand_id": 72, "limit": 20}),
                ]
            ),
            llm_response.final("Нашёл масло Castrol: арт. OIL-01245, цена 2500 руб"),
        )

        mcp = TestMCPProvider()
        mcp.add_tool(
            "schema_catalog_product", {"columns": ["id", "name", "price", "brand_id"]}
        )
        mcp.add_tool(
            "grep_catalog_brand",
            {"preview": [{"id": 72, "name": "Castrol"}], "returned": 1},
        )
        mcp.add_tool(
            "filter_catalog_product",
            {
                "preview": [
                    {"id": 1059, "name": "OIL-01245"},
                    {"id": 1060, "name": "OIL-01246"},
                ],
                "returned": 2,
            },
        )

        pipeline = Pipeline(
            stages=[LLMStage(), ToolExecutionStage()],
            middlewares=[SpendingMiddleware(), BacklogMiddleware()],
        )
        ctx = await make_pipeline_ctx(llm_provider=llm, mcp_provider=mcp)
        events = await collect_events(pipeline.run(ctx))

        event_types = [t for t, _ in events]

        # ❌ ГЛАВНАЯ ПРОВЕРКА: ни один тул не должен уйти в final как JSON!
        final_events = [(t, d) for t, d in events if t == "final"]
        for _, fd in final_events:
            content = ""
            if isinstance(fd, dict):
                content = fd.get("content", "") or fd.get("data", "")
            elif isinstance(fd, str):
                content = fd
            assert "Tool Calls" not in content, (
                f"JSON-текст тулов улетел в final! Финал: {content[:300]}"
            )
            assert "[{" not in content, (
                f"JSON-массив тулов улетел в final! Финал: {content[:300]}"
            )

        assert llm.call_count == 4, f"Должно быть 4 LLM-вызова, было {llm.call_count}"
        assert len(mcp.call_history) == 3, (
            f"Должно быть 3 tool calls: {[h['name'] for h in mcp.call_history]}"
        )
        assert "tool_call" in event_types, f"Нет tool_call: {event_types}"
        assert "tool_result" in event_types, f"Нет tool_result: {event_types}"
        assert "final" in event_types, f"Нет final: {event_types}"

        # Финальный ответ человекочитаемый
        final_content = ""
        for _, fd in final_events:
            if isinstance(fd, dict):
                final_content = fd.get("content", "")
        assert "OIL-01245" in final_content, (
            f"Финал не содержит данных: {final_content}"
        )

    @pytest.mark.asyncio
    async def test_normal_tool_call_still_works(self):
        """Проверка что обычные tool_calls не сломались парсингом."""
        llm = TestLLMProvider()
        llm.queue(
            llm_response.tool_call("get_product", {"id": 42}),
            llm_response.final("OK"),
        )

        mcp = TestMCPProvider()
        mcp.add_tool("get_product", {"id": 42, "name": "Test"})

        pipeline = Pipeline(
            stages=[LLMStage(), ToolExecutionStage()],
            middlewares=[SpendingMiddleware(), BacklogMiddleware()],
        )
        ctx = await make_pipeline_ctx(llm_provider=llm, mcp_provider=mcp)
        events = await collect_events(pipeline.run(ctx))

        event_types = [t for t, _ in events]
        assert "tool_call" in event_types, f"Обычный tool_call сломался: {event_types}"
        assert "tool_result" in event_types, (
            f"Обычный tool_result сломался: {event_types}"
        )
        assert "final" in event_types, f"Обычный final сломался: {event_types}"
