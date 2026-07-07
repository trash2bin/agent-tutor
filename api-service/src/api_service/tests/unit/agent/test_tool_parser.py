import pytest
from api_service.agent.tool_parser import ToolCallParser
from api_service.agent.types import ParsedToolCall


@pytest.fixture
def parser():
    return ToolCallParser()


def test_extract_native_tool_calls(parser):
    message = {
        "tool_calls": [
            {
                "id": "1",
                "function": {
                    "name": "get_student",
                    "arguments": '{"student_id": "123"}',
                },
            }
        ]
    }
    calls = parser.extract_tool_calls(message)
    assert len(calls) == 1
    assert calls[0]["name"] == "get_student"
    assert calls[0]["arguments"] == {"student_id": "123"}


def test_extract_json_tool_calls_markdown(parser):
    message = {
        "content": '```json\n{"tool_name": "get_disciplines", "arguments": {"student_id": "456"}}\n```'
    }
    calls = parser.extract_tool_calls(message)
    assert len(calls) == 1
    assert calls[0]["name"] == "get_disciplines"
    assert calls[0]["arguments"] == {"student_id": "456"}


def test_parse_tool_arguments_invalid(parser):
    assert parser.parse_tool_arguments("invalid-json") == {}
    assert parser.parse_tool_arguments(123) == {}


def test_format_for_model(parser):
    tool_call = ParsedToolCall(id="1", name="test_tool", arguments={"key": "val"})
    formatted = parser.format_for_model([tool_call])
    assert len(formatted) == 1
    assert formatted[0]["function"]["name"] == "test_tool"
    assert '{"key": "val"}' in formatted[0]["function"]["arguments"]
