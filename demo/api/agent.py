from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from demo.settings import PROJECT_ROOT, settings

# Set up debug logging for agent operations
logger = logging.getLogger("demo.api.agent")


# System prompt for the assistant
SYSTEM_PROMPT = """Ты университетский ассистент.
Отвечай по-русски, кратко и по делу. Для данных о студентах, расписании,
oценках, преподавателях и документах используй доступные MCP-инструменты.

Правила работы с документами:
- Если пользователь спрашивает про доступные материалы, сначала найди студента
  и его дисциплины, затем покажи материалы только по этим дисциплинам.
- В списке материалов не пропускай PDF: документы с mime_type application/pdf
  называй "Лекция (PDF)".
- Если пользователь просит пересказать, найти или объяснить что-то внутри
  документа, используй context_search_in_documents или search_documents, а не
  только list_documents.
- Не придумывай содержимое документов. Если найденных фрагментов мало, скажи
  что данных недостаточно.

Если данных не хватает, прямо скажи об этом и предложи уточнить запрос."""


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Create and manage an MCP client session."""
    logger.debug("[AGENT] Creating MCP session...")
    server_path = str(PROJECT_ROOT / "server.py")
    logger.debug(f"[AGENT] Starting MCP server at: {server_path}")
    params = StdioServerParameters(
        command=settings.python_executable,
        args=[server_path],
        env={**dict(os.environ), "PYTHONPATH": str(PROJECT_ROOT)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            logger.debug("[AGENT] MCP session initialized")
            yield session
            logger.debug("[AGENT] MCP session closing")


async def list_ollama_tools(session: ClientSession) -> list[dict[str, Any]]:
    """List all available MCP tools from the server."""
    result = await session.list_tools()
    tools = []
    for tool in result.tools:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
        )
    return tools


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
    """Call an MCP tool and return the result as a string."""
    try:
        logger.debug(f"[AGENT] MCP call_tool: {name} with args: {arguments}")
        result = await session.call_tool(name, arguments)
        if result.isError:
            error_text = _collect_text_content(result)
            logger.warning(f"[AGENT] Tool {name} returned error: {error_text}")
            return json.dumps({"error": error_text or f"Ошибка вызова инструмента {name}"}, ensure_ascii=False)

        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            logger.debug(f"[AGENT] Tool {name} returned structured: {structured}")
            return json.dumps(structured, ensure_ascii=False)

        content = _collect_text_content(result)
        if not content:
            logger.warning(f"[AGENT] Tool {name} returned empty content")
        return content or f"Инструмент {name} вернул пустой результат"
    except Exception as exc:
        logger.exception(f"[AGENT] Exception calling tool {name}")
        return json.dumps({"error": f"Ошибка при вызове инструмента {name}: {str(exc)}"}, ensure_ascii=False)


def _collect_text_content(result: Any) -> str:
    """Collect text content from MCP tool result."""
    parts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


class OllamaAgent:
    """Agent that handles Ollama communication, tool calling, and context management."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = httpx.Timeout(settings.request_timeout)

    async def stream_answer(self, user_message: str) -> AsyncIterator[str]:
        """Stream an answer to a user message, handling tool calls recursively."""
        logger.info(f"[AGENT] User message: {user_message[:100]}...")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_available(client)
            async with mcp_session() as session:
                tools = await list_ollama_tools(session)
                logger.info(f"[AGENT] Available tools: {[t['function']['name'] for t in tools]}")
                for _ in range(4):
                    logger.info("[AGENT] Iteration - calling model...")
                    message = await self._chat_once(client, messages, tools)
                    logger.info(f"[AGENT] Model response: {json.dumps(message, ensure_ascii=False)[:200]}...")
                    
                    tool_calls = self._extract_tool_calls(message)
                    logger.info(f"[AGENT] Extracted tool calls: {len(tool_calls)} - {tool_calls}")
                    
                    if not tool_calls:
                        # No tool calls - this is the final model response
                        if content := message.get("content"):
                            logger.info(f"[AGENT] Final content: {content[:100]}...")
                            yield content
                            return
                        # If no content, continue to streaming final
                        logger.info("[AGENT] No tool calls and no content, breaking to streaming...")
                        break

                    # Model has tool calls to make
                    logger.info(f"[AGENT] Processing {len(tool_calls)} tool call(s)")
                    messages.append(message)
                    for tool_call in tool_calls:
                        name = tool_call["name"]
                        arguments = tool_call["arguments"]
                        logger.info(f"[AGENT] Calling tool: {name} with args: {arguments}")
                        yield f"\n\n[tool:{name}]\n"
                        tool_result = await call_tool(session, name, arguments)
                        logger.info(f"[AGENT] Tool {name} result: {tool_result[:200]}...")
                        messages.append(
                            {
                                "role": "tool",
                                "content": tool_result,
                                "tool_name": name,
                            }
                        )
                else:
                    # We went through all 4 iterations with tool calls
                    # Model needs to give final answer via streaming
                    logger.info("[AGENT] Used all 4 iterations, switching to streaming final...")
                    has_tokens = False
                    async for token in self._stream_final(client, messages):
                        has_tokens = True
                        yield token
                    if not has_tokens:
                        logger.warning("[AGENT] No tokens from streaming final after 4 iterations")
                        yield "Извините, модель завершила работу без ответа. Попробуйте уточнить запрос."
                    return

                # If we broke from loop (no tool calls), check for content
                # If there was content, we already returned above
                # If there was no content, try streaming final
                if not message.get("content"):
                    logger.info("[AGENT] No content in final message, trying streaming final...")
                    has_tokens = False
                    async for token in self._stream_final(client, messages):
                        has_tokens = True
                        yield token
                    if not has_tokens:
                        logger.warning("[AGENT] No tokens from streaming final")
                        yield "Извините, модель завершила работу без ответа. Попробуйте уточнить запрос."

    async def health(self) -> dict[str, Any]:
        """Check Ollama server health and available models."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
        return {"status": "ok", "model": self.model, "models": data.get("models", [])}

    async def _ensure_available(self, client: httpx.AsyncClient) -> None:
        """Ensure Ollama server is available."""
        try:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama недоступна по адресу {self.base_url}. "
                "Запустите Ollama и проверьте OLLAMA_URL."
            ) from exc

    async def _chat_once(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send a single chat request to Ollama."""
        logger.debug(f"[AGENT] _chat_once: sending {len(messages)} messages, {len(tools)} tools")
        response = await client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "stream": False,
            },
        )
        response.raise_for_status()
        result = response.json().get("message", {})
        logger.debug(f"[AGENT] _chat_once: got content len={len(result.get('content', ''))}, tool_calls={bool(result.get('tool_calls'))}")
        return result

    async def _stream_final(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Stream the final response from Ollama."""
        logger.debug(f"[AGENT] _stream_final: starting with {len(messages)} messages")
        async with client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    logger.debug(f"[AGENT] _stream_final: got token (len={len(content)})")
                    yield content
                else:
                    logger.debug(f"[AGENT] _stream_final: empty content in chunk")

    @staticmethod
    def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool calls from an Ollama message."""
        calls = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            name = function.get("name")
            raw_args = function.get("arguments") or function.get("args") or {}
            if not name:
                continue
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            else:
                arguments = raw_args
            calls.append({"name": name, "arguments": arguments})
        return calls


# Global agent instance
agent = OllamaAgent()
