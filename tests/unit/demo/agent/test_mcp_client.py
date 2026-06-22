import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from mcp import ClientSession
from demo.api.agent.mcp_client import MCPClient


@pytest.mark.asyncio
async def test_mcp_client_list_tools():
    # Setup mock session
    mock_session = AsyncMock(spec=ClientSession)
    mock_tools_result = MagicMock()

    # Mocking individual tool
    tool1 = MagicMock()
    tool1.name = "get_student"
    tool1.description = "Get student info"
    tool1.inputSchema = {"type": "object"}

    mock_tools_result.tools = [tool1]
    mock_session.list_tools.return_value = mock_tools_result

    client = MCPClient()
    tools = await client.list_tools(mock_session)

    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "get_student"
    assert tools[0]["function"]["parameters"] == {"type": "object"}


@pytest.mark.asyncio
async def test_mcp_client_call_tool_success():
    mock_session = AsyncMock(spec=ClientSession)

    # Mock result with text content
    mock_result = MagicMock()
    mock_result.isError = False
    mock_result.content = [MagicMock(text="Student found")]
    mock_result.structuredContent = None

    mock_session.call_tool.return_value = mock_result

    client = MCPClient()
    response = await client.call_tool(mock_session, "get_student", {"id": "123"})

    data = json.loads(response)
    assert data["ok"] is True
    assert data["data"] == "Student found"


@pytest.mark.asyncio
async def test_mcp_client_call_tool_error():
    mock_session = AsyncMock(spec=ClientSession)

    # Mock result error
    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = [MagicMock(text="Error message")]

    mock_session.call_tool.return_value = mock_result

    client = MCPClient()
    response = await client.call_tool(mock_session, "get_student", {"id": "123"})

    data = json.loads(response)
    assert data["ok"] is False
    assert data["error"] == "Error message"
