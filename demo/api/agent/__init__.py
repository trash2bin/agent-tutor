"""Agent package for the LLM-based assistant."""

from __future__ import annotations

from .conversation import ConversationManager
from .llm_client import LLMClient
from .mcp_client import MCPClient
from .orchestrator import AgentEvent, LLMAgent, SYSTEM_PROMPT, agent
from .tool_parser import ToolCallParser
from .types import EventType, Message, ParsedToolCall, SessionId, TurnId

__all__ = [
    "AgentEvent",
    "ConversationManager",
    "EventType",
    "LLMAgent",
    "LLMClient",
    "MCPClient",
    "agent",
    "SYSTEM_PROMPT",
    "ToolCallParser",
    # Types
    "Message",
    "ParsedToolCall",
    "SessionId",
    "TurnId",
]
