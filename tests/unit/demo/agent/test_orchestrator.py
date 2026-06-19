import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from demo.api.agent.orchestrator import LLMAgent, AgentEvent

@pytest.mark.asyncio
async def test_llm_agent_stream_events():
    # Setup mocks
    mock_llm_client = AsyncMock()
    mock_mcp_client = AsyncMock()
    mock_conv_manager = MagicMock()
    
    # Mock LLM stream
    mock_llm_client.stream_completion.return_value = async_iter_return_final({"role": "assistant", "content": "Hello"})
    
    # Mock MCP session properly
    # The Orchestrator calls mcp_client.get_session(), which returns an AsyncContextManager
    mock_mcp_session = AsyncMock()
    mock_mcp_client.get_session.return_value.__aenter__.return_value = mock_mcp_session
    mock_mcp_client.list_tools.return_value = []
    
    # Mocking backlog (it is used in orchestrator)
    with patch("demo.api.agent.orchestrator.backlog"):
        agent = LLMAgent(
            llm_client=mock_llm_client,
            mcp_client=mock_mcp_client,
            conversation_manager=mock_conv_manager
        )
        
        events = []
        async for event in agent.stream_events("Hello", session_id="default"):
            events.append(event)
            
        assert any(e.type == "final" for e in events)

async def async_iter_return_final(final_val):
    yield (None, final_val)
