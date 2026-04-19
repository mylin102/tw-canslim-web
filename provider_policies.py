"""
Deterministic provider retry and throttling policy contracts.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_NON_CORE_DAILY_BUDGET = 1000


@dataclass(frozen=True)
class ProviderPolicy:
    """Shared retry and throttling contract for one provider."""

    name: str
    max_attempts: int
    base_backoff_seconds: float
    min_interval_seconds: float
    quota_window_seconds: int
    max_requests_per_window: int
    retryable_statuses: tuple[int, ...]
    retryable_exception_names: tuple[str, ...]
    daily_budget_target: int = DEFAULT_NON_CORE_DAILY_BUDGET


_POLICIES = {
    "requests": ProviderPolicy(
        name="requests",
        max_attempts=3,
        base_backoff_seconds=1.0,
        min_interval_seconds=0.2,
        quota_window_seconds=60,
        max_requests_per_window=120,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("RequestException", "ConnectionError", "Timeout"),
    ),
    "finmind": ProviderPolicy(
        name="finmind",
        max_attempts=4,
        base_backoff_seconds=2.0,
        min_interval_seconds=1.0,
        quota_window_seconds=60,
        max_requests_per_window=30,
        retryable_statuses=(402, 429, 500, 502, 503, 504),
        retryable_exception_names=("ConnectionError", "Timeout", "RuntimeError"),
    ),
    "tej": ProviderPolicy(
        name="tej",
        max_attempts=3,
        base_backoff_seconds=3.0,
        min_interval_seconds=1.5,
        quota_window_seconds=60,
        max_requests_per_window=20,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("ConnectionError", "Timeout", "RuntimeError"),
    ),
    "yfinance": ProviderPolicy(
        name="yfinance",
        max_attempts=3,
        base_backoff_seconds=1.5,
        min_interval_seconds=0.5,
        quota_window_seconds=60,
        max_requests_per_window=60,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("HTTPError", "ConnectionError", "Timeout"),
    ),
}


def get_provider_policy(provider_name: str) -> ProviderPolicy:
    """Return the explicit policy for a known provider."""
    normalized = provider_name.strip().lower()
    if normalized not in _POLICIES:
        raise KeyError(f"Unknown provider policy: {provider_name}")
    return _POLICIES[normalized]


def compute_backoff_seconds(policy: ProviderPolicy, attempt: int) -> float:
    """Compute deterministic exponential backoff for a retry attempt."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return policy.base_backoff_seconds * (2 ** (attempt - 1))
