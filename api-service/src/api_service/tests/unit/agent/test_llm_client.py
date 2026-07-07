import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api_service.agent.llm_client import LLMClient


@pytest.mark.asyncio
async def test_llm_client_stream_completion():
    # Mocking LiteLLM
    with (
        patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion,
        patch("litellm.stream_chunk_builder") as mock_chunk_builder,
    ):
        # Setup mock
        from litellm import CustomStreamWrapper

        mock_response = MagicMock(spec=CustomStreamWrapper)

        # Mocking async iterator
        async def async_iter(*args, **kwargs):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock(content="Hello")
            yield chunk

        mock_response.__aiter__ = async_iter
        mock_acompletion.return_value = mock_response

        # Setup final mock
        from litellm.types.utils import ModelResponse

        final_msg = MagicMock(spec=ModelResponse)
        final_msg.choices = [MagicMock()]
        final_msg.choices[0].message = MagicMock(role="assistant", content="Hello")
        final_msg.choices[0].message.tool_calls = None
        final_msg.choices[0].message.reasoning_content = None
        mock_chunk_builder.return_value = final_msg

        # Execute
        client = LLMClient(model="test-model")
        messages = [{"role": "user", "content": "Hi"}]

        results = []
        async for token, final in client.stream_completion(messages):
            results.append((token, final))

        assert len(results) == 2
        assert results[0] == ("Hello", None)
        assert results[1][0] is None
        assert results[1][1]["content"] == "Hello"
