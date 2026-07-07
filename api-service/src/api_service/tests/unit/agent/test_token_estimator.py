"""Tests for token_estimator — pure functions for token estimation & trimming."""

from __future__ import annotations

from api_service.agent.token_estimator import estimate_tokens, trim_for_fallback


# ── estimate_tokens ─────────────────────────────────────────────────────────


class TestEstimateTokens:
    """Tests for the estimate_tokens() function."""

    def test_empty_list(self):
        """estimate_tokens([]) should return 0."""
        assert estimate_tokens([]) == 0

    def test_single_message(self):
        """estimate_tokens with one message returns positive int."""
        msgs = [{"role": "user", "content": "hello"}]
        result = estimate_tokens(msgs)
        assert isinstance(result, int)
        assert result > 0

    def test_multiple_messages(self):
        """estimate_tokens with multiple messages is larger than single."""
        one = [{"role": "user", "content": "hello"}]
        two = [
            {"role": "system", "content": "you are a bot"},
            {"role": "user", "content": "hello"},
        ]
        assert estimate_tokens(two) > estimate_tokens(one)

    def test_russian_text(self):
        """estimate_tokens handles Cyrillic text."""
        msgs = [{"role": "user", "content": "Привет, как дела?"}]
        result = estimate_tokens(msgs)
        assert isinstance(result, int)
        assert result > 0

    def test_long_content_scales(self):
        """estimate_tokens grows with content length."""
        short = [{"role": "user", "content": "a"}]
        long = [{"role": "user", "content": "a" * 1000}]
        assert estimate_tokens(long) > estimate_tokens(short)

    def test_nested_dict_content(self):
        """estimate_tokens handles dict values (e.g. tool_calls)."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"function": {"name": "foo", "arguments": '{"x":1}'}}],
            }
        ]
        result = estimate_tokens(msgs)
        assert result > 0


# ── trim_for_fallback ────────────────────────────────────────────────────────


class TestTrimForFallback:
    """Tests for the trim_for_fallback() function."""

    def test_empty_list(self):
        """trim_for_fallback([]) returns []."""
        assert trim_for_fallback([]) == []

    def test_single_system_message(self):
        """trim_for_fallback with 1 message returns same length."""
        msgs = [{"role": "system", "content": "sp"}]
        result = trim_for_fallback(msgs)
        assert len(result) == 1
        assert result[0] == msgs[0]

    def test_exactly_three_messages(self):
        """trim_for_fallback with 3 messages returns them all."""
        msgs = [
            {"role": "system", "content": "sp"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = trim_for_fallback(msgs)
        assert len(result) == 3
        assert result == msgs

    def test_five_or_more_messages(self):
        """trim_for_fallback with 5+ messages keeps system + last 4."""
        msgs = [
            {"role": "system", "content": "sp"},
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "q3"},
        ]
        result = trim_for_fallback(msgs)
        # Expected: [system] + last 4 = 5 messages
        assert len(result) == 5
        assert result[0] == msgs[0]  # system prompt preserved
        assert result[1:] == msgs[-4:]  # last 4 preserved

    def test_returns_new_list(self):
        """trim_for_fallback returns a new list, not the same reference."""
        msgs = [{"role": "system", "content": "sp"}, {"role": "user", "content": "hi"}]
        result = trim_for_fallback(msgs)
        assert result is not msgs
        msgs.append({"role": "assistant", "content": "bye"})
        assert len(result) == 2  # original unaffected

    def test_system_prompt_first_preserved(self):
        """The first element (system prompt) is always preserved."""
        msgs = [
            {"role": "system", "content": "critical prompt"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ]
        result = trim_for_fallback(msgs)
        assert result[0]["content"] == "critical prompt"
