from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from demo.settings import PROJECT_ROOT, settings


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
    server_path = str(PROJECT_ROOT / "server.py")
    params = StdioServerParameters(
        command=settings.python_executable,
        args=[server_path],
        env={**dict(os.environ), "PYTHONPATH": str(PROJECT_ROOT)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


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
        result = await session.call_tool(name, arguments)
        if result.isError:
            error_text = _collect_text_content(result)
            return json.dumps({"error": error_text or f"Ошибка вызова инструмента {name}"}, ensure_ascii=False)

        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False)

        content = _collect_text_content(result)
        return content or f"Инструмент {name} вернул пустой результат"
    except Exception as exc:
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
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_available(client)
            async with mcp_session() as session:
                tools = await list_ollama_tools(session)
                for _ in range(4):
                    message = await self._chat_once(client, messages, tools)
                    tool_calls = self._extract_tool_calls(message)
                    if not tool_calls:
                        if content := message.get("content"):
                            yield content
                        else:
                            # Model returned no content and no tool calls
                            yield "Извините, не удалось получить ответ. Попробуйте переформулировать запрос."
                        return

                    messages.append(message)
                    for tool_call in tool_calls:
                        name = tool_call["name"]
                        arguments = tool_call["arguments"]
                        yield f"\n\n[tool:{name}]\n"
                        tool_result = await call_tool(session, name, arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "content": tool_result,
                                "tool_name": name,
                            }
                        )

                # After 4 iterations with tool calls, get final streaming response
                has_tokens = False
                async for token in self._stream_final(client, messages):
                    has_tokens = True
                    yield token

                if not has_tokens:
                    # Model didn't return any final text
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
        return response.json().get("message", {})

    async def _stream_final(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Stream the final response from Ollama."""
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
                    yield content

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
