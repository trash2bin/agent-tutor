"""Tests for per-tenant LLM spending limits."""

from __future__ import annotations

import pytest

from api_service.spending import SpendingChecker, SpendingConfig


@pytest.fixture
def checker():
    """SpendingChecker with test config."""
    config = SpendingConfig(enabled=True, default_budget=50.0)
    return SpendingChecker(config=config)


class TestSpending:
    """All spending limit test scenarios."""

    def test_checker_allows_under_budget(self, checker):
        """Spending $10 при бюджете $50 → allowed."""
        checker.record_spending("tenant-a", 10.0)
        allowed, reason = checker.check_limits("tenant-a")
        assert allowed is True
        assert reason == ""

    def test_checker_blocks_over_budget(self, checker):
        """Spending $60 при бюджете $50 → blocked."""
        checker.record_spending("tenant-a", 60.0)
        allowed, reason = checker.check_limits("tenant-a")
        assert allowed is False
        assert "limit exceeded" in reason.lower()

    def test_checker_blocks_at_exact_budget(self, checker):
        """Spending ровно $50 → blocked (на границе)."""
        checker.record_spending("tenant-a", 50.0)
        allowed, reason = checker.check_limits("tenant-a")
        assert allowed is False

    def test_checker_zero_budget_means_no_limit(self):
        """Budget=0 → allowed всегда."""
        config = SpendingConfig(enabled=True, default_budget=0.0)
        no_limit = SpendingChecker(config=config)
        no_limit.record_spending("tenant-a", 999999.0)
        allowed, reason = no_limit.check_limits("tenant-a")
        assert allowed is True

    def test_checker_accumulates_spending(self, checker):
        """Несколько вызовов суммируются."""
        checker.record_spending("tenant-a", 10.0)
        checker.record_spending("tenant-a", 20.0)
        checker.record_spending("tenant-a", 15.0)
        allowed, _ = checker.check_limits("tenant-a")
        assert allowed is True  # total = 45 < 50
        checker.record_spending("tenant-a", 10.0)
        allowed, _ = checker.check_limits("tenant-a")
        assert allowed is False  # total = 55 >= 50

    def test_checker_per_tenant_isolation(self, checker):
        """Spending tenant-a не влияет на tenant-b."""
        checker.record_spending("tenant-a", 60.0)
        allowed_a, _ = checker.check_limits("tenant-a")
        allowed_b, _ = checker.check_limits("tenant-b")
        assert allowed_a is False
        assert allowed_b is True  # tenant-b ничего не тратил

    def test_checker_disabled_if_not_enabled(self):
        """SPENDING_LIMIT_ENABLED=false → never blocks."""
        config = SpendingConfig(enabled=False, default_budget=1.0)
        disabled = SpendingChecker(config=config)
        disabled.record_spending("tenant-a", 999999.0)
        allowed, reason = disabled.check_limits("tenant-a")
        assert allowed is True

    def test_get_spending_returns_correct_values(self, checker):
        """get_spending возвращает корректные цифры."""
        checker.record_spending("tenant-a", 25.0)
        spending = checker.get_spending("tenant-a")
        assert spending["tenant_id"] == "tenant-a"
        assert spending["budget"] == 50.0
        assert spending["total_cost"] == 25.0

    def test_set_budget_override(self, checker):
        """set_budget переопределяет бюджет для конкретного tenant."""
        checker.set_budget("tenant-a", 100.0)
        assert checker.get_budget("tenant-a") == 100.0
        # Другой tenant использует default
        assert checker.get_budget("tenant-b") == 50.0

    def test_multiple_tenants_independent(self, checker):
        """Два tenant'а с разными бюджетами работают независимо."""
        checker.set_budget("tenant-premium", 200.0)
        checker.set_budget("tenant-free", 10.0)
        checker.record_spending("tenant-premium", 150.0)
        checker.record_spending("tenant-free", 15.0)
        assert checker.check_limits("tenant-premium") == (True, "")
        assert checker.check_limits("tenant-free")[0] is False
