"""Per-tenant LLM spending tracking and limits.

Tracks spending in-memory and enforces hard limits.
Configurable via env vars and admin API.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpendingConfig:
    """Spending limit configuration."""

    enabled: bool = True
    default_budget: float = 50.0  # USD per period
    period: str = "monthly"  # daily | weekly | monthly

    @classmethod
    def from_env(cls) -> SpendingConfig:
        import os

        return cls(
            enabled=os.environ.get("SPENDING_LIMIT_ENABLED", "true").lower()
            in ("true", "1", "yes"),
            default_budget=float(os.environ.get("SPENDING_DEFAULT_BUDGET", "50.0")),
            period=os.environ.get("SPENDING_BUDGET_PERIOD", "monthly"),
        )


class SpendingChecker:
    """Check and enforce per-tenant LLM spending limits."""

    def __init__(self, config: Optional[SpendingConfig] = None):
        self.config = config or SpendingConfig.from_env()
        # Per-tenant budget overrides: tenant_id -> budget_usd
        self._overrides: dict[str, float] = {}
        # Per-tenant spending: tenant_id -> total_cost
        self._spending: dict[str, float] = {}
        self._lock = threading.Lock()

    def reload(self) -> None:
        """Reload config from env."""
        self.config = SpendingConfig.from_env()

    def get_budget(self, tenant_id: str) -> float:
        """Get budget for a tenant."""
        with self._lock:
            if tenant_id in self._overrides:
                return self._overrides[tenant_id]
        return self.config.default_budget

    def set_budget(self, tenant_id: str, budget: float) -> None:
        """Set per-tenant budget override."""
        with self._lock:
            self._overrides[tenant_id] = budget

    def record_spending(self, tenant_id: str, cost: float) -> None:
        """Record an LLM call cost for a tenant."""
        with self._lock:
            current = self._spending.get(tenant_id, 0.0)
            self._spending[tenant_id] = current + cost

    def get_spending(self, tenant_id: str) -> dict:
        """Get current spending for a tenant."""
        with self._lock:
            total = self._spending.get(tenant_id, 0.0)
        return {
            "tenant_id": tenant_id,
            "budget": self.get_budget(tenant_id),
            "total_cost": round(total, 4),
            "period": self.config.period,
        }

    def check_limits(self, tenant_id: str) -> tuple[bool, str]:
        """Check if tenant has exceeded spending limit.

        Returns (allowed: bool, reason: str).
        If allowed=True, the LLM call can proceed.
        If allowed=False, the call should be blocked.
        """
        if not self.config.enabled:
            return True, ""

        budget = self.get_budget(tenant_id)
        if budget <= 0:
            # 0 means no limit
            return True, ""

        with self._lock:
            spent = self._spending.get(tenant_id, 0.0)

        if spent >= budget:
            logger.warning(
                "[SPENDING] Tenant %s exceeded budget: $%.2f >= $%.2f",
                tenant_id,
                spent,
                budget,
            )
            return False, f"Spending limit exceeded (${spent:.2f} >= ${budget:.2f})"

        return True, ""


# ── Singleton ────────────────────────────────────────────────────────────────

_spending_checker: Optional[SpendingChecker] = None


def get_spending_checker() -> SpendingChecker:
    """Get or create singleton spending checker."""
    global _spending_checker
    if _spending_checker is None:
        _spending_checker = SpendingChecker()
    return _spending_checker


def reload_spending_checker() -> None:
    """Reload spending checker from env."""
    global _spending_checker
    _spending_checker = SpendingChecker()
